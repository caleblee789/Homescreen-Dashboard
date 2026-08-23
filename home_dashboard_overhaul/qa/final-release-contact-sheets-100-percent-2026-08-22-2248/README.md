# Home Dashboard 1.7.0 contact sheets — 100% only

Candidate SHA-256: `3cdfc800de85eaa9fc59f1b06ab9169c517256299c9f174b5709c6bfbaa17ee6`

All UI renders in this set use 100% application/text scale. The native macOS captures retain Retina DPR 2 physical pixels; that is pixel density, not enlarged UI scale. No 125%, 150%, or 200% UI captures are included.

## Contact sheets

- [Home Dashboard 1.7.0 · Sapphire Glass](contact-sheets/01-dashboard-sapphire-glass-100-percent.png)
- [Home Dashboard 1.7.0 · Graphite](contact-sheets/02-dashboard-graphite-100-percent.png)
- [Home Dashboard 1.7.0 · Emerald](contact-sheets/03-dashboard-emerald-100-percent.png)
- [Home Dashboard 1.7.0 · High Contrast](contact-sheets/04-dashboard-high-contrast-100-percent.png)
- [Exact-package Home Dashboard · full screen](contact-sheets/05-exact-package-full-screen-dashboard-100-percent.png)
- [Exact-package Settings · responsive layouts](contact-sheets/06-exact-package-settings-responsive-100-percent.png)

## Evidence

- Renderer matrix: 32 captures across four themes, light/dark, Month/Year, and compact/wide layouts.
- Exact-package full-screen dashboard: Month and Year.
- Exact-package Settings: wide, intermediate, and narrow layouts.
- Every detail-sheet placement uses the source screenshot at scale `1.0`.
- Runtime report status: passed with no recorded errors in a disposable sync-disabled profile.

## Acceptance boundary

Spoken VoiceOver, Windows/Linux rendering, and true OS display scaling remain separate acceptance gates.

The separate
[`native 100% contact-sheet set`](../final-release-contact-sheets-100-percent-2026-08-22-2317/README.md)
retains all 34 raw Qt/AnkiWebView captures and five sheets from the current
exact package.
