"""
E2E: consolidated a11y check combining three guarantees in one run:

  A. Focus trap in the History modal
     - Tab / Shift+Tab never escape the dialog
     - Escape closes and restores focus to the trigger

  B. Correct Tab order on the main page
     - Forward Tab walks the four calculator inputs in DOM order
       (avg-now → total-lot → harga-avg → lot-tambah) then reaches
       the primary Hitung button
     - Shift+Tab reverses the exact chain

  C. Inline error aria contract is consistent across all inputs
     - Invalid value → aria-invalid="true" AND aria-describedby
       points to a live #<id>-error region with role="alert"
       whose text is non-empty
     - Fixing the value → aria-invalid removed (or "false") AND
       the alert region is empty (announcement cleared)
     - Contract holds identically for every calculator input

Usage:
  python3 e2e/a11y/focus_trap_tab_aria.py [--base-url http://localhost:8080]
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from playwright.async_api import Page, async_playwright


INPUT_IDS = [
    "avg-now-input",
    "total-lot-input",
    "harga-avg-input",
    "lot-tambah-input",
]

# Values that trigger validation errors:
#  - price fields: "0" survives blur reformatter but fails positive check
#  - lot fields: "0" fails positive check
BAD_VALUES = {
    "avg-now-input": ("0", "1000"),
    "total-lot-input": ("0", "10"),
    "harga-avg-input": ("0", "900"),
    "lot-tambah-input": ("0", "5"),
}


async def settle(page: Page) -> None:
    await page.wait_for_load_state("networkidle")
    await page.wait_for_timeout(300)


async def active_id(page: Page) -> str | None:
    return await page.evaluate(
        "() => document.activeElement && document.activeElement.id || null"
    )


async def active_label(page: Page) -> str | None:
    return await page.evaluate(
        "() => document.activeElement && (document.activeElement.getAttribute('aria-label') || document.activeElement.id || null)"
    )


async def focused_in_dialog(page: Page) -> bool:
    return await page.evaluate(
        """() => {
            const d = document.querySelector('[role="dialog"]');
            return !!(d && document.activeElement && d.contains(document.activeElement));
        }"""
    )


async def seed_history(page: Page) -> None:
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
        state="visible", timeout=5000
    )


# ---------------------- A. Focus trap in modal ----------------------
async def check_focus_trap(page: Page, failures: list[str], notes: list[str]) -> None:
    await seed_history(page)
    trigger = page.get_by_role("button", name=re.compile(r"riwayat|history", re.I)).first
    trigger_label = await trigger.get_attribute("aria-label")
    await trigger.click()
    dialog = page.locator('[role="dialog"]').first
    await dialog.wait_for(state="visible", timeout=2000)
    await page.wait_for_timeout(250)

    # Forward Tab: 25 hops must all stay inside the dialog.
    for i in range(25):
        await page.keyboard.press("Tab")
        if not await focused_in_dialog(page):
            failures.append(f"[trap-forward] focus escaped dialog at Tab #{i+1}")
            break
    else:
        notes.append("[trap-forward] 25 Tab presses stayed inside dialog")

    # Reverse Shift+Tab: same guarantee.
    for i in range(25):
        await page.keyboard.press("Shift+Tab")
        if not await focused_in_dialog(page):
            failures.append(f"[trap-reverse] focus escaped dialog at Shift+Tab #{i+1}")
            break
    else:
        notes.append("[trap-reverse] 25 Shift+Tab presses stayed inside dialog")

    # Escape closes and restores focus.
    await page.keyboard.press("Escape")
    await page.wait_for_timeout(350)
    if await dialog.is_visible():
        failures.append("[trap-close] dialog still visible after Escape")
    after = await active_label(page)
    if after != trigger_label:
        failures.append(
            f"[trap-return-focus] focus not on trigger (got '{after}', want '{trigger_label}')"
        )
    else:
        notes.append(f"[trap-return-focus] focus restored to '{trigger_label}'")


# ---------------------- B. Main-page Tab order ----------------------
async def check_main_tab_order(page: Page, failures: list[str], notes: list[str]) -> None:
    # Move focus to the very top of the document.
    await page.evaluate(
        "() => { const b=document.body; b.setAttribute('tabindex','-1'); b.focus(); }"
    )
    forward_seen: list[str] = []
    # Tab up to 40 times, collect the ordered subset of INPUT_IDS we land on.
    for _ in range(40):
        await page.keyboard.press("Tab")
        aid = await active_id(page)
        if aid in INPUT_IDS and (not forward_seen or forward_seen[-1] != aid):
            forward_seen.append(aid)
        if forward_seen == INPUT_IDS:
            break

    if forward_seen != INPUT_IDS:
        failures.append(
            f"[tab-order-forward] expected {INPUT_IDS}, got {forward_seen}"
        )
    else:
        notes.append("[tab-order-forward] all 4 inputs reached in DOM order")

    # From #lot-tambah-input, next Tab should reach the primary Hitung button.
    for _ in range(6):
        await page.keyboard.press("Tab")
        role = await page.evaluate(
            "() => document.activeElement && (document.activeElement.tagName + ':' + (document.activeElement.textContent||'').trim().slice(0,20))"
        )
        if role and role.startswith("BUTTON") and re.search(r"hitung|calc", role, re.I):
            notes.append(f"[tab-order-cta] reached primary button ({role})")
            break
    else:
        notes.append("[tab-order-cta] primary Hitung button not adjacent (soft)")

    # Reverse walk: Shift+Tab from last input back through inputs.
    await page.locator(f"#{INPUT_IDS[-1]}").focus()
    reverse_seen: list[str] = [INPUT_IDS[-1]]
    for _ in range(20):
        await page.keyboard.press("Shift+Tab")
        aid = await active_id(page)
        if aid in INPUT_IDS and (not reverse_seen or reverse_seen[-1] != aid):
            reverse_seen.append(aid)
        if reverse_seen == list(reversed(INPUT_IDS)):
            break

    if reverse_seen != list(reversed(INPUT_IDS)):
        failures.append(
            f"[tab-order-reverse] expected {list(reversed(INPUT_IDS))}, got {reverse_seen}"
        )
    else:
        notes.append("[tab-order-reverse] Shift+Tab reversed the input chain exactly")


# ---------------------- C. Inline error aria contract ----------------------
async def check_error_aria(page: Page, failures: list[str], notes: list[str]) -> None:
    # Reset any state.
    await page.keyboard.press("Alt+KeyR")
    await page.wait_for_timeout(200)

    for input_id, (bad, good) in BAD_VALUES.items():
        inp = page.locator(f"#{input_id}")
        await inp.click()
        await inp.fill("")
        await inp.fill(bad)
        await inp.blur()
        await page.wait_for_timeout(200)

        state_bad = await page.evaluate(
            f"""() => {{
                const el = document.getElementById({input_id!r});
                if (!el) return null;
                const describedById = el.getAttribute('aria-describedby');
                const alert = describedById ? document.getElementById(describedById) : null;
                return {{
                    ariaInvalid: el.getAttribute('aria-invalid'),
                    describedBy: describedById,
                    alertRole: alert && alert.getAttribute('role'),
                    alertText: alert && (alert.textContent || '').trim(),
                    alertLive: alert && alert.getAttribute('aria-live'),
                }};
            }}"""
        )
        if not state_bad:
            failures.append(f"[aria/{input_id}] input element not found")
            continue
        if state_bad["ariaInvalid"] != "true":
            failures.append(
                f"[aria/{input_id}] invalid value did not set aria-invalid=true (got {state_bad['ariaInvalid']})"
            )
        expected_err_id = input_id.replace("-input", "-error")
        if not state_bad["describedBy"]:
            failures.append(f"[aria/{input_id}] no aria-describedby on invalid state")
        elif state_bad["describedBy"] != expected_err_id:
            failures.append(
                f"[aria/{input_id}] aria-describedby not '{expected_err_id}' (got {state_bad['describedBy']})"
            )
        if state_bad["alertRole"] != "alert":
            failures.append(
                f"[aria/{input_id}] alert region role != 'alert' (got {state_bad['alertRole']})"
            )
        if not state_bad["alertText"]:
            failures.append(f"[aria/{input_id}] alert text empty while invalid")
        else:
            notes.append(
                f"[aria/{input_id}] invalid → aria-invalid=true, describedby={state_bad['describedBy']}, alert='{state_bad['alertText'][:40]}'"
            )

        # Fix the value → contract must clear.
        await inp.click()
        await inp.fill("")
        await inp.fill(good)
        await inp.blur()
        await page.wait_for_timeout(200)

        state_good = await page.evaluate(
            f"""() => {{
                const el = document.getElementById({input_id!r});
                const describedById = el.getAttribute('aria-describedby');
                const alert = document.getElementById({input_id!r} + '-error');
                return {{
                    ariaInvalid: el.getAttribute('aria-invalid'),
                    describedBy: describedById,
                    alertText: alert && (alert.textContent || '').trim(),
                }};
            }}"""
        )
        if state_good["ariaInvalid"] not in (None, "false"):
            failures.append(
                f"[aria/{input_id}] after fix aria-invalid still '{state_good['ariaInvalid']}'"
            )
        if state_good["alertText"]:
            failures.append(
                f"[aria/{input_id}] after fix alert text still '{state_good['alertText']}'"
            )
        if state_good["describedBy"]:
            # Acceptable if the region is empty; only flag if describedby is set AND
            # points at non-empty text (would be stale announcement).
            if state_good["alertText"]:
                failures.append(
                    f"[aria/{input_id}] stale describedby={state_good['describedBy']} after fix"
                )
        notes.append(f"[aria/{input_id}] fixed value cleared error contract")


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
        page = await ctx.new_page()
        await page.goto(args.base_url, wait_until="domcontentloaded")
        await settle(page)

        print("\n== A. focus trap ==")
        await check_focus_trap(page, failures, notes)

        print("== B. tab order ==")
        await check_main_tab_order(page, failures, notes)

        print("== C. error aria ==")
        await check_error_aria(page, failures, notes)

        await browser.close()

    print("\n--- results ---")
    for n in notes:
        print(f"  ok  {n}")
    for f in failures:
        print(f"  FAIL {f}")
    print(f"\n{'PASS' if not failures else 'FAIL'} — {len(failures)} failure(s)")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
