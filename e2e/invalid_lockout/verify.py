"""
Invalid-field lockout: verifies that when any single field becomes
invalid, neither the Calculate button (click) nor the Ctrl+Enter
shortcut can produce a new / mutated result card. The result card must
stay absent until every input is valid again AND the user re-triggers
the calculation.

The app auto-clears the previous result whenever any input changes
(inputs no longer match the snapshot that produced the card), so
"lockout" here means:

  - After making a field invalid, Calculate + Ctrl+Enter must NOT
    render any new result card.
  - `aria-disabled="true"` stays on the Calculate button so keyboard /
    assistive tech signal the locked state.
  - After restoring every field to valid values (but before
    re-calculating), the card must still be absent — the app must not
    silently re-materialize the old result.
  - Only an explicit Calculate action on a fully-valid form brings a
    fresh, correct card back.

Flow (per candidate field):
  1. Establish a "baseline" by loading valid inputs and calculating.
  2. Snapshot the baseline result card text.
  3. Corrupt one field → assert:
       - card disappears,
       - button is aria-disabled,
       - clicking Calculate (force, because of aria-disabled) does not
         create a new card,
       - Ctrl+Enter does not create a new card.
  4. Restore the field to its baseline value → card still absent (no
     phantom recalculation), button re-enabled.
  5. Bump one OTHER valid field so a real recalc would produce a
     different result, press Ctrl+Enter → card renders and differs
     from the baseline.
  6. Reset to baseline for the next case.

Run:
  python3 e2e/invalid_lockout/verify.py [--base-url http://localhost:8080]
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from pathlib import Path

from playwright.async_api import Page, async_playwright

SHOTS = Path("/tmp/browser/invalid_lockout")
SHOTS.mkdir(parents=True, exist_ok=True)

# Baseline: valid new-avg inputs that produce a stable calculation.
BASELINE = {
    "#avg-now-input":   "1500",
    "#total-lot-input": "10",
    "#harga-avg-input": "1200",
    "#lot-tambah-input": "5",
}

# One perturbed value per field. Each value must fail the field's
# validator without accidentally satisfying it.
INVALID_CASES: list[tuple[str, str, str]] = [
    # (input,               invalid_value, why)
    ("#avg-now-input",       "",           "empty avg price"),
    ("#avg-now-input",       "0",          "zero avg price"),
    ("#total-lot-input",     "",           "empty total lot"),
    ("#total-lot-input",     "0",          "zero total lot"),
    ("#harga-avg-input",     "",           "empty averaging price"),
    ("#lot-tambah-input",    "",           "empty lot tambah"),
    ("#lot-tambah-input",    "0",          "zero lot tambah"),
    # Over MAX_LOT (1_000_000) — sanitized digits but out-of-range.
    ("#total-lot-input",     "9999999",    "total lot over max"),
    ("#lot-tambah-input",    "9999999",    "lot tambah over max"),
]


async def settle(page: Page) -> None:
    await page.wait_for_load_state("domcontentloaded")
    await page.locator("#avg-now-input").wait_for(state="visible", timeout=5000)
    await page.wait_for_timeout(400)


async def set_value(page: Page, sel: str, value: str) -> None:
    """Clear the input, type the value, and blur so tick-rounding runs."""
    loc = page.locator(sel)
    await loc.click()
    await loc.press("Control+A")
    await loc.press("Delete")
    if value:
        await loc.type(value, delay=5)
    # Blur into the body so any onBlur normalization kicks in.
    await page.evaluate("() => document.activeElement && document.activeElement.blur()")
    await page.wait_for_timeout(80)


async def load_baseline(page: Page) -> None:
    for sel, v in BASELINE.items():
        await set_value(page, sel, v)


async def read_card(page: Page) -> str | None:
    loc = page.locator("[data-result-card]")
    if await loc.count() == 0:
        return None
    return (await loc.first.inner_text()).strip()


async def calc_button_state(page: Page) -> dict:
    return await page.evaluate(
        """() => {
            const btn = document.querySelector('button[aria-disabled], form button[type]');
            const submitBtn = Array.from(document.querySelectorAll('button'))
              .find(b => b.getAttribute('aria-disabled') !== null);
            const b = submitBtn || btn;
            return b ? {
                type: b.getAttribute('type'),
                ariaDisabled: b.getAttribute('aria-disabled'),
                text: (b.textContent || '').trim(),
            } : null;
        }"""
    )


async def try_calculate(page: Page) -> None:
    """Try both routes: click the Calculate button, then Ctrl+Enter."""
    # 1) Click the calculate button (it always exists; when invalid it
    #    should call focusFirstInvalid instead of computing).
    btn = page.get_by_role("button", name=re.compile(r"^(Hitung|Calculate)$", re.I))
    if await btn.count() > 0:
        # aria-disabled='true' makes Playwright treat the button as disabled;
        # force the click so we exercise the app's own guard (which routes
        # to focusFirstInvalid instead of running the calc).
        await btn.first.click(force=True)
        await page.wait_for_timeout(200)
    # 2) Keyboard shortcut.
    await page.locator("#avg-now-input").focus()
    await page.keyboard.press("Control+Enter")
    await page.wait_for_timeout(250)


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8080")
    args = parser.parse_args()

    errors: list[str] = []
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
            # ---- Establish baseline result ----
            await load_baseline(page)
            await page.locator("#lot-tambah-input").focus()
            await page.keyboard.press("Control+Enter")
            await page.wait_for_timeout(400)
            baseline = await read_card(page)
            if not baseline:
                print("FATAL: baseline calculation did not render a result card.")
                await page.screenshot(path=str(SHOTS / "fatal_no_baseline.png"))
                return 2
            await page.screenshot(path=str(SHOTS / "00_baseline.png"))

            for idx, (sel, bad, why) in enumerate(INVALID_CASES, start=1):
                tag = f"[{idx}] {sel} -> {bad!r} ({why})"

                # Corrupt a single field.
                await set_value(page, sel, bad)

                # Sanity: aria-invalid must reflect the bad state
                # (empty fields disable the calc without setting
                # aria-invalid, so we only check for non-empty payloads).
                aria = await page.locator(sel).get_attribute("aria-invalid")
                if bad and aria != "true":
                    errors.append(f"{tag}: expected aria-invalid='true', got {aria!r}")

                # Attempt to calculate — the button is aria-disabled and
                # Ctrl+Enter's guard should short-circuit. The result
                # card must NOT (re)appear.
                await try_calculate(page)
                after = await read_card(page)
                await page.screenshot(path=str(SHOTS / f"{idx:02d}_locked.png"))

                if after is not None:
                    errors.append(
                        f"{tag}: result card rendered while a field was "
                        f"invalid — content:\n{after[:300]}"
                    )

                btn_state = await calc_button_state(page)
                if btn_state and btn_state.get("ariaDisabled") != "true":
                    errors.append(
                        f"{tag}: Calculate button aria-disabled={btn_state.get('ariaDisabled')!r} "
                        f"(should be 'true' while a field is invalid)"
                    )

                # Restore this field to its baseline value. The card
                # must still be absent — no phantom recalculation.
                await set_value(page, sel, BASELINE[sel])
                await page.wait_for_timeout(120)
                dormant = await read_card(page)
                if dormant is not None:
                    errors.append(
                        f"{tag}: card re-appeared after restore without an explicit "
                        f"Calculate action — content:\n{dormant[:300]}"
                    )
                btn_state = await calc_button_state(page)
                if btn_state and btn_state.get("ariaDisabled") == "true":
                    errors.append(
                        f"{tag}: Calculate button remained aria-disabled after "
                        f"all fields were restored to valid values"
                    )

                # Restore to valid — and nudge one other field so the
                # recomputed card differs from the baseline. We tweak
                # `#lot-tambah-input` unless that IS the perturbed field,
                # in which case we tweak `#total-lot-input`.
                await set_value(page, sel, BASELINE[sel])
                bump_target = (
                    "#total-lot-input" if sel == "#lot-tambah-input" else "#lot-tambah-input"
                )
                bumped_value = "8" if bump_target == "#lot-tambah-input" else "20"
                await set_value(page, bump_target, bumped_value)

                await page.locator(bump_target).focus()
                await page.keyboard.press("Control+Enter")
                await page.wait_for_timeout(300)
                recovered = await read_card(page)
                await page.screenshot(path=str(SHOTS / f"{idx:02d}_recovered.png"))

                if recovered is None:
                    errors.append(f"{tag}: no result card after recovery")
                elif recovered == baseline:
                    errors.append(
                        f"{tag}: card did NOT update after fixing input + bumping "
                        f"{bump_target} to {bumped_value!r}"
                    )

                # Reset for the next round.
                await set_value(page, bump_target, BASELINE[bump_target])
                await page.locator("#lot-tambah-input").focus()
                await page.keyboard.press("Control+Enter")
                await page.wait_for_timeout(250)
                restored = await read_card(page)
                if restored != baseline:
                    errors.append(
                        f"{tag}: could not restore baseline card after this round"
                    )
        finally:
            await browser.close()

    print(f"\nScreenshots: {SHOTS}")
    if errors:
        print(f"\n{len(errors)} failure(s):")
        for e in errors:
            print(f"  · {e}")
        return 1
    print("\nInvalid-field lockout holds for every field and both calc paths.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
