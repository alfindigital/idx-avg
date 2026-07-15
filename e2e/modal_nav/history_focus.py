"""
E2E: navigate the History modal with Tab / Shift+Tab across the list of
history entries and verify:

  1. Seed ≥ 3 history entries (via computing valid results with Ctrl+Enter).
  2. Open the History modal; capture the trigger element for return-focus check.
  3. Tab through the entire dialog collecting focus-order snapshots.
     - Every focused element MUST stay inside the dialog (focus trap).
     - All rendered history-list <button>s MUST appear in the forward tab
       order (no entry is skipped or unreachable by keyboard).
     - Order must be a stable forward walk (indexes non-decreasing).
  4. Shift+Tab from the last focused element MUST reverse the exact chain.
  5. Close via Escape → focus returns to the trigger button.
  6. Close via close-button click → focus also returns to trigger.

Usage:
  python3 e2e/modal_nav/history_focus.py [--base-url http://localhost:8080]
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from playwright.async_api import Page, async_playwright


async def settle(page: Page) -> None:
    await page.wait_for_load_state("networkidle")
    await page.wait_for_timeout(500)


async def seed_history(page: Page, entries: list[tuple[str, str, str, str]]) -> None:
    """Fill form and submit N times to populate the history list."""
    for avg, lot, harga, tambah in entries:
        for id_, val in [
            ("avg-now-input", avg),
            ("total-lot-input", lot),
            ("harga-avg-input", harga),
            ("lot-tambah-input", tambah),
        ]:
            loc = page.locator(f"#{id_}")
            await loc.fill("")
            await loc.fill(val)
        await page.locator("#lot-tambah-input").focus()
        await page.keyboard.press("Control+Enter")
        await page.locator('[aria-labelledby="result-heading"]').first.wait_for(
            state="visible", timeout=3000
        )
        await page.wait_for_timeout(150)


async def focused_desc(page: Page) -> dict:
    return await page.evaluate(
        """() => {
            const ae = document.activeElement;
            if (!ae) return null;
            const dlg = document.querySelector('[role="dialog"]');
            return {
                tag: ae.tagName.toLowerCase(),
                id: ae.id || null,
                label: ae.getAttribute('aria-label') || null,
                text: (ae.textContent || '').replace(/\\s+/g,' ').trim().slice(0, 60),
                inDialog: !!(dlg && dlg.contains(ae)),
                // For history-list buttons: index in the list (or -1).
                listIdx: (() => {
                    const buttons = Array.from(document.querySelectorAll(
                        '[role="dialog"] .max-h-\\\\[60vh\\\\] > button, [role="dialog"] [class*="max-h-"] > button'
                    ));
                    return buttons.indexOf(ae);
                })(),
            };
        }"""
    )


async def list_button_count(page: Page) -> int:
    return await page.evaluate(
        """() => document.querySelectorAll('[role="dialog"] [class*="max-h-"] > button').length"""
    )


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://localhost:8080")
    args = ap.parse_args()

    failures: list[str] = []
    notes: list[str] = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(viewport={"width": 390, "height": 900})
        page = await ctx.new_page()
        # Clean localStorage so we start with an empty history.
        await page.goto(args.base_url, wait_until="domcontentloaded")
        await page.evaluate("() => localStorage.removeItem('idxavg-history-v1')")
        await page.reload(wait_until="domcontentloaded")
        await settle(page)

        # -------- Seed 3 distinct entries --------
        await seed_history(page, [
            ("1000", "10", "900", "5"),
            ("1500", "8",  "1400", "4"),
            ("2000", "5",  "1900", "3"),
        ])

        import re
        trigger = page.get_by_role("button", name=re.compile(r"riwayat|history", re.I)).first
        if await trigger.count() == 0:
            failures.append("[open] history trigger not found")
            print("FAIL"); return 1
        trigger_label = await trigger.get_attribute("aria-label")

        # -------- Open modal --------
        await trigger.click()
        dialog = page.locator('[role="dialog"]').first
        await dialog.wait_for(state="visible", timeout=2000)
        await page.wait_for_timeout(300)

        list_count = await list_button_count(page)
        if list_count < 3:
            failures.append(f"[seed] expected ≥3 history entries, got {list_count}")

        # -------- Forward Tab walk --------
        forward: list[dict] = []
        seen_ids: set[str] = set()
        for _ in range(30):
            await page.keyboard.press("Tab")
            f = await focused_desc(page)
            if not f:
                break
            forward.append(f)
            if not f["inDialog"]:
                failures.append(f"[trap] focus escaped dialog on Tab: {f}")
                break
            key = f"{f['tag']}#{f['id']}|{f['label']}|{f['text']}|{f['listIdx']}"
            if key in seen_ids:
                # Reached the wrap-around → focus trap is cycling. Stop.
                break
            seen_ids.add(key)

        # Every history-list button MUST be reachable.
        list_indices_seen = [f["listIdx"] for f in forward if f["listIdx"] >= 0]
        if sorted(list_indices_seen) != list(range(list_count)):
            failures.append(
                f"[reach] not all history buttons reachable via Tab. "
                f"seen={sorted(list_indices_seen)} expected={list(range(list_count))}"
            )
        # And they must appear in ascending order (natural DOM order).
        if list_indices_seen != sorted(list_indices_seen):
            failures.append(
                f"[order] history buttons focused out of order: {list_indices_seen}"
            )
        notes.append(f"[forward] {len(forward)} stops, list buttons focused in order: {list_indices_seen}")

        # -------- Reverse Shift+Tab walk --------
        # From the current focus, Shift+Tab should reverse through the list buttons.
        reverse_list_idx: list[int] = []
        for _ in range(30):
            await page.keyboard.press("Shift+Tab")
            f = await focused_desc(page)
            if not f:
                break
            if not f["inDialog"]:
                failures.append(f"[trap-rev] focus escaped dialog on Shift+Tab: {f}")
                break
            if f["listIdx"] >= 0:
                reverse_list_idx.append(f["listIdx"])
            # Stop after we've seen all list buttons in reverse.
            if len(reverse_list_idx) >= list_count:
                break

        if sorted(reverse_list_idx) != list(range(list_count)):
            failures.append(
                f"[reach-rev] not all history buttons reachable via Shift+Tab. seen={reverse_list_idx}"
            )
        elif reverse_list_idx != sorted(reverse_list_idx, reverse=True):
            failures.append(f"[order-rev] Shift+Tab order not descending: {reverse_list_idx}")
        else:
            notes.append(f"[reverse] Shift+Tab descending: {reverse_list_idx}")

        # -------- Close via Escape → focus returns to trigger --------
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(300)
        if await dialog.is_visible():
            failures.append("[close-esc] dialog still visible after Escape")
        after_esc = await page.evaluate(
            "() => document.activeElement && (document.activeElement.getAttribute('aria-label') || document.activeElement.id)"
        )
        if after_esc != trigger_label:
            failures.append(f"[close-esc] focus did not return to trigger (got '{after_esc}', expected '{trigger_label}')")
        else:
            notes.append(f"[close-esc] focus returned to '{trigger_label}'")

        # -------- Close via close-button click → focus returns to trigger --------
        await trigger.click()
        await dialog.wait_for(state="visible", timeout=2000)
        await page.wait_for_timeout(200)
        close_btn = dialog.get_by_role("button", name=re.compile(r"close|tutup", re.I)).first
        if await close_btn.count() == 0:
            # Radix ships a default close button with sr-only "Close" label.
            close_btn = dialog.locator("button").last
        await close_btn.click()
        await page.wait_for_timeout(300)
        if await dialog.is_visible():
            failures.append("[close-btn] dialog still visible after close click")
        after_btn = await page.evaluate(
            "() => document.activeElement && (document.activeElement.getAttribute('aria-label') || document.activeElement.id)"
        )
        if after_btn != trigger_label:
            failures.append(f"[close-btn] focus did not return to trigger (got '{after_btn}', expected '{trigger_label}')")
        else:
            notes.append(f"[close-btn] focus returned to '{trigger_label}'")

        await browser.close()

    print("\n--- history modal Tab navigation ---")
    for n in notes:
        print(f"  ok  {n}")
    for f in failures:
        print(f"  FAIL {f}")
    print(f"\n{'PASS' if not failures else 'FAIL'} — {len(failures)} failure(s)")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
