# Issue backlog: Azure Functions Event-Driven Processing

**Problem statement.** Order events arrive on an Azure Storage queue. Customers
were occasionally charged twice because the queue redelivered messages after a
timeout, and malformed events kept retrying until they were silently dropped.
The goal is a queue-triggered function that processes each event exactly once
in effect, retries only what can succeed, parks the rest in a poison queue, and
logs every decision in a queryable format.

### ISSUE-1: Idempotent processing for duplicate deliveries
**Labels:** bug, reliability, azure-functions
**Status:** Done - [src/processor.py](../src/processor.py), [tests/test_processor.py](../tests/test_processor.py)

**Acceptance criteria**
- [x] Idempotency key `orderId:eventId` claimed before the side effect, completed after it.
- [x] Duplicate or redelivered messages return `duplicate` and do not touch the ledger.
- [x] Claim is atomic across instances (Table Storage insert-if-absent; ETag for expired leases).

**Verification.** `python -m pytest tests -k duplicate`; `python src/local_runtime.py` shows ORD-1 delivered 3 times and recorded once.

### ISSUE-2: Retry transient failures, poison permanent ones
**Labels:** enhancement, reliability
**Status:** Done - [src/function_app.py](../src/function_app.py), [src/host.json](../src/host.json)

**Acceptance criteria**
- [x] Transient errors release the claim and re-raise so the queue retries.
- [x] `maxDequeueCount` 5 and a 10 s visibility timeout in `host.json`.
- [x] Schema errors go straight to `orders-poison` with a reason, without using retries.
- [x] A poison handler logs every parked message for review.

**Verification.** Local runtime scenarios 2–4 show retry then success, immediate poison, and poison after 5 attempts.

### ISSUE-3: Structured logging for every outcome
**Labels:** enhancement, observability
**Status:** Done - `log_event` in [src/processor.py](../src/processor.py)

**Acceptance criteria**
- [x] JSON log with `outcome`, `orderId`, `eventId`, `messageId`, `dequeueCount`.
- [x] KQL query in the README groups outcomes per minute.

**Verification.** `python src/local_runtime.py --verbose`; `test_structured_logs`.

### ISSUE-4: Troubleshoot - messages go to poison immediately after deployment
**Labels:** bug, troubleshooting
**Status:** Runbook

**Context.** After switching producers, every message lands in `orders-poison` on the first try.

**Acceptance criteria**
- [ ] Root cause found: producer sends plain text while `host.json` expects base64.
- [ ] Producer and `messageEncoding` agree.

**Verification.** `az storage message peek -q orders-poison ...` shows non-base64 content; after fixing, `send-test-messages.sh` messages are processed.

### ISSUE-5: Improvement - move to Service Bus sessions for ordering
**Labels:** enhancement, improvement
**Status:** Open

**Acceptance criteria**
- [ ] Events for the same order processed in order using Service Bus sessions.
- [ ] Built-in duplicate detection window compared with the table-based approach.

**Verification.** Out-of-order test events for one order are applied in sequence.

## Import into GitHub

```bash
python tools/import_issues.py projects/05-azure-functions-event-processing/docs/issues.md --repo gollapudisrinu18/my-profile --dry-run
python tools/import_issues.py projects/05-azure-functions-event-processing/docs/issues.md --repo gollapudisrinu18/my-profile
```
