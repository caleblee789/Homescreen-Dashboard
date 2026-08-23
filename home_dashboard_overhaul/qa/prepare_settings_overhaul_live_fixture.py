#!/usr/bin/env python3
"""Install the exact archive plus a migration/persistence fixture in a disposable run."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import zipfile


PACKAGE = "home_dashboard_overhaul"
PROBE_PACKAGE = "zz_hdo_settings_overhaul_probe"
EDITED_QUOTE = (
    "<strong>QA edited verse survives restart.</strong>"
    "<br>- Psalm 1:1 (NLT)"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _quote_fingerprint(quotes: list[str]) -> str:
    digest = hashlib.sha256()
    for quote in quotes:
        encoded = quote.encode("utf-8")
        digest.update(str(len(encoded)).encode("ascii"))
        digest.update(b":")
        digest.update(encoded)
    return digest.hexdigest()


def prepare(run_root: Path, archive_path: Path, probe_path: Path) -> dict[str, object]:
    resolved_root = run_root.resolve()
    if not str(resolved_root).startswith("/private/tmp/anki-release-qa."):
        raise ValueError("run root is not a helper-generated disposable Anki run")
    if not (resolved_root / "QA_IDENTITY.json").is_file():
        raise ValueError("run root is missing QA_IDENTITY.json")
    addons = resolved_root / "addons21"
    candidate = addons / PACKAGE
    probe = addons / PROBE_PACKAGE
    if candidate.exists() or probe.exists():
        raise FileExistsError("candidate or probe add-on already exists")
    candidate.mkdir(parents=True)
    probe.mkdir(parents=True)

    archive_members: dict[str, bytes] = {}
    with zipfile.ZipFile(archive_path) as source:
        for info in source.infolist():
            relative = PurePosixPath(info.filename)
            if relative.is_absolute() or ".." in relative.parts or info.is_dir():
                raise ValueError("unsafe archive member: {}".format(info.filename))
            data = source.read(info.filename)
            archive_members[info.filename] = data
            destination = candidate.joinpath(*relative.parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)

    config = json.loads((candidate / "config.json").read_text(encoding="utf-8"))
    config["schema_version"] = 5
    config["appearance"].update(
        preset="Graphite",
        mode="dark",
        opacity=91,
        text_scale=108,
    )
    config["heatmap"].update(calendar_view="month", week_start=6)
    config["heatmap"]["presets_by_theme"]["Graphite"] = "Steel"
    config["visibility"]["remaining"] = True
    config["home_screen"]["position"] = "bottom"
    config["events"]["items"] = [
        {
            "id": "qa-existing-active",
            "date": "2026-09-15",
            "name": "Existing migration event",
            "archived": False,
            "created_at": "2026-08-20T09:30:00-05:00",
            "archived_at": "",
        },
        {
            "id": "qa-existing-archived",
            "date": "2026-07-04",
            "name": "Existing archived event",
            "archived": True,
            "created_at": "2026-07-01T09:30:00-05:00",
            "archived_at": "2026-07-05T09:30:00-05:00",
        },
    ]
    quotes = list(config["bible"].get("quotes", []))
    if not quotes:
        verse_data = json.loads(
            (candidate / "default_verses.json").read_text(encoding="utf-8")
        )
        quotes = list(verse_data.get("quote", []))
    if not quotes:
        raise ValueError("candidate provides no Bible verse library")
    quotes[0] = EDITED_QUOTE
    config["bible"]["quotes"] = quotes
    config["bible"]["rotation_mode"] = "manual"
    config["migration"] = {
        "completed": True,
        "completed_at": "2026-08-20T09:30:00-05:00",
        "sources": {"schema5-live-fixture": "preserve"},
        "warnings": [],
    }
    config["qa_preserved_unknown"] = {
        "sentinel": "schema-five-settings-overhaul",
        "nested": {"keep": True},
    }
    (candidate / "meta.json").write_text(
        json.dumps({"config": config}, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    rotation_state = {
        "version": 1,
        "refresh_key": "manual",
        "quote_fingerprint": _quote_fingerprint(quotes),
        "quote": EDITED_QUOTE,
    }
    rotation_path = candidate / "user_files" / "rotation_state.json"
    rotation_path.parent.mkdir(parents=True, exist_ok=True)
    rotation_path.write_text(
        json.dumps(rotation_state, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    shutil.copy2(probe_path, probe / "__init__.py")

    mismatches = [
        name
        for name, expected in archive_members.items()
        if (candidate / name).read_bytes() != expected
    ]
    if mismatches:
        raise RuntimeError("installed candidate differs from archive: {}".format(mismatches))
    report = {
        "run_root": str(resolved_root),
        "archive": str(archive_path.resolve()),
        "archive_sha256": _sha256(archive_path),
        "archive_file_count": len(archive_members),
        "candidate": str(candidate),
        "candidate_payload_matches_archive": True,
        "probe": str(probe / "__init__.py"),
        "seed_schema": 5,
        "expected_migrated_schema": 6,
        "event_items": len(config["events"]["items"]),
        "verse_library_sha256": _quote_fingerprint(quotes),
        "rotation_state_sha256": _sha256(rotation_path),
        "unknown_sentinel": config["qa_preserved_unknown"],
    }
    (resolved_root / "hdo-settings-overhaul-fixture.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--probe", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.run_root, args.archive, args.probe), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
