"""
Verify the sr-only result summary paragraph and the aria-live status region
stay in sync with the current calculation, mode, and inputs.

Checks (Indonesian locale, default):
  1. Before Calculate → no sr-only summary rendered, live region empty.
  2. Mode "new-avg" → after Ctrl+Enter:
       - sr-only <p> inside [data-result-card] contains:
         "Ringkasan hasil", trend phrase ("Averaging Naik/Turun/Flat"),
         percentage with two decimals, "Avg Baru" label, formatted rupiah
         head value, and "Total Modal" line.
       - aria-live region text contains the same trend + percentage + head.
  3. Mode switch to "lots-needed" clears the result card (announcement text
     is not re-triggered until user recalculates); after filling target and
     Ctrl+Enter:
       - sr-only summary now mentions "Lot Diperlukan" (not "Avg Baru") and
         the head value is formatted as "<int> lot baru".
       - aria-live text updates to the new mode (differs from step 2).
  4. Changing an input after a valid calc removes the result card entirely
     (no sr-only summary present).

Usage:
  python3 e2e/aria_live/summary.py [--base-url http://localhost:8080]
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from pathlib import Path

from playwright.async_api import Page, async_playwright

LIVE_SEL = '[role="status"][aria-live="polite"]'
CARD_SEL = "[data-result-card]"
SR_SUMMARY_SEL = f"{CARD_SEL} p.sr-only"

SHOTS = Path(__file__).parent / "screenshots"
SHOTS.mkdir(parents=True, exist_ok=True)


async def settle(page: Page) -> None:
    await page.wait_for_load_state("networkidle")
    await page.wait_for_timeout(400)


async def live_text(page: Page) -> str:
    return (await page.locator(LIVE_SEL).first.inner_text()).strip()


async def summary_text(page: Page) -> str:
    loc = page.locator(SR_SUMMARY_SEL).first
    return (await loc.inner_text()).strip()


async def fill_base(page: Page, avg: str, lot: str, harga: str) -> None:
    await page.locator("#avg-now-input").fill(avg)
    await page.locator("#total-lot-input").fill(lot)
    await page.locator("#harga-avg-input").fill(harga)


async def submit(page: Page) -> None:
    await page.keyboard.press("Control+Enter")
    await page.locator(CARD_SEL).first.wait_for(state="visible", timeout=3000)
    await page.wait_for_timeout(250)  # let announce effect flush


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://localhost:8080")
    args = ap.parse_args()

    failures: list[str] = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(viewport={"width": 390, "height": 900})
        page = await ctx.new_page()
        await page.goto(args.base_url, wait_until="domcontentloaded")
        await settle(page)

        # 1. Pre-calc invariants.
        if await page.locator(SR_SUMMARY_SEL).count() != 0:
            failures.append("[pre] sr-only summary present before Calculate")
        if (initial := await live_text(page)) != "":
            failures.append(f"[pre] live region non-empty: {initial!r}")

        # 2. new-avg calculation — averaging DOWN scenario.
        # avg=2000, lot=10, harga=1500, tambah=10 → new avg 1750, -12.50%.
        await fill_base(page, "2000", "10", "1500")
        await page.locator("#lot-tambah-input").fill("10")
        await page.locator("#lot-tambah-input").blur()
        await submit(page)

        summary1 = await summary_text(page)
        live1 = await live_text(page)
        await page.screenshot(path=str(SHOTS / "1_new_avg.png"))

        must_have_1 = [
            "Result summary",
            "Averaging Down",
            "12.50%",
            "New Avg",
            "Rp 1.750",
            "Total Capital",
        ]
        for token in must_have_1:
            if token not in summary1:
                failures.append(f"[new-avg summary] missing {token!r}: {summary1!r}")
        for token in ("Averaging Down", "12.50%", "New Avg", "Rp 1.750"):
            if token not in live1:
                failures.append(f"[new-avg live] missing {token!r}: {live1!r}")

        # 3. Switch mode → recompute in lots-needed.
        await page.locator('[role="tab"][data-tab-value="lots-needed"]').click()
        await page.wait_for_timeout(200)

        await page.locator("#target-avg-input").fill("1800")
        await page.locator("#target-avg-input").blur()
        await submit(page)

        summary2 = await summary_text(page)
        live2 = await live_text(page)
        await page.screenshot(path=str(SHOTS / "2_lots_needed.png"))

        if "Lots Needed" not in summary2:
            failures.append(f"[lots-needed summary] missing 'Lots Needed': {summary2!r}")
        if re.search(r"New Avg:\s", summary2):
            failures.append(f"[lots-needed summary] unexpected 'New Avg' head: {summary2!r}")
        if not re.search(r"\d+\s+new lots", summary2):
            failures.append(f"[lots-needed summary] missing '<n> new lots': {summary2!r}")
        if "Lots Needed" not in live2:
            failures.append(f"[lots-needed live] missing 'Lots Needed': {live2!r}")
        if live2 == live1:
            failures.append("[lots-needed live] text did not change after mode switch")


        # 4. Changing an input removes the result card.
        await page.locator("#avg-now-input").fill("2100")
        await page.wait_for_timeout(200)
        if await page.locator(CARD_SEL).count() != 0:
            failures.append("[input-change] result card still present after edit")
        if await page.locator(SR_SUMMARY_SEL).count() != 0:
            failures.append("[input-change] sr-only summary still present after edit")

        await browser.close()

    if failures:
        print("FAIL")
        for f in failures:
            print(" -", f)
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
