#!/usr/bin/env python3
"""Point the portfolio at a GitHub account and repository.

  python tools/configure.py --user gollapudisrinu18 --repo my-profile [--branch main] [--pages-url URL]

Updates site/config.json and replaces repository placeholders in Markdown and
YAML files. The Pages URL defaults to https://<user>.github.io/<repo>/
(use https://<user>.github.io/ for a <user>.github.io repository).
"""
import argparse
import json
import os
import re

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
PLACEHOLDER = re.compile(r"(github\.com/)(YOUR-GITHUB-USERNAME/YOUR-REPO|[\w.-]+/[\w.-]+)(?=/(?:blob|tree|issues))")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", required=True)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--branch", default="main")
    ap.add_argument("--pages-url")
    a = ap.parse_args()
    if a.pages_url:
        pages = a.pages_url
    elif a.repo.lower() == f"{a.user.lower()}.github.io":
        pages = f"https://{a.user}.github.io/"
    else:
        pages = f"https://{a.user}.github.io/{a.repo}/"
    pages = pages.rstrip("/") + "/"

    cfg_path = os.path.join(ROOT, "site", "config.json")
    cfg = json.load(open(cfg_path))
    old_pages = cfg["pages_url"]
    cfg.update(github_user=a.user, repo=a.repo, branch=a.branch, pages_url=pages)
    json.dump(cfg, open(cfg_path, "w"), indent=2)

    changed = 0
    for dirpath, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in (".git", "_site", "node_modules")]
        for f in files:
            if not f.endswith((".md", ".yaml", ".yml")) or "workflows" in dirpath:
                continue
            p = os.path.join(dirpath, f)
            text = open(p, encoding="utf-8").read()
            new = PLACEHOLDER.sub(lambda m: f"{m.group(1)}{a.user}/{a.repo}", text)
            new = new.replace(old_pages, pages).replace("<owner>/<repo>", f"{a.user}/{a.repo}")
            if new != text:
                open(p, "w", encoding="utf-8").write(new)
                changed += 1
    print(f"Configured {a.user}/{a.repo} (branch {a.branch}), Pages {pages}; updated {changed} files")


if __name__ == "__main__":
    main()
