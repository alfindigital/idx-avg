# Visual regression

Playwright captures element-scoped screenshots of the **result card** and
**history modal** at 320/360/390/414 CSS px and compares them against
committed baselines using per-pixel tolerance.

## Run

```bash
# compare against baselines (fails on regression)
python3 e2e/visual/regression.py

# refresh baselines after an intentional UI change
python3 e2e/visual/regression.py --update
```

## Layout

```
e2e/visual/
├── baselines/<viewport>/<surface>.png   ← committed
├── artifacts/<viewport>/                ← gitignored (actual + diff)
└── regression.py
```

Tolerance: per-channel Δ ≤ 8/255 for ≥ 99.80% of pixels. CSS animations,
transitions, and the input caret are disabled before capture for
frame-to-frame stability. When intentional visual changes ship, rerun with
`--update` and commit the baseline PNGs.
