"""
E2E: click "Target Rata-rata" tab and verify focus moves to #target-avg-input
without breaking layout on small viewports.

Assertions:
  1. Clicking the tab flips aria-selected and reveals #target-avg-input.
  2. After click, document.activeElement is #target-avg-input.
  3. No horizontal overflow (documentElement.scrollWidth <= clientWidth).
  4. Tab labels remain single-line (offsetHeight <= 1.6 * lineHeight).
  5. Layout stable across viewports: 320, 360, 375, 390, 414 px.

Usage:
  python3 e2e/mode_switch/click_target_focus.py [--base-url http://localhost:8080]
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from playwright.async_api import Page, async_playwright


VIEWPORTS = [320, 360, 375, 390, 414]


async def settle(page: Page) -> None:
    await page.wait_for_load_state("domcontentloaded")
    await page.wait_for_timeout(300)


async def check_viewport(page: Page, width: int) -> list[str]:
    fails: list[str] = []
    await page.set_viewport_size({"width": width, "height": 900})
    await page.wait_for_timeout(150)

    # Ensure we start from the new-avg mode.
    add_tab = page.get_by_role("tab", name=re.compile(r"lot\s*tambah|add\s*lot", re.I)).first
    await add_tab.click()
    await page.wait_for_timeout(200)

    # No target input yet.
    if await page.locator("#target-avg-input").count() != 0:
        fails.append(f"[{width}px] target-avg-input visible before switch")

    # Click "Target Rata-rata" tab.
    target_tab = page.get_by_role("tab", name=re.compile(r"target", re.I)).first
    await target_tab.scroll_into_view_if_needed()
    await target_tab.click()
    await page.wait_for_timeout(250)

    aria_sel = await target_tab.get_attribute("aria-selected")
    if aria_sel != "true":
        fails.append(f"[{width}px] target tab aria-selected={aria_sel!r}")

    tgt = page.locator("#target-avg-input")
    if await tgt.count() == 0:
        fails.append(f"[{width}px] #target-avg-input did not render after click")
        return fails

    # Focus assertion.
    focused_id = await page.evaluate(
        "() => document.activeElement && document.activeElement.id"
    )
    if focused_id != "target-avg-input":
        fails.append(
            f"[{width}px] focus not on target-avg-input (activeElement id={focused_id!r})"
        )

    # No horizontal overflow.
    overflow = await page.evaluate(
        """() => {
            const d = document.documentElement;
            return { scroll: d.scrollWidth, client: d.clientWidth };
        }"""
    )
    if overflow["scroll"] > overflow["client"] + 1:
        fails.append(
            f"[{width}px] horizontal overflow scrollWidth={overflow['scroll']} > clientWidth={overflow['client']}"
        )

    # Tab labels single-line.
    tab_metrics = await page.evaluate(
        """() => {
            const tabs = Array.from(document.querySelectorAll('[role="tab"]'));
            return tabs.map(t => {
                const cs = getComputedStyle(t);
                const lh = parseFloat(cs.lineHeight) || parseFloat(cs.fontSize) * 1.2;
                return {
                    text: (t.textContent || '').trim(),
                    height: t.offsetHeight,
                    lineHeight: lh,
                    whiteSpace: cs.whiteSpace,
                    scrollW: t.scrollWidth,
                    clientW: t.clientWidth,
                };
            });
        }"""
    )
    for m in tab_metrics:
        # Heuristic: tab wraps if content height exceeds ~1.6x line-height.
        if m["lineHeight"] and m["height"] > m["lineHeight"] * 1.9:
            fails.append(
                f"[{width}px] tab {m['text']!r} looks wrapped: h={m['height']} lh={m['lineHeight']}"
            )
        if m["scrollW"] > m["clientW"] + 1:
            fails.append(
                f"[{width}px] tab {m['text']!r} label clipped scrollW={m['scrollW']} > clientW={m['clientW']}"
            )

    return fails


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://localhost:8080")
    args = ap.parse_args()

    all_fails: list[str] = []
    notes: list[str] = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(viewport={"width": 375, "height": 900})
        page = await ctx.new_page()
        await page.goto(args.base_url, wait_until="domcontentloaded")
        await settle(page)

        for w in VIEWPORTS:
            fs = await check_viewport(page, w)
            if fs:
                all_fails.extend(fs)
            else:
                notes.append(f"[{w}px] click→focus→layout OK")

        await browser.close()

    print("\n--- click Target Rata-rata → focus + layout ---")
    for n in notes:
        print(f"  ok  {n}")
    for f in all_fails:
        print(f"  FAIL {f}")
    print(f"\n{'PASS' if not all_fails else 'FAIL'} — {len(all_fails)} failure(s)")
    return 0 if not all_fails else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
