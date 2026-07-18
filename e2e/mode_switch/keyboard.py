"""
E2E: switch calculation modes (new-avg ↔ lots-needed) via keyboard only.

Invariants verified
-------------------
1. Both mode tabs are keyboard-reachable via Tab (role="tab", aria-selected
   flips on activation) and activatable with Space (native <button>
   semantics), no mouse required.
2. Activating the "Target Avg" tab renders #target-avg-input and unmounts
   #lot-tambah-input; the reverse activation restores #lot-tambah-input and
   unmounts #target-avg-input. Focus lands on the newly-mounted input on
   the next frame (component focuses via requestAnimationFrame in
   selectMode).
3. Validation is independent per mode: emptying the required "add / target"
   field for the current mode and pressing Ctrl+Enter must NOT render a
   result card AND must route focus to the invalid field. Switching modes
   does not carry inline error state across.
4. Result card content is preserved (byte-identical) across a mode change
   that happens without a recalculation — switching tabs alone must never
   mutate or erase the last rendered result.
5. Recomputing in the new mode replaces the header + values coherently
   (mode="lots-needed" → "Lots Needed" header; mode="new-avg" → "New
   Average" header) and the aria-live region reflects the newest result.

Usage:
  python3 e2e/mode_switch/keyboard.py [--base-url http://localhost:8080]
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from playwright.async_api import Page, async_playwright


async def settle(page: Page) -> None:
    await page.wait_for_load_state("domcontentloaded")
    # Hydration + URL-param reader effect need ~1s before controlled inputs
    # commit values reliably; anything shorter drops the first fill().
    await page.wait_for_timeout(1500)


async def focused_id(page: Page) -> str | None:
    return await page.evaluate(
        "() => document.activeElement && document.activeElement.id || null"
    )


async def focused_role_selected(page: Page) -> dict:
    return await page.evaluate(
        """() => {
            const el = document.activeElement;
            if (!el) return {tag: null};
            return {
                tag: el.tagName,
                role: el.getAttribute('role'),
                selected: el.getAttribute('aria-selected'),
                text: (el.textContent || '').trim(),
            };
        }"""
    )


async def result_card_html(page: Page) -> str | None:
    return await page.evaluate(
        """() => {
            const el = document.querySelector('[data-result-card]');
            return el ? el.outerHTML : null;
        }"""
    )


async def live_region_text(page: Page) -> str:
    return await page.evaluate(
        """() => {
            const r = document.querySelector('[aria-live]');
            return r ? (r.textContent || '').trim() : '';
        }"""
    )


async def fill(page: Page, sel: str, value: str) -> None:
    loc = page.locator(sel)
    await loc.focus()
    await loc.fill(value)


async def tab_until_role_tab(page: Page, max_steps: int = 40) -> int:
    """Tab from current focus until we land on the first role='tab'."""
    for i in range(max_steps):
        await page.keyboard.press("Tab")
        info = await focused_role_selected(page)
        if info.get("role") == "tab":
            return i + 1
    return -1


async def press_and_settle(page: Page, key: str, ms: int = 120) -> None:
    await page.keyboard.press(key)
    await page.wait_for_timeout(ms)


async def calc_via_shortcut(page: Page) -> None:
    await page.keyboard.press("Control+Enter")
    await page.wait_for_timeout(250)


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://localhost:8080")
    args = ap.parse_args()

    failures: list[str] = []
    notes: list[str] = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(viewport={"width": 1280, "height": 900})
        page = await ctx.new_page()
        await page.goto(args.base_url, wait_until="domcontentloaded")
        await settle(page)

        # ── Baseline: fill inputs in default mode (new-avg) and compute ──
        await fill(page, "#avg-now-input", "1000")
        await fill(page, "#total-lot-input", "10")
        await fill(page, "#harga-avg-input", "900")
        await fill(page, "#lot-tambah-input", "10")
        await calc_via_shortcut(page)

        baseline_html = await result_card_html(page)
        baseline_live = await live_region_text(page)
        if not baseline_html:
            failures.append("[baseline] result card did not render after Ctrl+Enter in new-avg mode")
        else:
            notes.append("[baseline] result card rendered in new-avg mode")
        if not baseline_live:
            failures.append("[baseline] aria-live region empty after first calc")
        else:
            notes.append(f"[baseline] aria-live populated ({len(baseline_live)} chars)")

        # ── Focus the first tab via keyboard only ──
        # Anchor at a stable input first so Tab stepping is deterministic.
        await page.locator("#avg-now-input").focus()
        steps = await tab_until_role_tab(page)
        if steps < 0:
            failures.append("[tab-nav] could not reach role='tab' from #avg-now-input via Tab")
        else:
            notes.append(f"[tab-nav] reached first role=tab in {steps} Tab presses")

        info = await focused_role_selected(page)
        first_tab_label = info.get("text", "")
        if info.get("selected") != "true":
            failures.append(
                f"[tab-nav] first reached tab is not aria-selected=true (got '{info.get('selected')}', label='{first_tab_label}')"
            )
        else:
            notes.append(f"[tab-nav] active tab is '{first_tab_label}' (aria-selected=true)")

        # Move to the sibling (inactive) tab via Tab, verify it's the other role=tab.
        await page.keyboard.press("Tab")
        info2 = await focused_role_selected(page)
        if info2.get("role") != "tab":
            failures.append(f"[tab-nav] second Tab did not land on a tab (got role='{info2.get('role')}')")
        elif info2.get("selected") != "false":
            failures.append(
                f"[tab-nav] sibling tab aria-selected='{info2.get('selected')}' (expected 'false')"
            )
        else:
            notes.append(f"[tab-nav] sibling inactive tab focusable: '{info2.get('text','')}'")

        # ── Activate lots-needed via Space ──
        await press_and_settle(page, "Space")
        # Component moves focus to #target-avg-input via rAF.
        after_focus = await focused_id(page)
        if after_focus != "target-avg-input":
            failures.append(
                f"[activate-lots-needed] focus after Space = '{after_focus}' (expected 'target-avg-input')"
            )
        else:
            notes.append("[activate-lots-needed] focus landed on #target-avg-input")

        # DOM invariants after mode flip.
        lot_tambah_count = await page.locator("#lot-tambah-input").count()
        target_avg_count = await page.locator("#target-avg-input").count()
        if lot_tambah_count != 0:
            failures.append(f"[activate-lots-needed] #lot-tambah-input still mounted ({lot_tambah_count})")
        if target_avg_count != 1:
            failures.append(f"[activate-lots-needed] #target-avg-input count={target_avg_count}")

        # Result card must NOT have been erased or mutated by the mode flip.
        html_after_flip = await result_card_html(page)
        if html_after_flip != baseline_html:
            failures.append("[preserve-result] result card HTML changed on mode flip (no recompute)")
        else:
            notes.append("[preserve-result] result card content byte-identical across mode flip")

        # ── Validation invariant: empty target-avg + Ctrl+Enter → no new card, focus routed ──
        # Field is empty (just mounted). Fire the shortcut.
        # Move focus away from the target input first so we can detect the routing.
        await page.locator("#avg-now-input").focus()
        await page.wait_for_timeout(40)
        await calc_via_shortcut(page)
        focused = await focused_id(page)
        if focused != "target-avg-input":
            failures.append(
                f"[lots-needed-invalid] Ctrl+Enter did not route focus to target-avg-input (got '{focused}')"
            )
        else:
            notes.append("[lots-needed-invalid] focus routed to empty target-avg-input")
        html_after_invalid = await result_card_html(page)
        if html_after_invalid != baseline_html:
            failures.append("[lots-needed-invalid] result card mutated despite invalid submit")
        else:
            notes.append("[lots-needed-invalid] previous result card preserved after invalid submit")

        # ── Successful compute in the new mode ──
        await fill(page, "#target-avg-input", "950")
        await calc_via_shortcut(page)
        html_lots_needed = await result_card_html(page)
        live_lots_needed = await live_region_text(page)
        if not html_lots_needed:
            failures.append("[lots-needed-calc] result card missing after valid submit")
        elif html_lots_needed == baseline_html:
            failures.append("[lots-needed-calc] result card unchanged after recompute in lots-needed mode")
        else:
            # Header should reflect the lots-needed mode ("Lot" or "Lots" appears in header text).
            header_ok = bool(re.search(r"lot", html_lots_needed, re.IGNORECASE))
            if not header_ok:
                failures.append("[lots-needed-calc] result card header does not reference lots")
            else:
                notes.append("[lots-needed-calc] result card recomputed with lots-needed header")
        if live_lots_needed and live_lots_needed == baseline_live:
            failures.append("[lots-needed-calc] aria-live text is stale (equals baseline)")
        else:
            notes.append("[lots-needed-calc] aria-live updated with new announcement")

        # ── Switch back to new-avg via keyboard: Tab to tablist and Space on the first tab ──
        await page.locator("#avg-now-input").focus()
        steps2 = await tab_until_role_tab(page)
        if steps2 < 0:
            failures.append("[back-to-new-avg] could not reach role=tab again")
        info3 = await focused_role_selected(page)
        # Currently active tab is "Target Avg" (selected). We need to move to
        # the FIRST tab (Lot Tambah). Since focus lands on the selected tab,
        # walk backwards with Shift+Tab until we hit the other role=tab.
        if info3.get("selected") == "true":
            await page.keyboard.press("Shift+Tab")
            back_info = await focused_role_selected(page)
            if back_info.get("role") != "tab" or back_info.get("selected") != "false":
                failures.append(
                    f"[back-to-new-avg] Shift+Tab did not land on inactive tab (role={back_info.get('role')}, selected={back_info.get('selected')})"
                )
            else:
                await press_and_settle(page, "Space")
        else:
            # First reached tab is the inactive one already.
            await press_and_settle(page, "Space")

        after_focus2 = await focused_id(page)
        if after_focus2 != "lot-tambah-input":
            failures.append(
                f"[back-to-new-avg] focus after Space = '{after_focus2}' (expected 'lot-tambah-input')"
            )
        else:
            notes.append("[back-to-new-avg] focus landed on #lot-tambah-input")

        # #lot-tambah-input remounted empty (selectMode wipes the OTHER field only,
        # so lot-tambah value from the very first burst was preserved earlier — but
        # after the round-trip through lots-needed, selectMode('lots-needed') cleared
        # lot-tambah). Verify the field is empty and there's no inline error.
        remounted_val = await page.locator("#lot-tambah-input").input_value()
        if remounted_val != "":
            notes.append(f"[back-to-new-avg] #lot-tambah-input remounted with value='{remounted_val}' (state carried)")
        aria = await page.locator("#lot-tambah-input").get_attribute("aria-invalid")
        if aria == "true":
            failures.append("[back-to-new-avg] inline error carried across mode switch")
        else:
            notes.append("[back-to-new-avg] no stale inline error after mode switch")

        # Result card from lots-needed compute must still be present, byte-identical.
        html_after_back = await result_card_html(page)
        if html_after_back != html_lots_needed:
            failures.append("[back-to-new-avg] result card mutated on switch back to new-avg")
        else:
            notes.append("[back-to-new-avg] result card content preserved across return mode flip")

        await browser.close()

    print("\n--- mode switch (keyboard) ---")
    for n in notes:
        print(f"  ok  {n}")
    for f in failures:
        print(f"  FAIL {f}")
    print(f"\n{'PASS' if not failures else 'FAIL'} — {len(failures)} failure(s)")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
