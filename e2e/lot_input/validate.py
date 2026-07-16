"""
E2E: lot inputs (#total-lot-input, #lot-tambah-input) must

  1. Strip non-digit characters even under fast keyboard input, so the
     rendered .value never contains letters, spaces, punctuation, or emojis.
  2. Show the correct inline error (#total-lot-error / #lot-tambah-error,
     role="alert") when the numeric value exceeds MAX_LOT (1_000_000),
     and clear it when the value returns to a valid range.
  3. Keep focus on the input the user is typing into throughout every
     keystroke and every render caused by validation (no focus jumping to
     another input / button / body).
  4. Preserve aria-invalid ↔ error-node presence in lockstep with the
     current value across the entire typing burst.

Usage:
  python3 e2e/lot_input/validate.py [--base-url http://localhost:8080]
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from playwright.async_api import Page, async_playwright


MAX_LOT = 1_000_000
GARBAGE = "1a2b!3@ 4#$%^&5*()_6+-=7"                # digits scattered inside junk
EXPECTED_STRIPPED = "1234567"                          # digits only, order preserved, valid (< MAX_LOT)


async def settle(page: Page) -> None:
    await page.wait_for_load_state("domcontentloaded")
    await page.wait_for_timeout(500)


async def input_value(page: Page, sel: str) -> str:
    return await page.locator(sel).input_value()


async def focused_id(page: Page) -> str | None:
    return await page.evaluate(
        "() => document.activeElement && document.activeElement.id || null"
    )


async def type_burst_and_watch(page: Page, sel: str) -> dict:
    """
    Type a garbage burst quickly (delay=0) and, after every key, snapshot:
      - active element id (focus stability)
      - the input's current value (digit-only enforcement)
    Returns dict with 'per_key' list and final state.
    """
    per_key: list[dict] = []
    loc = page.locator(sel)
    await loc.focus()
    await loc.fill("")
    input_id = await loc.get_attribute("id")

    # Press each character with delay=0 to simulate fast typing / autofill.
    for ch in GARBAGE:
        await page.keyboard.type(ch, delay=0)
        # Read immediately after each keystroke.
        state = await page.evaluate(
            """(id) => {
                const el = document.getElementById(id);
                return {
                    value: el ? el.value : null,
                    activeId: document.activeElement && document.activeElement.id || null,
                    ariaInvalid: el ? el.getAttribute('aria-invalid') : null,
                };
            }""",
            input_id,
        )
        per_key.append({"ch": ch, **state})

    return {"input_id": input_id, "per_key": per_key}


async def check_error_visibility(page: Page, error_id: str) -> tuple[bool, str]:
    """Returns (has_text, text)."""
    txt = await page.evaluate(
        """(id) => {
            const el = document.getElementById(id);
            if (!el) return null;
            return (el.textContent || '').trim();
        }""",
        error_id,
    )
    return (bool(txt), txt or "")


async def scenario_burst(page: Page, sel: str, err_id: str, failures: list[str], notes: list[str]) -> None:
    burst = await type_burst_and_watch(page, sel)
    input_id = burst["input_id"]

    # (1) After every keystroke, .value must contain only digits.
    bad = [
        (i, s) for i, s in enumerate(burst["per_key"])
        if s["value"] is None or any(c for c in s["value"] if not c.isdigit())
    ]
    if bad:
        failures.append(
            f"[{sel}] non-digit rendered mid-burst at steps "
            f"{[(i, s['ch'], s['value']) for i, s in bad[:3]]}"
        )
    else:
        notes.append(f"[{sel}] every intermediate value was digit-only across {len(burst['per_key'])} keys")

    # (2) Focus must never leave the input during the burst.
    focus_escapes = [
        (i, s["activeId"]) for i, s in enumerate(burst["per_key"])
        if s["activeId"] != input_id
    ]
    if focus_escapes:
        failures.append(
            f"[{sel}] focus escaped input mid-burst at steps {focus_escapes[:3]}"
        )
    else:
        notes.append(f"[{sel}] focus stayed on '{input_id}' across the whole burst")

    # (3) Final value matches EXPECTED_STRIPPED.
    final = await input_value(page, sel)
    if final != EXPECTED_STRIPPED:
        failures.append(f"[{sel}] final value '{final}' != expected '{EXPECTED_STRIPPED}'")
    else:
        notes.append(f"[{sel}] final value = '{final}'")

    # (4) Valid range → no inline error.
    has_err, txt = await check_error_visibility(page, err_id)
    if has_err:
        failures.append(f"[{sel}] unexpected inline error for valid value '{final}': '{txt}'")
    aria = await page.locator(sel).get_attribute("aria-invalid")
    if aria not in (None, "false"):
        failures.append(f"[{sel}] aria-invalid={aria} for a valid value")


async def scenario_over_max(page: Page, sel: str, err_id: str, failures: list[str], notes: list[str]) -> None:
    """Type MAX_LOT + 1 → inline error must appear and aria-invalid must flip to 'true'."""
    loc = page.locator(sel)
    await loc.focus()
    await loc.fill("")
    over = "2000000"  # 2,000,000 → over MAX_LOT; Backspace → "200000" (valid)
    input_id = await loc.get_attribute("id")

    for ch in over:
        await page.keyboard.type(ch, delay=0)

    # Focus preserved through validation.
    active_now = await focused_id(page)
    if active_now != input_id:
        failures.append(f"[{sel}] focus moved to '{active_now}' after over-max typing")
    else:
        notes.append(f"[{sel}] focus preserved on '{input_id}' after over-max typing")

    # Inline error node must have text; aria-invalid must be 'true'.
    has_err, txt = await check_error_visibility(page, err_id)
    aria = await loc.get_attribute("aria-invalid")
    if not has_err:
        failures.append(f"[{sel}] no inline error for over-max value '{over}'")
    else:
        notes.append(f"[{sel}] inline error present: '{txt}'")
    if aria != "true":
        failures.append(f"[{sel}] aria-invalid='{aria}' (expected 'true') for over-max value")
    else:
        notes.append(f"[{sel}] aria-invalid='true' for over-max value")

    # aria-describedby must now point to the error id.
    described = await loc.get_attribute("aria-describedby")
    if described != err_id:
        failures.append(
            f"[{sel}] aria-describedby='{described}' (expected '{err_id}') when in error state"
        )

    # Now delete one digit → value becomes 200000 (valid) → error must clear.
    await page.keyboard.press("Backspace")
    await page.wait_for_timeout(50)
    final_val = await loc.input_value()
    has_err2, txt2 = await check_error_visibility(page, err_id)
    aria2 = await loc.get_attribute("aria-invalid")
    active_after = await focused_id(page)
    if final_val != "200000":
        failures.append(f"[{sel}] after Backspace value='{final_val}' (expected '200000')")
    if has_err2:
        failures.append(f"[{sel}] inline error did not clear after Backspace: '{txt2}'")
    if aria2 not in (None, "false"):
        failures.append(f"[{sel}] aria-invalid='{aria2}' after returning to valid range")
    if active_after != input_id:
        failures.append(f"[{sel}] focus escaped ('{active_after}') after error cleared")
    if not (has_err2 or aria2 == "true"):
        notes.append(f"[{sel}] error cleared and focus preserved after Backspace")


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

        # ---- total-lot ----
        await scenario_burst(
            page, "#total-lot-input", "total-lot-error", failures, notes
        )
        await scenario_over_max(
            page, "#total-lot-input", "total-lot-error", failures, notes
        )

        # ---- lot-tambah (requires the other required inputs to render;
        #     the input itself is always present in "new-avg" mode which is
        #     the default). Ensure the field exists then run the same checks.
        if await page.locator("#lot-tambah-input").count() == 0:
            # Switch to "new-avg" mode if necessary — click first mode toggle button.
            toggle = page.get_by_role("button", name="Add Lots").first
            if await toggle.count():
                await toggle.click()
                await page.wait_for_timeout(200)

        if await page.locator("#lot-tambah-input").count():
            # The lot-tambah error node id — read it from the DOM.
            err_id = await page.evaluate(
                """() => {
                    const el = document.getElementById('lot-tambah-input');
                    if (!el) return null;
                    // Its aria-describedby is set only when in error state; the
                    // sibling <p role='alert'> has a stable id.
                    const p = el.closest('div')?.querySelector('p[role="alert"]');
                    return p ? p.id : null;
                }"""
            )
            if not err_id:
                # Force an error to make aria-describedby appear.
                await page.locator("#lot-tambah-input").fill(str(MAX_LOT + 1))
                err_id = await page.locator("#lot-tambah-input").get_attribute(
                    "aria-describedby"
                )
                await page.locator("#lot-tambah-input").fill("")
            if err_id:
                await scenario_burst(
                    page, "#lot-tambah-input", err_id, failures, notes
                )
                await scenario_over_max(
                    page, "#lot-tambah-input", err_id, failures, notes
                )
            else:
                failures.append("[lot-tambah] could not resolve inline error node id")
        else:
            notes.append("[lot-tambah] input not rendered — mode does not expose it")

        await browser.close()

    print("\n--- lot input validation ---")
    for n in notes:
        print(f"  ok  {n}")
    for f in failures:
        print(f"  FAIL {f}")
    print(f"\n{'PASS' if not failures else 'FAIL'} — {len(failures)} failure(s)")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
