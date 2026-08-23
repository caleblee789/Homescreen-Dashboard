# Release visual contract

Status: final 1.8.0 offline implementation contract. This document defines the
source and package gates for the release; it does not claim live Anki, human
accessibility, or cross-platform acceptance.

## Authority

The machine-readable authorities are:

- `qa/calendar_surface_manifest.json`: 25 canonical surfaces and 42 required
  finalization criteria.
- `qa/ui-surface-registry.json`: exact-once ownership and fixture mapping.
- `qa/visual_regression_matrix_1_8_0.json`: the exact 96-case product matrix of
  four themes, light/dark mode, Month/Year, compact/wide, and 100/125/150% text.

The immutable `qa/live-ui-acceptance-1.5.3-release-2026-08-15/` directory is a
historical comparison baseline only. It must not be changed, regenerated, or
presented as evidence for 1.8.0.

## Required composition

- Month and Year use one shared calendar-and-insight shell. At 940 CSS pixels
  and wider, the calendar sits beside a fixed-order 2×2 metrics grid and Bible
  card; at 440–939 pixels the insight rail follows the calendar; below 440
  pixels the metrics use one column.
- The calendar footer is one integrated surface containing distinct Completion,
  Reviews Due, and Event legend groups; selected-date context; the next event
  and edit action; and only the exact Browser actions applicable to that date.
- Card previews, the large selected-date panel, due-deck lists, a separate
  selected-date events column, and reserved layout slots for those surfaces are
  prohibited.
- Year renders the complete January-through-December week grid with readable
  month labels and uses only an internal scroller below its minimum width.
- Settings retains the four-page responsive shell, staged changes, production
  previews, per-row event actions, and explicit Theme color versus Custom color
  handling.

## Color and state contract

- Sapphire Glass, Graphite, Emerald, and High Contrast each provide complete
  light and dark token sets for canvas, three surface levels, borders, text,
  controls, focus, shadows, progress, and calendar overlays.
- New, Learning, Review, Buried, Success, Warning, Danger, and Event semantics
  remain stable across themes. The active theme accent is reserved for theme
  identity and primary interaction emphasis.
- Completion uses six explicit opaque levels with level-specific readable date
  text. Reviews Due uses five explicit soft violet backgrounds plus a stronger
  fixed-height bottom marker. It must remain distinguishable without hue alone.
- Today, Selected, keyboard focus, adjacent-month status, completion, Reviews
  Due, and Event are independent layers. Combined states must retain every
  applicable cue.
- Components consume semantic variables. Unclassified component-level color
  literals, blanket disabled opacity, brightness filters, and diffuse colored
  card glows fail the release gate.
- The active theme paints `html`, `body`, the dashboard host, its scroll surface,
  unused viewport space, and overscroll before dashboard content is visible.

## Automated release gate

The 1.8.0 release requires:

- the complete Python and JavaScript suites;
- `qa/validate_revised_ui_contract.py` passing the exact 25/42/96 contracts;
- `qa/color_system_audit.py` reporting zero unclassified component colors and
  no failed contrast pair;
- source compilation and valid JSON/Markdown links;
- a deterministic 24-file `.ankiaddon` with safe paths, fixed timestamps,
  manifest/version consistency, checksum verification, and source/archive byte
  parity;
- absence of QA tools, generated evidence, deferred calendar modules, local
  user data, caches, credentials, and machine-specific paths from the archive;
- `git diff --check` and the final repository secret/path review.

The retained 100%-scale reference images may be composed into contact sheets
offline. Their metadata must state their provenance and cannot describe the
1.8.0 archive as live-tested unless the image was captured from those exact
bytes.

## Explicitly unverified

The 1.8.0 workflow does not launch Anki. It therefore does not claim live
startup, native WebView behavior, restart persistence, spoken VoiceOver,
Windows/Linux rendering, operating-system forced colors, device-specific
behavior, or non-100% operating-system display scaling. These remain separate
acceptance gates and must stay unchecked in release reporting.
