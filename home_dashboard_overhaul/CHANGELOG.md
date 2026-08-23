# Changelog

## 1.7.0 — 2026-08-21

- Completed the second-pass Settings release audit: the editor now uses a true
  header/body/footer grid, contrast-safe native controls with vector select
  chevrons, keyboard-operable segmented choices, compact painted switches, and
  bounded intermediate fields that reflow safely at 150% application text.
- Reorganized the combined Dashboard into Appearance, Content & study metrics,
  and Calendar & data; separated visible sections from study calculations; and
  repaired legacy Calendar routing so the complete target heading remains in
  view after responsive layout settles.
- Replaced fixed preview canvases with content-sized Current section / Full
  dashboard and Fit / Actual size previews. Bible preview uses the selected
  staged verse without sample-data copy, while Dashboard labels deterministic
  fallback facts only when live collection facts are unavailable.
- Moved event actions into per-row overflow menus, added a centered empty state,
  made the verse library incremental, collapsed inactive custom-color controls,
  and removed empty minimum height from About cards.
- Added component-shaped loading skeletons, delayed and retryable failure states,
  a diagnostics route, and controlled-restart QA that waits for the finished
  dashboard before proving calendar view, week start, palette, visibility, and
  migration-preserved local data.

- Replaced the large selected-date details workspace with a compact Calendar
  context bar shared by Month, Year, narrow layouts, and the production Settings
  preview. It distinguishes the selected date, an event on that date, and the
  globally calculated next event; supports direct exact-event editing; keeps
  Reviewed or Due visible for the appropriate date type with an explanatory
  disabled state when no exact cards exist; and reveals Most missed only after
  an eligible Again answer.
- Removed the dashboard card-preview list, due-deck breakdown, separate events
  column, per-row Browser actions, expansion control, settings toggle, layout
  slot, preview data, and eager card-content loading. Most-missed IDs are now
  resolved only after an eligible date is selected and retain Again-count,
  total-answer, and stable-card-ID ordering in the Browser.
- Enforced omission-based rendering for unsupported metrics and tooltip rows.
  Tooltips now use the date as their heading, distinguish Completed reviews/New
  cards studied from Reviews due/New cards due, use locale formatting and plural
  rules, open on hover or keyboard focus, and remain collision-aware and pointer
  inert.
- Added 16 independent theme-specific completion ramps with authored light/dark
  empty, five intensity, foreground, and outside-month tokens. Calendar & data
  uses visual preset cards and remembers one ramp per theme.
- Made the quiet due band encode relative load using the 90th percentile of
  positive full-horizon counts and square-root scaling. Low, medium, and high
  density/opacity remain legible without letting one outlier flatten the
  forecast, and the due legend stays separate from completion intensity.
- Clarified calendar state ownership and enlarged the outlined diamond event
  marker. Today, selection, focus, out-of-month, completion, due, and event
  states no longer compete for the same border or fill.
- Moved the four metric groups above the Bible, added Last 7 Days New cards
  studied, and made Month use a 2×2 metric rail beside the calendar at 1,320 px
  and wider, a 2×2 grid below it at intermediate widths, and one card per row at
  narrow widths. Year stays full width with square cells and visible month
  labels. Values are locale-separated and tabular; ETA is neutral and retention
  remains target-aware.
- Rebuilt Today’s Progress as an exact-count four-segment workload bar for
  completed, New, Learning, and Review counts, with half-up completion rounding
  and buried cards kept outside the workload and Total remaining.
- Added a stable page scrim and a 91% effective opacity floor for text-bearing
  panels so user-selected background transparency cannot reduce readability.
- Rebuilt Settings preview around the production renderer with contextual and
  full-dashboard controls. Wide, intermediate, and narrow modes reuse one field
  structure; preview visibility no longer replaces navigation; custom Bible
  color uses a hex field plus swatch; and the footer occupies its own grid row.
- Upgraded configuration to schema 6 with an idempotent removal of stale
  selected-details/card-preview slots, canonical calendar/metrics/Bible order,
  per-theme heatmap choices, and a configured retention target.
- Aligned buried-card counts with scheduler-relevant Progressbar semantics,
  excluding suspended and future buried cards while distinguishing integer-day
  and timestamp learning due values.
- Replaced the superseded selected-panel release fixtures with a 28-criterion
  corrected UI contract and an exact 96-state visual-regression matrix covering
  four themes, two modes, Month/Year, compact/wide, and 100/125/150% text scale.

## Superseded 1.7.0 candidate — 2026-08-15 (not shipped)

- Upgraded configuration to schema 5, kept Layout Density retired, reduced the
  appearance system to Sapphire Glass, Graphite, Emerald, and High Contrast, and
  made every removed, legacy, malformed, or unknown palette persist as Sapphire
  Glass. Top/Bottom Home Screen Position remains restart-safe, Panel Opacity
  remains background-only at 70–100 with an 88 default, and missing or invalid
  verse rotation safely defaults to Daily without changing explicit choices.
- Added complete semantic palette roles and automated contrast/color-distance
  gates for Completion, Review, Success, Forecast, Event, Danger, selection,
  focus, buttons, and heatmap intensity. Sapphire retains its approved base
  palette, Emerald separates Accent from Review and Success, and High Contrast
  retains the CAL-05/INS-11 non-color patterns and shapes.
- Anchored both Home Screen Position choices below Anki's native deck list: Top
  now means first among injected add-on panels only, while native bottom actions
  remain in their separate unchanged bar.
- Rebuilt Settings responsiveness so only the extra-wide composition uses the
  sidebar; intermediate and minimum widths use the section selector and optional
  preview. The preview pane now follows measured dashboard content instead of a
  fixed split, and preview provenance badges were removed.
- Replaced flat deck exclusions with a collapsed cascading tri-state hierarchy,
  ancestor-preserving search, visible-match bulk actions, minimal-root storage,
  and removable unavailable deck identifiers.
- Reworked Events around Search, contained sort choices, Active/Archived tabs, a
  compact Add Event action, a full-width list, wrapping contextual actions, and
  destination-tab reselection with staged archive/restore feedback.
- Simplified About to manifest-derived product, version, supported Anki, license,
  privacy, Scripture, neutral help, third-party notices, and recovery guidance.

- Replaced renderer-side numeric defaults and reconciliation with one typed
  dashboard-facts authority for Calendar, tooltips, selected-date details,
  filtered statistics, exact Browse targets, and saved Settings previews.
- Reorganized statistics into Today’s Progress, Today’s Session, Last 7 Days,
  and All-Time. Last 7 Days contains exactly Cards studied, Retention, and Again
  rate; All-Time adds Avg cards/day, Active days, both streaks, Lifetime
  retention, and Lifetime cards studied. Buried counts remain a compact
  non-workload summary within Today’s Progress.
- Made the scheduler cutoff authoritative for Today, streaks, due work, and
  navigation; applied one deck-exclusion scope to Calendar, details, Today,
  Today’s Progress, Today’s Session, Last 7 Days, All-Time, buried summaries,
  Browse, and Settings previews; and added exact targetless states for deleted,
  no-history, and no-due results.
- Unified Reviews due, progress, percentage, ETA, tooltips, Browse, and previews
  on scoped raw scheduled demand without reducing review counts for daily limits.
- Added coalesced revisioned refreshes for answers and collection operations,
  explicit Settings/event invalidation, stale-result rejection, retained-data
  updating states, retry handling, and a single daily-rollover timer.
- Replaced Month breakpoint cliffs with measured intrinsic composition and added
  a capacity-driven 12-month Year layout with unique dates, cross-boundary
  keyboard navigation, and one persistent movable details component.
- Replaced every in-cell event title/count treatment with one accessible plain
  diamond while retaining complete inert event names in tooltips, details, and
  management.
- Made selected-date details persistent with the current scheduling day selected
  by default; removed the current-day summary boxes; and replaced question
  snippets with a compact three-row Most Missed list using normalized text-only
  answer summaries, bounded front/image/equation fallbacks, deck breadcrumbs,
  right-aligned Again counts, one four-line disclosure, and controller-owned
  per-card Browser actions. Source HTML, CSS, scripts, controls, and dimensions
  cannot style or execute inside the dashboard.
- Replaced Settings sample figures with a saved-data preview contract: staged
  appearance, layout, visibility, events, and verse changes remain visible,
  while collection-backed figures use the canonical Home snapshot and remain
  explicitly unavailable before Home has loaded one.
- Updated the event-name helper and About surface with release-accurate,
  privacy-forward copy, neutral project/support links, complete third-party
  attribution, and rollback guidance without internal implementation details.
- Added a deterministic, fail-closed candidate scenario contract for the full
  stable surface registry, including Most Missed safety/responsiveness, all four
  themes, supported opacity/background contexts, restart, and schema-5 fixtures.
- Added separate pending-contract and completed-evidence validation for the
  exact-once candidate set; release mode verifies exact package bytes, every
  registered raw capture, per-state and interaction reports, complete indexed
  contact sheets, fixture identity, and the pinned immutable-baseline digest.

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
