"""Professional preset palettes expressed as namespaced design tokens."""

from __future__ import annotations

from typing import Dict, Mapping


Theme = Dict[str, str]


def composite_color(foreground: str, background: str, opacity: float) -> str:
    """Return the opaque sRGB result of drawing foreground over background."""
    def channels(value: str) -> list[int]:
        raw = value.lstrip("#")
        return [int(raw[index:index + 2], 16) for index in (0, 2, 4)]

    values = [
        round(opacity * front + (1 - opacity) * back)
        for front, back in zip(channels(foreground), channels(background))
    ]
    return "#{:02x}{:02x}{:02x}".format(*values)


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
    progress_percent: str = "#6D28D9",
) -> Theme:
    return {
        "background": background,
        "surface": surface,
        "border": border,
        "control_border": border,
        "text": text,
        "muted": muted,
        "accent": accent,
        "accent_soft": accent_soft,
        "forecast": forecast,
        "progress_percent": progress_percent,
        "shadow": shadow,
        "focus": accent,
        "new": "#22a7d6",
        "success": "#22c55e",
        "warning": "#f59e0b",
        "danger": "#ef4444",
        "empty": "rgba(127, 140, 160, 0.18)",
    }


PRESETS: Mapping[str, Mapping[str, Theme]] = {
    "Adaptive Neutral": {
        "light": _theme("#f4f6f8", "#ffffff", "#d7dce3", "#1f2937", "#667085", "#475467", "#e4e7ec", "#98a2b3", "rgba(15,23,42,.12)"),
        "dark": _theme("#16191d", "#21252b", "#3a414b", "#f2f4f7", "#aab2bf", "#d0d5dd", "#344054", "#98a2b3", "rgba(0,0,0,.38)", "#C4B5FD"),
    },
    "Graphite": {
        "light": _theme("#eef0f3", "#fafafa", "#cfd3d9", "#202124", "#5f6368", "#343a40", "#dfe3e8", "#747b85", "rgba(18,22,28,.14)"),
        "dark": _theme("#111315", "#1c1f23", "#353a40", "#f5f6f7", "#a4abb3", "#dfe3e8", "#30353b", "#868e96", "rgba(0,0,0,.45)", "#C4B5FD"),
    },
    "Sapphire Glass": {
        "light": _theme("#edf5ff", "#ffffff", "#bfd5f2", "#16243a", "#5a6b82", "#2176d2", "#d9ebff", "#69a9e8", "rgba(20,67,116,.18)"),
        "dark": _theme("#0b1624", "#12243a", "#2b4d70", "#f0f7ff", "#a9bdd3", "#55a7ff", "#193d62", "#7ab9ef", "rgba(0,0,0,.50)", "#C4B5FD"),
    },
    "Arctic Blue": {
        "light": _theme("#f2f9fc", "#ffffff", "#c4e1ec", "#17313c", "#587680", "#1387ad", "#d8f1f8", "#6fb7ce", "rgba(19,75,94,.14)"),
        "dark": _theme("#09191f", "#102a34", "#28505c", "#ecfbff", "#a7c6cf", "#4cc9ef", "#164759", "#69b4ca", "rgba(0,0,0,.48)", "#C4B5FD"),
    },
    "Ocean Teal": {
        "light": _theme("#eefaf8", "#ffffff", "#b9ded8", "#153532", "#557873", "#078a7c", "#d2f2ed", "#5fbab0", "rgba(9,83,75,.15)"),
        "dark": _theme("#081b1a", "#102d2a", "#28544e", "#ebfffb", "#a4cbc5", "#32d5c4", "#154c45", "#68bcb3", "rgba(0,0,0,.48)", "#C4B5FD"),
    },
    "Emerald": {
        "light": _theme("#f0faf4", "#ffffff", "#bfdfca", "#173523", "#587864", "#16834b", "#d8f2e1", "#68b987", "rgba(14,86,47,.15)"),
        "dark": _theme("#091a11", "#112b1c", "#2c5239", "#effff4", "#a8c9b3", "#3fd17b", "#17492d", "#6ab58a", "rgba(0,0,0,.48)", "#C4B5FD"),
    },
    "Violet": {
        "light": _theme("#f7f3ff", "#ffffff", "#d7c8f2", "#2d2042", "#736486", "#7650c9", "#e9dfff", "#a88bdc", "rgba(61,34,108,.15)"),
        "dark": _theme("#160f24", "#261b3c", "#4a3970", "#f8f2ff", "#c4b3d9", "#ad82ff", "#3d285f", "#a691c9", "rgba(0,0,0,.5)", "#C4B5FD"),
    },
    "Rosewood": {
        "light": _theme("#fff4f5", "#ffffff", "#edc6cb", "#452329", "#86646a", "#b83b55", "#f9dfe4", "#dc8293", "rgba(105,29,45,.15)"),
        "dark": _theme("#210f13", "#371a21", "#6d3542", "#fff3f5", "#d7afb8", "#ff7693", "#5a2431", "#d18b9a", "rgba(0,0,0,.5)", "#C4B5FD"),
    },
    "Amber": {
        "light": _theme("#fff8e9", "#ffffff", "#ead39d", "#3f3218", "#7d6d48", "#b76d00", "#ffebbd", "#d39c46", "rgba(105,68,10,.15)"),
        "dark": _theme("#211807", "#36270c", "#6b5122", "#fff8e8", "#d4c29a", "#ffb83e", "#594014", "#d3a65f", "rgba(0,0,0,.5)", "#C4B5FD"),
    },
    "Sandstone": {
        "light": _theme("#f9f5ed", "#fffdf8", "#ddd0b8", "#393026", "#74695b", "#8b6840", "#efe3cf", "#b39a76", "rgba(74,53,30,.14)"),
        "dark": _theme("#1b1712", "#2c251d", "#55493a", "#faf5ed", "#c7bcae", "#d3ae7d", "#493923", "#b6a187", "rgba(0,0,0,.48)", "#C4B5FD"),
    },
    "Monochrome": {
        "light": _theme("#f5f5f5", "#ffffff", "#d4d4d4", "#171717", "#666666", "#171717", "#e5e5e5", "#858585", "rgba(0,0,0,.14)"),
        "dark": _theme("#0f0f0f", "#1d1d1d", "#3d3d3d", "#fafafa", "#b5b5b5", "#ffffff", "#333333", "#a3a3a3", "rgba(0,0,0,.55)", "#C4B5FD"),
    },
    "High Contrast": {
        "light": _theme("#ffffff", "#ffffff", "#000000", "#000000", "#303030", "#0047cc", "#dbe9ff", "#7a3e00", "rgba(0,0,0,.22)", "#4C1D95"),
        "dark": _theme("#000000", "#000000", "#ffffff", "#ffffff", "#e5e5e5", "#66b3ff", "#002b55", "#ffd166", "rgba(255,255,255,.18)", "#DDD6FE"),
    },
}


def resolve_theme(preset: object, mode: object, anki_dark: bool) -> Theme:
    name = preset if isinstance(preset, str) and preset in PRESETS else "Sapphire Glass"
    selected_mode = mode if mode in {"auto", "light", "dark"} else "auto"
    variant = "dark" if (selected_mode == "dark" or (selected_mode == "auto" and anki_dark)) else "light"
    resolved = dict(PRESETS[name][variant])

    def contrast(left: str, right: str) -> float:
        def luminance(value: str) -> float:
            raw = value.lstrip("#")
            channels = [int(raw[index:index + 2], 16) / 255 for index in (0, 2, 4)]
            linear = [channel / 12.92 if channel <= .04045 else ((channel + .055) / 1.055) ** 2.4 for channel in channels]
            return .2126 * linear[0] + .7152 * linear[1] + .0722 * linear[2]

        high, low = sorted((luminance(left), luminance(right)), reverse=True)
        return (high + .05) / (low + .05)

    try:
        if contrast(resolved["control_border"], resolved["surface"]) < 3:
            resolved["control_border"] = resolved["muted"]
        if contrast(resolved["focus"], resolved["surface"]) < 3:
            resolved["focus"] = resolved["text"]
        if contrast(resolved["forecast"], resolved["surface"]) < 3:
            resolved["forecast"] = resolved["muted"]
    except (ValueError, IndexError):
        resolved["control_border"] = resolved["text"]
        resolved["focus"] = resolved["text"]
        resolved["forecast"] = resolved["muted"]
    def on_color(background: str) -> str:
        candidate = background.lstrip("#")
        try:
            channels = [int(candidate[index:index + 2], 16) / 255 for index in (0, 2, 4)]
            linear = [value / 12.92 if value <= .04045 else ((value + .055) / 1.055) ** 2.4 for value in channels]
            luminance = .2126 * linear[0] + .7152 * linear[1] + .0722 * linear[2]
            white_ratio = 1.05 / (luminance + .05)
            black_ratio = (luminance + .05) / .05
            return "#ffffff" if white_ratio >= black_ratio else "#000000"
        except (ValueError, IndexError):
            return "#ffffff"

    # Accent fills retain each preset's identity, while text and study-status
    # roles use independently contrast-checked tokens. A single bright status
    # palette looked acceptable on dark cards but fell below AA on every light
    # card surface.
    minimum_opacity_surface = composite_color(
        resolved["surface"], resolved["background"], .70
    )
    resolved["accent_text"] = (
        resolved["accent"]
        if min(
            contrast(resolved["accent"], resolved["surface"]),
            contrast(resolved["accent"], minimum_opacity_surface),
        ) >= 4.5
        else resolved["text"]
    )
    resolved["new"] = "#38BDF8" if variant == "dark" else "#0369A1"
    resolved["success"] = "#4ADE80" if variant == "dark" else "#15803D"
    resolved["warning"] = "#FBBF24" if variant == "dark" else "#92400E"
    resolved["on_accent"] = on_color(resolved["accent"])
    resolved["on_warning"] = on_color(resolved["warning"])
    resolved["disabled"] = resolved["muted"]
    resolved["danger"] = "#ffb4ab" if variant == "dark" else "#b42318"
    resolved["danger_soft"] = "#4a2020" if variant == "dark" else "#fff0ee"
    return resolved
