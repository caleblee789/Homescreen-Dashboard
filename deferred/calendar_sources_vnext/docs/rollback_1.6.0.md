# Rollback and downgrade — 1.6.0

## Disable or return to the original add-ons

Disable Home Dashboard - Overhaul, re-enable the five preserved source add-ons,
and restart Anki. Home Dashboard never edits, moves, or deletes those originals.

## Downgrade Home Dashboard

Schema remains version 3. Existing local events under `events.items` therefore
remain compatible with 1.5.0, 1.4.0, and 1.3.1. Older releases do not understand
the version-1 external source registry, but leave `user_files/calendar_sources.json`
and `user_files/calendar_sources/` untouched and ignored. Reinstalling 1.6.0
reuses that state.

Before a downgrade, close Anki and back up the whole `user_files` directory. Do
not publish that backup: it can contain full private subscription URLs and feeds.

## Start external calendars over

Use Event Manager to remove sources individually whenever possible. That keeps
the deletion scoped and confirms that local events are untouched. For manual
recovery, close Anki, move both `calendar_sources.json` and `calendar_sources/`
out of `user_files`, and reopen Anki. This resets only external sources. Restore
both paths together if the reset was unintended.

