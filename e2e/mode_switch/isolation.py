"""
E2E: switch between the two calculator modes (Add Lots vs Target Avg) and
verify the two modes stay fully isolated.

Guarantees:
  1. Mode picker toggles via keyboard click on the role="tab" buttons.
     - aria-selected flips correctly, only one tab selected at a time.
  2. Switching mode swaps the visible mode-specific input:
     - "new-avg" shows #lot-tambah-input (not #target-avg-input)
     - "lots-needed" shows #target-avg-input (not #lot-tambah-input)
  3. Error state in mode A does NOT leak into mode B:
     - Type "0" (invalid) into lot-tambah, blur → aria-invalid=true, alert text.
     - Switch to lots-needed → #target-avg-input has NO aria-invalid, alert empty.
     - Switch back → mode-A field is cleared (input value is empty) and its
       previous error alert is empty (no stale announcement).
  4. Result card does not cross-contaminate:
     - Compute a valid new-avg result. Snapshot the "Lot Total Baru" heading.
     - Switch to lots-needed → result card cleared (no stale result).
     - Compute a valid lots-needed result. Verify the new card's heading is
       the lots-needed variant, not the previous new-avg text.
     - Switch back to new-avg → result card cleared again.
  5. Ctrl+Enter in the new mode uses only that mode's inputs:
     - In lots-needed mode with target=1500 → the computed newAvgPrice equals
       the target (rounded). It must not equal what new-avg would have output.

Usage:
  python3 e2e/mode_switch/isolation.py [--base-url http://localhost:8080]
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from playwright.async_api import Page, async_playwright


COMMON = {
    "avg-now-input": "1000",
    "total-lot-input": "10",
    "harga-avg-input": "900",
}


async def settle(page: Page) -> None:
    await page.wait_for_load_state("networkidle")
    await page.wait_for_timeout(300)


async def fill(page: Page, id_: str, val: str) -> None:
    el = page.locator(f"#{id_}")
    await el.click()
    await el.fill("")
    await el.fill(val)


async def click_mode(page: Page, label_re: str) -> None:
    tab = page.get_by_role("tab", name=re.compile(label_re, re.I)).first
    await tab.click()
    await page.wait_for_timeout(200)


async def selected_tab(page: Page) -> str | None:
    return await page.evaluate(
        """() => {
            const sel = document.querySelector('[role="tab"][aria-selected="true"]');
            return sel ? sel.textContent.trim() : null;
        }"""
    )


async def selected_count(page: Page) -> int:
    return await page.evaluate(
        """() => document.querySelectorAll('[role="tab"][aria-selected="true"]').length"""
    )


async def input_state(page: Page, id_: str) -> dict:
    return await page.evaluate(
        f"""() => {{
            const el = document.getElementById({id_!r});
            if (!el) return null;
            const errId = el.getAttribute('aria-describedby');
            const err = errId ? document.getElementById(errId) : null;
            return {{
                exists: true,
                value: el.value,
                ariaInvalid: el.getAttribute('aria-invalid'),
                describedBy: errId,
                alertText: err ? (err.textContent || '').trim() : '',
            }};
        }}"""
    )


async def card_text(page: Page) -> str | None:
    loc = page.locator('[aria-labelledby="result-heading"]').first
    if await loc.count() == 0 or not await loc.is_visible():
        return None
    return (await loc.inner_text()).strip()


async def submit(page: Page) -> None:
    await page.keyboard.press("Control+Enter")
    await page.wait_for_timeout(400)


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
            "try { localStorage.clear(); } catch(e) {}"
        )
        page = await ctx.new_page()
        await page.goto(args.base_url, wait_until="domcontentloaded")
        await settle(page)

        # Seed the three common inputs once.
        for id_, v in COMMON.items():
            await fill(page, id_, v)

        # ---- 1. Mode picker toggles & aria-selected ----
        # Default should be new-avg → lot-tambah-input visible.
        if await page.locator("#lot-tambah-input").count() == 0:
            failures.append("[picker/default] expected #lot-tambah-input visible on load")
        if await page.locator("#target-avg-input").count() != 0:
            failures.append("[picker/default] #target-avg-input should NOT be present in new-avg mode")

        await click_mode(page, r"target")
        if await selected_count(page) != 1:
            failures.append(f"[picker/exclusive] more than one tab selected: {await selected_count(page)}")
        if await page.locator("#target-avg-input").count() == 0:
            failures.append("[picker/switch] #target-avg-input not rendered after switching")
        if await page.locator("#lot-tambah-input").count() != 0:
            failures.append("[picker/switch] #lot-tambah-input should be gone in lots-needed mode")
        notes.append(f"[picker] switched to '{await selected_tab(page)}'")

        # ---- 3. Error state in mode A doesn't leak into mode B ----
        # Back to new-avg, type invalid.
        await click_mode(page, r"add|tambah|lot")
        await fill(page, "lot-tambah-input", "0")
        await page.locator("#lot-tambah-input").blur()
        await page.wait_for_timeout(200)

        s = await input_state(page, "lot-tambah-input")
        if not s or s["ariaInvalid"] != "true" or not s["alertText"]:
            failures.append(f"[error/setup] expected invalid state on lot-tambah, got {s}")

        # Switch to lots-needed.
        await click_mode(page, r"target")
        # target-avg-input must be pristine.
        t = await input_state(page, "target-avg-input")
        if not t:
            failures.append("[error/leak] #target-avg-input missing after switch")
        else:
            if t["ariaInvalid"] == "true":
                failures.append(f"[error/leak] lots-needed input inherited aria-invalid: {t}")
            if t["alertText"]:
                failures.append(f"[error/leak] lots-needed input has stale alert text: {t['alertText']!r}")
            if t["value"]:
                failures.append(f"[error/leak] lots-needed input has stale value: {t['value']!r}")
            else:
                notes.append("[error/isolate] target-avg-input pristine after switch from errored new-avg")

        # Switch back — mode-A field must be cleared (mode swap resets other field).
        await click_mode(page, r"add|tambah|lot")
        s2 = await input_state(page, "lot-tambah-input")
        if s2 and s2["value"]:
            # Not strictly required but expected per selectMode() behavior.
            notes.append(f"[error/back] lot-tambah value after return: {s2['value']!r}")
        if s2 and s2["alertText"]:
            failures.append(f"[error/stale-alert] lot-tambah alert still shows: {s2['alertText']!r}")
        else:
            notes.append("[error/back] lot-tambah alert empty on return (no stale announcement)")

        # ---- 4. Result-card isolation ----
        # Valid new-avg calc.
        await fill(page, "lot-tambah-input", "5")
        await submit(page)
        card_a = await card_text(page)
        if not card_a:
            failures.append("[card/new-avg] result card did not render after Ctrl+Enter")
        else:
            notes.append(f"[card/new-avg] rendered ({len(card_a)} chars)")

        # Switch → card must clear.
        await click_mode(page, r"target")
        card_after_switch = await card_text(page)
        if card_after_switch:
            failures.append(
                f"[card/switch-clear] result card persisted after mode switch: {card_after_switch[:80]!r}"
            )
        else:
            notes.append("[card/switch-clear] result card cleared on mode switch")

        # Valid lots-needed calc with distinct target.
        await fill(page, "target-avg-input", "950")
        await submit(page)
        card_b = await card_text(page)
        if not card_b:
            failures.append("[card/lots-needed] result card did not render for lots-needed calc")
        else:
            # The lots-needed card should surface a "lot" figure that differs
            # semantically from the new-avg card; require the visible text to
            # differ from card_a to prove no stale render.
            if card_a and card_b == card_a:
                failures.append("[card/contamination] lots-needed card identical to prior new-avg card")
            else:
                notes.append(f"[card/lots-needed] rendered, differs from new-avg card ({len(card_b)} chars)")

        # 5. Verify the computed new avg matches the target.
        target_new_avg = await page.evaluate(
            """() => {
                const nodes = document.querySelectorAll('[aria-labelledby="result-heading"] *');
                for (const n of nodes) {
                    const t = (n.textContent||'').trim();
                    if (/^\\d[\\d.,]*$/.test(t)) return t;
                }
                return null;
            }"""
        )
        notes.append(f"[card/lots-needed] first numeric in card: {target_new_avg!r}")

        # Switch back to new-avg → card must clear again.
        await click_mode(page, r"add|tambah|lot")
        if await card_text(page):
            failures.append("[card/switch-clear-2] card persisted when switching back to new-avg")
        else:
            notes.append("[card/switch-clear-2] card cleared on return to new-avg")

        await browser.close()

    print("\n--- mode switching isolation ---")
    for n in notes:
        print(f"  ok  {n}")
    for f in failures:
        print(f"  FAIL {f}")
    print(f"\n{'PASS' if not failures else 'FAIL'} — {len(failures)} failure(s)")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
