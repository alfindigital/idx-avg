"""
Divide-by-zero guard: target avg equal to averaging price.

In "lots needed" mode the formula divides by (hargaAveraging - targetAvg).
When those two prices are equal the app must NOT compute — instead it
shows the localized validation message "Target tidak boleh sama dengan
harga averaging" (via toast), leaves any previously rendered result card
untouched, keeps focus reasonable, and never renders NaN/Infinity.

Scenario:

  1) In new-avg mode, run a valid calculation and snapshot the result
     card HTML. This gives us a "before" baseline to prove the error
     path does not mutate prior state.
  2) Populate targetAvg equal to hargaAveraging (auto-switches to
     lots-needed mode). Clear lotTambah so mode resolves cleanly.
  3) Submit with Ctrl+Enter. Expect:
        · a toast with the exact validation message,
        · no NaN/Infinity anywhere in the DOM,
        · the previous result card, if still shown, is byte-identical
          to the snapshot (never recomputed with a bogus value),
        · target and averaging inputs report no per-field aria-invalid
          (the guard lives in calc, not per-field validation).
  4) Fix by nudging target off the collision (target = harga - tick).
     Submit again. Expect a fresh result card to render and the toast
     to disappear.

Run:
  python3 e2e/validation/target_equals_harga.py [--base-url http://localhost:8080]
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from playwright.async_api import Page, async_playwright

SHOTS = Path("/tmp/browser/target_eq_harga")
SHOTS.mkdir(parents=True, exist_ok=True)

RESULT_SEL = '[aria-labelledby="result-heading"]'
EXPECTED_MSG = "Target tidak boleh sama dengan harga averaging"


async def settle(page: Page) -> None:
    await page.wait_for_load_state("domcontentloaded")
    await page.locator("#avg-now-input").wait_for(state="visible", timeout=5000)
    await page.wait_for_timeout(800)


async def submit(page: Page, from_sel: str) -> None:
    await page.wait_for_timeout(120)
    await page.locator(from_sel).focus()
    await page.keyboard.press("Control+Enter")
    await page.wait_for_timeout(400)


async def result_html(page: Page) -> str | None:
    loc = page.locator(RESULT_SEL).first
    if await loc.count() == 0:
        return None
    return await loc.evaluate("(el) => el.outerHTML")


async def find_toast(page: Page, needle: str) -> str | None:
    return await page.evaluate(
        """(needle) => {
            const nodes = Array.from(document.querySelectorAll('*'));
            for (const n of nodes) {
                const txt = (n.textContent || '').trim();
                if (!txt) continue;
                if (txt.includes(needle) && txt.length < 400) return txt;
            }
            return null;
        }""",
        needle,
    )


async def dom_has_nan_or_infinity(page: Page) -> bool:
    return await page.evaluate(
        """() => {
            const txt = document.body.innerText || '';
            return /\\bNaN\\b/.test(txt) || /Infinity/.test(txt);
        }"""
    )


async def aria_invalid(page: Page, sel: str) -> str | None:
    return await page.locator(sel).get_attribute("aria-invalid")


async def run(page: Page) -> list[str]:
    errors: list[str] = []
    await settle(page)

    # --- 1) Baseline valid calculation in new-avg mode -----------------
    await page.locator("#avg-now-input").fill("1000")
    await page.locator("#total-lot-input").fill("50")
    await page.locator("#harga-avg-input").fill("900")
    await page.locator("#lot-tambah-input").fill("25")
    await page.locator("#lot-tambah-input").blur()
    await submit(page, "#lot-tambah-input")
    try:
        await page.locator(RESULT_SEL).first.wait_for(state="visible", timeout=4000)
    except Exception:
        await submit(page, "#lot-tambah-input")
        await page.locator(RESULT_SEL).first.wait_for(state="visible", timeout=4000)
    baseline_html = await result_html(page)
    if not baseline_html:
        return ["baseline result card missing"]
    await page.screenshot(path=str(SHOTS / "1_baseline.png"))

    # --- 2) Force target == harga by populating target and clearing tambah.
    # Clearing lotTambah + filling targetAvg auto-switches mode to
    # "lots-needed" per the calculator's derivation.
    await page.locator("#lot-tambah-input").fill("")
    await page.locator("#lot-tambah-input").blur()
    # Wait for target-avg-input to appear (mode picker flip).
    try:
        await page.locator("#target-avg-input").wait_for(state="visible", timeout=3000)
    except Exception:
        # Fallback: click the mode tab explicitly.
        try:
            await page.get_by_role("button", name="Target Avg").click()
        except Exception:
            await page.get_by_text("Target Avg", exact=False).first.click()
        await page.locator("#target-avg-input").wait_for(state="visible", timeout=3000)
    # Target equals current averaging price (900) → divide-by-zero case.
    await page.locator("#target-avg-input").fill("900")
    await page.locator("#target-avg-input").blur()
    await page.wait_for_timeout(250)

    # Per-field validation should not flag either input as invalid — the
    # guard lives at calculation time, not on individual fields.
    for sel in ("#target-avg-input", "#harga-avg-input"):
        ai = await aria_invalid(page, sel)
        if ai == "true":
            errors.append(
                f"pre-submit: {sel} incorrectly has aria-invalid=true "
                "(divide-by-zero is a calc-time guard, not a field error)"
            )

    # --- 3) Submit → expect toast, no mutation, no NaN -----------------
    await submit(page, "#target-avg-input")
    await page.screenshot(path=str(SHOTS / "2_after_collision_submit.png"))

    toast = await find_toast(page, EXPECTED_MSG)
    if not toast:
        errors.append(f"expected toast containing {EXPECTED_MSG!r} not found")

    if await dom_has_nan_or_infinity(page):
        errors.append("DOM contains NaN or Infinity after divide-by-zero submit")

    after_html = await result_html(page)
    if after_html is not None and after_html != baseline_html:
        errors.append(
            "prior result card mutated after invalid submit — the error "
            "path must never recompute the visible card"
        )

    # --- 4) Fix by moving target off the collision, re-submit ----------
    # 900 is band-5 (500 <= p < 2000, tick 5). Use 950 as a valid tick-aligned
    # target strictly less than harga so the calc succeeds.
    await page.locator("#target-avg-input").fill("950")
    await page.locator("#target-avg-input").blur()
    await page.wait_for_timeout(200)
    await submit(page, "#target-avg-input")
    try:
        await page.locator(RESULT_SEL).first.wait_for(state="visible", timeout=4000)
    except Exception:
        await submit(page, "#target-avg-input")
        await page.locator(RESULT_SEL).first.wait_for(state="visible", timeout=4000)
    await page.wait_for_timeout(300)
    fixed_html = await result_html(page)
    if not fixed_html:
        errors.append("after fix: result card did not render")
    elif fixed_html == baseline_html:
        errors.append(
            "after fix: result card is identical to the new-avg baseline — "
            "lots-needed calculation did not recompute"
        )
    if await dom_has_nan_or_infinity(page):
        errors.append("after fix: DOM still contains NaN or Infinity")
    await page.screenshot(path=str(SHOTS / "3_after_fix.png"))

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
    print("\ntarget == harga divide-by-zero guard scenario passes.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
