# Home Screen Dashboard

Home Screen Dashboard 1.8.7 is a calendar-first Deck Browser dashboard for
Anki Desktop 26.8. It combines study history, due work, local events, stable
metrics, and a rotating Bible verse without patching Anki's private Deck
Browser or statistics classes.

## 1.8.7 highlights

- Settings now uses the same native window contract as Progress Bar and
  PronounceIt: a movable, resizable `QDialog(mw)` with a 680×620 initial size,
  a 680×560 minimum, default flags, and a local `exec()` lifetime.
- The Caleb menu opens Settings directly and synchronously. Calendar/WebEngine
  requests alone wait one coalesced event-loop turn so the bridge callback can
  return before the dialog opens.
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
- Settings keeps the compact visual workflow used by conventional add-on
  settings in a normal parented dialog. It does not query a screen or call
  `move()` before opening; Qt therefore retains its parent-aware `QDialog`
  placement instead of treating Settings as an explicitly positioned desktop
  window. It also does not save coordinates, set window flags, hide Anki's
  backing views, force focus, or contain a WebEngine preview surface. Sidebar
  and Events-tab changes only swap child widgets in the existing stack.
- Responsive Settings grids parent every new field to its card before showing
  or visibility-filtering it. Dynamic heatmap and verse badges likewise have
  explicit child parents before visibility changes. Generic staged-setting
  synchronization no longer destroys and rebuilds the heatmap-card tree, while
  actual theme and color-mode changes still refresh those previews.

- Settings uses one native Qt composition at every size: a compact header,
  152 px text rail, one active page scroller, and a stable final-row footer.
- At 150% application font size, long Settings rail labels wrap within that
  fixed rail instead of being clipped or elided.
- Dashboard, Events, Bible verse, and About use compact content-sized controls
  while retaining schema 8, staged changes, three-way merge behavior, and all
  existing configuration keys. Event sorting additionally accepts `name`.
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
installation through **Tools → Add-ons → Install from file**. Its checksum is
written alongside the archive: SHA-256
`09d5dbbfae01d13b0a05798a756447c52ac347a670bf884bcaab868d60cc5376`.
This candidate remains local until the native macOS full-screen Space check
passes. Disable any legacy source add-ons named by the activation card.

The manifest supports Anki Desktop 26.8 (`min_point_version` and
`max_point_version` 260800).

## Build and minimal validation

Use Python 3.10 or newer:

```sh
python3 -m unittest home_dashboard_overhaul.tests.test_controller_insights home_dashboard_overhaul.tests.test_settings_release_contract -v
python3 home_dashboard_overhaul/qa/validate_settings_window_contract_1_8_7.py
python3 home_dashboard_overhaul/tools/build_ankiaddon.py
```

The builder creates one 24-member allowlisted archive and verifies its version,
safe paths, focused Settings contract, and source/archive byte parity. The
full 1.8.6 statistics and 94-frame evidence campaign is not rerun for this
compact-window candidate.

The current focused window authority is
[settings_window_contract_1_8_7.json](home_dashboard_overhaul/qa/settings_window_contract_1_8_7.json).
The frozen 1.8.6 release authorities remain:

- [capture_plan.json](home_dashboard_overhaul/qa/capture_plan.json), the
  extensible execution registry used by helper preparation, runtime selection,
  and evidence assembly
- [calendar_surface_manifest_1_8_6.json](home_dashboard_overhaul/qa/calendar_surface_manifest_1_8_6.json)
- [ui-surface-registry_1_8_6.json](home_dashboard_overhaul/qa/ui-surface-registry_1_8_6.json)
- [visual_regression_matrix_1_8_6.json](home_dashboard_overhaul/qa/visual_regression_matrix_1_8_6.json)
- [capture_evidence_manifest_1_8_6.json](home_dashboard_overhaul/qa/capture_evidence_manifest_1_8_6.json)

The [capture workflow](home_dashboard_overhaul/docs/qa/capture-workflow.md)
documents how to extend coverage, generate a named profile, run focused
diagnostic recaptures, and assemble fresh evidence from the shared plan.

The completed [1.8.6 native release evidence](home_dashboard_overhaul/qa/release-evidence-1.8.6-2026-08-25/README.md)
contains the exact 24-member archive, 94 contract-owned native captures,
passing restart-persistence and archive-parity reports, and four-gate isolation
proof repeated after restart. Its 19 generated presentation sheets were
reviewed locally and are retained with the current evidence set. Seventeen
capture-detail sheets cover every native frame exactly once, with one overview
and one package/isolation report sheet. The
[evidence manifest](home_dashboard_overhaul/qa/release-evidence-1.8.6-2026-08-25/capture-evidence-manifest.json)
records the sheet counts, exact package hash, and deferred gates.
Only the newest complete capture set is retained in the repository. Superseded
live-UI, 1.8.0-1.8.5, prior 1.8.6, and standalone Settings capture directories
were removed after this set passed; their Git history remains traceable.
The untracked 1.8.7 Settings review evidence is retained separately as immutable
design provenance. VoiceOver and forced-colors remain explicitly unrun and
nonblocking; Windows, Linux, DPR 1, true OS display scaling, and native macOS
full-screen Space behavior remain release-blocking until run successfully.

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
