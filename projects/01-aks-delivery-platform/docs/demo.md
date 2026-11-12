# Demo: AKS Delivery Platform with Azure DevOps

**Format:** Captioned MP4 screen recording of the browser walkthrough, plus the walkthrough itself

- Browser walkthrough (captioned, keyboard accessible): https://gollapudisrinu18.github.io/my-profile/demos/aks-delivery-platform.html
- Video (MP4, captions in WebVTT): https://gollapudisrinu18.github.io/my-profile/assets/video/aks-delivery-platform.mp4
- Run it yourself: `python scripts/local_release_demo.py` from `projects/01-aks-delivery-platform`

## Recording script

| Scene | Show on screen | Caption |
|---|---|---|
| 1 | Title card | A bad release reaches the cluster. The smoke test catches it and the pipeline rolls back on its own. |
| 2 | Diagram: System view | System view |
| 3 | Diagram: Deployment, smoke test and rollback sequence | Deployment, smoke test and rollback sequence |
| 4 | Terminal: Revision 1: deploy orders-api 1.0.0 | Revision 1 deploys orders-api 1.0.0. All four smoke checks pass. |
| 5 | Terminal: Revision 2: deploy orders-api 1.1.0 (contains a simulated defect) | Revision 2 deploys 1.1.0 with a simulated defect. Probes stay green but the orders API returns HTTP 500, so the smoke test fails and the release is rolled back to revision 1. |
| 6 | Terminal: Result | The release history shows the rollback as revision 3, and /version confirms 1.0.0 is serving again. |
| 7 | Result card | Release 1.1.0 failed the smoke test (HTTP 500 on /api/v1/orders). The script rolled back to revision 1 and the restored 1.0.0 passed every check. Verified locally; Azure steps are scripted. |

## Captured output

The walkthrough uses this output, captured from a real run by `tools/capture_demos.py`:

```text
$ python scripts/local_release_demo.py

=== Revision 1: deploy orders-api 1.0.0 ===
Deployed orders-api 1.0.0 as revision 1
Smoke test against http://127.0.0.1:49663
  [PASS] liveness /healthz returns 200 (HTTP 200)
  [PASS] /version reports 1.0.0 (HTTP 200, version=1.0.0)
  [PASS] GET /api/v1/orders returns orders (HTTP 200)
  [PASS] GET /api/v1/orders/ORD-1001 returns the order (HTTP 200)
SMOKE TEST PASSED

=== Revision 2: deploy orders-api 1.1.0 (contains a simulated defect) ===
Deployed orders-api 1.1.0 as revision 2
Smoke test against http://127.0.0.1:49663
  [PASS] liveness /healthz returns 200 (HTTP 200)
  [PASS] /version reports 1.1.0 (HTTP 200, version=1.1.0)
  [FAIL] GET /api/v1/orders returns orders (HTTP 500)
  [FAIL] GET /api/v1/orders/ORD-1001 returns the order (HTTP 500)
SMOKE TEST FAILED

Smoke test failed -> rolling back orders-api to revision 1
Rollback created revision 3, serving 1.0.0
Smoke test against http://127.0.0.1:49663
  [PASS] liveness /healthz returns 200 (HTTP 200)
  [PASS] /version reports 1.0.0 (HTTP 200, version=1.0.0)
  [PASS] GET /api/v1/orders returns orders (HTTP 200)
  [PASS] GET /api/v1/orders/ORD-1001 returns the order (HTTP 200)
SMOKE TEST PASSED
ROLLBACK VERIFIED

=== Result ===

$ helm history orders-api   (local equivalent)
  REVISION TAG     STATUS      DESCRIPTION
  1        1.0.0   superseded  Upgrade complete
  2        1.1.0   superseded  Upgrade complete
  3        1.0.0   deployed    Rollback to 1

Live /version after the pipeline run: {"environment":"local","version":"1.0.0"}


DEMO RESULT: PASS - bad release was rolled back to 1.0.0
```
