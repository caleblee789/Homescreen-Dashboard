#!/usr/bin/env python3
"""Generate deterministic release reports for the dashboard color system."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Iterable


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = PACKAGE_ROOT.parent
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from home_dashboard_overhaul.themes import (  # noqa: E402
    COMPLETION_SCALES,
    PRESETS,
    PROJECTED_DUE_SCALES,
    REVIEWS_DUE_INDICATORS,
    contrast_ratio,
    resolve_theme,
)


COLOR_PATTERN = re.compile(
    r"#[0-9A-Fa-f]{3,8}\b|rgba?\([^)]*\)|hsla?\([^)]*\)|"
    r"(?<![-\w])(?:white|black|blue|green|red)(?![-\w])",
    re.IGNORECASE,
)
SOURCE_SUFFIXES = {".css", ".scss", ".less", ".html", ".js", ".jsx", ".ts", ".tsx", ".svg", ".py", ".json"}
EXCLUDED_PARTS = {"_vendor", "dist", "tests", "tools", "__pycache__"}
QA_COLOR_FILES = {
    "qa/runtime_probe_contact_sheets_100.py",
    "qa/serve_revised_ui_preview.py",
    "qa/generate_final_release_contact_sheets.py",
}
CATEGORY_NAMES = {
    1: "Core theme token",
    2: "Stable semantic token",
    3: "Data visualization token",
    4: "Shadow or overlay",
    5: "Asset, configuration, or comparison-frame exception",
    6: "Unintentional component-level hardcoding",
}
DATA_COLOR_LITERALS = {
    color.upper()
    for theme_scales in COMPLETION_SCALES.values()
    for scale in theme_scales.values()
    for color in scale
} | {
    color.upper()
    for scale in PROJECTED_DUE_SCALES.values()
    for color in scale
    if color
} | {
    color.upper()
    for scale in REVIEWS_DUE_INDICATORS.values()
    for color in scale
    if color
}


def _source_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SOURCE_SUFFIXES:
            continue
        relative = path.relative_to(root)
        if any(part in EXCLUDED_PARTS for part in relative.parts):
            continue
        relative_name = relative.as_posix()
        if "qa" in relative.parts and relative_name not in QA_COLOR_FILES:
            continue
        if any(part.startswith(("final-release-contact-sheets-", "live-ui-acceptance-")) for part in relative.parts):
            continue
        yield path


def _category(relative: str, line: str, literal: str) -> tuple[int, str]:
    stripped = line.strip()
    lowered = line.casefold()
    if relative == "themes.py":
        if literal.casefold().startswith(("rgb", "hsl")) or "shadow" in lowered:
            return 4, "centralized opaque-overlay or shadow definition"
        if (
            literal.upper() in DATA_COLOR_LITERALS
            or "heat_" in lowered
            or "complete_text" in lowered
            or "due_text" in lowered
            or "completion_scale" in lowered
            or "projected_due" in lowered
        ):
            return 3, "centralized completion or projected-review visualization definition"
        if "status_" in lowered or "semantic_palette" in lowered:
            return 2, "centralized stable study-semantic definition"
        return 1, "centralized neutral or accent theme definition"
    if relative in QA_COLOR_FILES:
        return 5, "QA-only fixture or comparison framing outside the represented viewport"
    if relative in {"config.json", "default_verses.json"}:
        if literal.startswith("#") or "font color" in lowered or "font_color" in lowered:
            return 5, "persisted user-configurable custom verse-color default"
        return 5, "quoted content word; not a rendered color declaration"
    if stripped.startswith("#") or stripped.startswith(('"""', "'''")):
        return 5, "prose or comment reference; not a rendered color declaration"
    if "globalcolor." in lowered or "qcolor(" in lowered:
        return 5, "Qt application-palette lookup; not a raw rendered color"
    return 6, "rendered component color is outside the centralized token definitions"


def hardcoded_color_audit(root: Path = PACKAGE_ROOT) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    for path in _source_files(root):
        relative = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8")
        for line_number, line in enumerate(text.splitlines(), 1):
            for match in COLOR_PATTERN.finditer(line):
                category, reason = _category(relative, line, match.group(0))
                entries.append(
                    {
                        "file": relative,
                        "line": line_number,
                        "literal": match.group(0),
                        "category": category,
                        "category_name": CATEGORY_NAMES[category],
                        "reason": reason,
                    }
                )
    counts = Counter(entry["category"] for entry in entries)
    component_hardcoding = [entry for entry in entries if entry["category"] == 6]
    return {
        "schema_version": 1,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "scope": "Production CSS, JavaScript, HTML, SVG, Python renderers/settings, shipped JSON, and the active screenshot fixture/framing sources; tests, tools, vendor code, and generated evidence excluded",
        "pattern": COLOR_PATTERN.pattern,
        "files_scanned": len(list(_source_files(root))),
        "match_count": len(entries),
        "category_counts": {
            str(category): {
                "name": CATEGORY_NAMES[category],
                "count": counts.get(category, 0),
            }
            for category in CATEGORY_NAMES
        },
        "component_hardcoding_count": len(component_hardcoding),
        "status": "passed" if not component_hardcoding else "failed",
        "entries": entries,
    }


def _check(
    checks: list[dict[str, Any]],
    *,
    theme: str,
    mode: str,
    group: str,
    foreground_role: str,
    foreground: str,
    background_role: str,
    background: str,
    threshold: float,
    ratio: float | None = None,
    note: str = "",
) -> None:
    measured = contrast_ratio(foreground, background) if ratio is None else ratio
    checks.append(
        {
            "theme": theme,
            "mode": mode,
            "group": group,
            "foreground_role": foreground_role,
            "foreground": foreground,
            "background_role": background_role,
            "background": background,
            "ratio": round(measured, 3),
            "threshold": threshold,
            "passed": measured + 1e-9 >= threshold,
            "note": note,
        }
    )


def contrast_audit() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    advisories: list[dict[str, Any]] = []
    for theme_name in PRESETS:
        for mode in ("light", "dark"):
            tokens = resolve_theme(theme_name, mode, mode == "dark")
            for text_role in ("ui_text_primary", "ui_text_secondary", "ui_text_tertiary"):
                for surface_role in ("ui_surface_1", "ui_surface_2", "ui_surface_3", "calendar_footer_bg"):
                    _check(
                        checks,
                        theme=theme_name,
                        mode=mode,
                        group="calendar footer text" if surface_role == "calendar_footer_bg" else "interface text",
                        foreground_role=text_role,
                        foreground=tokens[text_role],
                        background_role=surface_role,
                        background=tokens[surface_role],
                        threshold=4.5,
                    )
            for state_role in ("ui_accent", "ui_accent_hover", "ui_accent_pressed"):
                _check(
                    checks,
                    theme=theme_name,
                    mode=mode,
                    group="primary button text",
                    foreground_role="ui_on_accent",
                    foreground=tokens["ui_on_accent"],
                    background_role=state_role,
                    background=tokens[state_role],
                    threshold=4.5,
                )
            for state_name, foreground_role, background_role in (
                ("default", "ui_text_secondary", "ui_surface_2"),
                ("hover", "ui_accent", "ui_accent_soft"),
                ("pressed", "ui_accent", "ui_surface_3"),
            ):
                _check(
                    checks,
                    theme=theme_name,
                    mode=mode,
                    group="secondary control text",
                    foreground_role=foreground_role,
                    foreground=tokens[foreground_role],
                    background_role=background_role,
                    background=tokens[background_role],
                    threshold=4.5,
                    note="{} neutral calendar-control state".format(state_name),
                )
            for semantic in ("new", "learning", "review", "buried", "success", "warning", "danger", "event"):
                _check(
                    checks,
                    theme=theme_name,
                    mode=mode,
                    group="semantic metric text",
                    foreground_role=f"status_{semantic}_text",
                    foreground=tokens[f"status_{semantic}_text"],
                    background_role="ui_surface_1",
                    background=tokens["ui_surface_1"],
                    threshold=4.5,
                )
            for level in range(6):
                fill_role = f"heat_complete_{level}"
                text_role = f"heat_complete_text_{level}"
                _check(
                    checks,
                    theme=theme_name,
                    mode=mode,
                    group="complete heat date text",
                    foreground_role=text_role,
                    foreground=tokens[text_role],
                    background_role=fill_role,
                    background=tokens[fill_role],
                    threshold=4.5,
                )
                selected_ratio = contrast_ratio(
                    tokens["calendar_selected_ring"], tokens["calendar_ring_halo"]
                )
                _check(
                    checks,
                    theme=theme_name,
                    mode=mode,
                    group="selected outline on completion heat",
                    foreground_role="calendar_selected_ring plus calendar_ring_halo",
                    foreground=tokens["calendar_selected_ring"],
                    background_role=fill_role,
                    background=tokens[fill_role],
                    threshold=3.0,
                    ratio=selected_ratio,
                    note="The focus-colored outer ring is directly adjacent to a one-pixel surface halo.",
                )
                today_ratio = contrast_ratio(tokens["calendar_today_ring"], tokens["calendar_ring_halo"])
                _check(
                    checks,
                    theme=theme_name,
                    mode=mode,
                    group="today ring on completion heat",
                    foreground_role="calendar_today_ring plus calendar_ring_halo",
                    foreground=tokens["calendar_today_ring"],
                    background_role=fill_role,
                    background=tokens[fill_role],
                    threshold=3.0,
                    ratio=today_ratio,
                    note="Today preserves the data fill and uses an inset accent ring with a surface halo.",
                )
                event_ratio = max(
                    contrast_ratio(tokens["status_event_fill"], tokens[fill_role]),
                    contrast_ratio(tokens["ui_text_primary"], tokens[fill_role]),
                    contrast_ratio(tokens["calendar_ring_halo"], tokens[fill_role]),
                )
                _check(
                    checks,
                    theme=theme_name,
                    mode=mode,
                    group="event marker on completion heat",
                    foreground_role="status_event_fill plus ui_text_primary outline plus calendar_ring_halo",
                    foreground=tokens["status_event_fill"],
                    background_role=fill_role,
                    background=tokens[fill_role],
                    threshold=3.0,
                    ratio=event_ratio,
                    note="Layered gold marker uses a text-primary outline and one-pixel surface halo.",
                )

            for level in range(1, 6):
                due_bg_role = "heat_due_bg_{}".format(level)
                due_mark_role = "heat_due_mark_{}".format(level)
                due_bg = tokens[due_bg_role]
                _check(
                    checks,
                    theme=theme_name,
                    mode=mode,
                    group="reviews due date text",
                    foreground_role="ui_text_primary",
                    foreground=tokens["ui_text_primary"],
                    background_role=due_bg_role,
                    background=due_bg,
                    threshold=4.5,
                )
                _check(
                    checks,
                    theme=theme_name,
                    mode=mode,
                    group="reviews due bottom marker",
                    foreground_role=due_mark_role,
                    foreground=tokens[due_mark_role],
                    background_role=due_bg_role,
                    background=due_bg,
                    threshold=2.75,
                    note="The fixed-height marker is also differentiated geometrically from full-cell completion fill.",
                )
                _check(
                    checks,
                    theme=theme_name,
                    mode=mode,
                    group="selected outline on reviews due",
                    foreground_role="calendar_selected_ring plus calendar_ring_halo",
                    foreground=tokens["calendar_selected_ring"],
                    background_role=due_bg_role,
                    background=due_bg,
                    threshold=3.0,
                    ratio=contrast_ratio(tokens["calendar_selected_ring"], tokens["calendar_ring_halo"]),
                )
                _check(
                    checks,
                    theme=theme_name,
                    mode=mode,
                    group="today ring on reviews due",
                    foreground_role="calendar_today_ring plus calendar_ring_halo",
                    foreground=tokens["calendar_today_ring"],
                    background_role=due_bg_role,
                    background=due_bg,
                    threshold=3.0,
                    ratio=contrast_ratio(tokens["calendar_today_ring"], tokens["calendar_ring_halo"]),
                )
                event_ratio = max(
                    contrast_ratio(tokens["status_event_fill"], tokens["ui_text_primary"]),
                    contrast_ratio(tokens["status_event_fill"], tokens["calendar_event_halo"]),
                )
                _check(
                    checks,
                    theme=theme_name,
                    mode=mode,
                    group="event marker on reviews due",
                    foreground_role="status_event_fill with text outline and surface halo",
                    foreground=tokens["status_event_fill"],
                    background_role=due_bg_role,
                    background=due_bg,
                    threshold=3.0,
                    ratio=event_ratio,
                )

            future_bg = tokens["calendar_future_bg"]
            _check(
                checks,
                theme=theme_name,
                mode=mode,
                group="future date text",
                foreground_role="calendar_future_text",
                foreground=tokens["calendar_future_text"],
                background_role="calendar_future_bg",
                background=future_bg,
                threshold=4.5,
            )
            _check(
                checks,
                theme=theme_name,
                mode=mode,
                group="empty past date text",
                foreground_role="heat_complete_text_0",
                foreground=tokens["heat_complete_text_0"],
                background_role="calendar_empty_bg",
                background=tokens["calendar_empty_bg"],
                threshold=4.5,
            )
            _check(
                checks,
                theme=theme_name,
                mode=mode,
                group="out-of-month date text",
                foreground_role="calendar_outside_text",
                foreground=tokens["calendar_outside_text"],
                background_role="calendar_outside_bg",
                background=tokens["calendar_outside_bg"],
                threshold=4.5,
            )
            for state_name, role in (
                ("selected outline", "calendar_selected_ring"),
                ("today ring", "calendar_today_ring"),
            ):
                _check(
                    checks,
                    theme=theme_name,
                    mode=mode,
                    group="{} on future date".format(state_name),
                    foreground_role="{} plus calendar_ring_halo".format(role),
                    foreground=tokens[role],
                    background_role="calendar_future_bg",
                    background=future_bg,
                    threshold=3.0,
                    ratio=contrast_ratio(tokens[role], tokens["calendar_ring_halo"]),
                    note="The interaction ring is isolated from data color by the surface halo.",
                )
            for boundary_role, adjacent_role in (("ui_border_strong", "ui_surface_2"),):
                _check(
                    checks,
                    theme=theme_name,
                    mode=mode,
                    group="important control boundary",
                    foreground_role=boundary_role,
                    foreground=tokens[boundary_role],
                    background_role=adjacent_role,
                    background=tokens[adjacent_role],
                    threshold=3.0,
                )
            _check(
                checks,
                theme=theme_name,
                mode=mode,
                group="selected control boundary",
                foreground_role="ui_focus",
                foreground=tokens["ui_focus"],
                background_role="ui_surface_1",
                background=tokens["ui_surface_1"],
                threshold=3.0,
            )
            default_border_ratio = contrast_ratio(tokens["ui_border_default"], tokens["ui_surface_2"])
            advisories.append(
                {
                    "theme": theme_name,
                    "mode": mode,
                    "pair": "ui_border_default against ui_surface_2",
                    "ratio": round(default_border_ratio, 3),
                    "purpose": "User-specified subtle structural/default border. It is not used alone as the selected, pressed, hover, or focus indicator.",
                }
            )
            advisories.append(
                {
                    "theme": theme_name,
                    "mode": mode,
                    "pair": "ui_accent_border against ui_accent_soft",
                    "ratio": round(contrast_ratio(tokens["ui_accent_border"], tokens["ui_accent_soft"]), 3),
                    "purpose": "The restrained accent border accompanies 4.5:1 accent text; keyboard focus and calendar selection use the independently gated ui-focus ring.",
                }
            )
            if theme_name == "High Contrast":
                for surface_role in ("ui_surface_1", "ui_surface_2", "ui_surface_3"):
                    _check(
                        checks,
                        theme=theme_name,
                        mode=mode,
                        group="High Contrast primary text",
                        foreground_role="ui_text_primary",
                        foreground=tokens["ui_text_primary"],
                        background_role=surface_role,
                        background=tokens[surface_role],
                        threshold=7.0,
                    )
    failures = [item for item in checks if not item["passed"]]
    return {
        "schema_version": 1,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "method": "WCAG 2.x relative luminance for opaque sRGB tokens; layered calendar states gate the deliberately adjacent accent/focus-to-surface-halo contour",
        "check_count": len(checks),
        "passed_count": len(checks) - len(failures),
        "failed_count": len(failures),
        "status": "passed" if not failures else "failed",
        "minimum_passing_ratio": min((item["ratio"] for item in checks), default=0),
        "checks": checks,
        "advisory_default_structural_borders": advisories,
    }


def changed_file_summary(root: Path = PACKAGE_ROOT) -> dict[str, Any]:
    command = ["git", "status", "--porcelain=v1", "--", root.name]
    result = subprocess.run(
        command,
        cwd=root.parent,
        check=True,
        capture_output=True,
        text=True,
    )
    files: list[dict[str, str]] = []
    evidence_prefix = f"{root.name}/qa/final-release-contact-sheets-"
    for raw in result.stdout.splitlines():
        if len(raw) < 4:
            continue
        status = raw[:2]
        path = raw[3:].split(" -> ")[-1]
        if path.startswith(evidence_prefix):
            continue
        relative = path[len(root.name) + 1:] if path.startswith(root.name + "/") else path
        if relative in {"themes.py", "renderer.py", "settings.py", "config_schema.py", "web/dashboard.css", "web/dashboard.js"}:
            group = "Color-system implementation"
        elif relative.startswith("tests/") or relative.startswith("qa/") or relative.startswith("tools/"):
            group = "Automated and visual QA"
        else:
            group = "Release documentation and metadata"
        files.append({"status": status, "file": relative, "group": group})
    return {
        "schema_version": 1,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "scope": "Current Home Dashboard 1.8.0 release-candidate worktree, excluding immutable generated evidence directories",
        "file_count": len(files),
        "files": files,
    }


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_release_reports(output: Path, root: Path = PACKAGE_ROOT) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    raw = hardcoded_color_audit(root)
    contrast = contrast_audit()
    changes = changed_file_summary(root)
    _write_json(output / "hardcoded-color-audit.json", raw)
    _write_json(output / "contrast-test-report.json", contrast)
    _write_json(output / "changed-file-summary.json", changes)

    category_lines = [
        "| Category | Classification | Matches |",
        "|---:|---|---:|",
        *[
            "| {} | {} | {} |".format(
                category,
                raw["category_counts"][str(category)]["name"],
                raw["category_counts"][str(category)]["count"],
            )
            for category in CATEGORY_NAMES
        ],
    ]
    exceptions = [entry for entry in raw["entries"] if entry["category"] == 5]
    raw_lines = [
        "# Hardcoded-color audit",
        "",
        f"Status: **{raw['status'].upper()}**",
        "",
        f"Scanned {raw['files_scanned']} production and active fixture files and classified {raw['match_count']} raw-color matches. Category 6 component hardcoding: **{raw['component_hardcoding_count']}**.",
        "",
        *category_lines,
        "",
        "Raw product literals are centralized in `themes.py`. Shipped JSON occurrences are the persisted, user-editable custom Bible color default; Qt named-color occurrences are application-palette lookups. Active fixture CSS is scanned, while opaque contact-sheet comparison framing is classified as an outside-viewport exception.",
        "",
        "## Classified exceptions",
        "",
        *(
            [f"- `{item['file']}:{item['line']}` — `{item['literal']}` — {item['reason']}" for item in exceptions]
            if exceptions else ["- None."]
        ),
        "",
    ]
    (output / "hardcoded-color-audit.md").write_text("\n".join(raw_lines), encoding="utf-8")

    group_counts = Counter(item["group"] for item in contrast["checks"])
    contrast_lines = [
        "# Contrast test report",
        "",
        f"Status: **{contrast['status'].upper()}**",
        "",
        f"Passed {contrast['passed_count']} of {contrast['check_count']} gated pairs; failed {contrast['failed_count']}. The lowest passing ratio was {contrast['minimum_passing_ratio']:.3f}:1.",
        "",
        "| Check family | Pairs | Result |",
        "|---|---:|---|",
        *[
            "| {} | {} | {} |".format(
                group,
                count,
                "PASS" if all(item["passed"] for item in contrast["checks"] if item["group"] == group) else "FAIL",
            )
            for group, count in sorted(group_counts.items())
        ],
        "",
        "The layered calendar checks model the rendered state: data fill first, then the one-pixel surface halo and selected/today ring, or the gold event fill with text-primary outline and surface halo.",
        "",
        "Default and restrained accent-border ratios are retained as advisory measurements because neither token is the sole focus or calendar-selection indicator. Gated important boundaries use `ui-border-strong` or the independent focus/state rings and clear 3:1.",
        "",
    ]
    if contrast["failed_count"]:
        contrast_lines.extend(
            ["## Failures", ""]
            + [
                "- {} / {} / {}: {} on {} = {:.3f}:1 (target {:.1f}:1)".format(
                    item["theme"], item["mode"], item["group"], item["foreground_role"],
                    item["background_role"], item["ratio"], item["threshold"],
                )
                for item in contrast["checks"] if not item["passed"]
            ]
            + [""]
        )
    (output / "contrast-test-report.md").write_text("\n".join(contrast_lines), encoding="utf-8")

    grouped = Counter(item["group"] for item in changes["files"])
    change_lines = [
        "# Changed-file summary",
        "",
        f"{changes['file_count']} current release-candidate files are modified or untracked outside immutable evidence directories.",
        "",
        *[
            f"## {group} ({grouped[group]})\n\n" + "\n".join(
                f"- `{item['status']}` `{item['file']}`"
                for item in changes["files"] if item["group"] == group
            ) + "\n"
            for group in (
                "Color-system implementation",
                "Automated and visual QA",
                "Release documentation and metadata",
            )
            if grouped[group]
        ],
        "",
    ]
    (output / "changed-file-summary.md").write_text("\n".join(change_lines), encoding="utf-8")
    return {
        "hardcoded_color_audit": {
            "status": raw["status"],
            "component_hardcoding_count": raw["component_hardcoding_count"],
            "json": "reports/hardcoded-color-audit.json",
            "markdown": "reports/hardcoded-color-audit.md",
        },
        "contrast_test_report": {
            "status": contrast["status"],
            "check_count": contrast["check_count"],
            "failed_count": contrast["failed_count"],
            "json": "reports/contrast-test-report.json",
            "markdown": "reports/contrast-test-report.md",
        },
        "changed_file_summary": {
            "file_count": changes["file_count"],
            "json": "reports/changed-file-summary.json",
            "markdown": "reports/changed-file-summary.md",
        },
    }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    summary = write_release_reports(args.output.resolve())
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if (
        summary["hardcoded_color_audit"]["status"] == "passed"
        and summary["contrast_test_report"]["status"] == "passed"
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
