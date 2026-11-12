#!/usr/bin/env python3
"""Run every project's local demo and save the real output for the website.

Writes projects/<project>/docs/demo-output.txt. Fails if any demo fails.
"""
import os
import subprocess
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DEMOS = {
    "01-aks-delivery-platform": ["scripts/local_release_demo.py"],
    "02-azure-hub-spoke-terraform": ["tools/dns_incident_demo.py"],
    "03-aks-observability-sre-lab": ["sim/live_incident_demo.py"],
    "04-azure-devsecops-supply-chain": ["admission/demo.py"],
    "05-azure-functions-event-processing": ["src/local_runtime.py"],
    "06-azure-dr-restore-drill": ["dr/drill.py"],
}


def main():
    failed = []
    for project, cmd in DEMOS.items():
        cwd = os.path.join(ROOT, "projects", project)
        out = subprocess.run([sys.executable, *cmd], cwd=cwd, capture_output=True, text=True, timeout=300)
        text = out.stdout.replace(cwd, ".")
        with open(os.path.join(cwd, "docs", "demo-output.txt"), "w") as fh:
            fh.write(f"$ python {' '.join(cmd)}\n{text}")
        status = "PASS" if out.returncode == 0 and "DEMO RESULT: PASS" in text else "FAIL"
        print(f"{status}  {project}")
        if status == "FAIL":
            failed.append(project)
            print(out.stderr[-2000:])
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
