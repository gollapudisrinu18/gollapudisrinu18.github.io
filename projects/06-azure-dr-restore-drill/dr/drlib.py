"""Backup, restore and integrity verification for the DR drill.

Local stand-in for Azure Blob Storage with point-in-time restore / Azure
Backup: the "primary" is a directory of JSON files, backups are immutable
snapshots with a SHA-256 manifest.
"""
import hashlib
import json
import os
import random
import shutil
import time
from datetime import datetime, timezone


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def generate_dataset(primary, files, records, seed=42):
    """Synthetic order records - no real customer data."""
    rng = random.Random(seed)
    os.makedirs(primary, exist_ok=True)
    for f in range(files):
        rows = [{"orderId": f"ORD-{f:03d}-{r:04d}", "customer": f"CUST-{rng.randint(1, 500):04d}",
                 "amount": round(rng.uniform(100, 5000), 2), "currency": "INR"} for r in range(records)]
        with open(os.path.join(primary, f"orders-{f:03d}.json"), "w") as fh:
            json.dump(rows, fh)


def append_records(primary, n, seed=7):
    """Writes after the last backup - these are what the RPO measures."""
    rng = random.Random(seed)
    path = os.path.join(primary, "orders-late.json")
    rows = [{"orderId": f"ORD-LATE-{i:04d}", "customer": f"CUST-{rng.randint(1, 500):04d}",
             "amount": round(rng.uniform(100, 5000), 2), "currency": "INR"} for i in range(n)]
    with open(path, "w") as fh:
        json.dump(rows, fh)
    return path


def count_records(directory):
    total = 0
    for name in sorted(os.listdir(directory)):
        if name.endswith(".json"):
            with open(os.path.join(directory, name)) as fh:
                total += len(json.load(fh))
    return total


def take_backup(primary, vault, when=None):
    ts = when or datetime.now(timezone.utc)
    snap = os.path.join(vault, ts.strftime("%Y%m%dT%H%M%SZ"))
    shutil.copytree(primary, os.path.join(snap, "data"))
    files = {}
    for name in sorted(os.listdir(os.path.join(snap, "data"))):
        p = os.path.join(snap, "data", name)
        files[name] = {"sha256": sha256(p), "bytes": os.path.getsize(p)}
    manifest = {"taken_at": ts.isoformat(), "files": files,
                "records": count_records(os.path.join(snap, "data"))}
    with open(os.path.join(snap, "manifest.json"), "w") as fh:
        json.dump(manifest, fh, indent=2)
    for root, _, fs in os.walk(snap):      # make the snapshot read-only (immutability stand-in)
        for f in fs:
            os.chmod(os.path.join(root, f), 0o444)
    return snap, manifest


def latest_backup(vault):
    snaps = sorted(d for d in os.listdir(vault) if os.path.isdir(os.path.join(vault, d)))
    if not snaps:
        raise FileNotFoundError("no backups in vault")
    snap = os.path.join(vault, snaps[-1])
    with open(os.path.join(snap, "manifest.json")) as fh:
        return snap, json.load(fh)


def restore(snap, target):
    if os.path.exists(target):
        shutil.rmtree(target)
    shutil.copytree(os.path.join(snap, "data"), target)
    for root, _, fs in os.walk(target):
        for f in fs:
            os.chmod(os.path.join(root, f), 0o644)


def verify(directory, manifest):
    """Return (ok, problems). Compares every file hash and the record count."""
    problems = []
    present = set(os.listdir(directory)) if os.path.isdir(directory) else set()
    for name, meta in manifest["files"].items():
        if name not in present:
            problems.append(f"missing {name}")
        elif sha256(os.path.join(directory, name)) != meta["sha256"]:
            problems.append(f"checksum mismatch {name}")
    if not problems and count_records(directory) != manifest["records"]:
        problems.append("record count mismatch")
    return not problems, problems


class Stopwatch:
    def __init__(self):
        self.t0 = time.perf_counter()

    def seconds(self):
        return time.perf_counter() - self.t0
