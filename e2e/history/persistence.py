"""
E2E: verify calculation history is persisted to localStorage across reloads
and that it renders in insertion order (newest first), capped at the last
10 entries.

Scenarios:
  A. Seed 12 entries directly into localStorage under key "idxavg-history-v1",
     reload the page, open the History dialog:
       - assert exactly 10 entries are rendered
       - assert they correspond to the 10 newest seeded entries, in
         newest-first order (matches Array.slice(0, 10) of the seed).
       - assert the persisted localStorage array itself gets trimmed to 10
         after the first save action (a subsequent compute persists a slice
         of length 10).
  B. Real user flow: clear storage, fill inputs, Ctrl+Enter to compute one
     entry, reload page, open history: the computed entry survives with the
     expected new-avg value.

Usage:
  python3 e2e/history/persistence.py [--base-url http://localhost:8080]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

from playwright.async_api import Page, async_playwright

SHOTS = Path(__file__).parent / "screenshots"
SHOTS.mkdir(parents=True, exist_ok=True)

HISTORY_KEY = "idxavg-history-v1"
DIALOG_SEL = '[role="dialog"]'


def make_entry(i: int) -> dict:
    """Deterministic valid CalcResult; newAvgPrice encodes the index so we
    can assert ordering by reading the rendered rows."""
    new_avg = 1000 + i  # unique per entry, small enough to stay readable
    return {
        "id": f"seed-{i}",
        "timestamp": 1_700_000_000_000 + i * 1000,
        "avgSekarang": 2000,
        "lotSekarang": 10,
        "hargaAvg": 1500,
        "lotTambah": 5,
        "newAvgPrice": new_avg,
        "totalLotBaru": 15,
        "lotDelta": 5,
        "totalModal": new_avg * 15 * 100,
        "status": "down",
        "percentage": 12.5,
    }


async def open_history(page: Page) -> None:
    btn = page.locator('button[title="Alt+H"]').first
    await btn.wait_for(state="visible", timeout=5000)
    await page.screenshot(path=str(SHOTS / "debug_before_click.png"))
    await btn.click()
    await page.wait_for_timeout(500)
    await page.screenshot(path=str(SHOTS / "debug_after_click.png"))
    await page.locator(DIALOG_SEL).wait_for(state="visible", timeout=5000)
    await page.wait_for_timeout(200)





async def read_rendered_new_avgs(page: Page) -> list[int]:
    """Extract the newAvgPrice from each rendered history row by reading the
    'Rp X → Rp Y' span inside each row's load button. Locale-agnostic."""
    spans = await page.locator(f'{DIALOG_SEL} span:has-text("→")').all()
    out: list[int] = []
    for s in spans:
        text = (await s.inner_text()).strip()
        # "Rp 2.000 → Rp 1.011"  → take part after arrow
        if "→" not in text:
            continue
        right = text.split("→", 1)[1]
        digits = "".join(ch for ch in right if ch.isdigit())
        if digits:
            out.append(int(digits))
    return out



async def scenario_seed(page: Page, base_url: str) -> None:
    # Seed 12 entries in newest-first order (index 11 = newest)
    seed = [make_entry(i) for i in range(11, -1, -1)]  # 11,10,...,0
    expected_top10 = [e["newAvgPrice"] for e in seed[:10]]

    await page.goto(base_url, wait_until="domcontentloaded")
    await page.evaluate(
        "([k, v]) => localStorage.setItem(k, v)",
        [HISTORY_KEY, json.dumps(seed)],
    )
    await page.reload(wait_until="domcontentloaded")
    await page.wait_for_timeout(300)

    await open_history(page)
    await page.screenshot(path=str(SHOTS / "seed_open.png"))

    rendered = await read_rendered_new_avgs(page)
    assert len(rendered) == 10, f"expected 10 rendered rows, got {len(rendered)}: {rendered}"
    assert rendered == expected_top10, (
        f"order mismatch\n  expected: {expected_top10}\n  rendered: {rendered}"
    )

    # Persisted storage may still be 12 until a save happens. Trigger a save
    # by computing once, then assert stored length is exactly 10 and the
    # newest entry is at index 0.
    await page.keyboard.press("Escape")
    await page.locator(DIALOG_SEL).wait_for(state="hidden", timeout=3000)

    for id_, v in [
        ("avg-now-input", "2000"),
        ("total-lot-input", "10"),
        ("harga-avg-input", "1500"),
        ("lot-tambah-input", "7"),
    ]:
        await page.locator(f"#{id_}").fill(v)
    await page.locator("#lot-tambah-input").blur()
    await page.keyboard.press("Control+Enter")
    await page.locator('[aria-labelledby="result-heading"]').first.wait_for(
        state="visible", timeout=5000
    )

    stored_raw = await page.evaluate(
        "(k) => localStorage.getItem(k)", HISTORY_KEY
    )
    stored = json.loads(stored_raw or "[]")
    assert len(stored) == 10, f"expected stored length 10 after save, got {len(stored)}"
    # newest entry is the just-computed one (not one of the seeded ids)
    assert not str(stored[0].get("id", "")).startswith("seed-"), (
        f"newest entry should be the fresh compute, got id={stored[0].get('id')!r}"
    )
    # remaining 9 must be the 9 newest seeded entries in order
    tail_ids = [e["id"] for e in stored[1:]]
    expected_tail = [f"seed-{i}" for i in range(11, 2, -1)]  # 11..3
    assert tail_ids == expected_tail, (
        f"trimmed tail mismatch\n  expected: {expected_tail}\n  got: {tail_ids}"
    )


async def scenario_reload(page: Page, base_url: str) -> None:
    await page.goto(base_url, wait_until="domcontentloaded")
    await page.evaluate("() => localStorage.removeItem('idxavg-history-v1')")
    await page.reload(wait_until="domcontentloaded")
    await page.wait_for_timeout(200)

    for id_, v in [
        ("avg-now-input", "2000"),
        ("total-lot-input", "10"),
        ("harga-avg-input", "1500"),
        ("lot-tambah-input", "10"),
    ]:
        await page.locator(f"#{id_}").fill(v)
    await page.locator("#lot-tambah-input").blur()
    await page.keyboard.press("Control+Enter")
    await page.locator('[aria-labelledby="result-heading"]').first.wait_for(
        state="visible", timeout=5000
    )

    before_raw = await page.evaluate("(k) => localStorage.getItem(k)", HISTORY_KEY)
    before = json.loads(before_raw or "[]")
    assert len(before) == 1, f"expected 1 entry pre-reload, got {len(before)}"
    expected_new_avg = before[0]["newAvgPrice"]

    await page.reload(wait_until="domcontentloaded")
    await page.wait_for_timeout(300)
    await open_history(page)
    await page.screenshot(path=str(SHOTS / "reload_open.png"))

    rendered = await read_rendered_new_avgs(page)
    assert len(rendered) == 1, f"expected 1 rendered row after reload, got {rendered}"
    assert rendered[0] == round(expected_new_avg), (
        f"persisted entry mismatch: expected ~{expected_new_avg}, rendered {rendered[0]}"
    )


async def main(base_url: str) -> int:
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        try:
            ctx = await browser.new_context(viewport={"width": 390, "height": 1800})
            page = await ctx.new_page()
            await scenario_seed(page, base_url)
            await ctx.close()

            ctx = await browser.new_context(viewport={"width": 390, "height": 1800})
            page = await ctx.new_page()
            await scenario_reload(page, base_url)
            await ctx.close()
        finally:
            await browser.close()
    print("OK e2e/history/persistence.py")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://localhost:8080")
    args = ap.parse_args()
    sys.exit(asyncio.run(main(args.base_url)))
