# Home Screen Dashboard 1.8.6 native release evidence

This immutable evidence set was assembled from the exact reproducible package
`home-dashboard-overhaul-1.8.6.ankiaddon` with SHA-256 `095bada7a6daf7cb9687feee81fb5918cacca1b51cfc62959c431fce120da724`.

- `captures/` contains 94 native frames derived from the current implementation
  contract: 92 initial and two controlled-restart frames.
- The 19 generated contact sheets are retained as local-only release evidence
  and intentionally excluded from version control. Their 18 detail sheets cover
  every native frame exactly once; the final sheet summarizes package and
  isolation proof.
- `reports/runtime-report-initial.json` and `runtime-report-restart.json` retain
  exact-package, scheduler-count, Settings, persistence, and all four isolation
  gates.
- `reports/archive-inspection.json` proves the 24-member allowlist, safe paths,
  and source/archive byte parity.

VoiceOver, Windows, Linux, forced-colors, DPR 1, and OS display-scaling
acceptance were not run and are not claimed.
