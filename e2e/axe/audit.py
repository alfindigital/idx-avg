"""
Automated axe-core accessibility audit driven by Playwright.
import re

Runs WCAG 2.1 A/AA rules against three critical surfaces of the calculator:
  1. Form (empty + validation error states)
  2. Result card (after a successful calculation)
  3. History modal (open dialog)

Executed across four mobile viewports (320, 360, 390, 414) to catch
regressions that only appear at narrow widths.

`color-contrast` is disabled because the design system uses OKLCH tokens
that axe's sRGB-based algorithm mis-reports; contrast is instead covered
by src/__tests__/contrast.test.ts.

Exit status:
  0  — zero violations across every surface / viewport combination
  1  — one or more violations (details printed to stdout)

Usage:
  python3 e2e/axe/audit.py [--base-url http://localhost:8080]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from playwright.async_api import Page, async_playwright

AXE_CDN = "https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.10.2/axe.min.js"
AXE_LOCAL = Path(__file__).parent / "axe.min.js"

VIEWPORTS = [
    {"name": "320w", "width": 320, "height": 720},
    {"name": "360w", "width": 360, "height": 780},
    {"name": "390w", "width": 390, "height": 844},
    {"name": "414w", "width": 414, "height": 896},
]

AXE_OPTIONS = {
    "runOnly": {"type": "tag", "values": ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]},
    # Contrast is validated by the OKLCH token test; axe uses sRGB and false-positives here.
    "rules": {"color-contrast": {"enabled": False}},
}


async def load_axe(page: Page) -> None:
    if AXE_LOCAL.exists():
        await page.add_script_tag(path=str(AXE_LOCAL))
    else:
        await page.add_script_tag(url=AXE_CDN)


async def run_axe(page: Page, context_selector: str | None = None) -> dict[str, Any]:
    ctx = json.dumps(context_selector) if context_selector else "document"
    script = f"""
        (async () => {{
            const results = await window.axe.run({ctx}, {json.dumps(AXE_OPTIONS)});
            return {{
                violations: results.violations.map(v => ({{
                    id: v.id,
                    impact: v.impact,
                    help: v.help,
                    nodes: v.nodes.map(n => ({{
                        target: n.target,
                        failureSummary: n.failureSummary,
                    }})),
                }})),
            }};
        }})()
    """
    return await page.evaluate(script)


async def settle(page: Page) -> None:
    await page.wait_for_load_state("networkidle")
    await page.wait_for_timeout(1500)


async def audit_surface(
    page: Page,
    base_url: str,
    surface: str,
    viewport: dict[str, Any],
) -> list[dict[str, Any]]:
    await page.set_viewport_size({"width": viewport["width"], "height": viewport["height"]})
    await page.goto(base_url, wait_until="domcontentloaded")
    await settle(page)
    await load_axe(page)

    if surface == "form-empty":
        target = None
    elif surface == "form-error":
        await page.locator("#avg-now-input").fill("0")
        await page.locator("#total-lot-input").fill("1")
        await page.locator("#total-lot-input").blur()
        await settle(page)
        target = None
    elif surface == "result-card":
        await page.locator("#avg-now-input").fill("1000")
        await page.locator("#total-lot-input").fill("10")
        await page.locator("#harga-avg-input").fill("900")
        await page.locator("#lot-tambah-input").fill("5")
        await page.keyboard.press("Control+Enter")
        await settle(page)
        target = '[aria-labelledby="result-heading"]'
    elif surface == "history-modal":
        trigger = page.get_by_role("button", name=re.compile(r"riwayat|history", re.I))
        await trigger.first.click()
        await settle(page)
        target = '[role="dialog"]'
    else:
        raise ValueError(f"Unknown surface: {surface}")

    # If a scoped selector isn't present, fall back to full-document audit.
    if target:
        exists = await page.locator(target).count()
        if exists == 0:
            target = None

    result = await run_axe(page, target)
    return result["violations"]


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8080")
    args = parser.parse_args()

    surfaces = ["form-empty", "form-error", "result-card", "history-modal"]
    total_violations = 0
    report: list[str] = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        try:
            for viewport in VIEWPORTS:
                context = await browser.new_context(
                    viewport={"width": viewport["width"], "height": viewport["height"]},
                )
                page = await context.new_page()
                for surface in surfaces:
                    try:
                        violations = await audit_surface(page, args.base_url, surface, viewport)
                    except Exception as e:  # noqa: BLE001
                        report.append(f"[ERROR] {viewport['name']}/{surface}: {e}")
                        total_violations += 1
                        continue
                    tag = f"{viewport['name']}/{surface}"
                    if violations:
                        total_violations += len(violations)
                        report.append(f"[FAIL] {tag}: {len(violations)} violation(s)")
                        for v in violations:
                            report.append(
                                f"  - {v['id']} ({v['impact']}): {v['help']} "
                                f"[{len(v['nodes'])} node(s)]"
                            )
                            for n in v["nodes"][:3]:
                                report.append(f"      target={n['target']}")
                    else:
                        report.append(f"[ OK ] {tag}")
                await context.close()
        finally:
            await browser.close()

    print("\n".join(report))
    print(f"\nTotal violations: {total_violations}")
    return 0 if total_violations == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
