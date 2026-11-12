#!/usr/bin/env python3
"""Local queue runtime that mimics Azure Storage Queue + Functions host semantics.

- at-least-once delivery, dequeue_count per message
- failed messages become visible again and are retried
- after maxDequeueCount (5, as in host.json) messages move to <queue>-poison
- an injected "lost ack" redelivers a message that was already processed

Runs the same processor.process() used by function_app.py.
"""
import json
import logging
import os
import sys
import uuid
from collections import deque

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from processor import (Ledger, PermanentError, SqliteIdempotencyStore,  # noqa: E402
                       TransientError, process)

MAX_DEQUEUE = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "host.json")))[
    "extensions"]["queues"]["maxDequeueCount"]


class LocalQueue:
    def __init__(self):
        self.messages = deque()
        self.poison = []

    def put(self, body):
        self.messages.append({"id": str(uuid.uuid4())[:8], "body": body, "dequeue_count": 0})


def run(queue, store, ledger, lose_ack_for=(), echo=print):
    lost = set(lose_ack_for)
    while queue.messages:
        m = queue.messages.popleft()
        m["dequeue_count"] += 1
        try:
            outcome = process(m["body"], store, ledger, m["id"], m["dequeue_count"])
            echo(f"  msg {m['id']} try {m['dequeue_count']}: {outcome}")
            key = json.loads(m["body"]).get("eventId")
            if key in lost:  # function succeeded but the delete never reached the queue
                lost.discard(key)
                echo(f"  msg {m['id']}: ack lost -> queue redelivers it")
                queue.messages.append(m)
        except PermanentError as exc:
            echo(f"  msg {m['id']} try {m['dequeue_count']}: permanent error ({exc}) -> poison")
            queue.poison.append({**m, "reason": str(exc)})
        except TransientError as exc:
            if m["dequeue_count"] >= MAX_DEQUEUE:
                echo(f"  msg {m['id']} try {m['dequeue_count']}: {exc} -> maxDequeueCount reached -> poison")
                queue.poison.append({**m, "reason": str(exc)})
            else:
                echo(f"  msg {m['id']} try {m['dequeue_count']}: {exc} -> retry")
                queue.messages.append(m)


def main():
    # --verbose prints the structured JSON log line for every attempt
    verbose = "--verbose" in sys.argv
    logging.basicConfig(level=logging.INFO if verbose else logging.ERROR, format="    log %(message)s")
    q, store, ledger = LocalQueue(), SqliteIdempotencyStore(), Ledger()
    order = lambda eid, oid, amt: json.dumps({"eventId": eid, "orderId": oid, "amount": amt, "currency": "INR"})

    print("=== Scenario 1: duplicate delivery (same event sent twice + lost ack) ===")
    q.put(order("evt-1", "ORD-1", 499.0))
    q.put(order("evt-1", "ORD-1", 499.0))
    run(q, store, ledger, lose_ack_for=["evt-1"])

    print("\n=== Scenario 2: transient downstream failure (2 x HTTP 503) ===")
    ledger.fail_next = 2
    q.put(order("evt-2", "ORD-2", 1250.0))
    run(q, store, ledger)

    print("\n=== Scenario 3: malformed message ===")
    q.put('{"orderId": "ORD-3"}')
    run(q, store, ledger)

    print("\n=== Scenario 4: downstream down for every attempt ===")
    ledger.fail_next = 99
    q.put(order("evt-4", "ORD-4", 75.0))
    run(q, store, ledger)
    ledger.fail_next = 0

    print("\n=== Result ===")
    print("  ledger entries:", ledger.entries)
    print("  poison queue:  ", [(p["id"], p["reason"]) for p in q.poison])
    ok = (ledger.entries.count(("ORD-1", 499.0, "INR")) == 1
          and ("ORD-2", 1250.0, "INR") in ledger.entries
          and len(ledger.entries) == 2 and len(q.poison) == 2)
    print("DEMO RESULT:", "PASS - ORD-1 processed exactly once despite 3 deliveries" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
