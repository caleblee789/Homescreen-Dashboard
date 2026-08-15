# Home Dashboard - Overhaul 1.5.2 release acceptance

Status: **REJECTED — superseded after an exact-package live Insights failure**

This is the historical rejection record for version 1.5.2. The sole current
release-status record is
[`release_acceptance_1.5.3.md`](release_acceptance_1.5.3.md).

## Rejected candidate

- Archive: `home-dashboard-overhaul-1.5.2.ankiaddon` (rejected artifact; not
  retained in the publishable release evidence)
- SHA-256: `d6cb8984fe10832b8a735fd07196e50eee1b5d3ea8cdc3f79a81258c71bbd2bb`
- Checksum sidecar: `home-dashboard-overhaul-1.5.2.ankiaddon.sha256`
- Package boundary: 23 allowlisted files, 125,938 bytes, deterministic second
  rebuild matched, source/archive bytes matched, and no deferred/vendor source
  entered the archive.
- Automated validation before live QA: 151 Python tests passed with zero skips
  under Python 3.12.13; the dependency-free JavaScript calendar suite and full
  source compile passed.

## Why it was rejected

Fresh sync-disabled Anki 26.8 exact-package testing exposed a first-render bridge
race in the Study Insight rail. On initial load, dashboard reload, and controlled
restart, the web page could request today's insight before Anki had installed its
asynchronous webview command bridge. The request was silently dropped, the rail
remained pending until its fallback timeout, and the populated current-day state
rendered as **Study insight unavailable.**

Direct backend evidence still contained the expected current-day insight, and
later requests worked once the bridge existed. That isolates the failure to
first-load request dispatch; it does not make the failed UI states acceptable.
The Settings and Calendar surface results from this archive cannot override the
failed Insights gate.

Version 1.5.2 was never accepted or released. Any screenshots or passing checks
from its partial live matrix remain diagnostic evidence only and must not be used
to accept version 1.5.3.
