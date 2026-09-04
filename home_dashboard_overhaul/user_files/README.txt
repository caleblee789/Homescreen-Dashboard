This directory contains profile-local runtime state created by Home Screen
Dashboard. Anki preserves user_files across add-on updates.

rotation_state.json stores only the current Bible verse, its mode-specific
refresh key, and the verse-library fingerprint used to validate that selection.
The add-on's settings, events, and verse library are stored in Anki's local
add-on configuration.

Configuration schema 8 offers exactly Sapphire Glass, Graphite, Emerald, and
High Contrast. Retired, legacy, malformed, or unknown theme values normalize
to Sapphire Glass, and the retired Layout Density key is removed. The 16
completion-palette IDs are stored per theme. Card opacity uses the supported
94-100 range with a 96 default, and Sapphire Glass blur uses 0-16 px with a 12
px default. No theme, palette, opacity, or blur migration file is written in
this directory.
