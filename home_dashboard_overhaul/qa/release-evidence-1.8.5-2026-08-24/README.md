# Home Screen Dashboard 1.8.5 native release evidence

This immutable evidence set was assembled from the exact reproducible package
`home-dashboard-overhaul-1.8.5.ankiaddon` with SHA-256 `2eb15cfd1c001f5eafa2e412f4a814aa4a683d7c5b372305b44e48f4627792f1`.

- `captures/` contains 97 native frames derived from the current implementation
  contract: 95 initial and two controlled-restart frames.
- `contact-sheets/contact-sheet-00-overview.png` indexes all frames.
- The 18 detail sheets cover every native frame exactly once; the final sheet
  summarizes package and isolation proof.
- `reports/runtime-report-initial.json` and `runtime-report-restart.json` retain
  exact-package, scheduler-count, Settings, persistence, and all four isolation
  gates.
- `reports/archive-inspection.json` proves the 24-member allowlist, safe paths,
  and source/archive byte parity.

VoiceOver, Windows, Linux, forced-colors, DPR 1, and OS display-scaling
acceptance were not run and are not claimed.
