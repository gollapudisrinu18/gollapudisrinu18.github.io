#!/usr/bin/env python3
"""Local release-and-rollback demo (no Azure needed).

Mirrors what scripts/deploy_with_rollback.sh does on AKS, using local
processes instead of Kubernetes pods and an in-memory revision history
instead of Helm's:

  revision 1  orders-api 1.0.0                 -> smoke test passes
  revision 2  orders-api 1.1.0 (RELEASE_DEFECT) -> smoke test fails
  rollback    back to revision 1 (as revision 3) -> smoke test passes, 1.0.0 served
"""
import os
import socket
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(HERE, "..", "app", "app.py")
sys.path.insert(0, HERE)
import smoke_test  # noqa: E402


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class LocalRelease:
    def __init__(self, name):
        self.name = name
        self.history = []  # list of dicts like `helm history`
        self.proc = None
        self.port = free_port()

    def _start(self, values):
        self.stop()
        env = dict(os.environ, PORT=str(self.port), APP_VERSION=values["tag"],
                   APP_ENV="local", RELEASE_DEFECT=str(values.get("releaseDefect", False)).lower())
        self.proc = subprocess.Popen([sys.executable, APP], env=env,
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        url = f"http://127.0.0.1:{self.port}/healthz"
        for _ in range(50):  # equivalent of `helm --wait` on readiness
            try:
                urllib.request.urlopen(url, timeout=1)
                return
            except Exception:
                time.sleep(0.1)
        raise RuntimeError("release did not become ready")

    def upgrade(self, tag, **values):
        values = dict(values, tag=tag)
        for h in self.history:
            if h["status"] == "deployed":
                h["status"] = "superseded"
        rev = len(self.history) + 1
        self._start(values)
        self.history.append({"revision": rev, "tag": tag, "status": "deployed",
                             "description": "Upgrade complete", "values": values})
        return rev

    def rollback(self, to_revision):
        target = next(h for h in self.history if h["revision"] == to_revision)
        for h in self.history:
            if h["status"] == "deployed":
                h["status"] = "superseded"
        rev = len(self.history) + 1
        self._start(target["values"])
        self.history.append({"revision": rev, "tag": target["tag"], "status": "deployed",
                             "description": f"Rollback to {to_revision}", "values": target["values"]})
        return rev

    def current(self):
        return next(h for h in reversed(self.history) if h["status"] == "deployed")

    def base_url(self):
        return f"http://127.0.0.1:{self.port}"

    def stop(self):
        if self.proc:
            self.proc.terminate()
            self.proc.wait(timeout=5)
            self.proc = None

    def print_history(self):
        print(f"\n$ helm history {self.name}   (local equivalent)")
        print(f"  {'REVISION':<9}{'TAG':<8}{'STATUS':<12}DESCRIPTION")
        for h in self.history:
            print(f"  {h['revision']:<9}{h['tag']:<8}{h['status']:<12}{h['description']}")


def step(title):
    print(f"\n=== {title} ===", flush=True)


def deploy_with_rollback(release, tag, **values):
    """Same decision logic as deploy_with_rollback.sh."""
    previous = release.current()["revision"] if release.history else None
    rev = release.upgrade(tag, **values)
    print(f"Deployed {release.name} {tag} as revision {rev}")
    if smoke_test.main(["--base-url", release.base_url(), "--expected-version", tag,
                        "--retries", "2", "--delay", "0.5"]) == 0:
        return True
    if previous is None:
        print("First install failed; nothing to roll back to.")
        return False
    print(f"\nSmoke test failed -> rolling back {release.name} to revision {previous}")
    new_rev = release.rollback(previous)
    restored = release.current()["tag"]
    print(f"Rollback created revision {new_rev}, serving {restored}")
    ok = smoke_test.main(["--base-url", release.base_url(), "--expected-version", restored,
                          "--retries", "2", "--delay", "0.5"]) == 0
    print("ROLLBACK VERIFIED" if ok else "ROLLBACK VERIFICATION FAILED")
    return False


def main():
    release = LocalRelease("orders-api")
    try:
        step("Revision 1: deploy orders-api 1.0.0")
        first_ok = deploy_with_rollback(release, "1.0.0")

        step("Revision 2: deploy orders-api 1.1.0 (contains a simulated defect)")
        second_ok = deploy_with_rollback(release, "1.1.0", releaseDefect=True)

        step("Result")
        release.print_history()
        with urllib.request.urlopen(release.base_url() + "/version") as r:
            served = r.read().decode()
        print(f"\nLive /version after the pipeline run: {served}")
        verified = first_ok and not second_ok and release.current()["tag"] == "1.0.0"
        print("\nDEMO RESULT:", "PASS - bad release was rolled back to 1.0.0" if verified else "FAIL")
        return 0 if verified else 1
    finally:
        release.stop()


if __name__ == "__main__":
    sys.exit(main())
