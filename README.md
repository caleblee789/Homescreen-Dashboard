# Home Screen Dashboard

Home Screen Dashboard 1.8.3 is a calendar-first responsive Deck Browser
dashboard for Anki Desktop 26.8. It combines study history, due work, local
events, stable metrics, and a rotating Bible verse without patching Anki's
private Deck Browser or statistics classes.

## 1.8.3 highlights

- Anki's document scroller owns vertical movement, with a 1,240 px dashboard
  maximum and 66 px of clearance above native controls.
- Calendar and the 372 px minimum rail stay side by side from 1,040 px. Below
  that, calendar, auto-fitting metrics, and Bible stack; narrow density starts
  below 420 px.
- Footer semantics distinguish `Next event`, `On this date`, and `No event
  on this date`, with contextual `Add event` and `Edit event` actions.
- Year remains fully visible from 480 px and gains its only internal horizontal
  scroller below that threshold, with complete January/current/December access
  and preserved manual position.
- Metric labels, progress copy, calendar indicators, theme palettes, loading
  skeletons, the failure panel, and the single timestamped refresh banner are
  corrected without changing schema 8.
- The host canvas, Deck Browser background, native controls, and external
  compatibility backgrounds remain untouched.

## Install

Install the verified
`home-dashboard-overhaul-1.8.3.ankiaddon` from the 1.8.3 release evidence
package through **Tools → Add-ons → Install from file**, then restart Anki.
Disable any legacy source add-ons identified by the activation card.

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
safe paths, and source/archive parity. Release runtime validation installs that
exact archive in one fresh sync-disabled disposable Anki profile, performs one
bounded smoke pass and one restart, then produces 56 native captures, one
overview, and 15 detail contact sheets.

The current machine-readable release contracts are:

- [calendar_surface_manifest_1_8_3.json](home_dashboard_overhaul/qa/calendar_surface_manifest_1_8_3.json)
- [visual_regression_matrix_1_8_3.json](home_dashboard_overhaul/qa/visual_regression_matrix_1_8_3.json)
- [capture_evidence_manifest_1_8_3.json](home_dashboard_overhaul/qa/capture_evidence_manifest_1_8_3.json)

The 1.8.0, 1.8.1, and 1.8.2 packages and evidence remain immutable historical
comparison material. VoiceOver, forced-colors, Windows/Linux, non-100% scaling,
and OS-level scaling remain deferred and unclaimed.

## Project layout

- `home_dashboard_overhaul/`: packaged add-on source and documentation
- `home_dashboard_overhaul/tests/`: behavior and release-contract tests
- `home_dashboard_overhaul/qa/`: machine-readable contracts, QA tools, and
  versioned release evidence
- `deferred/calendar_sources_vnext/`: intentionally deferred external-calendar
  source excluded from 1.8.3

## License and notices

The add-on is licensed under AGPL-3.0-or-later. See
[LICENSE.txt](home_dashboard_overhaul/LICENSE.txt) and
[THIRD_PARTY_NOTICES.md](home_dashboard_overhaul/THIRD_PARTY_NOTICES.md).
