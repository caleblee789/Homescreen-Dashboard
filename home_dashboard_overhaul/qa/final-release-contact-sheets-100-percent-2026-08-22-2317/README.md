# Home Dashboard 1.7.0 contact sheets — 100% only

Candidate SHA-256: `3cdfc800de85eaa9fc59f1b06ab9169c517256299c9f174b5709c6bfbaa17ee6`

These sheets were generated from the exact packaged add-on in a fresh, sync-disabled independent Anki profile. Every UI and text render is 100%. No 125%, 150%, or 200% cases are included.

The 34 original native screenshots remain byte-for-byte in `captures/` at Retina DPR 2. The sheets reduce those physical pixels to their corresponding logical size for pagination; this does not change the UI scale.

## Contact sheets

- [Home Dashboard 1.7.0 · Sapphire Glass](contact-sheets/01-dashboard-sapphire-glass-100-percent.png)
- [Home Dashboard 1.7.0 · Graphite](contact-sheets/02-dashboard-graphite-100-percent.png)
- [Home Dashboard 1.7.0 · Emerald](contact-sheets/03-dashboard-emerald-100-percent.png)
- [Home Dashboard 1.7.0 · High Contrast](contact-sheets/04-dashboard-high-contrast-100-percent.png)
- [Exact-package Home Dashboard 1.7.0 · full screen](contact-sheets/05-exact-package-full-screen-dashboard-100-percent.png)

## Evidence

- 32 dashboard captures: four themes, light/dark, Month/Year, and compact/wide.
- 2 exact-package full-screen dashboard captures: Month and Year.
- Native runtime report: passed with no recorded errors.
- Exact package: 24 files, installed payload byte-matched to the archive.
- Disposable profile: `Codex QA HDO Native Contact 20260822 2303`.
- Sync credentials: absent.

All 34 cases passed automated DOM, geometry, scale, save, and capture-hash
checks. Six representatives spanning all four themes, both modes, both layouts,
both views, and both full-screen cases were visually inspected:

- [`VR-SG-L-M-C-100.png`](captures/VR-SG-L-M-C-100.png)
- [`VR-GR-D-Y-W-100.png`](captures/VR-GR-D-Y-W-100.png)
- [`VR-EM-D-M-W-100.png`](captures/VR-EM-D-M-W-100.png)
- [`VR-HC-L-Y-C-100.png`](captures/VR-HC-L-Y-C-100.png)
- [`exact-package-full-screen-month-100.png`](captures/exact-package-full-screen-month-100.png)
- [`exact-package-full-screen-year-100.png`](captures/exact-package-full-screen-year-100.png)

## Acceptance boundary

Manual visual review covers the six representatives above. Spoken VoiceOver,
Windows/Linux rendering, device-specific behavior, and non-100% OS display
scaling remain separate acceptance gates.
