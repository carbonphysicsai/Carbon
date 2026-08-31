#!/usr/bin/env python3
"""Optional browser smoke test for the Carbon Development Hub.

The required validator uses only the Python standard library. This optional
check uses Playwright when available to render the primary static-first HTML
with JavaScript enabled and disabled, then renders the optional interactive
view. HTML is loaded from memory so restricted file-URL policies cannot mask
the result.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "index.html"
INTERACTIVE = ROOT / "interactive.html"


def chromium_path() -> str | None:
    explicit = os.environ.get("HUB_CHROMIUM")
    if explicit and Path(explicit).exists():
        return explicit
    for name in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable"):
        path = shutil.which(name)
        if path:
            return path
    return None


def main() -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("SKIP: Playwright is unavailable; validate_hub.py still enforces static content.")
        return

    executable = chromium_path()
    with sync_playwright() as playwright:
        kwargs = {"headless": True, "args": ["--no-sandbox", "--disable-dev-shm-usage"]}
        if executable:
            kwargs["executable_path"] = executable
        try:
            browser = playwright.chromium.launch(**kwargs)
        except Exception as exc:
            print(f"SKIP: Chromium could not launch: {exc}")
            return

        index_html = INDEX.read_text(encoding="utf-8")
        errors: list[str] = []
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.set_content(index_html, wait_until="load", timeout=30_000)
        visible = page.locator("#hub-content").inner_text().strip()
        if len(visible) < 12_000:
            raise SystemExit(f"FAIL: primary index rendered only {len(visible)} visible characters")
        if "Understand what is changing and why." not in visible:
            raise SystemExit("FAIL: primary index lacks the orientation heading")
        if errors:
            raise SystemExit(f"FAIL: primary index browser errors: {errors}")

        nojs_context = browser.new_context(java_script_enabled=False, viewport={"width": 1440, "height": 1000})
        nojs = nojs_context.new_page()
        nojs.set_content(index_html, wait_until="load", timeout=30_000)
        nojs_visible = nojs.locator("#hub-content").inner_text().strip()
        if len(nojs_visible) < 12_000:
            raise SystemExit(f"FAIL: no-script index rendered only {len(nojs_visible)} visible characters")
        if visible != nojs_visible:
            raise SystemExit("FAIL: primary index content differs with JavaScript disabled")
        nojs_context.close()

        interactive_visible = 0
        if INTERACTIVE.exists():
            app_html = INTERACTIVE.read_text(encoding="utf-8")
            app = browser.new_page(viewport={"width": 1440, "height": 1000})
            app_errors: list[str] = []
            app.on("pageerror", lambda error: app_errors.append(str(error)))
            app.set_content(app_html, wait_until="load", timeout=30_000)
            app.wait_for_timeout(250)
            interactive_visible = len(app.locator("#view").inner_text().strip())
            if interactive_visible < 500:
                raise SystemExit("FAIL: optional interactive view rendered too little content")
            if app_errors:
                raise SystemExit(f"FAIL: optional interactive view browser errors: {app_errors}")

        browser.close()

    print(
        "PASS: primary index rendered "
        f"{len(visible)} characters with scripts enabled and disabled; "
        f"optional interactive view rendered {interactive_visible} characters."
    )


if __name__ == "__main__":
    main()
