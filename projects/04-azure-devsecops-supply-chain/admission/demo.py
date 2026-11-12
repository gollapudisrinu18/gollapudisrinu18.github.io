#!/usr/bin/env python3
"""Supply-chain admission demo.

1. Generate a signing key pair (pipeline: key in Azure Key Vault).
2. "Build" two harmless synthetic images and compute their digests.
3. Sign only the first one (pipeline: cosign sign --key azurekms://...).
4. Send AdmissionReview requests for both to the webhook over HTTP.
   Unsigned -> rejected. Signed -> admitted. Tag-only and tampered -> rejected.
"""
import json
import os
import sys
import tempfile
import threading
import urllib.request
import uuid

import re

from werkzeug.serving import WSGIRequestHandler, make_server

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import signing  # noqa: E402
import webhook  # noqa: E402

class QuietHandler(WSGIRequestHandler):
    def log_request(self, *args, **kwargs):
        pass


def short(text):
    return re.sub(r"sha256:([a-f0-9]{12})[a-f0-9]{52}", r"sha256:\1...", text)


REPO = "acrportfolio.azurecr.io/supplychain/demo-app"


def admission_review(image, name):
    return {
        "apiVersion": "admission.k8s.io/v1",
        "kind": "AdmissionReview",
        "request": {
            "uid": str(uuid.uuid4()),
            "kind": {"group": "", "version": "v1", "kind": "Pod"},
            "operation": "CREATE",
            "object": {"apiVersion": "v1", "kind": "Pod", "metadata": {"name": name},
                       "spec": {"containers": [{"name": "app", "image": image}]}},
        },
    }


def main():
    work = tempfile.mkdtemp(prefix="supplychain-")
    store = os.path.join(work, "signatures")
    os.makedirs(store)

    print("=== 1. Generate signing key (ECDSA P-256) ===")
    priv, pub = signing.generate_keypair()
    print("  public key fingerprint:", signing.manifest_digest(pub)[:23] + "...")

    print("\n=== 2. Build two harmless test images ===")
    signed_digest = signing.manifest_digest(b'{"layers":["demo-app v1.0.0"],"note":"synthetic"}')
    unsigned_digest = signing.manifest_digest(b'{"layers":["demo-app v1.0.1-unsigned"],"note":"synthetic"}')
    print(f"  {REPO}@{signed_digest[:19]}...  (will be signed)")
    print(f"  {REPO}@{unsigned_digest[:19]}...  (not signed)")

    print("\n=== 3. Sign the release image ===")
    env = signing.sign(priv, REPO, signed_digest)
    with open(os.path.join(store, signed_digest.replace(":", "-") + ".sig.json"), "w") as fh:
        json.dump(env, fh)
    ok, _ = signing.verify(pub, REPO, signed_digest, env)
    print("  cosign-style verify:", "Verified OK" if ok else "FAILED")

    # Tampered: a signature file for the unsigned digest copied from the signed image.
    tampered_digest = signing.manifest_digest(b'{"layers":["demo-app tampered"]}')
    with open(os.path.join(store, tampered_digest.replace(":", "-") + ".sig.json"), "w") as fh:
        json.dump(env, fh)

    server = make_server("127.0.0.1", 0, webhook.create_app(pub, store), request_handler=QuietHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_port}/validate"

    def submit(image, name):
        body = json.dumps(admission_review(image, name)).encode()
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        resp = json.loads(urllib.request.urlopen(req).read())["response"]
        verdict = "ADMITTED" if resp["allowed"] else "REJECTED"
        print(f"  {name:<16} -> {verdict}: {short(resp['status']['message'])}")
        return resp["allowed"]

    print("\n=== 4. Admission decisions ===")
    results = {
        "unsigned": submit(f"{REPO}@{unsigned_digest}", "unsigned-pod"),
        "signed": submit(f"{REPO}@{signed_digest}", "signed-pod"),
        "tag-only": submit(f"{REPO}:1.0.0", "tag-only-pod"),
        "tampered": submit(f"{REPO}@{tampered_digest}", "tampered-pod"),
        "other-registry": submit("mcr.microsoft.com/azure-cli:2.60.0", "unprotected-pod"),
    }
    server.shutdown()

    expected = {"unsigned": False, "signed": True, "tag-only": False, "tampered": False, "other-registry": True}
    ok = results == expected
    print("\nDEMO RESULT:", "PASS - unsigned image rejected, signed image admitted" if ok else f"FAIL {results}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
