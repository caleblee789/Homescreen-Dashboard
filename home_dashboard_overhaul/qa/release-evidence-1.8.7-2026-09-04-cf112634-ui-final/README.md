# Home Screen Dashboard 1.8.7 final UI review evidence

This frozen review set contains **115 accepted native frames in 21 contact
sheets**, plus eight supplemental full-screen workflow images. It identifies
the six-page Settings reorganization and dashboard refinements described in the
[implementation report](../UI_RELEASE_REFINEMENTS_2026-09-04.md).

Candidate SHA-256: `cf11263491f2310aba3b4785f31596a33bd430f7fb320b7e0c64da7b091121c4`.
Capture-plan SHA-256: `026d1bbd0190942e9faa161463aa4432a1f74000c8f0ac5848ac7d7de3ee0365`.

[Installable candidate](package/hdo-ui-candidate-cf112634.ankiaddon) ·
[Overview](contact-sheets/contact-sheet-00-overview.png) ·
[Final validation](reports/final-validation.json)

The 325 Python tests, JavaScript checks, both UI contract validators, native
layout checks, exact 24-member package parity, restart persistence, and native
macOS full-screen workflow passed. Model visual review of the retained sheets
and supplemental images passed. **Independent human review remains unrun:**
`quality_status: review-required`, `release_ready: false`.

## Evidence scope and curation

The unchanged full capture plan calls for 116 frames. This review set retains
113 initial-state frames and two controlled-restart frames. All 63 Settings
frames are present. `PROD-PAL-HC-GOLD-L` was covered by another application;
the user explicitly requested that it be omitted without another capture run.

An unrelated window also obscured the full sequence's event-editor image.
`SET-EVENT-EDITOR-OPEN` uses the existing unobstructed focused capture from the
identical package, plan, scenario, and fixtures. Installed package bytes match
for all 24 members. The native display, DPR, and application font match; the
only release-probe difference adds OS/Qt metadata. The generated helpers and
source report are retained. No new capture run was made during curation.

The [curation record](reports/visual-curation.json) lists original and accepted
hashes. Original runtime reports keep their automated 116-frame results and
precede visual curation; their capture lists are not the final review manifest.
Rejected PNGs and affected draft sheets were preserved outside this bundle.
Historical evidence and the raw disposable-run captures remain unchanged.

The [capture manifest](capture-manifest.json) is the authority for the 115
accepted frames. The [sheet index](contact-sheets/contact-sheet-index.json)
records exact-once coverage across 19 detail sheets, plus one overview and
one report sheet. The [visual review](reports/visual-review.json) records the
reviewed sheet and supplemental-image hashes.

## Native interaction and package proof

- [Native platform profile](reports/platform-profile.json): macOS 26.6.2,
  Anki 26.8.1, Built-in Retina Display, DPR 2, 100% application font.
- [Structured layout](reports/settings-structured-layout.json): all six pages
  and both Bible views at the canonical font, plus disconnected-monitor
  geometry restoration.
- [Full-screen initial workflow](reports/fullscreen-workflow/workflow-initial.json)
  and [controlled restart](reports/fullscreen-workflow/workflow-restart.json):
  66 native observations through the actual menu action and production
  dashboard gear, covering navigation, Events tabs, resize, event/verse edits,
  save, and close/reopen. AppKit records the parent and child windows' display
  and active-Space state. These are automated observations, not pointer-only
  human acceptance.
- [Full-screen provenance](reports/fullscreen-workflow/provenance.json): actual
  executed workflow source and eight Pending save/Current images. These
  supplement the 115 canonical frames. `FULL` page-size captures show
  maximized decorated windows; the workflow separately proves native Spaces.
- [Archive inspection](reports/archive-inspection.json) and
  [isolation gates](reports/isolation-gates.json): source/package byte parity
  and separate disposable, sync-disabled profiles before and after restart.

Windows, Linux, DPR 1, alternate application-font percentages, alternate OS
display scaling, VoiceOver, forced colors, and reduced motion remain unrun,
unclaimed, and previously declared nonblocking. Nothing has been published
or merged as part of this implementation.

## Contact sheets

| Sheet | Accepted frames |
| --- | ---: |
| [Canonical UI release overview](contact-sheets/contact-sheet-00-overview.png) | 115 |
| [Production palettes · Sapphire Glass](contact-sheets/contact-sheet-01-production-palettes-sapphire-glass.png) | 8 |
| [Production palettes · Graphite](contact-sheets/contact-sheet-02-production-palettes-graphite.png) | 8 |
| [Production palettes · Emerald](contact-sheets/contact-sheet-03-production-palettes-emerald.png) | 8 |
| [Production palettes · High Contrast](contact-sheets/contact-sheet-04-production-palettes-high-contrast.png) | 7 |
| [Production Month, Year, and marker combinations](contact-sheets/contact-sheet-05-production-month-year-and-marker-combinations.png) | 7 |
| [Production legends, backgrounds, sections, clearance, and verse](contact-sheets/contact-sheet-06-production-legends-backgrounds-sections-clearance-and-verse.png) | 9 |
| [Settings Dashboard · 100% application font](contact-sheets/contact-sheet-07-settings-dashboard-100-application-font.png) | 5 |
| [Settings Appearance · widths and native themes](contact-sheets/contact-sheet-08-settings-appearance-widths-and-native-themes.png) | 7 |
| [Settings Calendar · widths and ranges](contact-sheets/contact-sheet-09-settings-calendar-widths-and-ranges.png) | 7 |
| [Settings Events · 100% application font](contact-sheets/contact-sheet-10-settings-events-100-application-font.png) | 5 |
| [Settings Bible verse · 100% application font](contact-sheets/contact-sheet-11-settings-bible-verse-100-application-font.png) | 5 |
| [Settings Bible display & rotation · widths and native themes](contact-sheets/contact-sheet-12-settings-bible-display-rotation-widths-and-native-themes.png) | 5 |
| [Settings About · 100% application font](contact-sheets/contact-sheet-13-settings-about-100-application-font.png) | 5 |
| [Settings Events states](contact-sheets/contact-sheet-14-settings-events-states.png) | 7 |
| [Settings Bible states](contact-sheets/contact-sheet-15-settings-bible-states.png) | 5 |
| [Settings dirty, discard, save, and error](contact-sheets/contact-sheet-16-settings-dirty-discard-save-and-error.png) | 6 |
| [Settings About bottom, legacy route, fresh open, and clamp](contact-sheets/contact-sheet-17-settings-about-bottom-legacy-route-fresh-open-and-clamp.png) | 5 |
| [Statistics accuracy · responsive shells](contact-sheets/contact-sheet-18-statistics-accuracy-responsive-shells.png) | 4 |
| [Controlled restart persistence](contact-sheets/contact-sheet-19-controlled-restart-persistence.png) | 2 |
| [Package and isolation reports](contact-sheets/contact-sheet-20-package-and-isolation-reports.png) | Report |
