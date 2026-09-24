"""Capture full-page screenshots of every app page with Playwright (for QA and the README).

The app must already be running, e.g. ``streamlit run app.py --server.port 8511``.

Usage::

    python scripts/screenshots.py --base-url http://localhost:8511 --out docs/screenshots
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

PAGES = {
    "dashboard": "/",
    "sku_explorer": "/sku_explorer",
    "sku_story": "/sku_explorer?sku=BTH-002",
    "replenishment": "/replenishment",
    "suppliers": "/suppliers",
    "backtest": "/backtest",
    "methodology": "/methodology",
    "about": "/about",
}


def capture(base_url: str, out: Path, width: int, height: int, full_page: bool, settle: float) -> None:
    out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=1)
        for name, path in PAGES.items():
            page.goto(base_url.rstrip("/") + path, wait_until="networkidle")
            # Streamlit renders progressively; wait until the status widget is idle and charts have drawn.
            page.wait_for_function(
                "() => !document.querySelector('[data-testid=\"stStatusWidget\"]')", timeout=60_000
            )
            time.sleep(settle)
            if full_page:
                # Streamlit scrolls inside its main section, so grow the viewport to the content height instead.
                content_height = page.evaluate(
                    "() => { const m = document.querySelector('[data-testid=\"stMain\"]') || document.body; return m.scrollHeight; }"
                )
                page.set_viewport_size({"width": width, "height": min(int(content_height) + 40, 8000)})
                time.sleep(settle)
            target = out / f"{name}.png"
            page.screenshot(path=str(target))
            page.set_viewport_size({"width": width, "height": height})
            print(f"saved {target}")
        browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8511")
    parser.add_argument("--out", type=Path, default=Path("docs/screenshots"))
    parser.add_argument("--width", type=int, default=1440)
    parser.add_argument("--height", type=int, default=900)
    parser.add_argument(
        "--viewport-only", action="store_true", help="capture only the first screen instead of the full page"
    )
    parser.add_argument(
        "--settle", type=float, default=2.5, help="seconds to wait after the page reports idle"
    )
    args = parser.parse_args()
    capture(args.base_url, args.out, args.width, args.height, not args.viewport_only, args.settle)
