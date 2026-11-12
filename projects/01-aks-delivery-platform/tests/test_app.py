import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from app import create_app  # noqa: E402


def client(**env):
    base = {"APP_VERSION": "1.0.0", "APP_ENV": "dev"}
    base.update(env)
    return create_app(base).test_client()


def test_health_and_readiness():
    c = client()
    assert c.get("/healthz").status_code == 200
    ready = c.get("/readyz")
    assert ready.status_code == 200
    assert ready.get_json()["version"] == "1.0.0"


def test_version_reports_environment():
    body = client(APP_ENV="qa").get("/version").get_json()
    assert body == {"version": "1.0.0", "environment": "qa"}


def test_list_orders():
    body = client().get("/api/v1/orders").get_json()
    assert body["count"] == 3
    assert {o["id"] for o in body["orders"]} == {"ORD-1001", "ORD-1002", "ORD-1003"}


def test_get_order_and_404():
    c = client()
    assert c.get("/api/v1/orders/ORD-1002").get_json()["item"] == "monitor"
    assert c.get("/api/v1/orders/ORD-9999").status_code == 404


def test_release_defect_breaks_orders_but_not_health():
    c = client(RELEASE_DEFECT="true")
    # Probes still pass, which is why a functional smoke test is needed.
    assert c.get("/healthz").status_code == 200
    assert c.get("/readyz").status_code == 200
    assert c.get("/api/v1/orders").status_code == 500
