# Home Dashboard - Overhaul 1.5.3

This Anki 26.8 add-on provides a compact calendar-first Deck Browser dashboard.
Its primary card combines a Month/Year review calendar, due forecast, integrated
event details, an adaptive selected-day insight rail, and all nonduplicate study
metrics. A rotating Bible verse is the only second card.

The Year heatmap opens on first use. Switching Month/Year is remembered without
rerunning collection analytics or advancing Bible rotation. At full-screen Month
widths, the calendar and a persistent date-details rail form one workspace; Year
and smaller windows use the same in-flow details structure beneath the calendar.
No details surface covers dates, statistics, Anki's toolbar, or the Bible card.

Selected-date details begin with a compact contextual summary: past dates show
Completed Reviews and New Cards Studied, today adds current Cards Due, and future
dates emphasize Cards Due. Below it, today and past dates rank up to three cards
by `Again` count across the complete Anki
scheduling day, then by latest miss and card ID. Each row contains a sanitized
question prompt, the full deck path, and `Again ×N`. For future dates it ranks up
to three decks by review cards due. The primary action adapts to the state—card
IDs use a controller-owned `cid:` query when available and otherwise fall back to
the selected date’s validated Anki Browser query—while **Manage this date** and
civil-date events remain unchanged. Days with no study, study without misses,
deleted missed cards, no due work, or unavailable data use explicit nonnumeric
states without removing date-scoped Browse or event management.

Partial collection failures never appear as real zeroes: affected Today,
remaining, buried, history, forecast, and date-summary layers use an em dash or
an explicit unavailable state. If every Home section is hidden, a small recovery
card remains so settings are always keyboard reachable.

Month view reserves separate date-number and event rows, while Year uses stable
intensity thresholds, weekday guides, and separate shape/pattern cues for events
and scheduled due work. Today, selection, and keyboard focus remain independently
visible across all presets.
Hovering or focusing a date shows a compact preview: completed reviews and new
cards studied for current/past dates, or cards due for future dates. The Today
group reports Total Cards Studied, New Cards Studied, Time studied, Pace, and an
optional local finish-clock ETA.

Today’s Progress adds a thin display-only bar directly below its heading. Its
segments are Completed, New, Learning, and Review, in that order. Completion is
the current scheduling-day answer count divided by that count plus the live actionable
New, Learning, and Review queue. Its rows report Percent Complete, each queue,
using the exact labels New remaining, Learning remaining, and Reviews remaining,
followed by Total remaining. ETA in Today uses the day's pace from answer 10
onward, otherwise lifetime pace; remaining new cards use their lifetime
first-answer timing. A day with no answers and no actionable work, or unavailable
Today/queue data, is shown as neutral rather than complete.

The separate Buried Cards group counts collection-wide new,
learning/relearning, and review cards in both buried queues. Those counts never
affect Today’s Progress, Total remaining, or ETA. Anki rollover semantics are
documented on the Calendar settings page instead of occupying the date-details
surface.

Open the editor from **Tools → Caleb M. Add-ons Settings → Home Dashboard -
Overhaul settings**. Its shell and content dialogs follow the staged dashboard
preset and light/dark choice immediately. Wide windows use a grouped navigation
rail, editor, and contextual production-rendered preview; medium and compact
windows collapse the preview behind a labeled toggle, and compact windows use a
top section selector. Save remains disabled until the pure settings draft is
dirty, Cancel/Escape/close protect unsaved work, and concurrent config changes
are merged or surfaced instead of silently overwritten. Local events remain on
the editor's **Events** page with their existing title-plus-civil-date format,
automatic archival, restoration, and Save-bound deletion confirmation.
Deck Browser-only Settings, Browse, Manage, and insight actions are disabled in
the contextual preview, while Month/Year and period controls continue to work
locally. Manual verse rotation includes an explicit staged **Use selected as
current** action; the chosen verse persists across restart after Save.

The add-on migrates the effective settings of the five local
source add-ons once, then remains paused until all five sources are disabled to
prevent duplicate output.

Rollback is immediate: disable this add-on, re-enable the five originals, and
restart Anki. The originals and their data are never modified or removed.

Full-day insights are queried directly from `revlog`, so they naturally span
multiple sessions and app restarts. Every selected date uses a validated,
stale-safe on-demand request; the contextual review/new/due summary renders
immediately from the cached calendar snapshot. No session hook, persistence file,
configuration field, migration, or schema bump is introduced; version 1.5.3
remains on configuration schema 3.

Copyright 2026. Licensed under AGPL-3.0-or-later. See `THIRD_PARTY_NOTICES.md`.
