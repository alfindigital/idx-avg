"""
Extreme-input stability for the calculator.

Exercises the boundaries around MAX_PRICE (1,000,000) and
MAX_LOT (1,000,000) plus the zero floor. The app must:

  · reject 0 with the "must be > 0" inline error (aria-invalid=true,
    role=alert), and Ctrl+Enter must not render a result card;
  · accept the exact maximum (MAX_PRICE, MAX_LOT) as valid — no alert,
    aria-invalid absent/false, submit renders a result card, and the
    DOM contains no NaN/Infinity;
  · reject values just past the maximum with the localized
    "Maks Rp 1.000.000" / "Maks 1.000.000 lot" errors, keep focus in
    the offending field on Ctrl+Enter, and NOT recompute the
    previously rendered card;
  · compute stably for a scenario using values near the maximum on
    every numeric input — total capital must be a well-formed
    id-ID Rupiah string and the arithmetic must not produce NaN.

Run:
  python3 e2e/validation/extreme_inputs.py [--base-url http://localhost:8080]
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from pathlib import Path

from playwright.async_api import Page, async_playwright

SHOTS = Path("/tmp/browser/extreme_inputs")
SHOTS.mkdir(parents=True, exist_ok=True)

MAX_PRICE = 1_000_000
MAX_LOT = 1_000_000
RESULT_SEL = '[aria-labelledby="result-heading"]'

PRICE_FIELDS = ("#avg-now-input", "#harga-avg-input")
LOT_FIELDS = ("#total-lot-input", "#lot-tambah-input")


async def settle(page: Page) -> None:
    await page.wait_for_load_state("domcontentloaded")
    await page.locator("#avg-now-input").wait_for(state="visible", timeout=5000)
    await page.wait_for_timeout(800)


async def submit(page: Page, from_sel: str = "#lot-tambah-input") -> None:
    await page.wait_for_timeout(120)
    await page.locator(from_sel).focus()
    await page.keyboard.press("Control+Enter")
    await page.wait_for_timeout(350)


async def field_state(page: Page, sel: str) -> dict:
    return await page.evaluate(
        """(sel) => {
            const el = document.querySelector(sel);
            if (!el) return null;
            let alert = null;
            const desc = el.getAttribute('aria-describedby');
            if (desc) {
                for (const id of desc.split(/\\s+/)) {
                    const n = document.getElementById(id);
                    if (n && n.getAttribute('role') === 'alert' && n.textContent.trim()) {
                        alert = n.textContent.trim();
                        break;
                    }
                }
            }
            return {
                value: el.value,
                ariaInvalid: el.getAttribute('aria-invalid'),
                focused: document.activeElement === el,
                alert,
            };
        }""",
        sel,
    )


async def result_html(page: Page) -> str | None:
    loc = page.locator(RESULT_SEL).first
    if await loc.count() == 0:
        return None
    return await loc.evaluate("(el) => el.outerHTML")


async def dom_has_nan(page: Page) -> bool:
    return await page.evaluate(
        "() => /\\bNaN\\b/.test(document.body.innerText || '') || /Infinity/.test(document.body.innerText || '')"
    )


async def fill(page: Page, sel: str, value: str) -> None:
    loc = page.locator(sel)
    await loc.click()
    await loc.press("Control+A")
    await loc.press("Delete")
    if value:
        for ch in value:
            await page.keyboard.type(ch, delay=8)
    await loc.blur()
    await page.wait_for_timeout(120)


async def scenario_zero_rejected(page: Page) -> list[str]:
    """Value 0 in any numeric field must show the positive error and block submit."""
    errs: list[str] = []
    # Seed a valid baseline first so only the zero field is invalid.
    await fill(page, "#avg-now-input", "1000")
    await fill(page, "#total-lot-input", "10")
    await fill(page, "#harga-avg-input", "900")
    await fill(page, "#lot-tambah-input", "5")
    await submit(page)
    await page.locator(RESULT_SEL).first.wait_for(state="visible", timeout=4000)
    baseline = await result_html(page)

    for sel in (*PRICE_FIELDS, *LOT_FIELDS):
        await fill(page, sel, "0")
        st = await field_state(page, sel)
        if st is None:
            errs.append(f"zero: {sel} not found")
            continue
        if st["ariaInvalid"] != "true":
            errs.append(f"zero: {sel} aria-invalid={st['ariaInvalid']!r} (want 'true')")
        if not st["alert"]:
            errs.append(f"zero: {sel} missing role=alert error text for value 0")
        # Try to submit — must not recompute the visible card.
        await submit(page, sel)
        after = await result_html(page)
        if after is not None and after != baseline:
            errs.append(
                f"zero: {sel} — result card recomputed while field was 0 "
                "(should keep last valid state or nothing)"
            )
        if await dom_has_nan(page):
            errs.append(f"zero: {sel} — DOM has NaN/Infinity after invalid submit")
        # Restore a valid value for the next iteration.
        default = "1000" if sel in PRICE_FIELDS else ("10" if sel == "#total-lot-input" else "5")
        await fill(page, sel, default)

    return errs


async def scenario_exact_max_ok(page: Page) -> list[str]:
    errs: list[str] = []
    # avg = MAX_PRICE (tick 25, 1_000_000 % 25 == 0 → valid), tot = MAX_LOT,
    # harga = MAX_PRICE - 25 (still valid tick), tambah = 1.
    await fill(page, "#avg-now-input", str(MAX_PRICE))
    await fill(page, "#total-lot-input", str(MAX_LOT))
    await fill(page, "#harga-avg-input", str(MAX_PRICE - 25))
    await fill(page, "#lot-tambah-input", "1")

    for sel in (*PRICE_FIELDS, *LOT_FIELDS):
        st = await field_state(page, sel)
        if st is None:
            errs.append(f"exact-max: {sel} not found")
            continue
        if st["ariaInvalid"] == "true":
            errs.append(f"exact-max: {sel} aria-invalid=true for boundary-valid value")
        if st["alert"]:
            errs.append(f"exact-max: {sel} unexpected inline error {st['alert']!r}")

    await submit(page)
    try:
        await page.locator(RESULT_SEL).first.wait_for(state="visible", timeout=4000)
    except Exception:
        errs.append("exact-max: result card did not render at exact MAX_PRICE/MAX_LOT")
    await page.wait_for_timeout(250)
    if await dom_has_nan(page):
        errs.append("exact-max: DOM contains NaN/Infinity after valid submit at limits")
    await page.screenshot(path=str(SHOTS / "1_exact_max.png"))
    return errs


async def scenario_over_max_rejected(page: Page) -> list[str]:
    errs: list[str] = []
    # Snapshot current (valid boundary) card first.
    baseline = await result_html(page)

    # Overshoot price on avg-now: MAX_PRICE + 25 to stay tick-aligned so the
    # ONLY reason for rejection is the max cap.
    await fill(page, "#avg-now-input", str(MAX_PRICE + 25))
    st = await field_state(page, "#avg-now-input")
    if st["ariaInvalid"] != "true" or not st["alert"] or "1.000.000" not in st["alert"]:
        errs.append(
            f"over-max price: aria-invalid={st['ariaInvalid']!r}, "
            f"alert={st['alert']!r} (expected max-price message with '1.000.000')"
        )
    # Ctrl+Enter must route focus back to the invalid field and not recompute.
    await submit(page, "#lot-tambah-input")
    st = await field_state(page, "#avg-now-input")
    if not st["focused"]:
        errs.append("over-max price: focus did not return to the invalid avg-now field")
    after = await result_html(page)
    if after is not None and after != baseline:
        errs.append("over-max price: result card recomputed while a field was over MAX_PRICE")

    # Restore, then overshoot lot.
    await fill(page, "#avg-now-input", str(MAX_PRICE))
    await fill(page, "#total-lot-input", str(MAX_LOT + 1))
    st = await field_state(page, "#total-lot-input")
    if st["ariaInvalid"] != "true" or not st["alert"] or "1.000.000" not in st["alert"]:
        errs.append(
            f"over-max lot: aria-invalid={st['ariaInvalid']!r}, "
            f"alert={st['alert']!r} (expected max-lot message with '1.000.000')"
        )
    await submit(page, "#lot-tambah-input")
    st = await field_state(page, "#total-lot-input")
    if not st["focused"]:
        errs.append("over-max lot: focus did not return to the invalid total-lot field")
    after = await result_html(page)
    if after is not None and after != baseline:
        errs.append("over-max lot: result card recomputed while a field was over MAX_LOT")
    if await dom_has_nan(page):
        errs.append("over-max: DOM contains NaN/Infinity after over-limit submit")
    await page.screenshot(path=str(SHOTS / "2_over_max.png"))
    return errs


async def scenario_near_max_stable(page: Page) -> list[str]:
    errs: list[str] = []
    # Return everything just under the caps and verify a clean compute.
    # All prices in band 25 (>=5000), all tick-aligned.
    await fill(page, "#avg-now-input", str(MAX_PRICE - 25))       # 999_975
    await fill(page, "#total-lot-input", str(MAX_LOT - 1))         # 999_999
    await fill(page, "#harga-avg-input", str(MAX_PRICE - 50))     # 999_950
    await fill(page, "#lot-tambah-input", "1")

    for sel in (*PRICE_FIELDS, *LOT_FIELDS):
        st = await field_state(page, sel)
        if st["ariaInvalid"] == "true" or st["alert"]:
            errs.append(f"near-max: {sel} unexpectedly invalid ({st})")

    await submit(page)
    try:
        await page.locator(RESULT_SEL).first.wait_for(state="visible", timeout=4000)
    except Exception:
        errs.append("near-max: result card missing after submit")
    await page.wait_for_timeout(300)

    text = await page.locator(RESULT_SEL).first.inner_text()
    # id-ID grouping: 3-digit groups separated by "." — must appear in the
    # very large monetary values this scenario produces (Total Capital is
    # roughly Rp 99_997_499_950).
    if not re.search(r"Rp[\s\u00a0]+\d{1,3}(?:\.\d{3}){2,}", text):
        errs.append("near-max: expected large Rp values with thousands grouping in result card")
    if "NaN" in text or "Infinity" in text:
        errs.append(f"near-max: result card text contains NaN/Infinity — {text!r}")
    if await dom_has_nan(page):
        errs.append("near-max: DOM contains NaN/Infinity anywhere")
    await page.screenshot(path=str(SHOTS / "3_near_max.png"))
    return errs


async def run(page: Page) -> list[str]:
    await settle(page)
    errors: list[str] = []
    errors += await scenario_zero_rejected(page)
    errors += await scenario_exact_max_ok(page)
    errors += await scenario_over_max_rejected(page)
    errors += await scenario_near_max_stable(page)
    return errors


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8080")
    args = parser.parse_args()

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 1800}, reduced_motion="reduce"
        )
        page = await context.new_page()
        await page.goto(args.base_url, wait_until="domcontentloaded")
        try:
            errors = await run(page)
        finally:
            await browser.close()

    print(f"\nScreenshots: {SHOTS}")
    if errors:
        print(f"\n{len(errors)} failure(s):")
        for e in errors:
            print(f"  · {e}")
        return 1
    print("\nExtreme-input scenarios pass.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
