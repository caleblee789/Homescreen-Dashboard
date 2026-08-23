# Home Screen Dashboard

Home Screen Dashboard 1.8.1 is a calendar-first, responsive Deck Browser
dashboard for Anki Desktop 26.8. It combines study history, due work, local
events, progress metrics, and a rotating Bible verse without patching Anki’s
private Deck Browser or statistics classes.

## 1.8.1 highlights

- Native 100% geometry uses a 1,480 px dashboard, a 430–450 px rail, compact
  Month rows, and an unframed Year heatmap with Mon/Wed/Fri references.
- The wide information architecture remains calendar left, four equal metric
  cards in a 2×2 rail right, and the Bible verse beneath both rail columns.
- Component-width rules move the rail below the calendar around 1,220 px and
  stack metric cards below about 640 px without horizontal scrolling.
- Calendar completion, today, selection, due work, and gold event markers have
  independent roles. Due work uses three presentation levels and selection is
  exactly one 2 px outline.
- True zero workload says `No cards due`. Statistics retain every defined row,
  use `—` for unavailable values, and apply category color only to positive
  values. ETA remains a permanent Today’s Session row.
- Selected-date events take precedence over the global next event; exact
  actions use `Reviewed cards` and `Due cards`.
- Native/default hosts stay transparent. A top-level scrim appears only when a
  real background image is detected.
- Configuration schema 7 retires only known ETA-visibility fields while
  preserving unrelated keys and all other settings.

## Install

1. Use the verified
   [`home-dashboard-overhaul-1.8.1.ankiaddon`](home_dashboard_overhaul/qa/release-evidence-1.8.1-2026-08-23/package/home-dashboard-overhaul-1.8.1.ankiaddon)
   from the 1.8.1 release evidence directory.
2. In Anki, choose **Tools → Add-ons → Install from file**.
3. Restart Anki and disable any legacy source add-ons identified by the
   activation card.

The manifest supports Anki Desktop 26.8 (`min_point_version` and
`max_point_version` 260800).

## Build and test

Use Python 3.10 or newer:

```sh
python3 -m unittest discover -s home_dashboard_overhaul/tests -p 'test_*.py' -v
node home_dashboard_overhaul/tests/calendar_model_test.js
python3 home_dashboard_overhaul/qa/validate_revised_ui_contract.py
python3 home_dashboard_overhaul/qa/color_system_audit.py --output home_dashboard_overhaul/dist/color-audit
python3 home_dashboard_overhaul/tools/build_ankiaddon.py
```

The deterministic builder creates a 24-file allowlisted archive, rejects unsafe
paths, fixes timestamps, and verifies source/archive byte parity. The 1.8.1
workflow also requires a second byte-identical build and exact-package native
Anki 26.8.1 validation in a fresh sync-disabled disposable profile.

The current machine-readable release contracts are:

- [`calendar_surface_manifest_1_8_1.json`](home_dashboard_overhaul/qa/calendar_surface_manifest_1_8_1.json)
- [`visual_regression_matrix_1_8_1.json`](home_dashboard_overhaul/qa/visual_regression_matrix_1_8_1.json)
- [`capture_evidence_manifest_1_8_1.json`](home_dashboard_overhaul/qa/capture_evidence_manifest_1_8_1.json)

The current
[`1.8.1 native release evidence`](home_dashboard_overhaul/qa/release-evidence-1.8.1-2026-08-23/README.md)
contains the complete 47-capture set, a full overview, 13 readable detail
contact sheets, the exact candidate archive, and the runtime reports. Restart
settings persistence is explicitly user-waived after the preserved calendar
view mismatch; it is not represented as passed.

The retained
[`1.8.0 release evidence`](home_dashboard_overhaul/qa/release-evidence-1.8.0-2026-08-23/README.md)
is immutable historical comparison material and is not 1.8.1 acceptance
evidence.

Dedicated 125%/150% captures, spoken screen-reader review, Windows/Linux,
forced-colors review, and OS-level scaling acceptance are deferred and must not
be inferred from the macOS 100% run.

## Project layout

- `home_dashboard_overhaul/`: packaged add-on source and user documentation
- `home_dashboard_overhaul/tests/`: behavior and release-contract tests
- `home_dashboard_overhaul/qa/`: machine-readable contracts, QA tools, and
  retained release evidence
- `deferred/calendar_sources_vnext/`: intentionally deferred external-calendar
  source excluded from 1.8.1

## License and notices

The add-on is licensed under AGPL-3.0-or-later. See
[`home_dashboard_overhaul/LICENSE.txt`](home_dashboard_overhaul/LICENSE.txt) and
[`home_dashboard_overhaul/THIRD_PARTY_NOTICES.md`](home_dashboard_overhaul/THIRD_PARTY_NOTICES.md)
for the complete license, Scripture notice, and upstream acknowledgements.
