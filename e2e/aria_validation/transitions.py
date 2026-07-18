"""
Verify aria-invalid + role="alert" semantics across the five calculator
inputs, including round-trip transitions valid → invalid → valid.

For each field we assert three things at each state:

  1. The <Input> exposes the correct aria-invalid ("true" | "false").
  2. The paired <p role="alert"> node is always present (stable region,
     never remounted) and its text tracks the error string.
  3. aria-describedby is only set while there is an error, so screen
     readers don't announce an empty helper node on valid inputs.

We drive real UI: fill(), then blur (Tab off) so React commits, then read
computed DOM attributes via Playwright.
"""

import argparse
import asyncio
import sys
from dataclasses import dataclass
from typing import Callable, Awaitable, List, Tuple

from playwright.async_api import Page, async_playwright


# ─────────────────────────────────────────────────────────────────────────────
# Field registry
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class FieldSpec:
    label: str            # human name for failure messages
    input_id: str         # #id of the <Input>
    alert_id: str         # id of the paired <p role="alert">
    invalid_value: str    # a value that triggers the inline error
    fix_value: str        # a value that clears the error
    activator: str        # for lots-needed / new-avg fields, which side to activate first
                          # values: "always" | "new-avg" | "lots-needed"


# Prices default to IDX tick=5 in the 500–2000 range, so "1001" is off-tick.
# Lots max out at 1,000,000, so "1000001" overflows.
FIELDS: List[FieldSpec] = [
    FieldSpec("avg-now",      "avg-now-input",     "avg-now-error",     "1001",    "1000",  "always"),
    FieldSpec("total-lot",    "total-lot-input",   "total-lot-error",   "1000001", "10",    "always"),
    FieldSpec("harga-avg",    "harga-avg-input",   "harga-avg-error",   "1001",    "900",   "always"),
    FieldSpec("lot-tambah",   "lot-tambah-input",  "lot-tambah-error",  "1000001", "5",     "new-avg"),
    FieldSpec("target-avg",   "target-avg-input",  "target-avg-error",  "1001",    "950",   "lots-needed"),
]


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

async def settle(page: Page) -> None:
    await page.wait_for_load_state("domcontentloaded")
    # Hydration + URL-param reader effect need ~1s.
    await page.wait_for_timeout(1200)


async def fill_and_commit(page: Page, sel: str, value: str) -> None:
    """Fill an input then move focus away so blur handlers + memo re-runs
    commit before we read DOM attributes."""
    loc = page.locator(sel)
    await loc.click()
    # Clear via keyboard so React 'change' events fire (fill('') is fine too
    # but a select-all+delete matches real user behavior best).
    await page.keyboard.press("ControlOrMeta+A")
    await page.keyboard.press("Delete")
    if value:
        await loc.type(value, delay=8)
    # Blur to another well-known input to commit.
    other = "#total-lot-input" if not sel.endswith("total-lot-input") else "#avg-now-input"
    await page.locator(other).focus()
    # Give React one paint to flush the aria-invalid/describedby update.
    await page.wait_for_timeout(60)


async def read_state(page: Page, spec: FieldSpec) -> Tuple[str | None, str | None, str, bool]:
    """Return (aria-invalid, aria-describedby, alert text, alert node exists)."""
    inp = page.locator(f"#{spec.input_id}")
    aria_invalid = await inp.get_attribute("aria-invalid")
    aria_describedby = await inp.get_attribute("aria-describedby")
    alert = page.locator(f"#{spec.alert_id}")
    exists = await alert.count() == 1
    text = (await alert.inner_text()).strip() if exists else ""
    return aria_invalid, aria_describedby, text, exists


async def activate_mode_if_needed(page: Page, spec: FieldSpec) -> None:
    """The mode-picker only mounts one of #lot-tambah-input / #target-avg-input.
    We seed the OTHER visible price/lot fields first, then flip the picker
    to expose the target field."""
    if spec.activator == "always":
        return
    tab_name = "Add Lots" if spec.activator == "new-avg" else "Target Avg"
    # role='tab' with accessible name matching the mode label.
    tab = page.get_by_role("tab", name=tab_name, exact=False)
    if await tab.count() == 0:
        return
    # Only click if not already selected.
    selected = await tab.first.get_attribute("aria-selected")
    if selected != "true":
        await tab.first.click()
        # Component moves focus to the newly mounted input on rAF.
        await page.wait_for_timeout(80)


# ─────────────────────────────────────────────────────────────────────────────
# Per-field scenario
# ─────────────────────────────────────────────────────────────────────────────

async def check_field(page: Page, spec: FieldSpec, failures: List[str], notes: List[str]) -> None:
    tag = f"[{spec.label}]"
    await activate_mode_if_needed(page, spec)

    # ── State 0: PRISTINE / EMPTY ──────────────────────────────────────────
    # A brand-new empty field must NOT claim to be invalid, must NOT set
    # aria-describedby, and the role=alert region must exist but be empty
    # (stable node = SR won't re-announce on first error).
    await fill_and_commit(page, f"#{spec.input_id}", "")
    ai, adb, text, exists = await read_state(page, spec)
    if not exists:
        failures.append(f"{tag} role='alert' node missing on empty field")
    if ai not in (None, "false"):
        failures.append(f"{tag} empty field has aria-invalid='{ai}' (expected 'false' or missing)")
    if adb is not None:
        failures.append(f"{tag} empty field has aria-describedby='{adb}' (expected unset)")
    if text != "":
        failures.append(f"{tag} empty field alert text='{text}' (expected empty)")
    if not failures or failures[-1].split(" ")[0] != tag:
        notes.append(f"{tag} pristine: aria-invalid=false, describedby unset, alert empty")

    # ── State 1: INVALID ───────────────────────────────────────────────────
    await fill_and_commit(page, f"#{spec.input_id}", spec.invalid_value)
    ai, adb, text, exists = await read_state(page, spec)
    if not exists:
        failures.append(f"{tag} role='alert' node disappeared under error state (must be stable)")
    if ai != "true":
        failures.append(f"{tag} invalid value '{spec.invalid_value}' → aria-invalid='{ai}' (expected 'true')")
    if adb != spec.alert_id:
        failures.append(f"{tag} invalid value → aria-describedby='{adb}' (expected '{spec.alert_id}')")
    if not text:
        failures.append(f"{tag} invalid value produced empty alert text")
    else:
        notes.append(f"{tag} invalid → aria-invalid=true, describedby='{spec.alert_id}', alert='{text[:48]}'")

    # ── State 2: FIX (valid replacement, no clear in between) ──────────────
    await fill_and_commit(page, f"#{spec.input_id}", spec.fix_value)
    ai, adb, text, exists = await read_state(page, spec)
    if ai == "true":
        failures.append(f"{tag} after fixing → aria-invalid still 'true' (stale)")
    if adb is not None:
        failures.append(f"{tag} after fixing → aria-describedby='{adb}' (expected unset)")
    if text != "":
        failures.append(f"{tag} after fixing → alert text='{text}' (expected empty)")
    if not exists:
        failures.append(f"{tag} alert node vanished after fix (must remain in DOM)")
    else:
        notes.append(f"{tag} fixed → aria-invalid=false, describedby unset, alert cleared")

    # ── State 3: ROUND-TRIP valid → invalid → valid ────────────────────────
    await fill_and_commit(page, f"#{spec.input_id}", spec.invalid_value)
    ai_bad, adb_bad, text_bad, _ = await read_state(page, spec)
    await fill_and_commit(page, f"#{spec.input_id}", spec.fix_value)
    ai_ok, adb_ok, text_ok, _ = await read_state(page, spec)
    if ai_bad != "true" or adb_bad != spec.alert_id or not text_bad:
        failures.append(f"{tag} round-trip: invalid re-entry did not restore error attributes")
    if ai_ok == "true" or adb_ok is not None or text_ok != "":
        failures.append(f"{tag} round-trip: second fix did not clear error attributes")
    if not failures or failures[-1].split(" ")[0] != tag:
        notes.append(f"{tag} round-trip valid→invalid→valid toggles attributes cleanly")


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8080")
    args = parser.parse_args()

    failures: List[str] = []
    notes: List[str] = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(viewport={"width": 1280, "height": 1000})
        page = await ctx.new_page()
        await page.goto(args.base_url, wait_until="domcontentloaded")
        await settle(page)

        # Seed the "always visible" price/lot fields with sane values before
        # activating alternate modes, so the tablist keeps its context.
        for f in FIELDS:
            await check_field(page, f, failures, notes)

        await browser.close()

    print("\n--- aria-invalid / role=alert transitions ---")
    for n in notes:
        print(f"  ok  {n}")
    for f in failures:
        print(f"  FAIL {f}")
    if failures:
        print(f"\nFAIL — {len(failures)} failure(s)")
        return 1
    print("\nPASS — 0 failure(s)")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
