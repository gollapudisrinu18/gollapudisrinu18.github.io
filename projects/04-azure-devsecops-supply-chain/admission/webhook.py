"""Validating admission webhook that only admits signed images.

Behaves like the Kyverno verifyImages policy in policy/kyverno, so the rule
can be exercised locally without a cluster:
  * images from protected registries must be referenced by digest
  * a signature for that digest must exist and verify against the trusted key

Signatures are looked up in a signature store directory
(<store>/<digest>.sig.json), which stands in for the registry's .sig tag.
"""
import fnmatch
import json
import os

from flask import Flask, jsonify, request

import signing

PROTECTED = os.environ.get("PROTECTED_IMAGES", "*.azurecr.io/supplychain/*").split(",")


def images_in(obj):
    spec = obj.get("spec", {})
    if obj.get("kind") in ("Deployment", "StatefulSet", "DaemonSet", "Job"):
        spec = spec.get("template", {}).get("spec", {})
    for key in ("initContainers", "containers", "ephemeralContainers"):
        for c in spec.get(key, []) or []:
            yield c["image"]


def evaluate(obj, public_pem, store):
    checked = 0
    for image in images_in(obj):
        if not any(fnmatch.fnmatch(image.split("@")[0], p) for p in PROTECTED):
            continue
        checked += 1
        repo, digest = signing.split_reference(image)
        if not digest:
            return False, f"{image}: protected images must be referenced by digest (@sha256:...)"
        sig_path = os.path.join(store, digest.replace(":", "-") + ".sig.json")
        if not os.path.exists(sig_path):
            return False, f"{image}: no signature found - image is unsigned"
        with open(sig_path) as fh:
            ok, reason = signing.verify(public_pem, repo, digest, json.load(fh))
        if not ok:
            return False, f"{image}: {reason}"
    if not checked:
        return True, "no images from protected registries"
    return True, "signature verified for all protected images"


def create_app(public_pem, store):
    app = Flask(__name__)

    @app.post("/validate")
    def validate():
        review = request.get_json(force=True)
        req = review["request"]
        allowed, message = evaluate(req["object"], public_pem, store)
        return jsonify({
            "apiVersion": "admission.k8s.io/v1",
            "kind": "AdmissionReview",
            "response": {
                "uid": req["uid"],
                "allowed": allowed,
                "status": {"code": 200 if allowed else 403, "message": message},
            },
        })

    return app
