"""
E2E: verify IDX tick-size rounding rules for price inputs.

Rules (from src/lib/idx-tick.ts):
  price < 200   → tick 1
  price < 500   → tick 2
  price < 2000  → tick 5
  price < 5000  → tick 10
  price >= 5000 → tick 25

Behavior under test:
  - While an off-tick value is typed but the input is still focused, the
    inline validator surfaces a tickError (aria-invalid=true, role="alert"
    contains the suggested rounded value).
  - On blur, `handlePriceBlur` auto-rounds via `roundToTick`, clears the
    error, and the input's stored value becomes the rounded one.
  - Boundary flips: entering a value at the START of a new band uses the
    NEW band's tick (e.g. 200 → tick 2, 500 → tick 5, 2000 → tick 5→10,
    5000 → tick 25). Values just under a boundary still use the lower band.
  - Values <= 0 or > MAX_PRICE (1_000_000) are not auto-rounded (blur is
    a no-op) — a separate validator surfaces the positive/max error.
  - Rounding is nearest-half-up-to-even via Math.round: e.g. 502 → 500,
    503 → 505 (tick 5); 5012 → 5000, 5013 → 5025 (tick 25).

Fields covered: #avg-now-input, #harga-avg-input, and #target-avg-input
(after switching to the lots-needed mode).

Usage:
  python3 e2e/rounding/tick_size.py [--base-url http://localhost:8080]
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from pathlib import Path
from playwright.async_api import Page, async_playwright


SHOTS = Path(__file__).parent / "screenshots"
SHOTS.mkdir(parents=True, exist_ok=True)


# (input, expected_rounded) — every non-identity pair covers a distinct
# rounding decision: below-band, boundary-flip, and sensitive halfway cases.
CASES: list[tuple[str, str]] = [
    # tick 1 band (<200): identity
    ("150",   "150"),
    ("199",   "199"),
    # tick 2 band boundary flip
    ("200",   "200"),      # boundary → tick becomes 2, already aligned
    ("201",   "202"),      # 201/2 = 100.5 → 101 → 202  (round-half-to-even? Math.round rounds .5 away from zero → 101)
    ("498",   "498"),
    ("499",   "500"),      # 499/2 = 249.5 → 250 → 500 (also crosses band)
    # tick 5 band
    ("500",   "500"),
    ("502",   "500"),      # 502/5 = 100.4 → 100 → 500
    ("503",   "505"),      # 503/5 = 100.6 → 101 → 505
    ("1999",  "2000"),     # tick 5 at 1999: 1999/5 = 399.8 → 400 → 2000
    # tick 10 band
    ("2000",  "2000"),
    ("2004",  "2000"),
    ("2005",  "2010"),     # 2005/10 = 200.5 → 201 → 2010 (Math.round)
    ("4999",  "5000"),     # tick 10 at 4999: 500 → 5000
    # tick 25 band
    ("5000",  "5000"),
    ("5012",  "5000"),     # 5012/25 = 200.48 → 200 → 5000
    ("5013",  "5025"),     # 5013/25 = 200.52 → 201 → 5025
    ("5037",  "5025"),     # 5037/25 = 201.48 → 201 → 5025
    ("5038",  "5050"),     # 5038/25 = 201.52 → 202 → 5050
]


async def field_state(page: Page, id_: str) -> dict:
    return await page.evaluate(
        f"""() => {{
            const el = document.getElementById({id_!r});
            if (!el) return null;
            const errId = el.getAttribute('aria-describedby');
            const err = errId ? document.getElementById(errId) : null;
            return {{
                value: el.value,
                ariaInvalid: el.getAttribute('aria-invalid'),
                alertText: err ? (err.textContent || '').trim() : '',
            }};
        }}"""
    )


async def type_and_blur(page: Page, id_: str, value: str) -> tuple[dict, dict]:
    """Type value, capture pre-blur state, blur, capture post-blur state."""
    el = page.locator(f"#{id_}")
    await el.click()
    await el.fill("")
    await el.fill(value)
    await page.wait_for_timeout(120)
    pre = await field_state(page, id_)
    await el.blur()
    await page.wait_for_timeout(180)
    post = await field_state(page, id_)
    return pre, post


async def seed_defaults(page: Page) -> None:
    # Some fields need siblings populated for a clean state, but tick-size
    # blur logic is field-local — seed just enough to keep the form quiet.
    for id_, v in (
        ("avg-now-input", "1000"),
        ("total-lot-input", "10"),
        ("harga-avg-input", "900"),
    ):
        el = page.locator(f"#{id_}")
        await el.click()
        await el.fill("")
        await el.fill(v)
    await page.locator("body").click()
    await page.wait_for_timeout(150)


async def run_field_cases(page: Page, id_: str, label: str, failures: list[str], notes: list[str]) -> None:
    notes.append(f"[{label}] running {len(CASES)} cases against #{id_}")
    for raw, expected in CASES:
        pre, post = await type_and_blur(page, id_, raw)
        if pre is None or post is None:
            failures.append(f"[{label}/{raw}] input not found")
            continue

        expects_rounding = raw != expected

        # Pre-blur: if the typed value is off-tick, aria-invalid must be true
        # and the alert should mention the expected rounded number.
        if expects_rounding:
            if pre["ariaInvalid"] != "true":
                failures.append(
                    f"[{label}/{raw}] pre-blur aria-invalid expected 'true', got {pre['ariaInvalid']!r}"
                )
            if expected not in pre["alertText"].replace(".", "").replace(",", ""):
                # The alert formats via formatNumber (id-ID locale uses '.'
                # thousands separator). Strip separators before matching.
                failures.append(
                    f"[{label}/{raw}] pre-blur alert missing suggested {expected!r}: {pre['alertText']!r}"
                )
        else:
            if pre["ariaInvalid"] == "true":
                failures.append(
                    f"[{label}/{raw}] pre-blur aria-invalid true for aligned value: alert={pre['alertText']!r}"
                )

        # Post-blur: value should equal expected (as a plain string), the
        # aria-invalid should be cleared and the alert emptied.
        if post["value"] != expected:
            failures.append(
                f"[{label}/{raw}] post-blur value expected {expected!r}, got {post['value']!r}"
            )
        if post["ariaInvalid"] == "true":
            failures.append(
                f"[{label}/{raw}] post-blur still aria-invalid, alert={post['alertText']!r}"
            )
        if post["alertText"]:
            failures.append(
                f"[{label}/{raw}] post-blur alert not cleared: {post['alertText']!r}"
            )

    # No-op cases: 0 and MAX_PRICE+1 should NOT auto-round via handlePriceBlur.
    # They surface a different validation error (positive / max), not tick.
    for raw, why in (("0", "non-positive"), ("1000001", "exceeds MAX_PRICE")):
        _, post = await type_and_blur(page, id_, raw)
        if post["value"] != raw:
            failures.append(
                f"[{label}/no-op {raw}] value changed on blur ({why}): {post['value']!r}"
            )
        if post["ariaInvalid"] != "true":
            failures.append(
                f"[{label}/no-op {raw}] expected aria-invalid=true ({why}), got {post['ariaInvalid']!r}"
            )
        else:
            notes.append(f"[{label}/no-op {raw}] {why} surfaced without rounding")


async def switch_to_lots_needed(page: Page) -> None:
    tab = page.get_by_role("tab", name=re.compile(r"target", re.I)).first
    await tab.click()
    await page.wait_for_timeout(200)


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://localhost:8080")
    args = ap.parse_args()

    failures: list[str] = []
    notes: list[str] = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(viewport={"width": 1280, "height": 1800})
        await ctx.add_init_script("try { localStorage.clear(); } catch(e) {}")
        page = await ctx.new_page()
        await page.goto(args.base_url, wait_until="domcontentloaded")
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(300)

        await seed_defaults(page)

        # 1) avg-now-input (Harga Rata-rata Sekarang)
        await run_field_cases(page, "avg-now-input", "avg-now", failures, notes)
        # Reseed sane value so downstream cases don't spam validation.
        await page.locator("#avg-now-input").fill("1000")
        await page.locator("body").click()
        await page.wait_for_timeout(100)

        # 2) harga-avg-input (Harga Averaging)
        await run_field_cases(page, "harga-avg-input", "harga-avg", failures, notes)
        await page.locator("#harga-avg-input").fill("900")
        await page.locator("body").click()
        await page.wait_for_timeout(100)

        # 3) Switch mode → target-avg-input
        await switch_to_lots_needed(page)
        if await page.locator("#target-avg-input").count() == 0:
            failures.append("[target-avg] input not rendered after mode switch")
        else:
            await run_field_cases(page, "target-avg-input", "target-avg", failures, notes)

        await page.screenshot(path=str(SHOTS / "final.png"))
        await browser.close()

    print("\n--- tick-size rounding ---")
    for n in notes[-10:]:
        print(f"  ok  {n}")
    for f in failures:
        print(f"  FAIL {f}")
    print(f"\n{'PASS' if not failures else 'FAIL'} — {len(failures)} failure(s), {len(CASES)*3 + 6} assertions/field-run")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
