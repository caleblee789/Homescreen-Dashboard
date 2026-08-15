# Home Dashboard Overhaul 1.5.3 — release UI evidence

This is the canonical, exact-package UI acceptance bundle for release 1.5.3.
All three automated live suites completed successfully in Anki Desktop 26.8.1
using fresh, sync-disabled disposable profiles. Initial and restart identity
gates passed for every suite.

- Candidate: `home-dashboard-overhaul-1.5.3.ankiaddon`
- SHA-256: `68705bc06dabd277130600f14db0c8dc907dc3b39177778a784aaaa275d01dee`
- Archive contents: 23 allowlisted files
- Calendar: 28 ordered captures
- Settings: 20 initial captures plus 1 restart-persistence capture
- Insights: 11 initial captures plus 1 restart capture
- Contact sheets: 20 overview/detail sheets
- Total raw captures: 61

## Automated coverage

The Calendar suite covers Year and Month views, 4/5/6-week months, year
boundaries, layout breakpoints, narrow sizing, light/dark/high-contrast modes,
150% and 200% display scale, date details, event chips and markers, hidden and
partial-data recovery, loading and legacy states, Calendar settings, Events
settings, keyboard behavior, safe text rendering, render timing, and restart
persistence.

The Settings suite covers all six pages at desktop and minimum supported sizes,
editor geometry and containment, theme variants, display scaling, accessible
names and focus order, dependency controls, dirty/cancel/discard behavior,
conflict recovery, appearance-only save behavior, event and verse editing, and
saved-state persistence after restart.

The Insights suite covers current, past, future, empty, deleted-card, and due
states; exact actions and visible copy; responsive and scaled layouts; dark,
light, and high-contrast appearances; safe prompt truncation; full-day ranking;
DOM-to-backend agreement; and current-day behavior after restart.

The machine-readable source of truth is `release-evidence.json`. It binds the
included archive to the three deterministic suite reports and records each
report's SHA-256, byte size, raw-capture count, and contact-sheet count. Report
capture paths are relative to this directory. Machine-specific run roots,
process details, launch arguments, raw isolation keys, and exact profile/window
titles were intentionally removed; only Anki version, profile fingerprints,
and boolean identity results remain.

## Accessibility boundary

Automated accessibility semantics, keyboard, focus, sizing, contrast, and
containment checks passed. A spoken VoiceOver pass was not run and remains a
human-required, explicitly incomplete acceptance item. This bundle therefore
closes the automated UI scope but does not claim completed spoken screen-reader
acceptance.
