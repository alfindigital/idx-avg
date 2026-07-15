"""
Runtime contrast guard for the Averaging Down / Averaging Up badges.

Complements the static token test (src/__tests__/contrast.test.ts) by
measuring the *actually rendered* colors in the browser. Any Tailwind
class swap, wrapper background change, or dark-mode regression that drops
either badge below WCAG AA (4.5:1 for small bold text) fails this test.

For each theme (light + dark) and each status (down + up):
  1. Fill the form to force the target status.
  2. Ctrl+Enter → wait for the result card.
  3. Locate the badge, read getComputedStyle color + rgba background.
  4. Walk parent chain to composite the translucent badge background over
     opaque ancestors (Tailwind uses `bg-destructive/15` etc).
  5. Compute WCAG contrast; assert ≥ 4.5.

Usage:
  python3 e2e/contrast/badge_runtime.py [--base-url http://localhost:8080]
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from playwright.async_api import Page, async_playwright

AA = 4.5

# Fill the form so the resulting status is "down" (averaging price < current avg)
# or "up" (averaging price > current avg).
CASES = [
    {"status": "down", "avg": "1000", "lot": "10", "harga": "800", "tambah": "5"},
    {"status": "up",   "avg": "1000", "lot": "10", "harga": "1200", "tambah": "5"},
]

# Extracts the badge's foreground color and the composited opaque background,
# by walking up ancestors and painting translucent layers back-to-front.
BADGE_JS = r"""
() => {
  const cards = document.querySelectorAll('[aria-labelledby="result-heading"]');
  const card = cards[cards.length - 1];
  if (!card) return { error: 'no result card' };
  const badge = Array.from(card.querySelectorAll('span,div'))
    .find(el => /%$/.test((el.textContent || '').trim()) && el.closest('.inline-flex,[class*="rounded-full"]'));
  const el = badge ? badge.closest('[class*="rounded-full"]') || badge : null;
  if (!el) return { error: 'no badge' };

  // Convert any CSS color (rgb, rgba, oklch, hsl…) to normalized rgba by
  // painting a pixel and reading it back — this is the exact color the user sees.
  const cvs = document.createElement('canvas');
  cvs.width = cvs.height = 1;
  const ctx = cvs.getContext('2d', { willReadFrequently: true });
  const toRgba = (css) => {
    if (!css || css === 'transparent') return { r: 0, g: 0, b: 0, a: 0 };
    ctx.clearRect(0, 0, 1, 1);
    ctx.fillStyle = '#000';
    ctx.fillStyle = css;                          // browser parses arbitrary color syntax
    ctx.fillRect(0, 0, 1, 1);
    const [r, g, b, a] = ctx.getImageData(0, 0, 1, 1).data;
    return { r: r/255, g: g/255, b: b/255, a: a/255 };
  };

  const layers = [];
  let node = el;
  while (node && node !== document.documentElement.parentNode) {
    const c = toRgba(getComputedStyle(node).backgroundColor);
    if (c.a > 0) layers.push(c);
    node = node.parentElement;
  }
  const rootBg = (() => {
    const r = toRgba(getComputedStyle(document.documentElement).backgroundColor);
    if (r.a > 0) return r;
    const b = toRgba(getComputedStyle(document.body).backgroundColor);
    return b.a > 0 ? b : { r: 1, g: 1, b: 1, a: 1 };
  })();

  let bg = rootBg;
  for (let i = layers.length - 1; i >= 0; i--) {
    const top = layers[i];
    bg = {
      r: top.r * top.a + bg.r * (1 - top.a),
      g: top.g * top.a + bg.g * (1 - top.a),
      b: top.b * top.a + bg.b * (1 - top.a),
      a: 1,
    };
  }
  const fg = toRgba(getComputedStyle(el).color);
  return {
    fg, bg,
    text: (el.textContent || '').trim(),
    fontSize: parseFloat(getComputedStyle(el).fontSize),
    fontWeight: getComputedStyle(el).fontWeight,
  };
}
"""


def rel_lum(c: dict) -> float:
    def ch(x: float) -> float:
        return x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4
    return 0.2126 * ch(c["r"]) + 0.7152 * ch(c["g"]) + 0.0722 * ch(c["b"])


def contrast(a: dict, b: dict) -> float:
    L1, L2 = rel_lum(a), rel_lum(b)
    hi, lo = (L1, L2) if L1 > L2 else (L2, L1)
    return (hi + 0.05) / (lo + 0.05)


def fmt(c: dict) -> str:
    return f"rgb({int(c['r']*255)},{int(c['g']*255)},{int(c['b']*255)})"


async def set_theme(page: Page, theme: str) -> None:
    await page.evaluate(
        f"""(() => {{
            localStorage.setItem('idxavg-theme', {theme!r});
            document.documentElement.classList.toggle('dark', {str(theme == 'dark').lower()});
        }})()"""
    )
    await page.wait_for_timeout(150)


async def render_case(page: Page, case: dict) -> None:
    for id_, val in [
        ("avg-now-input", case["avg"]),
        ("total-lot-input", case["lot"]),
        ("harga-avg-input", case["harga"]),
        ("lot-tambah-input", case["tambah"]),
    ]:
        loc = page.locator(f"#{id_}")
        await loc.fill("")
        await loc.fill(val)
    await page.locator("#lot-tambah-input").blur()
    await page.locator("#lot-tambah-input").focus()
    await page.keyboard.press("Control+Enter")
    await page.locator('[aria-labelledby="result-heading"]').first.wait_for(
        state="visible", timeout=3000
    )
    await page.wait_for_timeout(150)


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
        await page.wait_for_load_state("networkidle")

        for theme in ("light", "dark"):
            await set_theme(page, theme)
            for case in CASES:
                await render_case(page, case)
                data = await page.evaluate(BADGE_JS)
                if "error" in data:
                    failures.append(f"[{theme}/{case['status']}] {data['error']}")
                    continue
                ratio = contrast(data["fg"], data["bg"])
                label = f"[{theme}/{case['status']}] '{data['text']}' fg={fmt(data['fg'])} bg={fmt(data['bg'])} " \
                        f"@{data['fontSize']}px/{data['fontWeight']} → {ratio:.2f}:1"
                if ratio < AA:
                    failures.append(f"FAIL {label} (< {AA})")
                else:
                    notes.append(label)

        await browser.close()

    print("\n--- badge runtime contrast ---")
    for n in notes:
        print(f"  ok  {n}")
    for f in failures:
        print(f"  {f}")
    print(f"\n{'PASS' if not failures else 'FAIL'} — {len(failures)} failure(s)")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
