"""
E2E: verify keyboard shortcuts that (a) focus the first input via `/`,
(b) advance through inputs with Enter, (c) execute the calculation with
Ctrl+Enter, then (d) switch calculation mode using the keyboard (Space
on a role="tab" button) and re-run — asserting the numeric result is
correct in BOTH modes without a mouse click.

Scenarios:
  1. new-avg mode
       inputs: avgNow=1000, totalLot=10, hargaAvg=1000, lotTambah=10
       expected newAvg = 1000  → result card must show "Rp 1.000"
  2. lots-needed mode (switched via keyboard)
       inputs: avgNow=1000, totalLot=10, hargaAvg=900, targetAvg=950
       expected lotDelta = 10 lot
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from pathlib import Path
from playwright.async_api import Page, async_playwright

SCREENSHOTS = Path(__file__).parent / "screenshots_focus_mode_calc"
SCREENSHOTS.mkdir(parents=True, exist_ok=True)


async def active_id(page: Page) -> str | None:
    return await page.evaluate("() => document.activeElement?.id || null")


async def type_into(page: Page, input_id: str, value: str) -> None:
    assert await active_id(page) == input_id, f"expected focus on #{input_id}, got #{await active_id(page)}"
    await page.keyboard.type(value, delay=15)


async def press_and_settle(page: Page, key: str) -> None:
    await page.keyboard.press(key)
    await page.wait_for_timeout(120)


async def run(base_url: str) -> None:
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1280, "height": 1800})
        page = await context.new_page()

        await page.goto(base_url, wait_until="domcontentloaded")
        await page.wait_for_load_state("networkidle")
        # Ensure a clean slate.
        await page.evaluate("() => localStorage.clear()")
        await page.reload(wait_until="networkidle")
        await page.wait_for_timeout(200)

        # --- Scenario 1: new-avg via `/` + Enter chain + Ctrl+Enter ---------
        # Focus body so `/` handler (which ignores in-input keys) runs.
        await page.evaluate("() => document.body.focus()")
        await press_and_settle(page, "Slash")
        assert await active_id(page) == "avg-now-input", (
            f"`/` should focus first input, got #{await active_id(page)}"
        )

        await type_into(page, "avg-now-input", "1000")
        await press_and_settle(page, "Enter")
        await type_into(page, "total-lot-input", "10")
        await press_and_settle(page, "Enter")
        await type_into(page, "harga-avg-input", "1000")
        await press_and_settle(page, "Enter")
        await type_into(page, "lot-tambah-input", "10")

        # Ctrl+Enter → calculate.
        await press_and_settle(page, "Control+Enter")
        await page.wait_for_selector("[data-testid='result-card'], #result-card, main", timeout=3000)
        await page.wait_for_timeout(200)

        body_text = await page.locator("body").inner_text()
        # New avg = 1000; formatted id-ID as "Rp 1.000" (possibly "Rp\u00a01.000").
        norm = re.sub(r"\s+", " ", body_text)
        assert re.search(r"Rp\s?1\.000\b", norm), (
            "expected new avg 'Rp 1.000' in result card; body snippet: "
            + norm[: norm.find("Rp") + 400 if "Rp" in norm else 400]
        )
        await page.screenshot(path=str(SCREENSHOTS / "1_new_avg_result.png"))
        print("[ok] scenario 1 — new-avg mode via keyboard shortcuts → Rp 1.000")

        # --- Scenario 2: switch to lots-needed via keyboard, re-run --------
        # Reset via Alt+R (documented shortcut).
        await press_and_settle(page, "Alt+KeyR")
        # Reset clears values; verify the first input is empty.
        val = await page.locator("#avg-now-input").input_value()
        assert val == "", f"Alt+R should clear inputs, avg-now-input='{val}'"

        # Focus the second mode tab and activate with Space (keyboard only).
        tabs = page.locator('[role="tab"]')
        assert await tabs.count() == 2, "expected exactly 2 mode tabs"
        await tabs.nth(1).focus()
        await press_and_settle(page, "Space")
        selected = await tabs.nth(1).get_attribute("aria-selected")
        assert selected == "true", f"tab activation via Space failed (aria-selected={selected})"

        # selectMode() auto-focuses the mode-specific input; blur it so the
        # global `/` shortcut (which ignores in-input keys) fires.
        await page.evaluate("() => document.activeElement?.blur?.()")
        await press_and_settle(page, "Slash")
        await type_into(page, "avg-now-input", "1000")
        await press_and_settle(page, "Enter")
        await type_into(page, "total-lot-input", "10")
        await press_and_settle(page, "Enter")
        await type_into(page, "harga-avg-input", "900")
        await press_and_settle(page, "Enter")
        # In lots-needed mode the last input is #target-avg-input.
        await type_into(page, "target-avg-input", "950")

        await press_and_settle(page, "Control+Enter")
        await page.wait_for_timeout(300)

        body_text2 = await page.locator("body").inner_text()
        norm2 = re.sub(r"\s+", " ", body_text2)
        # Expected lot delta = (10 * (1000 - 950)) / (950 - 900) = 10 lot.
        assert re.search(r"\b10\s?lot\b", norm2, re.IGNORECASE), (
            "expected 10 lot in lots-needed result; snippet: " + norm2[:600]
        )
        assert "NaN" not in body_text2 and "Infinity" not in body_text2
        await page.screenshot(path=str(SCREENSHOTS / "2_lots_needed_result.png"))
        print("[ok] scenario 2 — lots-needed mode switched via Space → 10 lot")

        await browser.close()


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--base-url", default="http://localhost:8080")
    args = p.parse_args()
    try:
        asyncio.run(run(args.base_url))
    except AssertionError as e:
        print(f"[fail] {e}", file=sys.stderr)
        return 1
    print("[pass] focus + mode-switch + Ctrl+Enter keyboard shortcut flow")
    return 0


if __name__ == "__main__":
    sys.exit(main())
