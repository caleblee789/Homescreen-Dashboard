"""Central semantic color system for every dashboard theme and color mode."""

from __future__ import annotations

from typing import Dict, Mapping


Theme = Dict[str, str]
DEFAULT_CUSTOM_BIBLE_COLOR = "#1E90FF"


def _channels(value: str) -> list[int]:
    raw = value.lstrip("#")
    if len(raw) != 6:
        raise ValueError("theme colors must use six-digit hexadecimal notation")
    return [int(raw[index:index + 2], 16) for index in (0, 2, 4)]


def composite_color(foreground: str, background: str, opacity: float) -> str:
    """Return the opaque sRGB result of drawing foreground over background."""

    values = [
        round(opacity * front + (1 - opacity) * back)
        for front, back in zip(_channels(foreground), _channels(background))
    ]
    return "#{:02X}{:02X}{:02X}".format(*values)


def rgba_color(value: str, opacity: float) -> str:
    """Return a centralized CSS color for a translucent component surface."""

    channel_values = _channels(value)
    return "rgba({}, {}, {}, {:.2f})".format(
        *channel_values,
        max(0.0, min(1.0, opacity)),
    )


def _luminance(value: str) -> float:
    channels = [item / 255 for item in _channels(value)]
    linear = [
        item / 12.92 if item <= .04045 else ((item + .055) / 1.055) ** 2.4
        for item in channels
    ]
    return .2126 * linear[0] + .7152 * linear[1] + .0722 * linear[2]


def contrast_ratio(left: str, right: str) -> float:
    """Return the WCAG contrast ratio for two opaque hexadecimal colors."""

    high, low = sorted((_luminance(left), _luminance(right)), reverse=True)
    return (high + .05) / (low + .05)


# Stable study semantics never inherit the selected theme accent.
SEMANTIC_PALETTES: Mapping[str, Mapping[str, str]] = {
    "light": {
        "status_new_fill": "#2F7DD3",
        "status_new_text": "#2468B6",
        "status_learning_fill": "#C76A00",
        "status_learning_text": "#A85A00",
        "status_review_fill": "#7C3AED",
        "status_review_text": "#7C3AED",
        "status_buried_fill": "#64748B",
        "status_buried_text": "#64748B",
        "status_success_fill": "#147A42",
        "status_success_text": "#147A42",
        "status_warning_fill": "#D0A146",
        "status_warning_text": "#845A08",
        "status_danger_fill": "#D95C74",
        "status_danger_text": "#A92948",
        "status_event_fill": "#986800",
        "status_event_text": "#986800",
    },
    "dark": {
        "status_new_fill": "#60A5FA",
        "status_new_text": "#60A5FA",
        "status_learning_fill": "#F59E0B",
        "status_learning_text": "#F59E0B",
        "status_review_fill": "#C084FC",
        "status_review_text": "#C084FC",
        "status_buried_fill": "#94A3B8",
        "status_buried_text": "#94A3B8",
        "status_success_fill": "#4ADE80",
        "status_success_text": "#4ADE80",
        "status_warning_fill": "#E4C05B",
        "status_warning_text": "#E4C05B",
        "status_danger_fill": "#ED879A",
        "status_danger_text": "#ED879A",
        "status_event_fill": "#FACC15",
        "status_event_text": "#FACC15",
    },
}


# Reviews Due is a stable semantic visualization. The neutral background
# carries presence while the compact bottom marker carries three intensities.
PROJECTED_DUE_SCALES: Mapping[str, tuple[str, ...]] = {
    "light": ("", "#F4F2F5", "#F1EEF3", "#EDE9F0"),
    "dark": ("", "#242329", "#27242D", "#2B2632"),
}


REVIEWS_DUE_INDICATORS: Mapping[str, tuple[str, ...]] = {
    "light": ("", "#9C89AE", "#846B9A", "#65487C"),
    "dark": ("", "#89719D", "#A187B2", "#BDA4CC"),
}


COMPLETION_SCALES: Mapping[str, Mapping[str, tuple[str, ...]]] = {
    "Sapphire Glass": {
        "light": ("#F8FAFD", "#E7F0FA", "#D7E7F6", "#AFCDEA", "#78A8D2", "#356F9F"),
        "dark": ("#172434", "#1F3449", "#2B4B66", "#3B6C90", "#5A96BE", "#87BCD9"),
    },
    "Graphite": {
        "light": ("#F7F8FA", "#E9EDF1", "#DCE1E5", "#BAC2C9", "#8D99A3", "#5F6C76"),
        "dark": ("#20252B", "#2B3239", "#3C4650", "#58636D", "#7E8994", "#ADB6BF"),
    },
    "Emerald": {
        "light": ("#F8FAF9", "#E5F3EB", "#D1EBDD", "#A7D7BE", "#69B38E", "#287A55"),
        "dark": ("#17231D", "#1D3427", "#28503A", "#397052", "#58A074", "#85C89C"),
    },
    "High Contrast": {
        "light": ("#F4F7F8", "#D9ECEF", "#ABDCE0", "#71C2C9", "#1D7F89", "#075E68"),
        "dark": ("#11161A", "#10343A", "#0D5660", "#0A737F", "#2BA7B3", "#6ACFD8"),
    },
}


# The supplied light tertiary hues need a very small luminance correction to
# keep 9-12px tertiary copy at 4.5:1 on surface 3. Sapphire and Emerald focus
# also need a small darkening so the selected-date ring clears 3:1 against its
# one-pixel light surface halo. All other core values match the final contract.
CORE_PALETTES: Mapping[str, Mapping[str, Mapping[str, str]]] = {
    "Sapphire Glass": {
        "light": {
            "ui_canvas": "#F4F7FB",
            "ui_surface_1": "#FFFFFF",
            "ui_surface_2": "#F8FAFD",
            "ui_surface_3": "#EDF3F9",
            "ui_border_subtle": "#E4EBF3",
            "ui_border_default": "#D6E1ED",
            "ui_border_strong": "#7D91A8",
            "ui_text_primary": "#162235",
            "ui_text_secondary": "#5E6E80",
            "ui_text_tertiary": "#5E6E80",
            "ui_text_disabled": "#8B99A8",
            "ui_eyebrow": "#4D7098",
            "ui_accent": "#2A63C7",
            "ui_accent_hover": "#2457B2",
            "ui_accent_pressed": "#1F4996",
            "ui_accent_soft": "#E7F0FC",
            "ui_accent_border": "#7FA6DC",
            "ui_on_accent": "#FFFFFF",
            "ui_focus": "#6097DD",
            "progress_complete": "#2A63C7",
            "ui_card_gradient_start": "#FFFFFF",
            "ui_card_gradient_end": "#FAFCFF",
        },
        "dark": {
            "ui_canvas": "#0A131E",
            "ui_surface_1": "#101D2B",
            "ui_surface_2": "#142438",
            "ui_surface_3": "#1B2A3D",
            "ui_border_subtle": "#1E3348",
            "ui_border_default": "#28405A",
            "ui_border_strong": "#617B96",
            "ui_text_primary": "#F3F7FB",
            "ui_text_secondary": "#A2B2C3",
            "ui_text_tertiary": "#A2B2C3",
            "ui_text_disabled": "#637487",
            "ui_eyebrow": "#9ABBDD",
            "ui_accent": "#58A6FF",
            "ui_accent_hover": "#7BB6F8",
            "ui_accent_pressed": "#478CD8",
            "ui_accent_soft": "#173555",
            "ui_accent_border": "#477CAD",
            "ui_on_accent": "#08111D",
            "ui_focus": "#98C8FF",
            "progress_complete": "#5796DF",
            "ui_card_gradient_start": "#152234",
            "ui_card_gradient_end": "#111A27",
        },
    },
    "Graphite": {
        "light": {
            "ui_canvas": "#EFF1F3",
            "ui_surface_1": "#FFFFFF",
            "ui_surface_2": "#F7F8FA",
            "ui_surface_3": "#ECEFF2",
            "ui_border_subtle": "#DDE2E7",
            "ui_border_default": "#C6CDD4",
            "ui_border_strong": "#7D8791",
            "ui_text_primary": "#191C20",
            "ui_text_secondary": "#515A64",
            "ui_text_tertiary": "#646E77",
            "ui_text_disabled": "#979FA8",
            "ui_eyebrow": "#5D6670",
            "ui_accent": "#566B80",
            "ui_accent_hover": "#465B70",
            "ui_accent_pressed": "#3B4D60",
            "ui_accent_soft": "#E7EBEF",
            "ui_accent_border": "#8799AB",
            "ui_on_accent": "#FFFFFF",
            "ui_focus": "#566B80",
            "progress_complete": "#566B80",
        },
        "dark": {
            "ui_canvas": "#101214",
            "ui_surface_1": "#171A1D",
            "ui_surface_2": "#1D2125",
            "ui_surface_3": "#232A31",
            "ui_border_subtle": "#2B333B",
            "ui_border_default": "#343A40",
            "ui_border_strong": "#65717D",
            "ui_text_primary": "#F4F6F8",
            "ui_text_secondary": "#C2C9D0",
            "ui_text_tertiary": "#939CA6",
            "ui_text_disabled": "#69737D",
            "ui_eyebrow": "#AAB2BB",
            "ui_accent": "#8CA0B3",
            "ui_accent_hover": "#B4C5D6",
            "ui_accent_pressed": "#849BAF",
            "ui_accent_soft": "#29343F",
            "ui_accent_border": "#60788E",
            "ui_on_accent": "#151A1F",
            "ui_focus": "#7CB2F0",
            "progress_complete": "#9BA6B1",
        },
    },
    "Emerald": {
        "light": {
            "ui_canvas": "#EFF4F1",
            "ui_surface_1": "#FFFFFF",
            "ui_surface_2": "#F8FAF9",
            "ui_surface_3": "#EEF3F0",
            "ui_border_subtle": "#D9E2DC",
            "ui_border_default": "#C2CEC6",
            "ui_border_strong": "#789083",
            "ui_text_primary": "#17231C",
            "ui_text_secondary": "#4D6154",
            "ui_text_tertiary": "#617367",
            "ui_text_disabled": "#8F9F95",
            "ui_eyebrow": "#47765C",
            "ui_accent": "#137C55",
            "ui_accent_hover": "#106B49",
            "ui_accent_pressed": "#0C5A3E",
            "ui_accent_soft": "#E5F2EB",
            "ui_accent_border": "#77A98F",
            "ui_on_accent": "#FFFFFF",
            "ui_focus": "#44A67B",
            "progress_complete": "#137C55",
        },
        "dark": {
            "ui_canvas": "#0B1210",
            "ui_surface_1": "#101B17",
            "ui_surface_2": "#14231C",
            "ui_surface_3": "#17251F",
            "ui_border_subtle": "#294137",
            "ui_border_default": "#345444",
            "ui_border_strong": "#687E70",
            "ui_text_primary": "#F2F7F4",
            "ui_text_secondary": "#BBCAC1",
            "ui_text_tertiary": "#8E9F95",
            "ui_text_disabled": "#65766C",
            "ui_eyebrow": "#74B38D",
            "ui_accent": "#3CCF8E",
            "ui_accent_hover": "#58CF94",
            "ui_accent_pressed": "#2FA76B",
            "ui_accent_soft": "#173328",
            "ui_accent_border": "#3A7253",
            "ui_on_accent": "#07150D",
            "ui_focus": "#78E0AA",
            "progress_complete": "#37B577",
        },
    },
    "High Contrast": {
        "light": {
            "ui_canvas": "#FFFFFF",
            "ui_surface_1": "#FFFFFF",
            "ui_surface_2": "#FFFFFF",
            "ui_surface_3": "#EDEFF1",
            "ui_border_subtle": "#8C969F",
            "ui_border_default": "#515B65",
            "ui_border_strong": "#20262D",
            "ui_text_primary": "#000000",
            "ui_text_secondary": "#262D34",
            "ui_text_tertiary": "#4D5660",
            "ui_text_disabled": "#6F7882",
            "ui_eyebrow": "#005FCC",
            "ui_accent": "#005FCC",
            "ui_accent_hover": "#004EA8",
            "ui_accent_pressed": "#003E86",
            "ui_accent_soft": "#DDEBFF",
            "ui_accent_border": "#286FC2",
            "ui_on_accent": "#FFFFFF",
            "ui_focus": "#007BFF",
            "progress_complete": "#005FCC",
        },
        "dark": {
            "ui_canvas": "#000000",
            "ui_surface_1": "#080A0D",
            "ui_surface_2": "#0E1115",
            "ui_surface_3": "#161A20",
            "ui_border_subtle": "#626C76",
            "ui_border_default": "#7B8590",
            "ui_border_strong": "#C7CDD4",
            "ui_text_primary": "#FFFFFF",
            "ui_text_secondary": "#D8DDE3",
            "ui_text_tertiary": "#AAB2BB",
            "ui_text_disabled": "#747D87",
            "ui_eyebrow": "#7CB9FF",
            "ui_accent": "#5EA9FF",
            "ui_accent_hover": "#7DBAFF",
            "ui_accent_pressed": "#3B8DE8",
            "ui_accent_soft": "#102A46",
            "ui_accent_border": "#4D82B8",
            "ui_on_accent": "#06111E",
            "ui_focus": "#9DCEFF",
            "progress_complete": "#5EA9FF",
        },
    },
}


HEATMAP_PRESET_NAMES: Mapping[str, tuple[str, ...]] = {
    "Sapphire Glass": ("Sapphire", "Amethyst", "Glacier", "Sea Glass"),
    "Graphite": ("Slate", "Steel", "Plum", "Mint"),
    "Emerald": ("Emerald", "Jade", "Moss", "Lagoon"),
    "High Contrast": ("Cyan", "Gold", "Magenta", "Monochrome"),
}


def _heat_tokens(theme_name: str, variant: str, core: Mapping[str, str]) -> Theme:
    completion = COMPLETION_SCALES[theme_name][variant]
    complete_text = (
        (core["ui_text_primary"],) * 4 + ("#FFFFFF",) * 2
        if variant == "light" and theme_name == "High Contrast"
        else (core["ui_text_primary"],) * 5 + ("#FFFFFF",)
        if variant == "light"
        else (core["ui_text_primary"],) * 4 + ("#0B1116",) * 2
    )
    return {
        **{"heat_complete_{}".format(level): color for level, color in enumerate(completion)},
        **{"heat_complete_text_{}".format(level): color for level, color in enumerate(complete_text)},
        **{
            "heat_due_bg_{}".format(level): PROJECTED_DUE_SCALES[variant][level]
            for level in range(1, 4)
        },
        **{
            "heat_due_mark_{}".format(level): REVIEWS_DUE_INDICATORS[variant][level]
            for level in range(1, 4)
        },
    }


def _build_theme(theme_name: str, variant: str) -> Theme:
    core = dict(CORE_PALETTES[theme_name][variant])
    skeleton_opacity = .10 if variant == "light" else .16
    core["ui_skeleton_base"] = composite_color(
        core["ui_accent"], core["ui_surface_2"], skeleton_opacity
    )
    core["ui_skeleton_highlight"] = composite_color(
        core["ui_accent"], core["ui_surface_2"], skeleton_opacity * 1.8
    )
    core["ui_shadow_card"] = (
        "none" if theme_name == "High Contrast"
        else "0 1px 2px rgba(16, 24, 40, 0.05), 0 8px 20px rgba(16, 24, 40, 0.05)"
        if variant == "light"
        else "0 1px 1px rgba(0, 0, 0, 0.50), 0 8px 18px rgba(0, 0, 0, 0.22)"
    )
    core["ui_shadow_overlay"] = (
        "none" if theme_name == "High Contrast"
        else "0 4px 12px rgba(16, 24, 40, 0.10), 0 16px 32px rgba(16, 24, 40, 0.12)"
        if variant == "light"
        else "0 2px 8px rgba(0, 0, 0, 0.48), 0 18px 38px rgba(0, 0, 0, 0.30)"
    )
    core.update(SEMANTIC_PALETTES[variant])
    core.update(_heat_tokens(theme_name, variant, core))
    core.update({
        "ui_disabled_surface": core["ui_surface_3"],
        "ui_disabled_border": core["ui_border_default"],
        "ui_control_hover": core["ui_accent_soft"],
        "ui_control_pressed": core["ui_surface_3"],
        "ui_overlay_surface": core["ui_surface_1"],
        "ui_scrollbar_track": core["ui_surface_2"],
        "ui_scrollbar_thumb": core["ui_border_strong"],
        "ui_scrollbar_thumb_hover": core["ui_accent_border"],
        "status_warning_soft": composite_color(core["status_warning_fill"], core["ui_surface_1"], .13),
        "status_danger_soft": composite_color(core["status_danger_fill"], core["ui_surface_1"], .13),
        "calendar_empty_bg": core["heat_complete_0"],
        "calendar_outside_bg": core["ui_surface_2"],
        "calendar_outside_text": core["ui_text_tertiary"],
        "calendar_future_bg": core["ui_surface_3"],
        "calendar_future_text": core["ui_text_tertiary"],
        "calendar_footer_bg": core["ui_surface_2"],
        "calendar_today_ring": core["ui_accent"],
        "calendar_selected_ring": core["ui_focus"],
        "calendar_ring_halo": core["ui_surface_1"],
        "calendar_event_halo": core["ui_surface_1"],
        "theme_name": theme_name,
        "color_mode": variant,
    })
    return core


# Insertion order is the public Settings order. Theme identifiers are stable.
PRESETS: Mapping[str, Mapping[str, Theme]] = {
    theme_name: {
        variant: _build_theme(theme_name, variant)
        for variant in ("light", "dark")
    }
    for theme_name in ("Sapphire Glass", "Graphite", "Emerald", "High Contrast")
}


# Historical heatmap preference identifiers remain valid. They intentionally
# resolve to the theme's single canonical completion scale so a saved palette
# cannot turn Graphite blue or make Emerald semantics monochromatic.
HEATMAP_PRESETS: Mapping[str, Mapping[str, Mapping[str, Theme]]] = {
    theme_name: {
        preset_name: {
            variant: {
                key: value
                for key, value in PRESETS[theme_name][variant].items()
                if key.startswith("heat_complete_")
            }
            for variant in ("light", "dark")
        }
        for preset_name in HEATMAP_PRESET_NAMES[theme_name]
    }
    for theme_name in PRESETS
}


DEFAULT_HEATMAP_PRESETS: Mapping[str, str] = {
    theme_name: names[0] for theme_name, names in HEATMAP_PRESET_NAMES.items()
}
DEFAULT_HEATMAP_PRESET = DEFAULT_HEATMAP_PRESETS["Sapphire Glass"]


def resolve_theme(
    preset: object,
    mode: object,
    anki_dark: bool,
    heatmap_preset: object = DEFAULT_HEATMAP_PRESET,
) -> Theme:
    """Resolve one complete token set while retaining saved preference IDs."""

    name = preset if isinstance(preset, str) and preset in PRESETS else "Sapphire Glass"
    selected_mode = mode if mode in {"auto", "light", "dark"} else "auto"
    variant = "dark" if (
        selected_mode == "dark" or (selected_mode == "auto" and anki_dark)
    ) else "light"
    available = HEATMAP_PRESETS[name]
    calendar_name = (
        heatmap_preset
        if isinstance(heatmap_preset, str) and heatmap_preset in available
        else DEFAULT_HEATMAP_PRESETS[name]
    )
    resolved = dict(PRESETS[name][variant])
    resolved.update(available[calendar_name][variant])
    resolved["heatmap_preset"] = calendar_name
    return resolved
