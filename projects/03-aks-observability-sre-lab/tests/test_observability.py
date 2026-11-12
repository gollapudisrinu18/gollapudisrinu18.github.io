import os
import subprocess
import sys

import yaml

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path[:0] = [os.path.join(ROOT, "service"), os.path.join(ROOT, "sim")]

import burn_rate as br  # noqa: E402
from app import create_app  # noqa: E402
from metrics import parse  # noqa: E402


def test_metrics_exposition_counts_requests_and_buckets():
    c = create_app(seed=1).test_client()
    for _ in range(3):
        assert c.post("/api/checkout", json={}).status_code == 200
    m = parse(c.get("/metrics").get_data(as_text=True))
    count = [v for (n, _), v in m.items() if n == "http_request_duration_seconds_count"]
    fast = [v for (n, l), v in m.items() if n == "http_request_duration_seconds_bucket" and ("le", "0.3") in l]
    assert count == [3.0] and fast == [3.0]


def test_fault_and_fallback_toggle():
    c = create_app(seed=1).test_client()
    c.post("/admin/fault", json={"latency_ms": 400, "ratio": 1.0})
    c.post("/api/checkout", json={})
    slow = c.get("/debug/slow-requests").get_json()
    assert slow and max(slow[0]["spans_ms"], key=slow[0]["spans_ms"].get) == "inventory.lookup"
    c.post("/admin/fallback", json={"enabled": True})
    assert c.post("/api/checkout", json={}).get_json()["fallback"] is True


def test_burn_rate_math():
    series = [(100, 1)] * 60
    assert abs(br.burn_rate(br.bad_ratio(series, 59, 60)) - 1.0) < 1e-9
    series = [(100, 1)] * 55 + [(100, 60)] * 5
    assert br.condition(series, 59, 5, 5, 14.4)
    assert not br.condition(series, 59, 60, 5, 14.4)  # long window not yet over 14.4%


def test_budget_consumed():
    # 1% budget of 30 days at 6000 rpm = 2,592,000 bad requests
    assert abs(br.budget_consumed(2_592_000, 6000) - 1.0) < 1e-9


def test_rule_thresholds_match_simulator():
    rules = yaml.safe_load(open(os.path.join(ROOT, "prometheus", "rules", "slo-rules.yaml")))
    alerts = {r["alert"]: r for g in rules["groups"] for r in g["rules"] if "alert" in r}
    assert set(alerts) == set(br.ALERTS)
    for name, (_, _, factor, for_min, severity) in br.ALERTS.items():
        assert f"({factor:g} * 0.01)" in alerts[name]["expr"]
        assert alerts[name]["for"] == f"{for_min}m"
        assert alerts[name]["labels"]["severity"] == severity


def test_simulation_detects_and_recovers():
    out = subprocess.run([sys.executable, os.path.join(ROOT, "sim", "incident_sim.py")],
                         capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    assert "Time to detect" in out.stdout and "Page alert resolves" in out.stdout


def test_live_demo():
    out = subprocess.run([sys.executable, os.path.join(ROOT, "sim", "live_incident_demo.py")],
                         capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stdout + out.stderr
    assert "DEMO RESULT: PASS" in out.stdout


def test_postmortem_numbers_match_simulation():
    import json
    t = json.load(open(os.path.join(ROOT, "docs", "incident-timeline.json")))
    pm = open(os.path.join(ROOT, "docs", "postmortem.md")).read()
    assert f"| **Time to detect** | {t['time_to_detect_min']} minutes |" in pm
    assert f"| **Time to mitigate** | {t['time_to_mitigate_min']} minutes |" in pm
    assert f"{t['bad_requests']:,} slow requests" in pm
    assert f"{t['error_budget_consumed']:.1%}" in pm
    assert f"{t['peak_burn_rate_5m']}x" in pm
