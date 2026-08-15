# Changelog

## 1.5.3 — 2026-08-15

- Fixed first-load, reload, and restart insight requests by waiting for Anki's
  asynchronous webview command bridge before dispatch, starting the response
  timeout only after dispatch succeeds, and returning to a retryable unavailable
  state if the bridge never becomes ready within the bounded wait.

## 1.5.2 — 2026-08-13

- Added an intentional all-hidden Home state with a keyboard-reachable settings
  recovery action instead of an empty dashboard.
- Made partial Today, queue, buried, history, and forecast failures render as
  unavailable rather than real zeroes; technical exception text no longer
  appears in the primary UI, and selected-date summaries reconcile insight and
  forecast availability.
- Split fill and text-safe accent/status tokens, made 70% card compositing
  deterministic, protected Month date-number contrast, removed adjacent-date
  opacity, preserved configured verse sizes on narrow windows, and removed the
  no-op Background blur control while retaining its stored schema key for
  backward-compatible configuration.
- Corrected Year arrow-key movement to follow the seven-row visual/ARIA grid and
  retained Month behavior, focus restoration, and period navigation.
- Made Settings previews explicitly noninteractive for Deck Browser-only
  settings, Browse, Manage, and insight requests, eliminating dead actions and
  indefinite loading states while keeping local calendar controls usable.
- Added a staged **Use selected as current** action for manual verse rotation,
  restart-safe explicit selection, unavailable-font preservation, luminance-based
  custom-color feedback, expanding event fields, singular streak copy, and
  bounded verse entry/import handling.
- Added the complete NLT/Tyndale Scripture notice to the package and About page,
  and clarified that Scripture text is outside the add-on's AGPL license.
- Bound calendar acceptance to independently hashed package bytes and sidecar,
  rejected self-certified historical reports and warnings/errors/incomplete
  gates, pinned responsive geometry regressions, and captured editors at their
  real default/minimum sizes. Spoken VoiceOver remains a human-only boundary.

## 1.5.1 — 2026-08-13

- Rebuilt all six settings sections around a pure conflict-aware draft model,
  grouped responsive navigation, a fixed action bar, clean/dirty feedback,
  discard recovery, safe section resets, and unknown-key-preserving merges.
- Made the editor and both content dialogs follow the staged dashboard preset
  and mode, with production-rendered contextual previews, cached/sample and
  Updates-after-Save disclosure, selected-verse snapshot cloning, and no
  ordinary-preview collection queries.
- Redesigned Home screen dependencies, Calendar history/forecast/cleanup/deck
  exclusion controls, staged Events actions, duplicate-aware bounded verse
  imports, and manifest-driven About/privacy/migration/rollback cards while
  retaining schema 3, local-event, rotation, bridge, and analytics semantics.
- Added a contextual selected-date summary: past dates show Completed Reviews
  and New Cards Studied, today adds Cards Due, and future dates emphasize Cards
  Due, with a single polite spoken summary for assistive technology.
- Kept all full-day insights bounded, cached, on demand, and stale-response safe;
  Browse retains controller-cached card targets when available and otherwise uses
  the established `open_day` bridge with a validated date-scoped query.
- Added calendar-specific typography, geometry, spacing, control, and state
  tokens; improved Year cell proportions, label alignment, month rhythm, legend
  legibility, responsive Month cues, and bounded hover/focus previews.
- Clarified Calendar settings into Display, Range & Forecast, History Rules, and
  Deck Exclusions, including explicit disabled states, exclusion counts, and
  unambiguous filtered bulk actions.
- Polished local Events with localized display dates, empty/selection guidance,
  contextual Add actions, primary/destructive hierarchy, and accessible staged
  action feedback; empty tables no longer show native alternate-palette phantom
  rows, and disabled destructive actions are visually neutral. Archive, restore,
  auto-archive, and delete-confirmation behavior remain unchanged.
- Added a fail-closed 24-surface QA manifest, internal geometry/render hooks,
  report validation, and expanded contextual, responsive, safe-text, contrast,
  focus, and persistence coverage without changing schema 3 or dependencies.

## 1.5.0 — 2026-08-13

- Replaced duplicate selected-date completed/due tiles with an adaptive Study
  Insight rail while preserving the date heading, Events, navigation, and
  **Manage this date** action.
- Added complete scheduling-day `Again` aggregation directly from `revlog`, ranking up to
  three available cards by miss count, latest miss, and card ID across sessions
  and restarts; Hard and other ratings do not count as misses.
- Added sanitized 160-character question prompts, full deck paths, `Again ×N`,
  controller-owned `cid:` Browser targets, and explicit zero-study, no-miss,
  deleted-card, no-due, and unavailable states.
- Added future-date due-deck ranking with deck exclusions and forecast limits,
  plus validated on-demand background requests cached per profile/data generation
  with stale-response rejection.
- Preserved scheduling-day rollover, history/forecast limits, manual-reschedule
  behavior, configuration schema 3, and a persistence-free implementation.
- Renamed the visible Remaining group to Today’s Progress while retaining the
  existing `visibility.remaining` configuration key and schema 3 compatibility.
- Added a thin, textless Completed/New/Learning/Review bar based on current
  scheduling-day answers and the live actionable queue, with whole-number completion.
- Added neutral empty/unavailable states, complete progressbar semantics, and
  High Contrast separators and segment patterns without interaction or animation.
- Kept ETA in Today beside Total Cards Studied, New Cards Studied, Time studied,
  and Pace; Today’s Progress remains a five-row display of remaining work.
- Kept buried-card counts exclusively in the separate Buried Cards group and
  excluded them from progress, percentage, total remaining, and ETA.
- Preserved Year’s four-group row and Month’s 2×2 rail, with literal vertical
  label/value rows at narrow and zoomed sizes.
- Expanded renderer, accessibility, responsive asset, compatibility, and package
  regression coverage for the new progress presentation.

## 1.4.0 — 2026-08-13

- Moved the daily new-card count into Today as New Cards Studied and renamed the
  total row to Total Cards Studied.
- Replaced the rolling/custom New Cards Introduced group with collection-wide
  buried New, Learning/relearning, and Review counts.
- Added a local clock-time ETA using lifetime pace until ten answers today,
  today's pace thereafter, and empirical lifetime first-answer timing for new cards.
- Migrated configuration to schema 3 and removed obsolete pace-lookback,
  fixed-multiplier, period-summary, and custom-search controls.
- Updated calendar history, hover/focus copy, accessibility labels, and previews
  to use New Cards Studied terminology while preserving the responsive layout.

## 1.3.1 — 2026-08-13

- Added one compact hover/focus preview for every calendar date: current and
  retrospective dates show completed reviews plus new cards introduced, while
  prospective dates show cards due.
- Added per-day new-card introduction counts to the cached activity snapshot,
  using Anki study-day boundaries and the existing rescheduled-card preference.
- Removed the rollover disclaimer from date details and documented study-day
  versus civil-calendar behavior on the Calendar settings page.
- Renamed the Introduced metric and settings group to New Cards Introduced.

## 1.3.0 — 2026-08-13

- Expanded the dashboard to a centered 1680 CSS-pixel canvas with responsive
  outer padding and no minimum-width calendar overflow.
- Replaced the floating date popover and fixed narrow sheet with one reusable,
  non-modal details structure in normal document flow.
- Added a full-screen Month workspace with a two-thirds calendar and one-third
  persistent details rail; Year and sub-1180 px layouts use inline details.
- Retained Month selections by day number across navigation with destination-month
  clamping, and initialized the desktop rail to today or the first in-month date.
- Reserved independent Month date and event rows, restored two event chips plus
  accurate `+N` overflow, and added compact marker counts below chip capacity.
- Separated today, selection, focus, intensity, due hatching, and event shape cues;
  strengthened due bands to six pixels and enforced preset text/control contrast.
- Reflowed statistics at 1180 and 720 px, limited verse reading measure to 64
  characters, and added bottom scroll clearance for Anki's toolbar.
- Made settings and editors follow Anki's application palette with native checkbox
  glyphs and explicit focus, disabled, selected, and destructive states.
- Added a 56/44 desktop settings split, vertically stacked narrow editing, grouped
  Dashboard controls, columnar event management, a wider resizable event editor,
  full selected-verse reading, and structured integration/legal information.
- Expanded pure JavaScript, renderer, static, configuration, and contrast regression
  coverage while retaining configuration schema 2 and all bridge/cache contracts.

## 1.2.0 — 2026-08-13

- Stabilized review-intensity levels across Month and Year and added weekday and
  less-to-more guidance to the Year heatmap.
- Compacted Month view and strengthened independent current-day, due-pattern,
  and event-shape cues across standard and High Contrast themes.
- Added explicit scheduling-day rollover context to calendar details.
- Made narrow date details viewport-safe with internal scrolling and sticky actions,
  plus complete Home, End, Page Up, Page Down, arrow, Enter, Space, and Escape behavior.
- Reworked settings for responsive scaling, cached live-data preview, searchable
  deck/event managers, clearer dependent controls, and readable standalone editors.
- Improved event and Bible library counts, filtering, sorting, typography controls,
  long-name feedback, semantic About content, and theme contrast.
- Added lifecycle, accessibility, rollover, stable-threshold, preview, and responsive
  regression coverage while retaining configuration schema 2.

## 1.1.0 — 2026-08-13

- Replaced six stacked dashboard sections with one compact Study Calendar card
  and one Bible Verse card.
- Added a conventional Month view alongside the complete Year heatmap and
  restart-safe last-view persistence.
- Integrated active events as shape-marked calendar data, including two event
  chips plus `+N` overflow in Month view.
- Added accessible selected-date details with completed, due, all events,
  Browse cards, and direct Manage events actions.
- Moved every nonduplicate metric into four dense groups beneath the calendar.
- Added configurable week starts, period-aware keyboard navigation, responsive
  popover/sheet behavior, and compact error presentation.
- Upgraded configuration to schema 2, retired Continuous 9 Months, and separated
  render preferences from the collection analytics cache key.
- Added dependency-free JavaScript calendar-model coverage and expanded renderer,
  event-safety, migration, and cache regression tests.

## 1.0.0 — 2026-08-13

- Added one modern Deck Browser surface for five formerly separate add-ons.
- Added async collection analytics and profile-generation cache invalidation.
- Kept completed reviews and due forecast as independent per-day values.
- Removed reciprocal/derived duplicate metrics and clarified labels.
- Added active/archive event management and non-destructive legacy migration.
- Added restart-safe daily/manual/every-render Bible verse rotation and safe HTML.
- Added twelve light/dark preset palettes and responsive, accessible controls.
- Added a staged multi-page settings editor in the shared Caleb M. toolbar menu.
