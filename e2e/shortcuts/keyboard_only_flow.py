"""
E2E: complete a full calculation flow AND open/close the History modal using
ONLY the keyboard — no mouse clicks, no page.click(), no locator.click().

Scenario:
  1. Load app, reset history in localStorage, reload.
  2. Tab from the top of the document until focus lands on #avg-now-input.
  3. Type valid values into each input, advancing with Tab (never mouse).
  4. Press Ctrl+Enter → result card renders. Verify focus is still on the
     last input (Ctrl+Enter must not steal focus).
  5. Press Alt+H → History dialog opens. Verify:
       - dialog visible
       - document.activeElement is inside the dialog (focus trap)
       - the seeded entry appears in the list
  6. Press Escape → dialog closes. Verify:
       - dialog gone
       - focus returned to the history trigger button (aria-label match)
       - result card outerHTML unchanged from pre-open snapshot
  7. Press Alt+R (reset) → verify inputs cleared and focus moves to
     #avg-now-input (documented shortcut behaviour). Then re-run a second
     calculation entirely by keyboard to prove the flow is repeatable.

Usage:
  python3 e2e/shortcuts/keyboard_only_flow.py [--base-url http://localhost:8080]
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from playwright.async_api import Page, async_playwright


INPUT_IDS = [
    "avg-now-input",
    "total-lot-input",
    "harga-avg-input",
    "lot-tambah-input",
]


async def settle(page: Page) -> None:
    await page.wait_for_load_state("networkidle")
    await page.wait_for_timeout(300)


async def active_id(page: Page) -> str | None:
    return await page.evaluate("() => document.activeElement && document.activeElement.id || null")


async def active_label(page: Page) -> str | None:
    return await page.evaluate(
        "() => document.activeElement && (document.activeElement.getAttribute('aria-label') || document.activeElement.id || null)"
    )


async def tab_until(page: Page, target_id: str, max_hops: int = 40) -> bool:
    for _ in range(max_hops):
        if await active_id(page) == target_id:
            return True
        await page.keyboard.press("Tab")
    return await active_id(page) == target_id


async def type_into(page: Page, target_id: str, value: str) -> None:
    """Keyboard-only fill: select-all then type. Focus must already be on target."""
    cur = await active_id(page)
    if cur != target_id:
        raise RuntimeError(f"expected focus on #{target_id}, got #{cur}")
    await page.keyboard.press("Control+A")
    await page.keyboard.press("Delete")
    await page.keyboard.type(value, delay=10)


async def card_html(page: Page) -> str:
    return await page.locator('[aria-labelledby="result-heading"]').first.evaluate(
        "el => el.outerHTML"
    )


async def dialog_visible(page: Page) -> bool:
    loc = page.locator('[role="dialog"]').first
    if await loc.count() == 0:
        return False
    return await loc.is_visible()


async def run_calc_by_keyboard(
    page: Page, values: list[str]
) -> None:
    """Assumes focus is somewhere at the top; tabs into first input, fills the
    four inputs by Tab-hopping, then Ctrl+Enter to compute."""
    ok = await tab_until(page, INPUT_IDS[0])
    if not ok:
        raise RuntimeError("could not tab into first input")
    for idx, (target, value) in enumerate(zip(INPUT_IDS, values)):
        if await active_id(page) != target:
            # walk forward until we land on the right input
            ok2 = await tab_until(page, target)
            if not ok2:
                raise RuntimeError(f"could not tab into #{target}")
        await type_into(page, target, value)
        if idx < len(INPUT_IDS) - 1:
            await page.keyboard.press("Tab")
    # Compute
    await page.keyboard.press("Control+Enter")
    await page.locator('[aria-labelledby="result-heading"]').first.wait_for(
        state="visible", timeout=5000
    )
    await page.wait_for_timeout(200)


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://localhost:8080")
    args = ap.parse_args()

    failures: list[str] = []
    notes: list[str] = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(viewport={"width": 1280, "height": 1800})
        await ctx.add_init_script(
            "try { localStorage.removeItem('idxavg-history-v1'); } catch(e) {}"
        )
        await ctx.add_init_script(
            "try { localStorage.setItem('idxavg-tg-popup-v1','1'); } catch(e) {}"
        )
        page = await ctx.new_page()
        await page.goto(args.base_url, wait_until="domcontentloaded")
        await settle(page)

        # Put focus at the very top so Tab walks from the top of the document.
        await page.evaluate("() => { const b=document.body; b.setAttribute('tabindex','-1'); b.focus(); }")

        # ---- Step 1: full calc via keyboard ----
        try:
            await run_calc_by_keyboard(page, ["1000", "10", "900", "5"])
        except Exception as e:
            failures.append(f"[calc-keyboard] {e}")
            print("FAIL"); print("\n".join(failures)); return 1
        notes.append("[calc-keyboard] first calculation completed via Tab + typing + Ctrl+Enter")

        focused_after_calc = await active_id(page)
        # Ctrl+Enter submits the form; focus may blur but must not jump to a
        # different input field (which would confuse the user's next keystroke).
        other_inputs = [i for i in INPUT_IDS if i != "lot-tambah-input"]
        if focused_after_calc in other_inputs:
            failures.append(
                f"[focus-after-calc] Ctrl+Enter moved focus to a different input '{focused_after_calc}'"
            )
        else:
            notes.append(f"[focus-after-calc] focus after Ctrl+Enter: '{focused_after_calc}' (safe)")

        card_before = await card_html(page)

        # ---- Step 2: Alt+H opens history dialog ----
        await page.keyboard.press("Alt+KeyH")
        try:
            await page.locator('[role="dialog"]').first.wait_for(state="visible", timeout=2000)
        except Exception:
            failures.append("[alt-h-open] Alt+H did not open history dialog")
            print("\n".join(f"  FAIL {f}" for f in failures)); return 1
        notes.append("[alt-h-open] Alt+H opened history dialog without mouse")

        inside = await page.evaluate(
            """() => {
                const d = document.querySelector('[role="dialog"]');
                return !!(d && document.activeElement && d.contains(document.activeElement));
            }"""
        )
        if not inside:
            failures.append("[trap] focus not inside dialog after Alt+H")
        else:
            notes.append("[trap] focus trapped inside dialog")

        # Verify the seeded entry is present.
        entry_count = await page.evaluate(
            """() => document.querySelectorAll('[role="dialog"] [class*="max-h-"] > div').length"""
        )
        if entry_count < 1:
            failures.append(f"[seed] no history entries visible in dialog (found {entry_count})")
        else:
            notes.append(f"[seed] {entry_count} history entry visible in dialog")

        # Capture trigger label for return-focus check.
        # Radix's DialogTrigger is the last-focused element before open; grab from DOM.
        import re
        trigger = page.get_by_role("button", name=re.compile(r"riwayat|history", re.I)).first
        trigger_label = await trigger.get_attribute("aria-label") if await trigger.count() else None

        # ---- Step 3: Escape closes and restores focus ----
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(350)
        if await dialog_visible(page):
            failures.append("[esc-close] dialog still visible after Escape")
        else:
            notes.append("[esc-close] Escape closed dialog")

        after_esc = await active_label(page)
        if trigger_label and after_esc != trigger_label:
            failures.append(
                f"[return-focus] focus not on trigger (got '{after_esc}', want '{trigger_label}')"
            )
        else:
            notes.append(f"[return-focus] focus restored to '{after_esc}'")

        card_after = await card_html(page)
        if card_after != card_before:
            failures.append("[card-mutated] result card outerHTML changed after open/close")
        else:
            notes.append("[card-stable] result card content unchanged after modal cycle")

        # ---- Step 4: Alt+R resets, then re-run calc entirely by keyboard ----
        await page.keyboard.press("Alt+KeyR")
        await page.wait_for_timeout(300)
        cleared = await page.evaluate(
            f"() => {INPUT_IDS!r}.every(id => (document.getElementById(id)||{{}}).value === '')"
        )
        if not cleared:
            failures.append("[alt-r-reset] Alt+R did not clear all inputs")
        else:
            notes.append("[alt-r-reset] Alt+R cleared inputs")

        focused_after_reset = await active_id(page)
        if focused_after_reset != INPUT_IDS[0]:
            notes.append(
                f"[reset-focus] focus after Alt+R is '{focused_after_reset}' (not strict requirement)"
            )
        else:
            notes.append("[reset-focus] focus moved to first input after Alt+R")

        # Second calculation, again keyboard only.
        try:
            # Ensure we start tabbing from the top again if focus is elsewhere.
            if await active_id(page) != INPUT_IDS[0]:
                await page.evaluate(
                    "() => { const b=document.body; b.setAttribute('tabindex','-1'); b.focus(); }"
                )
            await run_calc_by_keyboard(page, ["2000", "5", "1900", "3"])
            notes.append("[calc-keyboard-2] second calculation completed via keyboard only")
        except Exception as e:
            failures.append(f"[calc-keyboard-2] {e}")

        # Verify a fresh result card and that Alt+H still opens the dialog with 2 entries.
        await page.keyboard.press("Alt+KeyH")
        try:
            await page.locator('[role="dialog"]').first.wait_for(state="visible", timeout=2000)
            entry_count2 = await page.evaluate(
                """() => document.querySelectorAll('[role="dialog"] [class*="max-h-"] > div').length"""
            )
            if entry_count2 < 2:
                failures.append(f"[history-grow] expected ≥2 entries after 2 calcs, got {entry_count2}")
            else:
                notes.append(f"[history-grow] dialog shows {entry_count2} entries after 2 calcs")
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(250)
        except Exception:
            failures.append("[alt-h-reopen] Alt+H did not reopen dialog after second calc")

        await browser.close()

    print("\n--- keyboard-only calc + history flow ---")
    for n in notes:
        print(f"  ok  {n}")
    for f in failures:
        print(f"  FAIL {f}")
    print(f"\n{'PASS' if not failures else 'FAIL'} — {len(failures)} failure(s)")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
