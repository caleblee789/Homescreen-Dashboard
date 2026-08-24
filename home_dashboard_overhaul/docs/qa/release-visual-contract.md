# Release visual contract

Status: Home Screen Dashboard 1.8.3 native UI 100% release contract.

## Authority and retained history

The current machine-readable authorities are:

- `qa/calendar_surface_manifest_1_8_3.json`
- `qa/ui-surface-registry_1_8_3.json`
- `qa/visual_regression_matrix_1_8_3.json`
- `qa/capture_evidence_manifest_1_8_3.json`

The supplied 3420×2214 screenshot and the complete 1.8.0, 1.8.1, and 1.8.2
packages, reports, captures, and contact sheets are immutable calibration
history. They must not be overwritten or represented as new 1.8.3 evidence.

## Native UI 100% composition

- The dashboard is at most 1,240 px wide and leaves 66 px beneath its content
  for Anki's 42 px native controls plus a 24 px gap.
- Anki's actual `document.scrollingElement` owns vertical scrolling. The
  dashboard adds no nested vertical scroller, fixed or sticky positioning, or
  page-level horizontal overflow.
- Calendar and rail remain side by side from 1,040 px; the rail is at least
  372 px wide. From 420–1,039 px the calendar, auto-fitting metrics, and Bible
  stack. Below 420 px the narrow density uses one metric column.
- The footer has separate date, event, and action regions: one row from 760 px,
  two rows from 420–759 px, and three rows below 420 px. Dates and event titles
  wrap when needed.
- Year is fully visible without horizontal scrolling at 480 px and above.
  Below 480 px, Year alone uses a 580 px minimum internal region with 12 px
  edge padding, a 5 px scrollbar, and subtle edge fades. January, the current
  month, and December remain reachable; initial/Today centering and preserved
  manual scroll position are required.
- Month remains content-driven, including unequal five- and six-row heights.
  Bible growth, font scope, and disabled state do not determine Year height.

Representative container widths are 1240, 1100, 1040, 1039, 620, 479, 419,
320, and 319 px. Capture subtitles record native dimensions, container width,
computed density, and UI 100%.

## Meaning and visual states

- Today uses `Next event`. A selected date with an event uses `On this date`;
  one without an event uses `No event on this date`. The event action switches
  between `Edit event` and `Add event`; Reviewed and Due actions remain
  secondary.
- Progress uses one readable completion bar. Wide labels remain on one line,
  and values stay tabular and right-aligned.
- Month due strips remain inset, event markers retain safe top/right placement,
  and Year due indicators remain visible but restrained. Legend meaning does
  not change.
- Graphite owns slate interaction accents while New cards retain semantic blue.
  Emerald Dark uses the final neutral-green surface set. High Contrast remains
  opaque.
- Dashboard-owned surfaces may be transparent where designed, but `html`,
  `body`, the Deck Browser, native controls, and external pink/purple
  compatibility backgrounds are never altered.
- Initial and delayed skeleton geometry remains stable. Initial failure uses a
  400–440 px panel, 20 px padding, and 32 px actions. Retained-data refresh
  failure uses one full-width banner containing one `last_updated_at`
  timestamp.

## Minimal release gate

Run the repository's Python suite once and JavaScript suite once, with targeted
regressions only for footer meaning/actions, bottom clearance/no page overflow,
Year centering/scroll preservation, the single timestamped refresh banner, and
version/manifest/capture consistency.

Build `home-dashboard-overhaul-1.8.3.ankiaddon` once. Verify only version,
the 24-member allowlist, safe paths, successful exact-package loading, and
source/archive parity.

Install that exact archive in one fresh disposable sync-disabled Anki 26.8
profile. After identity confirmation, perform one bounded smoke pass and one
restart covering initial load, bottom scrolling, narrow footer readability,
January/current-month/December Year access, failure/retry timestamp behavior,
and Year-view persistence.

The new evidence package must contain 55 initial captures plus
`RUNTIME-RESTART-PERSISTENCE`, one overview, and 15 detail sheets. Every
capture ID appears exactly once in the detail sheets. Review the overview and
changed/critical captures; exhaustive pixel review of unchanged states is not
required.

## Deferred and unrun

VoiceOver, forced-colors, Windows/Linux, non-100% scaling, and OS-level scaling
acceptance remain deferred and must be reported as unrun and unclaimed.
