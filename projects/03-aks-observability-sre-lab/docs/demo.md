# Demo: AKS Observability and SRE Incident Lab

**Format:** Captioned MP4 screen recording of the browser walkthrough, plus the walkthrough itself

- Browser walkthrough (captioned, keyboard accessible): https://gollapudisrinu18.github.io/my-profile/demos/aks-observability-sre-lab.html
- Video (MP4, captions in WebVTT): https://gollapudisrinu18.github.io/my-profile/assets/video/aks-observability-sre-lab.mp4
- Run it yourself: `python sim/live_incident_demo.py` from `projects/03-aks-observability-sre-lab`

## Recording script

| Scene | Show on screen | Caption |
|---|---|---|
| 1 | Title card | Checkout gets slow but keeps returning 200. The SLO alert catches it, traces point to the cause, and a fallback restores service. |
| 2 | Diagram: Telemetry flow | Telemetry flow |
| 3 | Diagram: Incident response sequence | Incident response sequence |
| 4 | Terminal: 1. Baseline: steady traffic | Baseline: steady traffic, no requests slower than 300 ms, burn rate 0x. |
| 5 | Terminal: 2. Fault: inventory dependency slows down (800 ms on 60% of calls) | Fault injected in the inventory dependency. More than half of the requests miss the 300 ms objective and the burn rate passes the 14.4x paging threshold. |
| 6 | Terminal: 3. Diagnose: slow-request span timings (exemplars) | Slow-request span timings show inventory.lookup taking about 800 ms while payment and persistence stay normal. |
| 7 | Terminal: 4. Mitigate: enable inventory cache fallback | The inventory cache fallback is enabled and the burn rate drops back to 0x. |
| 8 | Terminal: Result | Detected, diagnosed, mitigated and recovered. |
| 9 | Result card | Simulated incident: the latency SLO page fired 16 minutes after the fault, span timings pointed to inventory.lookup, the cache fallback mitigated it at T+27 min, and 3.6% of the monthly error budget was used. In the live demo the burn rate went from 0x to over 14.4x and back to 0x. |

## Captured output

The walkthrough uses this output, captured from a real run by `tools/capture_demos.py`:

```text
$ python sim/live_incident_demo.py
=== 1. Baseline: steady traffic ===
  baseline   requests= 313  slower than 300ms=   0  bad ratio=  0.0%  burn rate=  0.0x  [ok]

=== 2. Fault: inventory dependency slows down (800 ms on 60% of calls) ===
  incident   requests=  47  slower than 300ms=  30  bad ratio= 63.8%  burn rate= 63.8x  [BREACH]
  DETECTED: burn rate above 14.4x -> CheckoutLatencyBudgetFastBurn would page

=== 3. Diagnose: slow-request span timings (exemplars) ===
  859 ms total: inventory.lookup=818ms, order.persist=12ms, payment.authorize=28ms
  857 ms total: inventory.lookup=820ms, order.persist=9ms, payment.authorize=28ms
  858 ms total: inventory.lookup=818ms, order.persist=11ms, payment.authorize=28ms
  Slowest span: inventory.lookup

=== 4. Mitigate: enable inventory cache fallback ===
  mitigated  requests= 401  slower than 300ms=   0  bad ratio=  0.0%  burn rate=  0.0x  [ok]

=== Result ===
  baseline 0.0x -> incident 63.8x -> after mitigation 0.0x
DEMO RESULT: PASS - detected, diagnosed, mitigated and recovered
```
