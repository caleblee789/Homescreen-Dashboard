"""Four release palettes expressed as complete semantic design tokens."""

from __future__ import annotations

from typing import Dict, Mapping


Theme = Dict[str, str]


# Every calendar preset below owns a complete light and dark ladder.  The
# explicit foreground/background pairs are intentional: no level is produced
# by changing opacity or by guessing a text color at runtime.
def _authored_ramp(light, dark):
    roles = ("empty", "1", "2", "3", "4", "5", "out_of_month")
    return {
        variant: {
            key: value
            for role, pair in zip(roles, values)
            for key, value in (
                ("heatmap_{}".format(role), pair[0]),
                ("on_heatmap_{}".format(role), pair[1]),
            )
        }
        for variant, values in (("light", light), ("dark", dark))
    }


HEATMAP_PRESETS: Mapping[str, Mapping[str, Mapping[str, Mapping[str, str]]]] = {
    "Sapphire Glass": {
        "Sapphire": _authored_ramp(
            (("#e8eef7", "#344054"), ("#e0edff", "#17365d"),
             ("#bdd8ff", "#153250"), ("#75abf4", "#102c48"),
             ("#1e63b6", "#ffffff"), ("#123f78", "#ffffff"),
             ("#f3f6fa", "#596579")),
            (("#253449", "#d6e1f0"), ("#173b67", "#f4f8ff"),
             ("#14528f", "#ffffff"), ("#1b6ba9", "#ffffff"),
             ("#78aef2", "#102c48"), ("#c0d9ff", "#102c48"),
             ("#152234", "#93a4ba")),
        ),
        "Amethyst": _authored_ramp(
            (("#eceaf4", "#3c3650"), ("#f0e8ff", "#452b68"),
             ("#dcc9fb", "#3b2559"), ("#b493e5", "#2f1c49"),
             ("#7144a6", "#ffffff"), ("#4c2878", "#ffffff"),
             ("#f5f3f8", "#655d73")),
            (("#312d40", "#ded8eb"), ("#43285f", "#faf6ff"),
             ("#603885", "#ffffff"), ("#8050aa", "#ffffff"),
             ("#be9be4", "#2f1c49"), ("#e1cdf8", "#2f1c49"),
             ("#211e2b", "#9b92aa")),
        ),
        "Glacier": _authored_ramp(
            (("#e8f0f2", "#304349"), ("#e1f6fb", "#183f49"),
             ("#addfe9", "#173a43"), ("#7acbd9", "#12343b"),
             ("#187e91", "#ffffff"), ("#0e5868", "#ffffff"),
             ("#f2f7f8", "#586b70")),
            (("#26383d", "#d7e4e7"), ("#17444e", "#f2fcff"),
             ("#145d69", "#ffffff"), ("#167c8a", "#ffffff"),
             ("#72c7d4", "#12343b"), ("#bce8ef", "#12343b"),
             ("#17272b", "#8fa4a9")),
        ),
        "Sea Glass": _authored_ramp(
            (("#e7f0ed", "#30443e"), ("#e0f7f0", "#17453a"),
             ("#b8e8da", "#163d34"), ("#73c8b0", "#12352d"),
             ("#187f68", "#ffffff"), ("#0d594a", "#ffffff"),
             ("#f1f7f5", "#576d66")),
            (("#263a35", "#d7e6e1"), ("#17473b", "#f2fff9"),
             ("#12604e", "#ffffff"), ("#147e68", "#ffffff"),
             ("#6bc5ad", "#12352d"), ("#b4e6d8", "#12352d"),
             ("#172925", "#8ca59d")),
        ),
    },
    "Graphite": {
        "Slate": _authored_ramp(
            (("#e6e9ed", "#353b44"), ("#e4e9f0", "#303c4b"),
             ("#bdc7d3", "#2b3541"), ("#9daab9", "#222b35"),
             ("#596776", "#ffffff"), ("#37414d", "#ffffff"),
             ("#f2f3f5", "#60666f")),
            (("#30343a", "#dfe2e6"), ("#384553", "#f7f9fb"),
             ("#4b5b6b", "#ffffff"), ("#637486", "#ffffff"),
             ("#a5b0bc", "#222b35"), ("#d0d6dd", "#222b35"),
             ("#202327", "#9ba1a9")),
        ),
        "Steel": _authored_ramp(
            (("#e5eaec", "#344046"), ("#e1edf2", "#29414d"),
             ("#b4cdd7", "#263b45"), ("#8fb2c0", "#1d323b"),
             ("#48798c", "#ffffff"), ("#2c5362", "#ffffff"),
             ("#f1f4f5", "#5c696f")),
            (("#2d373b", "#dce5e8"), ("#28434f", "#f5fbfd"),
             ("#3a6070", "#ffffff"), ("#4a7486", "#ffffff"),
             ("#94bac7", "#1d323b"), ("#c5dbe2", "#1d323b"),
             ("#1e2528", "#96a4a9")),
        ),
        "Plum": _authored_ramp(
            (("#ebe7ec", "#413842"), ("#f0e5f2", "#49304d"),
             ("#ddc9df", "#412b44"), ("#b792bb", "#342037"),
             ("#794b7d", "#ffffff"), ("#542f58", "#ffffff"),
             ("#f5f2f5", "#6b606c")),
            (("#383038", "#e7dfe7"), ("#4b304e", "#fff8ff"),
             ("#664169", "#ffffff"), ("#87598b", "#ffffff"),
             ("#c29ac5", "#342037"), ("#e2cce4", "#342037"),
             ("#272127", "#a79aa7")),
        ),
        "Mint": _authored_ramp(
            (("#e7ece9", "#35413c"), ("#e2f2e9", "#244536"),
             ("#b4d7c4", "#213e32"), ("#8fbea4", "#19372a"),
             ("#4d8064", "#ffffff"), ("#315b45", "#ffffff"),
             ("#f1f4f2", "#5f6b65")),
            (("#2e3934", "#dce5e0"), ("#294a3a", "#f5fcf8"),
             ("#3a624e", "#ffffff"), ("#4b7861", "#ffffff"),
             ("#95bea8", "#19372a"), ("#c5ddcf", "#19372a"),
             ("#1f2723", "#98a69f")),
        ),
    },
    "Emerald": {
        "Emerald": _authored_ramp(
            (("#e5efe9", "#30443a"), ("#dcf5e6", "#17452e"),
             ("#afe5c5", "#153d29"), ("#66c28d", "#103522"),
             ("#147a43", "#ffffff"), ("#0b552f", "#ffffff"),
             ("#f0f6f2", "#566c60")),
            (("#243a2e", "#d4e6dc"), ("#15462b", "#effcf4"),
             ("#105f38", "#ffffff"), ("#127d49", "#ffffff"),
             ("#61c087", "#103522"), ("#abe3c1", "#103522"),
             ("#15281e", "#89a394")),
        ),
        "Jade": _authored_ramp(
            (("#e5efec", "#30443f"), ("#daf5ed", "#16473a"),
             ("#aae4d3", "#143f34"), ("#5fc0a4", "#0f372c"),
             ("#0e7a5d", "#ffffff"), ("#07543f", "#ffffff"),
             ("#eff6f4", "#556d65")),
            (("#233a34", "#d3e6e0"), ("#124735", "#effcf8"),
             ("#0d6047", "#ffffff"), ("#0e7d5d", "#ffffff"),
             ("#5bc09f", "#0f372c"), ("#a7e2d0", "#0f372c"),
             ("#142824", "#88a49b")),
        ),
        "Moss": _authored_ramp(
            (("#eaede4", "#3b4131"), ("#ecf3d8", "#3b461b"),
             ("#d1dfa7", "#35401a"), ("#a2bb66", "#2b3513"),
             ("#647b25", "#ffffff"), ("#445718", "#ffffff"),
             ("#f3f5ef", "#666c5b")),
            (("#34392c", "#e2e7d9"), ("#3d491f", "#fafdeb"),
             ("#53632b", "#ffffff"), ("#697c32", "#ffffff"),
             ("#aabb6b", "#2b3513"), ("#d1dea7", "#2b3513"),
             ("#24271f", "#a0a694")),
        ),
        "Lagoon": _authored_ramp(
            (("#e4efef", "#304445"), ("#d8f5f5", "#13464a"),
             ("#a7e3e5", "#123e42"), ("#5cbdc2", "#0d3639"),
             ("#08777d", "#ffffff"), ("#045257", "#ffffff"),
             ("#eff6f6", "#556c6d")),
            (("#223a3b", "#d2e6e7"), ("#10464a", "#effcfd"),
             ("#0b5f64", "#ffffff"), ("#0c7c82", "#ffffff"),
             ("#57bcc1", "#0d3639"), ("#a3e1e3", "#0d3639"),
             ("#132829", "#87a3a4")),
        ),
    },
    "High Contrast": {
        "Cyan": _authored_ramp(
            (("#e5eef0", "#243b41"), ("#d9f8ff", "#003d4a"),
             ("#9fe9f5", "#003842"), ("#42cadd", "#002f37"),
             ("#007e91", "#ffffff"), ("#004f5c", "#ffffff"),
             ("#f2f6f7", "#52686d")),
            (("#26373b", "#e5f2f5"), ("#00424e", "#ffffff"),
             ("#005d6e", "#ffffff"), ("#00798d", "#ffffff"),
             ("#54d1e1", "#002f37"), ("#a5ebf5", "#002f37"),
             ("#172528", "#9ab0b5")),
        ),
        "Gold": _authored_ramp(
            (("#f0ece2", "#443b27"), ("#fff2c2", "#4d3800"),
             ("#f5d978", "#453300"), ("#d9ad25", "#382900"),
             ("#9a6800", "#ffffff"), ("#684300", "#ffffff"),
             ("#f7f4ed", "#6d6555")),
            (("#3d382c", "#f0e9d8"), ("#4b3700", "#fff9e8"),
             ("#6b4e00", "#ffffff"), ("#876700", "#ffffff"),
             ("#e0b62e", "#382900"), ("#ffea73", "#382900"),
             ("#2a271f", "#ada48f")),
        ),
        "Magenta": _authored_ramp(
            (("#f0e7ed", "#463440"), ("#ffe2f4", "#5a1e43"),
             ("#f5b9df", "#501a3b"), ("#df72b6", "#42132f"),
             ("#a22370", "#ffffff"), ("#6e124a", "#ffffff"),
             ("#f7f1f5", "#705f69")),
            (("#3d3038", "#f0e0e9"), ("#5a1a43", "#fff5fb"),
             ("#7c205a", "#ffffff"), ("#a42a78", "#ffffff"),
             ("#e179ba", "#42132f"), ("#f4bade", "#42132f"),
             ("#2a2026", "#ad99a5")),
        ),
        "Monochrome": _authored_ramp(
            (("#e8e8e8", "#333333"), ("#f2f2f2", "#292929"),
             ("#c7c7c7", "#242424"), ("#9e9e9e", "#1f1f1f"),
             ("#565656", "#ffffff"), ("#202020", "#ffffff"),
             ("#f7f7f7", "#626262")),
            (("#303030", "#e5e5e5"), ("#404040", "#ffffff"),
             ("#535353", "#ffffff"), ("#6b6b6b", "#ffffff"),
             ("#b8b8b8", "#1f1f1f"), ("#e1e1e1", "#1f1f1f"),
             ("#1d1d1d", "#a8a8a8")),
        ),
    },
}

DEFAULT_HEATMAP_PRESETS: Mapping[str, str] = {
    theme_name: next(iter(presets))
    for theme_name, presets in HEATMAP_PRESETS.items()
}
DEFAULT_HEATMAP_PRESET = DEFAULT_HEATMAP_PRESETS["Sapphire Glass"]


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
    return "#{:02x}{:02x}{:02x}".format(*values)


def _luminance(value: str) -> float:
    channels = [item / 255 for item in _channels(value)]
    linear = [
        item / 12.92 if item <= .04045 else ((item + .055) / 1.055) ** 2.4
        for item in channels
    ]
    return .2126 * linear[0] + .7152 * linear[1] + .0722 * linear[2]


def _contrast(left: str, right: str) -> float:
    high, low = sorted((_luminance(left), _luminance(right)), reverse=True)
    return (high + .05) / (low + .05)


def _on_color(background: str) -> str:
    return (
        "#ffffff"
        if _contrast("#ffffff", background) >= _contrast("#000000", background)
        else "#000000"
    )


def _theme(
    background: str,
    surface: str,
    border: str,
    text: str,
    muted: str,
    accent: str,
    accent_soft: str,
    forecast: str,
    shadow: str,
    *,
    completion: str,
    new: str,
    review: str,
    success: str,
    warning: str,
    danger: str,
    event: str,
) -> Theme:
    """Build one variant without allowing components to invent local colors."""

    danger_soft = composite_color(danger, surface, .12)
    theme = {
        "background": background,
        "surface": surface,
        "panel_surface": surface,
        "border": border,
        "control_border": border,
        "text": text,
        "muted": muted,
        "disabled": muted,
        "accent": accent,
        "selection": accent,
        "accent_soft": accent_soft,
        "forecast": forecast,
        "due_stripe": forecast,
        "completion": completion,
        # Compatibility alias while consumers move to the semantic name.
        "progress_percent": completion,
        "new": new,
        "review": review,
        "success": success,
        "warning": warning,
        "danger": danger,
        "danger_soft": danger_soft,
        "event": event,
        "empty": "rgba(127, 140, 160, 0.18)",
        "shadow": shadow,
        "focus": accent,
        **HEATMAP_PRESETS["Sapphire Glass"][DEFAULT_HEATMAP_PRESET]["light"],
    }
    for role in (
        "accent",
        "selection",
        "forecast",
        "completion",
        "new",
        "review",
        "success",
        "warning",
        "danger",
        "event",
    ):
        theme["on_{}".format(role)] = _on_color(theme[role])
    for level in range(1, 6):
        theme["on_heatmap_{}".format(level)] = _on_color(
            theme["heatmap_{}".format(level)]
        )
    return theme


# Insertion order is the public Settings order. Do not add hidden legacy themes.
PRESETS: Mapping[str, Mapping[str, Theme]] = {
    "Sapphire Glass": {
        "light": _theme(
            "#edf5ff", "#ffffff", "#bfd5f2", "#16243a", "#5a6b82",
            "#2176d2", "#d9ebff", "#69a9e8", "rgba(20,67,116,.18)",
            completion="#6D28D9", new="#0369A1", review="#9D174D",
            success="#15803D", warning="#92400E", danger="#B42318",
            event="#7A4B00",
        ),
        "dark": _theme(
            "#0b1624", "#12243a", "#2b4d70", "#f0f7ff", "#a9bdd3",
            "#55a7ff", "#193d62", "#7ab9ef", "rgba(0,0,0,.50)",
            completion="#C4B5FD", new="#38BDF8", review="#F472B6",
            success="#4ADE80", warning="#FBBF24", danger="#FFB4AB",
            event="#FDBA74",
        ),
    },
    "Graphite": {
        "light": _theme(
            "#eef0f3", "#fafafa", "#cfd3d9", "#202124", "#5f6368",
            "#343a40", "#dfe3e8", "#747b85", "rgba(18,22,28,.14)",
            completion="#6D28D9", new="#0369A1", review="#9D174D",
            success="#15803D", warning="#92400E", danger="#B42318",
            event="#7A4B00",
        ),
        "dark": _theme(
            "#111315", "#1c1f23", "#353a40", "#f5f6f7", "#a4abb3",
            "#dfe3e8", "#30353b", "#868e96", "rgba(0,0,0,.45)",
            completion="#C4B5FD", new="#38BDF8", review="#F472B6",
            success="#4ADE80", warning="#FBBF24", danger="#FFB4AB",
            event="#FDBA74",
        ),
    },
    "Emerald": {
        "light": _theme(
            "#f0faf4", "#ffffff", "#bfdfca", "#173523", "#587864",
            "#16834b", "#d8f2e1", "#68b987", "rgba(14,86,47,.15)",
            completion="#6D28D9", new="#0369A1", review="#9D174D",
            success="#7A6B00", warning="#92400E", danger="#B42318",
            event="#7A4B00",
        ),
        "dark": _theme(
            "#091a11", "#112b1c", "#2c5239", "#effff4", "#a8c9b3",
            "#3fd17b", "#17492d", "#6ab58a", "rgba(0,0,0,.48)",
            completion="#C4B5FD", new="#38BDF8", review="#F472B6",
            success="#D9FF1A", warning="#FBBF24", danger="#FFB4AB",
            event="#FDBA74",
        ),
    },
    "High Contrast": {
        "light": _theme(
            "#ffffff", "#ffffff", "#000000", "#000000", "#303030",
            "#0047cc", "#dbe9ff", "#005A5A", "rgba(0,0,0,.22)",
            completion="#4C1D95", new="#006B8F", review="#9D174D",
            success="#006B2D", warning="#7A3E00", danger="#B00020",
            event="#7A4B00",
        ),
        "dark": _theme(
            "#000000", "#000000", "#ffffff", "#ffffff", "#e5e5e5",
            "#66b3ff", "#002b55", "#FFD166", "rgba(255,255,255,.18)",
            completion="#DDD6FE", new="#67E8F9", review="#F9A8D4",
            success="#86EFAC", warning="#FBBF24", danger="#FFB4AB",
            event="#FFFFFF",
        ),
    },
}


def resolve_theme(
    preset: object,
    mode: object,
    anki_dark: bool,
    heatmap_preset: object = DEFAULT_HEATMAP_PRESET,
) -> Theme:
    """Resolve a retained preset and enforce contrast-safe structural tokens."""

    name = preset if isinstance(preset, str) and preset in PRESETS else "Sapphire Glass"
    selected_mode = mode if mode in {"auto", "light", "dark"} else "auto"
    variant = "dark" if (
        selected_mode == "dark" or (selected_mode == "auto" and anki_dark)
    ) else "light"
    resolved = dict(PRESETS[name][variant])
    available_calendar_presets = HEATMAP_PRESETS[name]
    calendar_name = (
        heatmap_preset
        if isinstance(heatmap_preset, str) and heatmap_preset in available_calendar_presets
        else DEFAULT_HEATMAP_PRESETS[name]
    )
    resolved.update(available_calendar_presets[calendar_name][variant])
    resolved["heatmap_preset"] = calendar_name

    try:
        if _contrast(resolved["control_border"], resolved["surface"]) < 3:
            resolved["control_border"] = resolved["muted"]
        if _contrast(resolved["focus"], resolved["surface"]) < 3:
            resolved["focus"] = resolved["text"]
        if _contrast(resolved["forecast"], resolved["surface"]) < 3:
            resolved["forecast"] = resolved["muted"]
            resolved["due_stripe"] = resolved["forecast"]
    except (ValueError, IndexError):
        resolved["control_border"] = resolved["text"]
        resolved["focus"] = resolved["text"]
        resolved["forecast"] = resolved["muted"]
        resolved["due_stripe"] = resolved["forecast"]

    minimum_opacity_surface = composite_color(
        resolved["surface"], resolved["background"], .70
    )
    resolved["accent_text"] = (
        resolved["accent"]
        if min(
            _contrast(resolved["accent"], resolved["surface"]),
            _contrast(resolved["accent"], minimum_opacity_surface),
        ) >= 4.5
        else resolved["text"]
    )
    for role in (
        "accent",
        "selection",
        "forecast",
        "completion",
        "new",
        "review",
        "success",
        "warning",
        "danger",
        "event",
    ):
        resolved["on_{}".format(role)] = _on_color(resolved[role])
    # Heatmap foregrounds are authored alongside each fill and intentionally
    # survive instead of being replaced by a black/white heuristic.
    # Compatibility names consumed by the current renderer and native Settings.
    resolved["progress_percent"] = resolved["completion"]
    resolved["on_accent"] = resolved["on_selection"]
    resolved["on_warning"] = _on_color(resolved["warning"])
    resolved["disabled"] = resolved["muted"]
    return resolved
