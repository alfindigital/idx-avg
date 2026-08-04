import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { converter, parse, formatRgb } from "culori";

// ---------------------------------------------------------------------------
// Automated WCAG AA color-contrast test.
//
// Parses the design tokens from src/styles.css (`:root` = light, `.dark` = dark),
// resolves OKLCH values via culori, composites tinted backgrounds (e.g.
// `bg-destructive/15` over `bg-card`), and asserts contrast ratios for every
// label / error / badge pair used in the calculator UI.
//
// AA thresholds:
//   - normal text (< 18pt / < 14pt bold): 4.5:1
//   - large text: 3.0:1  (we still hold badges to 4.5 since text is small)
// ---------------------------------------------------------------------------

const CSS = readFileSync(resolve(__dirname, "../styles.css"), "utf8");
const toRgb = converter("rgb");

type Rgb = { r: number; g: number; b: number };

function extractBlock(selector: string): Record<string, string> {
  const re = new RegExp(String.raw`${selector.replace(".", "\\.")}\s*\{([\s\S]*?)\}`);
  const m = CSS.match(re);
  if (!m) throw new Error(`Missing CSS block: ${selector}`);
  const out: Record<string, string> = {};
  for (const line of m[1].split("\n")) {
    const decl = line
      .trim()
      .replace(/\/\*.*?\*\//g, "")
      .trim();
    const kv = decl.match(/^(--[\w-]+)\s*:\s*(.+)$/);
    if (kv) out[kv[1]] = kv[2].replace(/;+\s*$/, "").trim();
  }
  return out;
}

const LIGHT = extractBlock(":root");
const DARK = { ...LIGHT, ...extractBlock(".dark") };

function resolveColor(token: string, vars: Record<string, string>): { rgb: Rgb; a: number } {
  const raw = vars[token] ?? token;
  const parsed = parse(raw);
  if (!parsed) throw new Error(`Cannot parse color: ${token} = ${raw}`);
  const rgb = toRgb(parsed);
  if (!rgb) throw new Error(`Cannot convert to rgb: ${raw}`);
  const clamp = (n: number) => Math.max(0, Math.min(1, n));
  return {
    rgb: { r: clamp(rgb.r), g: clamp(rgb.g), b: clamp(rgb.b) },
    a: parsed.alpha ?? 1,
  };
}

function composite(fg: { rgb: Rgb; a: number }, bg: Rgb): Rgb {
  const a = fg.a;
  return {
    r: fg.rgb.r * a + bg.r * (1 - a),
    g: fg.rgb.g * a + bg.g * (1 - a),
    b: fg.rgb.b * a + bg.b * (1 - a),
  };
}

function relLum({ r, g, b }: Rgb): number {
  const ch = (c: number) => (c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4));
  return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b);
}

function contrast(a: Rgb, b: Rgb): number {
  const L1 = relLum(a);
  const L2 = relLum(b);
  const [hi, lo] = L1 > L2 ? [L1, L2] : [L2, L1];
  return (hi + 0.05) / (lo + 0.05);
}

/** Returns effective foreground color rendered at `alpha` opacity on `bg`. */
function tint(token: string, alpha: number, bg: Rgb, vars: Record<string, string>): Rgb {
  const c = resolveColor(token, vars);
  return composite({ rgb: c.rgb, a: alpha }, bg);
}

function solid(token: string, vars: Record<string, string>): Rgb {
  const { rgb, a } = resolveColor(token, vars);
  // Solid tokens should be opaque; if not, composite over background.
  if (a >= 1) return rgb;
  return composite({ rgb, a }, resolveColor("--background", vars).rgb);
}

const AA = 4.5;

function check(name: string, fgToken: string, bg: Rgb, vars: Record<string, string>, min = AA) {
  const fg = solid(fgToken, vars);
  const ratio = contrast(fg, bg);
  return {
    name,
    fg: formatRgb({ mode: "rgb", ...fg }),
    bg: formatRgb({ mode: "rgb", ...bg }),
    ratio,
    min,
  };
}

function runSuite(label: "light" | "dark", vars: Record<string, string>) {
  const bg = solid("--background", vars);
  const card = solid("--card", vars);
  // Badge backgrounds in calculator.tsx:
  //   light:  bg-destructive/15  / bg-success/15   over card
  //   dark:   bg-destructive/20  / bg-success/20   over card
  const badgeAlpha = label === "light" ? 0.15 : 0.2;
  const destBadgeBg = tint("--destructive", badgeAlpha, card, vars);
  const succBadgeBg = tint("--success", badgeAlpha, card, vars);

  const cases = [
    check("body text on background", "--foreground", bg, vars),
    check("muted-foreground on background", "--muted-foreground", bg, vars),
    check("muted-foreground on card", "--muted-foreground", card, vars),
    check("primary label on background", "--primary", bg, vars),
    check("destructive-strong error on background", "--destructive-strong", bg, vars),
    check("destructive-strong error on card", "--destructive-strong", card, vars),
    check(
      "badge Averaging Down (destructive-strong on tint)",
      "--destructive-strong",
      destBadgeBg,
      vars,
    ),
    check("badge Averaging Up (success-strong on tint)", "--success-strong", succBadgeBg, vars),
    check(
      "primary-foreground on primary (submit button)",
      "--primary-foreground",
      solid("--primary", vars),
      vars,
    ),
  ];

  describe(`${label} mode WCAG AA (>= ${AA}:1)`, () => {
    for (const c of cases) {
      it(`${c.name} — measured ${c.ratio.toFixed(2)}:1`, () => {
        expect(c.ratio, `${c.name}: fg=${c.fg} bg=${c.bg}`).toBeGreaterThanOrEqual(c.min);
      });
    }
  });
}

runSuite("light", LIGHT);
runSuite("dark", DARK);
