"""
MAX_LOT boundary behavior for the lot input.

Scenario: type an initial valid calculation to render a result card, capture
its HTML, then exercise the "total lot" input across the MAX_LOT boundary:

  1) Type exactly MAX_LOT (1_000_000). Field is valid, no inline error,
     aria-invalid is not "true", rendered value shows the formatted number,
     and the previously computed result card is unchanged (byte-identical
     HTML) because typing does not trigger recompute.
  2) Type one more digit → value now exceeds MAX_LOT. Inline
     role="alert" appears, aria-invalid="true", focus stays on the input,
     and the result card is STILL unchanged (we never recomputed).
  3) Press Backspace to return to exactly MAX_LOT. Error disappears,
     aria-invalid clears, focus stays put, result card still unchanged.
  4) Submit (Ctrl+Enter). Result recomputes with the MAX_LOT value; the
     new result card HTML must differ from the pre-boundary snapshot
     (because total lot changed from 10 → 1_000_000), and no error is
     shown. This proves the over-max state never leaked into a stale
     calculation.

Run:
  python3 e2e/lot_input/max_boundary.py [--base-url http://localhost:8080]
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from pathlib import Path

from playwright.async_api import Page, async_playwright

SHOTS = Path("/tmp/browser/lot_max_boundary")
SHOTS.mkdir(parents=True, exist_ok=True)

MAX_LOT = 1_000_000
LOT_SEL = "#total-lot-input"
RESULT_SEL = '[aria-labelledby="result-heading"]'


async def settle(page: Page) -> None:
    await page.wait_for_load_state("domcontentloaded")
    # Wait for hydration — inputs must be interactive before .fill() sticks.
    await page.locator("#avg-now-input").wait_for(state="visible", timeout=5000)
    await page.wait_for_timeout(1000)


async def submit(page: Page) -> None:
    await page.wait_for_timeout(200)
    await page.locator("#lot-tambah-input").focus()
    await page.keyboard.press("Control+Enter")


async def initial_calc(page: Page) -> None:
    await page.locator("#avg-now-input").fill("1000")
    await page.locator(LOT_SEL).fill("10")
    await page.locator("#harga-avg-input").fill("900")
    await page.locator("#lot-tambah-input").fill("5")
    await page.locator("#lot-tambah-input").blur()
    await submit(page)
    try:
        await page.locator(RESULT_SEL).first.wait_for(state="visible", timeout=5000)
    except Exception:
        await page.screenshot(path=str(SHOTS / "0_initial_fail.png"))
        await page.wait_for_timeout(500)
        await submit(page)
        await page.locator(RESULT_SEL).first.wait_for(state="visible", timeout=5000)
    await page.wait_for_timeout(300)


async def input_state(page: Page) -> dict:
    return await page.evaluate(
        """(sel) => {
            const el = document.querySelector(sel);
            const focused = document.activeElement === el;
            let alert = null;
            const desc = el?.getAttribute('aria-describedby');
            if (desc) {
                for (const id of desc.split(/\\s+/)) {
                    const n = document.getElementById(id);
                    if (n && n.getAttribute('role') === 'alert' && n.textContent.trim()) {
                        alert = n.textContent.trim();
                        break;
                    }
                }
            }
            if (!alert) {
                // Fallback: nearest sibling alert.
                const near = el?.closest('div')?.querySelector('[role="alert"]');
                if (near && near.textContent.trim()) alert = near.textContent.trim();
            }
            return {
                value: el?.value ?? null,
                ariaInvalid: el?.getAttribute('aria-invalid'),
                focused,
                alert,
            };
        }""",
        LOT_SEL,
    )


async def result_html(page: Page) -> str | None:
    loc = page.locator(RESULT_SEL).first
    if await loc.count() == 0:
        return None
    return await loc.evaluate("(el) => el.outerHTML")


def digits_only(s: str | None) -> str:
    return re.sub(r"\D", "", s or "")


async def run(page: Page) -> list[str]:
    errors: list[str] = []
    await settle(page)
    await initial_calc(page)
    baseline_html = await result_html(page)
    if not baseline_html:
        return ["initial result card missing"]
    await page.screenshot(path=str(SHOTS / "1_initial.png"))

    lot = page.locator(LOT_SEL)
    await lot.click()
    await lot.press("Control+A")
    await lot.press("Delete")
    await page.wait_for_timeout(80)

    # --- 1) Type exactly MAX_LOT digit-by-digit --------------------------
    for ch in str(MAX_LOT):
        await page.keyboard.type(ch, delay=15)
    await page.wait_for_timeout(200)
    s = await input_state(page)
    if digits_only(s["value"]) != str(MAX_LOT):
        errors.append(f"@ MAX_LOT: value digits={digits_only(s['value'])!r} expected {MAX_LOT}")
    if s["ariaInvalid"] == "true":
        errors.append("@ MAX_LOT: aria-invalid=true (should be valid)")
    if s["alert"]:
        errors.append(f"@ MAX_LOT: unexpected inline error: {s['alert']!r}")
    if not s["focused"]:
        errors.append("@ MAX_LOT: focus left the input")
    # Snapshot the current (valid) result card at MAX_LOT. This is the
    # canonical "valid state" — over-max must not mutate it, and returning
    # to MAX_LOT must restore it byte-for-byte.
    at_max_html = await result_html(page)
    if at_max_html is None:
        errors.append("@ MAX_LOT: result card missing")
    await page.screenshot(path=str(SHOTS / "2_at_max.png"))

    # --- 2) One extra digit → over MAX_LOT -------------------------------
    await page.keyboard.type("0", delay=15)
    await page.wait_for_timeout(200)
    s = await input_state(page)
    typed_digits = digits_only(s["value"])
    if int(typed_digits or "0") <= MAX_LOT:
        errors.append(f"> MAX_LOT: value {typed_digits!r} did not exceed MAX_LOT")
    if s["ariaInvalid"] != "true":
        errors.append(f"> MAX_LOT: aria-invalid={s['ariaInvalid']!r} (want 'true')")
    if not s["alert"]:
        errors.append("> MAX_LOT: expected inline role=alert error text")
    if not s["focused"]:
        errors.append("> MAX_LOT: focus left the input during validation")
    over_html = await result_html(page)
    if over_html != at_max_html:
        errors.append(
            "> MAX_LOT: result card recomputed with an invalid over-max value "
            "(should keep the last valid state)"
        )
    await page.screenshot(path=str(SHOTS / "3_over_max.png"))

    # --- 3) Backspace back to exactly MAX_LOT ----------------------------
    await page.keyboard.press("Backspace")
    await page.wait_for_timeout(250)
    s = await input_state(page)
    if digits_only(s["value"]) != str(MAX_LOT):
        errors.append(
            f"back @ MAX_LOT: value digits={digits_only(s['value'])!r} expected {MAX_LOT}"
        )
    if s["ariaInvalid"] == "true":
        errors.append("back @ MAX_LOT: aria-invalid still true after returning to valid range")
    if s["alert"]:
        errors.append(f"back @ MAX_LOT: inline error still shown: {s['alert']!r}")
    if not s["focused"]:
        errors.append("back @ MAX_LOT: focus escaped during backspace")
    back_html = await result_html(page)
    if back_html != at_max_html:
        errors.append(
            "back @ MAX_LOT: result card did not restore to the exact state seen at MAX_LOT"
        )
    await page.screenshot(path=str(SHOTS / "4_back_at_max.png"))

    # --- 4) Explicit submit at MAX_LOT — still valid, no error ----------
    await submit(page)
    await page.wait_for_timeout(400)
    final_html = await result_html(page)
    if final_html is None:
        errors.append("recompute: result card missing after submit at MAX_LOT")
    s = await input_state(page)
    if s["ariaInvalid"] == "true" or s["alert"]:
        errors.append(f"recompute: error surfaced on valid submit ({s})")
    await page.screenshot(path=str(SHOTS / "5_after_recompute.png"))

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
    print("\nMAX_LOT boundary scenario passes.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
