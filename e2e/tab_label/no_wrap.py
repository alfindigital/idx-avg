"""
Verify the "Target Rata-rata" tab label never wraps to a second line across
a range of viewport widths.

Strategy
--------
- Load the app at several widths (320 → 1440 CSS px), locate the tab button
  by role/name, and read the rendered <button> box vs its computed
  line-height.
- A tab wraps when the button's client height exceeds ~1.5× the computed
  line-height (i.e. it took more than one text line). We also assert
  scrollWidth <= clientWidth + 1px (no horizontal clipping either) and that
  the button has `white-space: nowrap` applied.

Exit 0 on success, 1 on any failure.
"""

from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path

from playwright.async_api import async_playwright

SHOTS = Path("/tmp/browser/tab_label_no_wrap")
SHOTS.mkdir(parents=True, exist_ok=True)

VIEWPORTS = [320, 360, 375, 390, 414, 480, 640, 768, 1024, 1280, 1440]

BASE_URL = "http://localhost:8080"


async def check_viewport(pw, width: int) -> list[str]:
    errors: list[str] = []
    browser_ctx = await pw.chromium.launch(headless=True)
    try:
        context = await browser_ctx.new_context(
            viewport={"width": width, "height": 900},
            device_scale_factor=1,
            reduced_motion="reduce",
        )
        page = await context.new_page()
        await page.goto(BASE_URL, wait_until="domcontentloaded")
        await page.wait_for_timeout(500)

        # Locate the tab by accessible name (matches both id + en labels).
        tab = page.get_by_role(
            "tab", name=re.compile(r"target\s+(rata-rata|avg)", re.I)
        ).first
        await tab.wait_for(state="visible", timeout=3000)

        metrics = await tab.evaluate(
            """(el) => {
                const cs = window.getComputedStyle(el);
                const lh = parseFloat(cs.lineHeight);
                const fs = parseFloat(cs.fontSize);
                const rect = el.getBoundingClientRect();
                // Height of the inner text: use the first text node's client rect
                // via a Range so padding is not counted.
                const range = document.createRange();
                range.selectNodeContents(el);
                const trect = range.getBoundingClientRect();
                return {
                    text: el.textContent,
                    whiteSpace: cs.whiteSpace,
                    lineHeight: isFinite(lh) ? lh : fs * 1.2,
                    fontSize: fs,
                    clientWidth: el.clientWidth,
                    scrollWidth: el.scrollWidth,
                    textHeight: trect.height,
                    boxHeight: rect.height,
                };
            }"""
        )

        await page.screenshot(path=str(SHOTS / f"{width}w.png"))

        text = (metrics["text"] or "").strip()
        if not text:
            errors.append(f"[{width}w] tab has empty text")

        if "nowrap" not in metrics["whiteSpace"]:
            errors.append(
                f"[{width}w] tab white-space is '{metrics['whiteSpace']}' — expected nowrap"
            )

        # Wrapping detection: text height > ~1.5 * line-height means 2+ lines.
        lh = metrics["lineHeight"] or (metrics["fontSize"] * 1.2)
        if metrics["textHeight"] > lh * 1.6:
            errors.append(
                f"[{width}w] tab wrapped: textHeight={metrics['textHeight']:.1f}px "
                f"> 1.6× line-height ({lh:.1f}px)"
            )

        if metrics["scrollWidth"] > metrics["clientWidth"] + 1:
            errors.append(
                f"[{width}w] tab text clipped: scrollWidth={metrics['scrollWidth']} "
                f"> clientWidth={metrics['clientWidth']}"
            )

        await context.close()
    finally:
        await browser_ctx.close()
    return errors


async def main() -> int:
    all_errors: list[str] = []
    async with async_playwright() as pw:
        for w in VIEWPORTS:
            errs = await check_viewport(pw, w)
            if errs:
                all_errors.extend(errs)
                print(f"  [FAIL] {w}w")
                for e in errs:
                    print(f"         · {e}")
            else:
                print(f"  [ OK ] {w}w")

    print(f"\nScreenshots: {SHOTS}")
    if all_errors:
        print(f"\n{len(all_errors)} failure(s)")
        return 1
    print("\n'Target Rata-rata' tab stays on one line at every viewport.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
