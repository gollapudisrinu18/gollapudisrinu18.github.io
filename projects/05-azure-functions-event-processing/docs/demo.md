# Demo: Azure Functions Event-Driven Processing

**Format:** Captioned MP4 screen recording of the browser walkthrough, plus the walkthrough itself

- Browser walkthrough (captioned, keyboard accessible): https://gollapudisrinu18.github.io/my-profile/demos/azure-functions-event-processing.html
- Video (MP4, captions in WebVTT): https://gollapudisrinu18.github.io/my-profile/assets/video/azure-functions-event-processing.mp4
- Run it yourself: `python src/local_runtime.py` from `projects/05-azure-functions-event-processing`

## Recording script

| Scene | Show on screen | Caption |
|---|---|---|
| 1 | Title card | The same order arrives three times and is processed once. |
| 2 | Diagram: Architecture | Architecture |
| 3 | Terminal: Scenario 1: duplicate delivery (same event sent twice + lost ack) | Duplicate delivery and a lost acknowledgement: two of three deliveries are recognised as duplicates. |
| 4 | Terminal: Scenario 2: transient downstream failure (2 x HTTP 503) | Two transient 503 errors are retried; the third attempt succeeds. |
| 5 | Terminal: Scenario 3: malformed message | A malformed message goes straight to the poison queue. |
| 6 | Terminal: Scenario 4: downstream down for every attempt | A message that fails on every attempt is moved to poison after five dequeues. |
| 7 | Terminal: Result | The ledger holds exactly one entry per order. |
| 8 | Result card | ORD-1 was delivered three times and recorded once. A transient failure succeeded on the third try; a malformed message and a message that failed five times went to the poison queue. |

## Captured output

The walkthrough uses this output, captured from a real run by `tools/capture_demos.py`:

```text
$ python src/local_runtime.py
=== Scenario 1: duplicate delivery (same event sent twice + lost ack) ===
  msg 6b7fc6d0 try 1: processed
  msg 6b7fc6d0: ack lost -> queue redelivers it
  msg 8e7831d3 try 1: duplicate
  msg 6b7fc6d0 try 2: duplicate

=== Scenario 2: transient downstream failure (2 x HTTP 503) ===
  msg b560e25d try 1: ledger service returned 503 -> retry
  msg b560e25d try 2: ledger service returned 503 -> retry
  msg b560e25d try 3: processed

=== Scenario 3: malformed message ===
  msg e14c86bd try 1: permanent error (missing fields: eventId, amount, currency) -> poison

=== Scenario 4: downstream down for every attempt ===
  msg 96a67ef5 try 1: ledger service returned 503 -> retry
  msg 96a67ef5 try 2: ledger service returned 503 -> retry
  msg 96a67ef5 try 3: ledger service returned 503 -> retry
  msg 96a67ef5 try 4: ledger service returned 503 -> retry
  msg 96a67ef5 try 5: ledger service returned 503 -> maxDequeueCount reached -> poison

=== Result ===
  ledger entries: [('ORD-1', 499.0, 'INR'), ('ORD-2', 1250.0, 'INR')]
  poison queue:   [('e14c86bd', 'missing fields: eventId, amount, currency'), ('96a67ef5', 'ledger service returned 503')]
DEMO RESULT: PASS - ORD-1 processed exactly once despite 3 deliveries
```
