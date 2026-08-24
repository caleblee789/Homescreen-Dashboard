# Home Screen Dashboard 1.8.2 native release evidence

This directory preserves the exact-package, native 100% Deck Browser evidence
for Home Screen Dashboard 1.8.2. The 48 raw PNG captures are copied
byte-for-byte from the passed isolated Anki 26.8.1 run and hard restart. The 13 numbered detail
sheets cover every capture exactly once, and the overview provides navigation
across the complete set.

## Acceptance authority

- `contact-sheets/contact-sheet-00-overview.png` indexes all 48 captures.
- `contact-sheets/contact-sheet-01-*.png` through
  `contact-sheet-13-*.png` are the readable review sheets.
- `contact-sheets/contact-sheet-index.json` maps every capture to its detail
  sheet and verifies complete, non-duplicated detail coverage.
- `capture-evidence-manifest.json` records hashes, tags, dimensions, package
  provenance, and the passed hard-restart persistence gate.
- `package/home-dashboard-overhaul-1.8.2.ankiaddon` is the byte-identical
  candidate installed in the disposable Anki run.
- `reports/runtime-report-initial.json` is the passed 47-frame native report.
- `reports/runtime-report-restart.json` is the passed one-frame hard-restart
  persistence report.
- `reports/validation-summary.json` records the complete automated, package,
  native, restart, and explicitly deferred release gates against implementation
  commit `b3a37fdf09fea7b30a273b1b3b6b53a9aa578581`.
- The exact installed package SHA-256 is `f1a3eddcd47f259b9b7c7645f5f355de1849711034361623498476973e7b2a70`.

The supplied 3420×2214 screenshot and retained 1.8.0 and 1.8.1 evidence were
calibration/comparison inputs only. They are not copied into this set, were not
modified, and are not represented as newly generated acceptance evidence.

## Hard-restart persistence

The isolated restart repeated the process, profile, add-on, filesystem,
window, sync-disabled, exact-package, run-root, and single-instance identity
gates. Month/Year selection, theme, mode, palette, visibility, opacity, blur,
week start, and clean Settings normalization all read back correctly. The
`RUNTIME-RESTART-PERSISTENCE` frame appears on the runtime detail sheet. No
restart waiver exists for this release.

## Deferred and unrun

Dedicated 125%/150% captures, spoken screen-reader review, Windows validation,
Linux validation, forced-colors review, and OS-level scaling acceptance were
not run and are not implied by this macOS native 100% evidence.
