# Event Manager and external calendar sources — 1.6.0

## What is supported

Home Dashboard keeps schema 3 and the existing `events.items` local-event format.
Event Manager adds two installation-local, read-only external source types:

- an imported `.ics` file copied as a managed snapshot; and
- an HTTPS or `webcal://` subscription, including Google Calendar's Secret
  address in iCal format.

There is no OAuth, Google Calendar API, write-back, CalDAV, authenticated header,
event-time, location, description, attendee, or per-source color support.

## Private Google iCal setup

1. In Google Calendar on the web, open **Settings and sharing** for the calendar.
2. Under **Integrate calendar**, copy **Secret address in iCal format**.
3. In Anki, open **Tools → Caleb M. Add-ons Settings → Manage events & calendars**.
4. On **Calendars**, choose **Subscribe to link**, paste the link, and save.
5. Event Manager downloads and validates the feed off the UI thread. After the
   initial success, only the calendar host is displayed.

Anyone with a Secret iCal link can read that calendar. Never include the link in
logs, screenshots, exports, support messages, or source control. If it is exposed,
reset the secret in Google Calendar and use **Replace link** with the new value.
Use only a disposable calendar for live QA.

## Storage and refresh

`user_files/calendar_sources.json` is a version-1 registry. A source record stores
its ID, kind, display name, enabled state, subscription URL when applicable,
content hash, ETag/Last-Modified values, timestamps, counts, and a redacted error.
Hidden occurrence identities are stored separately in the same registry.

Each source has a hashed subdirectory under `user_files/calendar_sources/`.
Content generations are addressed by SHA-256 and contain `calendar.ics` plus
bounded `occurrences-<start>-<end>.json` caches. A new generation is complete before the registry points at
it, so a failed refresh retains the prior good data. Files are mode 0600 and
directories mode 0700 where the platform supports POSIX permissions.

Subscriptions refresh at profile startup, every six hours while Anki remains
open, and on demand. Conditional ETag and Last-Modified requests are used. A
redirect must remain HTTPS. Imported snapshots refresh only through **Replace
file**.

## Recovery and privacy

- Close Anki before backing up or restoring calendar state.
- Restore `calendar_sources.json` and `calendar_sources/` from the same backup.
- Restoring add-on configuration alone restores local events, not external
  calendars.
- Deleting the registry and cache disconnects external calendars only; local
  `events.items` remains untouched.
- Removing one source deletes only its source cache and hidden-state records.
- Calendar data is unencrypted, installation-local, and never synced by Anki.

## Limits and errors

Feeds are limited to 10 MiB and 50,000 VEVENT components. A single query spans at
most ten years and is preflight-bounded to 20,000 expanded occurrences. Network
requests time out, unsafe redirect downgrades fail, and a source/range error is
shown instead of silently truncating results. Imported display titles are plain
text, control-cleaned, and capped at 500 characters; local editors remain capped
at 160.

The dashboard requests only its visible Month/Year range. Responses include a
render generation and request ID; stale responses are ignored. Calendar-only
changes refresh rendering without invalidating collection analytics.
