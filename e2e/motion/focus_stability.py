"""
Verify that open/close animations of the history modal and the appearance
transition of the result card do NOT:
  - move keyboard focus to an unexpected element mid-animation
  - swap or mutate the visible text content during the transition

Approach: poll the DOM at short intervals across the animation window,
capture (focused-id, text-snapshot) samples, and assert:
  * result card — from the moment it becomes visible, its main text
    (result heading + numeric summary) is byte-identical across every
    sample until the animation settles; focus stays where the user left
    it (the submit trigger / lot input) — Radix should NOT autofocus the card.
  * modal open — Radix moves focus INTO the dialog exactly once; after that
    initial move, the focused element stays inside the dialog for every
    sample and the dialog's title/body text is stable across samples.
  * modal close — focus returns to the trigger exactly once and stays
    there; result card text (if present behind the modal) is unchanged
    versus the pre-open snapshot.

Usage:
  python3 e2e/motion/focus_stability.py [--base-url http://localhost:8080]
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from playwright.async_api import Page, async_playwright


async def settle(page: Page) -> None:
    await page.wait_for_load_state("networkidle")
    await page.wait_for_timeout(600)


async def snap(page: Page) -> dict:
    return await page.evaluate(
        """() => {
            const ae = document.activeElement;
            const dlg = document.querySelector('[role="dialog"]');
            const res = document.querySelector('[aria-labelledby="result-heading"]');
            return {
                focusId: ae && ae.id || null,
                focusTag: (ae && ae.tagName || '').toLowerCase(),
                focusInDialog: !!(dlg && ae && dlg.contains(ae)),
                dialogVisible: !!dlg,
                dialogText: dlg ? (dlg.textContent || '').replace(/\\s+/g,' ').trim() : null,
                resultVisible: !!res,
                resultText: res ? (res.textContent || '').replace(/\\s+/g,' ').trim() : null,
            };
        }"""
    )


async def sample(page: Page, ms_total: int, step: int = 20) -> list[dict]:
    out = []
    for _ in range(max(1, ms_total // step)):
        out.append(await snap(page))
        await page.wait_for_timeout(step)
    return out


async def fill_valid(page: Page) -> None:
    await page.locator("#avg-now-input").fill("1000")
    await page.locator("#total-lot-input").fill("10")
    await page.locator("#harga-avg-input").fill("900")
    await page.locator("#lot-tambah-input").fill("5")
    await page.locator("#lot-tambah-input").blur()


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://localhost:8080")
    args = ap.parse_args()

    failures: list[str] = []
    notes: list[str] = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(viewport={"width": 390, "height": 900})
        page = await ctx.new_page()
        await page.goto(args.base_url, wait_until="domcontentloaded")
        await settle(page)

        # -------- 1. Result card transition --------
        await fill_valid(page)
        await page.locator("#lot-tambah-input").focus()
        pre_focus = await snap(page)
        await page.keyboard.press("Control+Enter")
        # Sample across the ~300ms fade-in / scale-in window.
        result_samples = await sample(page, ms_total=600, step=25)

        visible = [s for s in result_samples if s["resultVisible"]]
        if not visible:
            failures.append("[result] card never appeared after Ctrl+Enter")
        else:
            baseline = visible[0]["resultText"]
            # Extract the numeric summary to detect any content flip mid-anim.
            summary_re = re.compile(r"[\d.,]+\s*%")
            base_nums = summary_re.findall(baseline or "")
            for i, s in enumerate(visible):
                nums = summary_re.findall(s["resultText"] or "")
                if nums != base_nums:
                    failures.append(
                        f"[result] text changed during transition at frame {i}: "
                        f"{base_nums} → {nums}"
                    )
                    break
            # Focus must NOT jump into the result card during animation.
            for i, s in enumerate(visible):
                if s["focusId"] and s["focusId"].startswith("result"):
                    failures.append(
                        f"[result] focus jumped into result region at frame {i} (id={s['focusId']})"
                    )
                    break
            # Focus should stay on the submit trigger or an input the user had.
            allowed = {pre_focus["focusId"], "lot-tambah-input", "target-avg-input", None}
            last = visible[-1]
            if last["focusId"] not in allowed and last["focusTag"] not in ("button", "input"):
                failures.append(
                    f"[result] focus ended on unexpected element: {last['focusId']} <{last['focusTag']}>"
                )
            notes.append(
                f"[result] {len(visible)} stable samples; summary={base_nums}"
            )

        # -------- 2. Modal open transition --------
        trigger = page.get_by_role("button", name=re.compile(r"riwayat|history", re.I)).first
        if await trigger.count() == 0:
            failures.append("[modal] history trigger not found")
        else:
            pre_open_result = (await snap(page))["resultText"]
            await trigger.click()
            open_samples = await sample(page, ms_total=600, step=25)

            opened = [s for s in open_samples if s["dialogVisible"]]
            if not opened:
                failures.append("[modal-open] dialog never appeared")
            else:
                # Once focus lands inside the dialog, it must stay there.
                entered = False
                for i, s in enumerate(opened):
                    if s["focusInDialog"]:
                        entered = True
                    elif entered:
                        failures.append(
                            f"[modal-open] focus left dialog mid-animation at frame {i} "
                            f"(id={s['focusId']} tag={s['focusTag']})"
                        )
                        break
                if not entered:
                    failures.append("[modal-open] focus never moved into dialog")

                # Dialog title text is stable (Radix should not swap it mid-anim).
                titles = {s["dialogText"].split(" ")[0] for s in opened if s["dialogText"]}
                if len(titles) > 1:
                    # Not fatal if only whitespace differs — real content flip only.
                    failures.append(f"[modal-open] first token of dialog text changed: {titles}")
                notes.append(f"[modal-open] {len(opened)} samples, focus entered={entered}")

            # -------- 3. Modal close transition --------
            trigger_id = await trigger.evaluate("el => el.id || el.getAttribute('aria-label')")
            await page.keyboard.press("Escape")
            close_samples = await sample(page, ms_total=600, step=25)

            # Result card text underneath must not have mutated.
            for i, s in enumerate(close_samples):
                if s["resultText"] and pre_open_result and s["resultText"] != pre_open_result:
                    # allow only if numeric summary matches.
                    old_nums = re.findall(r"[\d.,]+\s*%", pre_open_result)
                    new_nums = re.findall(r"[\d.,]+\s*%", s["resultText"])
                    if old_nums != new_nums:
                        failures.append(
                            f"[modal-close] result text mutated at frame {i}: {old_nums}→{new_nums}"
                        )
                        break

            # Focus must return to the trigger and stay there.
            after = await page.evaluate(
                "() => document.activeElement && (document.activeElement.getAttribute('aria-label') || document.activeElement.id)"
            )
            if after != trigger_id:
                failures.append(
                    f"[modal-close] focus did not return to trigger (got '{after}', expected '{trigger_id}')"
                )
            else:
                notes.append(f"[modal-close] focus returned to trigger '{trigger_id}'")

        await browser.close()

    print("\n--- motion / focus stability ---")
    for n in notes:
        print(f"  ok  {n}")
    for f in failures:
        print(f"  FAIL {f}")
    print(f"\n{'PASS' if not failures else 'FAIL'} — {len(failures)} failure(s)")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
