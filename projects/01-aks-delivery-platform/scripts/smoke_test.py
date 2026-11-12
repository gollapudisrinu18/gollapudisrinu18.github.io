#!/usr/bin/env python3
"""Post-deployment smoke test for the Orders API.

Used by the Azure Pipelines deploy template and by the local release demo.
Exit code 0 = pass, 1 = fail.

  python smoke_test.py --base-url http://localhost:8080 --expected-version 1.1.0
"""
import argparse
import json
import sys
import time
import urllib.error
import urllib.request


def get(url, timeout=5):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as err:
        body = err.read()
        try:
            return err.code, json.loads(body or b"{}")
        except ValueError:
            return err.code, {}
    except (urllib.error.URLError, ConnectionError, TimeoutError) as err:
        return 0, {"error": str(err)}


def run_checks(base_url, expected_version=None):
    base_url = base_url.rstrip("/")
    results = []

    status, body = get(f"{base_url}/healthz")
    results.append(("liveness /healthz returns 200", status == 200, f"HTTP {status}"))

    status, body = get(f"{base_url}/version")
    ok = status == 200 and (expected_version is None or body.get("version") == expected_version)
    results.append((f"/version reports {expected_version or 'a version'}", ok,
                    f"HTTP {status}, version={body.get('version')}"))

    status, body = get(f"{base_url}/api/v1/orders")
    ok = status == 200 and body.get("count", 0) > 0
    results.append(("GET /api/v1/orders returns orders", ok, f"HTTP {status}"))

    status, body = get(f"{base_url}/api/v1/orders/ORD-1001")
    ok = status == 200 and body.get("id") == "ORD-1001"
    results.append(("GET /api/v1/orders/ORD-1001 returns the order", ok, f"HTTP {status}"))
    return results


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--expected-version")
    parser.add_argument("--retries", type=int, default=5)
    parser.add_argument("--delay", type=float, default=2.0)
    args = parser.parse_args(argv)

    for attempt in range(1, args.retries + 1):
        results = run_checks(args.base_url, args.expected_version)
        if all(ok for _, ok, _ in results):
            break
        if attempt < args.retries:
            time.sleep(args.delay)

    print(f"Smoke test against {args.base_url}")
    for name, ok, detail in results:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name} ({detail})")
    passed = all(ok for _, ok, _ in results)
    print("SMOKE TEST PASSED" if passed else "SMOKE TEST FAILED")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
