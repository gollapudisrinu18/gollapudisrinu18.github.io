# Runbook: CheckoutLatencyBudgetFastBurn / SlowBurn

**Meaning.** More than 14.4% (fast) or 6% (slow) of checkout requests are taking longer than 300 ms, in both a long and a short window. At 14.4x, 2% of the monthly error budget is spent every hour.

## First 5 minutes
1. Acknowledge the page and open the **checkout-api SLO** dashboard.
2. Check whether the burn rate is still rising (5m line) or already falling.
3. Check recent changes: `helm history checkout-api -n sre-lab`, Azure DevOps release log, feature flags.

## Diagnose
- Latency by span: open slow traces in Application Insights (or `curl /debug/slow-requests` in the lab). Find the span that dominates.
- Saturation: `kubectl top pods -n sre-lab`, HPA status, node pressure.
- Dependency health: inventory database metrics, connection pool errors in logs (KQL in [azure-monitor.md](azure-monitor.md)).

## Mitigate (pick the least risky)
| Cause | Action |
|---|---|
| Slow inventory dependency | Enable cache fallback: `curl -X POST /admin/fallback -d '{"enabled":true}'` (lab) or the equivalent feature flag |
| Bad release | `helm rollback checkout-api <previous> -n sre-lab` |
| CPU saturation | `kubectl scale deploy/checkout-api -n sre-lab --replicas=<n>` |

## Verify
- 5m burn rate below 1x and p99 under 300 ms for 10 minutes.
- Alert resolved.

## Afterwards
Open a postmortem from [postmortem.md](postmortem.md) within 2 working days.
