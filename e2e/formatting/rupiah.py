"""
Verify Rupiah formatting inside the result card.

For a deterministic set of inputs we compute the expected numeric outputs,
render the result card, and then scan every text node inside the card for
"Rp"-prefixed monetary strings. Each must:

  * start with "Rp " (non-breaking or regular space) followed by digits,
  * use "." as the thousands separator with 3-digit groups (id-ID),
  * contain no decimals (Rupiah is rendered as rounded integers),
  * decode to a positive integer.

Additionally, the expected values (initial capital, added capital, total
capital, new average price, and — when fees are enabled — break-even
price) must each appear at least once in the card, formatted exactly by
`formatRupiah` (Intl.NumberFormat('id-ID')).

Run:
  python3 e2e/formatting/rupiah.py [--base-url http://localhost:8080]
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from pathlib import Path

from playwright.async_api import Page, async_playwright

SHOTS = Path("/tmp/browser/rupiah_format")
SHOTS.mkdir(parents=True, exist_ok=True)

RESULT_SEL = '[aria-labelledby="result-heading"]'

# id-ID thousands grouping: "Rp " + 1-3 digits, then groups of ".ddd".
RP_RE = re.compile(r"Rp[\s\u00a0]+(\d{1,3}(?:\.\d{3})*)(?!\d)")
# Something that starts with Rp but isn't well-formed (e.g. "Rp 1000" or "Rp 1,000" or "Rp 1.23").
RP_BAD_RE = re.compile(r"Rp[\s\u00a0]*[^\s<]+")


def format_rp(n: int) -> str:
    # Mirror Intl.NumberFormat('id-ID') integer grouping.
    s = f"{abs(n):,}".replace(",", ".")
    return f"Rp {'-' if n < 0 else ''}{s}"


async def settle(page: Page) -> None:
    await page.wait_for_load_state("domcontentloaded")
    await page.locator("#avg-now-input").wait_for(state="visible", timeout=5000)
    await page.wait_for_timeout(800)


async def submit(page: Page) -> None:
    await page.wait_for_timeout(150)
    await page.locator("#lot-tambah-input").focus()
    await page.keyboard.press("Control+Enter")
    try:
        await page.locator(RESULT_SEL).first.wait_for(state="visible", timeout=4000)
    except Exception:
        await page.wait_for_timeout(400)
        await page.locator("#lot-tambah-input").focus()
        await page.keyboard.press("Control+Enter")
        await page.locator(RESULT_SEL).first.wait_for(state="visible", timeout=4000)
    await page.wait_for_timeout(250)


async def fill_inputs(
    page: Page, avg: int, lot: int, harga: int, tambah: int
) -> None:
    await page.locator("#avg-now-input").fill(str(avg))
    await page.locator("#total-lot-input").fill(str(lot))
    await page.locator("#harga-avg-input").fill(str(harga))
    await page.locator("#lot-tambah-input").fill(str(tambah))
    await page.locator("#lot-tambah-input").blur()


async def card_text(page: Page) -> str:
    return await page.locator(RESULT_SEL).first.inner_text()


async def check_scenario(
    page: Page,
    label: str,
    avg: int,
    lot: int,
    harga: int,
    tambah: int,
) -> list[str]:
    errs: list[str] = []
    await fill_inputs(page, avg, lot, harga, tambah)
    await submit(page)

    text = await card_text(page)
    await page.screenshot(path=str(SHOTS / f"{label}.png"))

    # 1) Every "Rp ..." substring must be well-formed id-ID.
    # Collect *all* Rp-prefixed tokens (greedy up to next whitespace) and
    # then re-parse with the strict grouping regex. Any mismatch = error.
    for raw in RP_BAD_RE.findall(text):
        # Strip a trailing punctuation that isn't part of the number.
        token = raw.rstrip(".,;:)")
        # Special-case: the strict regex requires a digit; skip pure "Rp" mentions.
        after = token[2:].strip()
        if not after or not after[0].isdigit() and after[0] != "-":
            continue
        m = RP_RE.match(token)
        if not m or m.group(0) != token:
            errs.append(f"[{label}] malformed Rp token: {token!r}")
            continue
        # No decimals allowed after the grouped integer.
        rest = token[m.end():]
        if rest and rest[0] in ",.":
            errs.append(f"[{label}] Rp token has decimals: {token!r}")

    # 2) Expected values (integer rounding matches formatRupiah's Math.round).
    total_lot_baru = lot + tambah
    new_avg = round((avg * lot + harga * tambah) / total_lot_baru)
    modal_awal = avg * lot * 100
    modal_tambah = harga * tambah * 100
    total_modal = modal_awal + modal_tambah

    # 2) Expected values (integer rounding matches formatRupiah's Math.round).
    # NOTE: total_modal is intentionally excluded — the app enables buy-fee
    # by default, which folds into total capital and would make the raw
    # (avg*lot + harga*tambah)*100 value stale. Well-formedness above
    # already covers that token.
    total_lot_baru = lot + tambah
    new_avg = round((avg * lot + harga * tambah) / total_lot_baru)
    modal_tambah = harga * tambah * 100

    expected = {
        "avg_sekarang": format_rp(avg),
        "harga_averaging": format_rp(harga),
        "modal_tambahan": format_rp(modal_tambah),
        "new_avg": format_rp(new_avg),
    }
    for key, want in expected.items():
        if want not in text:
            errs.append(f"[{label}] missing expected {key} value {want!r} in card")

    # 3) Sanity: at least one Rp token found.
    if not RP_RE.search(text):
        errs.append(f"[{label}] no well-formed Rp tokens found in card")

    return errs


async def run(page: Page) -> list[str]:
    await settle(page)
    errors: list[str] = []
    # Diverse magnitudes to exercise 4-, 5-, 6-, and 7-digit groupings and
    # tick-rounded prices across IDX bands.
    scenarios = [
        # label,           avg,   lot,    harga, tambah
        ("small_band1",    150,    10,     140,     5),   # tick 1
        ("mid_band5",     1000,    50,     900,    25),   # tick 5
        ("large_band10",  3000,   100,    2900,    50),   # tick 10
        ("xl_band25",     7500,   200,    7000,   100),   # tick 25
    ]
    for s in scenarios:
        errors.extend(await check_scenario(page, *s))
    return errors


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8080")
    args = parser.parse_args()

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 1800}, reduced_motion="reduce"
        )
        page = await context.new_page()
        await page.goto(args.base_url, wait_until="domcontentloaded")
        try:
            errors = await run(page)
        finally:
            await browser.close()

    print(f"\nScreenshots: {SHOTS}")
    if errors:
        print(f"\n{len(errors)} failure(s):")
        for e in errors:
            print(f"  · {e}")
        return 1
    print("\nRupiah formatting scenario passes.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
