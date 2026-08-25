# Release visual contract

Status: Home Screen Dashboard 1.8.6 canonical UI release contract.

## Authority and retained history

The current machine-readable authorities are:

- `qa/calendar_surface_manifest_1_8_6.json`
- `qa/ui-surface-registry_1_8_6.json`
- `qa/visual_regression_matrix_1_8_6.json`
- `qa/capture_evidence_manifest_1_8_6.json`

The supplied 3420×2214 screenshot and complete 1.8.0 through 1.8.5 packages,
reports, captures, and contact sheets are immutable calibration history. They
must not be overwritten or represented as new 1.8.6 evidence.

## Production composition

- The dashboard is at most 1,120 px wide, starts 24 px below the document top,
  and retains at least 20 px side margins.
- Anki's actual document scroller owns vertical movement. The dashboard adds
  no viewport-height root, root overflow clipping, fixed/sticky positioning, or
  page-level horizontal overflow.
- A visible fixed/sticky Anki bottom-action container is detected without
  localized button text and observed for resize. Root bottom padding and
  document scroll padding equal its measured height plus 24 px, using 60 px
  only as the missing-height fallback.
- Month is always a 42-cell, six-week grid. Completion fill, selected overlay,
  today's 2 px outline, due marker, and event diamond remain independently
  visible.
- Year is always a real 53-week grid with a 28 px weekday column and fluid week
  columns. Below 760 px its label column and gaps compact so the full grid stays
  inside the dashboard at 480 px and above; below 480 px only the heatmap may
  scroll internally.
- Month and Year share one header and identical outer-card width. The compact
  footer conditionally omits disabled due/event legend groups and event summary.
- Per-cell and secondary-card shadows are absent. The calendar card retains one
  restrained outer shadow and one-pixel boundaries.

Production captures cover Month/Year, stable switching, all semantic marker
combinations, every theme's four palette choices in light and dark, white,
black, purple, and image host backgrounds, sections below the calendar, and
bottom-scrolled clearance above Anki's native actions.

## Settings composition

- One native Qt tree owns all widths: compact header, fixed 152 px rail, one
  page scroller, and final-row footer. No WebEngine content is embedded.
- The resizable dialog targets 1200×800. A minimum up to 1040×700 is enforced
  when the screen permits, and the initial size is clamped to available
  geometry so the footer remains onscreen. The inner shell is centered and
  capped at 1,240 px; no geometry is persisted or positioned manually.
- Production opens a normal `QDialog(mw)` synchronously with `exec()` and
  default flags. Sidebar navigation only changes the native stacked page; it
  creates no timer, WebView, secondary window, or focus hook.
- The rail paints exactly one active row, legacy Calendar routing aligns the
  Calendar display card without exposing a preceding-card sliver, and the
  About lead cards share a matched visual row.
- Settings chrome follows only Anki's light/dark appearance. Application font
  scaling relies on font-relative roles and control minimums based on line
  height plus padding.
- Event, verse, and deck lists have no internal vertical scrollbars; their rows
  belong to the main page scroller. Verse loading remains incremental.

Settings captures cover all four pages at 1040, 1200, and full-screen widths;
100% and 150% application fonts; required Events/Bible/About states; dirty,
revert, save, and error states; legacy routing; standard/clamped windows; and
restart.

## Persistence and meaning

- Schema remains 8. The only persisted config-domain expansion is
  `events.sort = "name"`.
- Existing completion-palette IDs and per-theme selections remain stable.
- Settings size remains unpersisted and there is no preview preference.
- `SettingsDraft`, staged changes, three-way merge, dependency retention, and
  list-as-one-field dirty counting remain authoritative.
- Saving validates all staged state before either write, disables Save while
  active, updates the baseline only after complete success, and uses
  best-effort rollback plus a specific inline error after partial failure.
- Legacy Calendar routing activates Dashboard, settles on Calendar display,
  and preserves staged values.
- Saved configuration is loaded before the first production render.

## Release gate

Pass the Python and JavaScript suites, compilation, manifest/assets checks,
`git diff --check`, source/archive parity, safe-path inspection, and secret/link
audits. Build `home-dashboard-overhaul-1.8.6.ankiaddon` reproducibly.

Install that exact hash into one fresh disposable sync-disabled Anki 26.8
profile. Prove process, window, filesystem, and sync isolation before
interaction, then repeat all four gates after one controlled restart.

The implementation-derived evidence contract contains 94 native captures: 92
initial production/Settings states and two controlled-restart states. Every
capture ID must appear exactly once in validated contact-sheet coverage.

Only after local gates, exact-package QA, restart persistence, visual review,
and GitHub checks pass may the release PR be squash-merged.

## Deferred and unrun

VoiceOver, Windows, Linux, forced-colors, DPR 1, and OS display-scaling
acceptance remain deferred and must be reported as unrun and unclaimed unless
separately executed.
