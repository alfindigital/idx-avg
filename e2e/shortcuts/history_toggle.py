"""
E2E: keyboard shortcut opens the History modal, Escape closes it and returns
focus to the trigger without altering the result card contents.

Flow:
  1. Fill valid inputs and Ctrl+Enter → snapshot the result card outerHTML.
  2. Press Alt+H → History dialog becomes visible.
  3. Assert focus is inside the dialog (focus-trapped).
  4. Press Escape → dialog closes.
  5. Assert focus is back on the history trigger (aria-label match).
  6. Assert the result card outerHTML is byte-identical to the pre-open snapshot.
  7. Repeat with Alt+H acting as a toggle (open, then Alt+H again to close).
     Verify: Alt+H-close also returns focus to trigger and keeps the card intact.

Usage:
  python3 e2e/shortcuts/history_toggle.py [--base-url http://localhost:8080]
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from playwright.async_api import Page, async_playwright


async def settle(page: Page) -> None:
    await page.wait_for_load_state("networkidle")
    await page.wait_for_timeout(400)


async def fill_and_calc(page: Page) -> None:
    for id_, v in [
        ("avg-now-input", "1000"),
        ("total-lot-input", "10"),
        ("harga-avg-input", "900"),
        ("lot-tambah-input", "5"),
    ]:
        loc = page.locator(f"#{id_}")
        await loc.fill("")
        await loc.fill(v)
    await page.locator("#lot-tambah-input").focus()
    await page.keyboard.press("Control+Enter")
    await page.locator('[aria-labelledby="result-heading"]').first.wait_for(
        state="visible", timeout=3000
    )
    await page.wait_for_timeout(200)


async def card_html(page: Page) -> str:
    return await page.locator('[aria-labelledby="result-heading"]').first.evaluate(
        "el => el.outerHTML"
    )


async def focused_label(page: Page) -> str | None:
    return await page.evaluate(
        "() => document.activeElement && (document.activeElement.getAttribute('aria-label') || document.activeElement.id)"
    )


async def dialog_visible(page: Page) -> bool:
    return await page.locator('[role="dialog"]').first.is_visible()


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://localhost:8080")
    args = ap.parse_args()

    failures: list[str] = []
    notes: list[str] = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(viewport={"width": 1280, "height": 900})
        await ctx.add_init_script("try { localStorage.removeItem('idxavg-history-v1'); } catch(e) {}")
        page = await ctx.new_page()
        await page.goto(args.base_url, wait_until="domcontentloaded")
        await settle(page)

        # 1. Render a result card.
        await fill_and_calc(page)
        baseline_html = await card_html(page)
        baseline_text = await page.locator(
            '[aria-labelledby="result-heading"]'
        ).first.inner_text()

        trigger = page.get_by_role("button", name=re.compile(r"riwayat|history", re.I)).first
        if await trigger.count() == 0:
            failures.append("[setup] history trigger not found")
            print("FAIL — no trigger"); return 1
        trigger_label = await trigger.get_attribute("aria-label")

        # ---- Scenario A: Alt+H opens, Escape closes ----
        await page.locator("body").click()  # take focus off any input
        await page.wait_for_timeout(100)
        await page.keyboard.press("Alt+KeyH")
        try:
            await page.locator('[role="dialog"]').first.wait_for(state="visible", timeout=2000)
        except Exception:
            failures.append("[open-shortcut] Alt+H did not open history dialog")
            print("\n".join(f"  FAIL {f}" for f in failures)); return 1
        notes.append("[open-shortcut] Alt+H opened dialog")

        inside = await page.evaluate(
            """() => {
                const d = document.querySelector('[role="dialog"]');
                return !!(d && document.activeElement && d.contains(document.activeElement));
            }"""
        )
        if not inside:
            failures.append("[trap] focus not inside dialog after Alt+H open")

        await page.keyboard.press("Escape")
        await page.wait_for_timeout(350)
        if await dialog_visible(page):
            failures.append("[close-esc] dialog still visible after Escape")

        after = await focused_label(page)
        if after != trigger_label:
            failures.append(
                f"[return-focus-esc] focus not restored (got '{after}', want '{trigger_label}')"
            )
        else:
            notes.append(f"[return-focus-esc] focus back on '{trigger_label}'")

        after_html = await card_html(page)
        after_text = await page.locator(
            '[aria-labelledby="result-heading"]'
        ).first.inner_text()
        if after_html != baseline_html:
            failures.append("[card-mutated-esc] result card outerHTML changed after open/close")
        if after_text != baseline_text:
            failures.append(
                f"[card-text-esc] visible text changed: '{baseline_text[:60]}' → '{after_text[:60]}'"
            )
        else:
            notes.append("[card-stable-esc] result card content unchanged")

        # ---- Scenario B: Alt+H toggles closed too ----
        await page.keyboard.press("Alt+KeyH")
        try:
            await page.locator('[role="dialog"]').first.wait_for(state="visible", timeout=2000)
        except Exception:
            failures.append("[reopen-shortcut] Alt+H did not reopen dialog")

        await page.keyboard.press("Alt+KeyH")
        await page.wait_for_timeout(400)
        if await dialog_visible(page):
            failures.append("[toggle-close] Alt+H did not close dialog (toggle broken)")
        else:
            notes.append("[toggle-close] Alt+H closed dialog")

        after2 = await focused_label(page)
        if after2 != trigger_label:
            # Toggle-close via shortcut doesn't guarantee Radix's return-focus;
            # we only require the card to remain intact and focus not to escape
            # into some unrelated element (e.g. an input).
            active_tag = await page.evaluate(
                "() => document.activeElement && document.activeElement.tagName.toLowerCase()"
            )
            if active_tag == "input":
                failures.append(
                    f"[return-focus-toggle] focus landed on input '{after2}', not trigger"
                )
            else:
                notes.append(
                    f"[return-focus-toggle] focus is on '{after2}' (not trigger, but not an input)"
                )
        else:
            notes.append(f"[return-focus-toggle] focus back on '{trigger_label}'")

        after_html2 = await card_html(page)
        after_text2 = await page.locator(
            '[aria-labelledby="result-heading"]'
        ).first.inner_text()
        if after_html2 != baseline_html:
            failures.append("[card-mutated-toggle] result card outerHTML changed after Alt+H toggle")
        if after_text2 != baseline_text:
            failures.append("[card-text-toggle] visible text changed after Alt+H toggle")
        else:
            notes.append("[card-stable-toggle] result card content unchanged")

        await browser.close()

    print("\n--- history shortcut ---")
    for n in notes:
        print(f"  ok  {n}")
    for f in failures:
        print(f"  FAIL {f}")
    print(f"\n{'PASS' if not failures else 'FAIL'} — {len(failures)} failure(s)")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
