"""
E2E: verify IDX tick-size snapping on blur across all price inputs, at prices
that sit exactly on the boundary between two tick bands (just below / just
above), and confirm the result card reflects the snapped values — no stale
un-snapped digits leak through.

IDX tick bands (from src/lib/idx-tick.ts):
  price < 200   -> tick 1
  price < 500   -> tick 2
  price < 2000  -> tick 5
  price < 5000  -> tick 10
  price >= 5000 -> tick 25
"""

from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path
from playwright.async_api import Page, async_playwright

SHOTS = Path(__file__).parent / "screenshots"
SHOTS.mkdir(parents=True, exist_ok=True)

# (raw_input, expected_after_blur)
# Chosen to exercise both sides of every band boundary plus mid-band snaps.
CASES: list[tuple[str, str]] = [
    ("199", "199"),      # tick 1, just below 200
    ("201", "202"),      # tick 2, just above 200 → 100.5*2 → 202
    ("499", "500"),      # tick 2, boundary crossover to next band multiple
    ("501", "500"),      # tick 5, just above 500 → 100.2*5 → 500
    ("1998", "2000"),    # tick 5, just below 2000
    ("2002", "2000"),    # tick 10, just above 2000
    ("4998", "5000"),    # tick 10, just below 5000
    ("5002", "5000"),    # tick 25, just above 5000
    ("5013", "5025"),    # tick 25, mid-band
]

PRICE_INPUTS = ["#avg-now-input", "#harga-avg-input"]  # target-avg also below


async def set_and_blur(page: Page, sel: str, value: str) -> str:
    loc = page.locator(sel)
    await loc.focus()
    await page.keyboard.press("Control+A")
    await page.keyboard.press("Delete")
    await page.keyboard.type(value, delay=8)
    await loc.evaluate("el => el.blur()")
    await page.wait_for_timeout(80)
    return await loc.input_value()


async def run() -> int:
    errors: list[str] = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(viewport={"width": 1280, "height": 1800})
        page = await ctx.new_page()
        await page.goto("http://localhost:8080", wait_until="domcontentloaded")
        await page.wait_for_load_state("networkidle")
        await page.evaluate("() => localStorage.clear()")
        await page.reload(wait_until="networkidle")
        await page.wait_for_timeout(200)

        # --- Per-input snapping ---------------------------------------
        for sel in PRICE_INPUTS:
            for raw, want in CASES:
                got = await set_and_blur(page, sel, raw)
                if got != want:
                    errors.append(f"{sel} raw={raw!r} → blur={got!r}, expected {want!r}")

        # Target-avg only exists in lots-needed mode: switch to it via keyboard.
        tabs = page.locator('[role="tab"]')
        await tabs.nth(1).focus()
        await page.keyboard.press("Space")
        await page.wait_for_timeout(150)
        for raw, want in CASES:
            got = await set_and_blur(page, "#target-avg-input", raw)
            if got != want:
                errors.append(f"#target-avg-input raw={raw!r} → blur={got!r}, expected {want!r}")

        await page.screenshot(path=str(SHOTS / "1_per_input_snapping.png"))

        # --- Result card consistency after boundary snapping ----------
        # Switch back to new-avg mode.
        await tabs.nth(0).focus()
        await page.keyboard.press("Space")
        await page.wait_for_timeout(150)

        # Use boundary values: avg 1998→2000, harga 2002→2000 (both snap to
        # 2000). newAvg with lot 10 + tambah 5 must therefore be exactly 2000.
        await set_and_blur(page, "#avg-now-input", "1998")
        await set_and_blur(page, "#total-lot-input", "10")
        await set_and_blur(page, "#harga-avg-input", "2002")
        await set_and_blur(page, "#lot-tambah-input", "5")

        # Confirm both price inputs snapped.
        v_avg = await page.locator("#avg-now-input").input_value()
        v_harga = await page.locator("#harga-avg-input").input_value()
        if v_avg != "2000":
            errors.append(f"[calc-setup] avg-now not snapped: {v_avg!r}")
        if v_harga != "2000":
            errors.append(f"[calc-setup] harga-avg not snapped: {v_harga!r}")

        await page.locator("#lot-tambah-input").focus()
        await page.keyboard.press("Control+Enter")
        await page.locator('[aria-labelledby="result-heading"]').wait_for(
            state="visible", timeout=3000
        )
        await page.wait_for_timeout(200)

        card_text = await page.locator('[aria-labelledby="result-heading"]').inner_text()
        norm = re.sub(r"\s+", " ", card_text)
        # Expected new avg = 2000; also must itself be tick-aligned (2000 mod 25 == 0).
        if not re.search(r"Rp\s?2\.000\b", norm):
            errors.append(f"[card] expected 'Rp 2.000' in result card; got: {norm[:400]}")
        # No stale un-snapped digits from 1998 / 2002 should leak into the card.
        for stale in ("1.998", "2.002", "1998", "2002"):
            if stale in card_text:
                errors.append(f"[card] stale un-snapped value {stale!r} leaked into card")
        await page.screenshot(path=str(SHOTS / "2_card_after_snap.png"))

        # --- Reverse case: mid-band snap that changes value visibly ---
        # 5013 → 5025 (tick 25). Use identical avg/harga so newAvg = 5025.
        await set_and_blur(page, "#avg-now-input", "5013")
        await set_and_blur(page, "#harga-avg-input", "5013")
        # lots stay at 10 and 5.
        await page.locator("#lot-tambah-input").focus()
        await page.keyboard.press("Control+Enter")
        await page.wait_for_timeout(300)
        card_text2 = await page.locator('[aria-labelledby="result-heading"]').inner_text()
        if not re.search(r"Rp\s?5\.025\b", re.sub(r"\s+", " ", card_text2)):
            errors.append(f"[card-2] expected 'Rp 5.025' after 5013→5025 snap; got: {card_text2[:400]}")
        if "5.013" in card_text2 or "5013" in card_text2:
            errors.append("[card-2] stale 5013 leaked into card after mid-band snap")
        await page.screenshot(path=str(SHOTS / "3_midband_snap.png"))

        await browser.close()

    if errors:
        print("FAIL")
        for e in errors:
            print("  -", e)
        return 1
    print(f"PASS — {len(CASES) * (len(PRICE_INPUTS) + 1)} boundary snaps + 2 result cards verified")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(run()))
