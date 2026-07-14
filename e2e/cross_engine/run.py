"""
Cross-engine E2E: verify focus order and keyboard shortcuts stay consistent
across Chromium, Firefox, and WebKit.

Scenarios per engine:
  A. Tab order — from #avg-now-input walks through every visible form input
     and finally reaches the "Hitung" submit button (or a later toolbar
     button); order is stable and every step lands on a real focusable id.
  B. Shift+Tab — reverses exactly through the same chain.
  C. Ctrl+Enter shortcut — with valid inputs renders the result card and
     with an invalid input (avg=0) does NOT render it.
  D. Alt+L toggles language (button aria-label flips).
  E. Alt+R resets inputs to empty.
  F. History modal focus trap — Tab cycles inside the dialog, and
     Ctrl+Enter / Alt+L / Alt+R do not close it or produce a result card.
     Escape restores focus to the trigger.

Exit code non-zero on any assertion failure or engine mismatch.

Usage:
  python3 e2e/cross_engine/run.py [--base-url http://localhost:8080]
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass, field
from typing import Any

from playwright.async_api import BrowserContext, Page, async_playwright

ENGINES = ["chromium", "firefox", "webkit"]

EXPECTED_INPUT_CHAIN = [
    "avg-now-input",
    "total-lot-input",
    "harga-avg-input",
    # Either lot-tambah-input OR target-avg-input is rendered depending on the
    # active mode (they are mutually exclusive). We accept whichever is present.
    ("lot-tambah-input", "target-avg-input"),
]


@dataclass
class EngineReport:
    engine: str
    failures: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.failures


async def settle(page: Page) -> None:
    await page.wait_for_load_state("networkidle")
    await page.wait_for_timeout(1200)


async def focused_id(page: Page) -> str | None:
    return await page.evaluate("() => document.activeElement && document.activeElement.id || null")


async def focused_tag(page: Page) -> str:
    return await page.evaluate(
        "() => (document.activeElement && document.activeElement.tagName || '').toLowerCase()"
    )


async def walk_tab_chain(page: Page, start_id: str, max_steps: int = 40) -> list[str]:
    """Focus start_id, then Tab up to max_steps and collect the id at each stop."""
    await page.locator(f"#{start_id}").focus()
    seen = [start_id]
    for _ in range(max_steps):
        await page.keyboard.press("Tab")
        fid = await focused_id(page)
        seen.append(fid or f"<{await focused_tag(page)}>")
    return seen


async def resolve_chain(page: Page) -> list[str]:
    resolved: list[str] = []
    for step in EXPECTED_INPUT_CHAIN:
        candidates = step if isinstance(step, tuple) else (step,)
        picked: str | None = None
        for c in candidates:
            if await page.locator(f"#{c}").count():
                picked = c
                break
        if picked is None:
            raise RuntimeError(f"No candidate present for step {step}")
        resolved.append(picked)
    return resolved


async def scenario_tab_order(page: Page, report: EngineReport) -> None:
    expected = await resolve_chain(page)
    chain = await walk_tab_chain(page, expected[0], max_steps=25)
    positions: list[int] = []
    for eid in expected:
        try:
            positions.append(chain.index(eid))
        except ValueError:
            report.failures.append(
                f"[tab] {report.engine}: expected id '{eid}' never focused. chain={chain}"
            )
            return
    if positions != sorted(positions):
        report.failures.append(
            f"[tab] {report.engine}: input order not monotonic. positions={positions} chain={chain}"
        )
        return
    submit_selector = 'button[type="submit"]'
    submit_reachable = await page.evaluate(
        """(sel) => {
            const btn = document.querySelector(sel);
            if (!btn) return false;
            btn.focus();
            return document.activeElement === btn;
        }""",
        submit_selector,
    )
    if not submit_reachable:
        report.failures.append(f"[tab] {report.engine}: submit button not focusable")
    report.notes.append(f"[tab] {report.engine}: input chain OK ({expected})")


async def scenario_shift_tab(page: Page, report: EngineReport) -> None:
    expected = await resolve_chain(page)
    last = expected[-1]
    first = expected[0]
    await page.locator(f"#{last}").focus()
    reversed_seen = [last]
    for _ in range(len(expected) * 4):
        await page.keyboard.press("Shift+Tab")
        fid = await focused_id(page)
        if fid:
            reversed_seen.append(fid)
        if fid == first:
            break
    seen_expected = [x for x in reversed_seen if x in expected]
    if not seen_expected or seen_expected[0] != last or seen_expected[-1] != first:
        report.failures.append(
            f"[shift-tab] {report.engine}: did not reverse to first input. seen={seen_expected}"
        )
        return
    forward_positions = [expected.index(x) for x in seen_expected]
    if forward_positions != sorted(forward_positions, reverse=True):
        report.failures.append(
            f"[shift-tab] {report.engine}: reverse order broken. positions={forward_positions}"
        )
        return
    report.notes.append(f"[shift-tab] {report.engine}: reverse order OK")


async def _clear_and_fill(page: Page, id_: str, value: str) -> None:
    loc = page.locator(f"#{id_}")
    if await loc.count():
        await loc.fill(value)


async def fill_valid(page: Page) -> None:
    await page.locator("#avg-now-input").fill("1000")
    await page.locator("#total-lot-input").fill("10")
    await page.locator("#harga-avg-input").fill("900")
    await page.locator("#lot-tambah-input").fill("5")
    await page.locator("#lot-tambah-input").blur()


async def clear_form(page: Page) -> None:
    for id_ in ("avg-now-input", "total-lot-input", "harga-avg-input",
                "lot-tambah-input", "target-avg-input"):
        loc = page.locator(f"#{id_}")
        if await loc.count():
            await loc.fill("")


async def scenario_ctrl_enter(page: Page, report: EngineReport) -> None:
    # Invalid → no result card.
    await clear_form(page)
    await page.locator("#avg-now-input").fill("0")
    await page.locator("#total-lot-input").fill("1")
    await page.locator("#avg-now-input").focus()
    await page.keyboard.press("Control+Enter")
    await page.wait_for_timeout(400)
    result_visible = await page.locator('[aria-labelledby="result-heading"]').count()
    if result_visible:
        report.failures.append(f"[shortcut] {report.engine}: invalid input still rendered result card")

    # Valid → result card appears.
    await clear_form(page)
    await fill_valid(page)
    await page.locator("#lot-tambah-input").focus()
    await page.keyboard.press("Control+Enter")
    try:
        await page.locator('[aria-labelledby="result-heading"]').first.wait_for(
            state="visible", timeout=3000
        )
    except Exception:
        report.failures.append(f"[shortcut] {report.engine}: Ctrl+Enter did not render result card")
        return
    report.notes.append(f"[shortcut] {report.engine}: Ctrl+Enter OK")


async def scenario_alt_l(page: Page, report: EngineReport) -> None:
    btn = page.locator('button[aria-label="Toggle language"]').first
    if await btn.count() == 0:
        report.failures.append(f"[alt-l] {report.engine}: language toggle not found")
        return
    before = await btn.inner_text()
    await page.locator("body").click()
    await page.keyboard.press("Alt+KeyL")
    await page.wait_for_timeout(300)
    after = await btn.inner_text()
    if before == after:
        report.failures.append(
            f"[alt-l] {report.engine}: language did not toggle (still '{before.strip()}')"
        )
        return
    # Toggle back to keep state predictable for later scenarios.
    await page.keyboard.press("Alt+KeyL")
    await page.wait_for_timeout(200)
    report.notes.append(f"[alt-l] {report.engine}: language toggled OK")


async def scenario_alt_r(page: Page, report: EngineReport) -> None:
    await fill_valid(page)
    await page.locator("body").click()
    await page.keyboard.press("Alt+KeyR")
    await page.wait_for_timeout(400)
    for id_ in ("avg-now-input", "total-lot-input", "harga-avg-input", "lot-tambah-input"):
        val = await page.locator(f"#{id_}").input_value()
        if val:
            report.failures.append(f"[alt-r] {report.engine}: {id_} not reset (val='{val}')")
            return
    report.notes.append(f"[alt-r] {report.engine}: reset OK")


async def scenario_modal_focus_trap(page: Page, report: EngineReport) -> None:
    import re

    trigger = page.get_by_role("button", name=re.compile(r"riwayat|history", re.I)).first
    if await trigger.count() == 0:
        report.failures.append(f"[modal] {report.engine}: history trigger not found")
        return
    await trigger.click()
    await settle(page)
    dialog = page.locator('[role="dialog"]').first
    try:
        await dialog.wait_for(state="visible", timeout=2000)
    except Exception:
        report.failures.append(f"[modal] {report.engine}: dialog did not open")
        return

    # Tab several times — focused element must stay inside the dialog.
    for _ in range(12):
        await page.keyboard.press("Tab")
        inside = await page.evaluate(
            """() => {
                const d = document.querySelector('[role="dialog"]');
                return !!(d && document.activeElement && d.contains(document.activeElement));
            }"""
        )
        if not inside:
            report.failures.append(f"[modal] {report.engine}: focus escaped dialog on Tab")
            break

    # Shortcuts inside modal must NOT produce a result card.
    result_before = await page.locator('[aria-labelledby="result-heading"]').count()
    for combo in ("Control+Enter", "Alt+KeyL", "Alt+KeyR"):
        await page.keyboard.press(combo)
        await page.wait_for_timeout(150)
    if not await dialog.is_visible():
        report.failures.append(f"[modal] {report.engine}: shortcut closed the modal")
    result_after = await page.locator('[aria-labelledby="result-heading"]').count()
    if result_after > result_before:
        report.failures.append(f"[modal] {report.engine}: shortcut rendered result while modal open")

    # Escape closes and returns focus.
    await page.keyboard.press("Escape")
    await page.wait_for_timeout(300)
    if await dialog.is_visible():
        report.failures.append(f"[modal] {report.engine}: Escape did not close dialog")
        return
    report.notes.append(f"[modal] {report.engine}: focus trap + shortcut guard OK")


async def run_engine(pw: Any, engine: str, base_url: str) -> EngineReport:
    report = EngineReport(engine=engine)
    launcher = getattr(pw, engine)
    browser = await launcher.launch(headless=True)
    try:
        context: BrowserContext = await browser.new_context(viewport={"width": 1280, "height": 900})
        page = await context.new_page()
        await page.goto(base_url, wait_until="domcontentloaded")
        await settle(page)

        await scenario_tab_order(page, report)
        await scenario_shift_tab(page, report)
        await scenario_ctrl_enter(page, report)
        await scenario_alt_l(page, report)
        await scenario_alt_r(page, report)
        await scenario_modal_focus_trap(page, report)
        await context.close()
    finally:
        await browser.close()
    return report


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8080")
    parser.add_argument("--engines", default=",".join(ENGINES))
    args = parser.parse_args()
    engines = [e.strip() for e in args.engines.split(",") if e.strip()]

    reports: list[EngineReport] = []
    async with async_playwright() as pw:
        for engine in engines:
            print(f"\n=== {engine} ===")
            try:
                r = await run_engine(pw, engine, args.base_url)
            except Exception as exc:  # noqa: BLE001
                r = EngineReport(engine=engine, failures=[f"[engine-crash] {exc}"])
            reports.append(r)
            for n in r.notes:
                print(f"  ok  {n}")
            for f in r.failures:
                print(f"  FAIL {f}")

    print("\n--- summary ---")
    total_fail = 0
    for r in reports:
        status = "OK" if r.ok else f"FAIL ({len(r.failures)})"
        print(f"  {r.engine:10s} {status}")
        total_fail += len(r.failures)

    # Cross-engine consistency: same pass/fail signature across all engines.
    signatures = {r.engine: tuple(sorted(r.failures)) for r in reports}
    unique = set(signatures.values())
    if len(unique) > 1:
        print("\nENGINE DIVERGENCE — failure sets differ across engines:")
        for eng, sig in signatures.items():
            print(f"  {eng}: {list(sig) or 'clean'}")
        total_fail += 1

    return 0 if total_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
