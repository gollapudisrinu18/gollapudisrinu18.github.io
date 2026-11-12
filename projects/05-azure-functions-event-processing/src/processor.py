"""Order event processing with idempotency, retry classification and poison handling.

Queue delivery is at-least-once: the same message can arrive twice (for
example when the function finishes but the delete/ack is lost). Processing
is made idempotent with a key derived from the event, stored before the side
effect and marked complete after it.
"""
import json
import logging
import sqlite3
import threading
import time

log = logging.getLogger("order-processor")


class TransientError(Exception):
    """Downstream temporarily unavailable - let the queue retry."""


class PermanentError(Exception):
    """Message can never succeed (bad schema) - do not retry."""


REQUIRED = ("eventId", "orderId", "amount", "currency")


def parse(body):
    try:
        event = json.loads(body)
    except (ValueError, TypeError) as exc:
        raise PermanentError(f"invalid JSON: {exc}") from exc
    missing = [k for k in REQUIRED if k not in event]
    if missing:
        raise PermanentError(f"missing fields: {', '.join(missing)}")
    if not isinstance(event["amount"], (int, float)) or event["amount"] <= 0:
        raise PermanentError("amount must be a positive number")
    return event


# ---------------------------------------------------------------- stores
class InMemoryIdempotencyStore:
    def __init__(self):
        self._lock = threading.Lock()
        self._rows = {}

    def claim(self, key, lease_seconds=60):
        """Return 'claimed', 'done' or 'busy'."""
        now = time.time()
        with self._lock:
            row = self._rows.get(key)
            if row and row["status"] == "done":
                return "done"
            if row and row["status"] == "processing" and row["lease_until"] > now:
                return "busy"
            self._rows[key] = {"status": "processing", "lease_until": now + lease_seconds}
            return "claimed"

    def complete(self, key):
        with self._lock:
            self._rows[key] = {"status": "done", "lease_until": 0}

    def release(self, key):
        with self._lock:
            if self._rows.get(key, {}).get("status") == "processing":
                del self._rows[key]


class SqliteIdempotencyStore:
    """Durable local store with the same semantics (used by the local runtime)."""

    def __init__(self, path=":memory:"):
        self.db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self.db.execute("CREATE TABLE IF NOT EXISTS idem (key TEXT PRIMARY KEY, status TEXT, lease_until REAL)")
        self._lock = threading.Lock()

    def claim(self, key, lease_seconds=60):
        now = time.time()
        with self._lock:
            self.db.execute("BEGIN IMMEDIATE")
            row = self.db.execute("SELECT status, lease_until FROM idem WHERE key=?", (key,)).fetchone()
            if row and row[0] == "done":
                self.db.execute("COMMIT")
                return "done"
            if row and row[0] == "processing" and row[1] > now:
                self.db.execute("COMMIT")
                return "busy"
            self.db.execute("INSERT OR REPLACE INTO idem VALUES (?, 'processing', ?)", (key, now + lease_seconds))
            self.db.execute("COMMIT")
            return "claimed"

    def complete(self, key):
        with self._lock:
            self.db.execute("UPDATE idem SET status='done', lease_until=0 WHERE key=?", (key,))

    def release(self, key):
        with self._lock:
            self.db.execute("DELETE FROM idem WHERE key=? AND status='processing'", (key,))


class TableIdempotencyStore:
    """Azure Table Storage implementation used in Azure (azure-data-tables).

    claim() relies on create_entity failing with ResourceExistsError, which
    gives an atomic "insert if absent" across function instances.
    """

    def __init__(self, connection_string, table="idempotency"):
        from azure.data.tables import TableServiceClient  # imported only in Azure
        self.table = TableServiceClient.from_connection_string(connection_string).create_table_if_not_exists(table)

    def claim(self, key, lease_seconds=60):
        from azure.core import MatchConditions
        from azure.core.exceptions import ResourceExistsError, ResourceModifiedError
        now = time.time()
        try:
            self.table.create_entity({"PartitionKey": "orders", "RowKey": key,
                                      "status": "processing", "lease_until": now + lease_seconds})
            return "claimed"
        except ResourceExistsError:
            entity = self.table.get_entity("orders", key)
            if entity["status"] == "done":
                return "done"
            if entity["lease_until"] > now:
                return "busy"
            entity["lease_until"] = now + lease_seconds
            try:  # take over an expired lease, guarded by the ETag
                self.table.update_entity(entity, etag=entity.metadata["etag"],
                                         match_condition=MatchConditions.IfNotModified)
                return "claimed"
            except ResourceModifiedError:
                return "busy"

    def complete(self, key):
        self.table.upsert_entity({"PartitionKey": "orders", "RowKey": key, "status": "done", "lease_until": 0})

    def release(self, key):
        self.table.delete_entity("orders", key)


# ---------------------------------------------------------------- processing
class Ledger:
    """Side effect target (stands in for a payments/orders database)."""

    def __init__(self):
        self.entries = []
        self.fail_next = 0  # inject transient failures

    def record(self, event):
        if self.fail_next > 0:
            self.fail_next -= 1
            raise TransientError("ledger service returned 503")
        self.entries.append((event["orderId"], event["amount"], event["currency"]))


def log_event(level, msg, **fields):
    log.log(level, json.dumps({"msg": msg, **fields}, sort_keys=True))


def process(body, store, ledger, message_id="local", dequeue_count=1):
    """Process one queue message. Returns an outcome string.

    Raises TransientError so the Functions host leaves the message on the
    queue for another attempt (up to maxDequeueCount, then *-poison).
    Raises PermanentError for messages that must go straight to poison.
    """
    event = parse(body)
    key = f"{event['orderId']}:{event['eventId']}"
    ctx = {"orderId": event["orderId"], "eventId": event["eventId"],
           "messageId": message_id, "dequeueCount": dequeue_count}

    state = store.claim(key)
    if state == "done":
        log_event(logging.INFO, "duplicate ignored", outcome="duplicate", **ctx)
        return "duplicate"
    if state == "busy":
        log_event(logging.WARNING, "another instance is processing", outcome="busy", **ctx)
        raise TransientError("in progress elsewhere")

    try:
        ledger.record(event)
    except TransientError as exc:
        store.release(key)
        log_event(logging.WARNING, "transient failure, will retry", outcome="retry", error=str(exc), **ctx)
        raise
    store.complete(key)
    log_event(logging.INFO, "order processed", outcome="processed", **ctx)
    return "processed"
