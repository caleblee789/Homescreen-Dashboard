# Home Screen Dashboard 1.8.4 native release evidence

This directory preserves the exact-package, native 100% Deck Browser evidence
for Home Screen Dashboard 1.8.4. The 56 raw PNG captures are copied
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
- `package/home-dashboard-overhaul-1.8.4.ankiaddon` is the byte-identical
  candidate installed in the disposable Anki run.
- `reports/runtime-report-initial.json` is the passed 55-frame native report.
- `reports/runtime-report-restart.json` is the passed one-frame restart
  persistence report.
- The live collection gate kept head A active and proved independent remaining
  new limits of 3 and 7 aggregate to 10, excluding B leaves 3, and the
  unexcluded dashboard still shows 10 after restart.
- The exact installed package SHA-256 is `aba2bc24dd5b2fe8320460211b1244c00da18ff96f208f5cfa94fc862c99fbbe`.

The supplied 3420×2214 screenshot and retained 1.8.0 through 1.8.3 evidence were
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
