"""Central semantic color system for every dashboard theme and color mode."""

from __future__ import annotations

from typing import Dict, Mapping


Theme = Dict[str, str]
DEFAULT_CUSTOM_BIBLE_COLOR = "#1E90FF"


# Native Settings follows Anki's application appearance only. Dashboard theme
# selection never recolors the editor itself.
SETTINGS_COLOR_TOKENS: Mapping[str, Mapping[str, str]] = {
    "dark": {
        "ui_bg": "#101215",
        "ui_sidebar": "#101215",
        "ui_surface": "#191C21",
        "ui_surface_raised": "#22262D",
        "ui_surface_hover": "#202C37",
        "ui_border": "#353A43",
        "ui_border_strong": "#3A4C5E",
        "ui_text_primary": "#F2F3F5",
        "ui_text_secondary": "#ACB3BF",
        "ui_text_muted": "#ACB3BF",
        "ui_accent": "#8CB6FF",
        "ui_accent_soft": "#1B3354",
        "ui_accent_hover": "#B1C9DD",
        "ui_accent_pressed": "#8AA7BF",
        "ui_accent_ink": "#081727",
        "ui_warning": "#E2BD57",
        "ui_success": "#63D49A",
        "ui_danger": "#F47F8D",
        "ui_overlay": "rgba(0, 0, 0, 153)"
    },
    "light": {
        "ui_bg": "#F4F5F7",
        "ui_sidebar": "#F4F5F7",
        "ui_surface": "#FFFFFF",
        "ui_surface_raised": "#F5F6F8",
        "ui_surface_hover": "#EDF1F4",
        "ui_border": "#DDDFE4",
        "ui_border_strong": "#AAB8C5",
        "ui_text_primary": "#20242B",
        "ui_text_secondary": "#5C6470",
        "ui_text_muted": "#5C6470",
        "ui_accent": "#275ED6",
        "ui_accent_soft": "#EAF1FF",
        "ui_accent_hover": "#506D87",
        "ui_accent_pressed": "#445F78",
        "ui_accent_ink": "#FFFFFF",
        "ui_warning": "#8A6815",
        "ui_success": "#2F7D50",
        "ui_danger": "#B1374A",
        "ui_overlay": "rgba(0, 0, 0, 140)"
    }
}


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


# Stable study semantics use a shared baseline and never inherit the selected
# theme accent. Explicit overrides are limited to audited visual contracts.
SEMANTIC_PALETTES: Mapping[str, Mapping[str, str]] = {
    "light": {
        "status_new_fill": "#225FC6",
        "status_new_text": "#225FC6",
        "status_learning_fill": "#8B610A",
        "status_learning_text": "#8B610A",
        "status_review_fill": "#7347B1",
        "status_review_text": "#7347B1",
        "status_buried_fill": "#64748B",
        "status_buried_text": "#64748B",
        "status_success_fill": "#19714F",
        "status_success_text": "#19714F",
        "status_warning_fill": "#D0A146",
        "status_warning_text": "#845A08",
        "status_danger_fill": "#D95C74",
        "status_danger_text": "#A92948",
        "status_event_fill": "#7D5F19",
        "status_event_text": "#7D5F19"
    },
    "dark": {
        "status_new_fill": "#93BEFF",
        "status_new_text": "#93BEFF",
        "status_learning_fill": "#E9C16B",
        "status_learning_text": "#E9C16B",
        "status_review_fill": "#C5A7F0",
        "status_review_text": "#C5A7F0",
        "status_buried_fill": "#94A3B8",
        "status_buried_text": "#94A3B8",
        "status_success_fill": "#91DCB2",
        "status_success_text": "#91DCB2",
        "status_warning_fill": "#E4C05B",
        "status_warning_text": "#E4C05B",
        "status_danger_fill": "#ED879A",
        "status_danger_text": "#ED879A",
        "status_event_fill": "#F0CB74",
        "status_event_text": "#F0CB74"
    }
}


SEMANTIC_THEME_OVERRIDES: Mapping[str, Mapping[str, Mapping[str, str]]] = {
    "Sapphire Glass": {
        "dark": {
            "status_learning_fill": "#F47F8D",
            "status_learning_text": "#F47F8D",
            "status_review_fill": "#83D9A7",
            "status_review_text": "#83D9A7"
        }
    }
}


# Reviews Due is a stable semantic visualization. The neutral background
# carries presence while the compact bottom marker carries three intensities.
PROJECTED_DUE_SCALES: Mapping[str, tuple[str, ...]] = {
    "light": ("", "#F4F2F5", "#F1EEF3", "#EDE9F0"),
    "dark": ("", "#242329", "#27242D", "#2B2632"),
}


REVIEWS_DUE_INDICATORS: Mapping[str, tuple[str, ...]] = {
    "light": ("", "#82708F", "#A58CB3", "#C6ACD1"),
    "dark": ("", "#82708F", "#A58CB3", "#C6ACD1"),
}


COMPLETION_SCALES: Mapping[str, Mapping[str, tuple[str, ...]]] = {
    "Sapphire Glass": {
        "light": ("#F5F8FC", "#E6EDFB", "#C6D5F3", "#9BB6E6", "#6B8DCA", "#3C65A3",),
        "dark": ("#162438", "#1E3355", "#2B4F7A", "#4773A4", "#729BCD", "#A6C7EF",)
    },
    "Graphite": {
        "dark": ("#22262D", "#2B333D", "#434F5F", "#606F83", "#8291A4", "#AEBAC9",),
        "light": ("#F5F6F8", "#EAEDEF", "#D1D7DE", "#A7B2C0", "#77899E", "#4C6178",)
    },
    "Emerald": {
        "dark": ("#1B2D24", "#1E3B2E", "#2C5840", "#42815C", "#6CAF84", "#9ED4B0",),
        "light": ("#F2F7F4", "#E7F5EC", "#BFE2CE", "#8DC6A6", "#57A879", "#287747",)
    },
    "High Contrast": {
        "dark": ("#101820", "#143846", "#225C70", "#3C889F", "#6EBCD0", "#ADEDFC",),
        "light": ("#FFFFFF", "#E4F7FC", "#B0DFED", "#70BBD0", "#378499", "#175A70",)
    }
}


# Every saved palette identifier owns an authored light and dark ladder.  These
# values are deliberately explicit: composing a translucent hue over white or
# aliasing every identifier to the dashboard theme made the Settings choices
# visually indistinguishable and produced surprising changes over host images.
HEATMAP_COMPLETION_SCALES: Mapping[
    str, Mapping[str, Mapping[str, tuple[str, ...]]]
] = {
    "Sapphire Glass": {
        "Sapphire": {
            "light": ("#F5F8FC", "#E6EDFB", "#C6D5F3", "#9BB6E6", "#6B8DCA", "#3C65A3",),
            "dark": ("#162438", "#1E3355", "#2B4F7A", "#4773A4", "#729BCD", "#A6C7EF",)
        },
        "Amethyst": {
            "dark": ("#162438", "#352944", "#514064", "#72548A", "#9774B0", "#C1A1D4",),
            "light": ("#F5F8FC", "#EFE8F5", "#DAC9E8", "#BDA1D1", "#9772B2", "#73508D",)
        },
        "Glacier": {
            "light": ("#F5F8FC", "#E4EFF3", "#BEDAE3", "#91BFCE", "#5B94AC", "#326B84",),
            "dark": ("#162438", "#203E4B", "#2D5C6D", "#417C90", "#699FB1", "#9EC6D2",)
        },
        "Sea Glass": {
            "dark": ("#162438", "#203D35", "#2D5B4C", "#457D68", "#6CA18B", "#9BCBB5",),
            "light": ("#F5F8FC", "#E4F2ED", "#BCDDD0", "#8FC3B2", "#5C9D88", "#327560",)
        }
    },
    "Graphite": {
        "Slate": {
            "dark": ("#22262D", "#2B333D", "#434F5F", "#606F83", "#8291A4", "#AEBAC9",),
            "light": ("#F5F6F8", "#EAEDEF", "#D1D7DE", "#A7B2C0", "#77899E", "#4C6178",)
        },
        "Steel": {
            "light": ("#F5F6F8", "#E7EEF2", "#C5D5DF", "#9FB8C8", "#6A8FA5", "#426B82",),
            "dark": ("#22262D", "#273641", "#3B5365", "#55788B", "#80A0B0", "#B4CFD9",)
        },
        "Plum": {
            "dark": ("#22262D", "#362B3A", "#57405F", "#795680", "#9F78A8", "#C7A4CF",),
            "light": ("#F5F6F8", "#F1E9F1", "#DFCADD", "#C4A2C1", "#9E799D", "#765371",)
        },
        "Mint": {
            "light": ("#F5F6F8", "#EBF3EF", "#D0E4DA", "#A6CBB9", "#76A68F", "#487A63",),
            "dark": ("#22262D", "#1F3931", "#355949", "#517D65", "#7AA18A", "#AACBB4",)
        }
    },
    "Emerald": {
        "Emerald": {
            "dark": ("#1B2D24", "#1E3B2E", "#2C5840", "#42815C", "#6CAF84", "#9ED4B0",),
            "light": ("#F2F7F4", "#E7F5EC", "#BFE2CE", "#8DC6A6", "#57A879", "#287747",)
        },
        "Jade": {
            "light": ("#F2F7F4", "#E8F3EC", "#C4E2CF", "#98CAB0", "#61A47E", "#337650",),
            "dark": ("#1B2D24", "#223C30", "#365B46", "#518064", "#7BA48A", "#ADD2B9",)
        },
        "Moss": {
            "dark": ("#1B2D24", "#31391F", "#4A582A", "#687B3D", "#91A761", "#BBC993",),
            "light": ("#F2F7F4", "#EFF1DE", "#DDE2BC", "#BCC995", "#93A467", "#657A3F",)
        },
        "Lagoon": {
            "light": ("#F2F7F4", "#E4F2F1", "#BDE0DE", "#8BC4C1", "#57A29E", "#287975",),
            "dark": ("#1B2D24", "#173F3E", "#245D5B", "#3A7F7D", "#62A5A1", "#99CECA",)
        }
    },
    "High Contrast": {
        "Cyan": {
            "dark": ("#101820", "#143846", "#225C70", "#3C889F", "#6EBCD0", "#ADEDFC",),
            "light": ("#FFFFFF", "#E4F7FC", "#B0DFED", "#70BBD0", "#378499", "#175A70",)
        },
        "Gold": {
            "dark": ("#101820", "#3F3210", "#725818", "#A5862F", "#D5B457", "#F5DA95",),
            "light": ("#FFFFFF", "#FFF4D5", "#E7D299", "#C4A45E", "#907134", "#63470D",)
        },
        "Magenta": {
            "dark": ("#101820", "#462644", "#70416D", "#995995", "#C084BA", "#EDBCE4",),
            "light": ("#FFFFFF", "#FBE6F6", "#E7B9DB", "#C688B7", "#965587", "#672D59",)
        },
        "Monochrome": {
            "light": ("#FFFFFF", "#F0F0F0", "#CCCCCC", "#999999", "#606060", "#252525",),
            "dark": ("#101820", "#252525", "#505050", "#888888", "#BEBEBE", "#F0F0F0",)
        }
    }
}


# Shared surfaces from the redesign; saved IDs and semantic roles stay stable.
CORE_PALETTES: Mapping[str, Mapping[str, Mapping[str, str]]] = {
    "Sapphire Glass": {
        "light": {
            "ui_canvas": "#F3F6FB",
            "ui_surface_1": "#FFFFFF",
            "ui_surface_2": "#F5F8FC",
            "ui_surface_3": "#F5F8FC",
            "ui_border_subtle": "#D9E2EE",
            "ui_border_default": "#D9E2EE",
            "ui_border_strong": "#7D91A8",
            "ui_text_primary": "#17263A",
            "ui_text_secondary": "#52647C",
            "ui_text_tertiary": "#52647C",
            "ui_text_disabled": "#8B99A8",
            "ui_eyebrow": "#52647C",
            "ui_accent": "#275ED6",
            "ui_accent_hover": "#2457B2",
            "ui_accent_pressed": "#1F4996",
            "ui_accent_soft": "#EAF1FF",
            "ui_accent_border": "#7FA6DC",
            "ui_on_accent": "#FFFFFF",
            "ui_focus": "#6097DD",
            "progress_complete": "#275ED6"
        },
        "dark": {
            "ui_canvas": "#0B1220",
            "ui_surface_1": "#111D2E",
            "ui_surface_2": "#162438",
            "ui_surface_3": "#162438",
            "ui_border_subtle": "#29384B",
            "ui_border_default": "#29384B",
            "ui_border_strong": "#617B96",
            "ui_text_primary": "#EAF0F8",
            "ui_text_secondary": "#A4B4C8",
            "ui_text_tertiary": "#A4B4C8",
            "ui_text_disabled": "#637487",
            "ui_eyebrow": "#A4B4C8",
            "ui_accent": "#8CB6FF",
            "ui_accent_hover": "#7BB6F8",
            "ui_accent_pressed": "#478CD8",
            "ui_accent_soft": "#1B3354",
            "ui_accent_border": "#477CAD",
            "ui_on_accent": "#081727",
            "ui_focus": "#98C8FF",
            "progress_complete": "#8CB6FF"
        }
    },
    "Graphite": {
        "light": {
            "ui_canvas": "#F4F5F7",
            "ui_surface_1": "#FFFFFF",
            "ui_surface_2": "#F5F6F8",
            "ui_surface_3": "#F5F6F8",
            "ui_border_subtle": "#DDDFE4",
            "ui_border_default": "#DDDFE4",
            "ui_border_strong": "#7D8791",
            "ui_text_primary": "#20242B",
            "ui_text_secondary": "#5C6470",
            "ui_text_tertiary": "#5C6470",
            "ui_text_disabled": "#979FA8",
            "ui_eyebrow": "#5C6470",
            "ui_accent": "#465B78",
            "ui_accent_hover": "#465B70",
            "ui_accent_pressed": "#3B4D60",
            "ui_accent_soft": "#EDF0F5",
            "ui_accent_border": "#8799AB",
            "ui_on_accent": "#FFFFFF",
            "ui_focus": "#566B80",
            "progress_complete": "#465B78"
        },
        "dark": {
            "ui_canvas": "#101215",
            "ui_surface_1": "#191C21",
            "ui_surface_2": "#22262D",
            "ui_surface_3": "#22262D",
            "ui_border_subtle": "#353A43",
            "ui_border_default": "#353A43",
            "ui_border_strong": "#65717D",
            "ui_text_primary": "#F2F3F5",
            "ui_text_secondary": "#ACB3BF",
            "ui_text_tertiary": "#ACB3BF",
            "ui_text_disabled": "#69737D",
            "ui_eyebrow": "#ACB3BF",
            "ui_accent": "#A7BDDC",
            "ui_accent_hover": "#B4C5D6",
            "ui_accent_pressed": "#849BAF",
            "ui_accent_soft": "#28374B",
            "ui_accent_border": "#60788E",
            "ui_on_accent": "#152234",
            "ui_focus": "#7CB2F0",
            "progress_complete": "#A7BDDC"
        }
    },
    "Emerald": {
        "light": {
            "ui_canvas": "#F2F7F4",
            "ui_surface_1": "#FFFFFF",
            "ui_surface_2": "#F2F7F4",
            "ui_surface_3": "#F2F7F4",
            "ui_border_subtle": "#D7E4DC",
            "ui_border_default": "#D7E4DC",
            "ui_border_strong": "#789083",
            "ui_text_primary": "#18352A",
            "ui_text_secondary": "#527063",
            "ui_text_tertiary": "#527063",
            "ui_text_disabled": "#8F9F95",
            "ui_eyebrow": "#527063",
            "ui_accent": "#087451",
            "ui_accent_hover": "#106B49",
            "ui_accent_pressed": "#0C5A3E",
            "ui_accent_soft": "#E2F2E9",
            "ui_accent_border": "#77A98F",
            "ui_on_accent": "#FFFFFF",
            "ui_focus": "#44A67B",
            "progress_complete": "#087451"
        },
        "dark": {
            "ui_canvas": "#0C1512",
            "ui_surface_1": "#13211B",
            "ui_surface_2": "#1B2D24",
            "ui_surface_3": "#1B2D24",
            "ui_border_subtle": "#2C4437",
            "ui_border_default": "#2C4437",
            "ui_border_strong": "#687E70",
            "ui_text_primary": "#EDF6F0",
            "ui_text_secondary": "#ABC1B3",
            "ui_text_tertiary": "#ABC1B3",
            "ui_text_disabled": "#65766C",
            "ui_eyebrow": "#ABC1B3",
            "ui_accent": "#80D6AB",
            "ui_accent_hover": "#58CF94",
            "ui_accent_pressed": "#2FA76B",
            "ui_accent_soft": "#204634",
            "ui_accent_border": "#3A7253",
            "ui_on_accent": "#102E20",
            "ui_focus": "#78E0AA",
            "progress_complete": "#80D6AB"
        }
    },
    "High Contrast": {
        "light": {
            "ui_canvas": "#FFFFFF",
            "ui_surface_1": "#FFFFFF",
            "ui_surface_2": "#F3F3F3",
            "ui_surface_3": "#F3F3F3",
            "ui_border_subtle": "#525252",
            "ui_border_default": "#525252",
            "ui_border_strong": "#20262D",
            "ui_text_primary": "#111111",
            "ui_text_secondary": "#444444",
            "ui_text_tertiary": "#444444",
            "ui_text_disabled": "#6F7882",
            "ui_eyebrow": "#444444",
            "ui_accent": "#004FCE",
            "ui_accent_hover": "#004EA8",
            "ui_accent_pressed": "#003E86",
            "ui_accent_soft": "#E7EFFF",
            "ui_accent_border": "#286FC2",
            "ui_on_accent": "#FFFFFF",
            "ui_focus": "#007BFF",
            "progress_complete": "#004FCE"
        },
        "dark": {
            "ui_canvas": "#000000",
            "ui_surface_1": "#080C11",
            "ui_surface_2": "#101820",
            "ui_surface_3": "#101820",
            "ui_border_subtle": "#9BACBE",
            "ui_border_default": "#9BACBE",
            "ui_border_strong": "#C7CDD4",
            "ui_text_primary": "#FFFFFF",
            "ui_text_secondary": "#D0DCE9",
            "ui_text_tertiary": "#D0DCE9",
            "ui_text_disabled": "#747D87",
            "ui_eyebrow": "#D0DCE9",
            "ui_accent": "#80CAFF",
            "ui_accent_hover": "#7DBAFF",
            "ui_accent_pressed": "#3B8DE8",
            "ui_accent_soft": "#112F44",
            "ui_accent_border": "#4D82B8",
            "ui_on_accent": "#03111B",
            "ui_focus": "#9DCEFF",
            "progress_complete": "#80CAFF"
        }
    }
}


HEATMAP_PRESET_NAMES: Mapping[str, tuple[str, ...]] = {
    "Sapphire Glass": ("Sapphire", "Amethyst", "Glacier", "Sea Glass"),
    "Graphite": ("Slate", "Steel", "Plum", "Mint"),
    "Emerald": ("Emerald", "Jade", "Moss", "Lagoon"),
    "High Contrast": ("Cyan", "Gold", "Magenta", "Monochrome"),
}


HEATMAP_COMPLETION_TEXT = {
    "Sapphire Glass": {
        "Sapphire": {
            "light": ("#52647C", "#101820", "#101820", "#101820", "#101820", "#FFFFFF",),
            "dark": ("#A4B4C8", "#FFFFFF", "#FFFFFF", "#FFFFFF", "#101820", "#101820",)
        },
        "Amethyst": {
            "dark": ("#A4B4C8", "#FFFFFF", "#FFFFFF", "#FFFFFF", "#101820", "#101820",),
            "light": ("#52647C", "#101820", "#101820", "#101820", "#101820", "#FFFFFF",)
        },
        "Glacier": {
            "light": ("#52647C", "#101820", "#101820", "#101820", "#101820", "#FFFFFF",),
            "dark": ("#A4B4C8", "#FFFFFF", "#FFFFFF", "#FFFFFF", "#101820", "#101820",)
        },
        "Sea Glass": {
            "dark": ("#A4B4C8", "#FFFFFF", "#FFFFFF", "#FFFFFF", "#101820", "#101820",),
            "light": ("#52647C", "#101820", "#101820", "#101820", "#101820", "#FFFFFF",)
        }
    },
    "Graphite": {
        "Slate": {
            "dark": ("#ACB3BF", "#FFFFFF", "#FFFFFF", "#FFFFFF", "#101820", "#101820",),
            "light": ("#5C6470", "#101820", "#101820", "#101820", "#101820", "#FFFFFF",)
        },
        "Steel": {
            "light": ("#5C6470", "#101820", "#101820", "#101820", "#101820", "#FFFFFF",),
            "dark": ("#ACB3BF", "#FFFFFF", "#FFFFFF", "#FFFFFF", "#101820", "#101820",)
        },
        "Plum": {
            "dark": ("#ACB3BF", "#FFFFFF", "#FFFFFF", "#FFFFFF", "#101820", "#101820",),
            "light": ("#5C6470", "#101820", "#101820", "#101820", "#101820", "#FFFFFF",)
        },
        "Mint": {
            "light": ("#5C6470", "#101820", "#101820", "#101820", "#101820", "#FFFFFF",),
            "dark": ("#ACB3BF", "#FFFFFF", "#FFFFFF", "#FFFFFF", "#101820", "#101820",)
        }
    },
    "Emerald": {
        "Emerald": {
            "dark": ("#ABC1B3", "#FFFFFF", "#FFFFFF", "#FFFFFF", "#101820", "#101820",),
            "light": ("#527063", "#101820", "#101820", "#101820", "#101820", "#FFFFFF",)
        },
        "Jade": {
            "light": ("#527063", "#101820", "#101820", "#101820", "#101820", "#FFFFFF",),
            "dark": ("#ABC1B3", "#FFFFFF", "#FFFFFF", "#FFFFFF", "#101820", "#101820",)
        },
        "Moss": {
            "dark": ("#ABC1B3", "#FFFFFF", "#FFFFFF", "#FFFFFF", "#101820", "#101820",),
            "light": ("#527063", "#101820", "#101820", "#101820", "#101820", "#FFFFFF",)
        },
        "Lagoon": {
            "light": ("#527063", "#101820", "#101820", "#101820", "#101820", "#FFFFFF",),
            "dark": ("#ABC1B3", "#FFFFFF", "#FFFFFF", "#FFFFFF", "#101820", "#101820",)
        }
    },
    "High Contrast": {
        "Cyan": {
            "dark": ("#D0DCE9", "#FFFFFF", "#FFFFFF", "#000000", "#101820", "#101820",),
            "light": ("#444444", "#101820", "#101820", "#101820", "#000000", "#FFFFFF",)
        },
        "Gold": {
            "dark": ("#D0DCE9", "#FFFFFF", "#FFFFFF", "#101820", "#101820", "#101820",),
            "light": ("#444444", "#101820", "#101820", "#101820", "#FFFFFF", "#FFFFFF",)
        },
        "Magenta": {
            "dark": ("#D0DCE9", "#FFFFFF", "#FFFFFF", "#FFFFFF", "#101820", "#101820",),
            "light": ("#444444", "#101820", "#101820", "#101820", "#FFFFFF", "#FFFFFF",)
        },
        "Monochrome": {
            "light": ("#444444", "#101820", "#101820", "#101820", "#FFFFFF", "#FFFFFF",),
            "dark": ("#D0DCE9", "#FFFFFF", "#FFFFFF", "#101820", "#101820", "#101820",)
        }
    }
}


def _heat_text(fill: str, primary: str) -> str:
    """Choose the strongest readable date color for an authored heat cell."""

    candidates = (primary, "#FFFFFF", "#0B1116", "#000000")
    return max(candidates, key=lambda candidate: contrast_ratio(candidate, fill))


def _heat_tokens(
    theme_name: str,
    variant: str,
    core: Mapping[str, str],
    preset_name: str | None = None,
) -> Theme:
    selected = preset_name or HEATMAP_PRESET_NAMES[theme_name][0]
    completion = HEATMAP_COMPLETION_SCALES[theme_name][selected][variant]
    complete_text = HEATMAP_COMPLETION_TEXT[theme_name][selected][variant]
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
    core["ui_shadow_card"] = "none"
    core["ui_shadow_overlay"] = (
        "none" if theme_name == "High Contrast"
        else "0 4px 12px rgba(16, 24, 40, 0.10), 0 16px 32px rgba(16, 24, 40, 0.12)"
        if variant == "light"
        else "0 2px 8px rgba(0, 0, 0, 0.48), 0 18px 38px rgba(0, 0, 0, 0.30)"
    )
    core.update(SEMANTIC_PALETTES[variant])
    core.update(SEMANTIC_THEME_OVERRIDES.get(theme_name, {}).get(variant, {}))
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
        "calendar_selected_ring": core["ui_accent"],
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


# Historical heatmap preference identifiers remain valid.  Each identifier now
# resolves to its own authored hue ladder while retaining the stable theme
# boundary and the same persisted value.
HEATMAP_PRESETS: Mapping[str, Mapping[str, Mapping[str, Theme]]] = {
    theme_name: {
        preset_name: {
            variant: {
                key: value
                for key, value in _heat_tokens(
                    theme_name,
                    variant,
                    CORE_PALETTES[theme_name][variant],
                    preset_name,
                ).items()
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
    resolved["calendar_empty_bg"] = resolved["heat_complete_0"]
    resolved["heatmap_preset"] = calendar_name
    return resolved
