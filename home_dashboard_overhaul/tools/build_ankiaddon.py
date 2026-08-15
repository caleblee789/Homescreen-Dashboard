#!/usr/bin/env python3
"""Build and byte-verify a deterministic Home Dashboard .ankiaddon archive."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import zipfile


ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
PACKAGE_FILES = [
    "__init__.py",
    "analytics.py",
    "insights.py",
    "config.json",
    "config.md",
    "config_schema.py",
    "controller.py",
    "default_verses.json",
    "LICENSE.txt",
    "manifest.json",
    "migration.py",
    "models.py",
    "README.md",
    "CHANGELOG.md",
    "renderer.py",
    "settings.py",
    "settings_model.py",
    "themes.py",
    "THIRD_PARTY_NOTICES.md",
    "verse.py",
    "web/dashboard.css",
    "web/dashboard.js",
    "user_files/README.txt",
]
DEFERRED_SOURCE_FILES = frozenset(
    {
        "calendar_manager_model.py",
        "calendar_models.py",
        "calendar_repository.py",
        "event_manager.py",
        "vendor-requirements.lock",
    }
)
DEFERRED_SOURCE_PREFIXES = ("_vendor/",)
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
FIXED_TIMESTAMP = (2026, 8, 13, 0, 0, 0)


def _json(relative: str) -> dict:
    parsed = json.loads((ROOT / relative).read_text(encoding="utf-8"))
    if not isinstance(parsed, dict):
        raise ValueError("{} must contain a JSON object".format(relative))
    return parsed


def _quoted_verse_count(entries: list[object]) -> int:
    total = 0
    pattern = re.compile(
        r"<br>\s*-\s*.+?\s+\d+:(\d+)(?:[-–](\d+))?\s+\(NLT\)\s*$"
    )
    for entry in entries:
        if not isinstance(entry, str):
            raise ValueError("default verse entries must be strings")
        match = pattern.search(entry)
        if match is None:
            raise ValueError("default verse entry has an uncountable NLT reference")
        first = int(match.group(1))
        last = int(match.group(2) or first)
        if last < first:
            raise ValueError("default verse entry has a reversed verse range")
        total += last - first + 1
    return total


def validate_sources() -> dict:
    deferred_entries = [
        name
        for name in PACKAGE_FILES
        if name in DEFERRED_SOURCE_FILES
        or name.startswith(DEFERRED_SOURCE_PREFIXES)
    ]
    if deferred_entries:
        raise ValueError(
            "deferred calendar sources cannot be packaged: {}".format(
                ", ".join(deferred_entries)
            )
        )
    missing = [name for name in PACKAGE_FILES if not (ROOT / name).is_file()]
    if missing:
        raise FileNotFoundError("missing package files: {}".format(", ".join(missing)))
    manifest = _json("manifest.json")
    config = _json("config.json")
    verse_data = _json("default_verses.json")
    verses = verse_data.get("quote")
    if manifest.get("package") != "home_dashboard_overhaul":
        raise ValueError("manifest package must be home_dashboard_overhaul")
    if manifest.get("name") != "Home Dashboard - Overhaul":
        raise ValueError("unexpected manifest name")
    version = manifest.get("human_version")
    if not isinstance(version, str) or not VERSION_RE.fullmatch(version):
        raise ValueError("human_version must use MAJOR.MINOR.PATCH")
    if manifest.get("min_point_version") != 260800 or manifest.get("max_point_version") != 260800:
        raise ValueError("release must be pinned to Anki 26.8")
    if config.get("schema_version") != 3:
        raise ValueError("config schema must be version 3")
    analytics_source = (ROOT / "analytics.py").read_text(encoding="utf-8")
    controller_source = (ROOT / "controller.py").read_text(encoding="utf-8")
    renderer_source = (ROOT / "renderer.py").read_text(encoding="utf-8")
    javascript_source = (ROOT / "web/dashboard.js").read_text(encoding="utf-8")
    css_source = (ROOT / "web/dashboard.css").read_text(encoding="utf-8")
    required_contracts = {
        "analytics.py": ("def browser_search_for_day", "events=_events(config, calendar_today)"),
        "controller.py": ("open_day_in_browser", "browser_search_for_day", "collect_day_insight"),
        "renderer.py": (
            "data-hdo-day-insight",
            "data-hdo-details-summary",
            "data-hdo-details-announcement",
        ),
        "web/dashboard.js": ('command("open_day"', "Cards most missed today", "renderDetailsSummary"),
        "web/dashboard.css": ("hdo-details-summary", "hdo-visually-hidden"),
    }
    source_values = {
        "analytics.py": analytics_source,
        "controller.py": controller_source,
        "renderer.py": renderer_source,
        "web/dashboard.js": javascript_source,
        "web/dashboard.css": css_source,
    }
    for relative, markers in required_contracts.items():
        missing_markers = [marker for marker in markers if marker not in source_values[relative]]
        if missing_markers:
            raise ValueError("{} is missing the approved insight contract: {}".format(relative, ", ".join(missing_markers)))
    forbidden_contracts = {
        "analytics.py": ("today_insight=today_insight", "collect_day_insight"),
        "controller.py": ("open_insight_in_browser", "snapshot.today_insight.date"),
        "web/dashboard.js": ('command("open_insight"', "Anki day", "Anki-day"),
    }
    for relative, markers in forbidden_contracts.items():
        present = [marker for marker in markers if marker in source_values[relative]]
        if present:
            raise ValueError("{} contains a superseded insight contract: {}".format(relative, ", ".join(present)))
    heatmap = config.get("heatmap", {})
    if heatmap.get("calendar_view") not in {"month", "year"} or "calendar_mode" in heatmap:
        raise ValueError("schema 3 must use calendar_view without calendar_mode")
    if not isinstance(verses, list) or not verses or len(verses) > 500:
        raise ValueError("default verse library must contain 1-500 entries")
    if (
        len(verses) != 483
        or _quoted_verse_count(verses) != 500
        or verse_data.get("scripture quoted verse count") != 500
    ):
        raise ValueError("bundled NLT library must remain at 483 entries / 500 quoted verses")
    scripture_notice = str(verse_data.get("scripture copyright", ""))
    notice_document = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    if (
        not scripture_notice
        or re.sub(r"\s+", " ", scripture_notice).strip()
        not in re.sub(r"\s+", " ", notice_document).strip()
    ):
        raise ValueError("the full bundled Scripture notice must ship in THIRD_PARTY_NOTICES.md")
    return manifest


def _zip_info(relative: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(relative, FIXED_TIMESTAMP)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    info.flag_bits |= 0x800
    return info


def verify_archive(artifact: Path) -> None:
    with zipfile.ZipFile(artifact) as archive:
        names = archive.namelist()
        if names != PACKAGE_FILES:
            raise ValueError("archive contents do not match the package allowlist")
        deferred_entries = [
            name
            for name in names
            if name in DEFERRED_SOURCE_FILES
            or name.startswith(DEFERRED_SOURCE_PREFIXES)
        ]
        if deferred_entries:
            raise ValueError(
                "archive contains deferred calendar sources: {}".format(
                    ", ".join(deferred_entries)
                )
            )
        if archive.testzip() is not None:
            raise ValueError("archive contains corrupt data")
        for name in names:
            path = PurePosixPath(name)
            if path.is_absolute() or ".." in path.parts or "__pycache__" in path.parts:
                raise ValueError("unsafe archive path: {}".format(name))
            if archive.read(name) != (ROOT / name).read_bytes():
                raise ValueError("archive differs from source: {}".format(name))
            if archive.getinfo(name).date_time != FIXED_TIMESTAMP:
                raise ValueError("archive timestamp is not deterministic")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_artifact() -> tuple[Path, Path, str]:
    manifest = validate_sources()
    version = manifest["human_version"]
    artifact = DIST / "home-dashboard-overhaul-{}.ankiaddon".format(version)
    temporary = Path(str(artifact) + ".tmp")
    checksum_file = Path(str(artifact) + ".sha256")
    DIST.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(temporary, "w") as archive:
            for relative in PACKAGE_FILES:
                archive.writestr(_zip_info(relative), (ROOT / relative).read_bytes())
        verify_archive(temporary)
        temporary.replace(artifact)
        verify_archive(artifact)
        digest = sha256(artifact)
        checksum_file.write_text("{}  {}\n".format(digest, artifact.name), encoding="ascii")
    except Exception:
        try:
            temporary.unlink()
        except OSError:
            pass
        raise
    return artifact, checksum_file, digest


def main() -> None:
    artifact, checksum_file, digest = build_artifact()
    print(artifact)
    print("sha256 {}".format(digest))
    print(checksum_file)


if __name__ == "__main__":
    main()
