#!/usr/bin/env python3
"""Deterministic minute-by-minute simulation of the latency incident.

Shows how the multi-window burn-rate alert detects the incident, how long
diagnosis and mitigation take, and how much error budget is consumed.
Writes docs/incident-timeline.json, which the postmortem references.
"""
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import burn_rate as br  # noqa: E402

RPM = 6000                 # 100 req/s
FAULT_START = 60           # inventory DB index rebuild starts (synthetic)
DIAGNOSE_AFTER = 6         # minutes from page to identified cause
MITIGATE_AFTER = 5         # minutes from diagnosis to fallback enabled
FAULT_END = 150            # rebuild finishes
DURATION = 180


def generate(seed=7):
    rng = random.Random(seed)
    series, events = [], {}
    mitigated_at = None
    firing_since = None
    for m in range(DURATION):
        fault = FAULT_START <= m < FAULT_END and (mitigated_at is None or m < mitigated_at)
        bad_share = 0.58 if fault else 0.002
        bad = int(RPM * bad_share * rng.uniform(0.95, 1.05))
        series.append((RPM, bad))

        long_w, short_w, factor, for_min, _ = br.ALERTS["CheckoutLatencyBudgetFastBurn"]
        if br.condition(series, m, long_w, short_w, factor):
            firing_since = m if firing_since is None else firing_since
            if m - firing_since >= for_min and "paged" not in events:
                events["paged"] = m
                events["diagnosed"] = m + DIAGNOSE_AFTER
                mitigated_at = events["diagnosed"] + MITIGATE_AFTER
                events["mitigated"] = mitigated_at
        else:
            firing_since = None
            if "mitigated" in events and "alert_resolved" not in events and m > events["mitigated"]:
                events["alert_resolved"] = m
        if "mitigated" in events and "recovered" not in events and m > events["mitigated"] \
                and br.bad_ratio(series, m, 5) < br.ERROR_BUDGET:
            events["recovered"] = m
    events["fault_start"] = FAULT_START
    return series, events


def main():
    series, ev = generate()
    bad_total = sum(b for _, b in series[FAULT_START:ev["recovered"] + 1])
    consumed = br.budget_consumed(bad_total, RPM)
    peak_5m = max(br.burn_rate(br.bad_ratio(series, m, 5)) for m in range(DURATION))

    rows = [
        ("T+00", ev["fault_start"], "Latency rises: 58% of checkouts slower than 300 ms"),
        (None, ev["paged"], "CheckoutLatencyBudgetFastBurn fires (1h and 5m burn > 14.4x for 2m) - on-call paged"),
        (None, ev["diagnosed"], "Slow-request exemplars show inventory.lookup ~800 ms; payment and persist normal"),
        (None, ev["mitigated"], "Mitigation: inventory cache fallback enabled"),
        (None, ev["recovered"], "5-minute bad ratio back under 1% - user impact over"),
        (None, ev["alert_resolved"], "Page alert resolves (5m burn drops below 14.4x)"),
    ]
    print("Latency incident simulation (synthetic, 100 req/s, SLO 99% <= 300 ms)\n")
    print(f"{'minute':>6}  {'since start':>11}  event")
    timeline = []
    for _, m, text in sorted(rows, key=lambda r: r[1]):
        rel = m - ev["fault_start"]
        print(f"{m:>6}  {'T+%02d min' % rel:>11}  {text}")
        timeline.append({"minute": m, "t_plus_min": rel, "event": text})
    ttd = ev["paged"] - ev["fault_start"]
    ttm = ev["mitigated"] - ev["fault_start"]
    print(f"\nTime to detect:   {ttd} min")
    print(f"Time to mitigate: {ttm} min")
    print(f"Peak 5m burn rate: {peak_5m:.1f}x")
    print(f"Bad requests: {bad_total:,}  -> {consumed:.1%} of the 30-day latency error budget")

    out = {
        "slo": "99% of POST /api/checkout <= 300 ms over 30 days",
        "requests_per_minute": RPM,
        "time_to_detect_min": ttd,
        "time_to_mitigate_min": ttm,
        "peak_burn_rate_5m": round(peak_5m, 1),
        "bad_requests": bad_total,
        "error_budget_consumed": round(consumed, 4),
        "timeline": timeline,
    }
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs", "incident-timeline.json")
    with open(path, "w") as fh:
        json.dump(out, fh, indent=2)
    print(f"\nWrote {os.path.relpath(path)}")
    return out


if __name__ == "__main__":
    main()
