# Home Screen Dashboard settings

Open the editor from **Tools → Home Screen Dashboard settings**. The calendar
gear opens **Calendar & data** directly.

Schema 6 keeps exactly three layout roles in the built-in hierarchy:
`study_calendar`, `summary_metrics`, and `bible_verse`. Legacy selected-date,
due-deck, and dashboard card-preview roles are removed during normalization and
are never recreated. Unknown unrelated keys are retained.

`appearance.preset` accepts `Sapphire Glass`, `Graphite`, `Emerald`, or `High
Contrast`. `appearance.mode` accepts `auto`, `light`, or `dark`.
`appearance.opacity` accepts 70–100, while the renderer applies a stable page
scrim and a 91% effective minimum for text-bearing panels. Decorative
background transparency never makes panel text translucent.
`appearance.text_scale` accepts 90–150.

`heatmap.presets_by_theme` stores an independent completion ramp for every
dashboard theme:

- Sapphire Glass: Sapphire, Amethyst, Glacier, Sea Glass
- Graphite: Slate, Steel, Plum, Mint
- Emerald: Emerald, Jade, Moss, Lagoon
- High Contrast: Cyan, Gold, Magenta, Monochrome

An unknown or legacy value resets only that theme to its first preset. Switching
dashboard themes restores the last valid ramp saved for that theme.

`heatmap.calendar_view` accepts `month` or `year`; `week_start` accepts 0–6.
History, forecast, manual-reschedule, deleted-card, and deck-exclusion options
form one scope shared by calendar counts and their exact Browser targets.
`forecast_days: 0` or `show_due_forecast: false` retains Today’s due value but
omits unsupported future due rows and actions.

`study.retention_target` accepts 50–100 and defaults to 80. It controls only the
semantic presentation of available retention values. `study.show_eta` controls
the Today’s Session ETA row.

The compact context bar has no visibility or placement setting. It always
belongs to the calendar card and distinguishes the selected date, an event on
that date, and the global next event. Past/current dates retain Reviewed and
future dates retain Due; the applicable action is disabled with a reason when
its exact card set is empty or unavailable. Most missed remains hidden until an
eligible Again answer is confirmed.

Collection-backed preview figures use the most recent saved Home snapshot.
Staged display, event, heatmap, and Bible changes update the production-rendered
Live preview immediately but write nothing until Save.

When `bible.theme_aware_color` is enabled, the stored `bible.font_color` is
preserved while its input and swatch are disabled. Rotation accepts the existing
supported values and invalid/missing rotation normalizes to `daily`.

The add-on performs a one-time source migration and remains paused while any
legacy source add-on is enabled. Direct JSON editing remains available for
recovery; values are normalized on load and save.
