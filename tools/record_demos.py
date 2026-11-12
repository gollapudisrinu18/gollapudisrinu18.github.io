#!/usr/bin/env python3
"""Record each captioned walkthrough to MP4 with a matching WebVTT caption file.

Needs: the built site served at SITE_URL, Chrome, Playwright, ffmpeg.
  python -m http.server 8765 --directory _site &
  python tools/record_demos.py
Writes site/static/assets/video/<slug>.mp4 and .vtt (rebuild the site afterwards).
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

from playwright.sync_api import sync_playwright

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
OUT = os.path.join(ROOT, "site", "static", "assets", "video")
BASE = os.environ.get("SITE_URL", "http://127.0.0.1:8765/")
SECONDS = float(os.environ.get("SCENE_SECONDS", "5"))
SIZE = {"width": 1280, "height": 720}


def ts(sec):
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{s:06.3f}"


def record(browser, slug, tmp):
    ctx = browser.new_context(viewport=SIZE, record_video_dir=tmp, record_video_size=SIZE,
                              color_scheme="light", reduced_motion="reduce")
    page = ctx.new_page()
    t_page = time.monotonic()
    page.goto(f"{BASE}demos/{slug}.html?autoplay=1&seconds={SECONDS}", wait_until="load")
    page.wait_for_function("document.body.dataset.scene === '1'")
    t_play = time.monotonic()
    captions = page.eval_on_selector_all(".scene", "els => els.map(e => e.dataset.caption)")
    page.wait_for_function("document.body.dataset.finished === 'true'", timeout=SECONDS * 1000 * (len(captions) + 3))
    page.wait_for_timeout(int(SECONDS * 1000))  # hold the last scene
    video_path = page.video.path()
    ctx.close()
    return video_path, t_play - t_page, captions


def main():
    os.makedirs(OUT, exist_ok=True)
    slugs = [p["slug"] for p in json.load(open(os.path.join(ROOT, "site", "src", "content.json")))["projects"]]
    if len(sys.argv) > 1:
        slugs = [s for s in slugs if s in sys.argv[1:]]
    tmp = tempfile.mkdtemp()
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=os.environ.get("CHROME_PATH", "/usr/bin/google-chrome"),
                                    args=["--no-sandbox"])
        for slug in slugs:
            webm, offset, captions = record(browser, slug, tmp)
            mp4 = os.path.join(OUT, slug + ".mp4")
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{offset:.2f}", "-i", webm,
                            "-c:v", "libx264", "-preset", "veryfast", "-crf", "30", "-pix_fmt", "yuv420p",
                            "-movflags", "+faststart", "-an", mp4], check=True)
            lines = ["WEBVTT", ""]
            for i, cap in enumerate(captions):
                end = (i + 1) * SECONDS if i < len(captions) - 1 else (i + 2) * SECONDS
                lines += [str(i + 1), f"{ts(i * SECONDS)} --> {ts(end)}", cap, ""]
            with open(os.path.join(OUT, slug + ".vtt"), "w", encoding="utf-8") as fh:
                fh.write("\n".join(lines))
            print(f"recorded {slug}: {len(captions)} scenes")
        browser.close()
    shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
