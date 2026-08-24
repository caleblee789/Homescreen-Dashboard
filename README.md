# Home Screen Dashboard

Home Screen Dashboard 1.8.6 is a calendar-first Deck Browser dashboard for
Anki Desktop 26.8. It combines study history, due work, local events, stable
metrics, and a rotating Bible verse without patching Anki's private Deck
Browser or statistics classes.

## 1.8.6 highlights

- Every study-derived value now uses one scheduler-authoritative snapshot.
  Today and historical facts use exact rollover-relative periods; New,
  Learning, Review, and Total remaining are reconciled with Anki's due tree
  and built reviewer queue; and calendar due forecasting matches Anki's
  non-new, non-suspended future-due rules.
- Last 7 Days and All Time Retention now match Anki 26.8.1 native eligible
  retention instead of all-answer success. The visible Retention is rounded
  half-up once and Again is its exact complement, so the 80% all-answer
  regression correctly displays 86% Retention and 14% Again.
- Initial HTML, live refresh, wide Month and Year 2×2 layouts, intermediate and
  narrow shells, Settings Preview, and hard restart are contractually checked
  against identical values from the same collection snapshot.
- Settings remains one fixed, non-modal, parented native Qt composition. On
  macOS it verifies a native child relationship to Anki before opening, which
  keeps the window in Anki's active full-screen Space; geometry is not saved.

- Settings uses one native Qt composition at every size: a compact header,
  152 px text rail, one active page scroller, one shared optional Preview dock,
  and a stable final-row footer.
- Dashboard, Events, Bible verse, and About use compact content-sized controls
  while retaining schema 8, staged previews, three-way merge behavior, and all
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

The local 1.8.6 candidate is built as
`home_dashboard_overhaul/dist/home-dashboard-overhaul-1.8.6.ankiaddon` for
installation through **Tools → Add-ons → Install from file**. Its SHA-256 is
`bb9b76df9f4d40302ee1d3322a061b520517d885ff6181031e3f702004ce5ffd`.
It will be copied into versioned native release evidence only after the
remaining runtime gate is completed. Disable any legacy source add-ons named
by the activation card.

The manifest supports Anki Desktop 26.8 (`min_point_version` and
`max_point_version` 260800).

## Build and minimal validation

Use Python 3.10 or newer:

```sh
python3 -m unittest discover -s home_dashboard_overhaul/tests -p 'test_*.py' -v
node home_dashboard_overhaul/tests/calendar_model_test.js
python3 home_dashboard_overhaul/qa/validate_revised_ui_contract.py
python3 home_dashboard_overhaul/tools/build_ankiaddon.py
```

The builder creates one 24-member allowlisted archive and verifies its version,
safe paths, and source/archive byte parity. Release validation installs that
exact archive in a fresh sync-disabled disposable Anki profile, proves four
isolation gates before interaction and after one controlled restart, and
captures the 102 states derived from the current implementation contract.

The current machine-readable release authorities are:

- [calendar_surface_manifest_1_8_6.json](home_dashboard_overhaul/qa/calendar_surface_manifest_1_8_6.json)
- [ui-surface-registry_1_8_6.json](home_dashboard_overhaul/qa/ui-surface-registry_1_8_6.json)
- [visual_regression_matrix_1_8_6.json](home_dashboard_overhaul/qa/visual_regression_matrix_1_8_6.json)
- [capture_evidence_manifest_1_8_6.json](home_dashboard_overhaul/qa/capture_evidence_manifest_1_8_6.json)

The pending 1.8.6 evidence contract requires the exact 24-member archive, 102
contract-owned native captures, all 19 detail sheets, an overview contact
sheet, restart-persistence results, archive parity, and four-gate isolation
reports. None of those runtime deliverables are claimed complete until the
remaining native capture and restart gate is run successfully.
The [1.8.3 Settings contact-sheet baseline](home_dashboard_overhaul/qa/settings-menu-contact-sheets-1.8.3-2026-08-23-2222/capture-manifest.json)
is preserved separately as historical design evidence with 21 raw captures and
six presentation sheets.

The 1.8.0 through 1.8.5 packages and evidence remain immutable historical
comparison material. VoiceOver, Windows, Linux, forced-colors, DPR 1, and true
OS display-scaling acceptance remain deferred and unclaimed unless run.

## Project layout

- `home_dashboard_overhaul/`: packaged add-on source and documentation
- `home_dashboard_overhaul/tests/`: behavior and release-contract tests
- `home_dashboard_overhaul/qa/`: machine-readable contracts, QA tools, and
  versioned release evidence
- `deferred/calendar_sources_vnext/`: intentionally deferred external-calendar
  source excluded from 1.8.6

## License and notices

The add-on is licensed under AGPL-3.0-or-later. See
[LICENSE.txt](home_dashboard_overhaul/LICENSE.txt) and
[THIRD_PARTY_NOTICES.md](home_dashboard_overhaul/THIRD_PARTY_NOTICES.md).
