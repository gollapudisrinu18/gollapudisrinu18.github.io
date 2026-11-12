import json
import os
import subprocess
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "tools"))
import dns_check  # noqa: E402
import validate_tf  # noqa: E402

NAME = "sthslabdemo01.blob.core.windows.net"


def model(name):
    return dns_check.load_model(os.path.join(ROOT, "scenarios", name))


def test_unlinked_spoke_resolves_public():
    r = dns_check.resolve(model("broken.json"), "app", NAME)
    assert r["kind"] == "public"


def test_linked_spoke_resolves_private_endpoint():
    r = dns_check.resolve(model("fixed.json"), "app", NAME)
    assert r == {**r, "kind": "private", "answer": "10.1.2.4"}


def test_missing_record_is_nxdomain():
    m = model("fixed.json")
    m["zones"]["privatelink.blob.core.windows.net"]["records"] = {}
    assert dns_check.resolve(m, "app", NAME)["kind"] == "NXDOMAIN"


def test_accepts_full_terraform_output_shape(tmp_path):
    wrapped = {"dns_model": {"value": model("fixed.json"), "type": "object", "sensitive": False}}
    p = tmp_path / "out.json"
    p.write_text(json.dumps(wrapped))
    assert dns_check.main(["--model", str(p), "--from-vnet", "app", "--name", NAME, "--expect", "private"]) == 0


def test_demo_end_to_end():
    out = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "dns_incident_demo.py")],
                         capture_output=True, text=True)
    assert out.returncode == 0, out.stdout
    assert "DEMO RESULT: PASS" in out.stdout


def test_terraform_static_checks():
    assert validate_tf.check() == []


def test_misconfig_tfvars_matches_broken_scenario():
    text = open(os.path.join(ROOT, "envs", "lab", "misconfig.tfvars")).read()
    assert 'dns_linked_spokes = ["data"]' in text
    linked = model("broken.json")["zones"]["privatelink.blob.core.windows.net"]["linked_vnets"]
    assert "app" not in linked
