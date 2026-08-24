# Release visual contract

Status: Home Screen Dashboard 1.8.2 native 100% release contract.

## Authority and provenance

The current machine-readable authorities are:

- `qa/calendar_surface_manifest_1_8_2.json`: layout, component, behavior, and
  acceptance requirements.
- `qa/ui-surface-registry_1_8_2.json`: exact-once surface ownership and fixture
  mapping.
- `qa/visual_regression_matrix_1_8_2.json`: 16 mandatory native Deck Browser
  theme/mode/view frames at 100% text scale.
- `qa/capture_evidence_manifest_1_8_2.json`: 48 required fresh, populated,
  responsive, state, background, Bible, lifecycle, and restart frames.

The supplied 3420x2214 screenshot is geometry calibration input only. Retained
1.8.0 and 1.8.1 packages, reports, captures, and contact sheets are immutable
history. They must not be overwritten or represented as new 1.8.2 evidence.

## Native 100% composition

- The dashboard is at most 1,320 px wide, keeps at least 16 px side margins,
  starts 22 px below the host content edge, uses 12–14 px grid gaps, and keeps
  a 72 px bottom safe area above Anki's footer.
- At 940 px and above, calendar and insight rail are side by side. From
  440–939 px, the calendar is followed by a 2x2 metric grid. Below 440 px,
  metrics form one column.
- Calendar and rail have no shared-height coupling. Month naturally differs
  between five and six rows. Year remains content-driven at approximately
  285–310 px in the wide layout and may differ by at most 2 px across Bible
  short, long, and disabled states.
- Month never scrolls internally. Only the continuous 53-column Year grid may
  scroll horizontally, and only below 320 px. The document itself never
  overflows horizontally and keeps normal vertical scrolling.

The exact container widths under automated and native evidence are 1320, 1100,
940, 939, 620, 440, 439, 320, and 319 px.

## Calendar and data states

- Future cells remain neutral and can carry a due strip. Completion fill,
  Today, selection, due level, event marker/count, hover, and keyboard focus
  have deterministic, composable ownership.
- Year is one continuous 53-column grid with corrected month boundaries and
  labels. The legend matches completion, three due levels, and events.
- The footer keeps legend and context compact, groups the selected or next
  event with its adjacent pencil, and uses a tonal `Reviewed cards` or `Due
  cards` action only when an exact target exists. Below 700 px it remains a
  deliberate two-row grid: chip/date/pencil/action first, event summary second.
- One delegated tooltip is 190–220 px wide, collision-aware, keyboard
  reachable, and constrained to the viewport.

## Statistics, Bible, lifecycle, and themes

- Today's Progress uses one 12–14 px completion bar containing `N% complete`.
  It distinguishes `No cards scheduled`, `All clear`, `100% complete`, active
  progress, and unavailable state without inventing a percentage.
- Today's Session exposes Cards studied, New cards studied, Cards buried, Time
  spent, Pace, and ETA. The Buried value is the existing scheduler-authoritative
  current total, not historical buried analytics. The remaining card groups
  use the final row order recorded in the surface manifest.
- Large values remain stable; time and ETA switch to compact presentation
  before type shrinks. Bible height follows content without changing Year
  geometry, and disabling Bible removes the rail slot.
- Initial loading preserves layout, delayed loading uses the exact status copy,
  initial failure exposes Retry and diagnostics, and a failed refresh retains
  the previously loaded dashboard with Retry.
- Sapphire Glass alone receives component-level translucency and real backdrop
  blur. Graphite, Emerald, and High Contrast remain opaque. High Contrast has
  no decorative transparency or shadow. No theme paints, masks, recolors, or
  scrims the host wallpaper, deck list, toolbar, footer, or surrounding canvas.

## Automated and exact-package release gate

The 1.8.2 gate requires the complete Python and JavaScript suites, current
contract validator, color/contrast and hardcoded-color audits, compilation and
import checks, link/secret review, and `git diff --check`.

The 24-file allowlisted archive is built twice and must have identical SHA-256,
safe paths, valid ZIP integrity, valid imports, and byte-for-byte source parity.
That exact archive must run in a fresh sync-disabled disposable Anki 26.8.1
base/profile with process, package, filesystem, profile, window, and sync
identity verified before interaction. A hard restart of the same profile and
single-instance identity must preserve Month/Year, theme, mode, palette,
visibility, glass settings, week start, and a clean normalized Settings state.
No restart waiver is allowed.

Acceptance requires all 48 native captures, including
`RUNTIME-RESTART-PERSISTENCE`, one complete overview, and 13 readable detail
sheets. The restart frame belongs on the runtime sheet. Background fixtures
simulate a host wallpaper while proving that only dashboard components change.

## Deferred and unrun

Dedicated 125%/150% captures, spoken screen-reader review, Windows, Linux,
forced-colors review, and OS-level scaling acceptance remain deferred and must
be reported as unrun and unclaimed.
