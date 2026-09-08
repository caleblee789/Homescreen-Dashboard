# Functional release audit — Home Screen Dashboard 1.8.7

The functional checks passed with the fixes below. The existing calendar/footer work was preserved and included in the rebuilt candidate. No release was published and no normal-profile add-on was installed or changed by this audit.

## Fixed user-facing bugs

- **Statistics stop updating when the calendar is hidden.** The live-update handler now mounts independently of the calendar. A real-browser reproduction stayed at 567 before the fix and changed to the expected 123 afterward.
- **The empty verse library's Add verses button does nothing.** The controller now accepts its Bible library route and opens the correct Settings page.
- **Most missed becomes stale after a refresh.** Capabilities are invalidated when data advances, outdated replies are rejected, and a pending Browser action is cancelled if the selected date changes before its query completes.
- **Calendar refresh and rollover leave the wrong period visible.** Refresh requests the currently displayed range again; following Today also moves the calendar across month/year boundaries. The browser reproduction remained in 2026 before the fix and moved to 2027 afterward.
- **A newly rotated daily verse fails to appear after a live refresh.** A changed verse now remounts the rendered dashboard, while an unchanged verse retains the ordinary in-place statistics update.

[Functional source diff](functional-changes.patch) records only this audit's production edits relative to the saved working-tree baseline.

## Validation

- 327 existing/updated Python tests pass on Python 3.12.14, with no skips. Reused two controller regression tests and added one small verse-refresh test. No new test framework or dependency was added to the add-on.
- JavaScript calendar model tests, corrected UI contract, Settings window contract, and whitespace checks pass.
- Browser before/after evidence: [statistics](browser-after.json) and [calendar refresh/rollover](calendar-after.json). Both runs report no JavaScript errors. Baseline results are retained alongside them.
- Native Anki 26.8.1: menu and dashboard-gear opening routes, all six Settings pages and both Bible views, Events tabs, editor fields, resizing, event/verse saves, reopen, and controlled-restart persistence pass. Both windowed and fullscreen runs passed; fullscreen observations confirm retention on Anki's Space. Structured reports are in the four `native-*.json` files.
- The exact 25-member archive passed the repository builder and final source-byte verification. The native installed copy matched the same archive.

Candidate: `../../dist/home-dashboard-overhaul-1.8.7.ankiaddon`

SHA-256: `c6834df3a93d98607a04deafc516727cfa32affe55009be79087bab38f2514bf`

## Isolation and limits

Native QA used `/private/tmp/anki-release-qa.9gwt43qn`, profile `Codex QA Functional Audit 20260907`, instance-key fingerprint `3fc9aeffab81`. Process, window title, installed-file identity, and disconnected/disabled sync were checked before interaction. All four disposable Anki processes exited; the two excluded Anki processes were still running afterward.

This is functional evidence, not full visual release sign-off. The inspected compositor screenshot showed the desktop lock overlay; compositor captures are excluded from visual approval. The full 116-frame visual matrix was not regenerated. Windows, Linux, accessibility, and other Anki versions were not exercised. Native Settings used a disposable collection; review arithmetic and scheduler edge cases were covered by the existing automated fixtures rather than the user's real collection.
