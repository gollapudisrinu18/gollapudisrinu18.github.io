#!/usr/bin/env python3
"""Verify a downloaded/restored directory against a backup manifest.

  python dr/verify_dir.py --dir ./restored --manifest ./manifest.json
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drlib  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--dir", required=True)
ap.add_argument("--manifest", required=True)
a = ap.parse_args()
ok, problems = drlib.verify(a.dir, json.load(open(a.manifest)))
print("INTEGRITY PASS" if ok else "INTEGRITY FAIL: " + "; ".join(problems))
sys.exit(0 if ok else 1)
