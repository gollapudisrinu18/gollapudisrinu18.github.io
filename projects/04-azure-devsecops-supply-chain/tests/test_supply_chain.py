import json
import os
import subprocess
import sys

import yaml

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "admission"))
import signing  # noqa: E402
import webhook  # noqa: E402

REPO = "acrtest.azurecr.io/supplychain/demo-app"


def pod(image):
    return {"kind": "Pod", "spec": {"containers": [{"name": "c", "image": image}]}}


def setup(tmp_path, sign_digest=None):
    priv, pub = signing.generate_keypair()
    if sign_digest:
        env = signing.sign(priv, REPO, sign_digest)
        (tmp_path / (sign_digest.replace(":", "-") + ".sig.json")).write_text(json.dumps(env))
    return priv, pub


def test_signed_image_admitted(tmp_path):
    d = signing.manifest_digest(b"a")
    _, pub = setup(tmp_path, d)
    assert webhook.evaluate(pod(f"{REPO}@{d}"), pub, str(tmp_path))[0] is True


def test_unsigned_image_rejected(tmp_path):
    d = signing.manifest_digest(b"b")
    _, pub = setup(tmp_path)
    ok, msg = webhook.evaluate(pod(f"{REPO}@{d}"), pub, str(tmp_path))
    assert not ok and "unsigned" in msg


def test_signature_from_other_key_rejected(tmp_path):
    d = signing.manifest_digest(b"c")
    setup(tmp_path, d)
    _, other_pub = signing.generate_keypair()
    ok, msg = webhook.evaluate(pod(f"{REPO}@{d}"), other_pub, str(tmp_path))
    assert not ok and "trusted public key" in msg


def test_tag_reference_rejected(tmp_path):
    _, pub = setup(tmp_path)
    ok, msg = webhook.evaluate(pod(f"{REPO}:1.0.0"), pub, str(tmp_path))
    assert not ok and "digest" in msg


def test_deployment_template_is_checked(tmp_path):
    _, pub = setup(tmp_path)
    dep = {"kind": "Deployment", "spec": {"template": {"spec": {"containers": [{"name": "c", "image": f"{REPO}:x"}]}}}}
    assert webhook.evaluate(dep, pub, str(tmp_path))[0] is False


def test_payload_matches_cosign_simple_signing_shape():
    body = json.loads(signing.payload(REPO, "sha256:" + "0" * 64))
    assert body["critical"]["type"] == "cosign container image signature"
    assert body["critical"]["identity"]["docker-reference"] == REPO


def test_kyverno_policy_targets_same_images_as_webhook():
    pol = yaml.safe_load(open(os.path.join(ROOT, "policy/kyverno/verify-image-signatures.yaml")))
    rule = pol["spec"]["rules"][0]["verifyImages"][0]
    assert pol["spec"]["validationFailureAction"] == "Enforce"
    assert rule["imageReferences"] == webhook.PROTECTED
    assert rule["verifyDigest"] and rule["required"]


def test_all_yaml_parses():
    for dirpath, _, files in os.walk(ROOT):
        for f in files:
            if f.endswith((".yml", ".yaml")):
                list(yaml.safe_load_all(open(os.path.join(dirpath, f))))


def test_demo_end_to_end():
    out = subprocess.run([sys.executable, os.path.join(ROOT, "admission", "demo.py")],
                         capture_output=True, text=True)
    assert out.returncode == 0, out.stdout + out.stderr
    assert "unsigned-pod     -> REJECTED" in out.stdout
    assert "signed-pod       -> ADMITTED" in out.stdout
