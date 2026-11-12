"""Image signing and verification in Cosign's "simple signing" format.

Cosign signs a JSON payload that binds the repository to the manifest
digest, using ECDSA P-256 with SHA-256. This module produces and checks the
same payload so the local admission demo behaves like `cosign sign` /
`cosign verify --key`. In the pipeline the real cosign CLI is used with a key
held in Azure Key Vault (azurekms://).
"""
import base64
import hashlib
import json
import re

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

DIGEST_RE = re.compile(r"^(?P<repo>[^@]+)@(?P<digest>sha256:[a-f0-9]{64})$")


def manifest_digest(manifest_bytes):
    return "sha256:" + hashlib.sha256(manifest_bytes).hexdigest()


def split_reference(image):
    m = DIGEST_RE.match(image)
    if not m:
        return None, None
    return m.group("repo"), m.group("digest")


def payload(repo, digest):
    return json.dumps({
        "critical": {
            "identity": {"docker-reference": repo},
            "image": {"docker-manifest-digest": digest},
            "type": "cosign container image signature",
        },
        "optional": None,
    }, separators=(",", ":"), sort_keys=True).encode()


def generate_keypair():
    key = ec.generate_private_key(ec.SECP256R1())
    priv = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                             serialization.NoEncryption())
    pub = key.public_key().public_bytes(serialization.Encoding.PEM,
                                        serialization.PublicFormat.SubjectPublicKeyInfo)
    return priv, pub


def sign(private_pem, repo, digest):
    key = serialization.load_pem_private_key(private_pem, password=None)
    body = payload(repo, digest)
    sig = key.sign(body, ec.ECDSA(hashes.SHA256()))
    return {"payload": base64.b64encode(body).decode(), "signature": base64.b64encode(sig).decode()}


def verify(public_pem, repo, digest, envelope):
    """Return (ok, reason)."""
    key = serialization.load_pem_public_key(public_pem)
    body = base64.b64decode(envelope["payload"])
    try:
        key.verify(base64.b64decode(envelope["signature"]), body, ec.ECDSA(hashes.SHA256()))
    except InvalidSignature:
        return False, "signature does not match the trusted public key"
    claims = json.loads(body)["critical"]
    if claims["image"]["docker-manifest-digest"] != digest:
        return False, "signature was made for a different digest"
    if claims["identity"]["docker-reference"] != repo:
        return False, "signature was made for a different repository"
    return True, "verified"
