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

The completed `qa/release-evidence-1.8.6-2026-08-25` directory remains the
retained full 94-frame baseline. The current 1.8.7 review candidate is
`c4b794f0b4e1bcf4c380b0092c9436f0594f7f26d12ae9af2345a03e2eb39a3f`.
Its `qa/home-dashboard-evidence-1.8.7-2026-08-27-c4b794f0-fresh-100`
directory contains 42 native Dashboard and interaction-state frames at 100%,
and `qa/settings-evidence-1.8.7-2026-08-27-c4b794f0-fresh-100` contains all 41
100%-font Settings frames. The Settings set remains
`review-incomplete-nonrelease` because the native macOS full-screen menu and
Dashboard-gear opening-path checks were explicitly skipped. These focused
1.8.7 sets are not a replacement for the complete release gate. A corrected
candidate must always write a new evidence directory and never overwrite an
existing result. Superseded or failed local Settings sets may be removed only
after the retained current set is identified and a recoverable safety snapshot
has captured every deletion target.

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
  unconditional post-show movement, raising, or activation.
- Geometry uses logical coordinates: 1080×760 default, 820×600 normal minimum,
  48 px normal margins, and a 24 px constrained-screen fallback.
- `settings_dialog_geometry/v4` stores logical geometry, screen identity,
  available bounds, and informational DPR. A v3 record migrates only when it
  meets the new minimum, names a connected screen, and remains at least 80%
  visible. Maximized/full-screen geometry is never saved.
- The shell is a fixed header, `min-height: 0` body, and fixed footer. Each page
  owns one vertical `QScrollArea`; horizontal scrolling is disabled; page
  bottom padding equals the live footer height plus 16 logical pixels.
- The shell is capped at 1,120 px. A 184 px sidebar spans the 72 px baseline
  page header, scrolling page body, and 60 px baseline footer; header, footer,
  rows, and actions grow with application fonts. Ordinary pages are capped at
  920 px and About at 840 px.
- Vertical navigation remains active in normal operation. A synchronized top
  navigation activates whenever the sidebar would leave less than 680 px for
  the main region; the 820 px supported minimum therefore uses compact nav.
- Cards and toolbars reflow using current width and font metrics. Settings has
  no rendered preview cards or preview-only reflow branch. Navigation never
  changes native window geometry.

## Settings surfaces and behavior

- Dark and light Settings roles follow Anki's live palette only. Dashboard
  Color mode changes production output, not dialog chrome or a Settings preview.
- Role fonts are application-relative, visible text is at least 12 px at the
  100% baseline, ordinary controls are at least 36 px high, list rows are
  54 px or taller where specified, and the action footer is fixed at 60 px.
- Selected navigation and verse rows use accent-soft surfaces and a substantial
  accent edge. Events tabs use neutral graphite surfaces. Event rows have no
  persistent selection; activation opens the editor.
- Dashboard contains Appearance, Dashboard sections, Study metrics, and
  Calendar display. Text selectors replace palette/theme/heatmap previews;
  Reset is scoped and never saves immediately.
- Events shows both header and empty-state Add actions only while empty, then a
  populated-toolbar Add action. Its search/sort toolbar, Active/Archived tabs,
  naturally growing 54 px baseline rows, six-row scrolling threshold,
  distinct empty/no-results states, and parented editor capped near 440 px are
  asserted.
- Bible verse contains Appearance, Rotation, and a flexible Verse library;
  equal-width color-source segments; the retained custom-color well; one
  blocking inline hex error; and clamped two-line library excerpts.
- About contains Version and support, Privacy and legal, and Backup and recovery,
  with manifest-derived `Supports Anki Desktop 26.8` compatibility copy.
- Dirty, animated saving, success, validation, and persistence feedback is
  local to the footer. Failed saves retain all staged values and expose View
  details and Copy error. Dirty close uses Cancel, Discard, and Save and close
  in the existing scrimmed in-window prompt.

## Automated capture assertions

Before every Settings frame, the native probe requires zero horizontal scroll
range; all visible interactive widgets inside their content viewport; no
footer/final-card overlap; no unintended title, navigation, or button elision;
preview absence; legible selected text at 100% application font; action-local
feedback; Save enabled after failure; and Save disabled after success.

The Settings profile is a hard ceiling of exactly 41 frames: 40 initial states
and one controlled restart. Twelve page frames cover all four pages at
1080×760, 1280×800, and full screen, all at 100% application font. The other
28 initial frames replace obsolete preview assertions with preview-absence
assertions and rename the standard window state to fresh-open. Every frame must
appear exactly once across no more than 11 validated compact sheets. The 720,
940, and 150%-font Settings page matrices are not part of this profile.
Every PNG must also sample-match the live Settings client so a same-sized
Dashboard background cannot pass. The 12 page frames must come from the screen
compositor and include the complete decorated native Settings window.

Small-screen fallback, two legacy geometry sizes, valid 1180×800 restore,
secondary/disconnected screen handling, 80% visibility, and no post-show shrink
are structured assertions rather than additional PNGs. A canonical-100%
structured pass also checks all four pages in a 1366×768
logical work-area fixture and opens a real disconnected-monitor v4 record; it
adds no PNGs. Alternate application-font scales remain intentionally unrun.
Full-screen behavior is a mandatory structured native macOS acceptance result because a still frame
cannot prove it. The exact package must open Settings from both the menu and
Dashboard gear while remaining on Anki's full-screen Space, with no desktop or
Space switch. Through each route, the schema-v2 report records page navigation,
Events tabs, resize, event edit, verse edit, save, close/reopen, and controlled
restart as separate steps; every step must independently retain the current
Anki Space. The focused assembler
rejects a missing, failed, candidate-mismatched, or plan-mismatched report; the
41 PNGs cannot waive this gate.

## Exact-package release gate

Run the Python, JavaScript, contract, builder, source-parity, process,
filesystem, profile, sync-disabled, statistics, save, and controlled-restart
gates against one 24-member candidate. The assembler rejects evidence unless
all reports reference that package hash and the same capture-plan hash.

The minimal Settings overhaul does not run the expanded platform or
alternate-scale matrices. These release gates remain explicitly unrun rather
than being inferred from the 41-frame visual acceptance set:

- Windows at 100%, 125%, and 150% OS display scaling
- Linux at 100% and 150% OS display scaling, both with DPR 1
- DPR 1 and macOS Retina or equivalent high-DPR rendering

Environment-variable scale substitutes do not count. Each report records OS,
Anki version, Qt platform, logical and physical geometry, DPI, DPR, application
font coverage, package hash, and plan hash. Physical dimensions must agree with
logical dimensions multiplied by DPR; DPR-1 profiles must report approximately
1.0 and matching dimensions. Each native report also carries passing structured
layout assertions for all four Settings pages. The macOS report additionally
must pass the complete per-route full-screen workflow without a Space switch.

VoiceOver and forced-colors may remain explicitly unrun and nonblocking. Any
missing Windows, Linux, DPR, OS-scaling, or macOS full-screen evidence is a hard
failure. Do not publish, merge as a release, or mark `release_ready` until all
blocking profiles pass.
