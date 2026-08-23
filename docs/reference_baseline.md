# Historical migration-source checksums

These checksums record the legacy source copies used while implementing and
testing migration compatibility. The physical source directories are no longer
kept in this repository workspace; current migration behavior is defined by the
production code and its isolated test fixtures. None of these sources is
packaged with Home Screen Dashboard.

Payload hashes exclude `meta.json` and generated caches:

| Source | SHA-256 |
| --- | --- |
| `1771074083` | `361e0d023a18d2262c01607c87f3f87bc3bff5a058380304c2fe3a0b9099b745` |
| `635082046` | `9ab75c4b2dcd345f497ffec8db83c4b8b74412ffbe6bd3a0753e4f3a7d178bc0` |
| `1556734708` | `23cd118bc31686dc0ac4004cabeb120738244d34000da56b0cc7b1108b876a77` |
| `1143540799` | `11c8f39db659be9e09781d07322dbc330a6085c7958f7eb9740d8c0a58b2a99f` |
| `BibleVerses` project source copy | `d176c570322610b76ebc6060836f6327520155cb0cc090d7c565440a6ca56409` |
| installed `290511870` payload | `b56e2f00b9398cd2ad14119a7ae3edf134b2306ca65a9b964bc59ca48627a2d3` |

Hashes use each relative path, a NUL separator, and the file bytes in sorted
order. `meta.json`, Python bytecode, cache folders, and Git metadata are excluded.
The recorded project-source digest included its pre-existing distribution
archives and Finder metadata; the installed-payload digest did not.

The unified add-on uses a fresh renderer and analytics boundary. It does not
bundle the legacy Review Heatmap JavaScript, D3, Cal-Heatmap, icons, or vendored
framework code.
