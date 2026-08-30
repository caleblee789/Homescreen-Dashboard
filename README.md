# Home Screen Dashboard

Home Screen Dashboard 1.8.7 is a calendar-first Deck Browser dashboard for
Anki Desktop 26.8. It combines study history, due work, local events, stable
metrics, and a rotating Bible verse without patching Anki's private Deck
Browser or statistics classes.

## 1.8.7 highlights

- Settings remains a parented native `QDialog(mw)` with a local `exec()`
  lifetime. Its logical default is 1080×760, its normal minimum is 860×640,
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
- Schema 8, all Settings fields, and the corrected scheduler and retention
  calculations remain unchanged.

- Every study-derived value now uses one collection-wide analytics scope.
  Today and historical facts use exact rollover-relative periods; New,
  Learning, Review, and Total remaining use each included top-level head's
  limited due tree without depending on the selected deck; and calendar due
  forecasting matches Anki's non-new, non-suspended future-due rules.
- Last 7 Days and All Time Retention now match Anki 26.8.1 native eligible
  retention instead of all-answer success. The visible Retention is rounded
  half-up once. Last 7 Days now displays Time spent from those same seven
  rollover-relative periods instead of displaying Again rate.
- Remaining categories follow scheduler queues rather than card types: queue 0
  is New, queues 1/3/4 are Learning, and queue 2 is Review. Suspended and
  explicitly buried queues are excluded; Cards buried reports only scoped
  queues -2/-3 that are New or currently due/overdue. Future Learning and
  Review cards and transient queue-hidden siblings are excluded. While work
  remains, the progress bar displays `N% complete` inside the progress bar.
- Initial HTML, live refresh, wide Month and Year 2×2 layouts, intermediate and
  narrow shells, and hard restart are contractually checked
  against identical values from the same collection snapshot.
- Settings uses a fixed header, vertically scrollable native page body, a
  reserved error region, and a separate fixed 56 px action footer. A centered
  shell capped at 1,264 px contains a 184 px sidebar and a page column capped
  at 1,080 px. At the supported 860×640 minimum, the page title remains above
  a single-row tab bar.
- Responsive Settings grids parent every field to its card before showing or
  filtering it. At 760 px of page content, Dashboard sections pair with Study
  metrics, Calendar display pairs with Calendar range, Bible Appearance pairs
  with Rotation, and About uses two deliberate columns. Appearance stays full
  width. The heatmap selector includes a five-step palette preview and Bible
  Appearance includes a compact live preview.
- Dashboard theme and Calendar heatmap palette share one responsive Appearance
  row.
  Their layout-changing staged updates run after the native combo popup closes,
  and save locking restores both the combo boxes and their nested popup views.

- Dashboard groups Appearance, Dashboard sections, Study metrics, Calendar
  display, and Calendar range. Events has one content-sized Add event action,
  a searchable/sortable Active/Archived list bounded to five rows, and a shared
  parented window-modal editor 480–540 px wide and at most 80% of the Settings
  body. Bible verse has Appearance, Rotation, and a flexible clamped Verse
  library. About groups Version and support, Privacy and legal, and Backup and
  recovery.
- Dirty, saving, success, and discard feedback remains in the fixed action
  footer; validation and save failures use the reserved region above it.
  Failed saves retain the complete draft for lossless retry and expose
  technical details separately.
- Settings colors follow only Anki's live palette: light `#F3F6F8`/`#E9EFF4`
  surfaces with `#C7D1DB` borders and dark `#0B1118`/`#151D26` surfaces with
  `#2B3948` borders. Native controls use 34 px targets and the shared
  4/8/12/16/24 spacing scale at the canonical 100% application font.
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
writes the candidate checksum beside the archive. The frozen `4d0a4107…`
candidate passed the required macOS Retina 100% native checks and the
pointer-only full-screen menu and Dashboard-gear workflows. It remains
`review-required`, with independent human review still unrun.
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

The current [1.8.7 exact-package native evidence](home_dashboard_overhaul/qa/release-evidence-1.8.7-2026-08-30-4d0a4107-ui-readiness-100/README.md)
is bound to candidate SHA-256
`4d0a410721ba5af43cd672127531eefc90795881ef4f9e755a6fb8550aa61994`
and capture-plan SHA-256
`e99c6d7ad357e73649a20bbbf65deea2524218173cb4c963df27de62fee33e45`.
It retains 94 native frames, 18 contact sheets, the exact 24-member archive,
source/archive byte parity, restart persistence, and isolation proof. The
[overview sheet](home_dashboard_overhaul/qa/release-evidence-1.8.7-2026-08-30-4d0a4107-ui-readiness-100/contact-sheets/contact-sheet-00-overview.png)
covers the complete Dashboard and Settings profile.

Automated checks, exact-package capture, and the pointer-only macOS full-screen
menu and Dashboard-gear routes passed before and after controlled restart.
This evidence remains `quality_status: review-required` and
`release_ready: false` until an independent human reviews every contact sheet
and the native interaction result. VoiceOver, forced colors, reduced motion,
Windows, Linux, DPR 1, alternate application-font percentages, and alternate
native OS display scaling remain explicitly unrun, unclaimed, and nonblocking
for 1.8.7. The packaged documentation still contains legacy Settings-layout,
rotation-state, and native-scaling wording. Correcting those packaged members
changes the candidate hash and therefore requires a new exact-package
validation and evidence cycle.
Superseded capture sets were retired only after their replacement hashes and
exact-once coverage were verified and a recoverable safety snapshot was made.

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
