# External calendar sources — deferred patch

Status: source-only and intentionally excluded from the active 1.5.0 add-on.

This directory preserves the completed external-calendar implementation for a
later patch. It includes the repository and filtering models, Event Manager UI,
integration snapshots, pinned iCalendar dependencies, design documentation, and
historical 1.6.0 QA evidence. The archived 1.6.0 package is retained here only as
an internal implementation record and is not a current distribution artifact.

The active add-on continues to use schema 3 and the embedded local Events settings
page. Its controller, renderer, settings, JavaScript, and CSS do not import or
expose this implementation. The 1.5.0 package allowlist rejects these modules,
the vendor lock, and every `_vendor/` path.

Before activation in a later patch, restore the integration snapshots deliberately,
reconcile them with intervening active changes, rerun the source tests, rebuild
with a new version, and repeat exact-package isolated Anki acceptance.

No personal Google Calendar data or subscription URL is stored in this directory.
