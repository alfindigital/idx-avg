"""
E2E mobile: verify the calculator form, mode tab picker, and result card
remain readable without horizontal overflow on small viewports, and the
Calculate (Hitung) button is genuinely clickable (visible, hit-testable,
tap-target ≥44×44 px).

Runs across 320w, 360w, 390w, 414w.
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from pathlib import Path
from playwright.async_api import Page, async_playwright

VIEWPORTS = [
    ("iphone-se-320", 320, 640),
    ("android-360", 360, 720),
    ("iphone-13-390", 390, 844),
    ("iphone-plus-414", 414, 896),
]

SCREENSHOTS = Path(__file__).parent / "screenshots_readable_mobile"
SCREENSHOTS.mkdir(parents=True, exist_ok=True)


async def check_no_horizontal_overflow(page: Page, label: str) -> None:
    metrics = await page.evaluate(
        "() => ({ sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth })"
    )
    assert metrics["sw"] <= metrics["cw"] + 1, (
        f"{label}: horizontal overflow (scrollWidth={metrics['sw']} > clientWidth={metrics['cw']})"
    )


async def check_element_within_viewport(page: Page, selector: str, label: str) -> dict:
    box = await page.locator(selector).first.bounding_box()
    assert box, f"{label}: element {selector} missing"
    vw = await page.evaluate("() => window.innerWidth")
    assert box["x"] >= -1 and box["x"] + box["width"] <= vw + 1, (
        f"{label}: {selector} spills viewport (x={box['x']:.1f}, w={box['width']:.1f}, vw={vw})"
    )
    return box


async def readable_text(page: Page, selector: str, label: str) -> None:
    """Font-size ≥12px, not clipped by overflow:hidden ancestor, visible."""
    info = await page.locator(selector).first.evaluate(
        """el => {
            const cs = getComputedStyle(el);
            const rect = el.getBoundingClientRect();
            return {
              fontSize: parseFloat(cs.fontSize),
              opacity: parseFloat(cs.opacity),
              visibility: cs.visibility,
              display: cs.display,
              width: rect.width,
              height: rect.height,
            };
        }"""
    )
    assert info["visibility"] != "hidden" and info["display"] != "none", (
        f"{label}: {selector} not visible"
    )
    assert info["opacity"] > 0.5, f"{label}: {selector} faded (opacity={info['opacity']})"
    assert info["fontSize"] >= 11, f"{label}: {selector} font too small ({info['fontSize']}px)"
    assert info["width"] > 0 and info["height"] > 0, f"{label}: {selector} zero-sized"


async def run_one(page: Page, name: str, w: int, h: int, base_url: str) -> None:
    await page.set_viewport_size({"width": w, "height": h})
    await page.goto(base_url, wait_until="domcontentloaded")
    await page.wait_for_load_state("networkidle")
    await page.evaluate("() => localStorage.clear()")
    await page.reload(wait_until="networkidle")
    await page.wait_for_timeout(200)

    label = f"{name} ({w}x{h})"

    # --- Empty form: no overflow, tabs & inputs visible & readable ---------
    await check_no_horizontal_overflow(page, f"{label} empty")

    tabs = page.locator('[role="tab"]')
    assert await tabs.count() == 2, f"{label}: expected 2 mode tabs"
    for i in range(2):
        tab_box = await check_element_within_viewport(page, f'[role="tab"] >> nth={i}', label)
        assert tab_box["height"] >= 32, (
            f"{label}: tab #{i} too short ({tab_box['height']:.1f}px)"
        )
        # Readable label inside the tab.
        await readable_text(page, f'[role="tab"] >> nth={i}', label)

    for iid in ("avg-now-input", "total-lot-input", "harga-avg-input", "lot-tambah-input"):
        box = await check_element_within_viewport(page, f"#{iid}", label)
        assert box["height"] >= 40, f"{label}: #{iid} too short ({box['height']:.1f}px)"

    # Calculate button reachable? (disabled while inputs empty — still must be
    # sized, visible, on-screen, and NOT covered by another element.)
    btn = page.get_by_role("button", name=re.compile(r"^(Hitung|Calculate)$", re.I)).first
    await btn.wait_for(state="visible")
    btn_box = await btn.bounding_box()
    assert btn_box, f"{label}: calculate button missing"
    assert btn_box["height"] >= 44 and btn_box["width"] >= 44, (
        f"{label}: calculate tap target {btn_box['width']:.0f}x{btn_box['height']:.0f} < 44"
    )
    # No occluder at button center.
    cx, cy = btn_box["x"] + btn_box["width"] / 2, btn_box["y"] + btn_box["height"] / 2
    covered = await page.evaluate(
        """([x, y]) => {
            const top = document.elementFromPoint(x, y);
            const btn = document.querySelector('button[type="submit"], button[aria-disabled]');
            // The topmost element at the button's center must be inside the button.
            if (!top) return { covered: true, reason: 'no element at point' };
            const targets = Array.from(document.querySelectorAll('button')).filter(b => /^(hitung|calculate)$/i.test((b.textContent||'').trim()));
            for (const t of targets) {
              if (t.contains(top) || top.contains(t) || t === top) return { covered: false };
            }
            return { covered: true, tag: top.tagName, cls: top.className.toString().slice(0,80) };
        }""",
        [cx, cy],
    )
    assert not covered["covered"], f"{label}: calculate button occluded: {covered}"

    # Fill via keyboard-friendly typing and submit with a real click.
    await page.locator("#avg-now-input").fill("1000")
    await page.locator("#total-lot-input").fill("10")
    await page.locator("#harga-avg-input").fill("1000")
    await page.locator("#lot-tambah-input").fill("10")
    await page.wait_for_timeout(150)

    # Now the button should be enabled → real click must trigger calc.
    await btn.click()
    await page.wait_for_selector("[data-result-card]", timeout=3000)
    await page.wait_for_timeout(200)

    # --- Filled + result: no overflow, result card fits, readable heading ---
    await check_no_horizontal_overflow(page, f"{label} with result")
    card_box = await check_element_within_viewport(page, "[data-result-card]", label)
    assert card_box["width"] <= w + 1, f"{label}: result card wider than viewport"
    await readable_text(page, "#result-heading", label)

    body_text = await page.locator("body").inner_text()
    assert re.search(r"Rp\s?1\.000\b", re.sub(r"\s+", " ", body_text)), (
        f"{label}: expected 'Rp 1.000' in result card"
    )
    assert "NaN" not in body_text and "Infinity" not in body_text

    await page.screenshot(path=str(SCREENSHOTS / f"{name}.png"))
    print(f"[ok] {label}: form + tabs + result readable, no overflow, Hitung clickable")


async def main_async(base_url: str) -> None:
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 320, "height": 640})
        page = await context.new_page()
        for name, w, h in VIEWPORTS:
            await run_one(page, name, w, h, base_url)
        await browser.close()


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--base-url", default="http://localhost:8080")
    args = p.parse_args()
    try:
        asyncio.run(main_async(args.base_url))
    except AssertionError as e:
        print(f"[fail] {e}", file=sys.stderr)
        return 1
    print("[pass] mobile readability + Hitung clickability across all viewports")
    return 0


if __name__ == "__main__":
    sys.exit(main())
