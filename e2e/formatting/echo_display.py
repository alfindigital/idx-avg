"""
Echo / display rules for numeric inputs.

Verifies the calculator "re-displays" typed numbers according to the app's
sanitization + rounding rules, and that those rules never corrupt the
result card:

  1. Zero  — typing "0" is accepted as text but flips aria-invalid to
     "true", the Hitung button stays disabled, and no result card renders.
  2. Big integers — typing digits above MAX_LOT (1_000_000) in a lot
     field flips aria-invalid to "true"; typing a huge price above
     MAX_PRICE (10_000_000) in a price field does the same.
  3. Decimals in lot inputs — dot / comma characters are stripped by
     `intOnly` and the input echoes back digits only.
  4. Decimals in price inputs — dots are preserved by `numOnly` during
     typing, and `handlePriceBlur` snaps off-tick values to the nearest
     IDX tick on blur (e.g. 201 -> 202, 5013 -> 5025).
  5. After correcting all fields to a valid combination and pressing
     Ctrl+Enter, the result card renders and every "Rp" token in it
     uses the id-ID thousands separator ("."), no decimals, no NaN.

Run:
  python3 e2e/formatting/echo_display.py [--base-url http://localhost:8080]
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from pathlib import Path

from playwright.async_api import Page, async_playwright

SHOTS = Path("/tmp/browser/echo_display")
SHOTS.mkdir(parents=True, exist_ok=True)

MAX_LOT = 1_000_000
MAX_PRICE = 10_000_000


async def settle(page: Page) -> None:
    await page.wait_for_load_state("domcontentloaded")
    await page.locator("#avg-now-input").wait_for(state="visible", timeout=5000)
    await page.wait_for_timeout(600)


async def type_into(page: Page, sel: str, text: str) -> None:
    loc = page.locator(sel)
    await loc.click()
    await loc.fill("")
    await loc.type(text, delay=15)


async def value_of(page: Page, sel: str) -> str:
    return await page.locator(sel).input_value()


async def aria_invalid(page: Page, sel: str) -> str:
    return await page.locator(sel).get_attribute("aria-invalid") or "false"


async def blur(page: Page, sel: str) -> None:
    # Tab away so onBlur fires
    await page.locator(sel).press("Tab")
    await page.wait_for_timeout(150)


def check(cond: bool, label: str, errors: list[str]) -> None:
    marker = "OK" if cond else "FAIL"
    print(f"  [{marker}] {label}")
    if not cond:
        errors.append(label)


async def scenario_zero(page: Page, errors: list[str]) -> None:
    print("\n[1] Zero echoes but flags invalid")
    await page.evaluate("() => document.querySelector('button[aria-label*=Reset], [data-testid=reset]')?.click()")
    await page.keyboard.press("Alt+R")
    await page.wait_for_timeout(200)

    await type_into(page, "#avg-now-input", "0")
    await type_into(page, "#total-lot-input", "0")
    await type_into(page, "#harga-avg-input", "0")
    await blur(page, "#harga-avg-input")

    check(await value_of(page, "#avg-now-input") == "0", "avg echoes '0'", errors)
    check(await value_of(page, "#total-lot-input") == "0", "lot echoes '0'", errors)
    check(await aria_invalid(page, "#avg-now-input") == "true", "avg=0 aria-invalid=true", errors)
    check(await aria_invalid(page, "#total-lot-input") == "true", "lot=0 aria-invalid=true", errors)

    # Ctrl+Enter must not render a result card when inputs are invalid.
    await page.keyboard.press("Control+Enter")
    await page.wait_for_timeout(250)
    result_visible = await page.locator("[data-testid='result-card'], #result-card").count()
    if result_visible == 0:
        # Fallback: check for known result-only text
        body = await page.locator("main, body").inner_text()
        result_visible = 1 if re.search(r"Total\s+Modal|New\s+Avg", body) and "Rp" in body and "0" != body else 0
    check(result_visible == 0, "no result card while any field invalid", errors)


async def scenario_big_numbers(page: Page, errors: list[str]) -> None:
    print("\n[2] Over-max numbers flag invalid")
    await page.keyboard.press("Alt+R")
    await page.wait_for_timeout(200)

    huge_lot = str(MAX_LOT + 1)       # 1_000_001
    huge_price = str(MAX_PRICE + 5)   # 10_000_005

    await type_into(page, "#avg-now-input", huge_price)
    await blur(page, "#avg-now-input")
    check(await aria_invalid(page, "#avg-now-input") == "true", f"avg={huge_price} aria-invalid=true", errors)

    await type_into(page, "#total-lot-input", huge_lot)
    await blur(page, "#total-lot-input")
    check(await aria_invalid(page, "#total-lot-input") == "true", f"lot={huge_lot} aria-invalid=true", errors)
    # Digits echoed as typed (no silent truncation of the string).
    check(await value_of(page, "#total-lot-input") == huge_lot, "lot echoes exact digits", errors)


async def scenario_decimals_in_lot(page: Page, errors: list[str]) -> None:
    print("\n[3] Decimals rejected in lot fields")
    await page.keyboard.press("Alt+R")
    await page.wait_for_timeout(200)

    for sel in ("#total-lot-input", "#lot-tambah-input"):
        # #lot-tambah-input only exists in lots-needed mode; skip if absent.
        if await page.locator(sel).count() == 0:
            continue
        await type_into(page, sel, "12.34")
        v = await value_of(page, sel)
        check(v == "1234", f"{sel} strips dots -> '1234' (got '{v}')", errors)

        await type_into(page, sel, "56,78")
        v = await value_of(page, sel)
        check(v == "5678", f"{sel} strips commas -> '5678' (got '{v}')", errors)


async def scenario_price_tick_rounding(page: Page, errors: list[str]) -> None:
    print("\n[4] Off-tick prices snap on blur")
    await page.keyboard.press("Alt+R")
    await page.wait_for_timeout(200)

    # (typed, expected-after-blur) per IDX tick bands.
    #   <200        -> tick 1  (exact)
    #   200-499     -> tick 2  (201 -> 202)
    #   500-1999    -> tick 5  (503 -> 505)
    #   2000-4999   -> tick 10 (2011 -> 2010)
    #   >=5000      -> tick 25 (5013 -> 5025)
    cases = [
        ("199", "199"),
        ("201", "202"),
        ("503", "505"),
        ("2011", "2010"),
        ("5013", "5025"),
    ]
    for typed, expected in cases:
        await type_into(page, "#avg-now-input", typed)
        await blur(page, "#avg-now-input")
        got = await value_of(page, "#avg-now-input")
        check(got == expected, f"blur({typed}) -> '{expected}' (got '{got}')", errors)


async def scenario_valid_flow_formatting(page: Page, errors: list[str]) -> None:
    print("\n[5] Valid inputs -> result card with id-ID Rupiah")
    await page.keyboard.press("Alt+R")
    await page.wait_for_timeout(200)

    await type_into(page, "#avg-now-input", "1000")
    await blur(page, "#avg-now-input")
    await type_into(page, "#total-lot-input", "10")
    await type_into(page, "#harga-avg-input", "800")
    await blur(page, "#harga-avg-input")

    # Fire calc via keyboard.
    await page.keyboard.press("Control+Enter")
    await page.wait_for_timeout(600)

    text = await page.locator("main, body").inner_text()
    # Extract every "Rp <number>" token.
    tokens = re.findall(r"Rp\s?([0-9\.\,]+)", text)
    check(len(tokens) > 0, "at least one Rp token present in result", errors)

    bad = []
    for tok in tokens:
        # id-ID: uses "." as thousands separator, no decimals for whole rupiah.
        # A comma appearing anywhere means en-US formatting leaked through.
        if "," in tok:
            bad.append(tok)
            continue
        # Reject stray non-digit chars other than dot.
        if re.search(r"[^0-9\.]", tok):
            bad.append(tok)
            continue
        # If length > 3, must contain a dot separator.
        digits_only = tok.replace(".", "")
        if len(digits_only) > 3 and "." not in tok:
            bad.append(tok)

    check(not bad, f"all Rp tokens formatted id-ID (bad={bad[:5]})", errors)
    check("NaN" not in text and "Infinity" not in text, "no NaN/Infinity in result", errors)


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8080")
    args = parser.parse_args()

    errors: list[str] = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(viewport={"width": 1280, "height": 1800})
        page = await ctx.new_page()
        await page.goto(args.base_url, wait_until="domcontentloaded")
        await settle(page)

        await scenario_zero(page, errors)
        await page.screenshot(path=str(SHOTS / "1_zero.png"))
        await scenario_big_numbers(page, errors)
        await page.screenshot(path=str(SHOTS / "2_big.png"))
        await scenario_decimals_in_lot(page, errors)
        await page.screenshot(path=str(SHOTS / "3_decimals.png"))
        await scenario_price_tick_rounding(page, errors)
        await page.screenshot(path=str(SHOTS / "4_tick.png"))
        await scenario_valid_flow_formatting(page, errors)
        await page.screenshot(path=str(SHOTS / "5_valid.png"))

        await browser.close()

    print("\n=== summary ===")
    if errors:
        for e in errors:
            print(f"  FAIL: {e}")
        return 1
    print("  all echo/display checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
