# Home Screen Dashboard 1.8.1 native release evidence

This directory preserves the exact-package, native 100% Deck Browser evidence
for Home Screen Dashboard 1.8.1. The 47 raw PNG captures are copied
byte-for-byte from the passed isolated Anki 26.8.1 run. The 13 numbered detail
sheets cover every capture exactly once, and the overview provides navigation
across the complete set.

## Acceptance authority

- `contact-sheets/contact-sheet-00-overview.png` indexes all 47 captures.
- `contact-sheets/contact-sheet-01-*.png` through
  `contact-sheet-13-*.png` are the readable review sheets.
- `contact-sheets/contact-sheet-index.json` maps every capture to its detail
  sheet and verifies complete, non-duplicated detail coverage.
- `capture-evidence-manifest.json` records hashes, tags, dimensions, package
  provenance, and the explicit restart waiver.
- `package/home-dashboard-overhaul-1.8.1.ankiaddon` is the byte-identical
  candidate installed in the disposable Anki run.
- `reports/runtime-report-initial.json` is the passed 47-frame native report.
- `reports/validation-summary.json` records the final automated, package, and
  native validation results and keeps the restart waiver separate.
- `reports/final-contrast-test-report.*` and
  `reports/final-hardcoded-color-audit.*` preserve the final color-system gate.

The supplied 3420×2146 screenshot and retained 1.8.0 contact sheets were
calibration/comparison inputs only. They are not copied into this set and are
not represented as newly generated acceptance evidence.

## Explicit restart boundary

The isolated restart repeated the process, profile, add-on, filesystem,
window, sync-disabled, exact-package, run-root, and single-instance identity
gates. It then detected that `heatmap.calendar_view` read back as Year instead
of the expected Month. At the user's direction, no further fix or restart
capture was attempted. Restart/settings persistence therefore remains
user-waived, not passed, and no restart image appears in the contact sheets.

## Deferred and unrun

Dedicated 125%/150% captures, spoken screen-reader review, Windows validation,
Linux validation, forced-colors review, and OS-level scaling acceptance were
not run and are not implied by this macOS native 100% evidence.
