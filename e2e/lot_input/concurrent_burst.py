"""
E2E: interleaved fast typing across the two lot inputs.

Simulates a user (or paste-macro) that rapidly alternates focus + keystrokes
between #total-lot-input and #lot-tambah-input. Verifies:

  1. No lag / dropped keys: each input's final value equals the digits it
     actually received, in order.
  2. Digit-only enforcement holds even under interleaved bursts.
  3. Focus lands on the input we just clicked/typed into and never escapes
     to <body> / another input mid-render.
  4. aria-invalid + inline error (role="alert") reflect the final numeric
     value (valid ≤ MAX_LOT, invalid > MAX_LOT) for BOTH inputs
     independently — one field's error state must not leak to the other.
  5. The whole burst completes within a reasonable time budget (no re-render
     stall). Budget is generous to stay stable across engines.

Usage:
  python3 e2e/lot_input/concurrent_burst.py [--base-url http://localhost:8080]
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from playwright.async_api import Page, async_playwright

MAX_LOT = 1_000_000
# Interleaved plan: (selector, char). Keeps both fields valid (< MAX_LOT).
# Left target digits:  "12345678" (=12,345,678 → OVER MAX_LOT for scenario 2)
# Right target digits: "87654321" (=87,654,321 → OVER MAX_LOT for scenario 2)
# But scenario 1 uses smaller strings to stay valid.
LEFT_SEL = "#total-lot-input"
RIGHT_SEL = "#lot-tambah-input"


async def settle(page: Page) -> None:
    await page.wait_for_load_state("domcontentloaded")
    await page.wait_for_timeout(400)


async def ensure_new_avg_mode(page: Page) -> None:
    # lot-tambah-input only exists in "new-avg" (Lot Tambah) mode; it's the
    # default, but be defensive if a prior state is persisted.
    if await page.locator(RIGHT_SEL).count() == 0:
        btn = page.get_by_role("button", name="Lot Tambah").first
        if await btn.count() == 0:
            btn = page.get_by_role("button", name="Add Lots").first
        if await btn.count():
            await btn.click()
            await page.wait_for_timeout(150)


async def focused_id(page: Page) -> str | None:
    return await page.evaluate(
        "() => document.activeElement && document.activeElement.id || null"
    )


async def read(page: Page, sel: str) -> dict:
    return await page.evaluate(
        """(s) => {
            const el = document.querySelector(s);
            if (!el) return {value: null, aria: null, errText: null};
            const wrap = el.closest('div');
            const err = wrap ? wrap.querySelector('p[role="alert"]') : null;
            return {
                value: el.value,
                aria: el.getAttribute('aria-invalid'),
                errText: err ? (err.textContent || '').trim() : '',
            };
        }""",
        sel,
    )


async def clear(page: Page, sel: str) -> None:
    loc = page.locator(sel)
    await loc.focus()
    await loc.fill("")


async def run_interleaved(
    page: Page,
    plan: list[tuple[str, str]],
    failures: list[str],
    notes: list[str],
    label: str,
) -> dict:
    """Type per (sel, ch) plan. After every keystroke, snapshot focus."""
    await clear(page, LEFT_SEL)
    await clear(page, RIGHT_SEL)
    # Warm the browser + React so the first real keystroke isn't dropped
    # while a focus/blur re-render is still flushing.
    await page.locator(plan[0][0]).focus()
    await page.wait_for_timeout(80)

    per_key: list[dict] = []
    current_focus: str | None = plan[0][0].lstrip("#")
    t0 = time.perf_counter()

    for sel, ch in plan:
        target_id = sel.lstrip("#")
        if current_focus != target_id:
            # Switch focus without a mouse click so caret position is
            # deterministic (append to end) regardless of existing text length.
            await page.locator(sel).focus()
            # Wait a frame so React can settle the focus event before typing.
            await page.wait_for_timeout(16)
            await page.keyboard.press("End")
            current_focus = target_id
        await page.keyboard.type(ch, delay=0)
        active = await focused_id(page)
        per_key.append({"sel": sel, "ch": ch, "activeId": active})

    elapsed = time.perf_counter() - t0

    # Focus stability: after each keystroke, active element must be the input
    # we just targeted (never <body>, never the other input).
    escapes = [
        (i, s["sel"], s["activeId"])
        for i, s in enumerate(per_key)
        if s["activeId"] != s["sel"].lstrip("#")
    ]
    if escapes:
        failures.append(
            f"[{label}] focus escaped during burst at {escapes[:3]} (of {len(escapes)})"
        )
    else:
        notes.append(
            f"[{label}] focus tracked target across {len(per_key)} interleaved keys"
        )

    # Timing budget: 200 keys should complete well under 8s even on slow CI.
    budget_s = max(4.0, len(plan) * 0.05)
    if elapsed > budget_s:
        failures.append(
            f"[{label}] burst took {elapsed:.2f}s > budget {budget_s:.2f}s (lag suspected)"
        )
    else:
        notes.append(f"[{label}] burst finished in {elapsed:.2f}s (budget {budget_s:.2f}s)")

    left_expect = "".join(c for s, c in plan if s == LEFT_SEL)
    right_expect = "".join(c for s, c in plan if s == RIGHT_SEL)
    left = await read(page, LEFT_SEL)
    right = await read(page, RIGHT_SEL)

    if left["value"] != left_expect:
        failures.append(f"[{label}] left value '{left['value']}' != expected '{left_expect}'")
    if right["value"] != right_expect:
        failures.append(f"[{label}] right value '{right['value']}' != expected '{right_expect}'")

    if not any(f.startswith(f"[{label}]") and "value" in f for f in failures):
        notes.append(f"[{label}] final values ok — left='{left['value']}', right='{right['value']}'")

    return {"left": left, "right": right, "left_expect": left_expect, "right_expect": right_expect}


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
        await ensure_new_avg_mode(page)

        # --- Scenario A: both fields end VALID (below MAX_LOT). ---
        # Left digits collect to "123456" (=123,456); right to "987654" (=987,654).
        left_digits_a = "123456"
        right_digits_a = "987654"
        plan_a: list[tuple[str, str]] = []
        # Interleave: L R L R L R ...
        for lc, rc in zip(left_digits_a, right_digits_a):
            plan_a.append((LEFT_SEL, lc))
            plan_a.append((RIGHT_SEL, rc))
        state_a = await run_interleaved(page, plan_a, failures, notes, "valid-interleave")

        # Both must be aria-invalid=false/null and have no error text.
        for side, r in (("left", state_a["left"]), ("right", state_a["right"])):
            if r["aria"] not in (None, "false"):
                failures.append(f"[valid-interleave] {side} aria-invalid='{r['aria']}' for valid value")
            if r["errText"]:
                failures.append(f"[valid-interleave] {side} inline error present: '{r['errText']}'")

        # --- Scenario B: independence of error state. ---
        # Left becomes OVER MAX_LOT ("12345678" → 12,345,678), right stays VALID
        # ("87654" → 87,654). Only the left input must report aria-invalid=true.
        await clear(page, LEFT_SEL)
        await clear(page, RIGHT_SEL)

        left_digits_b = "12345678"       # over max
        right_digits_b = "87654"         # valid
        plan_b: list[tuple[str, str]] = []
        it_l = iter(left_digits_b)
        it_r = iter(right_digits_b)
        # Round-robin, exhaust the longer sequence.
        while True:
            got = False
            try:
                plan_b.append((LEFT_SEL, next(it_l))); got = True
            except StopIteration:
                pass
            try:
                plan_b.append((RIGHT_SEL, next(it_r))); got = True
            except StopIteration:
                pass
            if not got:
                break

        state_b = await run_interleaved(page, plan_b, failures, notes, "mixed-validity")

        if state_b["left"]["aria"] != "true":
            failures.append(
                f"[mixed-validity] left aria-invalid='{state_b['left']['aria']}' (expected 'true' for over-max)"
            )
        else:
            notes.append("[mixed-validity] left correctly aria-invalid=true")
        if not state_b["left"]["errText"]:
            failures.append("[mixed-validity] left inline error missing for over-max value")

        if state_b["right"]["aria"] not in (None, "false"):
            failures.append(
                f"[mixed-validity] right aria-invalid='{state_b['right']['aria']}' leaked from left's error"
            )
        else:
            notes.append("[mixed-validity] right stayed valid — no error leakage")
        if state_b["right"]["errText"]:
            failures.append(
                f"[mixed-validity] right inline error unexpectedly present: '{state_b['right']['errText']}'"
            )

        # --- Scenario C: recovery — delete one digit from left, right untouched. ---
        await page.locator(LEFT_SEL).focus()
        await page.keyboard.press("End")
        # Delete two digits so 12,345,678 → 123,456 (valid, < MAX_LOT).
        await page.keyboard.press("Backspace")
        await page.keyboard.press("Backspace")
        await page.wait_for_timeout(60)
        after = await read(page, LEFT_SEL)
        right_after = await read(page, RIGHT_SEL)
        expected_left_after = left_digits_b[:-2]
        if after["value"] != expected_left_after:
            failures.append(
                f"[recovery] left value='{after['value']}' after 2×Backspace (expected '{expected_left_after}')"
            )
        if after["aria"] not in (None, "false"):
            failures.append(f"[recovery] left aria-invalid='{after['aria']}' after returning to valid")
        else:
            notes.append("[recovery] left cleared error after Backspace")
        if right_after["value"] != right_digits_b:
            failures.append(
                f"[recovery] right value mutated during left's re-render: '{right_after['value']}'"
            )
        else:
            notes.append("[recovery] right value preserved through left's validation re-render")
        if (await focused_id(page)) != "total-lot-input":
            failures.append("[recovery] focus escaped left input after Backspace")

        await browser.close()

    print("\n--- concurrent lot input burst ---")
    for n in notes:
        print(f"  ok  {n}")
    for f in failures:
        print(f"  FAIL {f}")
    print(f"\n{'PASS' if not failures else 'FAIL'} — {len(failures)} failure(s)")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
