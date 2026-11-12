"""Minimal, dependency-free Prometheus metrics (text exposition format 0.0.4).

Kept small on purpose so the lab runs without extra packages. The metric
names and labels match what prometheus_client would produce, so the
recording rules work unchanged.
"""
import threading

LATENCY_BUCKETS = (0.05, 0.1, 0.2, 0.3, 0.5, 1.0, 2.0, 5.0)


class Registry:
    def __init__(self):
        self._lock = threading.Lock()
        self.requests = {}  # (route, code) -> count
        self.hist = {}      # route -> {"buckets": [..], "sum": float, "count": int}

    def observe(self, route, code, seconds):
        with self._lock:
            key = (route, str(code))
            self.requests[key] = self.requests.get(key, 0) + 1
            h = self.hist.setdefault(route, {"buckets": [0] * len(LATENCY_BUCKETS), "sum": 0.0, "count": 0})
            for i, le in enumerate(LATENCY_BUCKETS):
                if seconds <= le:
                    h["buckets"][i] += 1
            h["sum"] += seconds
            h["count"] += 1

    def render(self):
        lines = [
            "# HELP http_requests_total Total HTTP requests.",
            "# TYPE http_requests_total counter",
        ]
        with self._lock:
            for (route, code), n in sorted(self.requests.items()):
                lines.append(f'http_requests_total{{service="checkout-api",route="{route}",code="{code}"}} {n}')
            lines += [
                "# HELP http_request_duration_seconds Request latency.",
                "# TYPE http_request_duration_seconds histogram",
            ]
            for route, h in sorted(self.hist.items()):
                for le, n in zip(LATENCY_BUCKETS, h["buckets"]):
                    lines.append(f'http_request_duration_seconds_bucket{{service="checkout-api",route="{route}",le="{le}"}} {n}')
                lines.append(f'http_request_duration_seconds_bucket{{service="checkout-api",route="{route}",le="+Inf"}} {h["count"]}')
                lines.append(f'http_request_duration_seconds_sum{{service="checkout-api",route="{route}"}} {h["sum"]:.6f}')
                lines.append(f'http_request_duration_seconds_count{{service="checkout-api",route="{route}"}} {h["count"]}')
        return "\n".join(lines) + "\n"


def parse(text):
    """Parse exposition text into {(name, frozenset(labels)): value}. Used by tests and the demo."""
    out = {}
    for line in text.splitlines():
        if not line or line.startswith("#"):
            continue
        name_labels, value = line.rsplit(" ", 1)
        if "{" in name_labels:
            name, raw = name_labels.split("{", 1)
            labels = frozenset(tuple(p.split("=", 1)) for p in raw.rstrip("}").replace('"', "").split(","))
        else:
            name, labels = name_labels, frozenset()
        out[(name, labels)] = float(value)
    return out
