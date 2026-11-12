# Issue backlog: AKS Observability and SRE Incident Lab

**Problem statement.** The checkout service has dashboards but no agreed
reliability target. Alerts fire on raw CPU and on single slow requests, so the
on-call engineer is paged often for nothing and was not paged at all when
checkouts became slow but still succeeded. The goal is to instrument the
service, define SLIs and SLOs with error budgets, alert on burn rate, and
practise the full incident loop from detection to postmortem.

### ISSUE-1: Instrument checkout-api with OpenTelemetry and Prometheus metrics
**Labels:** enhancement, observability, opentelemetry
**Status:** Done - [service/app.py](../service/app.py), [service/metrics.py](../service/metrics.py), [otel-collector/config.yaml](../otel-collector/config.yaml)

**Acceptance criteria**
- [x] Spans for `inventory.lookup`, `payment.authorize` and `order.persist` under the request span.
- [x] `http_requests_total` and `http_request_duration_seconds` histogram with a 0.3 s bucket.
- [x] OTLP export enabled by `OTEL_EXPORTER_OTLP_ENDPOINT`; no-op locally.

**Verification.** `python -m pytest tests -k metrics` passes; `curl localhost:8080/metrics` shows the histogram.

### ISSUE-2: Define latency and availability SLOs with multi-window burn-rate alerts
**Labels:** enhancement, sre, alerting
**Status:** Done - [prometheus/rules/slo-rules.yaml](../prometheus/rules/slo-rules.yaml), [prometheus/tests/slo-rules.test.yaml](../prometheus/tests/slo-rules.test.yaml)

**Acceptance criteria**
- [x] Recording rules for bad-request ratio over 5m, 30m, 1h and 6h.
- [x] Fast burn (14.4x, 1h + 5m, page) and slow burn (6x, 6h + 30m, ticket).
- [x] promtool unit test proves the page fires for a 60% slow scenario and not before.

**Verification.** `promtool test rules prometheus/tests/slo-rules.test.yaml` (runs in CI). Thresholds are cross-checked against the simulator in `tests/test_observability.py`.

### ISSUE-3: Latency incident - checkout slow but returning 200
**Labels:** incident, troubleshooting, sre
**Status:** Resolved (simulated) - [docs/postmortem.md](postmortem.md), [sim/live_incident_demo.py](../sim/live_incident_demo.py)

**Acceptance criteria**
- [x] Incident detected by the SLO alert, not by a user report.
- [x] Cause identified from span timings.
- [x] Mitigation verified by burn rate returning below 1x.
- [x] Blameless postmortem with timeline, budget impact and action items.

**Verification.** `python sim/live_incident_demo.py` ends with `DEMO RESULT: PASS`.

### ISSUE-4: Move metrics, rules and dashboard to Azure Monitor
**Labels:** enhancement, azure-monitor, aks
**Status:** Documented - [docs/azure-monitor.md](azure-monitor.md), [k8s/](../k8s) (needs an AKS cluster)

**Acceptance criteria**
- [ ] Managed Prometheus scrapes the service via PodMonitor.
- [ ] Rule groups created from `slo-rules.yaml` with an action group.
- [ ] Dashboard imported into Azure Managed Grafana; logs queryable in Log Analytics.

**Verification.** In Grafana, the burn-rate panel shows data; a test fault triggers the action group.

### ISSUE-5: Improvement - automatic fallback on dependency timeout
**Labels:** enhancement, improvement, reliability
**Status:** Open (postmortem action item 1)

**Acceptance criteria**
- [ ] 250 ms timeout on inventory lookups; cache used on timeout.
- [ ] Live demo shows burn rate staying under 14.4x with the fault active.

**Verification.** Re-run the live demo without the manual mitigation step.

## Import into GitHub

```bash
python tools/import_issues.py projects/03-aks-observability-sre-lab/docs/issues.md --repo gollapudisrinu18/my-profile --dry-run
python tools/import_issues.py projects/03-aks-observability-sre-lab/docs/issues.md --repo gollapudisrinu18/my-profile
```
