# Home Dashboard - Overhaul 1.5.3 release acceptance

Status: **HISTORICAL RECORD — automated release candidate**

The raw 1.5.3 capture bundle and packaged artifact were removed from the
current tree on 2026-08-25 after newer complete evidence superseded them. The
checksums and results below are retained for traceability, not current release
acceptance.

Version 1.5.3 is the sole accepted release candidate. It replaces the rejected
1.5.2 package, whose exact-package Insights run exposed a first-load webview
bridge race. All machine-checkable release gates below are bound to one frozen
archive. Spoken VoiceOver remains an explicit human verification boundary and
is not represented as complete.

## Frozen artifact

- Archive: `home-dashboard-overhaul-1.5.3.ankiaddon` (no longer retained in the current tree)
- Checksum sidecar: `home-dashboard-overhaul-1.5.3.ankiaddon.sha256` (no longer retained in the current tree)
- SHA-256: `68705bc06dabd277130600f14db0c8dc907dc3b39177778a784aaaa275d01dee`
- Archive size: 126,322 bytes
- Contents: 23 allowlisted files; configuration schema 3; package version 1.5.3
- Determinism: a second build reproduced the archive byte for byte.
- Integrity: checksum, safe paths, manifest/version/schema consistency,
  source/archive byte parity, and exclusion of deferred and vendored source all
  passed.

The bridge correction waits boundedly for Anki's asynchronous webview command
bridge before dispatching an insight request, starts the response timeout only
after a successful dispatch, and leaves an unavailable bridge attempt retryable.

## Automated validation

- Python 3.12.13: 163 tests passed, 0 skipped.
- Dependency-free JavaScript calendar and bridge model suite: passed.
- Python compile validation: passed.
- Deterministic archive rebuild and source/archive verification: passed.

## Exact-package live acceptance

The exact archive above was installed in three distinct fresh, sync-disabled
disposable profiles under Anki Desktop 26.8.1. Every suite passed its initial
and controlled-restart process, unique-window, disposable-filesystem, package,
and sync identity gates. The normal Anki base and collection fingerprints were
unchanged before and after the full run.

| Suite | Captures | Result | Scope |
| --- | ---: | --- | --- |
| Calendar | 28 | Passed | Year and Month, responsive boundaries, themes and scaling, date details, events, all-hidden recovery, partial/unavailable data, loading, legacy activation, keyboard behavior, safe text, and persistence |
| Settings | 20 initial + 1 restart | Passed | Every page, desktop and minimum sizes, event and verse editors, accessibility geometry, dependencies, conflicts, staged changes, and persistence |
| Insights | 11 initial + 1 restart | Passed | Current/past/future and empty states, exact copy/actions, responsive and scaled layouts, DOM/backend agreement, reloads, and restart |

The superseded evidence bundle contained all 61 raw captures, 20
overview/detail contact sheets, the exact archive and sidecar, and three
sanitized reports. Those files are no longer retained in the current tree;
their recorded identifiers were:

- Bundle: `live-ui-acceptance-1.5.3-release-2026-08-15/`
- Machine-readable index: `release-evidence.json`, SHA-256 `8a9b45c96ac64f3fe80344a97d424bb54785c4c8b9109ed87e997aa25f66a297`
- Calendar report SHA-256: `e09a995fac90f5037247bbeafd7f7df491d668392249fb760ed1b8238e4ba822`
- Settings report SHA-256: `759899992e0ee4b7d32d148b3a53274aeb8e58086b64fbd4df0f100027dc4775`
- Insights report SHA-256: `039a95c2508f7d5cda1d009671a9184fa120b935c466cf7e7bc100d07fdb05dd`

The Calendar report also passed the independent fail-closed validator against
the artifact bytes, checksum sidecar, release manifest, exact ordered 28-surface
contract, package parity, restart state, and identity results.

## Closure

- [x] Complete Python suite passed without skips under Python 3.10 or newer;
  JavaScript model suite passed.
- [x] Final deterministic archive, checksum sidecar, allowlist, safe paths,
  version/schema consistency, and source/archive byte parity verified.
- [x] Every live report is bound to the exact artifact bytes.
- [x] Fresh, distinct, sync-disabled profiles passed initial and restart
  identity gates without changing the normal Anki base.
- [x] Complete Calendar, Settings, and Insights automated UI contracts passed.
- [ ] Spoken VoiceOver listening pass. This remains human-required and was not
  run; automated semantics, keyboard, focus, sizing, contrast, and containment
  checks passed.

At the time of this record, the archive was accepted for distribution.
Repository publication was a separate operational boundary. The current tree
retains only the newest complete 1.8.6 evidence set; this 1.5.3 bundle remains
available through Git history.

The rejected 1.5.2 record remains available for traceability in
[`release_acceptance_1.5.2.md`](release_acceptance_1.5.2.md).
