#!/usr/bin/env python3
"""Build a deterministic disposable-Anki capture helper from one plan profile."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
from typing import Any, Sequence

from capture_plan import CapturePlanError, load_capture_plan


QA_ROOT = Path(__file__).resolve().parent
PLAN_PATH = QA_ROOT / "capture_plan.json"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _selection_from_file(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.casefold() == ".json":
        value = json.loads(text)
        if not isinstance(value, list):
            raise CapturePlanError("selection JSON must contain a list of capture IDs")
        return [str(item) for item in value]
    return [line.strip() for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")]


def prepare_helper(
    output: Path,
    *,
    profile_id: str,
    include_ids: Sequence[str] | None = None,
) -> Path:
    plan = load_capture_plan(PLAN_PATH)
    plan.validate_authorities(QA_ROOT)
    selected = plan.cases(profile_id, include_ids=include_ids)
    counts = plan.counts(profile_id, include_ids=include_ids)
    if include_ids is not None and counts["restart"] and not counts["initial"]:
        raise CapturePlanError("restart-only helpers are unsafe because no initial fixture/persistence stage is prepared")
    output = output.resolve()
    if output.exists():
        raise FileExistsError("refusing to overwrite capture helper: {}".format(output))
    output.mkdir(parents=True)
    try:
        sources = {
            "__init__.py": QA_ROOT / "runtime_probe_profile_entrypoint.py",
            "_release_probe.py": QA_ROOT / "runtime_probe_release_1_8_7.py",
            "_probe_base.py": QA_ROOT / "runtime_probe_release_1_8_4.py",
            "_workflow_probe.py": QA_ROOT / "runtime_probe_settings_workflow_1_8_7.py",
            "_capture_plan.py": QA_ROOT / "capture_plan.py",
            "_capture_plan.json": PLAN_PATH,
        }
        profile = plan.profile(profile_id)
        if bool(profile.get("full_screen")):
            sources["_fullscreen_profile.py"] = QA_ROOT / "runtime_probe_fullscreen_profile.py"
        missing = [str(path) for path in sources.values() if not path.is_file()]
        if missing:
            raise FileNotFoundError("capture helper sources are missing: {}".format(", ".join(missing)))
        for destination, source in sources.items():
            shutil.copyfile(source, output / destination)

        canonical_ids = [str(case["id"]) for case in selected]
        request: dict[str, Any] = {
            "schema_version": 1,
            "id": profile_id,
            "release": plan.release,
            "plan_sha256": plan.sha256,
        }
        if include_ids is not None:
            request["include_ids"] = canonical_ids
        _write_json(output / "_capture_profile.json", request)

        package_slug = re.sub(r"[^a-z0-9]+", "_", profile_id.casefold()).strip("_")
        manifest = {
            "name": "Home Dashboard {} {} capture probe".format(plan.release, profile_id),
            "package": "zz_hdo_{}_{}_probe".format(plan.release.replace(".", "_"), package_slug),
            "ankiweb_id": "",
            "homepage": "",
            "conflicts": [],
            "candidate_package": "home_dashboard_overhaul",
            "schema_version": 1,
            "capture_profile": profile_id,
            "capture_plan_sha256": plan.sha256,
            "expected_capture_counts": counts,
            "expected_capture_count": counts["total"],
            "stages": [stage for stage in ("initial", "restart") if counts[stage]],
            "selected_capture_ids": canonical_ids,
            "required_structured_manual_results": list(
                profile.get("required_structured_manual_results", ())
            ),
            "helper_files": {
                name: {"sha256": _sha256(output / name), "source": source.name}
                for name, source in sources.items()
            },
        }
        _write_json(output / "manifest.json", manifest)
    except Exception:
        shutil.rmtree(output, ignore_errors=True)
        raise
    return output


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--profile", default="full")
    parser.add_argument(
        "--only",
        action="append",
        default=[],
        metavar="CAPTURE_ID",
        help="Build a focused helper; repeat for each capture ID.",
    )
    parser.add_argument("--only-file", type=Path, help="Newline or JSON-list capture selection.")
    args = parser.parse_args(argv)
    try:
        requested = list(args.only)
        if args.only_file is not None:
            requested.extend(_selection_from_file(args.only_file))
        include_ids = tuple(dict.fromkeys(requested)) if requested else None
        output = prepare_helper(
            args.output,
            profile_id=args.profile,
            include_ids=include_ids,
        )
        manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    except Exception as exc:
        print("ERROR: {}: {}".format(type(exc).__name__, exc), file=sys.stderr)
        return 1
    print(
        "{} ({} captures: {} initial + {} restart)".format(
            output,
            manifest["expected_capture_count"],
            manifest["expected_capture_counts"]["initial"],
            manifest["expected_capture_counts"]["restart"],
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
