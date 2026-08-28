# Home Screen Dashboard

Home Screen Dashboard 1.8.7 is a calendar-first Deck Browser dashboard for
Anki Desktop 26.8. It combines study history, due work, local events, stable
metrics, and a rotating Bible verse without patching Anki's private Deck
Browser or statistics classes.

## 1.8.7 highlights

- Settings remains a parented native `QDialog(mw)` with a local `exec()`
  lifetime. Its logical default is 1080×760, its normal minimum is 820×600,
  and it keeps 48 px normal screen margins or 24 px on a constrained screen.
- The UI-only `settings_dialog_geometry/v4` record stores logical geometry,
  screen identity, available bounds, and informational DPR. A valid v3 record
  migrates only when it meets the current minimum and remains at least 80%
  visible; disconnected, undersized, maximized, and full-screen records are
  rejected.
- The Caleb menu opens Settings directly and synchronously. Deck Browser
  bridge requests alone wait one coalesced event-loop turn so the callback can
  return first, and re-entry routes to the live modal dialog.
- Dashboard-specific workspace insertion, backing-view hiding, menu-dismissal
  timers, focus retries, focus restoration, and activation handling have been
  removed. Qt owns the window and focus lifecycle.
- Schema 8, all Settings fields, dashboard rendering, and the corrected 1.8.6
  statistics calculations remain unchanged.

- Every study-derived value now uses one collection-wide analytics scope.
  Today and historical facts use exact rollover-relative periods; New,
  Learning, Review, and Total remaining use each included top-level head's
  limited due tree without depending on the selected deck; and calendar due
  forecasting matches Anki's non-new, non-suspended future-due rules.
- Last 7 Days and All Time Retention now match Anki 26.8.1 native eligible
  retention instead of all-answer success. The visible Retention is rounded
  half-up once and Again is its exact complement, so the 80% all-answer
  regression correctly displays 86% Retention and 14% Again.
- Remaining categories follow scheduler queues rather than card types: queue 0
  is New, queues 1/3/4 are Learning, and queue 2 is Review. Suspended and
  explicitly buried queues are excluded; Cards buried reports only scoped
  queues -2/-3 that are New or currently due/overdue. Future Learning and
  Review cards and transient queue-hidden siblings are excluded.
- Initial HTML, live refresh, wide Month and Year 2×2 layouts, intermediate and
  narrow shells, and hard restart are contractually checked
  against identical values from the same collection snapshot.
- Settings uses a fixed header, vertically scrollable native page body, and
  fixed 60 px footer. A shell capped near 1,240 px contains a 184 px sidebar,
  fixed 72 px page header, and page column capped at 980 px. Compact top
  navigation is reserved for screens that cannot accommodate the 920×640
  normal minimum and activates below 820 logical pixels.
- Responsive Settings grids parent every field to its card before showing or
  filtering it. Settings renders no Dashboard, verse, palette, theme, or
  heatmap previews; selector text carries those choices and the custom-color
  well remains an input.
- Dashboard theme and Heatmap palette share one responsive Appearance row.
  Their layout-changing staged updates run after the native combo popup closes,
  and save locking restores both the combo boxes and their nested popup views.

- Dashboard groups Appearance, Dashboard sections, Study metrics, and Calendar
  display. Events has a header Add action, flexible searchable/sortable
  Active/Archived list with 54 px rows, and a parented 560×320 editor. Bible
  verse has Appearance, Rotation, and a flexible clamped Verse library. About
  groups Version and support, Privacy and legal, and Backup and recovery.
- Dirty, saving, success, validation, and persistence feedback now lives in
  the footer beside Close and Save. Failed saves retain every staged value and
  expose generic user-facing copy with technical details collapsed separately.
- Settings colors follow only Anki's live palette. Dark and light graphite
  tokens, accent-soft selection, neutral Events tabs, relative role fonts,
  36 px controls, and the shared 4/8/12/16/20/24/32 spacing scale are applied
  consistently at the canonical 100% application font.
- Month is a stable 42-cell grid and Year remains a true 53-week grid. The
  production dashboard is capped at 1,120 px and measures Anki's visible
  bottom actions to maintain 24 px of clearance in normal document flow.
- All 16 existing completion-palette IDs now resolve to separately authored
  light and dark ladders while preserving each theme's saved selection.
- Config and manual-verse persistence is transactional, with best-effort
  rollback and an inline error if only part of a save succeeds.
- Labels, ordering, whole-percent formatting, schema 8, existing metric/bridge
  keys, events, verses, migration behavior, and Anki's native navigation, deck
  table, gear, background, and bottom actions remain intact.

## Install

The local 1.8.7 candidate is built as
`home_dashboard_overhaul/dist/home-dashboard-overhaul-1.8.7.ankiaddon` for
installation through **Tools → Add-ons → Install from file**. The builder
writes the candidate checksum beside the archive. This candidate remains local
until the native platform matrix and macOS full-screen Space checks pass.
Disable any legacy source add-ons named by the activation card.

The manifest supports Anki Desktop 26.8 (`min_point_version` and
`max_point_version` 260800).

## Build and minimal validation

Use Python 3.10 or newer:

```sh
python3 -m unittest home_dashboard_overhaul.tests.test_controller_insights home_dashboard_overhaul.tests.test_settings_release_contract -v
python3 -m unittest discover -s home_dashboard_overhaul/tests -v
node home_dashboard_overhaul/tests/calendar_model_test.js
python3 home_dashboard_overhaul/qa/capture_plan.py --json
python3 home_dashboard_overhaul/qa/validate_revised_ui_contract.py
python3 home_dashboard_overhaul/qa/validate_settings_window_contract_1_8_7.py
python3 home_dashboard_overhaul/tools/build_ankiaddon.py
```

The builder creates one 24-member allowlisted archive and verifies its version,
safe paths, current Settings contract, and source/archive byte parity. The
canonical 1.8.7 plan contains 94 native frames: 92 initial states and two
controlled-restart states. Its minimal Settings profile is exactly 41 frames
at 100% application font, with no more than 11 compact contact sheets.
Each PNG must sample-match the live Settings client, and all 12 page captures
must include the complete decorated native Settings window; a same-sized
Dashboard background is a capture failure.
Settings acceptance also requires a structured exact-package native macOS
result proving that opening Settings from both the full-screen menu and the
Dashboard gear stays on Anki's full-screen Space without switching to the
desktop. Each route separately verifies all pages, Events tabs, resize, event
and verse edits, save, close/reopen, and controlled restart with current-Space
retention recorded for every step. This gate adds no PNG captures.

The current 1.8.7 authorities are:

- [capture_plan.json](home_dashboard_overhaul/qa/capture_plan.json), the sole
  executable case, count, order, profile, and presentation authority
- [calendar_surface_manifest_1_8_7.json](home_dashboard_overhaul/qa/calendar_surface_manifest_1_8_7.json)
- [ui-surface-registry_1_8_7.json](home_dashboard_overhaul/qa/ui-surface-registry_1_8_7.json)
- [visual_regression_matrix_1_8_7.json](home_dashboard_overhaul/qa/visual_regression_matrix_1_8_7.json)
- [capture_evidence_manifest_1_8_7.json](home_dashboard_overhaul/qa/capture_evidence_manifest_1_8_7.json)
- [runtime_probe_release_1_8_7_manifest.json](home_dashboard_overhaul/qa/runtime_probe_release_1_8_7_manifest.json)
- [settings_window_contract_1_8_7.json](home_dashboard_overhaul/qa/settings_window_contract_1_8_7.json)

The [capture workflow](home_dashboard_overhaul/docs/qa/capture-workflow.md)
documents how to extend coverage, generate a named profile, run focused
diagnostic recaptures, and assemble fresh evidence from the shared plan.

The completed [1.8.6 native release evidence](home_dashboard_overhaul/qa/release-evidence-1.8.6-2026-08-25/README.md)
remains the retained full 94-frame baseline. It contains the exact 24-member
archive, passing restart-persistence and archive-parity reports, four-gate
isolation proof repeated after restart, and 19 reviewed presentation sheets.

The current 1.8.7 candidate is `c4b794f0b4e1bcf4c380b0092c9436f0594f7f26d12ae9af2345a03e2eb39a3f`.
Its [Dashboard review evidence](home_dashboard_overhaul/qa/home-dashboard-evidence-1.8.7-2026-08-27-c4b794f0-fresh-100/README.md)
contains 42 native 100% captures and six contact sheets: 32 theme/layout
states, eight interaction-state fixtures, and two exact-package full-screen
Dashboard frames. Runtime, archive parity, color-hardcoding, and all 582 gated
contrast-pair checks passed.

The matching [Settings review evidence](home_dashboard_overhaul/qa/settings-evidence-1.8.7-2026-08-27-c4b794f0-fresh-100/README.md)
contains exactly 41 native Settings captures at 100% application font plus 11
contact sheets. Its status remains `review-incomplete-nonrelease`: capture and
structured-layout checks passed without recorded failures, but the
exact-package full-screen macOS menu and Dashboard-gear opening paths were
explicitly skipped and remain unrun. These two 1.8.7 sets are review evidence,
not release approval. VoiceOver and forced-colors remain explicitly unrun and
nonblocking. Windows, Linux, DPR 1, and true OS display scaling remain separate
release-blocking gates until run successfully.

## Project layout

- `home_dashboard_overhaul/`: packaged add-on source and documentation
- `home_dashboard_overhaul/tests/`: behavior and release-contract tests
- `home_dashboard_overhaul/qa/`: machine-readable contracts, QA tools, and
  versioned release evidence
- `deferred/calendar_sources_vnext/`: intentionally deferred external-calendar
  source excluded from 1.8.7

## License and notices

The add-on is licensed under AGPL-3.0-or-later. See
[LICENSE.txt](home_dashboard_overhaul/LICENSE.txt) and
[THIRD_PARTY_NOTICES.md](home_dashboard_overhaul/THIRD_PARTY_NOTICES.md).
