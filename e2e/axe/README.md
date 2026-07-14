# Axe-core accessibility audit

Playwright-driven WCAG 2.1 A/AA audit for the calculator's form, result card,
and history modal, executed across mobile viewports (320–414px).

## Run locally

```bash
bun run dev           # in one shell — serves http://localhost:8080
python3 -m pip install --no-cache-dir playwright
python3 -m playwright install chromium
python3 e2e/axe/audit.py
```

Exit code is non-zero on any WCAG violation. Contrast rules are intentionally
disabled here (covered by `src/__tests__/contrast.test.ts` against the
OKLCH tokens); axe's sRGB-based algorithm would otherwise report false
positives on this design system.

## CI

The GitHub Actions workflow `.github/workflows/ci.yml` runs this audit on
every PR as the `a11y-axe` job.
