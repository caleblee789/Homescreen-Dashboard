# Release visual contract

Status: Home Screen Dashboard 1.8.1 native 100% release contract.

## Authority and provenance

The current machine-readable authorities are:

- `qa/calendar_surface_manifest_1_8_1.json`: layout, component, behavior, and
  acceptance requirements.
- `qa/ui-surface-registry_1_8_1.json`: exact-once surface ownership and fixture
  mapping.
- `qa/visual_regression_matrix_1_8_1.json`: 16 mandatory native Deck Browser
  frames covering four themes, light/dark, and Month/Year at 100% text scale.
- `qa/capture_evidence_manifest_1_8_1.json`: tagged fresh/populated,
  responsive, state, background, Bible, lifecycle, and persistence evidence.

The user-supplied 3420×2146 native screenshot is geometry calibration input.
The retained 1.8.0 contact sheets are comparison and navigation material. They
must not be overwritten or represented as newly generated 1.8.1 evidence.
The complete `qa/release-evidence-1.8.0-2026-08-23/` directory remains
immutable history.

## Native 100% composition

- The dashboard uses `min(1480px, calc(100vw - 64px))` with 24 px top and
  32 px bottom margins.
- At about 1,220 component pixels and above, the calendar sits left of a
  430–450 px rail. Four equal statistics cards form a 2×2 grid and the Bible
  card sits beneath both rail columns.
- From 900–1,219 px the calendar becomes full width and the rail follows it.
  Below about 640 px statistics use one column and controls/footer stack with
  no horizontal scrolling.
- Month uses compact 44–48 px rows (42–46 px under height pressure). Year uses
  an unframed wrapper up to about 940 px with wide cells near 14 px, week-column
  month labels, and Mon/Wed/Fri references.
- No whole-dashboard transform or zoom is permitted. The legend and selected-
  date footer remain visible under height pressure.

## Calendar and data states

- Historical completion owns the cell fill. Today owns one number capsule in
  Month or one inner marker in Year. Selection owns exactly one 2 px outline.
- Due workload keeps the existing raw calculations and percentile reference,
  then maps to presentation levels 0–3. Month uses 2/4/6 px bottom indicators;
  Year uses a compact bottom marker. Due may coexist with today and completion.
- Events remain gold/orange in every theme; multiple events use one compact
  count. The legend says Completed reviews and presents three matching due
  samples.
- One delegated 220–260 px tooltip uses historical or future wording and stays
  inside the viewport.
- The integrated footer gives selected-date events precedence (`Event on this
  date`), otherwise presents the global `Next event`. Date, title, countdown,
  count, and pencil edit affordance remain grouped. Actions are exactly
  `Reviewed cards` and `Due cards`; Most missed remains conditional.

## Statistics, Bible, themes, and background

- Today’s Progress distinguishes no cards due, in progress, complete, and
  unavailable. The exact-count bar contains Completed, New, Learning, and
  Review; buried cards remain separate.
- Today’s Session always has five rows. Last 7 Days and All Time retain their
  rate rows when unavailable. Positive semantic values are colored; zero is
  neutral; unavailable is a muted em dash. Python initial rendering and live
  JavaScript updates consume the same derived presentation payload.
- The Bible preference maps into a safe responsive text clamp, long verses are
  never truncated, and disabling the card also removes its rail gap.
- Themes extend the existing semantic token system. Routine Emerald values are
  neutral, Graphite dark uses steel hierarchy, High Contrast surfaces are
  opaque, and study/event/status semantics remain stable.
- The default/native host receives no add-on-painted global canvas. A top-level
  scrim is activated only when a real or QA-injected background image is
  detected.

## Automated and exact-package release gate

The 1.8.1 gate requires the Python and JavaScript suites, the current contract
validator, color audit, source checks, deterministic double build, safe 24-file
allowlist, archive integrity, imports, source/archive parity, and a final secret
and machine-path audit.

The exact candidate archive must then run in a fresh sync-disabled disposable
Anki 26.8.1 base/profile with a unique single-instance key. Process, profile,
add-on, filesystem, window, and disconnected-sync identity are verified before
interaction. The same run root and key are reused for restart/persistence
readback. The user’s normal Anki process is never focused, resized, closed, or
otherwise controlled.

## Acceptance boundaries

The native run and its machine-readable reports support macOS Anki 26.8.1 at
100% dashboard text scale. Dedicated 125%/150% captures, spoken screen-reader
review, Windows, Linux, forced-colors review, and OS-level scaling acceptance
are deferred and must be reported as unrun. Existing keyboard and inexpensive
accessibility regressions remain preserved, but they are not new 1.8.1 release
gates.
