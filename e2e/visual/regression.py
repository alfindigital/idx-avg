"""
Screenshot-based visual regression for the result card and the history modal
across mobile viewports (320, 360, 390, 414).

Model
-----
- Baselines live under e2e/visual/baselines/<viewport>/<surface>.png and are
  committed to the repo. Actuals + diffs are written under
  e2e/visual/artifacts/ (gitignored).
- Compare pixels with a small per-channel tolerance (default 8/255) and a
  small fraction of differing pixels allowed (default 0.20%). Both defaults
  absorb sub-pixel anti-aliasing noise without hiding real UI changes.
- Deterministic inputs and CSS animations are disabled before capture so
  runs are reproducible.
- First run for a surface has no baseline: the actual is copied in and the
  case is reported as `baseline-created` (still exits 0). Use `--update` to
  refresh all baselines intentionally.

Exit code
---------
  0  — every surface within tolerance (or freshly baselined)
  1  — one or more surfaces regressed; see artifacts/ for diff PNGs

Usage
-----
  python3 e2e/visual/regression.py                       # compare
  python3 e2e/visual/regression.py --update              # refresh baselines
  python3 e2e/visual/regression.py --base-url http://localhost:8080
"""

from __future__ import annotations

import argparse
import asyncio
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable

from PIL import Image, ImageChops
from playwright.async_api import Locator, Page, async_playwright

ROOT = Path(__file__).parent
BASELINES = ROOT / "baselines"
ARTIFACTS = ROOT / "artifacts"

VIEWPORTS = [
    {"name": "320w", "width": 320, "height": 780},
    {"name": "360w", "width": 360, "height": 800},
    {"name": "390w", "width": 390, "height": 844},
    {"name": "414w", "width": 414, "height": 896},
]

# Per-channel absolute difference tolerated per pixel (0-255).
PIXEL_TOLERANCE = 8
# Fraction of pixels allowed to exceed PIXEL_TOLERANCE.
MAX_DIFF_RATIO = 0.002  # 0.20%

# CSS injected before capture: disable animations/transitions and hide the
# native caret so the screenshot is stable frame-to-frame.
STABILIZE_CSS = """
    *, *::before, *::after {
        animation-duration: 0s !important;
        animation-delay: 0s !important;
        transition-duration: 0s !important;
        transition-delay: 0s !important;
        caret-color: transparent !important;
    }
    html { scroll-behavior: auto !important; }
"""


@dataclass
class Case:
    viewport: dict
    surface: str
    status: str  # ok | baseline-created | regressed | missing-target | error
    diff_ratio: float = 0.0
    detail: str = ""


async def settle(page: Page) -> None:
    await page.wait_for_load_state("networkidle")
    await page.wait_for_timeout(1200)


async def open_result_card(page: Page) -> Locator | None:
    await page.locator("#avg-now-input").fill("1000")
    await page.locator("#total-lot-input").fill("10")
    await page.locator("#harga-avg-input").fill("900")
    await page.locator("#lot-tambah-input").fill("5")
    await page.locator("#lot-tambah-input").blur()
    await page.keyboard.press("Control+Enter")
    card = page.locator('[aria-labelledby="result-heading"]').first
    try:
        await card.wait_for(state="visible", timeout=3000)
    except Exception:
        return None
    await page.wait_for_timeout(400)
    return card


async def open_history_modal(page: Page) -> Locator | None:
    trigger = page.get_by_role("button", name=re.compile(r"riwayat|history", re.I)).first
    if await trigger.count() == 0:
        return None
    await trigger.click()
    dialog = page.locator('[role="dialog"]').first
    try:
        await dialog.wait_for(state="visible", timeout=2000)
    except Exception:
        return None
    await page.wait_for_timeout(400)
    return dialog


SURFACES: dict[str, Callable[[Page], Awaitable[Locator | None]]] = {
    "result-card": open_result_card,
    "history-modal": open_history_modal,
}


def compare(baseline_path: Path, actual_path: Path, diff_path: Path) -> tuple[float, bool]:
    """Return (diff_ratio, within_tolerance). Writes a diff PNG on regression."""
    a = Image.open(baseline_path).convert("RGB")
    b = Image.open(actual_path).convert("RGB")
    if a.size != b.size:
        # Size change is a regression; write a side-by-side diff.
        w = max(a.size[0], b.size[0])
        h = max(a.size[1], b.size[1])
        canvas = Image.new("RGB", (w * 2 + 10, h), (255, 0, 255))
        canvas.paste(a, (0, 0))
        canvas.paste(b, (w + 10, 0))
        canvas.save(diff_path)
        return (1.0, False)

    diff = ImageChops.difference(a, b)
    # Reduce to a single per-pixel worst-channel value.
    bbox_pixels = list(diff.getdata())
    total = len(bbox_pixels)
    bad = 0
    for r, g, bl in bbox_pixels:
        if max(r, g, bl) > PIXEL_TOLERANCE:
            bad += 1
    ratio = bad / total if total else 0.0
    within = ratio <= MAX_DIFF_RATIO
    if not within:
        # Amplify diff for humans.
        amplified = diff.point(lambda p: min(255, p * 8))
        amplified.save(diff_path)
    return (ratio, within)


async def run_case(
    page: Page,
    viewport: dict,
    surface: str,
    update: bool,
) -> Case:
    baseline_dir = BASELINES / viewport["name"]
    actual_dir = ARTIFACTS / viewport["name"]
    baseline_dir.mkdir(parents=True, exist_ok=True)
    actual_dir.mkdir(parents=True, exist_ok=True)
    baseline_path = baseline_dir / f"{surface}.png"
    actual_path = actual_dir / f"{surface}.actual.png"
    diff_path = actual_dir / f"{surface}.diff.png"

    target = await SURFACES[surface](page)
    if target is None:
        return Case(viewport, surface, "missing-target",
                    detail=f"could not open {surface}")

    try:
        await target.screenshot(path=str(actual_path))
    except Exception as exc:  # noqa: BLE001
        return Case(viewport, surface, "error", detail=str(exc))

    if update or not baseline_path.exists():
        shutil.copyfile(actual_path, baseline_path)
        return Case(viewport, surface,
                    "baseline-created" if not update else "ok",
                    detail=f"baseline written → {baseline_path.relative_to(ROOT.parent.parent)}")

    ratio, within = compare(baseline_path, actual_path, diff_path)
    if within:
        return Case(viewport, surface, "ok", diff_ratio=ratio)
    return Case(
        viewport, surface, "regressed", diff_ratio=ratio,
        detail=f"diff {ratio*100:.3f}% > {MAX_DIFF_RATIO*100:.3f}% "
               f"(see {diff_path.relative_to(ROOT.parent.parent)})",
    )


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8080")
    parser.add_argument("--update", action="store_true",
                        help="Overwrite all baselines with current output.")
    parser.add_argument("--surfaces", default=",".join(SURFACES.keys()))
    args = parser.parse_args()

    surfaces = [s.strip() for s in args.surfaces.split(",") if s.strip()]
    if ARTIFACTS.exists():
        shutil.rmtree(ARTIFACTS)
    ARTIFACTS.mkdir(parents=True)

    cases: list[Case] = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        try:
            for viewport in VIEWPORTS:
                for surface in surfaces:
                    context = await browser.new_context(
                        viewport={"width": viewport["width"], "height": viewport["height"]},
                        device_scale_factor=1,
                        reduced_motion="reduce",
                    )
                    page = await context.new_page()
                    await page.add_init_script(
                        f"window.__stabilize = () => {{"
                        f"  const s = document.createElement('style');"
                        f"  s.textContent = {STABILIZE_CSS!r};"
                        f"  document.head.appendChild(s);"
                        f"}}"
                    )
                    await page.goto(args.base_url, wait_until="domcontentloaded")
                    await page.evaluate("window.__stabilize && window.__stabilize()")
                    await settle(page)
                    case = await run_case(page, viewport, surface, args.update)
                    cases.append(case)
                    await context.close()
        finally:
            await browser.close()

    print()
    fail = 0
    for c in cases:
        tag = f"{c.viewport['name']}/{c.surface}"
        if c.status == "ok":
            print(f"  [ OK  ] {tag}  diff={c.diff_ratio*100:.4f}%")
        elif c.status == "baseline-created":
            print(f"  [BASE ] {tag}  {c.detail}")
        elif c.status == "regressed":
            print(f"  [FAIL ] {tag}  {c.detail}")
            fail += 1
        elif c.status == "missing-target":
            print(f"  [SKIP ] {tag}  {c.detail}")
            fail += 1
        else:
            print(f"  [ERR  ] {tag}  {c.detail}")
            fail += 1
    print(f"\nRegressions: {fail}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
