#!/usr/bin/env python3
"""Install an exact add-on archive plus the disposable contact-sheet probe."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import zipfile


PACKAGE = "home_dashboard_overhaul"
PROBE_PACKAGE = "zz_hdo_contact_sheet_probe"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def prepare(run_root: Path, archive: Path, probe: Path) -> dict[str, object]:
    root = run_root.resolve()
    if not str(root).startswith("/private/tmp/anki-release-qa."):
        raise ValueError("run root is not a helper-generated disposable Anki run")
    if not (root / "QA_IDENTITY.json").is_file():
        raise ValueError("run root is missing QA_IDENTITY.json")
    archive = archive.resolve()
    probe = probe.resolve()
    addons = root / "addons21"
    candidate_root = addons / PACKAGE
    probe_root = addons / PROBE_PACKAGE
    if candidate_root.exists() or probe_root.exists():
        raise FileExistsError("candidate or contact-sheet probe already exists")
    candidate_root.mkdir(parents=True)
    probe_root.mkdir(parents=True)

    members: dict[str, str] = {}
    with zipfile.ZipFile(archive) as source:
        for info in source.infolist():
            relative = PurePosixPath(info.filename)
            if relative.is_absolute() or ".." in relative.parts or info.is_dir():
                raise ValueError("unsafe archive member: {}".format(info.filename))
            data = source.read(info.filename)
            destination = candidate_root.joinpath(*relative.parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
            members[info.filename] = hashlib.sha256(data).hexdigest()
    shutil.copy2(probe, probe_root / "__init__.py")

    mismatches = []
    for name, expected in members.items():
        actual = sha256_file(candidate_root.joinpath(*PurePosixPath(name).parts))
        if actual != expected:
            mismatches.append(name)
    if mismatches:
        raise RuntimeError("installed archive payload mismatch: {}".format(mismatches))

    report = {
        "run_root": str(root),
        "archive": str(archive),
        "archive_sha256": sha256_file(archive),
        "archive_file_count": len(members),
        "candidate": str(candidate_root),
        "candidate_payload_matches_archive": True,
        "probe": str(probe_root / "__init__.py"),
        "probe_sha256": sha256_file(probe_root / "__init__.py"),
        "ui_scale_percent": 100,
        "sync_boundary": "disabled-and-disconnected disposable profile",
    }
    report_path = root / "hdo-contact-sheet-fixture.json"
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True, type=Path)
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--probe", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(prepare(args.run_root, args.archive, args.probe), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
