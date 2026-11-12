import os
import subprocess
import sys

HERE = os.path.dirname(__file__)


def test_local_demo_rolls_back_bad_release():
    script = os.path.join(HERE, "..", "scripts", "local_release_demo.py")
    out = subprocess.run([sys.executable, script], capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stdout + out.stderr
    assert "SMOKE TEST FAILED" in out.stdout
    assert "ROLLBACK VERIFIED" in out.stdout
    assert "Rollback to 1" in out.stdout
    assert '"version":"1.0.0"' in out.stdout.replace(" ", "")


def test_smoke_test_fails_when_service_is_down():
    sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
    import smoke_test
    rc = smoke_test.main(["--base-url", "http://127.0.0.1:9", "--retries", "1"])
    assert rc == 1
