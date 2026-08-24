# Home Screen Dashboard 1.8.3 native release evidence

This directory preserves the exact-package, native 100% Deck Browser evidence
for Home Screen Dashboard 1.8.3. The 56 raw PNG captures are copied
byte-for-byte from the passed isolated Anki 26.8 run and one restart. The 15 numbered detail
sheets cover every capture exactly once, and the overview provides navigation
across the complete set.

## Acceptance authority

- `contact-sheets/contact-sheet-00-overview.png` indexes all 56 captures.
- `contact-sheets/contact-sheet-01-*.png` through
  `contact-sheet-15-*.png` are the readable review sheets.
- `contact-sheets/contact-sheet-index.json` maps every capture to its detail
  sheet and verifies complete, non-duplicated detail coverage.
- `capture-evidence-manifest.json` records hashes, tags, dimensions, package
  provenance, and the passed single-restart persistence gate.
- `package/home-dashboard-overhaul-1.8.3.ankiaddon` is the byte-identical
  candidate installed in the disposable Anki run.
- `reports/runtime-report-initial.json` is the passed 55-frame native report.
- `reports/runtime-report-restart.json` is the passed one-frame restart
  persistence report.
- The exact installed package SHA-256 is `3b40664ff34ae94ff86a2f22dd5e6eb552e3ca4f233380a141f821c44a1c1e67`.

The supplied 3420×2214 screenshot and retained 1.8.0, 1.8.1, and 1.8.2 evidence were
calibration/comparison inputs only. They are not copied into this set, were not
modified, and are not represented as newly generated acceptance evidence.

## Restart persistence

The isolated restart repeated the process, profile, add-on, filesystem,
window, sync-disabled, exact-package, run-root, and single-instance identity
gates. The Year view and clean schema-8 Settings normalization read back
correctly. The
`RUNTIME-RESTART-PERSISTENCE` frame appears on the runtime detail sheet. No
restart waiver exists for this release.

## Deferred and unrun

VoiceOver, Windows validation, Linux validation, forced-colors review,
non-100% scaling, and OS-level scaling acceptance were
not run and are not implied by this macOS native 100% evidence.
