# Release visual contract

Status: Home Screen Dashboard 1.8.7 implementation, automated, exact-package,
and required macOS native gates complete; independent human review remains
required, so `release_ready` remains false.

## Authority and retained evidence

The current machine-readable authorities are:

- `qa/capture_plan.json`, the sole executable case/count/order authority
- `qa/calendar_surface_manifest_1_8_7.json`
- `qa/ui-surface-registry_1_8_7.json`
- `qa/visual_regression_matrix_1_8_7.json`
- `qa/capture_evidence_manifest_1_8_7.json`
- `qa/settings_window_contract_1_8_7.json`
- `qa/runtime_probe_release_1_8_7_manifest.json`

The retained exact-package candidate is
`4d0a410721ba5af43cd672127531eefc90795881ef4f9e755a6fb8550aa61994`.
Its `qa/release-evidence-1.8.7-2026-08-30-4d0a4107-ui-readiness-100`
directory contains the complete 94-frame profile, 18 contact sheets, package
and contract snapshots, archive/source parity, restart persistence, and all
four isolation gates. The companion
`qa/macos-retina-platform-1.8.7-2026-08-30-4d0a4107-ui-readiness` report records
passing pointer-only menu and Dashboard-gear full-screen workflows before and
after controlled restart. The status remains `review-required` rather than
release approval because independent human review is unrun. A corrected
candidate must always write a new evidence directory and never overwrite an
existing result. Superseded sets may be removed only after the retained current
set is hash-verified and a recoverable safety snapshot captures every deletion
target.

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
- Geometry uses logical coordinates: 1080×760 default, 860×640 normal minimum,
  48 px normal margins, and a 24 px constrained-screen fallback.
- `settings_dialog_geometry/v4` stores logical geometry, screen identity,
  available bounds, and informational DPR. A v3 record migrates only when it
  meets the new minimum, names a connected screen, and remains at least 80%
  visible. Maximized/full-screen geometry is never saved.
- The shell is a fixed header, `min-height: 0` body, reserved error region, and
  separate fixed 56 px action footer. Each page owns one vertical
  `QScrollArea`; horizontal scrolling is disabled.
- The centered shell is capped at 1,264 px. A 184 px sidebar spans the 72 px
  baseline page header, scrolling page body, error region, and footer; every
  page column is capped at 1,080 px.
- Vertical navigation remains active above the compact boundary. At the
  supported 860 px minimum, the page title stays above one synchronized,
  non-eliding row of top navigation.
- Cards and toolbars reflow using current width and font metrics. At 760 px of
  page content, related cards form deliberate pairs while Appearance remains
  full width. Navigation never changes native window geometry.

## Settings surfaces and behavior

- Dark and light Settings roles follow Anki's live palette only. Dashboard
  Color mode changes production output, not dialog chrome or a Settings preview.
- Role fonts are application-relative, visible text is at least 12 px at the
  100% baseline, ordinary controls are at least 34 px high, list rows are
  54 px or taller where specified, and the action footer is fixed at 56 px.
- Selected navigation and verse rows use accent-soft surfaces and a substantial
  accent edge. Events tabs use neutral graphite surfaces. Event rows have no
  persistent selection; activation opens the editor.
- Dashboard contains Appearance, Dashboard sections, Study metrics, Calendar
  display, and Calendar range. The heatmap selector includes a compact
  five-step palette preview; Reset is scoped and never saves immediately.
- Events shows one empty-state Add action while empty, then a populated-toolbar
  Add action. Its search/sort toolbar, Active/Archived tabs,
  naturally growing 54 px baseline rows, five-row scrolling threshold,
  distinct empty/no-results states, and a shared parented window-modal editor
  480–540 px wide and at most 80% of the Settings body are asserted.
- Bible verse contains Appearance, Rotation, a compact live appearance preview,
  and a flexible Verse library; equal-width color-source segments; the retained
  custom-color well; one blocking inline hex error; and clamped two-line
  library excerpts.
- About contains Version and support, Privacy and legal, and Backup and recovery,
  with manifest-derived `Supports Anki Desktop 26.8` compatibility copy.
- Dirty, saving, success, and discard feedback stays in the action footer;
  validation and save failures use the reserved region above it. Failed saves
  retain the complete draft and expose View details and Copy error. Dirty close
  uses Cancel, Discard changes, and Save and close in the existing scrimmed
  in-window prompt.

## Automated capture assertions

Before every Settings frame, the native probe requires zero horizontal scroll
range; all visible interactive widgets inside their content viewport; no
footer/final-card overlap; no unintended title, navigation, or button elision;
preview integrity; legible selected text at 100% application font; action-local
feedback; Save enabled after failure; and Save disabled after success.

The Settings profile is a hard ceiling of exactly 41 frames: 40 initial states
and one controlled restart. Twelve page frames cover all four pages at
1080×760, 1280×800, and full screen, all at 100% application font. The other
28 initial frames cover interaction, geometry, feedback, preview, and theme
states and rename the standard window state to fresh-open. Every frame must
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

The 1.8.7 Settings release scope does not run the expanded platform or
alternate-scale matrices. These cases remain explicitly unrun and nonblocking
rather than being inferred from the 41-frame visual acceptance set:

- Windows at 100%, 125%, and 150% OS display scaling
- Linux at 100% and 150% OS display scaling, both with DPR 1
- DPR 1 and alternate native display scaling

Environment-variable scale substitutes do not count. Each report records OS,
Anki version, Qt platform, logical and physical geometry, DPI, DPR, application
font coverage, package hash, and plan hash. The required macOS Retina report
carries passing structured layout assertions for all four Settings pages and
must pass the complete per-route full-screen workflow without a Space switch.

VoiceOver, forced-colors, Windows, Linux, DPR 1, OS scaling, reduced motion,
and alternate application-font percentages may
remain explicitly unrun and nonblocking. Missing macOS Retina 100% or macOS
full-screen evidence is a hard failure. Even after both blocking macOS gates
pass, do not mark `release_ready` until independent human review of every
contact sheet and the native interaction result is recorded.
