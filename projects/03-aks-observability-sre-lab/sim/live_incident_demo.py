#!/usr/bin/env python3
"""Live, compressed version of the incident against the real instrumented service.

Starts checkout-api locally, sends steady traffic, injects latency in the
inventory dependency, detects the SLO breach from scraped /metrics, diagnoses
it from slow-request span timings, mitigates with the cache fallback and
verifies recovery. Windows are seconds instead of hours so it runs in ~30 s.
"""
import json
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SERVICE = os.path.join(HERE, "..", "service")
sys.path.insert(0, SERVICE)
sys.path.insert(0, HERE)
from metrics import parse  # noqa: E402
import burn_rate as br  # noqa: E402

THRESHOLD = 14.4  # same page threshold as the Prometheus rule


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Lab:
    def __init__(self):
        self.port = free_port()
        self.base = f"http://127.0.0.1:{self.port}"
        env = dict(os.environ, PORT=str(self.port))
        env.pop("OTEL_EXPORTER_OTLP_ENDPOINT", None)
        self.proc = subprocess.Popen([sys.executable, os.path.join(SERVICE, "app.py")], env=env,
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(100):
            try:
                urllib.request.urlopen(self.base + "/healthz", timeout=1)
                break
            except Exception:
                time.sleep(0.1)
        self.running = True
        self.threads = [threading.Thread(target=self._load, daemon=True) for _ in range(6)]
        for t in self.threads:
            t.start()

    def _load(self):
        while self.running:
            try:
                self.post("/api/checkout", {})
            except Exception:
                pass
            time.sleep(0.02)

    def post(self, path, body):
        req = urllib.request.Request(self.base + path, data=json.dumps(body).encode(), method="POST",
                                     headers={"Content-Type": "application/json"})
        return json.loads(urllib.request.urlopen(req, timeout=10).read())

    def get(self, path):
        return urllib.request.urlopen(self.base + path, timeout=5).read().decode()

    def counts(self):
        m = parse(self.get("/metrics"))
        good = total = 0
        for (name, labels), v in m.items():
            d = dict(labels)
            if name == "http_request_duration_seconds_bucket" and d.get("le") == "0.3":
                good = v
            if name == "http_request_duration_seconds_count":
                total = v
        return total, total - good

    def window(self, seconds):
        t0, b0 = self.counts()
        time.sleep(seconds)
        t1, b1 = self.counts()
        total, bad = t1 - t0, b1 - b0
        ratio = bad / total if total else 0.0
        return total, bad, ratio, br.burn_rate(ratio)

    def stop(self):
        self.running = False
        self.proc.terminate()
        self.proc.wait(timeout=5)


def report(label, w):
    total, bad, ratio, burn = w
    state = "BREACH" if burn > THRESHOLD else "ok"
    print(f"  {label:<10} requests={total:>4.0f}  slower than 300ms={bad:>4.0f}  "
          f"bad ratio={ratio:6.1%}  burn rate={burn:5.1f}x  [{state}]", flush=True)
    return burn


def main():
    lab = Lab()
    try:
        print("=== 1. Baseline: steady traffic ===")
        base = report("baseline", lab.window(4))

        print("\n=== 2. Fault: inventory dependency slows down (800 ms on 60% of calls) ===")
        lab.post("/admin/fault", {"latency_ms": 800, "ratio": 0.6})
        burn_fault = report("incident", lab.window(5))
        detected = burn_fault > THRESHOLD
        print("  DETECTED: burn rate above 14.4x -> CheckoutLatencyBudgetFastBurn would page" if detected
              else "  not detected")

        print("\n=== 3. Diagnose: slow-request span timings (exemplars) ===")
        slow = json.loads(lab.get("/debug/slow-requests"))[-3:]
        for s in slow:
            spans = ", ".join(f"{k}={v:.0f}ms" for k, v in s["spans_ms"].items())
            print(f"  {s['duration_ms']:.0f} ms total: {spans}")
        culprit = max(slow[-1]["spans_ms"], key=slow[-1]["spans_ms"].get) if slow else "unknown"
        print(f"  Slowest span: {culprit}")

        print("\n=== 4. Mitigate: enable inventory cache fallback ===")
        lab.post("/admin/fallback", {"enabled": True})
        time.sleep(1.5)  # let in-flight slow requests drain
        burn_after = report("mitigated", lab.window(4))

        print("\n=== Result ===")
        ok = base < 1 and detected and culprit == "inventory.lookup" and burn_after < 1
        print(f"  baseline {base:.1f}x -> incident {burn_fault:.1f}x -> after mitigation {burn_after:.1f}x")
        print("DEMO RESULT:", "PASS - detected, diagnosed, mitigated and recovered" if ok else "FAIL")
        return 0 if ok else 1
    finally:
        lab.stop()


if __name__ == "__main__":
    sys.exit(main())
