import json
import logging
import os
import subprocess
import sys

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..", "src")
sys.path.insert(0, ROOT)
from processor import (InMemoryIdempotencyStore, Ledger, PermanentError,  # noqa: E402
                       SqliteIdempotencyStore, TransientError, process)


def event(eid="e1", oid="O1", amount=10.0):
    return json.dumps({"eventId": eid, "orderId": oid, "amount": amount, "currency": "INR"})


@pytest.fixture(params=[InMemoryIdempotencyStore, SqliteIdempotencyStore])
def store(request):
    return request.param()


def test_duplicate_delivery_processed_once(store):
    ledger = Ledger()
    assert process(event(), store, ledger) == "processed"
    assert process(event(), store, ledger) == "duplicate"
    assert process(event(), store, ledger, dequeue_count=2) == "duplicate"
    assert ledger.entries == [("O1", 10.0, "INR")]


def test_same_order_different_event_is_processed(store):
    ledger = Ledger()
    process(event("e1"), store, ledger)
    process(event("e2"), store, ledger)
    assert len(ledger.entries) == 2


def test_transient_failure_releases_claim_so_retry_succeeds(store):
    ledger = Ledger()
    ledger.fail_next = 1
    with pytest.raises(TransientError):
        process(event(), store, ledger)
    assert process(event(), store, ledger, dequeue_count=2) == "processed"
    assert len(ledger.entries) == 1


def test_concurrent_claim_is_busy(store):
    assert store.claim("k") == "claimed"
    assert store.claim("k") == "busy"
    store.complete("k")
    assert store.claim("k") == "done"


def test_expired_lease_can_be_reclaimed(store):
    assert store.claim("k", lease_seconds=-1) == "claimed"
    assert store.claim("k") == "claimed"


@pytest.mark.parametrize("body", ["not json", '{"orderId": "x"}',
                                  json.dumps({"eventId": "e", "orderId": "o", "amount": -5, "currency": "INR"})])
def test_permanent_errors(body, store):
    with pytest.raises(PermanentError):
        process(body, store, Ledger())


def test_structured_logs(store, caplog):
    caplog.set_level(logging.INFO, logger="order-processor")
    process(event(), store, Ledger(), message_id="m-1")
    record = json.loads(caplog.records[-1].getMessage())
    assert record["outcome"] == "processed" and record["messageId"] == "m-1"


def test_local_runtime_demo():
    out = subprocess.run([sys.executable, os.path.join(ROOT, "local_runtime.py")], capture_output=True, text=True)
    assert out.returncode == 0, out.stdout + out.stderr
    assert "DEMO RESULT: PASS" in out.stdout
    assert "maxDequeueCount reached -> poison" in out.stdout
