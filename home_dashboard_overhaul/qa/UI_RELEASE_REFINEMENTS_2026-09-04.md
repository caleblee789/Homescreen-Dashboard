# UI release refinements — 4 September 2026

The approved Settings reorganization and restrained dashboard refinements are
implemented. No dashboard overhaul was needed. The existing calendar, insight
rail, summary cards, deck table, navigation, and bottom actions retain their
composition.

Candidate: `cf11263491f2310aba3b4785f31596a33bd430f7fb320b7e0c64da7b091121c4`.
Capture plan: `026d1bbd0190942e9faa161463aa4432a1f74000c8f0ac5848ac7d7de3ee0365`.
Independent human approval remains required; `release_ready` is `false`.

[Installable candidate](release-evidence-1.8.7-2026-09-04-cf112634-ui-final/package/hdo-ui-candidate-cf112634.ankiaddon)
· [Contact sheets and native evidence](release-evidence-1.8.7-2026-09-04-cf112634-ui-final/README.md)
· [Evidence manifest](release-evidence-1.8.7-2026-09-04-cf112634-ui-final/capture-evidence-manifest.json)

## Review basis and scope

The review began with all 18 sheets in the retained
[30 August exact-package evidence](release-evidence-1.8.7-2026-08-30-4d0a4107-ui-readiness-100/README.md)
and the newer 31 August Retina Month/Year spacing captures. Raw frames and
their manifests were used to resolve details too small to judge on a sheet.
Historical captures remain unchanged. The pre-existing analytics, performance,
theme, and dashboard spacing work in the checkout was retained.

The dashboard pass covered all four themes and their 16 light/dark completion
palettes, Month and Year, markers, legends, custom backgrounds, optional sections,
verse typography, responsive stacking, and native bottom-action clearance.
The Settings pass covered navigation, grouping, card alignment, control labels,
previews, library and event lists, empty and searched states, editors, resets,
save feedback, errors, geometry restoration, and light/dark appearance.

## Findings and implemented changes

| Area | Issue found | Result |
| --- | --- | --- |
| Settings navigation | Dashboard mixed visibility, appearance, calendar, and local-data choices. The old four-page organization made controls difficult to find. | Six pages: Dashboard, Appearance, Calendar, Events, Bible verse, About & support. Old appearance/calendar links resolve to their new pages. |
| Dashboard settings | Unrelated appearance and calendar controls made the page long. Placement was grouped with appearance. | Dashboard now owns sections, study metrics, panel placement, and deck filters. Card resets follow the controls they own. |
| Calendar settings | Common calendar controls were hidden behind a disclosure; history cutoff was separated from its range. | Calendar display and range are directly visible. Custom cutoff belongs with history range, with help explaining its wider history effect. |
| Responsive Settings | Six destinations would crowd the previous compact tabs. Adjacent cards stretched to inconsistent heights. | The 184 px sidebar remains at supported widths, including 860 px. Constrained screens use a labelled Section selector. Cards align at the top and stack at narrow widths. |
| Bible organization | Display/rotation controls displaced the library, and nested scrolling wasted useful space. | Library is the default view. Display & rotation has its own tab and scroll area. The library list uses the remaining viewport while its actions stay visible. |
| Minimum-size library | Visual inspection found bottom actions outside the 860×640 viewport despite the original geometry check passing. | The list's native size hint now permits it to shrink. The existing runtime check includes the list, search, add, current-selection, and editing action groups against the actual page viewport. |
| Bible state and appearance | Current versus staged selection relied too heavily on visual indicators. Light-mode delegate rows could retain dark colors. Preview styling did not accurately represent the selected verse. | Rows label Current and Pending save. They use their Settings window's palette. The preview renders the selected verse at its selected font size against staged dashboard colors, with contrast and invalid-color feedback. |
| Editors | Field order and constrained body sizing made important content hard to inspect. | Event Name and Date and verse Reference and Body remain visible. Native editor chrome and parented modal ownership remain intact. |
| Save feedback | Error content crowded the footer and lacked internal spacing. | A padded error region sits above the fixed action footer. Retry, details, copy error, and retained draft behavior remain available. |
| Dashboard empty verse | No verse selected offered no direct recovery action. | Choose a verse opens the Bible library. |
| Dashboard averages | Identical average labels used different denominators without an explanation. | Tooltips distinguish all seven study-day periods from days with recorded study activity. Visible metric names remain stable. |

Schema 8, stored keys and values, staged Save/Discard behavior, the native
`QDialog(mw).exec()` lifecycle, the 1080×760 default, the 860×640 supported
minimum, and geometry restoration remain intact. The dashboard retains the
1160 px composition, 360 px insight rail, 14 px column gap, 12 px summary gap,
and literal `N% complete` label inside the progress bar.

## Validation and review

- Existing Python suite: 325 tests passed. Tests were updated where behavior or
  ownership changed; no additional narrow unit tests were added.
- Calendar JavaScript checks and both current UI contract validators passed.
- The package builder verifies the 24-member allowlist, safe paths, version,
  and source/archive byte parity.
- The capture contract now contains 116 frames: 114 initial and two after
  controlled restart. Its Settings subset has 63 frames, including all seven
  page/view combinations in light mode and at the supported minimum.
- The final review set contains **115 accepted native frames in 21 contact
  sheets**, including all 63 Settings frames. Every accepted frame appears
  exactly once in the 19 detail sheets. The overview and report make up the
  other two sheets. All 21 sheets and close-ups of the editors, error region,
  minimum-size library, light-mode list, previews, and empty verse action
  received model visual review.
- `PROD-PAL-HC-GOLD-L` was obstructed by another application and is omitted at
  the user's explicit request. This is one omitted palette/color-mode state,
  not a claim of 116 visually accepted frames.
- The full sequence's `SET-EVENT-EDITOR-OPEN` was also obstructed. It was
  replaced by an already captured, unobstructed native frame with identical
  package and plan hashes, the same scenario and fixtures, 24 byte-matched
  installed package members, and the same Retina display and font settings.
  The probe difference adds only OS/Qt metadata. No new capture run was made.
  [Curation provenance](release-evidence-1.8.7-2026-09-04-cf112634-ui-final/reports/visual-curation.json)
  records the omitted and replaced hashes. Raw runtime reports keep their
  original automated results; they do not represent visual acceptance.
- Native full-screen workflow: **66 observations passed** across initial and
  controlled-restart processes, covering both the menu and production
  dashboard gear. Eight supplemental images verify Pending save and Current
  labels before and after save for both routes and stages. They are separate
  from the 115 canonical frames and were also visually reviewed.

The visual iteration rejected earlier candidates after finding native Bible
tab/background defects, minimum-size library clipping, and inconsistent
light-mode list colors. Editor and save-error acceptance now requires actual
native compositor captures; a composited fallback cannot stand in for them.
The focused harness also establishes its requested monitor when production
captures are omitted.

The fullscreen workflow separately checks the menu and production dashboard
gear, all six pages and both Bible views, Events tabs, resize, event and verse
editors, save, close/reopen, and a controlled restart. Native AppKit window,
display, and active-Space observations distinguish real retention from a Qt
fullscreen flag. It waits for the Space animation to finish and records
foreground-app interruptions. Automated observations do not constitute
independent human approval.

The `FULL` page-size captures show maximized, decorated Settings windows;
native macOS full-screen Space behavior is proved separately by the workflow
observations. The evidence includes the generated standard and focused
capture helpers with verified member hashes, plus the actual executed
full-screen workflow probe. Rejected images and their affected draft sheets
were retained outside the final bundle. Historical release evidence and the
original captures in the disposable runs remain unchanged.

## Remaining release decision

An independent human must review the final sheets and native interaction
results before release approval. Windows, Linux, alternate native display
scaling, alternate application-font percentages, VoiceOver, forced colors,
and reduced motion remain unrun and unclaimed; they remain the previously
declared nonblocking boundaries for this release. No publication or merge is
part of this implementation.
