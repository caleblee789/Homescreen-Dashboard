# Final-release dashboard overhaul evidence

Candidate: `home-dashboard-overhaul-1.7.0.ankiaddon`

SHA-256: `3cdfc800de85eaa9fc59f1b06ab9169c517256299c9f174b5709c6bfbaa17ee6`

## Offline validation

- 177 Python tests passed with Python 3.12 and no skips.
- Calendar JavaScript model checks passed.
- Revised UI contract passed: 24 surfaces, 28 criteria, 96 visual cases.
- The deterministic package builder verified the allowlisted contents, archive integrity, fixed timestamps, and byte parity with current source.

## Exact-package isolated Anki run

- Anki: 26.8.1
- Disposable profile: `Codex QA HDO PR 20260822 2238`
- Disposable base: fresh temporary `anki-release-qa` base (path sanitized in this published evidence copy)
- Collection remained inside the disposable base.
- Sync credentials were absent.
- Runtime probe status: passed with no errors.
- Live Month: 1680px dashboard container, 42 cells at 62px, 2x2 statistics on the right, no horizontal overflow, 8.3ms switch.
- Live Year: 365 cells, 12 month labels, 0px maximum square error, no page overflow, 25.2ms switch.
- Settings wide, intermediate, narrow, and 150% enlarged-font states passed without horizontal overflow.
- All eight retained captures were inspected after the run.

The companion
[`100% contact-sheet set`](../final-release-contact-sheets-100-percent-2026-08-22-2248/README.md)
adds the complete 32-case renderer matrix and six full-resolution sheets.

The probe launched and exited against only the disposable collection. A distinct normal-profile Anki process was observed after the probe had exited; it was not used for this evidence and was left untouched.

## Remaining human/platform gates

- Spoken VoiceOver grid and tooltip announcement review was not performed.
- Native Windows high-DPI review was not performed.

Prior package and evidence artifacts were not overwritten.
