# Changelog

## Unreleased

## 1.8.2 — 2026-08-23

- Rebuilt the 100% dashboard around a 1,320 px maximum, 16 px minimum side
  margins, 22 px top spacing, 12 px component gaps, and 72 px native-footer
  clearance. Calendar and rail heights are independent; Month stays naturally
  five or six rows and Year remains content-driven.
- Replaced the 1,220/900/640 responsive thresholds with container breakpoints
  at 940 and 440 px. The rail is side by side at 940 px and above, a 2x2 grid
  from 440–939 px, and one column below 440 px. Only Year scrolls internally
  below 320 px.
- Corrected Month and continuous 53-column Year state layering, neutral future
  cells, due strips, event markers/counts, legend, compact footer, adjacent
  event pencil, tonal card action, and collision-aware 190–220 px tooltip.
- Replaced the segmented workload visualization with one 14 px completion bar
  and explicit `No cards scheduled`, `All clear`, `100% complete`, active
  percentage, and unavailable states.
- Finalized the four metric cards. The scheduler-authoritative current buried
  total moved into Today’s Session beside Cards studied, New cards studied,
  Time spent, Pace, and ETA; `visibility.buried` was retired.
- Added compact time/ETA display, stable large-number handling,
  content-responsive Bible sizing, intentional fresh/empty/complete fixtures,
  and retained-data refresh failure with Retry. Initial and live rendering now
  consume the same presentation fields.
- Centralized theme and semantic tokens. Sapphire Glass alone applies
  component translucency and real backdrop blur; Graphite, Emerald, and High
  Contrast remain opaque, with no High Contrast decorative shadow. Host
  wallpaper and Anki chrome remain unpainted and unmodified.
- Upgraded configuration to schema 8. Opacity now normalizes to 94–100 with a
  96 default, blur to 0–16 px with a 12 px default, and both controls disable
  outside Sapphire Glass. Migration clamps schema-7 values, removes
  `visibility.buried`, preserves unrelated settings, and retains valid stored
  Month/Year choice from first render through hard restart.
- Expanded the fail-closed 100% release contract to nine exact widths and 48
  native captures, including `RUNTIME-RESTART-PERSISTENCE`, one overview, and
  13 detail sheets. Retained 1.8.0/1.8.1 evidence and the supplied screenshot
  remain immutable calibration history.

## 1.8.1 — 2026-08-23

- Recalibrated the native 100% Deck Browser layout to a 1,480 px maximum
  dashboard, a 430–450 px statistics rail, 16 px shell gaps, compact 44–48 px
  Month rows, and an unframed Year heatmap with readable week-aligned month
  labels and Mon/Wed/Fri references. Container-width rules now move the rail
  below the calendar near 1,220 px and use one card per row below 640 px.
- Replaced competing calendar rings with one Today capsule or Year marker and
  one 2 px selection outline. Completion remains the historical fill, due work
  now maps the existing percentile reference to three presentation levels, and
  2/4/6 px Month indicators can coexist with today, completion, selection, and
  gold event markers.
- Rebuilt the integrated footer around selected-date event precedence, the
  exact `Event on this date` and `Next event` relationships, grouped title/date/
  countdown/edit content, ellipsis-safe long titles, event counts, and the
  shorter `Reviewed cards` and `Due cards` actions.
- Made all statistics cards structurally stable across fresh, populated, zero,
  completed, and partially unavailable data. True zero workload now reads
  `No cards due`; Today’s Session always exposes Cards studied, New cards
  studied, Time, Pace, and ETA; unavailable rates and estimates render `—`; and
  semantic category colors apply only to positive values.
- Added one shared progress presentation state for initial Python render and
  live JavaScript updates. `Done` is now limited to completed nonzero workload,
  while the exact-count Completed/New/Learning/Review bar and buried-card
  exclusion remain unchanged.
- Preserved the Bible font-size preference through a safe 15–19 px responsive
  mapping, improved long-verse sizing and dark reference clarity, and removed
  the entire rail gap when the Bible card is disabled.
- Refined Sapphire, steel-accent Graphite dark, neutral-valued Emerald, and
  fully opaque High Contrast through the existing semantic token system.
  Native/default hosts remain transparent; a top-level scrim is activated only
  when a real or deliberately injected QA background image is detected.
- Upgraded configuration to schema 7. The retired `study.show_eta`,
  `study.show_estimate`, and legacy `ShowTimeLeft` inputs are dropped while
  unrelated unknown keys and all other saved preferences remain intact; ETA is
  now a permanent Today’s Session row.
- Added a 100%-only 1.8.1 native evidence contract with 16 mandatory
  theme/mode/view Deck Browser frames and tagged supplemental coverage. The
  prior 1.8.0 evidence and the user-supplied native geometry reference remain
  immutable calibration history.
- Fixed the Today’s Progress Buried total by reconciling cards already in
  queues -2/-3 with due siblings Anki omits from its authoritative reviewer
  queue, matching the accurate Progressbar counting model.

## 1.8.0 — 2026-08-23

- Rebuilt the calendar footer as one integrated surface with explicit
  Completion, Reviews due, and Event legend groups; Today/Selected date chips;
  a global next-event row using weekday metadata and `in N days`; an adjacent
  pencil; and a 30 px solid primary Browser action that disappears when no
  exact card set applies.
- Separated future workload from completed activity: future cells now remain
  neutral when empty and use five soft violet backgrounds with a fixed-height
  stronger bottom marker when Reviews Due data exists. Today and selected use
  independent interaction rings; event diamonds and focus remain composable,
  including combined states.
- Increased Year heatmap scale and month-label readability; strengthened small
  statistics and verse typography; thickened the contiguous workload bar; and
  refined light/dark surface hierarchy without changing the shared shell,
  two-by-two rail, Bible placement, content-driven height, or theme geometry.
- Tuned Sapphire dark borders and secondary text, neutralized Emerald dark
  surfaces, strengthened Graphite interaction affordance, and made High
  Contrast structurally distinct through luminance and boundaries while
  preserving stable study-semantic and Reviews Due colors.
- Finalized the Sapphire Glass dashboard shell: Month and Year now share one
  calendar-left / insight-rail-right composition at 940 px and wider, retain a
  two-by-two metric grid beneath the calendar from 440–939 px, and use one
  metric column only below 440 px. The Bible verse now belongs to the persistent
  insight rail instead of a full-dashboard banner.
- Rebuilt Year as a fluid week grid with true week-column month labels, complete
  January-through-December compact rendering, quiet lower-edge due marks, and
  an internal scroller only below the minimum readable heatmap width. Switching
  views preserves the selected date and leaves the insight rail mounted.
- Reduced Month cells to a 34–40 px responsive range, made statistic rows
  content-driven, added overflow-safe metric alignment and action wording, and
  replaced ambiguous calendar/event glyphs with recognizable vector icons.
- Rebuilt all four light/dark themes around one semantic contract separating
  neutral canvas/surface elevation, theme accent, stable study semantics,
  explicit completion and subordinate reviews-due indicators, calendar overlays, disabled
  states, borders, and shadows. Sapphire now uses neutral navy depth, Graphite
  is deliberately neutral, High Contrast reserves strong borders for state,
  and Emerald uses charcoal-green rather than a uniform green field.
- Stabilized New cyan, Learning orange, Review violet, Buried slate, Success
  leaf green, Danger rose, and Event gold across themes. Percent Complete and
  the completed progress segment now use the selected theme accent; remaining
  workload segments use their matching semantic values and remain zero-safe.
- Replaced opacity-derived heat colors with explicit opaque six-level
  completion scales and a separate purple Reviews Due indicator system,
  including explicit level-based date text, independent Today/selected states, and
  a gold event marker with contrasting outline and surface halo. Month, Year,
  and both legend systems consume the same variables.
- Removed component color literals, diffuse colored card glows, blanket
  High-Contrast outlines, brightness filters, and whole-control disabled
  opacity. Theme previews now show canvas, surface, accent, and high-completion
  roles, while dashboard and Settings ancillary surfaces consume the semantic
  system.

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
