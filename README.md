# Home Screen Dashboard

A study calendar, progress tracker, and statistics dashboard for Anki's home
screen.

**Version 1.8.7** · **Anki Desktop 26.8**

## Features

- Browse your completed reviews and upcoming due cards in Month or Year view.
- Track today's progress, study time, retention, and streaks.
- Add local events and see what's coming up on your calendar.
- Customize themes, calendar colors, text size, and visible sections.
- Display an optional Bible verse with your own library and appearance settings.

## Screenshots

Click an image to view it at full size.

**Sapphire Glass · Month view**

[![Sapphire Glass dashboard with a blue Month calendar, progress bar, four statistics cards, and optional verse](docs/images/1.8.7/dashboard-sapphire-dark.png)](docs/images/1.8.7/dashboard-sapphire-dark.png)

| Emerald · dark Month view | Graphite · Year overview |
| --- | --- |
| [![Emerald dashboard with a green Month calendar on Anki's dark background](docs/images/1.8.7/dashboard-emerald-dark.png)](docs/images/1.8.7/dashboard-emerald-dark.png) | [![Graphite Year view showing a full-year heatmap and study summaries](docs/images/1.8.7/dashboard-year.png)](docs/images/1.8.7/dashboard-year.png) |

**Settings**

| Appearance · dark Settings | Bible library · light Settings |
| --- | --- |
| [![Appearance Settings with six-page navigation, theme and palette selectors, color mode, and scale](docs/images/1.8.7/settings-appearance-dark.png)](docs/images/1.8.7/settings-appearance-dark.png) | [![Light Bible library with search, verse rows, separate display tab, and editing actions](home_dashboard_overhaul/qa/release-evidence-1.8.7-2026-09-04-cf112634-ui-final/captures/SET-LIGHT-BIBLE.png)](home_dashboard_overhaul/qa/release-evidence-1.8.7-2026-09-04-cf112634-ui-final/captures/SET-LIGHT-BIBLE.png) |

## Installation

1. Download the [1.8.7 add-on](https://github.com/caleblee789/Homescreen-Dashboard/releases/download/v1.8.7/home-dashboard-overhaul-1.8.7.ankiaddon).
2. In Anki, choose **Tools → Add-ons → Install from file** and select the file.
3. Restart Anki.

If the dashboard reports conflicting add-ons, disable the entries listed in
its message and restart Anki.

See [what changed in 1.8.7](docs/releases/1.8.7.md).

## Using the dashboard

Switch between **Month** and **Year**, then select a day to see its reviews,
due cards, and events.

Hover over a future date to check its due cards. To also mark them on the
calendar, turn on **Show future due indicators** in Calendar settings.

Open the calendar's gear icon or
**Caleb M. Add-ons Settings → Home Screen Dashboard settings** to customize it.
Choose a page, make your changes, and click **Save changes**.

| Settings page | What you'll find |
| --- | --- |
| Dashboard | Visible sections, panel placement, study preferences, and deck filters |
| Appearance | Themes, calendar colors, text size, opacity, and blur |
| Calendar | Default view, week start, event markers, and history and due ranges |
| Events | Add, edit, search, archive, and restore events |
| Bible verse | Your verse library, text styling, and rotation options |
| About & support | Version information, diagnostics, help, and verse export |

Settings follows Anki's light or dark appearance. Dashboard colors can be
chosen separately.

## Help and backups

[Report a bug or request a feature](https://github.com/caleblee789/Homescreen-Dashboard/issues).
Include your Anki version and a screenshot when helpful.

Export your custom verse library from **About & support** before updating or
reinstalling. The add-on does not change your cards or review history.

## Development

See the [build and test instructions](home_dashboard_overhaul/README.md#build-and-validation),
[capture workflow](home_dashboard_overhaul/docs/qa/capture-workflow.md), and
[changelog](home_dashboard_overhaul/CHANGELOG.md) for technical details.

## License

[AGPL-3.0-or-later](home_dashboard_overhaul/LICENSE.txt) ·
[Third-party notices](home_dashboard_overhaul/THIRD_PARTY_NOTICES.md)
