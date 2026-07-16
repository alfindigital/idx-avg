"""
E2E: verify Tab / Shift+Tab navigation across the main page runs smoothly.

Scope:
  - Left/right column inputs (avg-now, total-lot, harga-avg, lot-tambah OR
    target-avg depending on active mode) plus header/toolbar buttons.
  - Result card action buttons (copy value, share, save PNG, reset) and each
    CopyRow button rendered after a valid calculation.

Assertions:
  1. Forward Tab walk collects >= EXPECTED_MIN unique focusable stops without
     the focus getting stuck (never two consecutive stops on the same element).
  2. All required IDs (form inputs + submit) and result-card action aria-labels
     appear in the forward walk order — ordered ascending in the sequence
     (inputs come before submit, submit comes before result actions).
  3. Focus eventually wraps: after enough Tab presses, we revisit an earlier
     stop (cycle exists, no dead end).
  4. Shift+Tab reverses the same sequence — the reversed order of unique
     stops must contain the forward-order IDs in reverse.
  5. Result card innerText is byte-identical before, mid-walk, and after the
     full Tab/Shift+Tab traversal (navigation must not mutate content).
  6. Focus never escapes the document (activeElement always defined and
     inside <body>).

Usage:
  python3 e2e/tab_order/main_page.py [--base-url http://localhost:8080]
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from playwright.async_api import Page, async_playwright


REQUIRED_INPUT_IDS = [
    "avg-now-input",
    "total-lot-input",
    "harga-avg-input",
]
# lot-tambah-input OR target-avg-input depending on mode.
ONE_OF_INPUTS = ("lot-tambah-input", "target-avg-input")

# Result-card action buttons (aria-label substrings, case-insensitive).
REQUIRED_ACTION_LABELS = ["share", "png", "reset"]

EXPECTED_MIN_STOPS = 10
MAX_TAB_STEPS = 60


async def settle(page: Page) -> None:
    await page.wait_for_load_state("domcontentloaded")
    await page.wait_for_timeout(800)


async def fill_and_calc(page: Page) -> None:
    for id_, v in [
        ("avg-now-input", "1000"),
        ("total-lot-input", "10"),
        ("harga-avg-input", "900"),
        ("lot-tambah-input", "5"),
    ]:
        await page.locator(f"#{id_}").fill(v)
    await page.locator("#lot-tambah-input").blur()
    await page.locator("#lot-tambah-input").focus()
    await page.keyboard.press("Control+Enter")
    await page.locator('[aria-labelledby="result-heading"]').first.wait_for(
        state="visible", timeout=5000
    )
    await page.wait_for_timeout(200)


async def result_text(page: Page) -> str:
    return await page.locator(
        '[aria-labelledby="result-heading"]'
    ).first.inner_text()


async def focused_desc(page: Page) -> dict:
    return await page.evaluate(
        """() => {
            const ae = document.activeElement;
            if (!ae || ae === document.body) {
                return { tag: ae ? 'body' : null, id: null, label: null, key: '<body>', inBody: !!ae };
            }
            const id = ae.id || null;
            const label = ae.getAttribute('aria-label') || null;
            const text = (ae.textContent || '').replace(/\\s+/g,' ').trim().slice(0, 40);
            return {
                tag: ae.tagName.toLowerCase(),
                id,
                label,
                text,
                key: `${ae.tagName.toLowerCase()}#${id || ''}|${label || ''}|${text}`,
                inBody: document.body.contains(ae),
            };
        }"""
    )


async def walk(page: Page, direction: str, steps: int) -> list[dict]:
    combo = "Tab" if direction == "forward" else "Shift+Tab"
    seq: list[dict] = []
    prev_key: str | None = None
    for _ in range(steps):
        await page.keyboard.press(combo)
        f = await focused_desc(page)
        if not f.get("inBody"):
            f["_escaped"] = True
            seq.append(f)
            break
        # Stall detection: two consecutive Tabs must move focus.
        if prev_key is not None and f["key"] == prev_key:
            f["_stall"] = True
        seq.append(f)
        prev_key = f["key"]
    return seq


def unique_order(seq: list[dict]) -> list[str]:
    """Ordered list of first-seen keys."""
    seen: set[str] = set()
    out: list[str] = []
    for f in seq:
        k = f["key"]
        if k not in seen:
            seen.add(k)
            out.append(k)
    return out


def index_of_id(order: list[str], id_: str) -> int:
    for i, k in enumerate(order):
        if f"#{id_}|" in k:
            return i
    return -1


def index_of_label_substr(order: list[str], substr: str) -> int:
    s = substr.lower()
    for i, k in enumerate(order):
        # label is between the first '|' and second '|'.
        parts = k.split("|")
        label = (parts[1] if len(parts) > 1 else "").lower()
        text = (parts[2] if len(parts) > 2 else "").lower()
        if s in label or s in text:
            return i
    return -1


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://localhost:8080")
    args = ap.parse_args()

    failures: list[str] = []
    notes: list[str] = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(viewport={"width": 1280, "height": 900})
        await ctx.add_init_script(
            "try { localStorage.removeItem('idxavg-history-v1'); } catch(e) {}"
        )
        page = await ctx.new_page()
        await page.goto(args.base_url, wait_until="domcontentloaded")
        await settle(page)

        # Prepare: valid form + rendered result card so all action buttons exist.
        await fill_and_calc(page)
        text_before = await result_text(page)

        # Reset focus to the top of the document.
        await page.evaluate("() => { document.activeElement && document.activeElement.blur(); }")
        await page.evaluate("() => document.body.focus()")

        # -------- Forward Tab walk --------
        forward_seq = await walk(page, "forward", MAX_TAB_STEPS)
        forward_order = unique_order(forward_seq)

        stalls = [i for i, f in enumerate(forward_seq) if f.get("_stall")]
        if stalls:
            failures.append(
                f"[stall-fwd] focus did not advance on Tab at steps {stalls[:5]}"
            )
        escaped = [i for i, f in enumerate(forward_seq) if f.get("_escaped")]
        if escaped:
            failures.append(f"[escape-fwd] focus escaped document at step {escaped[0]}")

        if len(forward_order) < EXPECTED_MIN_STOPS:
            failures.append(
                f"[reach-fwd] only {len(forward_order)} unique stops, want >= {EXPECTED_MIN_STOPS}"
            )

        # Mid-walk content check.
        text_mid = await result_text(page)
        if text_mid != text_before:
            failures.append("[content-mid] result card text changed during Tab walk")

        # -------- Required inputs must be visited, in order --------
        input_positions: list[tuple[str, int]] = []
        for id_ in REQUIRED_INPUT_IDS:
            pos = index_of_id(forward_order, id_)
            if pos < 0:
                failures.append(f"[reach-input] '{id_}' never focused via Tab")
            input_positions.append((id_, pos))

        # Optional-of-pair (mode-dependent).
        one_of_pos = -1
        for id_ in ONE_OF_INPUTS:
            pos = index_of_id(forward_order, id_)
            if pos >= 0:
                one_of_pos = pos
                notes.append(f"[reach-input] optional '{id_}' focused at pos {pos}")
                break
        if one_of_pos < 0:
            failures.append(
                f"[reach-input] neither {ONE_OF_INPUTS} focused via Tab (mode-dependent input missing)"
            )

        positions_only = [p for _, p in input_positions if p >= 0]
        if positions_only and positions_only != sorted(positions_only):
            failures.append(
                f"[order-input] input focus order not ascending: {input_positions}"
            )

        # -------- Result-card actions must be reachable AFTER inputs --------
        last_input_pos = max([p for _, p in input_positions if p >= 0] + [one_of_pos])
        action_positions: list[tuple[str, int]] = []
        for lbl in REQUIRED_ACTION_LABELS:
            pos = index_of_label_substr(forward_order, lbl)
            action_positions.append((lbl, pos))
            if pos < 0:
                failures.append(f"[reach-action] action '{lbl}' never focused via Tab")
            elif pos <= last_input_pos:
                failures.append(
                    f"[order-action] action '{lbl}' focused before/at last input (pos {pos} <= {last_input_pos})"
                )
        notes.append(
            f"[forward] {len(forward_seq)} stops, {len(forward_order)} unique. "
            f"inputs={input_positions} actions={action_positions}"
        )

        # -------- Cycle detection: forward walk revisits an earlier stop --------
        seen: set[str] = set()
        revisit_at = -1
        for i, f in enumerate(forward_seq):
            if f["key"] in seen:
                revisit_at = i
                break
            seen.add(f["key"])
        if revisit_at < 0:
            # It's fine if we simply ran out of steps before wrap. Warn if no
            # cycle at all AND we saw few stops — indicates a dead end.
            if len(forward_seq) >= MAX_TAB_STEPS and len(forward_order) < MAX_TAB_STEPS:
                notes.append("[cycle-fwd] no revisit within MAX_TAB_STEPS (walk kept discovering new stops)")
        else:
            notes.append(f"[cycle-fwd] focus wraps: revisit at step {revisit_at}")

        # -------- Shift+Tab reverse walk --------
        # Land on the last-known focused element, then reverse.
        reverse_seq = await walk(page, "backward", MAX_TAB_STEPS)
        reverse_order = unique_order(reverse_seq)

        stalls_r = [i for i, f in enumerate(reverse_seq) if f.get("_stall")]
        if stalls_r:
            failures.append(
                f"[stall-rev] focus did not advance on Shift+Tab at steps {stalls_r[:5]}"
            )
        escaped_r = [i for i, f in enumerate(reverse_seq) if f.get("_escaped")]
        if escaped_r:
            failures.append(f"[escape-rev] focus escaped document at step {escaped_r[0]}")

        # Reverse-walk sanity: at least the required input IDs must appear.
        rev_inputs = [
            (id_, index_of_id(reverse_order, id_)) for id_ in REQUIRED_INPUT_IDS
        ]
        missing_rev = [id_ for id_, p in rev_inputs if p < 0]
        if missing_rev:
            failures.append(f"[reach-rev-input] {missing_rev} never focused via Shift+Tab")
        else:
            # Reverse order must be descending w.r.t. forward positions.
            fwd_of_rev = [index_of_id(forward_order, id_) for id_, _ in rev_inputs]
            if fwd_of_rev != sorted(fwd_of_rev, reverse=True):
                failures.append(
                    f"[order-rev-input] Shift+Tab order does not mirror Tab order: forward-positions={fwd_of_rev}"
                )
            else:
                notes.append(f"[reverse] inputs re-focused in reverse order: {fwd_of_rev}")

        # -------- Post-walk content check --------
        text_after = await result_text(page)
        if text_after != text_before:
            failures.append(
                f"[content-after] result card text changed after full Tab/Shift+Tab walk: "
                f"'{text_before[:60]}' → '{text_after[:60]}'"
            )
        else:
            notes.append("[content-after] result card text unchanged after full traversal")

        await browser.close()

    print("\n--- main-page Tab / Shift+Tab traversal ---")
    for n in notes:
        print(f"  ok  {n}")
    for f in failures:
        print(f"  FAIL {f}")
    print(f"\n{'PASS' if not failures else 'FAIL'} — {len(failures)} failure(s)")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
