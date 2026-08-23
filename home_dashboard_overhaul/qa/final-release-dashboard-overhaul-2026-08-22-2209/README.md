# Final-release dashboard overhaul evidence

Candidate: `home-dashboard-overhaul-1.7.0.ankiaddon`

SHA-256: `de3064655ce4fa574320cd8bcc67c529f373bb19d502e8158896abb04fa493b7`

This retained run predates the final documentation reconciliation. The current
exact-package evidence is in
[`final-release-dashboard-overhaul-2026-08-22-2237`](../final-release-dashboard-overhaul-2026-08-22-2237/README.md).

## Offline validation

- 177 Python tests passed; 17 environment-dependent tests were intentionally skipped.
- Calendar JavaScript model checks passed.
- Revised UI contract passed: 24 surfaces, 28 criteria, 96 visual cases.
- The deterministic package builder verified the allowlisted contents, archive integrity, fixed timestamps, and byte parity with the source snapshot used for this run.

## Responsive visual checks

- 1754×900 Month preview: calendar left, four statistic cards in a 2×2 right rail, complete Bible verse visible, and no horizontal overflow.
- Intermediate preview: full-width calendar with the 2×2 statistic grid beneath it.
- Narrow preview: 52px Month cells, one statistic card per row, wrapped actions, and no page-level horizontal overflow.
- Narrow 150% High Contrast preview: no clipped buttons or page-level horizontal overflow.
- Year preview: 12 visible month labels, fixed square cells, and a scrollable grid at narrow widths.
- Historical, current, future, event, and unavailable action/tooltip states were checked against the temporal wording and capability rules.

## Exact-package isolated Anki run

- Anki: 26.8.1
- Disposable profile: `Codex QA HDO Final 20260822 2204`
- Disposable base: fresh temporary `anki-release-qa` base (path sanitized in
  this published evidence copy)
- Collection remained inside the disposable base.
- Sync credentials were absent.
- Runtime probe status: passed with no errors.
- Live Month: 1680px dashboard container, 42 cells at 62px, 2×2 statistics on the right, no horizontal overflow, 9.4ms switch.
- Live Year: 365 cells, 12 month labels, 0px maximum square error, no page overflow, 24.6ms switch.
- Settings wide, intermediate, narrow, and 150% enlarged-font checks passed without horizontal overflow.

## Remaining human/platform gates

- Spoken VoiceOver grid and tooltip announcement review was not performed.
- Native Windows high-DPI review was not performed.

The normal Anki profile was not opened or modified. Prior package and evidence artifacts were not overwritten.
