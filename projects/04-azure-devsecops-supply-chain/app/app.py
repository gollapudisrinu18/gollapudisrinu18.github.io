"""Tiny synthetic service used as the image that moves through the supply chain."""
import os

from flask import Flask, jsonify

app = Flask(__name__)


@app.get("/")
def index():
    # DB_PASSWORD is mounted from Azure Key Vault by the Secrets Store CSI driver.
    secret_path = "/mnt/secrets/app-db-password"
    return jsonify(service="supplychain-demo",
                   secret_mounted=os.path.exists(secret_path))


@app.get("/healthz")
def healthz():
    return jsonify(status="ok")
