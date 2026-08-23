# Home Screen Dashboard 1.8.0 offline release evidence

This directory contains the canonical repository evidence for release 1.8.0.
The release workflow intentionally did not launch Anki.

## Package

- [`home-dashboard-overhaul-1.8.0.ankiaddon`](package/home-dashboard-overhaul-1.8.0.ankiaddon)
- [`SHA-256 sidecar`](package/home-dashboard-overhaul-1.8.0.ankiaddon.sha256)
- SHA-256: `84ce1ad81f888d18f856bef14b06759bae9631e5dc16da47338817ee391733e8`
- Contents: 24 allowlisted files
- Determinism: two consecutive builds were byte-identical
- Integrity: safe paths, fixed timestamps, manifest/version consistency, and
  source/archive byte parity passed

## Offline validation

- Python 3.12.14: 186 tests passed with zero skips.
- JavaScript calendar model: passed.
- Source compilation: passed.
- UI contract: 25 surfaces, 42 criteria, and 96 visual cases passed.
- [Contrast report](reports/contrast-test-report.md): 662 gated pairs passed.
- [Hardcoded-color report](reports/hardcoded-color-audit.md): zero unclassified
  component-level colors.
- Contact-sheet index: eight source images and five generated sheet artifacts
  passed exact-once metadata validation.

Machine-readable results are summarized in
[`offline-validation.json`](offline-validation.json).

## Visual-reference provenance

The eight retained 100%-scale Month views cover all four themes in light and
dark mode. They were captured by the completed color-work task before the
release-only 1.8.0 metadata and documentation update. A byte comparison between
that source archive and the final package found differences only in
`manifest.json`, `README.md`, and `CHANGELOG.md`; every executable and visual
package member is identical. The source IDs, dimensions, and hashes are recorded
in [`capture-manifest.json`](capture-manifest.json).

- [Overview contact sheet](contact-sheets/contact-sheet-overview.png)
- [Theme contact sheet](contact-sheets/contact-sheet-category-themes-01.png)
- [Full-resolution captures](captures/)

The contact sheets were composed offline and do not convert these references
into exact-package live evidence for 1.8.0.

## Acceptance boundary

Live startup, native WebView behavior, restart persistence, spoken VoiceOver,
Windows/Linux rendering, operating-system forced colors, device-specific
behavior, and non-100% operating-system display scaling were not tested for
1.8.0 and are not claimed.
