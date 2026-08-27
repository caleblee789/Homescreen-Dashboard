# Release visual contract

Status: Home Screen Dashboard 1.8.7 implementation contract complete; native
release evidence blocked until every required platform bundle passes.

## Authority and retained evidence

The current machine-readable authorities are:

- `qa/capture_plan.json`, the sole executable case/count/order authority
- `qa/calendar_surface_manifest_1_8_7.json`
- `qa/ui-surface-registry_1_8_7.json`
- `qa/visual_regression_matrix_1_8_7.json`
- `qa/capture_evidence_manifest_1_8_7.json`
- `qa/settings_window_contract_1_8_7.json`
- `qa/runtime_probe_release_1_8_7_manifest.json`

The completed `qa/release-evidence-1.8.6-2026-08-25` directory and the
untracked 41-frame `qa/settings-evidence-1.8.7-2026-08-26-b995fec` review set
are immutable provenance. A corrected candidate must write a new evidence
directory; neither retained set may be overwritten, regenerated, or deleted.

## Production composition

- The dashboard remains at most 1,120 px wide with normal document scrolling
  and measured clearance above Anki's visible bottom actions.
- Month remains a 42-cell six-week grid. Year remains a real 53-week grid.
  Completion, selection, Today, due, and event semantics remain independent.
- Existing theme IDs, heatmap palette IDs, events, verses, study statistics,
  schema 8 behavior, and restart semantics do not change.

All unaffected production and statistics cases remain in the canonical plan
and must be captured from the same exact candidate as Settings.

## Settings window and shell

- Production opens `SettingsDialog(mw, controller, …).exec()` with the parented
  native Qt lifecycle and no WebEngine content, custom window flags, `winId()`,
  post-show movement, activation, or focus manipulation.
- Geometry uses logical coordinates: 940×680 default, 720×520 minimum, and
  initial caps of 92% available width and 88% available height.
- A versioned UI-only `QSettings` key stores the non-maximized logical `QRect`.
  Launch restores a valid position, clamps it to the active screen, and
  recenters an off-screen or disconnected-monitor rectangle before visibility.
- The shell is a fixed header, `min-height: 0` body, and fixed footer. Each page
  owns one vertical `QScrollArea`; horizontal scrolling is disabled; page
  bottom padding equals the live footer height plus 16 logical pixels.
- The centered shell is capped at 1,120 px. The desktop body uses a 152 px
  sidebar, 24 px gap, and a centered page column capped at 940 px.
- Below 760 logical body pixels, or before live font metrics would wrap a rail
  label, a synchronized single-line, non-eliding `QTabBar` replaces the rail.
- Cards and toolbars reflow from two columns to one using their current width
  and font metrics. Wide native previews appear only when the main page column
  is at least 900 px. Navigation never changes native window geometry.

## Settings surfaces and behavior

- Dark and light Settings roles follow Anki's live palette only. Dashboard
  Color mode changes dashboard output and native previews, not dialog chrome.
- Role fonts are application-relative, visible text is at least 12 px at the
  100% baseline, ordinary controls are at least 36 px high, list rows are
  48–54 px or taller, and the footer is at least 52 px high.
- Selected navigation and verse rows use accent-soft surfaces and a substantial
  accent edge. Events tabs use neutral graphite surfaces. Event rows have no
  persistent selection; activation opens the editor.
- Dashboard contains responsive Appearance, sections, Study metrics, Calendar
  display/range, and Local data groups. Reset is visible only when its scope
  differs from defaults and never saves immediately.
- Events contains one bounded list surface with search clearing, explicit Sort
  by labeling, result counts, Active/Archived tabs, internal scrolling,
  distinct empty and no-results states, and contained 32 px action menus.
- Bible verse contains a native preview, attached Custom color controls,
  blocking hex validation, nonblocking contrast warning, dynamic Rotation
  copy, and a complete filtered model with delegate-painted two-line rows.
- About uses top-aligned, independently sized 60/40 Version and Help cards,
  manifest-derived compatibility copy, local two-second diagnostics feedback,
  standardized disclosures, and Export verse edits wording.
- Dirty, saving, success, validation, and persistence feedback is local to the
  footer. Failed saves retain all staged values and expose the generic release
  copy with raw details collapsed. Dirty close requires Keep editing or
  Discard and close in the existing embedded prompt.

## Automated capture assertions

Before every Settings frame, the native probe requires zero horizontal scroll
range; all visible interactive widgets inside their content viewport; no
footer/final-card overlap; no unintended title, navigation, or button elision;
no clipping at 150% application font; legible selected text; action-local
feedback; Save enabled after failure; and Save disabled after success.

The plan contains 106 native frames: 104 initial and two controlled-restart
states. It includes all four Settings pages at 720/default/full widths and
100%/150% application font, Anki light/dark representatives, custom-color
validation, event and verse long rows, future off/on, Advanced appearance,
dirty close, saving, production-safe failure, geometry restore, legacy route,
and restart-clean states. Every frame must appear exactly once in validated
detail-sheet coverage.

## Exact-package release gate

Run the Python, JavaScript, contract, builder, source-parity, process,
filesystem, profile, sync-disabled, statistics, save, and controlled-restart
gates against one 24-member candidate. The assembler rejects evidence unless
all reports reference that package hash and the same capture-plan hash.

Six native platform profiles are mandatory:

- Windows at 100%, 125%, and 150% OS display scaling
- Linux at 100% and 150% OS display scaling
- DPR 1 and macOS Retina or equivalent high-DPR rendering

Environment-variable scale substitutes do not count. Each report records OS,
Anki version, Qt platform, logical and physical geometry, DPI, DPR, application
font coverage, package hash, and plan hash. The macOS report additionally must
pass both full-screen opening paths, all four pages, Events tabs, move/resize,
save/close/reopen, and hard restart without a Space switch.

VoiceOver and forced-colors may remain explicitly unrun and nonblocking. Any
missing Windows, Linux, DPR, OS-scaling, or macOS full-screen evidence is a hard
failure. Do not publish, merge as a release, or mark `release_ready` until all
blocking profiles pass.
