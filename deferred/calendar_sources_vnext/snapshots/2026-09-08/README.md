# Calendar source snapshot — September 8, 2026

These four modules and two tests were relocated byte-for-byte from the active
add-on during pre-merge cleanup. They differ from the original deferred archive,
which remains intact. They are source-only and are not shipped in the add-on.

The 833 tracked vendor files and dependency lock removed from the active add-on
were byte-identical to those already in `deferred/calendar_sources_vnext/`.
The test runner reuses those dependencies without copying them. It supplies a
temporary package alias in its own process so the preserved tests retain their
original imports and mock targets without importing the active Anki add-on.

From the repository root, using Python 3.10 or newer:

```sh
python3 deferred/calendar_sources_vnext/snapshots/2026-09-08/run_tests.py
```

Run this separately from active add-on test discovery. Restoring this feature
still requires deliberate integration and the acceptance work described in the
original deferred archive's README.
