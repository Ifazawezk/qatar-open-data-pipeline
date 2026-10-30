"""Take screenshots of every dashboard page for the README.

Starts the Streamlit app on a spare port, opens each page in a headless
browser, waits for the charts to draw and saves a PNG in docs/images.
Needs Playwright (`pip install playwright`). It uses the Microsoft Edge or
Google Chrome already installed on the machine; otherwise run
`python -m playwright install chromium` once.

    python scripts/screenshots.py
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "images"

PAGES = {
    "overview": "",
    "population": "population",
    "prices": "prices",
    "travel": "travel",
    "utilities": "utilities",
    "pipeline": "pipeline",
}


def wait_until_up(url: str, timeout: float = 60) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{url}/_stcore/health", timeout=2) as response:
                if response.status == 200:
                    return
        except OSError:
            time.sleep(0.5)
    raise RuntimeError(f"streamlit did not start at {url}")


def wait_for_charts(page, timeout: float = 30) -> None:
    """Wait until the script has finished and every Plotly chart has drawn."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        page.wait_for_timeout(500)
        running = page.locator('[data-testid="stStatusWidget"]').count()
        expected = page.locator('[data-testid="stPlotlyChart"]').count()
        drawn = page.locator('[data-testid="stPlotlyChart"] .js-plotly-plot').count()
        if not running and drawn >= expected:
            page.wait_for_timeout(800)
            return
    raise RuntimeError("charts did not finish drawing")


def launch_browser(playwright):
    for channel in ("msedge", "chrome", None):
        try:
            return (
                playwright.chromium.launch(channel=channel)
                if channel
                else (playwright.chromium.launch())
            )
        except Exception:  # noqa: BLE001 - try the next browser
            continue
    raise RuntimeError("no browser found; run `python -m playwright install chromium`")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", type=int, default=8599)
    parser.add_argument("--width", type=int, default=1440)
    parser.add_argument("--only", nargs="+", choices=sorted(PAGES))
    args = parser.parse_args()

    from playwright.sync_api import sync_playwright

    url = f"http://localhost:{args.port}"
    server = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            "dashboard/app.py",
            "--server.port",
            str(args.port),
            "--server.headless",
            "true",
        ],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        wait_until_up(url)
        OUT.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as p:
            browser = launch_browser(p)
            page = browser.new_page(viewport={"width": args.width, "height": 900})
            for name in args.only or PAGES:
                page.set_viewport_size({"width": args.width, "height": 900})
                page.goto(f"{url}/{PAGES[name]}", wait_until="networkidle")
                page.wait_for_selector("h1", timeout=30_000)
                wait_for_charts(page)
                # Streamlit scrolls an inner container, so grow the window to
                # the content height to capture the whole page.
                height = page.evaluate(
                    "() => document.querySelector('[data-testid=\"stMain\"]').scrollHeight"
                )
                page.set_viewport_size({"width": args.width, "height": int(height) + 40})
                wait_for_charts(page)
                path = OUT / f"{name}.png"
                page.screenshot(path=str(path))
                print(f"saved {path.relative_to(ROOT)}")
            browser.close()
    finally:
        server.terminate()
        server.wait(timeout=20)
    return 0


if __name__ == "__main__":
    sys.exit(main())
