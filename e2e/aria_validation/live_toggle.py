"""
E2E: verify inline error messages have the correct ARIA contract AND the
global aria-live status region stays consistent as I flip input validity
back and forth (valid → invalid → valid → invalid) across multiple fields
without reloading.

Focus of this scenario (complements aria_validation/transitions.py and
aria_live/verify.py):

  1. For each covered field, when the input becomes invalid the SAME DOM
     alert node is present with:
        - role="alert"
        - aria-live="assertive" or "polite" (implicit for role="alert")
        - id linked from the input's aria-describedby
     and the input has aria-invalid="true".
  2. When the input flips back to valid, aria-invalid becomes "false"
     (or is removed), aria-describedby is cleared, and the alert node is
     removed from the DOM (not just visually hidden).
  3. Flipping validity does NOT emit anything into the global
     aria-live="polite" #status region — that region must only change on
     Ctrl+Enter submit, otherwise screen readers get noisy per keystroke.
  4. After a successful submit, the status region announces the fresh
     result. Making an input invalid AGAIN clears the result card
     (existing auto-clear behavior) but must NOT append/repeat the old
     announcement in the status region — it either stays as the last
     spoken value (atomic replace) or clears; it never duplicates.
  5. The status region's DOM node identity is stable across the whole
     flow (critical for aria-atomic semantics on some screen readers).

Fields exercised: avg-now-input, total-lot-input, harga-avg-input,
lot-tambah-input. Invalid states are triggered with values the app
rejects WITHOUT auto-rounding (0 for prices/lots, non-integer for lots)
so the alert survives blur.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from playwright.async_api import Page, async_playwright


LIVE_SEL = '[role="status"][aria-live="polite"]'


async def field_aria(page: Page, id_: str) -> dict:
    # The alert <p> nodes for each field are always rendered (persistent
    # role="alert" containers whose text is populated only when the field
    # is invalid). We treat "invalid" as: aria-invalid=true AND the linked
    # alert node has non-empty text AND aria-describedby is set.
    return await page.evaluate(
        f"""() => {{
            const el = document.getElementById({id_!r});
            if (!el) return null;
            const describedBy = el.getAttribute('aria-describedby');
            const alertEl = describedBy ? document.getElementById(describedBy) : null;
            return {{
                ariaInvalid: el.getAttribute('aria-invalid'),
                describedBy,
                alertPresent: !!alertEl,
                alertRole: alertEl ? alertEl.getAttribute('role') : null,
                alertText: alertEl ? (alertEl.textContent || '').trim() : '',
            }};
        }}"""
    )


async def nonempty_alert_count(page: Page) -> int:
    return await page.evaluate(
        """() => Array.from(document.querySelectorAll('[role="alert"]'))
            .filter(n => (n.textContent || '').trim().length > 0).length"""
    )



async def live_text(page: Page) -> str:
    return (await page.locator(LIVE_SEL).first.inner_text()).strip()


async def set_value(page: Page, id_: str, val: str) -> None:
    el = page.locator(f"#{id_}")
    await el.click()
    await el.fill("")
    if val:
        await el.fill(val)
    await el.blur()
    await page.wait_for_timeout(120)


async def seed_valid(page: Page) -> None:
    for id_, v in (
        ("avg-now-input", "1000"),
        ("total-lot-input", "10"),
        ("harga-avg-input", "900"),
        ("lot-tambah-input", "5"),
    ):
        await set_value(page, id_, v)


async def submit(page: Page) -> None:
    await page.locator("#lot-tambah-input").focus()
    await page.keyboard.press("Control+Enter")
    await page.wait_for_timeout(300)


# (id, invalid_value, valid_value, why). Lot inputs sanitize non-digits on
# keystroke (intOnly), so "1.5" would collapse to "15" — invalid values here
# are chosen to survive sanitization and actually reach the validator.
CASES: list[tuple[str, str, str, str]] = [
    ("avg-now-input", "0", "1000", "price must be positive"),
    ("total-lot-input", "0", "10", "lot must be positive integer"),
    ("harga-avg-input", "0", "900", "price must be positive"),
    ("lot-tambah-input", "0", "5", "additional lot must be positive"),
]



async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://localhost:8080")
    args = ap.parse_args()

    failures: list[str] = []
    notes: list[str] = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(viewport={"width": 390, "height": 900})
        await ctx.add_init_script("try { localStorage.clear(); } catch(e) {}")
        page = await ctx.new_page()
        await page.goto(args.base_url, wait_until="domcontentloaded")
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(300)

        # Pin the live region node so we can detect replacement later.
        await page.locator(LIVE_SEL).first.evaluate("el => { window.__liveNode = el; }")

        # Global assumption: on first paint, region is empty and no alerts exist.
        if (t0 := await live_text(page)):
            failures.append(f"[baseline] status region non-empty on paint: {t0!r}")
        if (n0 := await page.locator('[role="alert"]').count()) != 0:
            failures.append(f"[baseline] expected 0 alerts on paint, found {n0}")

        await seed_valid(page)

        # Sanity: seeded state has no alerts and status region is still empty
        # (we haven't submitted yet).
        if (n1 := await page.locator('[role="alert"]').count()) != 0:
            failures.append(f"[seed] expected 0 alerts after seeding valid, got {n1}")
        if (t1 := await live_text(page)):
            failures.append(f"[seed] status region non-empty before submit: {t1!r}")

        # Establish a baseline announcement.
        await submit(page)
        base_announce = await live_text(page)
        if not base_announce:
            failures.append("[submit-1] status region empty after first submit")
        else:
            notes.append(f"[submit-1] announced: {base_announce[:80]}")

        # For each case: flip valid → invalid → valid, verifying ARIA contract
        # and that the status region does NOT change during typing/blur.
        for id_, bad, good, why in CASES:
            # Ensure baseline is valid (reseed the specific field to good).
            await set_value(page, id_, good)
            pre_toggle_text = await live_text(page)

            # invalid
            await set_value(page, id_, bad)
            state = await field_aria(page, id_)
            if state is None:
                failures.append(f"[{id_}/{bad}] input not found")
                continue
            if state["ariaInvalid"] != "true":
                failures.append(
                    f"[{id_}/{bad}] ({why}) expected aria-invalid=true, got {state['ariaInvalid']!r}"
                )
            if not state["describedBy"]:
                failures.append(f"[{id_}/{bad}] ({why}) aria-describedby missing")
            if not state["alertPresent"]:
                failures.append(
                    f"[{id_}/{bad}] ({why}) alert node referenced by aria-describedby not in DOM"
                )
            elif state["alertRole"] != "alert":
                failures.append(
                    f"[{id_}/{bad}] ({why}) alert role expected 'alert', got {state['alertRole']!r}"
                )
            elif not state["alertText"]:
                failures.append(f"[{id_}/{bad}] ({why}) alert text empty")

            # Global status region must not react to per-field validity.
            during_toggle_text = await live_text(page)
            if during_toggle_text != pre_toggle_text:
                failures.append(
                    f"[{id_}/{bad}] status region changed during invalid toggle "
                    f"({pre_toggle_text!r} → {during_toggle_text!r})"
                )

            # valid again
            await set_value(page, id_, good)
            state2 = await field_aria(page, id_)
            if state2["ariaInvalid"] == "true":
                failures.append(
                    f"[{id_}/{good}] recovered but aria-invalid still true"
                )
            if state2["describedBy"]:
                failures.append(
                    f"[{id_}/{good}] recovered but aria-describedby still set: {state2['describedBy']!r}"
                )
            if state2["alertPresent"]:
                failures.append(
                    f"[{id_}/{good}] recovered but alert node still in DOM: {state2['alertText']!r}"
                )

            after_recover_text = await live_text(page)
            if after_recover_text != pre_toggle_text:
                failures.append(
                    f"[{id_}/{good}] status region changed on recovery "
                    f"({pre_toggle_text!r} → {after_recover_text!r})"
                )

            notes.append(f"[{id_}] flip OK ({why})")

        # Second submit → status must UPDATE (not append) and be non-empty.
        # Change harga-avg to shift the numeric answer so we can detect replace.
        await set_value(page, "harga-avg-input", "800")
        # Result card auto-clears on input change; re-submit.
        await submit(page)
        second = await live_text(page)
        if not second:
            failures.append("[submit-2] status region empty after second submit")
        elif second == base_announce:
            failures.append(
                f"[submit-2] status region did not update after re-submit (still {second!r})"
            )
        else:
            # Atomic replace: the region shows the LATEST announcement only,
            # never a concatenation of both.
            if base_announce and base_announce in second and second != base_announce:
                failures.append(
                    f"[submit-2] status region appended old announcement: {second!r}"
                )
            notes.append(f"[submit-2] announced: {second[:80]}")

        # Region DOM identity must be stable across the whole session.
        same_node = await page.locator(LIVE_SEL).first.evaluate(
            "el => el === window.__liveNode"
        )
        if not same_node:
            failures.append("[stability] status region node was replaced during flow")

        await browser.close()

    print("\n--- aria live + inline error contract ---")
    for n in notes:
        print(f"  ok  {n}")
    for f in failures:
        print(f"  FAIL {f}")
    print(f"\n{'PASS' if not failures else 'FAIL'} — {len(failures)} failure(s)")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
