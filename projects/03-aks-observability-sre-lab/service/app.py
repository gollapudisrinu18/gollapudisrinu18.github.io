"""checkout-api: synthetic service instrumented with OpenTelemetry and Prometheus.

Request path for POST /api/checkout:
    inventory.lookup  -> payment.authorize -> order.persist

Fault injection (lab only):
    POST /admin/fault     {"latency_ms": 800, "ratio": 0.6}  slow inventory lookups
    POST /admin/fallback  {"enabled": true}                 serve inventory from cache
    POST /admin/reset
"""
import os
import random
import threading
import time
from collections import deque

from flask import Flask, jsonify, request
from opentelemetry import trace

from metrics import Registry

tracer = trace.get_tracer("checkout-api")


def configure_otel():
    """Use the OTel SDK + OTLP exporter when installed (container image).
    Locally only the API is needed; spans become no-ops."""
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not endpoint:
        return False
    try:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        return False
    provider = TracerProvider(resource=Resource.create({"service.name": "checkout-api"}))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, insecure=True)))
    trace.set_tracer_provider(provider)
    return True


def create_app(seed=None):
    app = Flask(__name__)
    rng = random.Random(seed)
    registry = Registry()
    state = {"latency_ms": 0, "ratio": 0.0, "fallback": False}
    slow = deque(maxlen=50)  # recent slow requests with per-span timing (exemplars)
    lock = threading.Lock()
    app.config["registry"] = registry

    def stage(name, base_ms, extra_ms=0):
        with tracer.start_as_current_span(name) as span:
            ms = base_ms + rng.uniform(0, base_ms * 0.5) + extra_ms
            time.sleep(ms / 1000)
            span.set_attribute("lab.duration_ms", round(ms, 1))
            return ms

    @app.post("/api/checkout")
    def checkout():
        start = time.perf_counter()
        with tracer.start_as_current_span("POST /api/checkout") as root:
            with lock:
                inject = (not state["fallback"]) and rng.random() < state["ratio"]
                extra = state["latency_ms"] if inject else 0
                fallback = state["fallback"]
            timings = {}
            if fallback:
                timings["inventory.cache"] = stage("inventory.cache", 2)
            else:
                timings["inventory.lookup"] = stage("inventory.lookup", 15, extra)
            timings["payment.authorize"] = stage("payment.authorize", 20)
            timings["order.persist"] = stage("order.persist", 8)
            root.set_attribute("lab.fallback", fallback)
        elapsed = time.perf_counter() - start
        registry.observe("/api/checkout", 200, elapsed)
        if elapsed > 0.3:
            slow.append({"duration_ms": round(elapsed * 1000, 1),
                         "spans_ms": {k: round(v, 1) for k, v in timings.items()}})
        return jsonify(status="confirmed", fallback=fallback)

    @app.get("/healthz")
    def healthz():
        return jsonify(status="ok")

    @app.get("/metrics")
    def metrics():
        return registry.render(), 200, {"Content-Type": "text/plain; version=0.0.4"}

    @app.get("/debug/slow-requests")
    def slow_requests():
        return jsonify(list(slow))

    @app.post("/admin/fault")
    def fault():
        body = request.get_json(force=True)
        with lock:
            state["latency_ms"] = int(body.get("latency_ms", 800))
            state["ratio"] = float(body.get("ratio", 0.5))
        return jsonify(state)

    @app.post("/admin/fallback")
    def fallback():
        with lock:
            state["fallback"] = bool(request.get_json(force=True).get("enabled", True))
        return jsonify(state)

    @app.post("/admin/reset")
    def reset():
        with lock:
            state.update(latency_ms=0, ratio=0.0, fallback=False)
        return jsonify(state)

    return app


if __name__ == "__main__":
    configure_otel()
    create_app().run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")), threaded=True)
