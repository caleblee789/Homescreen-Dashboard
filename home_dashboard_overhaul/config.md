# Home Screen Dashboard settings

Open the editor from **Tools → Home Screen Dashboard settings**. The calendar
gear opens **Calendar & data** directly.

Schema 7 keeps exactly three layout roles in the built-in hierarchy:
`study_calendar`, `summary_metrics`, and `bible_verse`. Legacy selected-date,
due-deck, and dashboard card-preview roles are removed during normalization and
are never recreated. Unknown unrelated keys are retained.

`appearance.preset` accepts `Sapphire Glass`, `Graphite`, `Emerald`, or `High
Contrast`. `appearance.mode` accepts `auto`, `light`, or `dark`.
`appearance.opacity` accepts 70–100. Normal native hosts remain transparent;
text-bearing panel colors are precomposited with a 91% effective minimum, and
High Contrast surfaces remain fully opaque. A top-level scrim is activated
only when the host actually has a background image (or QA deliberately injects
one); there is no custom-background preference in this add-on.
`appearance.text_scale` accepts 90–150.

At the 100% release target, the dashboard uses a 1,480 px maximum width. The
calendar and a 430–450 px two-column insight rail remain side by side from
about 1,220 component pixels; from 900–1,219 px the rail moves below the
calendar, and below about 640 px its metric cards use one column. Dedicated
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
Schema 7 intentionally drops only the known retired `study.show_eta` and
`study.show_estimate` keys (and does not import legacy `ShowTimeLeft`) while
preserving unrelated unknown keys and all other preferences.

The integrated calendar footer has no visibility or placement setting. It
always belongs to the calendar card and combines the Completion, Reviews due,
and Event legend groups with a Today/Selected date chip and the global next
event. Past/current dates with studied cards expose Reviewed cards and
supported future dates expose Due cards; the action is hidden when its
exact card set is empty or unavailable. It uses the solid theme
primary treatment. Most missed remains hidden until an
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
