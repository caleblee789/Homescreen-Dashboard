# Release visual contract

Status: approved 1.7.0 architecture and release-acceptance contract, pending
candidate implementation and exact-package evidence. This document does not by
itself approve a package or release.

## Authority and scope

The immutable evidence bundle at
`qa/live-ui-acceptance-1.5.3-release-2026-08-15/` is the source of truth for the
current product surface area. Its overview sheets, full-resolution detail
sheets, raw captures, manifests, fixture descriptions, reports, and acceptance
scripts establish what 1.5.3 actually exposed. They are evidence of the current
behavior, not the target design.

The candidate must preserve useful behavior that this contract does not
explicitly replace. A new visual direction does not silently waive keyboard,
focus, safe-text, staged-save, restart, unavailable-data, or recovery behavior.
The candidate must reproduce every applicable baseline state and must add
evidence for new transition and interaction states introduced by the redesign.

The following rules are absolute:

- Never overwrite, rename, delete, or regenerate anything in the 1.5.3 evidence
  directory.
- Never use the baseline's absolute machine path in production code.
- Never encode screenshot dimensions, fixture dates, fixture counts, or fixture
  strings as production layout or data rules.
- Never render an unavailable value as zero. Zero is a valid available value;
  unavailable is a separate state.
- Never claim exact-package acceptance from a source checkout, preview renderer,
  or package other than the archive whose checksum is recorded in the candidate
  report.
- Never create a second panel, button, tooltip, or metric-row visual language to
  work around shared-component ownership.

`qa/ui-surface-registry.json` registers the 61 immutable baseline surfaces
exactly once. The candidate scenario contract adds NFS-01 through NFS-25,
THM-01 through THM-08, and OPA-01 through OPA-12 for a registry-derived
106-state canonical candidate set.
`qa/ui-issue-register.json` records defects, decisions, owners, and evidence.
Those files and the contact-sheet audit are the machine-readable and human-
readable companions to this contract.

## Ownership contract

Ownership follows behavior, not whichever file currently happens to contain the
behavior.

| Agent | Exclusive product ownership | Current source responsibility |
| --- | --- | --- |
| Data | Collection, scheduler, statistics, availability, and date-query services | `analytics.py`, the query/service portions of `insights.py`, `models.py`, and any activated calendar repository/service modules |
| Design system | Tokens and shared panel, button, tooltip, metric-row, alert, loading, focus, and field primitives | Shared/token portions currently embedded in `renderer.py`, `web/dashboard.css`, and settings styling; future extracted primitive files |
| Calendar | Year and Month layout, cells, heatmaps, calendar tooltips, dashboard composition, selected-date shell placement, and loading/recovery/fallback shells | Calendar and shell portions of `renderer.py`, `web/dashboard.js`, and `web/dashboard.css`; Calendar capture logic |
| Insight | Selected-date content, contextual summaries, card/deck rendering, events in details, and date actions | Selected-date portions currently embedded in `renderer.py`, `web/dashboard.js`, `web/dashboard.css`, and the action/cache portions of `controller.py` |
| Settings | Settings windows, configuration UI, editors, deck exclusions, About copy, section placement, selector, sticky footer, and preview placement | `settings.py`, `settings_model.py`, `config_schema.py`, and settings capture logic |
| Theme | Preset token values and preset migration | `themes.py` and preset-specific migration values only |
| Integration | Verified cross-agent defects and final wiring only | May edit any area only after the defect crosses an ownership boundary and is reproduced; it is not a substitute feature owner |

Tests follow the same ownership. For example, Data owns analytics and query
service tests, Calendar owns calendar-model and calendar-capture assertions,
Insight owns selected-date content/action tests, Settings owns settings/editor
tests, Theme owns preset-value tests, and Integration owns package-wide parity
and cross-feature regression gates.

### Current mixed hot spots and extraction order

`renderer.py`, `web/dashboard.js`, `web/dashboard.css`, and `controller.py` mix
multiple ownership domains. They are serialized hot spots: only one designated
owner may edit a hot-spot file in a given integration step. Agents must not make
parallel competing edits in those files and reconcile them after the fact.

Extraction proceeds in this order:

1. The Design-system agent establishes the canonical tokens and shared
   primitives without changing product behavior.
2. The Calendar agent moves the calendar grid, responsive placement, tooltip
   invocation, dashboard shell, and fallback shells onto those primitives.
3. The Insight agent supplies one selected-date content component through the
   Calendar-owned shell slot. It does not create a second details panel.
4. The Settings agent consumes the shared primitives where appropriate while
   preserving native settings behavior, selector placement, and the sticky
   action footer.
5. The Theme agent maps presets to the canonical tokens and owns preset
   migration.
6. The Integration agent resolves only demonstrated cross-boundary defects and
   runs the full evidence gate.

Until a mixed file is split, the integration plan must name one temporary file
owner and the exact regions delegated for review. Extraction must be behavior-
preserving and test-backed. No agent may independently introduce a local panel,
button, tooltip, alert, loading, or metric-row variant.

## Calendar architecture

### One content-driven Month strategy

CAL-11 through CAL-14 currently encode abrupt one-pixel layout changes through
JavaScript width constants and matching CSS media boundaries. The candidate must
replace those separate breakpoint rules with one content-driven strategy.

The Month grid and selected-date shell may sit side by side only when the actual
container can satisfy both components' intrinsic readable minimums plus the
shared gap. Otherwise the selected-date shell follows the grid in document
flow. Font scaling, settings-preview width, sidebar changes, translations, and
window chrome must feed the same decision naturally. CSS container behavior is
preferred; if measurement is required, it must have one source of truth and
must not be mirrored by contradictory CSS and JavaScript thresholds.

CAL-11, CAL-12, CAL-13, and CAL-14 remain required captures at their registered
sizes. They no longer assert that 1150 means rail, 1149 means inline, 1180 means
rail, or 1179 means inline. Instead, the paired captures and automation must
prove:

- no overlap, clipping, or horizontal scrolling;
- stable selected date, focus, and content across reflow;
- no presentation flip caused solely by crossing an obsolete magic pixel;
- the grid retains readable day cells and the details component retains its
  intrinsic content width; and
- the same strategy works in the dashboard and cached settings preview.

### One diamond-only day-event representation

CAL-15 and CAL-16 must render the same day-cell event component at 720 and 719
pixels of calendar width and at every other width. Event names do not appear in
day cells. The visible cell affordance is a diamond glyph, not an event-name
chip, truncated label, overflow label, or width-specific alternate component.

Event names and full event lists belong to the Calendar tooltip and the
Insight-owned selected-date content. Calendar owns the count-only cell marker
semantics and tooltip invocation; Design-system owns the tooltip primitive. The
marker's accessible name communicates the event count without names, while full
names remain available through the tooltip and selected-date details. Adding a visible
numeric badge or a second marker language would require an explicit product
decision and new evidence; the 1.5.3 contact sheets do not authorize it.

Automated acceptance must prove identical marker markup and styling at the
CAL-15 and CAL-16 widths, the absence of event-name text from every day cell,
safe full text in details, and keyboard/focus access to the associated date.

### Separate narrow Year strategy

CAL-03 demonstrates that indefinitely shrinking the continuous 53-week heatmap
does not remain readable. The candidate must expose a distinct narrow-Year
strategy when the container cannot satisfy the continuous heatmap's intrinsic
cell and label requirements.

The narrow strategy's final composition is a Calendar design decision and is
not invented here. It must nevertheless preserve access to every civil date,
month boundaries, intensity, due and event semantics, selected/today/focus
states, legend meaning, keyboard navigation, and year navigation. It must not
solve fit by hiding dates, relying on horizontal scrolling, or encoding the
CAL-03 screenshot width as a production special case.

CAL-03 must visibly demonstrate the distinct strategy at 620 by 780. Scaled
states whose effective content width is narrow must select the same strategy by
content capacity, not by a device-name branch.

### One persistent selected-date component

CAL-06, CAL-18, CAL-19, and CAL-20 require one persistent selected-date
component and one DOM instance. Calendar owns the shell slot and whether that
slot is beside or below the calendar. Insight owns everything rendered inside
it: contextual metrics, trouble/deleted/empty/due cards, event lists, safe text,
and date actions.

Responsive reflow moves the shell; it does not destroy and recreate competing
rail and inline versions. The selected civil date, focus semantics, pending or
resolved insight request, and user-visible content survive resize and reflow.
Past, today, and future remain distinct content states. Event text is retained
in details even though it is removed from day cells.

The component has no close button, empty placeholder, or dismissed state. The
current Anki scheduling day is selected and populated by default. Past and
future dates remain selectable, and every selection repopulates the same
component instance.

The controller preserves the semantic selected date across a webview recreation
within the current profile session and rehydrates the newly mounted component;
DOM-node identity is required only within one mounted webview. Profile reopen or
application restart selects the current Anki scheduling day by default.

### First-class dashboard shells

CAL-21 through CAL-24 are owned states, not incidental error branches:

- CAL-21: all sections hidden, with a settings recovery action;
- CAL-22: partial data unavailable, retaining usable sections and showing
  unavailable values rather than fabricated zeros or raw exceptions;
- CAL-23: loading, with a semantic progress/status primitive and no stale data;
- CAL-24: legacy activation required, with release-safe mapped product copy and
  a recovery action rather than a raw add-on identifier.

Calendar owns their composition and placement. Design system owns their shared
panel, alert, button, loading, and focus primitives. Data owns the availability
and failure information. Settings owns the destination opened by recovery
actions. Each state must be directly renderable and independently tested; none
may depend on an exception occurring during a screenshot run.

## Insight, Settings, copy, and data contracts

### Insight state matrix

INS-01 through INS-12 are distinct contracts and must not be collapsed into a
single generic detail card. Candidate evidence must retain:

- current with trouble content in dark mode;
- historical with no miss, deleted-card, and empty variants;
- future with due content and an empty variant;
- current at 620 by 780, 150 percent scale, and 200 percent scale;
- current in light and high-contrast modes; and
- current after controlled restart.

The content component may share primitives, but copy, metrics, actions, empty
states, ranking, and availability remain state-specific. The current day shows
no Completed Reviews, New Cards Studied, or Cards Due summary boxes: Study
Insight moves upward while Events and valid actions remain. Historical dates
retain two metrics and distinct Again-found, no-Again, deleted/unavailable-card,
and no-study-activity states. Future dates retain Cards Due, Top Due Decks,
Events, and Browse due cards only when a nonzero due target exists.

Historical trouble rows show sanitized, bounded text summaries rather than raw
card HTML. Each row carries explicit `summary_text`, `preview_kind`, deck
breadcrumb, accessible full deck path, regenerated browser token, and Again
count metadata. Answer text is preferred; safe front text is a typed fallback;
image-only, equation, and unavailable previews are labeled explicitly. Source
CSS, scripts, iframes, media renderers, handlers, controls, and raw markup never
enter the dashboard. A summary uses at most four lines and one optional Expand
preview/Collapse preview disclosure in normal page flow. Exactly three ranked
rows are visible, with total and hidden counts exposed when more results exist;
each row has a direct Open card in Browser action.

Full-day ranking, DOM/backend agreement, stale-response protection, immediate
post-Again refresh, browser queries, and event rendering remain behavioral
contracts. Query failure is unavailable with Retry and can never masquerade as
the no-Again state.

### Settings responsive contract

Settings has exactly four pages in this order: Dashboard, Events, Bible verse,
and About & support. Dashboard contains exactly three internal areas: Appearance,
Content & study metrics, and Calendar & data. Content & study metrics separates
Visible sections from Study calculations while preserving dependent values.
Legacy Theme & layout, Home screen, and Calendar & data routes open Dashboard
and scroll its body to the corresponding complete heading after layout settles.
There are no category headings or global reset actions.

At 1,180 logical pixels and wider, a content-sized vertical rail and the
contextual Dashboard/Bible preview sit beside the editor. From 760–1,179 pixels,
horizontal tabs replace the rail and Preview opens the contextual surface.
Below 760 pixels, a four-item labeled selector shares a wrapping compact toolbar
with Preview.
Events and About & support never show persistent preview chrome. The normal-grid
footer is approximately 60 pixels tall and never overlays the page scrollbar. Its clean,
dirty, saving, saved, and failure states keep Close/Discard changes and Save
changes reachable without horizontal scrolling. At 900×900 there is no rail or
persistent preview.

Settings previews use the production render path and cached data contract. They
must adopt the candidate calendar strategy and marker without querying live
collection data merely to reproduce a screenshot. Staged changes, cancel,
discard, conflict recovery, dependencies, deck exclusions, editor containment,
and saved-state persistence remain intact.

Extra-wide preview allocation is bounded and top-aligned. The editor receives
the remaining width, while the preview offers Current section / Full dashboard,
Fit / Actual size, and Open full preview. Current-section Dashboard preview
follows the last-focused field, shows only a focused Calendar or study-metrics
region where appropriate, and outlines individual visibility targets. Bible
verse renders the selected staged verse at 1× and never shows sample-data copy.
Events and About & support use the editor width. Only collection-backed
Dashboard fallback facts receive the compact Sample data badge. The webview is
measured from its rendered content and cannot reserve a large unused canvas.

Calendar deck exclusions use a collapsed hierarchy. Parent selection cascades,
child-only selection creates a partial parent, filtering keeps ancestor context,
bulk actions affect visible matches, unavailable stored identifiers remain
removable under Unavailable decks, and persistence stores only minimal checked
roots. `SET-03-deck-exclusions.png` must show an expanded branch, a collapsed
branch, tri-state selection, and an unavailable deck.

Events use Add event, Active/Archived tabs, and intentional no-event/no-results
states; Search and sort stay hidden until there is content to manage. Populated
wide/intermediate views use the full-width list, while narrow rows become
stacked cards. Every row owns an always-visible overflow menu with Edit,
Archive/Restore, and separated Delete actions; there is no detached selection
summary or large destructive action. Archive and restore switch to the
destination tab, reselect the moved event, provide staged feedback, and expose
Undo.

Initial dashboard loading uses component-shaped calendar, metric, and optional
Bible skeleton regions with busy semantics. After 2.5 seconds it announces
“Still loading your study data…”. After 12 seconds it reveals the retryable
failure “The dashboard could not finish loading.” with Retry and Open
diagnostics actions. A controlled restart is accepted only after the normal
calendar, metrics, and configured Bible regions finish rendering.

### Required copy corrections

SET-07 and SET-17 use: “Calendar cells display an event marker. The full event
name appears in date details and hover information.” The separate character
count and 160-character input limit remain visible and enforced.

SET-06 and SET-16 must remove internal implementation and personal-facing text
from the release About UI. This includes maintainer-specific menu routing and
implementation details such as bridge commands, schema storage, preview
internals, and test/development language. About is manifest-derived and contains
Home Screen Dashboard, version, supported Anki version, license, data/privacy,
the complete Scripture notice, neutral Third-party notices/help, and recovery.
It contains no legacy product name, personal name, Credits presentation, normal
upstream credit, or raw migration timestamp. Required upstream attribution stays
in the packaged notices file.

### Schema 6, four retained themes, and runtime placement

Schema 6 retains exactly four presets in Settings order: Sapphire Glass,
Graphite, Emerald, and High Contrast. Sapphire Glass is the quality reference
and receives only minor accessibility refinements. Graphite must remain neutral,
Emerald must be polished without making Accent visually interchangeable with
Review or Success, and High Contrast must preserve the pattern, shape, label,
boundary, and focus distinctions proved by CAL-05 and INS-11. Every light/dark
pair uses identical dashboard component geometry and every preset maps semantic
roles through tokens. Settings control geometry follows the second-pass native
control and responsive-density contract.

Panel Opacity remains 70–100 percent with an 88 percent default and changes
only the alpha-aware panel background token. Text, borders, controls, shadows,
and focus indicators remain fully opaque. Text Scale remains 90–150 percent and
must match between the live dashboard and Settings preview. Schema 6 retains
`home_screen.position` (`top` or `bottom`, default `top`) and unrelated unknown
keys while keeping the retired layout-density key absent.

Home Screen Position is relative only to injected add-on panels after Deck
Browser render hooks complete. The native deck list always remains above the
entire add-on panel stack, including when the position is Top; native bottom
actions do not move, and Settings previews never perform stack repositioning. Missing or
invalid Bible rotation becomes Daily while valid explicit Daily, Every render,
and Manual preferences remain unchanged.

### Typed availability: unavailable is not zero

Every statistic crossing the Data boundary must carry an explicit state, for
example `loading`, `available(value)`, or `unavailable(reason_code)`. The exact
type name is a Data-agent decision, but these semantics are required:

- `available(0)` renders zero;
- `unavailable(...)` renders an unavailable treatment such as an em dash plus
  approved explanation, never zero;
- `loading` does not reuse stale or default numeric content;
- raw exception text, queries, collection identifiers, and internal reason
  details never reach release UI copy; and
- partial failure does not discard independently available sections.

Truthiness, default numeric fields, and missing dictionary keys are not valid
availability signals. CAL-09 and CAL-22, the future insight states, and all
summary/metric-row consumers must test the typed boundary end to end.

### Resolved metric scope

One resolved filter scope is authoritative across Calendar cells, tooltips,
selected-date details, Today’s Progress, Today’s Session, Last 7 Days, All-Time,
the buried-card inset, exact Browse targets, and the saved Settings preview.
Active deck exclusions apply to
every one of those consumers, including excluded descendants and a card's
original deck while it is in a filtered deck. Deleted-card and manual-change
rules apply to history wherever relevant.

`Reviews due` always means active review and relearning cards scheduled for the
date, with overdue work folded into the current scheduler day. It excludes
suspended, deleted, buried, and deck-excluded cards and is not reduced by deck
daily limits. The current date's canonical value also drives Reviews remaining,
Total remaining, Percent Complete, the completed progress segment, and ETA.
Scoped raw new-card inventory and learning work complete that Progress workload;
no scheduler-limited fallback is permitted. The deck-exclusion live sequence
must prove that Calendar, tooltip, selected details, Today’s Progress, Today’s
Session, Browse, and the full saved Settings preview all refresh from 9/3/9 to
7/2/7.

## Candidate exact-package evidence contract

### Artifact and environment

The candidate evidence run must:

1. Build one deterministic candidate `.ankiaddon`, record its SHA-256 and byte
   size, validate safe archive paths and the package allowlist, and prove source
   and archive parity for packaged files.
2. Install that exact archive into a fresh, uniquely named, sync-disabled
   disposable Anki profile. The user's normal base, profile, collection, and
   add-ons must remain untouched.
3. Pass process, window, filesystem, package, and sync identity gates before any
   capture is accepted.
4. Use manifest-owned fixtures and civil dates. Fixture values may configure the
   QA run but may not enter production conditionals or styling.
5. Record application version, color mode, logical viewport, text scale, display
   scale, selected date, data/event state, archive hash, and relative capture
   path for every state.
6. Capture the initial and controlled-restart states from the same isolated
   candidate installation where persistence is part of the contract.
7. Generate new raw captures and overview/detail sheets outside the immutable
   1.5.3 directory. Candidate sheets are evidence, not a substitute for raw
   images or machine-readable results.

### Required baseline state set

All 61 baseline IDs below are required exactly once in the candidate manifest
and registry comparison. A redesigned state keeps its ID; it is not deleted and
replaced by an extension capture. The 45 registered NFS, THM, and OPA extensions
complete the 106-state candidate canonical set.

**Calendar (28):** CAL-01 Year Desktop Light Populated; CAL-02 Year
Intermediate Light; CAL-03 Year Narrow 620x780; CAL-04 Year Dark 125 Text 150
Scale; CAL-05 Year High Contrast 200 Scale; CAL-06 Year Selected Today Focus;
CAL-07 Year Transition December January; CAL-08 Month Four Week; CAL-09 Month
Five Week Leap February; CAL-10 Month Six Week Populated; CAL-11 Month Rail
1150; CAL-12 Month Inline 1149; CAL-13 Month Layout 1180; CAL-14 Month Layout
1179; CAL-15 Month Event Chips 720; CAL-16 Month Event Markers 719; CAL-17 Month
Narrow 620x780; CAL-18 Date Details Past; CAL-19 Date Details Today Combined;
CAL-20 Date Details Future Overflow Safe Text; CAL-21 All Hidden Recovery;
CAL-22 Partial Data Unavailable; CAL-23 Loading State; CAL-24 Legacy Activation
Required; CAL-25 Calendar Settings Desktop; CAL-26 Calendar Settings
Intermediate; CAL-27 Events Empty And Contextual; CAL-28 Events Active Archived
Feedback.

**Study Insight (12):** INS-01 Current Trouble Dark; INS-02 Past No Miss;
INS-03 Past Deleted; INS-04 Past Empty; INS-05 Future Due; INS-06 Future Empty;
INS-07 Current 620x780; INS-08 Current 150%; INS-09 Current 200%; INS-10 Current
Light; INS-11 Current High Contrast; INS-12 Current After Restart.

**Settings (20):** SET-01 Desktop Theme Layout; SET-02 Desktop Home Screen;
SET-03 Desktop Calendar Data; SET-04 Desktop Events; SET-05 Desktop Bible Verse;
SET-06 Desktop About; SET-07 Desktop Event Editor; SET-08 Desktop Verse Editor;
SET-09 Desktop Light Calendar; SET-10 Desktop Dark Events; SET-11 Minimum Theme
Layout; SET-12 Minimum Home Screen; SET-13 Minimum Calendar Data; SET-14 Minimum
Events; SET-15 Minimum Bible Verse; SET-16 Minimum About; SET-17 Minimum Event
Editor; SET-18 Minimum Verse Editor; SET-19 Scale 150 Dark Calendar; SET-20
Scale 200 High Contrast Home.

**Restart (1):** RST-01 Restart Persistence.

“Event Chips” and “Rail/Inline” remain historical canonical titles for CAL-15
and CAL-11/CAL-12. Their candidate images must show the new contract and their
registry/issue records must explain the intentional visual change; titles must
not be silently renamed.

### Required extension evidence

The baseline static states do not fully prove the new interaction model. The
candidate manifest must add separately named extension evidence for:

- responsive continuity: the same selected Month state before, through, and
  after the intrinsic rail/stack crossover, including a text/display-scale
  change;
- selected-date persistence: one DOM/component instance retaining the selected
  civil date, focus semantics, pending/resolved insight state, and actions while
  the shell moves between side and stacked placement;
- narrow-Year operation: entering the distinct narrow strategy, reaching dates
  across month boundaries, and returning without losing selection;
- event-marker access: zero, one, and multiple events using the same visible
  diamond component, with count-only cell semantics and full names available
  through the tooltip and selected-date details; and
- typed availability transitions: loading to available zero, loading to
  unavailable, and partial failure while other sections remain available.

These may be ordered interaction captures plus machine-readable assertions when
a single screenshot cannot prove the behavior. The surface registry assigns the
initial extension namespace and capture obligations: NFS-01 current empty,
NFS-02 selected-date unavailable, NFS-03 selected-date loading, NFS-04 populated
Settings event preview, NFS-05 intrinsic Month-fit continuum, NFS-06 selected-
date 200-percent continuation, NFS-07 history out of range, NFS-08 forecast
disabled, and NFS-09 forecast out of range. NFS-10 through NFS-25 cover the
complete Most Missed layout, scaling, keyboard/high-contrast, hostile-content,
typed-preview, overflow, footer-clearance, and restart matrix described by their
exact registry records. The candidate QA manifest must bind those IDs to exact
fixtures before capture. Any revision requires an approved
registry change; extensions supplement the 61 states and do not change the
“exactly once” baseline rule.

THM-01 through THM-08 are the complete four-preset candidate matrix: Sapphire
Glass, Graphite, Emerald, and High Contrast, each in light and dark mode. Each
cell contains the complete semantic-role fixture. Emerald must visibly test
Percent Complete text, the completed progress segment, Reviews Remaining,
Success, selected controls, event diamond, due hatch, calendar heatmap, buttons,
and focus ring, with Accent distinct from both Review and Success.

OPA-01 through OPA-12 test 100, 88, and 70 percent against, respectively,
Graphite on dark Anki, Sapphire Glass in light mode, High Contrast, and Emerald
over deterministic representative imagery. Each opacity cell must report
requested and effective opacity, prove single-layer compositing, preserve the
semantic fixture and focus cues, and keep geometry identical.

Two non-canonical supplemental images are mandatory in the same evidence
manifest and contact sheets: `SET-03-deck-exclusions.png` and the existing
NFS-06 continuation image.

### Geometry revision and freeze

The candidate records `ui_geometry_revision: 1` and measured CSS-pixel
rectangles for every primary state. The immutable 1.5.3 baseline remains
read-only; every intentional changed surface is registered in
`qa/ui-geometry-contract-1.7.0.json`. The first complete candidate freezes those
registered changes. After that freeze, a missing or extra component, a revision
mismatch, theme-specific geometry, or any per-field drift greater than 0.5 CSS
pixel fails acceptance.

### Automated and visual acceptance

Acceptance requires all of the following:

- manifest validation fails closed for a missing, duplicate, renamed, stale, or
  unexpected baseline state;
- candidate captures are bound to the exact archive checksum and ordered
  manifest;
- 4-, 5-, and 6-week months, leap day, December-to-January navigation, all week
  starts, all Year dates, outside-month dates, keyboard navigation, focus, and
  safe literal HTML remain correct;
- CAL-11 through CAL-14 prove content-driven continuity rather than the old
  pixel constants;
- CAL-15 and CAL-16 use identical diamond-only cell markers;
- CAL-03 proves a distinct narrow-Year strategy with no horizontal overflow;
- CAL-06 and CAL-18 through CAL-20 prove one persistent selected-date component;
- CAL-21 through CAL-24 are directly captured first-class states;
- INS-01 through INS-12 remain distinct and SET-11 through SET-20 preserve their
  responsive selector/footer behavior;
- SET-06/SET-16 and SET-07/SET-17 contain the approved release copy;
- SET-01 through SET-20 prove sidebar/selector selection, intrinsic preview
  sizing, sticky-footer containment, focus order, and no clipping or horizontal
  overflow at desktop, intermediate, minimum, 150 percent Qt font, and 200
  percent Qt font states;
- RST-01 proves schema 6 and reaches a fully rendered dashboard both before and
  after a controlled process restart. It persists Year view, Monday week start,
  a changed theme-specific heatmap palette, and a changed visibility option;
  then reads those values back from both dashboard DOM and clean Settings. It
  also proves unchanged events, edited verse-library content, rotation mode and
  state hash, theme settings, dashboard preferences, deck exclusions, unknown
  retained keys, and every schema-6 value after the restart;
- unavailable values are never zero and raw error/internal text is absent;
- settings previews and the live dashboard use the same production render path;
- automated focus, names, roles, contrast, target sizing, containment, safe text,
  restart, and identity gates pass; and
- a human reviews every raw full-resolution candidate image and every generated
  contact sheet against this contract and the issue register.

## Evidence limits and approved decisions

The 1.5.3 bundle passed its automated contract in Anki Desktop 26.8.1 and is
valuable evidence of behavior, but it is not visual approval for the candidate.
The contact sheets are static: they cannot by themselves prove keyboard
sequences, responsive persistence, stale-response handling, or restart. Those
claims require scripts and ordered interaction evidence.

Automated semantics, keyboard, focus, sizing, contrast, and containment were
covered in 1.5.3. Spoken VoiceOver, Windows and Linux behavior, OS forced
colors, and true OS display scaling remain explicitly unverified nonblocking
boundaries for the 1.7.0 gate. Candidate evidence must label macOS/DPR 2,
webview zoom, Qt font scale, and the app High Contrast preset accurately.

The approved decisions are recorded in `qa/ui-issue-register.json`: Month uses
measured intrinsic fit; narrow Year uses stacked months; one selected-date
component keeps a session-only selection; every event-bearing cell uses a plain
diamond with no visible count; availability is typed per fact and date; and the
event helper and About page use the exact approved release copy. Their status is
`implemented_pending_candidate`, so none of these decisions is a claim that
runtime or visual acceptance has passed.

Calendar, tooltip, selected details, Today’s Progress, Today’s Session, Last 7
Days, All-Time, the buried-card inset, exact Browse targets, and the saved
Settings preview all consume one resolved filter scope. Reviews due and every
due-review projection use scoped
raw scheduled demand without daily-limit reduction; the current day's value is
also the review component used by Progress, Percent Complete, and ETA.

Web and native Settings expose the same conceptual `extra-wide`, `intermediate`,
and `narrow` modes. Controls use one comfortable 30-pixel visual geometry inside
at least 36-pixel interaction bounds with a 3-pixel visible focus treatment.

CAL-07's static baseline image does not alone demonstrate the January side of a
December-to-January transition. The candidate must pair the capture with date-
navigation automation rather than overstate what the image proves.

Release acceptance is complete only when every required state and extension is
captured from the exact candidate package, all automated gates pass, the issue
register contains no unowned release blocker, and the remaining human-only
boundaries are stated accurately.

## Final pre-release contact-sheet audit

Anki capture begins only after the full implementation and offline contract
suite are complete. The fresh candidate evidence directory must contain all 106
ordered primary captures plus both registered supplements, without overwriting
an existing capture directory or the immutable baseline. The generator must
produce a concise overview, complete category sheets for Calendar, selected
date/Most Missed, statistics, Settings, themes, opacity/backgrounds, and restart
persistence, plus paginated full-resolution detail sheets.

`contact-sheet-index.json` is the audit authority. It records every primary and
supplemental raw capture exactly once with source hash, stable ID, title, state,
theme, mode, scale, opacity, candidate hash, geometry revision, category, and
detail-sheet cell. Release cannot enter its final phase until that index
validates, all sheet artifacts are hash-bound to the same exact package, and a
human has used the organized complete set to audit every UI surface.
