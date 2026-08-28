# Home Dashboard 1.8.7 contact sheets — 100% only

Candidate SHA-256: `c4b794f0b4e1bcf4c380b0092c9436f0594f7f26d12ae9af2345a03e2eb39a3f`

These sheets were generated from the exact packaged add-on in a fresh, sync-disabled independent Anki profile. Every UI and text render is 100%. No 125%, 150%, or 200% cases are included.

The 42 original native screenshots remain byte-for-byte in `captures/` at Retina DPR 2. The sheets reduce those physical pixels to their corresponding logical size for pagination; this does not change the UI scale.

## Contact sheets

- [Home Dashboard 1.8.7 · Sapphire Glass](contact-sheets/01-dashboard-sapphire-glass-100-percent.png)
- [Home Dashboard 1.8.7 · Graphite](contact-sheets/02-dashboard-graphite-100-percent.png)
- [Home Dashboard 1.8.7 · Emerald](contact-sheets/03-dashboard-emerald-100-percent.png)
- [Home Dashboard 1.8.7 · High Contrast](contact-sheets/04-dashboard-high-contrast-100-percent.png)
- [Home Dashboard 1.8.7 · interaction color states](contact-sheets/05-interaction-state-fixture-100-percent.png)
- [Exact-package Home Dashboard 1.8.7 · full screen](contact-sheets/06-exact-package-full-screen-dashboard-100-percent.png)

## Evidence

- 32 dashboard captures: four themes, light/dark, Month/Year, and compact/wide.
- 8 interaction-state captures: four themes in light/dark with primary and secondary controls, completion and Reviews Due levels, every Today/Selected completion level, event/outside combinations, target-aware rates, and empty/partial/full progress.
- 2 exact-package full-screen dashboard captures: Month and Year.
- Native runtime report: passed with no recorded errors.
- [Hardcoded-color audit](reports/hardcoded-color-audit.md): passed with zero component-level hardcoding.
- [Contrast test report](reports/contrast-test-report.md): 582 gated pairs passed.
- [Changed-file summary](reports/changed-file-summary.md): 9 release-candidate files.
- Exact package: 24 files, installed payload byte-matched to the archive.
- Disposable profile: `Codex QA HDO 1.8.7 Dashboard Fresh c4b794f0 20260827-194200`.
- Sync credentials: absent.

## Acceptance boundary

Spoken VoiceOver, Windows/Linux rendering, device-specific behavior, and non-100% OS display scaling remain separate acceptance gates.
