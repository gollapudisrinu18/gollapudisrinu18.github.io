#!/usr/bin/env python3
"""Static checks that run without Terraform installed.

Complements `terraform fmt -check`, `terraform validate` and `terraform test`
(run in CI). Checks: module file layout, typed variables, balanced braces,
no hard-coded secrets or subscription IDs, and backend kept out of modules.
"""
import os
import re
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SECRET = re.compile(r'(password|client_secret|access_key)\s*=\s*"[^"$]+"', re.I)
GUID = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I)


def tf_files(path):
    for dirpath, _, files in os.walk(path):
        if ".terraform" in dirpath:
            continue
        for f in files:
            if f.endswith(".tf"):
                yield os.path.join(dirpath, f)


def check():
    problems = []
    modules = os.path.join(ROOT, "modules")
    for mod in sorted(os.listdir(modules)):
        for required in ("main.tf", "variables.tf", "outputs.tf"):
            if not os.path.exists(os.path.join(modules, mod, required)):
                problems.append(f"modules/{mod}: missing {required}")
        for f in tf_files(os.path.join(modules, mod)):
            if re.search(r'backend\s+"', open(f).read()):
                problems.append(f"{f}: modules must not declare a backend")

    for f in tf_files(ROOT):
        text = open(f).read()
        rel = os.path.relpath(f, ROOT)
        if text.count("{") != text.count("}"):
            problems.append(f"{rel}: unbalanced braces")
        if SECRET.search(text):
            problems.append(f"{rel}: hard-coded secret")
        if GUID.search(text):
            problems.append(f"{rel}: hard-coded GUID (subscription/tenant ID?)")
        for block in re.finditer(r'variable\s+"([^"]+)"\s*\{(.*?)\n\}', text, re.S):
            if not re.search(r"\btype\s*=", block.group(2)):
                problems.append(f"{rel}: variable {block.group(1)} has no type")
    return problems


if __name__ == "__main__":
    issues = check()
    for p in issues:
        print("FAIL", p)
    print("Terraform static checks:", "PASS" if not issues else f"{len(issues)} problem(s)")
    sys.exit(1 if issues else 0)
