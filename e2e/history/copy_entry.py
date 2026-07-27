"""
E2E: verify the per-entry Copy button inside the History dialog copies the
correct summary to the clipboard and surfaces accessible success feedback
(a live-region toast) without loading the entry back into the form.

Flow:
  1. Clear localStorage, load app, fill valid inputs, Ctrl+Enter to compute.
  2. Snapshot current form values + result card outerHTML.
  3. Open History via Alt+H, wait for dialog.
  4. Locate the per-entry Copy button (aria-label starts with "Copy: Rp ...").
     - Assert it exposes an accessible name.
  5. Click it. Assert:
     a. Clipboard text matches expected summary (head line + New Avg + trend +
        percentage + Total Capital line).
     b. A Sonner toast with role="status" (aria-live) becomes visible and
        contains "Summary copied" (English) or "Ringkasan disalin" (Indo).
     c. Dialog stays open (copy is per-entry, not "load"); form inputs and the
        result card outerHTML are byte-identical to the snapshot.

Usage:
  python3 e2e/history/copy_entry.py [--base-url http://localhost:8080]
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

CARD_SEL = '[aria-labelledby="result-heading"]'
DIALOG_SEL = '[role="dialog"]'


async def settle(page: Page) -> None:
    await page.wait_for_load_state("networkidle")
    await page.wait_for_timeout(300)


async def fill_and_calc(page: Page) -> None:
    for id_, v in [
        ("avg-now-input", "2000"),
        ("total-lot-input", "10"),
        ("harga-avg-input", "1500"),
        ("lot-tambah-input", "10"),
    ]:
        await page.locator(f"#{id_}").fill(v)
    await page.locator("#lot-tambah-input").blur()
    await page.keyboard.press("Control+Enter")
    await page.locator(CARD_SEL).first.wait_for(state="visible", timeout=5000)
    await page.wait_for_timeout(300)


async def read_inputs(page: Page) -> dict[str, str]:
    out: dict[str, str] = {}
    for id_ in ["avg-now-input", "total-lot-input", "harga-avg-input", "lot-tambah-input"]:
        out[id_] = await page.locator(f"#{id_}").input_value()
    return out


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://localhost:8080")
    args = ap.parse_args()

    failures: list[str] = []
    notes: list[str] = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            permissions=["clipboard-read", "clipboard-write"],
        )
        await ctx.add_init_script(
            "try { localStorage.removeItem('idxavg-history-v1'); } catch(e) {}"
        )
        page = await ctx.new_page()
        await page.goto(args.base_url, wait_until="domcontentloaded")
        await settle(page)

        # 1. Compute a result -> creates 1 history entry.
        await fill_and_calc(page)
        baseline_inputs = await read_inputs(page)
        baseline_card = await page.locator(CARD_SEL).first.evaluate("el => el.outerHTML")

        # 2. Open history dialog.
        await page.locator("body").click()
        await page.wait_for_timeout(100)
        await page.keyboard.press("Alt+KeyH")
        try:
            await page.locator(DIALOG_SEL).first.wait_for(state="visible", timeout=2000)
        except Exception:
            failures.append("[open] Alt+H did not open history dialog")
            print("FAIL"); return 1

        # 3. Locate per-entry Copy button. aria-label pattern: "<Copy>: Rp ..."
        copy_btn = page.locator(
            f'{DIALOG_SEL} button[aria-label^="Copy:"], {DIALOG_SEL} button[aria-label^="Salin:"]'
        ).first
        if await copy_btn.count() == 0:
            failures.append("[find] per-entry copy button not found in dialog")
            print("FAIL"); return 1

        label = await copy_btn.get_attribute("aria-label")
        if not label or not re.search(r"Rp\s*[\d.]+", label):
            failures.append(f"[a11y] copy button aria-label missing Rp value: {label!r}")
        else:
            notes.append(f"[a11y] copy button labelled '{label}'")

        # 4. Click and validate clipboard + toast.
        await copy_btn.click()
        await page.wait_for_timeout(400)

        clip = await page.evaluate("() => navigator.clipboard.readText()")
        for token in ("New Avg", "Ringkasan", "Rp"):
            pass  # placeholder — we check specific tokens below

        # Expected structural tokens (locale-agnostic: match either language).
        expected_tokens = [
            ("head",   [r"New Avg:", r"Avg Baru:"]),
            ("trend",  [r"[↑↓→]\s*\d+\.\d{2}%"]),
            ("newlot", [r"New Lots:", r"Lot Baru:"]),
            ("total",  [r"Total Capital:", r"Total Modal:"]),
            ("rupiah", [r"Rp\s*[\d.]+"]),
        ]
        for name, patterns in expected_tokens:
            if not any(re.search(p, clip) for p in patterns):
                failures.append(
                    f"[clipboard] missing {name}: none of {patterns} in {clip!r}"
                )
        if not failures:
            notes.append(f"[clipboard] contains expected summary tokens ({len(clip)} chars)")

        # Accessible feedback: Sonner mounts toasts inside a
        # <section aria-live="polite" aria-label="Notifications ..."> region;
        # each toast is a <li data-sonner-toast data-type="success">.
        region = page.locator('section[aria-live][aria-label*="Notifications"]').first
        try:
            await region.wait_for(state="attached", timeout=2000)
            live = await region.get_attribute("aria-live")
            if live not in ("polite", "assertive"):
                failures.append(f"[a11y-toast] region aria-live={live!r}")
            else:
                notes.append(f"[a11y-toast] toast region aria-live={live}")

            toast_li = region.locator(
                'li[data-sonner-toast]:has-text("Summary copied"), '
                'li[data-sonner-toast]:has-text("Ringkasan disalin")'
            ).first
            await toast_li.wait_for(state="visible", timeout=2000)
            dtype = await toast_li.get_attribute("data-type")
            if dtype != "success":
                failures.append(f"[a11y-toast] toast data-type={dtype!r}, want 'success'")
            else:
                notes.append("[a11y-toast] success toast visible inside live region")
            await page.screenshot(path=str(SHOTS / "1_toast.png"))
        except Exception as e:
            failures.append(f"[a11y-toast] no accessible 'copied' toast appeared: {e}")
            await page.screenshot(path=str(SHOTS / "1_no_toast.png"))

        # 5. Dialog stays open; form + card unchanged.
        if not await page.locator(DIALOG_SEL).first.is_visible():
            failures.append("[side-effect] dialog closed after copy click")
        else:
            notes.append("[side-effect] dialog remains open")

        # Close dialog to compare card cleanly.
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(300)

        after_inputs = await read_inputs(page)
        if after_inputs != baseline_inputs:
            failures.append(
                f"[side-effect] form inputs changed: {baseline_inputs} → {after_inputs}"
            )
        after_card = await page.locator(CARD_SEL).first.evaluate("el => el.outerHTML")
        if after_card != baseline_card:
            failures.append("[side-effect] result card outerHTML changed after copy")
        else:
            notes.append("[side-effect] form and result card unchanged")

        await browser.close()

    print("\n--- history copy entry ---")
    for n in notes:
        print(f"  ok  {n}")
    for f in failures:
        print(f"  FAIL {f}")
    print(f"\n{'PASS' if not failures else 'FAIL'} — {len(failures)} failure(s)")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
