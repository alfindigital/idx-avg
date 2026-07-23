"""
Paste normalization for every user-facing numeric input.

Verifies that when a user pastes a "human" numeric string — with a Rupiah
prefix, spaces, thousands-separator dots or commas, a stray decimal comma,
or unicode digits — the app normalizes it to plain ASCII digits according
to the calculator's rules, and that the downstream result card renders
the correct calculation without any NaN / Infinity artifacts.

App rules (see `intOnly` / `numOnly` in src/components/calculator.tsx):
  - Lot inputs: strip everything except ASCII digits.
  - Price inputs: strip everything except ASCII digits (IDX prices are
    whole Rupiah — no fractional ticks).

Scenarios (per input):
  1.  "Rp 12500"                         → "12500"
  2.  "Rp 1.500" (id thousands dot)      → "1500"
  3.  "12,500" (en thousands comma)      → "12500"
  4.  "12 500" (space separator)         → "12500"
  5.  "1500,75" (decimal comma)          → "150075"  (comma stripped; app has no decimals)
  6.  "  2500  " (leading/trailing ws)   → "2500"
  7.  "\u0661\u0662\u0663" (arabic-indic)→ ""        (non-ASCII digits are dropped)

After the input matrix, we run one end-to-end calc-flow scenario:
  Paste "Rp 1.500" into avg price, "10" into total lot,
        "Rp 1.200" into harga averaging, "5" into lot tambah.
  Press Ctrl+Enter → the result card must render, show a numeric
  "New Average" between 1200 and 1500, and contain no NaN/Infinity.

Run:
  python3 e2e/paste_normalization/verify.py [--base-url http://localhost:8080]
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from pathlib import Path

from playwright.async_api import Page, async_playwright

SHOTS = Path("/tmp/browser/paste_normalization")
SHOTS.mkdir(parents=True, exist_ok=True)

PRICE_INPUTS = ("#avg-now-input", "#harga-avg-input", "#target-avg-input")
LOT_INPUTS = ("#total-lot-input", "#lot-tambah-input")


async def settle(page: Page) -> None:
    await page.wait_for_load_state("domcontentloaded")
    await page.locator("#avg-now-input").wait_for(state="visible", timeout=5000)
    await page.wait_for_timeout(500)


async def clear(page: Page, sel: str) -> None:
    loc = page.locator(sel)
    await loc.click()
    await loc.press("Control+A")
    await loc.press("Delete")
    await page.wait_for_timeout(40)


async def paste(page: Page, sel: str, text: str) -> None:
    """Fire a real `paste` ClipboardEvent with a DataTransfer payload,
    then fall back to a native value-setter + input event if the app
    didn't handle the paste itself (matches what a real Cmd/Ctrl+V does)."""
    await page.locator(sel).focus()
    await page.evaluate(
        """({sel, text}) => {
            const el = document.querySelector(sel);
            if (!el) throw new Error('input not found: ' + sel);
            el.focus();
            const dt = new DataTransfer();
            dt.setData('text/plain', text);
            const ev = new ClipboardEvent('paste', {
                clipboardData: dt, bubbles: true, cancelable: true,
            });
            const dispatched = el.dispatchEvent(ev);
            if (dispatched && !ev.defaultPrevented) {
                const setter = Object.getOwnPropertyDescriptor(
                    window.HTMLInputElement.prototype, 'value'
                ).set;
                setter.call(el, (el.value || '') + text);
                el.dispatchEvent(new Event('input', { bubbles: true }));
            }
        }""",
        {"sel": sel, "text": text},
    )
    await page.wait_for_timeout(120)


async def read(page: Page, sel: str) -> dict:
    return await page.evaluate(
        """(sel) => {
            const el = document.querySelector(sel);
            return {
                value: el?.value ?? null,
                ariaInvalid: el?.getAttribute('aria-invalid'),
                focused: document.activeElement === el,
            };
        }""",
        sel,
    )


# label,                          payload,              expected_value
CASES: list[tuple[str, str, str]] = [
    ("rp-prefix",                  "Rp 12500",          "12500"),
    ("rp-thousands-dot",           "Rp 1.500",          "1500"),
    ("thousands-comma",            "12,500",            "12500"),
    ("space-separator",            "12 500",            "12500"),
    ("decimal-comma",              "1500,75",           "150075"),
    ("wrapping-whitespace",        "  2500  ",          "2500"),
    ("arabic-indic-digits",        "\u0661\u0662\u0663", ""),
]


async def run_input_case(
    page: Page, sel: str, label: str, payload: str, expected: str
) -> list[str]:
    tag = f"{sel} {label!r}"
    errors: list[str] = []
    await clear(page, sel)
    await paste(page, sel, payload)
    s = await read(page, sel)

    got = s["value"] or ""
    if got != expected:
        errors.append(f"{tag}: value={got!r} != expected {expected!r}")

    # Never any non-digit char lingering in the rendered value.
    if got and not re.fullmatch(r"\d*", got):
        errors.append(f"{tag}: value has non-digit chars: {got!r}")

    if not s["focused"]:
        errors.append(f"{tag}: focus escaped the input after paste")
    return errors


async def run_endtoend(page: Page) -> list[str]:
    """Paste 'human' numbers into every field, press Ctrl+Enter, verify
    the result card renders a real number and contains no NaN/Infinity."""
    errors: list[str] = []
    # Reset the form first so any prior state doesn't contaminate the run.
    await page.keyboard.press("Alt+r")
    await page.wait_for_timeout(200)

    # Make sure we're in "new-avg" mode (the default). We don't rely on
    # localized labels; the first mode tab is the correct one on load.
    await clear(page, "#avg-now-input")
    await paste(page, "#avg-now-input",   "Rp 1.500")   # → 1500
    await clear(page, "#total-lot-input")
    await paste(page, "#total-lot-input", "10 lot")     # → 10
    await clear(page, "#harga-avg-input")
    await paste(page, "#harga-avg-input", "Rp 1.200")   # → 1200
    await clear(page, "#lot-tambah-input")
    await paste(page, "#lot-tambah-input", "5 lots")    # → 5

    # Trigger blur on the last field so tick rounding kicks in like a
    # real user tabbing / clicking away before hitting the shortcut.
    await page.keyboard.press("Tab")
    await page.wait_for_timeout(120)
    await page.keyboard.press("Control+Enter")
    await page.wait_for_timeout(500)

    # Read raw values back so we know the numbers used by the calc.
    vals = await page.evaluate(
        """() => ({
            avg:  document.querySelector('#avg-now-input')?.value ?? '',
            lot:  document.querySelector('#total-lot-input')?.value ?? '',
            hrg:  document.querySelector('#harga-avg-input')?.value ?? '',
            tmb:  document.querySelector('#lot-tambah-input')?.value ?? '',
        })"""
    )
    expected = {"avg": "1500", "lot": "10", "hrg": "1200", "tmb": "5"}
    for k, want in expected.items():
        if vals.get(k) != want:
            errors.append(f"e2e: field {k}={vals.get(k)!r} != {want!r}")

    body = (await page.locator("main").inner_text()).replace("\u00a0", " ")
    if "NaN" in body:
        errors.append("e2e: result card contains 'NaN'")
    if "Infinity" in body:
        errors.append("e2e: result card contains 'Infinity'")

    # Weighted new avg = (1500*10 + 1200*5) / 15 = 1400 → rounded to tick
    # for prices in this band (tick=1) = 1400. The rendered number uses
    # id-ID thousands separators, so match either "1.400" or "1400".
    if not re.search(r"\b1\.?400\b", body):
        errors.append(
            "e2e: expected new average '1.400' (or '1400') in result card body:\n"
            + body[:600]
        )
    return errors


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8080")
    args = parser.parse_args()

    all_errors: list[str] = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 1800},
            reduced_motion="reduce",
        )
        page = await context.new_page()
        await page.goto(args.base_url, wait_until="domcontentloaded")
        await settle(page)

        try:
            for sel in PRICE_INPUTS + LOT_INPUTS:
                for label, payload, expected in CASES:
                    errs = await run_input_case(page, sel, label, payload, expected)
                    all_errors.extend(errs)
                    stamp = f"{sel.strip('#')}_{label.replace('-', '_')}"
                    await page.screenshot(path=str(SHOTS / f"{stamp}.png"))

            e2e_errors = await run_endtoend(page)
            all_errors.extend(e2e_errors)
            await page.screenshot(path=str(SHOTS / "e2e_result_card.png"))
        finally:
            await browser.close()

    print(f"\nScreenshots: {SHOTS}")
    if all_errors:
        print(f"\n{len(all_errors)} failure(s):")
        for e in all_errors:
            print(f"  · {e}")
        return 1
    print("\nPaste normalization: all inputs sanitized and calc renders correctly.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
