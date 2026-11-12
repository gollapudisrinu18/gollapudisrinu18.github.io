# Postmortem: checkout latency SLO breach (simulated)

> **Simulated incident.** This postmortem describes the lab scenario produced by
> `sim/incident_sim.py` (timeline in [incident-timeline.json](incident-timeline.json))
> and reproduced live by `sim/live_incident_demo.py`. Services, data and times are synthetic.

| | |
|---|---|
| **Severity** | SEV-2 (degraded, no data loss) |
| **SLO affected** | 99% of `POST /api/checkout` within 300 ms over 30 days |
| **Duration of user impact** | 31 minutes (T+0 to T+31) |
| **Time to detect** | 16 minutes |
| **Time to mitigate** | 27 minutes |
| **Error budget consumed** | 3.6% of the 30-day latency budget (93,959 slow requests at 100 req/s) |
| **Peak burn rate (5m)** | 59.1x |

## Summary
An index rebuild on the inventory database (synthetic) made inventory lookups take about 800 ms for most requests. Checkout requests stayed successful (HTTP 200) but 58% of them exceeded the 300 ms objective. The fast-burn latency alert paged the on-call engineer, slow-request traces pointed to `inventory.lookup`, and enabling the inventory cache fallback brought latency back within the SLO.

## Timeline (minutes after the fault started)
| T+ | Event |
|---|---|
| 0 | Inventory lookups slow down; 58% of checkouts take more than 300 ms |
| 16 | `CheckoutLatencyBudgetFastBurn` fires: 1h and 5m burn rates above 14.4x for 2 minutes. On-call paged |
| 22 | Trace review shows `inventory.lookup` at ~800 ms while `payment.authorize` and `order.persist` are normal |
| 27 | Cache fallback enabled for inventory reads |
| 30 | Page alert resolves |
| 31 | 5-minute bad ratio back under 1%; user impact over |

## What went well
- The burn-rate alert ignored short blips but paged within 16 minutes of a sustained breach.
- Span-level timing made the cause obvious without guessing.
- A pre-built fallback existed and was safe to enable.

## What went wrong
- Error rate stayed at 0%, so the availability alert never fired. Only the latency SLO caught this.
- No alert existed on the dependency itself; detection depended on the user-facing SLO.
- The database maintenance was not on the change calendar used by on-call.

## Root cause and contributing factors
- **Trigger:** inventory database index rebuild during business hours.
- **Contributing:** checkout calls inventory synchronously with no timeout below the SLO threshold; fallback was manual.

## Action items
| # | Action | Type | Owner | Status |
|---|---|---|---|---|
| 1 | Add a 250 ms timeout on inventory lookups with automatic cache fallback | Prevent | Service team | Open |
| 2 | Alert on `inventory.lookup` p95 > 200 ms for 5 minutes | Detect | SRE | Open |
| 3 | Add database maintenance to the shared change calendar and block it in peak hours | Prevent | DBA | Open |
| 4 | Add the fallback toggle to the runbook with a one-command script | Mitigate | SRE | Done ([runbook.md](runbook.md)) |

## Lessons
Latency SLOs catch "successful but slow" failures that error-rate alerts miss. Multi-window burn-rate alerts trade a few minutes of detection time for far fewer false pages.
