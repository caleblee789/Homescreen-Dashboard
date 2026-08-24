# Home Screen Dashboard settings

Open the editor from **Tools → Home Screen Dashboard settings**. The calendar
gear opens **Calendar & data** directly.

Schema 8 keeps exactly three layout roles in the built-in hierarchy:
`study_calendar`, `summary_metrics`, and `bible_verse`. Legacy selected-date,
due-deck, and dashboard card-preview roles are removed during normalization and
are never recreated. Unknown unrelated keys are retained.

`appearance.preset` accepts `Sapphire Glass`, `Graphite`, `Emerald`, or `High
Contrast`. `appearance.mode` accepts `auto`, `light`, or `dark`.
`appearance.opacity` accepts 94–100 and defaults to 96.
`appearance.blur` accepts 0–16 px and defaults to 12 px. Both controls apply
only to Sapphire Glass and are disabled for Graphite, Emerald, and High
Contrast. Sapphire uses component-level translucency and backdrop blur;
Graphite, Emerald, and High Contrast are opaque, and High Contrast has no
decorative shadows. The host wallpaper, Deck Browser canvas, toolbar, deck
list, and native footer remain untouched; there is no host scrim or custom
background preference in this add-on.
`appearance.text_scale` accepts 90–150.

At the 100% release target, the dashboard uses a 1,320 px maximum width, 16 px
minimum side margins, 22 px top spacing, 12 px component gaps, and 72 px bottom
safe area. Calendar and rail stay side by side from 940 component pixels; from
440–939 px the calendar is followed by a 2x2 metric grid; below 440 px metrics
use one column. Month never scrolls internally. The continuous 53-column Year
view is the only internal horizontal scroller and only below 320 px. Dedicated
125% and 150% visual calibration is deferred, but saved scale values remain
supported.

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
semantic presentation of available retention values. The ETA row is permanent.
Schema 8 drops the known retired `study.show_eta`, `study.show_estimate`, and
`visibility.buried` keys (and does not import legacy `ShowTimeLeft`) while
preserving unrelated unknown keys and all other preferences. A valid stored
`heatmap.calendar_view` remains `month` or `year` through migration, first
render, refresh, retry, settings saves, and restart.

The integrated calendar footer has no visibility or placement setting. It
always belongs to the calendar card and combines the Completion, Reviews due,
and Event legend groups with a Today/Selected date chip and the global next
event. Past/current dates with studied cards expose Reviewed cards and
supported future dates expose Due cards; the action is hidden when its
exact card set is empty or unavailable. It uses the solid theme
tonal treatment. Most missed remains hidden until an
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
