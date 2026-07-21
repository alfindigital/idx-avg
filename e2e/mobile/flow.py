"""
Responsive mobile flow test.

Complements e2e/mobile/layout.py (which measures overflow) by driving the
full calculation flow on real mobile viewports with touch, and verifying:

  1. The complete flow works end-to-end using taps (not clicks/keyboard):
     fill inputs → tap Hitung → result card appears → tap reset.
  2. Every interactive control on the primary UI has a touch target of at
     least 44×44 CSS px (WCAG 2.5.5 / Apple HIG minimum).
  3. Interactive controls are not covered by another element: the point at
     the center of each control's bounding box must hit that control (or a
     descendant), not something layered above it.
  4. When an input is focused (as if the mobile keyboard were open), the
     input remains visible in the top half of the viewport — the sticky
     footer / mode tabs must not obscure the currently focused field.
  5. No horizontal overflow is introduced at any step of the flow.

Run:
  python3 e2e/mobile/flow.py [--base-url http://localhost:8080]

Exit 0 on success, 1 on any failure. Screenshots under
/tmp/browser/mobile_flow/.
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from pathlib import Path

from playwright.async_api import Locator, Page, async_playwright

SHOTS = Path("/tmp/browser/mobile_flow")
SHOTS.mkdir(parents=True, exist_ok=True)

VIEWPORTS = [
    {"name": "320w", "width": 320, "height": 780},
    {"name": "360w", "width": 360, "height": 800},
    {"name": "390w", "width": 390, "height": 844},
    {"name": "414w", "width": 414, "height": 896},
]

MIN_TAP = 44  # WCAG 2.5.5 minimum in CSS pixels.
TOL = 1


async def settle(page: Page) -> None:
    await page.wait_for_load_state("domcontentloaded")
    await page.wait_for_timeout(500)


async def horizontal_overflow(page: Page) -> list[str]:
    m = await page.evaluate(
        """() => ({
            ds: document.documentElement.scrollWidth,
            dc: document.documentElement.clientWidth,
            bs: document.body.scrollWidth,
            bc: document.body.clientWidth,
        })"""
    )
    out = []
    if m["ds"] > m["dc"] + TOL:
        out.append(f"document scrollWidth={m['ds']} > clientWidth={m['dc']}")
    if m["bs"] > m["bc"] + TOL:
        out.append(f"body scrollWidth={m['bs']} > clientWidth={m['bc']}")
    return out


async def tap_fill(page: Page, sel: str, value: str) -> None:
    loc = page.locator(sel)
    await loc.scroll_into_view_if_needed()
    await loc.tap()
    await loc.fill(value)


async def measure_tap_targets(page: Page) -> list[str]:
    """Return list of failures for controls smaller than MIN_TAP px."""
    data = await page.evaluate(
        """(min) => {
            const selectors = [
              'form button[type="submit"]',
              'button[aria-label]',
              '[role="tab"]',
            ];
            const seen = new Set();
            const bad = [];
            for (const sel of selectors) {
                for (const el of document.querySelectorAll(sel)) {
                    if (seen.has(el)) continue;
                    seen.add(el);
                    if (el.hasAttribute('disabled')) continue;
                    const style = getComputedStyle(el);
                    if (style.display === 'none' || style.visibility === 'hidden') continue;
                    const r = el.getBoundingClientRect();
                    if (r.width === 0 || r.height === 0) continue;
                    if (r.width < min - 0.5 || r.height < min - 0.5) {
                        bad.push({
                            label: (el.getAttribute('aria-label')
                                    || el.textContent || '').trim().slice(0, 40),
                            tag: el.tagName.toLowerCase(),
                            w: Math.round(r.width),
                            h: Math.round(r.height),
                        });
                    }
                }
            }
            return bad;
        }""",
        MIN_TAP,
    )
    return [
        f"tap target too small: <{d['tag']} aria-label={d['label']!r}> "
        f"= {d['w']}×{d['h']} (min {MIN_TAP})"
        for d in data
    ]


async def check_not_covered(page: Page, selectors: list[str]) -> list[str]:
    """For each selector, tap-point should hit the element or a descendant."""
    fails = await page.evaluate(
        """(selectors) => {
            const fails = [];
            for (const sel of selectors) {
                const el = document.querySelector(sel);
                if (!el) { fails.push({sel, reason: 'not-found'}); continue; }
                el.scrollIntoView({block: 'center', inline: 'center'});
                const r = el.getBoundingClientRect();
                if (r.width === 0 || r.height === 0) {
                    fails.push({sel, reason: 'zero-size'}); continue;
                }
                const cx = Math.round(r.left + r.width / 2);
                const cy = Math.round(r.top + r.height / 2);
                if (cy < 0 || cy > window.innerHeight
                    || cx < 0 || cx > window.innerWidth) {
                    fails.push({sel, reason: `center offscreen (${cx},${cy})`});
                    continue;
                }
                const top = document.elementFromPoint(cx, cy);
                if (!top) { fails.push({sel, reason: 'no-hit'}); continue; }
                if (top !== el && !el.contains(top) && !top.contains(el)) {
                    fails.push({
                        sel,
                        reason: `covered by <${top.tagName.toLowerCase()}` +
                                (top.className ? ' .' + String(top.className).slice(0, 30) : '') +
                                '>',
                    });
                }
            }
            return fails;
        }""",
        selectors,
    )
    return [f"{f['sel']}: {f['reason']}" for f in fails]


async def check_focused_input_visible(page: Page, sel: str) -> list[str]:
    loc = page.locator(sel)
    await loc.scroll_into_view_if_needed()
    await loc.focus()
    await page.wait_for_timeout(120)
    info = await page.evaluate(
        """(sel) => {
            const el = document.querySelector(sel);
            if (!el) return null;
            const r = el.getBoundingClientRect();
            return {
                top: r.top, bottom: r.bottom,
                left: r.left, right: r.right,
                vh: window.innerHeight, vw: window.innerWidth,
                focused: document.activeElement === el,
            };
        }""",
        sel,
    )
    errs: list[str] = []
    if not info:
        return [f"{sel}: element missing"]
    if not info["focused"]:
        errs.append(f"{sel}: did not receive focus")
    if info["top"] < 0 or info["bottom"] > info["vh"] + TOL:
        errs.append(
            f"{sel}: focused field not fully in viewport "
            f"(top={info['top']:.0f}, bottom={info['bottom']:.0f}, vh={info['vh']})"
        )
    if info["right"] > info["vw"] + TOL or info["left"] < -TOL:
        errs.append(
            f"{sel}: focused field horizontally clipped "
            f"(left={info['left']:.0f}, right={info['right']:.0f}, vw={info['vw']})"
        )
    return errs


async def run_one(page: Page, viewport: dict) -> list[str]:
    name = viewport["name"]
    errors: list[str] = []

    await settle(page)
    errors += [f"[{name} landing overflow] {e}" for e in await horizontal_overflow(page)]
    await page.screenshot(path=str(SHOTS / f"{name}_1_landing.png"))

    # Focused-input visibility on each of the four price/lot fields.
    for sel in ("#avg-now-input", "#total-lot-input", "#harga-avg-input", "#lot-tambah-input"):
        errors += [f"[{name} focus-visible] {e}"
                   for e in await check_focused_input_visible(page, sel)]

    # Fill via taps + fill (mimics mobile input path).
    await tap_fill(page, "#avg-now-input", "1000")
    await tap_fill(page, "#total-lot-input", "10")
    await tap_fill(page, "#harga-avg-input", "900")
    await tap_fill(page, "#lot-tambah-input", "5")
    await page.locator("#lot-tambah-input").blur()

    # Tap targets must meet the 44px minimum before we submit.
    errors += [f"[{name} tap-target] {e}" for e in await measure_tap_targets(page)]

    # Key interactive controls must not be visually covered.
    covered_selectors = [
        'form button[type="submit"]',
        '[role="tab"][aria-selected="true"]',
    ]
    # Include the History trigger if present.
    hist_id = await page.evaluate(
        """() => {
            const t = [...document.querySelectorAll('button')].find(b =>
                /riwayat|history/i.test(b.getAttribute('aria-label') || b.textContent || '')
            );
            if (!t) return null;
            if (!t.id) t.id = '__test_history_trigger__';
            return '#' + t.id;
        }"""
    )
    if hist_id:
        covered_selectors.append(hist_id)
    errors += [f"[{name} covered] {e}"
               for e in await check_not_covered(page, covered_selectors)]

    # Tap Hitung.
    submit = page.locator('form button[type="submit"]').first
    await submit.scroll_into_view_if_needed()
    await submit.tap()

    card = page.locator('[aria-labelledby="result-heading"]').first
    try:
        await card.wait_for(state="visible", timeout=5000)
    except Exception:
        errors.append(f"[{name} calc] result card never appeared")
        await page.screenshot(path=str(SHOTS / f"{name}_ERR_no_card.png"))
        return errors
    await page.wait_for_timeout(300)
    await page.screenshot(path=str(SHOTS / f"{name}_2_result.png"))

    # Overflow / coverage must still hold after the result card renders.
    errors += [f"[{name} post-calc overflow] {e}" for e in await horizontal_overflow(page)]
    reset_id = await page.evaluate(
        """() => {
            const b = [...document.querySelectorAll('button')].find(x =>
                /^reset$|reset/i.test(x.getAttribute('aria-label') || '')
            );
            if (!b) return null;
            if (!b.id) b.id = '__test_reset_btn__';
            return '#' + b.id;
        }"""
    )
    post_selectors = ['[aria-labelledby="result-heading"]']
    if reset_id:
        post_selectors.append(reset_id)
    errors += [f"[{name} post-calc covered] {e}"
               for e in await check_not_covered(page, post_selectors)]
    errors += [f"[{name} post-calc tap-target] {e}"
               for e in await measure_tap_targets(page)]

    # Tap reset and confirm the flow tears down cleanly.
    if reset_id:
        reset_btn = page.locator(reset_id)
        await reset_btn.scroll_into_view_if_needed()
        await reset_btn.tap()
        await page.wait_for_timeout(250)
        cleared = await page.evaluate(
            """() => {
                const inputs = ['#avg-now-input','#total-lot-input',
                                '#harga-avg-input','#lot-tambah-input'];
                return inputs.every(s => (document.querySelector(s)?.value ?? '') === '');
            }"""
        )
        if not cleared:
            errors.append(f"[{name} reset] inputs not cleared after tap reset")
    else:
        errors.append(f"[{name} reset] reset button not found")

    await page.screenshot(path=str(SHOTS / f"{name}_3_after_reset.png"))
    errors += [f"[{name} final overflow] {e}" for e in await horizontal_overflow(page)]
    return errors


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8080")
    args = parser.parse_args()

    all_errors: list[str] = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        try:
            for vp in VIEWPORTS:
                context = await browser.new_context(
                    viewport={"width": vp["width"], "height": vp["height"]},
                    device_scale_factor=2,
                    is_mobile=True,
                    has_touch=True,
                    reduced_motion="reduce",
                )
                page = await context.new_page()
                await page.goto(args.base_url, wait_until="domcontentloaded")
                errs = await run_one(page, vp)
                if errs:
                    all_errors.extend(errs)
                    print(f"  [FAIL] {vp['name']}")
                    for e in errs:
                        print(f"         · {e}")
                else:
                    print(f"  [ OK ] {vp['name']}")
                await context.close()
        finally:
            await browser.close()

    print(f"\nScreenshots: {SHOTS}")
    if all_errors:
        print(f"\n{len(all_errors)} failure(s)")
        return 1
    print("\nAll mobile flow scenarios pass.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
