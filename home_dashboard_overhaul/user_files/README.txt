This directory contains profile-local runtime state created by Home Screen
Dashboard. Anki preserves user_files across add-on updates.

rotation_state.json stores only the selected Bible verse and its rotation key.
The add-on's settings and events are stored in Anki's local add-on configuration.

Configuration schema 8 offers exactly Sapphire Glass, Graphite, Emerald, and
High Contrast. Retired, legacy, malformed, or unknown theme values normalize
to Sapphire Glass, and the retired Layout Density key is removed. The 16
completion-palette IDs are stored per theme. Card opacity uses the supported
94-100 range with a 96 default, and Sapphire Glass blur uses 0-16 px with a 12
px default. No theme, palette, opacity, or blur migration file is written in
this directory.
