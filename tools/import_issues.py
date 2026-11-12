#!/usr/bin/env python3
"""Create GitHub issues from a project's docs/issues.md with the GitHub CLI.

  python tools/import_issues.py projects/<project>/docs/issues.md --repo owner/repo [--dry-run]

Issues marked Done/Fixed/Resolved are created and then closed with a comment
pointing to the evidence, so the backlog shows both history and open work.
Re-running skips issues whose title already exists.
"""
import argparse
import json
import re
import subprocess
import sys

HEAD = re.compile(r"^### (ISSUE-\d+): (.+)$", re.M)
CLOSED = ("done", "fixed", "resolved")


def parse(text):
    text = text.split("\n## Import into GitHub")[0]
    project = re.search(r"^# Issue backlog: (.+)$", text, re.M).group(1).strip()
    matches = list(HEAD.finditer(text))
    issues = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = text[m.end():end].strip()
        labels = re.search(r"^\*\*Labels:\*\*\s*(.+)$", block, re.M)
        status = re.search(r"^\*\*Status:\*\*\s*(.+)$", block, re.M)
        body = re.sub(r"^\*\*Labels:\*\*.*\n?", "", block, flags=re.M).strip()
        issues.append({
            "id": m.group(1),
            "title": f"[{project}] {m.group(2).strip()}",
            "labels": [l.strip() for l in labels.group(1).split(",")] if labels else [],
            "status": status.group(1).strip() if status else "Open",
            "body": body,
        })
    return issues


def gh(args, dry):
    print("$ gh " + " ".join(a if " " not in a else repr(a) for a in args[:6]) + (" ..." if len(args) > 6 else ""))
    if dry:
        return ""
    return subprocess.run(["gh", *args], check=True, capture_output=True, text=True).stdout


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("issues_md")
    ap.add_argument("--repo", required=True)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    issues = parse(open(a.issues_md, encoding="utf-8").read())
    existing = set()
    if not a.dry_run:
        out = gh(["issue", "list", "--repo", a.repo, "--state", "all", "--limit", "500", "--json", "title"], False)
        existing = {i["title"] for i in json.loads(out or "[]")}
    for label in sorted({l for i in issues for l in i["labels"]}):
        gh(["label", "create", label, "--repo", a.repo, "--force"], a.dry_run)
    for issue in issues:
        if issue["title"] in existing:
            print(f"skip (exists): {issue['title']}")
            continue
        args = ["issue", "create", "--repo", a.repo, "--title", issue["title"], "--body", issue["body"]]
        for label in issue["labels"]:
            args += ["--label", label]
        url = gh(args, a.dry_run).strip()
        if issue["status"].lower().startswith(CLOSED):
            gh(["issue", "close", url or "<new-issue-url>", "--repo", a.repo,
                "--comment", f"Completed. Evidence: {issue['status']}"], a.dry_run)
    print(f"{len(issues)} issues processed from {a.issues_md}")


if __name__ == "__main__":
    sys.exit(main())
