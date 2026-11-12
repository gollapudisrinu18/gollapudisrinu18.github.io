"""Orders API - a small synthetic service used to demonstrate AKS delivery.

The data is synthetic. Behaviour is controlled by environment variables so the
same image can be deployed to Dev, QA and Production with different settings:

  APP_VERSION     version string reported by /version (set by the pipeline)
  APP_ENV         dev | qa | prod
  RELEASE_DEFECT  "true" simulates a bad release: /api/v1/orders returns 500.
                  Used only to demonstrate a failed smoke test and rollback.
"""
import json
import logging
import os
import sys
import time

from flask import Flask, jsonify, request

ORDERS = [
    {"id": "ORD-1001", "item": "keyboard", "quantity": 2, "status": "shipped"},
    {"id": "ORD-1002", "item": "monitor", "quantity": 1, "status": "processing"},
    {"id": "ORD-1003", "item": "usb-c dock", "quantity": 3, "status": "delivered"},
]


class JsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
            "level": record.levelname,
            "msg": record.getMessage(),
            "service": "orders-api",
        }
        payload.update(getattr(record, "extra_fields", {}))
        return json.dumps(payload)


def _logger():
    log = logging.getLogger("orders-api")
    if not log.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        log.addHandler(handler)
        log.setLevel(logging.INFO)
    return log


def create_app(env=None):
    env = dict(os.environ if env is None else env)
    app = Flask(__name__)
    log = _logger()
    version = env.get("APP_VERSION", "0.0.0-local")
    app_env = env.get("APP_ENV", "local")
    defect = env.get("RELEASE_DEFECT", "false").lower() == "true"

    @app.after_request
    def access_log(response):
        log.info(
            "request",
            extra={"extra_fields": {
                "path": request.path,
                "status": response.status_code,
                "version": version,
            }},
        )
        return response

    @app.get("/healthz")
    def healthz():
        # Liveness: the process is up.
        return jsonify(status="ok")

    @app.get("/readyz")
    def readyz():
        # Readiness: the app can serve traffic.
        return jsonify(status="ready", version=version)

    @app.get("/version")
    def version_info():
        return jsonify(version=version, environment=app_env)

    @app.get("/api/v1/orders")
    def list_orders():
        if defect:
            return jsonify(error="order repository unavailable"), 500
        return jsonify(orders=ORDERS, count=len(ORDERS))

    @app.get("/api/v1/orders/<order_id>")
    def get_order(order_id):
        if defect:
            return jsonify(error="order repository unavailable"), 500
        for order in ORDERS:
            if order["id"] == order_id:
                return jsonify(order)
        return jsonify(error="not found"), 404

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
