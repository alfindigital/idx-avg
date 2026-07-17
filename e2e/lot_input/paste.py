"""
Paste behavior for the lot inputs.

Verifies:
  1. Pasting a purely-numeric string yields the same digits in the input.
  2. Pasting mixed garbage (letters, symbols, whitespace, unicode) is
     sanitized to digits only — no non-digit ever renders in `.value`.
  3. Pasting a numeric string that exceeds MAX_LOT flips aria-invalid
     to "true" and shows an inline role="alert" error.
  4. Pasting an empty / non-digit-only string leaves the input empty
     (or unchanged) without crashing, and clears any prior error.
  5. Multiple back-to-back pastes ("fast paste") never move focus away
     from the input during or after the burst.

The test runs the same matrix against `#total-lot-input` and
`#lot-tambah-input`. Paste is dispatched two ways per case to catch
either implementation path:
  - a real ClipboardEvent with DataTransfer (what the browser fires when
    the user hits Cmd/Ctrl+V), and
  - Ctrl+V through the OS clipboard (granted via browser permissions).

Run:
  python3 e2e/lot_input/paste.py [--base-url http://localhost:8080]
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from pathlib import Path

from playwright.async_api import Page, async_playwright

SHOTS = Path("/tmp/browser/lot_paste")
SHOTS.mkdir(parents=True, exist_ok=True)

MAX_LOT = 1_000_000
INPUTS = ("#total-lot-input", "#lot-tambah-input")


async def settle(page: Page) -> None:
    await page.wait_for_load_state("domcontentloaded")
    await page.locator("#avg-now-input").wait_for(state="visible", timeout=5000)
    await page.wait_for_timeout(800)


async def state(page: Page, sel: str) -> dict:
    return await page.evaluate(
        """(sel) => {
            const el = document.querySelector(sel);
            const focused = document.activeElement === el;
            let alert = null;
            const desc = el?.getAttribute('aria-describedby');
            if (desc) {
                for (const id of desc.split(/\\s+/)) {
                    const n = document.getElementById(id);
                    if (n && n.getAttribute('role') === 'alert' && n.textContent.trim()) {
                        alert = n.textContent.trim();
                        break;
                    }
                }
            }
            if (!alert) {
                const near = el?.closest('div')?.querySelector('[role="alert"]');
                if (near && near.textContent.trim()) alert = near.textContent.trim();
            }
            return {
                value: el?.value ?? null,
                ariaInvalid: el?.getAttribute('aria-invalid'),
                focused,
                alert,
                activeTag: (document.activeElement?.tagName || '').toLowerCase(),
                activeId: document.activeElement?.id || null,
            };
        }""",
        sel,
    )


def digits_only(s: str | None) -> str:
    # ASCII digits only — the app strips unicode digits (e.g. Arabic-Indic).
    return re.sub(r"[^0-9]", "", s or "")


async def clear(page: Page, sel: str) -> None:
    loc = page.locator(sel)
    await loc.click()
    await loc.press("Control+A")
    await loc.press("Delete")
    await page.wait_for_timeout(60)


async def paste_via_event(page: Page, sel: str, text: str) -> None:
    """Dispatch a real paste ClipboardEvent with DataTransfer on the input."""
    await page.locator(sel).focus()
    await page.evaluate(
        """({sel, text}) => {
            const el = document.querySelector(sel);
            if (!el) throw new Error('input not found: ' + sel);
            el.focus();
            const dt = new DataTransfer();
            dt.setData('text/plain', text);
            const ev = new ClipboardEvent('paste', {
                clipboardData: dt,
                bubbles: true,
                cancelable: true,
            });
            const dispatched = el.dispatchEvent(ev);
            // If the app doesn't handle the paste event itself, fall back
            // to setting the value the same way a real paste would: insert
            // at the caret via execCommand + input event so React's
            // onChange fires.
            if (dispatched && !ev.defaultPrevented) {
                const setter = Object.getOwnPropertyDescriptor(
                    window.HTMLInputElement.prototype, 'value'
                ).set;
                setter.call(el, (el.value || '') + text);
                el.dispatchEvent(new Event('input', { bubbles: true }));
            }
        }""",
        {"sel": sel, "text": text},
    )
    await page.wait_for_timeout(180)


async def paste_via_clipboard(page: Page, sel: str, text: str) -> None:
    """Write text to the OS clipboard and press Ctrl+V on the input."""
    await page.evaluate("(t) => navigator.clipboard.writeText(t)", text)
    await page.locator(sel).focus()
    await page.keyboard.press("Control+V")
    await page.wait_for_timeout(180)


CASES: list[tuple[str, str, bool, bool]] = [
    # label,                          payload,                        expect_alert, expect_over_max
    ("digits-only",                    "12345",                        False, False),
    ("mixed-garbage",                  "9a9b!9@ 9#$%^&9*()_9+-=",     False, False),
    ("with-newlines-and-unicode",      "1\n2\t3٤5",                    False, False),
    ("over-max-numeric",               str(MAX_LOT + 1),               True,  True),
    ("only-symbols",                   "!!!$$$###",                    False, False),
]


async def run_case(page: Page, sel: str, label: str, payload: str,
                   expect_alert: bool, expect_over_max: bool,
                   mode: str) -> list[str]:
    tag = f"{sel} [{mode}] {label!r}"
    errors: list[str] = []
    await clear(page, sel)

    if mode == "event":
        await paste_via_event(page, sel, payload)
    else:
        await paste_via_clipboard(page, sel, payload)

    s = await state(page, sel)

    # (a) rendered value contains ONLY digits — never a stray char.
    if s["value"] and not re.fullmatch(r"[\d.,\s]*", s["value"] or ""):
        # Allow formatter's thousands separators (dot/comma/space), but
        # after stripping non-digits we get pure digits.
        errors.append(f"{tag}: value has non-numeric chars: {s['value']!r}")
    typed_digits = digits_only(s["value"])
    expected_digits = re.sub(r"\D", "", payload)
    if not expect_over_max and expected_digits and typed_digits != expected_digits:
        errors.append(
            f"{tag}: sanitized digits {typed_digits!r} != expected {expected_digits!r}"
        )
    if not expected_digits and typed_digits:
        errors.append(f"{tag}: input received digits from a non-digit paste: {typed_digits!r}")

    # (b) error state matches expectation.
    if expect_alert:
        if s["ariaInvalid"] != "true":
            errors.append(f"{tag}: aria-invalid={s['ariaInvalid']!r} (want 'true')")
        if not s["alert"]:
            errors.append(f"{tag}: missing inline role=alert error")
    else:
        if s["ariaInvalid"] == "true":
            errors.append(f"{tag}: aria-invalid=true unexpectedly")
        if s["alert"]:
            errors.append(f"{tag}: unexpected inline error: {s['alert']!r}")

    # (c) focus is still on the target input.
    if not s["focused"]:
        errors.append(
            f"{tag}: focus jumped to <{s['activeTag']}#{s['activeId']}> after paste"
        )

    return errors


async def run_fast_burst(page: Page, sel: str) -> list[str]:
    """5 back-to-back pastes with no wait between them."""
    errors: list[str] = []
    await clear(page, sel)
    payloads = ["12", "34", "5x", "!!", "67"]  # last two exercise sanitization
    for p in payloads:
        # No sleep — hammer as fast as the driver allows.
        await page.evaluate(
            """({sel, text}) => {
                const el = document.querySelector(sel);
                el.focus();
                const dt = new DataTransfer();
                dt.setData('text/plain', text);
                const ev = new ClipboardEvent('paste', {
                    clipboardData: dt, bubbles: true, cancelable: true,
                });
                const dispatched = el.dispatchEvent(ev);
                if (dispatched && !ev.defaultPrevented) {
                    const setter = Object.getOwnPropertyDescriptor(
                        window.HTMLInputElement.prototype, 'value'
                    ).set;
                    setter.call(el, (el.value || '') + text);
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                }
            }""",
            {"sel": sel, "text": p},
        )
    await page.wait_for_timeout(300)
    s = await state(page, sel)
    if not s["focused"]:
        errors.append(
            f"fast-burst {sel}: focus escaped mid-burst to "
            f"<{s['activeTag']}#{s['activeId']}>"
        )
    if s["value"] and not re.fullmatch(r"[\d.,\s]*", s["value"]):
        errors.append(f"fast-burst {sel}: value contains non-digits: {s['value']!r}")
    # 12+34+5+67 = 123457 digits (sanitized concatenation).
    if digits_only(s["value"]) != "123457":
        errors.append(
            f"fast-burst {sel}: expected sanitized concat '123457', got "
            f"{digits_only(s['value'])!r}"
        )
    return errors


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8080")
    args = parser.parse_args()

    all_errors: list[str] = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 1800},
            reduced_motion="reduce",
            permissions=["clipboard-read", "clipboard-write"],
        )
        page = await context.new_page()
        await page.goto(args.base_url, wait_until="domcontentloaded")
        await settle(page)

        try:
            for sel in INPUTS:
                for label, payload, expect_alert, expect_over_max in CASES:
                    for mode in ("event", "clipboard"):
                        errs = await run_case(
                            page, sel, label, payload, expect_alert, expect_over_max, mode
                        )
                        all_errors.extend(errs)
                        stamp = f"{sel.strip('#')}_{mode}_{label.replace('-', '_')}"
                        await page.screenshot(path=str(SHOTS / f"{stamp}.png"))
                # Fast burst per input.
                all_errors.extend(await run_fast_burst(page, sel))
                await page.screenshot(path=str(SHOTS / f"{sel.strip('#')}_burst.png"))
        finally:
            await browser.close()

    print(f"\nScreenshots: {SHOTS}")
    if all_errors:
        print(f"\n{len(all_errors)} failure(s):")
        for e in all_errors:
            print(f"  · {e}")
        return 1
    print("\nPaste behavior scenarios pass for all inputs.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
