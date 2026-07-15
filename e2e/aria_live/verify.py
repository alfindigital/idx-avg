"""
Verify the aria-live status region only announces the LATEST result after
Ctrl+Enter, without stale duplicates or re-announcing previous updates.

Checks:
  1. Region exists exactly once, with role="status", aria-live="polite",
     aria-atomic="true". A single atomic region guarantees AT clients read
     the current content — not a growing log.
  2. Empty on first paint (no announcement before the user acts).
  3. After Ctrl+Enter with valid inputs → region contains a non-empty string
     matching the freshly rendered result (avg baru + percentage).
  4. Change inputs (result card auto-clears) then Ctrl+Enter again → region
     text REPLACES the previous message; it does not append/duplicate, and
     the new value is reflected (not the stale one).
  5. Region's DOM node is stable (same element) — a new node each time would
     defeat aria-atomic semantics in some screen readers.

Usage:
  python3 e2e/aria_live/verify.py [--base-url http://localhost:8080]
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from playwright.async_api import Page, async_playwright

LIVE_SEL = '[role="status"][aria-live="polite"]'


async def settle(page: Page) -> None:
    await page.wait_for_load_state("networkidle")
    await page.wait_for_timeout(800)


async def live_text(page: Page) -> str:
    return (await page.locator(LIVE_SEL).first.inner_text()).strip()


async def fill(page: Page, avg: str, lot: str, harga: str, tambah: str) -> None:
    await page.locator("#avg-now-input").fill(avg)
    await page.locator("#total-lot-input").fill(lot)
    await page.locator("#harga-avg-input").fill(harga)
    await page.locator("#lot-tambah-input").fill(tambah)
    await page.locator("#lot-tambah-input").blur()


async def submit(page: Page) -> None:
    await page.locator("#lot-tambah-input").focus()
    await page.keyboard.press("Control+Enter")
    await page.locator('[aria-labelledby="result-heading"]').first.wait_for(
        state="visible", timeout=3000
    )
    # Let the announce effect flush.
    await page.wait_for_timeout(250)


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://localhost:8080")
    args = ap.parse_args()

    failures: list[str] = []
    notes: list[str] = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(viewport={"width": 390, "height": 900})
        page = await ctx.new_page()
        await page.goto(args.base_url, wait_until="domcontentloaded")
        await settle(page)

        # 1. Region invariants.
        count = await page.locator(LIVE_SEL).count()
        if count != 1:
            failures.append(f"[region] expected 1 status region, found {count}")
        else:
            attrs = await page.locator(LIVE_SEL).first.evaluate(
                "el => ({atomic: el.getAttribute('aria-atomic'), live: el.getAttribute('aria-live'), role: el.getAttribute('role')})"
            )
            if attrs.get("atomic") != "true":
                failures.append(f"[region] aria-atomic must be 'true', got {attrs}")
            notes.append(f"[region] OK ({attrs})")

        # Capture the DOM node identity so we can verify it stays the same
        # across updates (a stable node is what makes aria-atomic meaningful).
        await page.locator(LIVE_SEL).first.evaluate(
            "el => { window.__liveNode = el; }"
        )

        # 2. Empty on first paint.
        initial = await live_text(page)
        if initial:
            failures.append(f"[initial] region should be empty, got '{initial}'")
        else:
            notes.append("[initial] region empty OK")

        # 3. First calc.
        await fill(page, "1000", "10", "900", "5")
        await submit(page)
        first = await live_text(page)
        if not first:
            failures.append("[calc-1] region empty after Ctrl+Enter")
        elif not re.search(r"\d", first):
            failures.append(f"[calc-1] no numeric content: '{first}'")
        else:
            # Percentage between 900 and 1000 with 5 extra lot on 10 lot:
            # newAvg = (1000*10 + 900*5)/15 ≈ 966.67 → ~3.33% turun.
            if "3.33" not in first:
                failures.append(f"[calc-1] expected '3.33%' in announcement, got '{first}'")
            else:
                notes.append(f"[calc-1] announced: {first[:80]}")

        # 4. Change inputs → result card clears (autoreset effect), then re-submit.
        await page.locator("#harga-avg-input").fill("800")
        await page.wait_for_timeout(200)
        # Result card should be gone now.
        if await page.locator('[aria-labelledby="result-heading"]').count():
            failures.append("[reset] result card did not clear on input change")

        await submit(page)
        second = await live_text(page)
        if not second:
            failures.append("[calc-2] region empty after second Ctrl+Enter")
        elif second == first:
            failures.append(f"[calc-2] announcement did not update (still '{second}')")
        else:
            # newAvg = (1000*10 + 800*5)/15 ≈ 933.33 → ~6.67% turun.
            if "6.67" not in second:
                failures.append(f"[calc-2] expected '6.67%' in second announcement, got '{second}'")
            # The stale value from the first calc must NOT be present anymore.
            if "3.33" in second:
                failures.append(f"[calc-2] stale '3.33%' still present: '{second}'")
            notes.append(f"[calc-2] announced: {second[:80]}")

        # 5. Region node stability + no accumulated children.
        stability = await page.locator(LIVE_SEL).first.evaluate(
            """el => ({
                same: el === window.__liveNode,
                childCount: el.childNodes.length,
                textLen: (el.textContent || '').length,
            })"""
        )
        if not stability["same"]:
            failures.append("[stability] status region was replaced with a new node")
        # aria-atomic region should render a single text node (React string child).
        if stability["childCount"] > 1:
            failures.append(
                f"[stability] region has {stability['childCount']} child nodes — "
                "expected 1 (screen readers may otherwise concat old + new)"
            )
        notes.append(f"[stability] {stability}")

        await browser.close()

    print("\n--- aria-live verification ---")
    for n in notes:
        print(f"  ok  {n}")
    for f in failures:
        print(f"  FAIL {f}")
    print(f"\n{'PASS' if not failures else 'FAIL'} — {len(failures)} failure(s)")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
