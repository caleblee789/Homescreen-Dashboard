This directory contains profile-local runtime state created by Home Screen
Dashboard. Anki preserves user_files across add-on updates.

rotation_state.json stores only the selected Bible verse and its rotation key.
The add-on's settings and events are stored in Anki's local add-on configuration.

Configuration schema 5 offers exactly Sapphire Glass, Graphite, Emerald, and
High Contrast. Retired, legacy, malformed, or unknown palette values reset to
Sapphire Glass, and the retired Layout Density key is removed. Panel Opacity is
stored in the supported 70-100 range with an 88 default; no theme or opacity
migration file is written in this directory.
