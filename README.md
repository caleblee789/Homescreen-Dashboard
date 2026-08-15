# Home Dashboard - Overhaul

Home Dashboard - Overhaul combines the useful home-screen information from five
local Anki add-ons into one responsive, configurable dashboard for Anki 26.8.

Version 1.5.3 uses a centered 1680 CSS-pixel full-screen canvas. Month becomes a
calendar-plus-details workspace at desktop width, while Year and smaller layouts
use one non-overlapping in-flow details panel. Native settings follow Anki's
palette and reflow from a 56/44 editor-preview split to a vertical workspace.
Compact date hover/focus previews show reviews and new cards studied for
current/past dates, then switch to due counts for future dates. Today contains
five rows—Total Cards Studied, New Cards Studied, Time studied, Pace, and ETA—
while Today’s Progress adds a thin segmented view of completed answers and the
live actionable queue plus five remaining-work rows. Local event management
remains on the existing Events settings page.

Selected-date details pair a compact contextual summary with an adaptive Study
Insight rail. Past dates show Completed Reviews and New Cards Studied, today adds
Cards Due, and future dates emphasize Cards Due. Today and past dates rank up to
three cards by complete scheduling-day `Again` answers, including every review
session before rollover;
future dates rank the three decks contributing the most due review cards. Trouble
cards show a plain-text question prompt, full deck path, and `Again ×N`. Browser
targets are retained by the controller, and the card action uses Anki's supported
`cid:` search without exposing card IDs to the webview. Empty days, successful
days without misses, deleted cards, disabled/out-of-range forecasts, and query
failures each have an explicit state. Events and **Manage this date** remain tied
to the selected civil-calendar date.

Partial collection failures render as unavailable instead of plausible zeroes,
and hiding every Home section leaves a small keyboard-reachable recovery card.
Year keyboard movement follows the visual and accessibility grid, contextual
Settings previews expose only actions that can work inside a preview, and manual
verse rotation has an explicit staged current-verse action.

The dashboard has one canonical Deck Browser renderer with two surfaces:

1. a Study Calendar card with Month/Year views, completed-review intensity, due
   forecast, adaptive full-day insights, event markers/details, and compact
   Today, Today’s Progress, Buried Cards, and Consistency metric groups; and
2. a rotating Bible verse card directly below it.

Year is the first-run view. The last Month/Year choice persists independently of
analytics, while each new Anki session returns the viewed period to today.

The implementation is intentionally independent of the five source add-ons. It
does not modify, move, or delete them. On first run it reads their effective
settings and event/rotation data where available, stores a local migration
snapshot, and keeps its dashboard inactive until the legacy add-ons are disabled.

## Build and test

Use Python 3.10 or newer for the complete zero-skip suite. Python 3.9 can run the
active-package tests but skips the deferred iCalendar dependency cases.

```sh
python3 -m unittest discover -s home_dashboard_overhaul/tests -v
node home_dashboard_overhaul/tests/calendar_model_test.js
python3 home_dashboard_overhaul/tools/build_ankiaddon.py
```

The build script produces a deterministic, allowlisted archive in
`home_dashboard_overhaul/dist/` and immediately verifies every archived byte.
The 1.5.3 distribution contains no external-calendar UI, runtime, vendored
dependencies, or source registry. The repository retains that future work under
[`deferred/calendar_sources_vnext/`](deferred/calendar_sources_vnext/) and in
source-only QA modules and fixtures beside the active source, including
`calendar_*.py`, `event_manager.py`, `vendor-requirements.lock`, and `_vendor/`.
None is imported by the active integration or included in the package allowlist;
the package validator rejects every deferred module and `_vendor/` entry.

## Release acceptance

Version 1.5.3 is the accepted automated release candidate. Its sole canonical
release-status record is
[`docs/release_acceptance_1.5.3.md`](docs/release_acceptance_1.5.3.md). The
deterministic archive has SHA-256
`68705bc06dabd277130600f14db0c8dc907dc3b39177778a784aaaa275d01dee`.
Exact-package Calendar, Settings, and Insights acceptance passed across 61 raw
captures in three fresh, sync-disabled Anki 26.8.1 profiles, initially and after
controlled restart. The canonical reports, archive, screenshots, and 20 review
sheets are retained under
[`home_dashboard_overhaul/qa/live-ui-acceptance-1.5.3-release-2026-08-15/`](home_dashboard_overhaul/qa/live-ui-acceptance-1.5.3-release-2026-08-15/).
Automated accessibility checks passed; a spoken VoiceOver listening pass remains
human-required and is not claimed complete.

The rejected 1.5.2 candidate and its failure are retained in
[`docs/release_acceptance_1.5.2.md`](docs/release_acceptance_1.5.2.md). Earlier
machine-local QA runs remain available in the development workspace but are
intentionally excluded from repository publication. Their hashes and pass labels
must not be used to accept 1.5.3; the sanitized 1.5.3 bundle above is the only
canonical live evidence.

Today’s Progress is display-only. Its rows are Percent Complete, New remaining,
Learning remaining, Reviews remaining, and Total remaining. Its percentage is
completed answers divided by completed answers plus the current New, Learning,
and Review queues. Buried cards remain visible only in their separate group and
never affect progress, total remaining, or ETA.

The insight rail is derived directly from `revlog` and the current cards table.
It adds no session recorder, persistence file, migration, or configuration field;
configuration remains schema 3. Insights are loaded on demand and cached only for
the active profile/data generation, while the contextual summary is available
immediately from the normal calendar snapshot.

## Compatibility

The release target is Anki Desktop 26.8. The add-on uses the current Deck Browser
render hook, background collection operations, namespaced web assets, and one
strictly scoped webview command channel. It does not patch private Deck Browser or
statistics classes.

## Source references and licensing

The five preserved source copies and their baseline hashes are documented in
[`docs/reference_baseline.md`](docs/reference_baseline.md). This project is
licensed under AGPL-3.0-or-later. See
[`home_dashboard_overhaul/THIRD_PARTY_NOTICES.md`](home_dashboard_overhaul/THIRD_PARTY_NOTICES.md)
for acknowledgements and data notices.
