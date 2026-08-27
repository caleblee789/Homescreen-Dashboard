"""Shared semantic UI contracts for the dashboard and native Settings.

The two surfaces use different rendering toolkits, but their public component
names, content modes, interaction geometry, and semantic color roles must stay
aligned.  Keep fixture dimensions and capture-specific values out of this file.
"""

from __future__ import annotations

from typing import Tuple


CONTENT_MODE_EXTRA_WIDE = "extra-wide"
CONTENT_MODE_INTERMEDIATE = "intermediate"
CONTENT_MODE_NARROW = "narrow"
CONTENT_MODES: Tuple[str, ...] = (
    CONTENT_MODE_EXTRA_WIDE,
    CONTENT_MODE_INTERMEDIATE,
    CONTENT_MODE_NARROW,
)

DASHBOARD_PRIMITIVES: Tuple[str, ...] = (
    "dashboard-header",
    "dashboard-panel",
    "calendar-context-bar",
    "statistics-card",
    "summary-metrics-grid",
    "bible-verse-card",
    "metric-row",
    "alert-banner",
    "recovery-card",
    "loading-card",
    "tooltip",
    "event-marker",
    "due-hatch",
)

SETTINGS_PRIMITIVES: Tuple[str, ...] = (
    "settings-sidebar",
    "settings-footer",
    "form-control",
    "list-or-table-row",
    "contextual-action-group",
    "editor-dialog",
)

PRIMITIVE_NAMES: Tuple[str, ...] = DASHBOARD_PRIMITIVES + SETTINGS_PRIMITIVES

INTERACTION_TARGET_MIN_PX = 36
VISUAL_CHROME_PX = 36
FOCUS_RING_PX = 3
FOCUS_RING_OFFSET_PX = 2
COMPLETION_TOKEN_ROLE = "completion"


def normalize_content_mode(value: object) -> str:
    """Return a supported mode without inventing a fourth fallback state."""

    text = str(value or "").strip().lower()
    return text if text in CONTENT_MODES else CONTENT_MODE_NARROW
