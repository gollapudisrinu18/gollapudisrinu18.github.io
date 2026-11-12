#!/usr/bin/env python3
"""Render every ```mermaid block in the repository's Markdown to check syntax (needs mmdc)."""
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
CFG = os.path.join(ROOT, "site", "puppeteer.json")
failed = 0
count = 0
for dirpath, dirs, files in os.walk(ROOT):
    dirs[:] = [d for d in dirs if d not in (".git", "_site", "node_modules")]
    for f in files:
        if not f.endswith(".md"):
            continue
        path = os.path.join(dirpath, f)
        for n, block in enumerate(re.findall(r"```mermaid\n(.*?)```", open(path, encoding="utf-8").read(), re.S), 1):
            count += 1
            with tempfile.TemporaryDirectory() as tmp:
                src = os.path.join(tmp, "d.mmd")
                open(src, "w").write(block)
                args = ["mmdc", "-i", src, "-o", os.path.join(tmp, "d.svg")]
                if os.path.exists("/usr/bin/google-chrome"):
                    args += ["-p", CFG]
                r = subprocess.run(args, capture_output=True, text=True)
            rel = os.path.relpath(path, ROOT)
            if r.returncode:
                failed += 1
                print(f"FAIL {rel} block {n}\n{r.stderr[-800:]}")
            else:
                print(f"ok   {rel} block {n}")
print(f"{count - failed}/{count} Mermaid diagrams render")
sys.exit(1 if failed else 0)
