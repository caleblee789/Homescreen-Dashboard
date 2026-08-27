#!/usr/bin/env python3
"""Load and validate the declarative Home Dashboard capture plan.

The plan is intentionally free of Anki and Qt imports so the same ordered case
registry can drive helper preparation, the native runtime probe, evidence
assembly, and offline contract tests.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import date
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from typing import Any, Iterable, Mapping, Sequence


CASE_ID_RE = re.compile(r"^[A-Z0-9]+(?:-[A-Z0-9]+)*$")
PLAN_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
OUTPUT_DIRECTORY_RE = re.compile(r"^[a-z0-9][a-z0-9.-]*$")
STAGES = ("initial", "restart")
COMPONENTS = ("production", "settings")
SEMANTIC_CAPTURE_FIELDS = (
    "anki_theme",
    "host_platform",
    "os_scale_percent",
    "dpr_class",
)
REQUIRED_NATIVE_PLATFORM_PROFILES = (
    ("windows", 100, "dpr-1"),
    ("windows", 125, "native"),
    ("windows", 150, "native"),
    ("linux", 100, "dpr-1"),
    ("linux", 150, "native"),
    ("macos", 100, "retina"),
)


class CapturePlanError(ValueError):
    """Raised when a capture plan is ambiguous or internally inconsistent."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CapturePlanError(message)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CapturePlanError("could not read capture plan {}: {}".format(path, exc)) from exc
    _require(isinstance(value, dict), "{} must contain a JSON object".format(path))
    return value


def _slug_id(value: object) -> str:
    return re.sub(r"[^A-Z0-9]+", "-", str(value).upper()).strip("-")


def default_plan_path(module_path: Path | None = None) -> Path:
    """Resolve the source plan or the renamed copy inside a helper add-on."""

    root = (module_path or Path(__file__)).resolve().parent
    candidates = (root / "_capture_plan.json", root / "capture_plan.json")
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise CapturePlanError(
        "capture plan is missing; expected {}".format(
            " or ".join(str(candidate) for candidate in candidates)
        )
    )


class CapturePlan:
    """Expanded, ordered capture cases plus named selection profiles."""

    def __init__(self, path: Path, raw: Mapping[str, Any]) -> None:
        self.path = path.resolve()
        self.raw = deepcopy(dict(raw))
        self.schema_version = int(self.raw.get("schema_version", 0))
        self.release = str(self.raw.get("release", ""))
        self.reference_date = str(self.raw.get("reference_date", ""))
        self.sha256 = hashlib.sha256(self.path.read_bytes()).hexdigest()
        self._family_specs = self._indexed_objects("families")
        self._profile_specs = self._indexed_objects("profiles")
        presentation = self.raw.get("presentation")
        _require(isinstance(presentation, Mapping), "capture plan presentation must be an object")
        groups = presentation.get("sheet_groups")
        _require(isinstance(groups, list) and groups, "capture plan must define sheet groups")
        report = presentation.get("report")
        _require(isinstance(report, Mapping), "capture plan presentation must define a report sheet")
        _require(
            bool(str(report.get("id", "")).strip()) and bool(str(report.get("title", "")).strip()),
            "capture plan report sheet needs an id and title",
        )
        _require(
            bool(PLAN_ID_RE.fullmatch(str(report["id"]))),
            "capture plan report sheet id is unsafe",
        )
        self.presentation = deepcopy(dict(presentation))
        self._group_specs = self._index_named_list(groups, "sheet group")
        _require(
            str(report["id"]) not in self._group_specs,
            "report sheet id duplicates a capture sheet group",
        )
        self._cases = self._expand_cases()
        self._validate()

    def _index_named_list(
        self,
        values: Sequence[object],
        label: str,
    ) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        for raw in values:
            _require(isinstance(raw, Mapping), "{} entries must be objects".format(label))
            value = deepcopy(dict(raw))
            item_id = str(value.get("id", "")).strip()
            _require(item_id, "{} entry has no id".format(label))
            _require(item_id not in result, "duplicate {} id: {}".format(label, item_id))
            result[item_id] = value
        return result

    def _indexed_objects(self, key: str) -> dict[str, dict[str, Any]]:
        values = self.raw.get(key)
        _require(isinstance(values, list) and values, "capture plan {} must be a non-empty list".format(key))
        return self._index_named_list(values, key[:-1])

    def _merged_case(
        self,
        family: Mapping[str, Any],
        values: Mapping[str, Any],
    ) -> dict[str, Any]:
        defaults = family.get("defaults", {})
        _require(isinstance(defaults, Mapping), "family defaults must be an object")
        case = deepcopy(dict(defaults))
        case.update(deepcopy(dict(values)))
        case["family"] = str(family["id"])
        case["stage"] = str(family["stage"])
        if "component" not in case:
            case["component"] = str(family.get("component", ""))
        if case["component"] == "production":
            case.setdefault("selected", self.reference_date)
        return case

    def _expand_palette_axes(self, family: Mapping[str, Any]) -> list[dict[str, Any]]:
        themes = family.get("themes")
        modes = family.get("modes")
        _require(isinstance(themes, list) and themes, "palette family has no themes")
        _require(isinstance(modes, list) and modes, "palette family has no modes")
        result: list[dict[str, Any]] = []
        for raw_theme in themes:
            _require(isinstance(raw_theme, Mapping), "palette theme must be an object")
            palettes = raw_theme.get("palettes")
            _require(isinstance(palettes, list) and palettes, "palette theme has no palettes")
            for palette in palettes:
                for raw_mode in modes:
                    _require(isinstance(raw_mode, Mapping), "palette mode must be an object")
                    result.append(self._merged_case(family, {
                        "id": "PROD-PAL-{}-{}-{}".format(
                            raw_theme.get("id"), _slug_id(palette), raw_mode.get("id")
                        ),
                        "theme": str(raw_theme.get("name", "")),
                        "palette": str(palette),
                        "mode": str(raw_mode.get("name", "")),
                        "sheet_group": str(raw_theme.get("sheet_group", "")),
                    }))
        return result

    def _expand_settings_page_axes(self, family: Mapping[str, Any]) -> list[dict[str, Any]]:
        pages = family.get("pages")
        widths = family.get("widths")
        fonts = family.get("font_percents")
        _require(isinstance(pages, list) and pages, "Settings page family has no pages")
        _require(isinstance(widths, list) and widths, "Settings page family has no widths")
        _require(isinstance(fonts, list) and fonts, "Settings page family has no font percentages")
        large_group = str(family.get("large_font_sheet_group", ""))
        result: list[dict[str, Any]] = []
        for raw_page in pages:
            _require(isinstance(raw_page, Mapping), "Settings page axis must be an object")
            for raw_width in widths:
                _require(isinstance(raw_width, Mapping), "Settings width axis must be an object")
                for raw_font in fonts:
                    font_percent = int(raw_font)
                    result.append(self._merged_case(family, {
                        "id": "SET-PAGE-{}-{}-{}".format(
                            raw_page.get("id"), raw_width.get("id"), font_percent
                        ),
                        "page": str(raw_page.get("page", "")),
                        "width": raw_width.get("value"),
                        "font_percent": font_percent,
                        "special": "page-axis",
                        "sheet_group": (
                            large_group
                            if font_percent > 100
                            else str(raw_page.get("sheet_group", ""))
                        ),
                    }))
        return result

    def _expand_cases(self) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for family in self._family_specs.values():
            generator = str(family.get("generator", ""))
            if generator == "palette-axes":
                result.extend(self._expand_palette_axes(family))
                continue
            if generator == "settings-page-axes":
                result.extend(self._expand_settings_page_axes(family))
                continue
            _require(not generator, "unknown family generator: {}".format(generator))
            raw_cases = family.get("cases")
            _require(isinstance(raw_cases, list) and raw_cases, "family {} has no cases".format(family["id"]))
            for raw_case in raw_cases:
                _require(isinstance(raw_case, Mapping), "family case must be an object")
                result.append(self._merged_case(family, raw_case))
        return result

    def _validate(self) -> None:
        _require(self.schema_version == 1, "unsupported capture plan schema")
        _require(bool(re.fullmatch(r"\d+\.\d+\.\d+", self.release)), "capture plan release is invalid")
        try:
            date.fromisoformat(self.reference_date)
        except ValueError as exc:
            raise CapturePlanError("capture plan reference date is invalid") from exc
        for family_id in self._family_specs:
            _require(bool(PLAN_ID_RE.fullmatch(family_id)), "invalid capture family id: {}".format(family_id))
        for profile_id in self._profile_specs:
            _require(bool(PLAN_ID_RE.fullmatch(profile_id)), "invalid capture profile id: {}".format(profile_id))
        overview = self.presentation.get("overview")
        detail_defaults = self.presentation.get("detail_defaults")
        _require(isinstance(overview, Mapping), "capture plan overview must be an object")
        _require(isinstance(detail_defaults, Mapping), "capture plan detail defaults must be an object")
        _require(bool(str(overview.get("title", "")).strip()), "capture plan overview has no title")
        for label, geometry in (("overview", overview), ("detail defaults", detail_defaults)):
            thumbnail = geometry.get("thumbnail")
            _require(
                isinstance(geometry.get("columns"), int) and geometry["columns"] > 0,
                "{} columns must be a positive integer".format(label),
            )
            _require(
                isinstance(thumbnail, list)
                and len(thumbnail) == 2
                and all(isinstance(value, int) and value > 0 for value in thumbnail),
                "{} thumbnail must contain two positive integers".format(label),
            )
        for group_id, group in self._group_specs.items():
            _require(bool(PLAN_ID_RE.fullmatch(group_id)), "invalid sheet group id: {}".format(group_id))
            _require(bool(str(group.get("title", "")).strip()), "sheet group {} has no title".format(group_id))
            resolved_geometry = dict(detail_defaults)
            resolved_geometry.update(group)
            thumbnail = resolved_geometry.get("thumbnail")
            _require(
                isinstance(resolved_geometry.get("columns"), int)
                and resolved_geometry["columns"] > 0,
                "sheet group {} columns must be a positive integer".format(group_id),
            )
            _require(
                isinstance(thumbnail, list)
                and len(thumbnail) == 2
                and all(isinstance(value, int) and value > 0 for value in thumbnail),
                "sheet group {} thumbnail must contain two positive integers".format(group_id),
            )
        case_ids: list[str] = []
        for case in self._cases:
            case_id = str(case.get("id", ""))
            _require(bool(CASE_ID_RE.fullmatch(case_id)), "invalid capture id: {}".format(case_id))
            _require(case.get("stage") in STAGES, "{} has an invalid stage".format(case_id))
            _require(case.get("component") in COMPONENTS, "{} has an invalid component".format(case_id))
            for field in SEMANTIC_CAPTURE_FIELDS:
                _require(
                    field in case and case[field] not in (None, ""),
                    "{} has no semantic {} field".format(case_id, field),
                )
            _require(
                isinstance(case.get("os_scale_percent"), int)
                and int(case["os_scale_percent"]) > 0,
                "{} has an invalid OS scale".format(case_id),
            )
            if case.get("component") == "production":
                try:
                    date.fromisoformat(str(case.get("selected", "")))
                except ValueError as exc:
                    raise CapturePlanError(
                        "{} has an invalid selected date".format(case_id)
                    ) from exc
            group = str(case.get("sheet_group", ""))
            _require(group in self._group_specs, "{} has an unknown sheet group: {}".format(case_id, group))
            case_ids.append(case_id)
        _require(len(case_ids) == len(set(case_ids)), "capture plan contains duplicate capture ids")

        platform_matrix = self.raw.get("native_platform_matrix")
        _require(
            isinstance(platform_matrix, list),
            "capture plan native_platform_matrix must be a list",
        )
        resolved_platforms: list[tuple[str, int, str]] = []
        for entry in platform_matrix:
            _require(isinstance(entry, Mapping), "native platform entries must be objects")
            resolved_platforms.append((
                str(entry.get("host_platform", "")),
                int(entry.get("os_scale_percent", 0)),
                str(entry.get("dpr_class", "")),
            ))
        _require(
            tuple(resolved_platforms) == REQUIRED_NATIVE_PLATFORM_PROFILES,
            "native platform matrix differs from the release-blocking contract",
        )
        _require(
            len(resolved_platforms) == len(set(resolved_platforms)),
            "native platform matrix contains duplicate profiles",
        )

        all_families = set(self._family_specs)
        all_components = set(COMPONENTS)
        for profile_id, profile in self._profile_specs.items():
            families = profile.get("families")
            components = profile.get("components")
            _require(isinstance(families, list) and families, "profile {} has no families".format(profile_id))
            _require(isinstance(components, list) and components, "profile {} has no components".format(profile_id))
            _require(set(families) <= all_families, "profile {} names an unknown family".format(profile_id))
            _require(set(components) <= all_components, "profile {} names an unknown component".format(profile_id))
            output_directory = str(profile.get("output_directory", ""))
            _require(
                bool(OUTPUT_DIRECTORY_RE.fullmatch(output_directory)) and ".." not in output_directory,
                "profile {} has an unsafe output directory".format(profile_id),
            )
            filters = profile.get("family_filters", {})
            _require(isinstance(filters, Mapping), "profile filters must be an object")
            _require(set(filters) <= set(families), "profile {} filters an excluded family".format(profile_id))
            for family_id, fields in filters.items():
                _require(isinstance(fields, Mapping), "{} profile filter must be an object".format(family_id))
                family_cases = [case for case in self._cases if case["family"] == family_id]
                for key, allowed in fields.items():
                    _require(isinstance(allowed, list) and allowed, "{} filter {} must be a list".format(family_id, key))
                    _require(
                        all(key in case for case in family_cases),
                        "{} filter names an undefined field: {}".format(family_id, key),
                    )
                    _require(
                        all(any(value == case.get(key) for case in family_cases) for value in allowed),
                        "{} filter {} contains a value absent from the family".format(family_id, key),
                    )
            overrides = profile.get("component_overrides", {})
            _require(isinstance(overrides, Mapping), "profile overrides must be an object")
            _require(set(overrides) <= set(components), "profile {} overrides an excluded component".format(profile_id))
            for component_id, fields in overrides.items():
                _require(isinstance(fields, Mapping), "{} component override must be an object".format(component_id))
                protected = {"id", "family", "stage", "component", "sheet_group"}
                _require(
                    not (set(fields) & protected),
                    "{} component override changes capture identity or ownership".format(component_id),
                )
            selected = self.cases(profile_id)
            _require(bool(selected), "profile {} selects no capture cases".format(profile_id))
            for stage in STAGES:
                _require(
                    any(case["stage"] == stage for case in selected),
                    "profile {} has no {} captures".format(profile_id, stage),
                )
            expected_counts = profile.get("expected_capture_counts")
            if expected_counts is not None:
                _require(
                    isinstance(expected_counts, Mapping)
                    and dict(expected_counts) == self.counts(profile_id),
                    "profile {} capture ceiling differs from its selected cases".format(
                        profile_id
                    ),
                )
            required_font_percent = profile.get(
                "required_application_font_percent"
            )
            if required_font_percent is not None:
                _require(
                    all(
                        case.get("font_percent") == required_font_percent
                        for case in selected
                        if case["component"] == "settings"
                    ),
                    "profile {} contains an alternate application-font capture".format(
                        profile_id
                    ),
                )
            maximum_sheets = profile.get("maximum_contact_sheets")
            if maximum_sheets is not None:
                planned_sheet_count = 2 + len(self.detail_groups(profile_id))
                _require(
                    isinstance(maximum_sheets, int)
                    and maximum_sheets > 0
                    and planned_sheet_count <= maximum_sheets,
                    "profile {} exceeds its contact-sheet ceiling".format(profile_id),
                )
            manual_results = profile.get("required_structured_manual_results", [])
            _require(
                isinstance(manual_results, list)
                and all(
                    isinstance(result_id, str)
                    and bool(PLAN_ID_RE.fullmatch(result_id))
                    for result_id in manual_results
                )
                and len(manual_results) == len(set(manual_results)),
                "profile {} has invalid structured manual-result requirements".format(
                    profile_id
                ),
            )

        _require("full" in self._profile_specs, "capture plan requires a full profile")
        _require(
            self.ids("full") == tuple(case_ids),
            "full profile must preserve every declared case in contract order",
        )
        _require(
            {str(case["sheet_group"]) for case in self._cases} == set(self._group_specs),
            "full profile has unused or missing presentation groups",
        )
        for profile_id in self.profile_ids:
            grouped = [case_id for group in self.detail_groups(profile_id) for case_id in group["capture_ids"]]
            expected = list(self.ids(profile_id))
            _require(len(grouped) == len(set(grouped)), "{} profile has duplicate sheet coverage".format(profile_id))
            _require(set(grouped) == set(expected), "{} profile has incomplete sheet coverage".format(profile_id))

    @property
    def profile_ids(self) -> tuple[str, ...]:
        return tuple(self._profile_specs)

    def profile(self, profile_id: str) -> dict[str, Any]:
        try:
            return deepcopy(self._profile_specs[profile_id])
        except KeyError as exc:
            raise CapturePlanError("unknown capture profile: {}".format(profile_id)) from exc

    def cases(
        self,
        profile_id: str = "full",
        *,
        stage: str | None = None,
        component: str | None = None,
        include_ids: Iterable[str] | None = None,
    ) -> list[dict[str, Any]]:
        profile = self._profile_specs.get(profile_id)
        _require(profile is not None, "unknown capture profile: {}".format(profile_id))
        if stage is not None:
            _require(stage in STAGES, "unknown capture stage: {}".format(stage))
        if component is not None:
            _require(component in COMPONENTS, "unknown capture component: {}".format(component))
        families = set(str(value) for value in profile["families"])
        components = set(str(value) for value in profile["components"])
        filters = profile.get("family_filters", {})
        overrides = profile.get("component_overrides", {})
        requested: tuple[str, ...] | None = None
        requested_set: set[str] | None = None
        if include_ids is not None:
            requested = tuple(dict.fromkeys(str(value) for value in include_ids))
            _require(bool(requested), "capture selection must not be empty")
            available = {
                str(original["id"])
                for original in self._cases
                if original["family"] in families
                and original["component"] in components
                and not any(
                    original.get(key) not in allowed
                    for key, allowed in filters.get(original["family"], {}).items()
                )
            }
            unknown = [case_id for case_id in requested if case_id not in available]
            _require(not unknown, "capture selection is outside profile {}: {}".format(profile_id, ", ".join(unknown)))
            requested_set = set(requested)
        selected: list[dict[str, Any]] = []
        for original in self._cases:
            if original["family"] not in families or original["component"] not in components:
                continue
            if stage is not None and original["stage"] != stage:
                continue
            if component is not None and original["component"] != component:
                continue
            family_filters = filters.get(original["family"], {})
            if any(original.get(key) not in allowed for key, allowed in family_filters.items()):
                continue
            if requested_set is not None and original["id"] not in requested_set:
                continue
            case = deepcopy(original)
            component_override = overrides.get(case["component"], {})
            _require(isinstance(component_override, Mapping), "component override must be an object")
            case.update(deepcopy(dict(component_override)))
            selected.append(case)

        return selected

    def ids(
        self,
        profile_id: str = "full",
        *,
        stage: str | None = None,
        component: str | None = None,
        include_ids: Iterable[str] | None = None,
    ) -> tuple[str, ...]:
        return tuple(
            str(case["id"])
            for case in self.cases(
                profile_id,
                stage=stage,
                component=component,
                include_ids=include_ids,
            )
        )

    def counts(
        self,
        profile_id: str = "full",
        *,
        include_ids: Iterable[str] | None = None,
    ) -> dict[str, int]:
        cases = self.cases(profile_id, include_ids=include_ids)
        result = {stage: sum(case["stage"] == stage for case in cases) for stage in STAGES}
        result["total"] = len(cases)
        return result

    def family_ids(self, family_id: str) -> tuple[str, ...]:
        _require(family_id in self._family_specs, "unknown capture family: {}".format(family_id))
        return tuple(str(case["id"]) for case in self._cases if case["family"] == family_id)

    def tagged_ids(
        self,
        tag: str,
        profile_id: str = "full",
        *,
        stage: str | None = None,
    ) -> tuple[str, ...]:
        return tuple(
            str(case["id"])
            for case in self.cases(profile_id, stage=stage)
            if tag in case.get("tags", [])
        )

    def detail_groups(
        self,
        profile_id: str = "full",
        *,
        include_ids: Iterable[str] | None = None,
    ) -> list[dict[str, Any]]:
        cases = self.cases(profile_id, include_ids=include_ids)
        ids_by_group: dict[str, list[str]] = {group_id: [] for group_id in self._group_specs}
        for case in cases:
            ids_by_group[str(case["sheet_group"])].append(str(case["id"]))
        defaults = self.presentation.get("detail_defaults", {})
        _require(isinstance(defaults, Mapping), "detail presentation defaults must be an object")
        result: list[dict[str, Any]] = []
        for group_id, spec in self._group_specs.items():
            capture_ids = ids_by_group[group_id]
            if not capture_ids:
                continue
            group = deepcopy(dict(defaults))
            group.update(deepcopy(spec))
            group["capture_ids"] = capture_ids
            result.append(group)
        return result

    def validate_authorities(self, qa_root: Path | None = None) -> dict[str, Any]:
        root = (qa_root or self.path.parent).resolve()
        authorities = self.raw.get("authority_files")
        _require(isinstance(authorities, Mapping), "capture plan authority_files must be an object")
        _require(
            set(authorities) == {"surface_manifest", "visual_matrix", "evidence_contract"},
            "capture plan authority_files must name the surface, visual, and evidence contracts",
        )
        loaded = {name: _read_json(root / str(relative)) for name, relative in authorities.items()}
        _require(all(value.get("release") == self.release for value in loaded.values()), "capture authorities use different releases")
        matrix = loaded.get("visual_matrix", {})
        contract = loaded.get("evidence_contract", {})
        surface = loaded.get("surface_manifest", {})
        _require(
            contract.get("authority") == "qa/{}".format(authorities["surface_manifest"])
            and contract.get("visual_matrix") == "qa/{}".format(authorities["visual_matrix"])
            and contract.get("execution_plan") == "qa/capture_plan.json",
            "capture evidence authority links differ from the execution plan",
        )
        _require(
            surface.get("visual_matrix") == "qa/{}".format(authorities["visual_matrix"])
            and surface.get("capture_manifest") == "qa/{}".format(authorities["evidence_contract"]),
            "surface authority links differ from the execution plan",
        )
        contract_families = {
            str(item.get("id")): item
            for item in contract.get("capture_families", [])
            if isinstance(item, Mapping)
        }
        _require(set(contract_families) == set(self._family_specs), "capture family sets differ between plan and evidence contract")
        for family_id in self._family_specs:
            planned_ids = self.family_ids(family_id)
            declared = contract_families[family_id]
            _require(declared.get("count") == len(planned_ids), "{} family count drifted".format(family_id))
            explicit = declared.get("capture_ids")
            if explicit is not None:
                _require(tuple(str(value) for value in explicit) == planned_ids, "{} capture ids drifted".format(family_id))
        matrix_palettes = tuple(
            (
                str(item.get("id")),
                str(item.get("theme")),
                str(item.get("palette")),
                str(item.get("mode")),
                str(item.get("view")),
            )
            for item in matrix.get("palette_cases", [])
            if isinstance(item, Mapping)
        )
        planned_palettes = tuple(
            (
                str(item["id"]),
                str(item["theme"]),
                str(item["palette"]),
                str(item["mode"]),
                str(item["view"]),
            )
            for item in self._cases
            if item["family"] == "production-palettes"
        )
        _require(
            matrix_palettes == planned_palettes,
            "palette matrix order or semantics differ from the capture plan",
        )
        _require(
            tuple(str(item.get("id")) for item in matrix.get("view_cases", []))
            == self.tagged_ids("stable_width_switching", "full", stage="initial"),
            "stable view matrix differs from the capture plan",
        )
        _require(
            tuple(str(item.get("id")) for item in matrix.get("statistics_accuracy_cases", []))
            == self.family_ids("statistics-accuracy"),
            "statistics matrix differs from the capture plan",
        )
        settings_axes = matrix.get("settings_page_axes", {})
        settings_family = self._family_specs.get("settings-pages", {})
        planned_settings_axes = {
            "page": [str(item.get("page")) for item in settings_family.get("pages", [])],
            "window_width": [
                "full-screen" if item.get("value") == "full" else item.get("value")
                for item in settings_family.get("widths", [])
            ],
            "application_font_percent": [
                int(value) for value in settings_family.get("font_percents", [])
            ],
        }
        _require(
            isinstance(settings_axes, Mapping)
            and all(settings_axes.get(key) == value for key, value in planned_settings_axes.items())
            and matrix.get("settings_page_case_count")
            == len(self.family_ids("settings-pages")),
            "Settings page axes differ from the capture plan",
        )
        planned_platforms = self.raw.get("native_platform_matrix")
        _require(
            matrix.get("required_native_platform_profiles") == planned_platforms
            and contract.get("required_native_platform_profiles") == planned_platforms,
            "native platform requirements differ from the capture plan",
        )
        settings_manual_results = tuple(
            str(value)
            for value in self._profile_specs.get("settings", {}).get(
                "required_structured_manual_results", ()
            )
        )
        settings_manual_gate = contract.get("settings_profile_structured_manual_gate")
        _require(
            isinstance(settings_manual_gate, Mapping)
            and settings_manual_gate.get("required_for_acceptance") is True
            and settings_manual_gate.get("adds_png_frames") is False
            and settings_manual_results == (str(settings_manual_gate.get("id", "")),),
            "Settings structured manual acceptance gate differs from the capture plan",
        )
        derived = contract.get("derived_native_frame_count", {})
        full_counts = self.counts("full")
        _require(
            isinstance(derived, Mapping)
            and all(derived.get(key) == value for key, value in full_counts.items()),
            "derived full capture counts differ from the execution plan",
        )
        contact_output = contract.get("contact_sheet_output", {})
        report_id = str(self.presentation["report"]["id"])
        planned_sheet_groups = tuple(self._group_specs) + (report_id,)
        _require(
            isinstance(contact_output, Mapping)
            and contact_output.get("overview_count") == 1
            and tuple(str(value) for value in contact_output.get("detail_groups", ()))
            == planned_sheet_groups
            and contact_output.get("detail_sheet_count") == len(planned_sheet_groups),
            "contact-sheet presentation differs from the execution plan",
        )
        return {
            "status": "passed",
            "release": self.release,
            "plan_sha256": self.sha256,
            "profiles": {profile_id: self.counts(profile_id) for profile_id in self.profile_ids},
            "required_structured_manual_results": {
                profile_id: list(
                    self._profile_specs[profile_id].get(
                        "required_structured_manual_results", ()
                    )
                )
                for profile_id in self.profile_ids
            },
            "authority_files": {name: str(value) for name, value in authorities.items()},
        }


def load_capture_plan(path: Path | str | None = None) -> CapturePlan:
    resolved = Path(path) if path is not None else default_plan_path()
    return CapturePlan(resolved, _read_json(resolved))


def load_profile_request(
    module_path: Path | None = None,
    *,
    plan: CapturePlan | None = None,
) -> dict[str, Any]:
    """Load helper-bundled profile/selection metadata, with an env fallback."""

    root = (module_path or Path(__file__)).resolve().parent
    packaged = root / "_capture_profile.json"
    if packaged.is_file():
        value = _read_json(packaged)
    else:
        value = {"id": os.environ.get("HDO_CAPTURE_PROFILE", "full")}
    profile_id = str(value.get("id", "")).strip()
    _require(profile_id, "capture profile request has no id")
    include_ids = value.get("include_ids")
    _require(include_ids is None or isinstance(include_ids, list), "capture profile include_ids must be a list")
    if include_ids is not None:
        _require(bool(include_ids), "capture profile include_ids must not be empty")
        _require(
            all(isinstance(item, str) and item.strip() for item in include_ids),
            "capture profile include_ids must contain non-empty strings",
        )
        _require(
            len(include_ids) == len(set(include_ids)),
            "capture profile include_ids must be unique",
        )
    if plan is not None:
        requested_release = value.get("release")
        requested_hash = value.get("plan_sha256")
        _require(
            requested_release is None or requested_release == plan.release,
            "capture profile release differs from its bundled plan",
        )
        _require(
            requested_hash is None or requested_hash == plan.sha256,
            "capture profile hash differs from its bundled plan",
        )
        plan.cases(profile_id, include_ids=include_ids)
    return value


def _main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=None)
    parser.add_argument("--profile", default="full")
    parser.add_argument("--stage", choices=STAGES)
    parser.add_argument("--list-ids", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        plan = load_capture_plan(args.plan)
        authority = plan.validate_authorities()
        ids = plan.ids(args.profile, stage=args.stage)
        summary = {
            "status": "passed",
            "release": plan.release,
            "profile": args.profile,
            "counts": plan.counts(args.profile),
            "selected_count": len(ids),
            "plan_sha256": plan.sha256,
            "authority": authority,
        }
    except Exception as exc:
        print("ERROR: {}: {}".format(type(exc).__name__, exc), file=sys.stderr)
        return 1
    if args.json:
        if args.list_ids:
            summary["capture_ids"] = list(ids)
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(
            "Capture plan: PASS (release {}, profile {}, {} selected, {} initial + {} restart)".format(
                plan.release,
                args.profile,
                len(ids),
                summary["counts"]["initial"],
                summary["counts"]["restart"],
            )
        )
        if args.list_ids:
            print("\n".join(ids))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
