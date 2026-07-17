"""
Mobile-first layout sanity check across small viewports.

For each viewport (320, 360, 390, 414) verify:
  1. No horizontal overflow on <html> or <body> — content fits width.
  2. Every key surface (header, form, result card, footer) stays within the
     viewport's inner width (no element wider than viewport, no element
     bleeding past the right edge).
  3. Result card renders after a valid calculation and does not overflow
     its own container (scrollWidth <= clientWidth + 1px tolerance).
  4. History modal opens, is visible, fits within viewport width, has a
     close control, and closes cleanly (focus returns to trigger).

Run:
  python3 e2e/mobile/layout.py [--base-url http://localhost:8080]

Exit 0 on success, 1 on any failure. Screenshots saved under
/tmp/browser/mobile_layout/ for debugging.
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from pathlib import Path

from playwright.async_api import Page, async_playwright

SHOTS = Path("/tmp/browser/mobile_layout")
SHOTS.mkdir(parents=True, exist_ok=True)

VIEWPORTS = [
    {"name": "320w", "width": 320, "height": 780},
    {"name": "360w", "width": 360, "height": 800},
    {"name": "390w", "width": 390, "height": 844},
    {"name": "414w", "width": 414, "height": 896},
]

TOL = 1  # px tolerance for sub-pixel rounding


async def settle(page: Page) -> None:
    await page.wait_for_load_state("domcontentloaded")
    await page.wait_for_timeout(600)


async def fill_and_calc(page: Page) -> None:
    await page.locator("#avg-now-input").fill("1000")
    await page.locator("#total-lot-input").fill("10")
    await page.locator("#harga-avg-input").fill("900")
    await page.locator("#lot-tambah-input").fill("5")
    await page.locator("#lot-tambah-input").blur()
    # Prefer clicking the submit button — Ctrl+Enter isn't a mobile gesture.
    submit = page.locator('form button[type="submit"]').first
    if await submit.count() > 0:
        await submit.click()
    else:
        await page.keyboard.press("Control+Enter")
    await page.locator('[aria-labelledby="result-heading"]').first.wait_for(
        state="visible", timeout=5000
    )
    await page.wait_for_timeout(400)


async def check_no_horizontal_overflow(page: Page, vw: int) -> list[str]:
    """Return list of failure strings."""
    errors: list[str] = []
    metrics = await page.evaluate(
        """() => ({
            docScroll: document.documentElement.scrollWidth,
            docClient: document.documentElement.clientWidth,
            bodyScroll: document.body.scrollWidth,
            bodyClient: document.body.clientWidth,
            innerWidth: window.innerWidth,
        })"""
    )
    if metrics["docScroll"] > metrics["docClient"] + TOL:
        errors.append(
            f"document overflow: scrollWidth={metrics['docScroll']} > "
            f"clientWidth={metrics['docClient']}"
        )
    if metrics["bodyScroll"] > metrics["bodyClient"] + TOL:
        errors.append(
            f"body overflow: scrollWidth={metrics['bodyScroll']} > "
            f"clientWidth={metrics['bodyClient']}"
        )

    # Any element wider than the viewport or bleeding past the right edge.
    offenders = await page.evaluate(
        """(vw) => {
            const bad = [];
            const els = document.querySelectorAll('body *');
            for (const el of els) {
                const r = el.getBoundingClientRect();
                if (r.width === 0 || r.height === 0) continue;
                if (r.right > vw + 1 || r.width > vw + 1) {
                    const tag = el.tagName.toLowerCase();
                    const cls = (el.getAttribute('class') || '').slice(0, 60);
                    const id = el.id ? '#' + el.id : '';
                    bad.push({
                        sel: tag + id + (cls ? '.' + cls.replace(/\\s+/g, '.') : ''),
                        right: Math.round(r.right),
                        width: Math.round(r.width),
                    });
                    if (bad.length >= 5) break;
                }
            }
            return bad;
        }""",
        vw,
    )
    for o in offenders:
        errors.append(
            f"element out of viewport ({vw}px): {o['sel']} right={o['right']} width={o['width']}"
        )
    return errors


async def check_result_card_fit(page: Page) -> list[str]:
    errors: list[str] = []
    info = await page.evaluate(
        """() => {
            const card = document.querySelector('[aria-labelledby="result-heading"]');
            if (!card) return null;
            return {
                scrollWidth: card.scrollWidth,
                clientWidth: card.clientWidth,
                offsetLeft: card.getBoundingClientRect().left,
                offsetRight: card.getBoundingClientRect().right,
                innerWidth: window.innerWidth,
            };
        }"""
    )
    if not info:
        errors.append("result card missing after calc")
        return errors
    if info["scrollWidth"] > info["clientWidth"] + TOL:
        errors.append(
            f"result card overflows itself: scrollWidth={info['scrollWidth']} "
            f"> clientWidth={info['clientWidth']}"
        )
    if info["offsetRight"] > info["innerWidth"] + TOL:
        errors.append(
            f"result card past viewport right: right={info['offsetRight']} "
            f"> innerWidth={info['innerWidth']}"
        )

    # No descendant of the card should overflow it horizontally.
    kids = await page.evaluate(
        """() => {
            const card = document.querySelector('[aria-labelledby="result-heading"]');
            if (!card) return [];
            const rect = card.getBoundingClientRect();
            const bad = [];
            for (const el of card.querySelectorAll('*')) {
                const r = el.getBoundingClientRect();
                if (r.width === 0) continue;
                if (r.right > rect.right + 1 || r.left < rect.left - 1) {
                    bad.push({
                        sel: el.tagName.toLowerCase() +
                             (el.id ? '#' + el.id : '') +
                             ((el.getAttribute('class') || '').slice(0, 40)),
                        left: Math.round(r.left),
                        right: Math.round(r.right),
                    });
                    if (bad.length >= 3) break;
                }
            }
            return bad;
        }"""
    )
    for k in kids:
        errors.append(f"result card child overflow: {k['sel']} l={k['left']} r={k['right']}")
    return errors


async def check_history_modal(page: Page, vw: int) -> list[str]:
    errors: list[str] = []
    trigger = page.get_by_role("button", name=re.compile(r"riwayat|history", re.I)).first
    if await trigger.count() == 0:
        errors.append("history trigger button not found")
        return errors

    await trigger.focus()
    await trigger.click()
    dialog = page.locator('[role="dialog"]').first
    try:
        await dialog.wait_for(state="visible", timeout=2500)
    except Exception:
        errors.append("history dialog did not open")
        return errors
    await page.wait_for_timeout(250)

    box = await dialog.bounding_box()
    if not box:
        errors.append("history dialog has no bounding box")
    else:
        if box["width"] > vw + TOL:
            errors.append(f"dialog wider than viewport: {box['width']} > {vw}")
        if box["x"] + box["width"] > vw + TOL:
            errors.append(
                f"dialog past viewport right: right={box['x'] + box['width']} > {vw}"
            )
        if box["x"] < -TOL:
            errors.append(f"dialog past viewport left: x={box['x']}")

    # Descendants of the dialog must not overflow the dialog horizontally.
    kids = await page.evaluate(
        """() => {
            const d = document.querySelector('[role="dialog"]');
            if (!d) return [];
            const rect = d.getBoundingClientRect();
            const bad = [];
            for (const el of d.querySelectorAll('*')) {
                const r = el.getBoundingClientRect();
                if (r.width === 0) continue;
                if (r.right > rect.right + 1) {
                    bad.push({
                        sel: el.tagName.toLowerCase(),
                        right: Math.round(r.right),
                    });
                    if (bad.length >= 3) break;
                }
            }
            return bad;
        }"""
    )
    for k in kids:
        errors.append(f"dialog child overflow: {k['sel']} right={k['right']}")

    # Close via Escape and confirm focus returns to trigger.
    await page.keyboard.press("Escape")
    try:
        await dialog.wait_for(state="hidden", timeout=2000)
    except Exception:
        errors.append("dialog did not close on Escape")
        return errors
    await page.wait_for_timeout(150)
    focused_is_trigger = await page.evaluate(
        """() => {
            const t = [...document.querySelectorAll('button')].find(b =>
                /riwayat|history/i.test(b.textContent || b.getAttribute('aria-label') || '')
            );
            return t && document.activeElement === t;
        }"""
    )
    if not focused_is_trigger:
        errors.append("focus did not return to history trigger after Escape")
    return errors


async def run_one(page: Page, viewport: dict) -> list[str]:
    vw = viewport["width"]
    name = viewport["name"]
    errors: list[str] = []

    await settle(page)
    await page.screenshot(path=str(SHOTS / f"{name}_1_landing.png"))
    errors += [f"[{name} landing] {e}" for e in await check_no_horizontal_overflow(page, vw)]

    await fill_and_calc(page)
    await page.screenshot(path=str(SHOTS / f"{name}_2_result.png"))
    errors += [f"[{name} result-view] {e}" for e in await check_no_horizontal_overflow(page, vw)]
    errors += [f"[{name} result-card] {e}" for e in await check_result_card_fit(page)]

    errors += [f"[{name} history] {e}" for e in await check_history_modal(page, vw)]
    await page.screenshot(path=str(SHOTS / f"{name}_3_after_modal.png"))
    # Overflow must not have appeared as a side-effect of the modal cycle.
    errors += [f"[{name} post-modal] {e}" for e in await check_no_horizontal_overflow(page, vw)]

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
                    reduced_motion="reduce",
                    is_mobile=True,
                    has_touch=True,
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
    print("\nAll mobile viewports pass.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
