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

The current exact-package candidate is
`cf11263491f2310aba3b4785f31596a33bd430f7fb320b7e0c64da7b091121c4`.
Its `qa/release-evidence-1.8.7-2026-09-04-cf112634-ui-final` directory retains
115 accepted frames in 21 sheets against the unchanged 116-frame plan. All
63 Settings frames are present. The user requested omission of the obstructed
High Contrast Gold/light frame. The event editor uses a verified existing
focused capture with identical package, plan, and fixture/rendering dependencies.
The bundle's curation record distinguishes the accepted set from the original
automated runtime results.

Required macOS Retina layout and native full-screen checks passed. The menu
and production Dashboard gear each cover page navigation, Events tabs, resize,
event/verse edits, save, close/reopen, and controlled restart. The 66 AppKit
observations prove parent/child display and active-Space retention. Eight
supplemental Pending save/Current images accompany those automated reports.
These observations do not constitute independent human acceptance.

The previous 30 August release evidence and 31 August spacing inputs remain
historical provenance. A corrected candidate must write a new evidence
location; never overwrite a frozen result. The final release decision remains
`quality_status: review-required` and `release_ready: false` until independent
human review of the sheets and native interactions is recorded.

## Production composition

- The dashboard remains at most 1,160 px wide with normal document scrolling
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
  separate fixed 56 px action footer. Pages scroll vertically as needed;
  the Bible Library scrolls its list only, while Display & rotation owns a
  separate scroll area. Horizontal scrolling is disabled.
- The centered shell is capped at 1,264 px. A 184 px sidebar spans the 72 px
  baseline page header, scrolling page body, error region, and footer; every
  page column is capped at 1,080 px.
- The 184 px sidebar remains active at the supported 860 px minimum.
  Constrained screens use a labelled Section selector. Navigation never
  squeezes the six destinations into a horizontal tab row.
- Cards and toolbars reflow using current width and font metrics. At 760 px of
  page content, related cards form deliberate pairs while Appearance remains
  full width. Navigation never changes native window geometry.

## Settings surfaces and behavior

- Dark and light Settings roles follow Anki's live palette only. Dashboard
  Color mode changes the dashboard and verse preview, while dialog chrome
  continues to follow Anki.
- Role fonts are application-relative, visible text is at least 12 px at the
  100% baseline, ordinary controls are at least 34 px high, list rows are
  54 px or taller where specified, and the action footer is fixed at 56 px.
- Selected navigation and verse rows use accent-soft surfaces and a substantial
  accent edge. Events tabs use neutral graphite surfaces. Event rows have no
  persistent selection; activation opens the editor.
- Dashboard contains section visibility, Study metrics, Panel placement, and
  Deck exclusions and filters. Appearance owns theme, palette, scale, opacity,
  and blur. Calendar owns the display and history/future ranges. Custom cutoff
  help explains its effect on historical metrics. Reset follows each card's
  scope and never saves immediately.
- Events shows one empty-state Add action while empty, then a populated-toolbar
  Add action. Its search/sort toolbar, Active/Archived tabs,
  naturally growing 54 px baseline rows, five-row scrolling threshold,
  distinct empty/no-results states, and a shared parented window-modal editor
  480–540 px wide and at most 80% of the Settings body are asserted.
- Bible verse opens to Library with a flexible list and persistent actions.
  Current and Pending save labels distinguish committed and staged choices.
  Display & rotation holds typography, color, rotation, and the selected verse
  preview at its chosen size against staged dashboard colors. Invalid hex
  blocks saving; low contrast remains an optional warning.
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

The Settings profile contains exactly 63 frames: 62 initial states and one
controlled restart. Twenty-one page frames cover six pages and both Bible
views at 1080×760, 1280×800, and a maximized decorated size, all at 100%
application font. The other 41 initial frames cover interaction, geometry,
feedback, previews, all views at the supported minimum, and native light/dark
appearance. Each retained frame must appear exactly once across no more than
14 compact Settings sheets. The 720, 940, and 150%-font page matrices remain
outside the canonical profile.
Every Settings PNG must sample-match the live client; all 21 page frames must
include the complete decorated native Settings window. Event/verse editors
and save-error states require the actual native compositor. Visual review is
still necessary to reject foreign-window occlusion missed by sampling.

Small-screen fallback, two legacy geometry sizes, valid 1180×800 restore,
secondary/disconnected screen handling, 80% visibility, and no post-show shrink
are structured assertions rather than additional PNGs. A canonical-100%
structured pass also checks all six pages and both Bible views in a 1366×768
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
63 PNGs cannot waive this gate.

## Exact-package release gate

Run the Python, JavaScript, contract, builder, source-parity, process,
filesystem, profile, sync-disabled, statistics, save, and controlled-restart
gates against one 24-member candidate. The assembler rejects evidence unless
all reports reference that package hash and the same capture-plan hash.

The 1.8.7 Settings release scope does not run the expanded platform or
alternate-scale matrices. These cases remain explicitly unrun and nonblocking
rather than being inferred from the 63-frame Settings capture profile:

- Windows at 100%, 125%, and 150% OS display scaling
- Linux at 100% and 150% OS display scaling, both with DPR 1
- DPR 1 and alternate native display scaling

Environment-variable scale substitutes do not count. Each report records OS,
Anki version, Qt platform, logical and physical geometry, DPI, DPR, application
font coverage, package hash, and plan hash. The required macOS Retina report
carries passing structured layout assertions for all six Settings pages and both Bible views and
must pass the complete per-route full-screen workflow without a Space switch.

VoiceOver, forced-colors, Windows, Linux, DPR 1, OS scaling, reduced motion,
and alternate application-font percentages may
remain explicitly unrun and nonblocking. Missing macOS Retina 100% or macOS
full-screen evidence is a hard failure. Even after both blocking macOS gates
pass, do not mark `release_ready` until independent human review of every
contact sheet and the native interaction result is recorded.
