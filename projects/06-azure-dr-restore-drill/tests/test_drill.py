import json
import os
import subprocess
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "dr"))
import drlib  # noqa: E402


def test_backup_restore_roundtrip(tmp_path):
    primary, vault = tmp_path / "p", tmp_path / "v"
    vault.mkdir()
    drlib.generate_dataset(str(primary), 3, 5)
    snap, manifest = drlib.take_backup(str(primary), str(vault))
    assert manifest["records"] == 15
    drlib.restore(snap, str(tmp_path / "r"))
    assert drlib.verify(str(tmp_path / "r"), manifest) == (True, [])


def test_verify_detects_tampering_and_missing(tmp_path):
    primary, vault = tmp_path / "p", tmp_path / "v"
    vault.mkdir()
    drlib.generate_dataset(str(primary), 2, 3)
    _, manifest = drlib.take_backup(str(primary), str(vault))
    with open(primary / "orders-000.json", "w") as fh:
        json.dump([], fh)
    os.remove(primary / "orders-001.json")
    ok, problems = drlib.verify(str(primary), manifest)
    assert not ok and "checksum mismatch orders-000.json" in problems and "missing orders-001.json" in problems


def test_dataset_is_deterministic(tmp_path):
    drlib.generate_dataset(str(tmp_path / "a"), 2, 4)
    drlib.generate_dataset(str(tmp_path / "b"), 2, 4)
    assert drlib.sha256(tmp_path / "a" / "orders-001.json") == drlib.sha256(tmp_path / "b" / "orders-001.json")


def test_drill_end_to_end(tmp_path):
    report = tmp_path / "report.md"
    out = subprocess.run([sys.executable, os.path.join(ROOT, "dr", "drill.py"), "--report", str(report),
                          "--workdir", str(tmp_path / "w")], capture_output=True, text=True)
    assert out.returncode == 0, out.stdout + out.stderr
    text = report.read_text()
    assert "All file checksums match" in text and "**MET**" in text
    assert "Records lost (after last backup) | 37" in text
