"""Constant-rate load generator (stdlib only)."""
import argparse
import threading
import time
import urllib.request


def fire(url):
    try:
        req = urllib.request.Request(url, data=b"{}", method="POST",
                                     headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10).read()
    except Exception:
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--rps", type=float, default=10)
    ap.add_argument("--seconds", type=float, default=0, help="0 = run forever")
    a = ap.parse_args()
    end = time.time() + a.seconds if a.seconds else float("inf")
    while time.time() < end:
        threading.Thread(target=fire, args=(a.url,), daemon=True).start()
        time.sleep(1 / a.rps)


if __name__ == "__main__":
    main()
