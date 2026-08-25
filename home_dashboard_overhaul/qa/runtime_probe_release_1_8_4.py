"""Fail-closed native Deck Browser evidence probe for release 1.8.4.

This module is installed only into a helper add-on directory in a disposable,
sync-disabled Anki base.  It never opens a preview web view: every frame is the
isolated process's real main Deck Browser, mounted through the exact production
controller and renderer from the installed candidate archive.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import date
import hashlib
import json
import os
from pathlib import Path
import traceback
from typing import Any, Dict, Iterable, Mapping
import zipfile

import anki
import home_dashboard_overhaul
from anki.collection import AddNoteRequest
from aqt import gui_hooks, mw
from aqt.qt import QApplication, QTimer

from home_dashboard_overhaul.analytics import (
    collect_snapshot,
    representative_preview_snapshot,
    unavailable_snapshot,
)
from home_dashboard_overhaul.config_schema import normalize_config
from home_dashboard_overhaul.renderer import _progress_presentation
from home_dashboard_overhaul.models import (
    AvailabilityReason,
    BrowseTarget,
    BrowseTargetKind,
    BuriedStats,
    DashboardSnapshot,
    DayDomainState,
    DayFacts,
    DayRelation,
    EventItem,
    LastSevenDaysStats,
    LongTermStats,
    QueueStats,
    RateMetric,
    TodayStats,
    ValueState,
    VerseContent,
)


RELEASE = "1.8.4"
REFERENCE_DATE = "2026-08-23"
QA_HEAD_A = "HDO 1.8.4 QA Head A"
QA_HEAD_B = "HDO 1.8.4 QA Head B"
QA_CONFIG_A = "HDO 1.8.4 QA Limit 3"
QA_CONFIG_B = "HDO 1.8.4 QA Limit 7"
QA_RAW_NEW_PER_HEAD = 40
RUN_ROOT = Path(os.environ.get("HDO_RELEASE_RUN_ROOT", ""))
EXPECTED_PROFILE = os.environ.get("HDO_RELEASE_PROFILE", "")
EXPECTED_SHA256 = os.environ.get("HDO_RELEASE_CANDIDATE_SHA256", "")
EXPECTED_INSTANCE_KEY = os.environ.get("HDO_RELEASE_INSTANCE_KEY", "")
EXPECTED_NORMAL_PID = int(os.environ.get("HDO_RELEASE_EXCLUDED_PID", "0") or 0)
EXPECTED_CAPTURE_SCREEN = os.environ.get("HDO_RELEASE_CAPTURE_SCREEN", "").strip()
STAGE = os.environ.get("HDO_RELEASE_PROBE_STAGE", "initial")
RESTART_PRE_FIXTURE_EXPECTED_NEW = 10
RESTART_MULTI_DECK_EXPECTED_TOTAL = 10
OUTPUT_ROOT = RUN_ROOT / "hdo-release-evidence-1.8.4"
CAPTURE_ROOT = OUTPUT_ROOT / "captures"
REPORT_PATH = OUTPUT_ROOT / ("runtime-report-{}.json".format(STAGE))
RUN_MARKER = RUN_ROOT / "QA_IDENTITY.json"
ADDON_ROOT = Path(home_dashboard_overhaul.__file__).resolve().parent
PROBE_ROOT = Path(__file__).resolve().parent

ENABLED = (
    str(RUN_ROOT).startswith("/private/tmp/anki-release-qa.")
    and EXPECTED_PROFILE.startswith("Codex QA HDO 1.8.4 ")
    and len(EXPECTED_SHA256) == 64
    and len(EXPECTED_INSTANCE_KEY) >= 24
    and STAGE in {"initial", "restart"}
)

REPORT: Dict[str, Any] = {
    "schema_version": 2,
    "release": RELEASE,
    "stage": STAGE,
    "status": "running",
    "authority": "native-deck-browser-100-percent",
    "errors": [],
    "captures": {},
    "scale_policy": {
        "ui_scale_percent": 100,
        "text_scale_percent": 100,
        "deferred_ui_scales_percent": [125, 150],
    },
}

_started = False
_controller: Any = None
_live_snapshot: DashboardSnapshot | None = None
_cases: list[dict[str, Any]] = []
_case_index = 0
_active_case: dict[str, Any] | None = None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_report() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps(REPORT, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _qa_screen() -> Any:
    if EXPECTED_CAPTURE_SCREEN:
        matches = [screen for screen in QApplication.screens() if screen.name() == EXPECTED_CAPTURE_SCREEN]
        _require(len(matches) == 1, "expected capture screen is unavailable or ambiguous")
        return matches[0]
    screen = mw.screen() or QApplication.primaryScreen()
    _require(screen is not None, "no Qt screen is available")
    return screen


def _error(stage: str, exc: BaseException) -> None:
    REPORT["errors"].append(
        {
            "stage": stage,
            "error": "{}: {}".format(type(exc).__name__, exc),
            "traceback": traceback.format_exc(),
        }
    )
    REPORT["status"] = "failed"
    _write_report()
    QTimer.singleShot(300, QApplication.instance().quit)


def _normal_pid_is_alive() -> bool:
    if EXPECTED_NORMAL_PID <= 1 or EXPECTED_NORMAL_PID == os.getpid():
        return False
    try:
        os.kill(EXPECTED_NORMAL_PID, 0)
        return True
    except OSError:
        return False


def _candidate_install_identity() -> dict[str, Any]:
    marker = json.loads(RUN_MARKER.read_text(encoding="utf-8"))
    candidate = Path(str(marker.get("candidate", ""))).resolve(strict=True)
    archive_sha = _sha256(candidate)
    _require(archive_sha == EXPECTED_SHA256, "candidate archive checksum changed")
    _require(marker.get("candidate_sha256") == EXPECTED_SHA256, "run marker candidate checksum mismatch")
    _require(marker.get("single_instance_key") == EXPECTED_INSTANCE_KEY, "run marker instance key mismatch")
    _require(
        os.environ.get("ANKI_SINGLE_INSTANCE_KEY") == EXPECTED_INSTANCE_KEY,
        "process did not inherit the unique single-instance key",
    )
    compared: list[str] = []
    with zipfile.ZipFile(candidate) as archive:
        members = sorted(info.filename for info in archive.infolist() if not info.is_dir())
        _require(len(members) == 24, "candidate archive member count is not 24")
        for member in members:
            installed = ADDON_ROOT / member
            _require(installed.is_file(), "installed candidate member is missing: {}".format(member))
            _require(
                hashlib.sha256(archive.read(member)).hexdigest() == _sha256(installed),
                "installed candidate member differs from the archive: {}".format(member),
            )
            compared.append(member)
    manifest = json.loads((ADDON_ROOT / "manifest.json").read_text(encoding="utf-8"))
    _require(manifest.get("human_version") == RELEASE, "installed manifest version is not 1.8.4")
    return {
        "candidate": str(candidate),
        "candidate_sha256": archive_sha,
        "member_count": len(compared),
        "installed_member_parity": "passed",
        "manifest_version": manifest.get("human_version"),
    }


def _identity_gate() -> None:
    actual_profile = str(getattr(mw.pm, "name", ""))
    collection_path = Path(str(getattr(mw.col, "path", ""))).resolve(strict=False)
    window_title = str(mw.windowTitle())
    profile_data = getattr(mw.pm, "profile", {}) or {}
    sync_auth_present = bool(
        profile_data.get("syncKey")
        or profile_data.get("sync_key")
        or profile_data.get("syncUser")
        or profile_data.get("sync_user")
    )
    auto_sync = bool(profile_data.get("autoSync", False))
    media_sync = bool(profile_data.get("syncMedia", False))

    _require(actual_profile == EXPECTED_PROFILE, "isolated profile name mismatch")
    _require(
        collection_path.is_relative_to(RUN_ROOT.resolve(strict=True)),
        "collection path escaped the disposable run root",
    )
    _require(ADDON_ROOT.is_relative_to(RUN_ROOT.resolve(strict=True)), "candidate add-on escaped run root")
    _require(PROBE_ROOT.is_relative_to(RUN_ROOT.resolve(strict=True)), "probe add-on escaped run root")
    _require(EXPECTED_PROFILE in window_title, "main window title does not identify the disposable profile")
    _require(not sync_auth_present, "sync credentials are present")
    _require(not auto_sync and not media_sync, "automatic or media sync is enabled")
    normal_process_present = EXPECTED_NORMAL_PID > 1
    if normal_process_present:
        _require(_normal_pid_is_alive(), "excluded normal Anki PID is no longer independently present")
    candidate = _candidate_install_identity()
    REPORT["identity"] = {
        "gated_before_window_interaction": True,
        "pid": os.getpid(),
        "excluded_normal_pid": EXPECTED_NORMAL_PID if normal_process_present else None,
        "excluded_normal_process_state": "alive-and-untouched" if normal_process_present else "none-present-at-prelaunch",
        "excluded_normal_pid_alive": _normal_pid_is_alive() if normal_process_present else False,
        "processes_are_distinct": not normal_process_present or os.getpid() != EXPECTED_NORMAL_PID,
        "run_root": str(RUN_ROOT),
        "profile": actual_profile,
        "profile_matches": True,
        "collection_path": str(collection_path),
        "collection_inside_run_root": True,
        "candidate_addon_root": str(ADDON_ROOT),
        "probe_addon_root": str(PROBE_ROOT),
        "addons_inside_run_root": True,
        "window_title": window_title,
        "window_title_matches_profile": True,
        "sync_credentials_present": False,
        "auto_sync": False,
        "media_sync": False,
        "sync_identity": "disabled-and-disconnected",
        "single_instance_key_fingerprint": hashlib.sha256(
            EXPECTED_INSTANCE_KEY.encode("utf-8")
        ).hexdigest()[:12],
        "anki_version": getattr(anki, "__version__", "26.8.1"),
        "candidate": candidate,
    }


def _due_tree_node(node: Any, deck_id: int) -> Any | None:
    if int(getattr(node, "deck_id", 0) or 0) == deck_id:
        return node
    for child in getattr(node, "children", ()):
        match = _due_tree_node(child, deck_id)
        if match is not None:
            return match
    return None


def _configure_new_limit(deck_id: int, config_name: str, limit: int) -> None:
    configs = mw.col.decks.all_config()
    config = next(
        (item for item in configs if str(item.get("name", "")) == config_name),
        None,
    )
    if config is None:
        base = mw.col.decks.config_dict_for_deck_id(deck_id)
        config = mw.col.decks.add_config(config_name, clone_from=base)
    config["new"]["perDay"] = limit
    mw.col.decks.update_config(config)
    deck = mw.col.decks.get(deck_id, default=False)
    _require(deck is not None, "QA head deck disappeared while setting its limit")
    mw.col.decks.set_config_id_for_deck_dict(deck, config["id"])
    readback = mw.col.decks.config_dict_for_deck_id(deck_id)
    _require(
        int(readback["new"]["perDay"]) == limit,
        "QA head deck daily new limit did not persist",
    )


def _add_qa_new_cards(deck_id: int, label: str) -> None:
    notetype = mw.col.models.current()
    _require(notetype is not None, "the disposable collection has no current note type")
    requests = []
    for index in range(QA_RAW_NEW_PER_HEAD):
        note = mw.col.new_note(notetype)
        _require(len(note.fields) >= 2, "the disposable note type needs at least two fields")
        note.fields[0] = "{} new card {:02d}".format(label, index + 1)
        note.fields[1] = "Home Dashboard 1.8.4 scheduler-limit QA"
        requests.append(AddNoteRequest(note=note, deck_id=deck_id))
    mw.col.add_notes(requests)


def _prepare_multi_deck_fixture(*, allow_create: bool) -> dict[str, Any]:
    deck_ids: dict[str, int] = {}
    for label, name in (("A", QA_HEAD_A), ("B", QA_HEAD_B)):
        existing = mw.col.decks.id_for_name(name)
        if existing is None:
            _require(allow_create, "QA head deck {} is missing after restart".format(label))
            existing = mw.col.decks.id(name)
        _require(existing is not None, "could not create QA head deck {}".format(label))
        deck_ids[label] = int(existing)

    if allow_create:
        _configure_new_limit(deck_ids["A"], QA_CONFIG_A, 3)
        _configure_new_limit(deck_ids["B"], QA_CONFIG_B, 7)
    else:
        for label, expected in (("A", 3), ("B", 7)):
            readback = mw.col.decks.config_dict_for_deck_id(deck_ids[label])
            _require(
                int(readback["new"]["perDay"]) == expected,
                "QA head {} daily new limit did not persist after restart".format(label),
            )
    raw_counts: dict[str, int] = {}
    for label in ("A", "B"):
        deck_id = deck_ids[label]
        raw = int(mw.col.db.scalar(
            "SELECT count() FROM cards WHERE did = ? AND queue = 0 AND type = 0",
            deck_id,
        ) or 0)
        if raw == 0:
            _require(allow_create, "QA new cards are missing after restart")
            _add_qa_new_cards(deck_id, label)
            raw = int(mw.col.db.scalar(
                "SELECT count() FROM cards WHERE did = ? AND queue = 0 AND type = 0",
                deck_id,
            ) or 0)
        _require(
            raw == QA_RAW_NEW_PER_HEAD,
            "QA head {} must contain exactly {} raw new cards".format(
                label, QA_RAW_NEW_PER_HEAD
            ),
        )
        raw_counts[label] = raw

    if allow_create:
        mw.col.decks.select(deck_ids["A"])
    _require(
        int(mw.col.decks.get_current_id()) == deck_ids["A"],
        "QA head A is not the active deck{}".format(
            " after restart" if not allow_create else ""
        ),
    )
    tree = mw.col.sched.deck_due_tree()
    remaining_limits: dict[str, int] = {}
    for label, expected in (("A", 3), ("B", 7)):
        node = _due_tree_node(tree, deck_ids[label])
        _require(node is not None, "Anki's due tree omitted QA head {}".format(label))
        remaining = int(getattr(node, "new_count", -1))
        _require(
            remaining == expected,
            "QA head {} due-tree allowance is {}, expected {}".format(
                label, remaining, expected
            ),
        )
        remaining_limits[label] = remaining
    return {
        "deck_ids": deck_ids,
        "deck_names": {"A": QA_HEAD_A, "B": QA_HEAD_B},
        "active_head": "A",
        "active_deck_id": deck_ids["A"],
        "raw_new_cards": raw_counts,
        "remaining_limits": remaining_limits,
    }


def _queue_values(snapshot: DashboardSnapshot) -> dict[str, Any]:
    state = snapshot.facts.queue
    _require(state.is_available, "Today’s Progress is unavailable in multi-deck QA")
    queue = state.value
    return {
        "new": int(queue.new),
        "learning": int(queue.learning),
        "review": int(queue.review),
        "total": int(queue.total),
        "eta_seconds": queue.estimated_duration_seconds,
    }


def _show_live_snapshot(
    *,
    label: str,
    config: dict[str, Any],
    snapshot: DashboardSnapshot,
    expected_new: int,
    expected_total: int,
    continuation: Any,
) -> None:
    try:
        queue = _queue_values(snapshot)
        _require(queue["new"] == expected_new, "{} analytics New remaining mismatch".format(label))
        _require(queue["total"] == expected_total, "{} analytics Total remaining mismatch".format(label))
        expected_progress = _progress_presentation(snapshot).label
        _controller.config = config
        _controller.snapshot = snapshot
        _controller.cache_key = _controller._key()
        _controller.inflight_key = None
        _controller.facts_revision += 1
        _controller.selected_date = snapshot.facts.scheduling_date
        _controller.selection_follows_today = True
        mw.deckBrowser.refresh()
        QTimer.singleShot(
            600,
            lambda: _inspect_live_snapshot(
                label=label,
                queue=queue,
                expected_new=expected_new,
                expected_total=expected_total,
                expected_progress=expected_progress,
                continuation=continuation,
                attempt=0,
            ),
        )
    except Exception as exc:
        _error("multi-deck-{}".format(label), exc)


def _inspect_live_snapshot(
    *,
    label: str,
    queue: Mapping[str, Any],
    expected_new: int,
    expected_total: int,
    expected_progress: str,
    continuation: Any,
    attempt: int,
) -> None:
    try:
        web = mw.deckBrowser.web
        script = (
            "(function(){var r=document.getElementById('hdo-dashboard');"
            "function value(k){var n=r&&r.querySelector('[data-hdo-metric=\"'+k+'\"]');"
            "return n?n.textContent.trim():'';}"
            "var p=r&&r.querySelector('[data-hdo-progress-label]');"
            "return {mounted:!!r,newText:value('queue.new'),totalText:value('queue.total'),"
            "progressLabel:p?p.textContent.trim():''};})()"
        )

        def inspected(value: object) -> None:
            try:
                state = value if isinstance(value, dict) else {}
                expected_new_text = str(expected_new)
                expected_total_text = str(expected_total)
                if (
                    state.get("mounted") is not True
                    or state.get("newText") != expected_new_text
                    or state.get("totalText") != expected_total_text
                    or state.get("progressLabel") != expected_progress
                ):
                    if attempt < 12:
                        QTimer.singleShot(
                            180,
                            lambda: _inspect_live_snapshot(
                                label=label,
                                queue=queue,
                                expected_new=expected_new,
                                expected_total=expected_total,
                                expected_progress=expected_progress,
                                continuation=continuation,
                                attempt=attempt + 1,
                            ),
                        )
                        return
                    raise RuntimeError("{} live dashboard values did not settle".format(label))
                REPORT.setdefault("multi_deck_new_limit_smoke", {}).setdefault(
                    "assertions", []
                ).append({
                    "label": label,
                    "expected_new_remaining": expected_new,
                    "expected_total_remaining": expected_total,
                    "expected_progress_label": expected_progress,
                    "analytics": dict(queue),
                    "dom": dict(state),
                    "production_dashboard_mounted": True,
                })
                _write_report()
                continuation()
            except Exception as exc:
                _error("multi-deck-{}-dom".format(label), exc)

        web.evalWithCallback(script, inspected)
    except Exception as exc:
        _error("multi-deck-{}-inspect".format(label), exc)


def _run_multi_deck_smoke(continuation: Any) -> None:
    try:
        _require(_live_snapshot is not None, "the production dashboard never completed its initial load")
        pre_fixture_queue = _queue_values(_live_snapshot)
        if STAGE == "initial":
            _require(
                pre_fixture_queue["new"] == 0 and pre_fixture_queue["total"] == 0,
                "initial production snapshot has the wrong remaining count",
            )
        elif RESTART_PRE_FIXTURE_EXPECTED_NEW is None:
            _require(
                all(pre_fixture_queue[key] >= 0 for key in ("new", "learning", "review", "total"))
                and pre_fixture_queue["total"]
                == pre_fixture_queue["new"] + pre_fixture_queue["learning"] + pre_fixture_queue["review"],
                "restart initial production snapshot has an inconsistent scheduler queue",
            )
        else:
            _require(
                pre_fixture_queue["new"] == RESTART_PRE_FIXTURE_EXPECTED_NEW
                and pre_fixture_queue["total"] == RESTART_PRE_FIXTURE_EXPECTED_NEW,
                "restart initial production snapshot has the wrong remaining count",
            )
        fixture = _prepare_multi_deck_fixture(allow_create=STAGE == "initial")
        base_config = normalize_config(_controller.config)
        base_config["heatmap"]["excluded_deck_ids"] = []
        unexcluded = collect_snapshot(mw.col, base_config, VerseContent())
        REPORT["multi_deck_new_limit_smoke"] = {
            "status": "running",
            "stage": STAGE,
            "fixture": fixture,
            "initial_dashboard_loaded_before_fixture": True,
            "initial_dashboard_queue": pre_fixture_queue,
            "assertions": [],
        }

        def finished_unexcluded() -> None:
            if STAGE == "restart":
                REPORT["multi_deck_new_limit_smoke"]["status"] = "passed"
                _write_report()
                continuation()
                return
            excluded_config = deepcopy(base_config)
            excluded_config["heatmap"]["excluded_deck_ids"] = [
                fixture["deck_ids"]["B"]
            ]
            excluded = collect_snapshot(mw.col, excluded_config, VerseContent())

            def finished_excluded() -> None:
                REPORT["multi_deck_new_limit_smoke"]["status"] = "passed"
                _write_report()
                continuation()

            _show_live_snapshot(
                label="excluding-head-b",
                config=excluded_config,
                snapshot=excluded,
                expected_new=3,
                expected_total=3,
                continuation=finished_excluded,
            )

        _show_live_snapshot(
            label=("restart-unexcluded" if STAGE == "restart" else "active-a-unexcluded"),
            config=base_config,
            snapshot=unexcluded,
            expected_new=10,
            expected_total=(RESTART_MULTI_DECK_EXPECTED_TOTAL if STAGE == "restart" else 10),
            continuation=finished_unexcluded,
        )
    except Exception as exc:
        _error("multi-deck-{}-setup".format(STAGE), exc)


def _base_config(theme: str, mode: str, view: str) -> dict[str, Any]:
    config = normalize_config({})
    config["appearance"].update(
        preset=theme,
        mode=mode,
        opacity=96,
        blur=12,
        text_scale=100,
    )
    config["home_screen"]["position"] = "top"
    config["heatmap"].update(
        calendar_view=view,
        week_start=0,
        history_days=0,
        forecast_days=90,
        show_due_forecast=True,
    )
    return config


def _relation(iso: str) -> DayRelation:
    if iso < REFERENCE_DATE:
        return DayRelation.PAST
    if iso > REFERENCE_DATE:
        return DayRelation.FUTURE
    return DayRelation.CURRENT


def _ensure_day(snapshot: DashboardSnapshot, iso: str) -> DayFacts:
    existing = snapshot.facts.days.get(iso)
    if existing is not None:
        return existing
    return DayFacts(
        date=iso,
        scheduling_date=REFERENCE_DATE,
        relation=_relation(iso),
        reviews_completed=(
            ValueState.available(0)
            if iso <= REFERENCE_DATE
            else ValueState.unavailable(AvailabilityReason.HISTORY_OUT_OF_RANGE)
        ),
        new_cards_studied=(
            ValueState.available(0)
            if iso <= REFERENCE_DATE
            else ValueState.unavailable(AvailabilityReason.HISTORY_OUT_OF_RANGE)
        ),
        reviews_due=(
            ValueState.available(0)
            if iso >= REFERENCE_DATE
            else ValueState.unavailable(AvailabilityReason.FORECAST_OUT_OF_RANGE)
        ),
        again_count=(
            ValueState.available(0)
            if iso <= REFERENCE_DATE
            else ValueState.unavailable(AvailabilityReason.HISTORY_OUT_OF_RANGE)
        ),
        events=ValueState.available(()),
        browse_target=BrowseTarget(),
        domain_state=DayDomainState.NO_DUE,
    )


def _events_snapshot(selected: str, *, selected_has_events: bool) -> DashboardSnapshot:
    snapshot = representative_preview_snapshot(REFERENCE_DATE)
    selected_events: tuple[EventItem, ...] = ()
    if selected_has_events:
        selected_events = (
            EventItem(
                "selected-one",
                "Comprehensive Pediatrics Board Review and Longitudinal Planning Conference",
                selected,
                (date.fromisoformat(selected) - date.fromisoformat(REFERENCE_DATE)).days,
            ),
            EventItem(
                "selected-two",
                "Second event on the selected date",
                selected,
                (date.fromisoformat(selected) - date.fromisoformat(REFERENCE_DATE)).days,
            ),
        )
    next_event = EventItem("global-next", "Next global study milestone", "2026-08-25", 2)
    all_events = selected_events + (next_event,)
    days = dict(snapshot.facts.days)
    if selected_events:
        selected_day = _ensure_day(snapshot, selected)
        days[selected] = replace(selected_day, events=ValueState.available(selected_events))
    next_day = _ensure_day(snapshot, next_event.date)
    days[next_event.date] = replace(next_day, events=ValueState.available((next_event,)))
    return replace(
        snapshot,
        facts=replace(snapshot.facts, events=ValueState.available(all_events), days=days),
    )


def _many_events_snapshot(selected: str) -> DashboardSnapshot:
    snapshot = representative_preview_snapshot(REFERENCE_DATE)
    offset = (date.fromisoformat(selected) - date.fromisoformat(REFERENCE_DATE)).days
    events = tuple(
        EventItem(
            "selected-{:02d}".format(index),
            (
                "Comprehensive Pediatrics Board Review and Longitudinal Planning Conference"
                if index == 0
                else "Follow-up selected-date event {:02d}".format(index + 1)
            ),
            selected,
            offset,
        )
        for index in range(10)
    )
    day = _ensure_day(snapshot, selected)
    days = dict(snapshot.facts.days)
    days[selected] = replace(day, events=ValueState.available(events))
    return replace(
        snapshot,
        facts=replace(snapshot.facts, events=ValueState.available(events), days=days),
    )


def _combined_today_snapshot() -> DashboardSnapshot:
    snapshot = representative_preview_snapshot(REFERENCE_DATE)
    today = _ensure_day(snapshot, REFERENCE_DATE)
    event = EventItem("today-event", "Learning checkpoint", REFERENCE_DATE, 0)
    days = dict(snapshot.facts.days)
    days[REFERENCE_DATE] = replace(
        today,
        reviews_completed=ValueState.available(60),
        new_cards_studied=ValueState.available(12),
        reviews_due=ValueState.available(31),
        again_count=ValueState.available(3),
        events=ValueState.available((event,)),
        browse_target=BrowseTarget(BrowseTargetKind.REVIEWED, "rated:1", True, ()),
        domain_state=DayDomainState.TROUBLE,
    )
    return replace(
        snapshot,
        facts=replace(
            snapshot.facts,
            today=ValueState.available(TodayStats(60, 12, 1_860, 31.0)),
            queue=ValueState.available(QueueStats(14, 1, 16, 31, 1_220)),
            events=ValueState.available((event,)),
            days=days,
        ),
    )


def _complete_snapshot() -> DashboardSnapshot:
    snapshot = representative_preview_snapshot(REFERENCE_DATE)
    today = _ensure_day(snapshot, REFERENCE_DATE)
    days = dict(snapshot.facts.days)
    days[REFERENCE_DATE] = replace(
        today,
        reviews_completed=ValueState.available(120),
        new_cards_studied=ValueState.available(18),
        reviews_due=ValueState.available(42),
        again_count=ValueState.available(4),
        browse_target=BrowseTarget(BrowseTargetKind.REVIEWED, "rated:1", True, ()),
        domain_state=DayDomainState.TROUBLE,
    )
    return replace(
        snapshot,
        facts=replace(
            snapshot.facts,
            today=ValueState.available(TodayStats(120, 18, 3_060, 25.5)),
            queue=ValueState.available(QueueStats(0, 0, 0, 0, 0)),
            days=days,
        ),
    )


def _all_clear_snapshot() -> DashboardSnapshot:
    """Historical account with no scheduled work and no completed work today."""

    snapshot = representative_preview_snapshot(REFERENCE_DATE)
    return replace(
        snapshot,
        facts=replace(
            snapshot.facts,
            today=ValueState.available(TodayStats(0, 0, 0, None)),
            queue=ValueState.available(QueueStats(0, 0, 0, 0, 0)),
        ),
    )


def _stress_snapshot() -> DashboardSnapshot:
    snapshot = representative_preview_snapshot(REFERENCE_DATE)
    january = EventItem("year-january", "January boundary event", "2026-01-02", -233)
    december = EventItem("year-december", "December boundary event", "2026-12-29", 128)
    days = dict(snapshot.facts.days)
    for event, completed, due in ((january, 901, 0), (december, 0, 9876)):
        base = _ensure_day(snapshot, event.date)
        days[event.date] = replace(
            base,
            reviews_completed=(
                ValueState.available(completed)
                if event.date <= REFERENCE_DATE
                else ValueState.unavailable(AvailabilityReason.HISTORY_OUT_OF_RANGE)
            ),
            reviews_due=(
                ValueState.available(due)
                if event.date >= REFERENCE_DATE
                else ValueState.unavailable(AvailabilityReason.FORECAST_OUT_OF_RANGE)
            ),
            events=ValueState.available((event,)),
            domain_state=DayDomainState.FUTURE_DUE if due else DayDomainState.TROUBLE,
        )
    return replace(
        snapshot,
        facts=replace(
            snapshot.facts,
            today=ValueState.available(TodayStats(12_486, 1_048, 313_000, 25.1)),
            queue=ValueState.available(QueueStats(3_200, 1, 7_800, 11_001, 89_000)),
            buried=ValueState.available(BuriedStats(120, 80, 640)),
            events=ValueState.available((january, december)),
            last_seven_days=ValueState.available(
                LastSevenDaysStats(
                    cards_studied=98_765,
                    new_cards_studied=8_765,
                    retention=RateMetric.from_counts(90_864, 98_765),
                    again_rate=RateMetric.from_counts(7_901, 98_765),
                )
            ),
            long_term=ValueState.available(
                LongTermStats(
                    average_reviews_per_active_day=12_486,
                    active_days_percent=99,
                    longest_streak=1_517,
                    current_streak=1_024,
                    lifetime_retention=RateMetric.from_counts(974_376, 1_082_640),
                    lifetime_cards_studied=1_082_640,
                )
            ),
            due_load_reference=9876.0,
            days=days,
        ),
        verse=VerseContent(
            "The steadfast love of the Lord never ceases; his mercies never come to an end; "
            "they are new every morning; great is your faithfulness, and your loving care "
            "continues through every season of patient study and service.",
            "Lamentations 3:22-23",
        ),
    )


def _fixture(case: Mapping[str, Any]) -> DashboardSnapshot:
    fixture = str(case.get("fixture", "populated"))
    if fixture == "fresh":
        _require(_live_snapshot is not None, "live fresh snapshot is unavailable")
        return _live_snapshot
    if fixture == "combined-today":
        return _combined_today_snapshot()
    if fixture == "selected-event":
        return _events_snapshot("2026-08-27", selected_has_events=True)
    if fixture == "next-event-future":
        return _events_snapshot("2026-08-29", selected_has_events=False)
    if fixture == "selected-long-event-plus-nine":
        return _many_events_snapshot("2026-08-27")
    if fixture in {"very-large", "year-boundaries"}:
        return _stress_snapshot()
    if fixture == "complete":
        return _complete_snapshot()
    if fixture == "historical-all-clear":
        return _all_clear_snapshot()
    if fixture == "failure":
        return unavailable_snapshot(
            verse=VerseContent("The Lord is my strength and my song.", "Psalm 118:14"),
            scheduling_date=REFERENCE_DATE,
            day_cutoff_iso="2026-08-24T04:00-05:00",
            revision="release-probe-failure",
        )
    snapshot = representative_preview_snapshot(REFERENCE_DATE)
    if fixture == "long-verse":
        snapshot = replace(
            snapshot,
            verse=VerseContent(
                "Trust in the Lord with all your heart and lean not on your own understanding; "
                "in all your ways acknowledge him, and he will make your paths straight, even "
                "through long seasons of careful learning, review, reflection, and service.",
                "Proverbs 3:5-6",
            ),
        )
    return snapshot


def _case(
    case_id: str,
    theme: str,
    mode: str,
    view: str,
    *,
    fixture: str = "populated",
    layout: str = "wide",
    selected: str = REFERENCE_DATE,
    tags: Iterable[str] = (),
    special: str = "",
    week_start: int = 0,
    container_width: int | None = None,
) -> dict[str, Any]:
    return {
        "id": case_id,
        "theme": theme,
        "mode": mode,
        "view": view,
        "fixture": fixture,
        "layout": layout,
        "selected": selected,
        "tags": list(tags),
        "special": special,
        "week_start": week_start,
        "container_width": container_width,
        "ui_scale_percent": 100,
        "text_scale_percent": 100,
    }


def _build_initial_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    prefixes = {
        "Sapphire Glass": "SG",
        "Graphite": "GR",
        "Emerald": "EM",
        "High Contrast": "HC",
    }
    for theme in ("Sapphire Glass", "Graphite", "Emerald", "High Contrast"):
        for mode in ("light", "dark"):
            for view in ("month", "year"):
                cases.append(_case(
                    "PRIMARY-{}-{}-{}".format(prefixes[theme], "L" if mode == "light" else "D", "M" if view == "month" else "Y"),
                    theme,
                    mode,
                    view,
                    tags=("primary_native", "populated_data"),
                ))

    cases.extend((
        _case("FRESH-SG-L-M", "Sapphire Glass", "light", "month", fixture="fresh", tags=("fresh_data", "no_cards_scheduled", "missing_pace_eta", "missing_retention", "zero_lifetime")),
        _case("FRESH-SG-L-Y", "Sapphire Glass", "light", "year", fixture="fresh", tags=("fresh_data", "empty_year")),
        _case("HISTORICAL-ALL-CLEAR-SG-D-M", "Sapphire Glass", "dark", "month", fixture="historical-all-clear", tags=("all_clear", "short_verse")),
        _case("FRESH-SG-D-Y", "Sapphire Glass", "dark", "year", fixture="fresh", tags=("fresh_data", "empty_year")),
        _case("RESP-SG-L-INTERMEDIATE", "Sapphire Glass", "light", "month", layout="intermediate", tags=("responsive",)),
        _case("RESP-SG-D-INTERMEDIATE", "Sapphire Glass", "dark", "year", layout="intermediate", tags=("responsive",)),
        _case("RESP-SG-L-NARROW", "Sapphire Glass", "light", "month", layout="intermediate", tags=("responsive", "no_horizontal_scroll")),
        _case("RESP-SG-D-NARROW", "Sapphire Glass", "dark", "year", layout="narrow", tags=("responsive", "no_horizontal_scroll")),
        _case("RESP-HC-L-NARROW", "High Contrast", "light", "month", layout="narrow", tags=("responsive", "no_horizontal_scroll")),
        _case("RESP-HC-D-NARROW", "High Contrast", "dark", "year", layout="narrow", tags=("responsive", "no_horizontal_scroll")),
        _case("STATE-COMBINED-TODAY", "Sapphire Glass", "dark", "month", fixture="combined-today", tags=("combined_state_markers", "today_completed_with_due", "one_learning_card", "partial_progress", "reviewed_cards_action")),
        _case("STATE-SELECTED-EVENT", "Sapphire Glass", "light", "month", fixture="selected-event", selected="2026-08-27", tags=("event_on_selected_date", "event_count", "multiple_events", "footer_relationships", "footer_edit_action")),
        _case("STATE-NEXT-EVENT-FUTURE", "Graphite", "dark", "month", fixture="next-event-future", selected="2026-08-29", tags=("next_event", "future_selected", "due_cards_action")),
        _case("STATE-PAST-TOOLTIP", "Emerald", "light", "month", selected="2026-08-15", tags=("calendar_tooltip", "selected_past", "historical_wording"), special="tooltip"),
        _case("STATE-FIVE-ROW-SUNDAY", "Sapphire Glass", "light", "month", selected="2026-04-15", tags=("five_row_month", "sunday_start"), week_start=6),
        _case("STATE-SIX-ROW-MONDAY", "Sapphire Glass", "dark", "month", fixture="very-large", selected="2026-08-15", tags=("six_row_month", "monday_start", "very_large_counts", "large_streak"), week_start=0),
        _case("STATE-YEAR-BOUNDARIES", "High Contrast", "dark", "year", fixture="year-boundaries", tags=("populated_year", "year_boundaries", "year_weekday_references")),
        _case("STATE-COMPLETE-METRICS", "Sapphire Glass", "dark", "month", fixture="complete", tags=("complete_progress", "eta_done_positive_workload", "populated_rates")),
        _case("BACKGROUND-SG-L", "Sapphire Glass", "light", "month", tags=("background_case", "native_host_unchanged", "component_only_theming"), special="background"),
        _case("BACKGROUND-SG-D", "Sapphire Glass", "dark", "year", tags=("background_case", "native_host_unchanged", "component_only_theming"), special="background"),
        _case("BACKGROUND-EM-L", "Emerald", "light", "month", tags=("background_case", "native_host_unchanged", "opaque_non_sapphire"), special="background"),
        _case("BACKGROUND-EM-D", "Emerald", "dark", "year", tags=("background_case", "native_host_unchanged", "opaque_non_sapphire"), special="background"),
        _case("BACKGROUND-REDUCED-OPACITY", "Sapphire Glass", "dark", "month", tags=("background_case", "sapphire_only_glass", "opacity_94", "blur_16", "text_readability"), special="background-opacity"),
        _case("BIBLE-SHORT", "Sapphire Glass", "light", "year", tags=("bible_case", "short_verse", "year_height_independent_of_bible")),
        _case("BIBLE-LONG", "Sapphire Glass", "light", "year", fixture="long-verse", tags=("bible_case", "long_verse", "no_truncation", "year_height_independent_of_bible")),
        _case("BIBLE-CUSTOM-FONT", "Emerald", "light", "year", tags=("bible_case", "custom_font"), special="custom-font"),
        _case("BIBLE-DISABLED", "Sapphire Glass", "light", "year", tags=("bible_case", "bible_disabled", "no_bible_gap", "year_height_independent_of_bible"), special="bible-disabled"),
        _case("RUNTIME-INITIAL-LOADING", "Sapphire Glass", "light", "month", fixture="loading", tags=("runtime_state", "initial_loading"), special="loading-initial"),
        _case("RUNTIME-DELAYED-LOADING", "Sapphire Glass", "dark", "month", fixture="loading", tags=("runtime_state", "delayed_loading"), special="loading-delayed"),
        _case("RUNTIME-FAILURE", "High Contrast", "light", "month", fixture="loading", tags=("runtime_state", "loading_failure"), special="loading-failure"),
        _case("RUNTIME-RETRY", "High Contrast", "dark", "year", tags=("runtime_state", "retry_retained_data", "retained_prior_data"), special="retry-retained"),
        _case("RESP-SG-D-INTERMEDIATE-SCROLLED-BOTTOM", "Sapphire Glass", "dark", "month", layout="intermediate", tags=("responsive", "bottom_clearance", "single_vertical_scroll"), special="scroll-bottom"),
        _case("RESP-HC-D-NARROW-SCROLLED-BOTTOM", "High Contrast", "dark", "month", layout="narrow", tags=("responsive", "bottom_clearance", "single_vertical_scroll"), special="scroll-bottom"),
        _case("RESP-YEAR-NARROW-JANUARY", "Sapphire Glass", "dark", "year", layout="intermediate", tags=("responsive", "year_january_reachable"), special="year-january"),
        _case("RESP-YEAR-NARROW-CURRENT-MONTH", "Graphite", "light", "year", layout="narrow", tags=("responsive", "year_initial_current_month_centering"), special="year-current"),
        _case("RESP-YEAR-NARROW-DECEMBER", "Emerald", "dark", "year", layout="narrow", tags=("responsive", "year_december_reachable"), special="year-december"),
        _case("BIBLE-LONG-NARROW", "Sapphire Glass", "light", "year", fixture="long-verse", layout="narrow", tags=("bible_case", "long_verse", "natural_bible_growth"), special="bible-long-narrow"),
        _case("STATE-NARROW-LONG-EVENT-PLUS-9", "Graphite", "dark", "month", fixture="selected-long-event-plus-nine", layout="narrow", selected="2026-08-27", tags=("footer_relationships", "event_count_plus_nine")),
        _case("STATE-NARROW-LONG-LOCALIZED-DATE", "High Contrast", "light", "month", layout="narrow", tags=("footer_relationships", "long_localized_date", "footer_date_readability"), special="localized-date"),
    ))
    exact_widths = {
        "PRIMARY-SG-L-M": 1240,
        "PRIMARY-SG-L-Y": 1100,
        "PRIMARY-SG-D-M": 1040,
        "RESP-SG-L-INTERMEDIATE": 1039,
        "RESP-SG-D-INTERMEDIATE": 620,
        "RESP-SG-L-NARROW": 419,
        "RESP-SG-D-NARROW": 419,
        "RESP-HC-L-NARROW": 320,
        "RESP-HC-D-NARROW": 319,
        "RESP-SG-D-INTERMEDIATE-SCROLLED-BOTTOM": 620,
        "RESP-HC-D-NARROW-SCROLLED-BOTTOM": 319,
        "RESP-YEAR-NARROW-JANUARY": 479,
        "RESP-YEAR-NARROW-CURRENT-MONTH": 419,
        "RESP-YEAR-NARROW-DECEMBER": 319,
        "BIBLE-LONG-NARROW": 419,
        "STATE-NARROW-LONG-EVENT-PLUS-9": 419,
        "STATE-NARROW-LONG-LOCALIZED-DATE": 319,
    }
    for case in cases:
        if case["id"] in exact_widths:
            case["container_width"] = exact_widths[case["id"]]
            case["tags"].append("container_{}".format(exact_widths[case["id"]]))
    return cases


def _restart_case(observed_view: str = "year") -> dict[str, Any]:
    return _case(
        "RUNTIME-RESTART-PERSISTENCE",
        "Sapphire Glass",
        "dark",
        observed_view,
        tags=("runtime_state", "restart", "calendar_view_persistence", "clean_settings_state", "no_waiver"),
        special="restart",
    )


def _config_for(case: Mapping[str, Any]) -> dict[str, Any]:
    if str(case.get("special", "")) == "restart":
        return normalize_config(mw.addonManager.getConfig(_controller.package))
    config = _base_config(str(case["theme"]), str(case["mode"]), str(case["view"]))
    config["heatmap"]["week_start"] = int(case.get("week_start", 0))
    special = str(case.get("special", ""))
    if special == "background-opacity":
        config["appearance"]["opacity"] = 94
        config["appearance"]["blur"] = 16
    if special == "custom-font":
        config["bible"]["font_family"] = "Avenir Next, sans-serif"
        config["bible"]["font_size"] = "36px"
    if special == "bible-disabled":
        config["visibility"]["bible"] = False
    return config


def _target_frame(case: Mapping[str, Any]) -> tuple[int, int]:
    screen = _qa_screen()
    available = screen.availableGeometry()
    layout = str(case.get("layout", "wide"))
    if layout == "intermediate":
        return min(1120, available.width()), min(940, available.height())
    if layout == "narrow":
        return min(620, available.width()), min(980, available.height())
    return available.width(), available.height()


def _fit_native_frame(case: Mapping[str, Any], continuation: Any, attempt: int = 0) -> None:
    try:
        screen = _qa_screen()
        available = screen.availableGeometry()
        target_width, target_height = _target_frame(case)
        mw.showNormal()
        frame = mw.frameGeometry()
        width_delta = target_width - frame.width()
        height_delta = target_height - frame.height()
        if width_delta or height_delta:
            mw.resize(max(420, mw.width() + width_delta), max(620, mw.height() + height_delta))
        frame = mw.frameGeometry()
        target_x = available.x() + max(0, (available.width() - target_width) // 2)
        target_y = available.y() + max(0, (available.height() - target_height) // 2)
        mw.move(mw.x() + target_x - frame.x(), mw.y() + target_y - frame.y())
        mw.raise_()
        mw.activateWindow()
        QApplication.processEvents()
        frame = mw.frameGeometry()
        if (abs(frame.width() - target_width) > 1 or abs(frame.height() - target_height) > 1) and attempt < 5:
            QTimer.singleShot(160, lambda: _fit_native_frame(case, continuation, attempt + 1))
            return
        _require(abs(frame.width() - target_width) <= 1, "native frame width did not settle")
        _require(abs(frame.height() - target_height) <= 1, "native frame height did not settle")
        continuation()
    except Exception as exc:
        _error(str(case.get("id", "frame")), exc)


def _mount_case(case: dict[str, Any]) -> None:
    global _active_case
    _active_case = case
    try:
        config = _config_for(case)
        _controller.config = config
        _controller.last_updated_at = "2026-08-23T20:14:00-05:00"
        if STAGE == "initial":
            _controller.year_scroll_left = None
        _controller.selected_date = str(case.get("selected", REFERENCE_DATE))
        _controller.selection_follows_today = _controller.selected_date == REFERENCE_DATE
        special = str(case.get("special", ""))
        if str(case.get("fixture")) == "loading":
            key = _controller._key()
            _controller.snapshot = None
            _controller.cache_key = None
            _controller.inflight_key = key
        else:
            snapshot = _fixture(case)
            _controller.snapshot = snapshot
            _controller.cache_key = _controller._key()
            _controller.inflight_key = None
            _controller.facts_revision += 1
        mw.deckBrowser.refresh()
        if special == "retry-retained":
            QTimer.singleShot(700, lambda: _trigger_retained_refresh_failure(case))
            return
        delay = {
            "loading-initial": 450,
            "loading-delayed": 2850,
            "loading-failure": 12350,
        }.get(str(case.get("special", "")), 500)
        QTimer.singleShot(delay, lambda: _poll_case(case, 0))
    except Exception as exc:
        _error(str(case.get("id", "mount")), exc)


def _trigger_retained_refresh_failure(case: dict[str, Any]) -> None:
    """Prove that refresh and failure states retain the mounted good snapshot."""

    try:
        web = mw.deckBrowser.web
        _require(_controller.snapshot is not None, "retained-data fixture lost its snapshot")
        _require(_controller._set_dashboard_updating(True), "could not expose retained refresh state")

        def inspected_refresh(value: object) -> None:
            try:
                transition = value if isinstance(value, dict) else {}
                _require(transition.get("refreshStatus") == "Refreshing…", "retained refresh status is missing")
                _require(int(transition.get("statisticsCardCount", 0)) == 4, "refresh replaced prior metric cards")
                _require(_controller._set_dashboard_refresh_failed(), "could not expose retained refresh failure")
                REPORT.setdefault("runtime_transitions", {})[str(case["id"])] = {
                    **transition,
                    "prior_snapshot_retained": True,
                    "failure_transition_requested": True,
                }
                _write_report()
                QTimer.singleShot(220, lambda: _poll_case(case, 0))
            except Exception as exc:
                _error(str(case.get("id", "retained-refresh")), exc)

        QTimer.singleShot(
            160,
            lambda: web.evalWithCallback(
                "(function(){var r=document.getElementById('hdo-dashboard');return {"
                "refreshStatus:(r&&r.querySelector('[data-hdo-refresh-status]')||{}).textContent||'',"
                "statisticsCardCount:r?r.querySelectorAll('.hdo-statistics-card').length:0};})()",
                inspected_refresh,
            ),
        )
    except Exception as exc:
        _error(str(case.get("id", "retained-refresh")), exc)


def _prepare_dom(case: Mapping[str, Any], callback: Any) -> None:
    special = str(case.get("special", ""))
    scripts: list[str] = []
    settle_delay = 180
    container_width = case.get("container_width")
    if isinstance(container_width, int):
        scripts.append(
            "var r=document.getElementById('hdo-dashboard');"
            "if(r){r.style.width='%dpx';r.style.maxWidth='%dpx';r.dataset.hdoQaContainerWidth='%d';}"
            % (container_width, container_width, container_width)
        )
    if special in {"background", "background-opacity"}:
        scripts.append(
            "document.body.style.backgroundImage='linear-gradient(135deg,#17365f 0%,#6a3b73 52%,#d59a3a 100%)';"
            "var r=document.getElementById('hdo-dashboard');"
            "if(r){r.dataset.hdoQaBackgroundImage='true';"
            "if(globalThis.HDOCalendarModel){globalThis.HDOCalendarModel.applyDocumentTheme(r);}}"
        )
    if special == "tooltip":
        scripts.append(
            "var c=document.querySelector('.hdo-calendar-day[data-date=\"2026-08-15\"]');"
            "if(c){c.dispatchEvent(new PointerEvent('pointerover',{bubbles:true,relatedTarget:null,clientX:c.getBoundingClientRect().left+4,clientY:c.getBoundingClientRect().top+4}));}"
        )
    if special == "localized-date":
        scripts.append(
            "var d=document.querySelector('[data-hdo-context-date]');"
            "if(d){d.textContent='Sonntag, den 23. August 2026';d.dataset.hdoQaLocalized='true';}"
        )
    if special == "scroll-bottom":
        settle_delay = 360
        scripts.append(
            "requestAnimationFrame(function(){requestAnimationFrame(function(){"
            "var s=document.scrollingElement;if(s){s.scrollTop=s.scrollHeight;}"
            "});});"
        )
    if special == "bible-long-narrow":
        settle_delay = 520
        scripts.append(
            "requestAnimationFrame(function(){requestAnimationFrame(function(){"
            "var b=document.querySelector('.hdo-bible-card');"
            "if(b){b.scrollIntoView({block:'center',inline:'nearest'});}"
            "});});"
        )
    if special in {"year-january", "year-current", "year-december"}:
        settle_delay = 760
        position = {
            "year-january": "f.scrollLeft=0",
            "year-current": "var t=document.querySelector('[data-hdo-calendar=\"today\"]');if(t){t.click();}",
            "year-december": "f.scrollLeft=f.scrollWidth",
        }[special]
        scripts.append(
            "setTimeout(function(){"
            "var f=document.querySelector('.hdo-calendar-grid-frame');if(f){%s}"
            "},360);" % position
        )
    if not scripts:
        callback()
        return
    web = mw.deckBrowser.web
    web.eval("(function(){" + "".join(scripts) + "})()")
    QTimer.singleShot(settle_delay, callback)


DOM_REPORT_SCRIPT = r"""
(function () {
  var root = document.getElementById('hdo-dashboard');
  if (!root) return {ready:false};
  function q(selector) { return root.querySelector(selector); }
  function qa(selector) { return Array.from(root.querySelectorAll(selector)); }
  function rect(node) {
    if (!node) return null;
    var value = node.getBoundingClientRect();
    return {
      left:+value.left.toFixed(2), top:+value.top.toFixed(2),
      right:+value.right.toFixed(2), bottom:+value.bottom.toFixed(2),
      width:+value.width.toFixed(2), height:+value.height.toFixed(2)
    };
  }
  function visible(node) {
    return !!node && !node.hidden && getComputedStyle(node).display !== 'none';
  }
  function bands(nodes, key) {
    return Array.from(new Set(nodes.map(function(node) {
      return Math.round(node.getBoundingClientRect()[key]);
    }))).length;
  }
  function text(selector) {
    var node = q(selector);
    return node ? node.textContent.trim() : '';
  }
  function wraps(node) {
    if (!node) return false;
    var lineHeight = parseFloat(getComputedStyle(node).lineHeight) || 0;
    return lineHeight > 0 && node.getBoundingClientRect().height > lineHeight * 1.5;
  }
  function overlapArea(left, right) {
    if (!left || !right) return 0;
    return Math.max(0, Math.min(left.right, right.right) - Math.max(left.left, right.left)) *
      Math.max(0, Math.min(left.bottom, right.bottom) - Math.max(left.top, right.top));
  }

  var loading = root.classList.contains('hdo-dashboard--loading');
  var layout = q('.hdo-dashboard-layout');
  var calendar = q('.hdo-calendar-card');
  var rail = q('.hdo-insight-rail');
  var cards = qa('.hdo-statistics-card');
  var bible = q('.hdo-bible-card');
  var frame = q('.hdo-calendar-grid-frame');
  var cells = qa('.hdo-calendar-day');
  var selected = qa('.hdo-calendar-day.is-selected');
  var currentMonth = q('.hdo-calendar-day[data-date="2026-08-15"]');
  var january = q('.hdo-calendar-day[data-date="2026-01-01"]');
  var december = q('.hdo-calendar-day[data-date="2026-12-31"]');
  var footer = q('.hdo-calendar-context');
  var footerAreas = footer ? getComputedStyle(footer).gridTemplateAreas : '';
  var footerParts = [
    q('.hdo-calendar-footer__date-context'),
    q('.hdo-calendar-footer__event'),
    q('.hdo-calendar-footer__actions')
  ].filter(visible).map(rect);
  var footerOverlap = 0;
  footerParts.forEach(function(left, index) {
    footerParts.slice(index + 1).forEach(function(right) {
      footerOverlap += overlapArea(left, right);
    });
  });
  var dateNode = q('[data-hdo-context-date]');
  var eventTitle = q('[data-hdo-open-events]');
  var rootStyle = getComputedStyle(root);
  var scroller = document.scrollingElement;
  var scrollerStyle = scroller ? getComputedStyle(scroller) : null;
  var firstCardStyle = cards.length ? getComputedStyle(cards[0]) : null;
  var failurePanel = q('.hdo-loading-failure');

  return {
    ready:true,
    loading:loading,
    loadState:root.dataset.hdoLoadState || '',
    rootAriaBusy:root.getAttribute('aria-busy') || '',
    loadingMessage:text('[data-hdo-loading-message]'),
    loadingSkeletonVisible:visible(q('[data-hdo-loading-skeleton]')),
    loadingFailureVisible:visible(failurePanel),
    loadingFailureHeading:text('.hdo-loading-failure h2'),
    loadingFailureCopy:text('.hdo-loading-failure p:not(.hdo-eyebrow)'),
    loadingFailureActions:qa('.hdo-loading-failure button').map(function(node){return node.textContent.trim();}),
    loadingFailurePanel:rect(failurePanel),
    loadingFailureActionHeights:qa('.hdo-loading-failure button').map(function(node){return rect(node).height;}),
    theme:root.dataset.hdoTheme || '',
    mode:root.dataset.hdoColorMode || '',
    view:root.dataset.hdoCalendarView || '',
    density:root.dataset.hdoContentMode || '',
    viewport:{width:window.innerWidth,height:window.innerHeight},
    root:rect(root),
    calendar:rect(calendar),
    rail:rect(rail),
    bible:rect(bible),
    frame:rect(frame),
    rootPosition:rootStyle.position,
    rootMarginTop:rootStyle.marginTop,
    rootPaddingBottom:rootStyle.paddingBottom,
    rootBackground:rootStyle.backgroundColor,
    rootScrollOwner:root.dataset.hdoScrollOwner || '',
    documentScrollPaddingBlockEnd:scrollerStyle ? scrollerStyle.scrollPaddingBlockEnd : '',
    documentOverflowX:document.documentElement.scrollWidth-document.documentElement.clientWidth,
    bodyOverflowX:document.body.scrollWidth-document.body.clientWidth,
    documentScrollTop:scroller ? scroller.scrollTop : 0,
    documentScrollMaximum:scroller ? Math.max(0,scroller.scrollHeight-scroller.clientHeight) : 0,
    documentBottomReached:scroller ? Math.abs(scroller.scrollTop-Math.max(0,scroller.scrollHeight-scroller.clientHeight))<=2 : false,
    qaContainerWidth:root.dataset.hdoQaContainerWidth || '',
    qaBackgroundImage:root.dataset.hdoQaBackgroundImage || '',
    bodyBackgroundImage:getComputedStyle(document.body).backgroundImage,
    hostPreserved:root.dataset.hdoHostPreserved || '',
    statisticsCardCount:cards.length,
    statisticColumns:cards.length?bands(cards,'left'):0,
    layoutSideBySide:!!calendar&&!!rail&&rect(calendar).right<=rect(rail).left+1,
    layoutStacked:!!calendar&&!!rail&&rect(calendar).bottom<=rect(rail).top+1,
    railWidth:rail?rect(rail).width:0,
    progressText:text('[data-hdo-progress-label]') || text('[data-hdo-progress-chip]'),
    progressLabelCount:qa('[data-hdo-progress-label], [data-hdo-progress-label-fill]').length,
    calendarCellCount:cells.length,
    selectedCount:selected.length,
    yearMonthLabels:qa('.hdo-year-month-label').map(function(node){return node.textContent.trim();}),
    frameOverflowX:frame?frame.scrollWidth-frame.clientWidth:0,
    frameOverflowMode:frame?getComputedStyle(frame).overflowX:'',
    yearScrollLeft:frame?frame.scrollLeft:0,
    yearScrollMaximum:frame?Math.max(0,frame.scrollWidth-frame.clientWidth):0,
    currentMonthCell:rect(currentMonth),
    januaryCell:rect(january),
    decemberCell:rect(december),
    contextEventLabel:text('[data-hdo-context-event-label]'),
    contextEventTitle:text('[data-hdo-open-events]'),
    contextEventMeta:text('[data-hdo-event-meta]'),
    eventMoreText:text('[data-hdo-event-more]'),
    editEventVisible:visible(q('[data-hdo-edit-event]')),
    editEventTitle:(q('[data-hdo-edit-event]')||{}).title || '',
    primaryActionText:text('[data-hdo-primary-action]'),
    footerGridTemplateAreas:footerAreas,
    footerRowCount:(footerAreas.match(/"[^"]+"/g)||[]).length,
    footerOverlapArea:+footerOverlap.toFixed(2),
    contextDateText:dateNode?dateNode.textContent.trim():'',
    contextDateLocalized:dateNode?dateNode.dataset.hdoQaLocalized||'':'',
    contextDateWraps:wraps(dateNode),
    contextDateClipped:dateNode?dateNode.scrollWidth>dateNode.clientWidth+1&&dateNode.scrollHeight<=dateNode.clientHeight+1:false,
    eventTitleWraps:wraps(eventTitle),
    eventTitleClipped:eventTitle?eventTitle.scrollWidth>eventTitle.clientWidth+1&&eventTitle.scrollHeight<=eventTitle.clientHeight+1:false,
    refreshStatus:text('[data-hdo-refresh-status]'),
    refreshWarning:text('.hdo-refresh-warning'),
    refreshWarningCount:qa('.hdo-refresh-warning').length,
    refreshRetryVisible:visible(q('.hdo-refresh-warning button')),
    lastUpdatedAt:root.dataset.hdoLastUpdatedAt || '',
    biblePresent:!!bible,
    bibleFontSize:bible?getComputedStyle(q('.hdo-verse')).fontSize:'',
    bibleOverflow:bible?bible.scrollHeight>bible.clientHeight+1:false,
    cardBackdrop:firstCardStyle?(firstCardStyle.backdropFilter||firstCardStyle.webkitBackdropFilter||'none'):'',
    cardSurfaceOpacity:rootStyle.getPropertyValue('--hdo-card-surface-opacity').trim()
  };
})()
"""


def _validate_dom(case: Mapping[str, Any], state: Mapping[str, Any]) -> None:
    """Check only the release-critical native smoke contract."""

    _require(bool(state.get("ready")), "Deck Browser dashboard did not mount")
    special = str(case.get("special", ""))
    if special.startswith("loading-"):
        if special == "loading-failure":
            _require(state.get("loadState") == "failure", "loading lifecycle did not reach Failure")
            _require(bool(state.get("loadingFailureVisible")), "failure panel is hidden")
            _require(state.get("loadingFailureHeading") == "Dashboard could not load", "failure heading changed")
            _require(state.get("loadingFailureActions") == ["Retry", "Open diagnostics"], "failure actions are incomplete")
            panel = state.get("loadingFailurePanel") or {}
            _require(399 <= float(panel.get("width", 0)) <= 441, "failure panel escaped 400-440px")
            _require(
                all(31 <= float(value) <= 33 for value in state.get("loadingFailureActionHeights", [])),
                "failure actions are not 32px high",
            )
        else:
            _require(bool(state.get("loading")), "loading shell was not mounted")
            _require(bool(state.get("loadingSkeletonVisible")), "loading skeleton is hidden")
            if special == "loading-delayed":
                _require(
                    state.get("loadingMessage") == "Still loading your study data...",
                    "delayed loading wording is missing",
                )
        return

    _require(not bool(state.get("loading")), "dashboard remained in loading state")
    _require(state.get("theme") == case.get("theme"), "theme identity mismatch")
    _require(state.get("mode") == case.get("mode"), "color mode identity mismatch")
    _require(state.get("view") == case.get("view"), "calendar view identity mismatch")
    _require(int(state.get("statisticsCardCount", 0)) == 4, "dashboard did not load all four metric cards")
    _require(float(state.get("documentOverflowX", 0)) <= 1, "document has horizontal overflow")
    _require(float(state.get("bodyOverflowX", 0)) <= 1, "Deck Browser body has horizontal overflow")

    root = state.get("root") or {}
    root_width = float(root.get("width", 0))
    _require(0 < root_width <= 1240.5, "dashboard exceeds its 1240px maximum")
    _require(state.get("rootPosition") not in {"fixed", "sticky"}, "dashboard uses fixed or sticky positioning")
    _require(state.get("rootPaddingBottom") == "66px", "native-control clearance is not 66px")
    _require(state.get("documentScrollPaddingBlockEnd") == "66px", "document scroller lacks 66px clearance")
    _require(state.get("rootScrollOwner") in {"documentElement", "body"}, "document.scrollingElement is not the scroll owner")
    _require(state.get("hostPreserved") == "true", "dashboard did not preserve the host canvas")
    _require(state.get("rootBackground") in {"rgba(0, 0, 0, 0)", "transparent"}, "dashboard root paints the host canvas")

    expected_width = case.get("container_width")
    if isinstance(expected_width, int):
        _require(abs(root_width - expected_width) <= 1, "exact dashboard container width did not settle")
        _require(state.get("qaContainerWidth") == str(expected_width), "container-width capture identity is missing")
    density = "wide" if root_width >= 1040 else "intermediate" if root_width >= 420 else "narrow"
    _require(state.get("density") == density, "dashboard density does not match its container width")
    if root_width >= 1040:
        _require(bool(state.get("layoutSideBySide")), "wide calendar and rail are not side by side")
        _require(float(state.get("railWidth", 0)) >= 371.5, "wide rail is narrower than 372px")
    else:
        _require(bool(state.get("layoutStacked")), "sub-1040 dashboard did not stack")
    calendar_width = float((state.get("calendar") or {}).get("width", 0))
    expected_footer_rows = 1 if calendar_width >= 760 else 2 if calendar_width >= 420 else 3
    _require(int(state.get("footerRowCount", 0)) == expected_footer_rows, "footer row density is incorrect")
    _require(float(state.get("footerOverlapArea", 1)) <= 0.5, "footer regions overlap")
    _require(not bool(state.get("contextDateClipped")), "localized date is clipped")
    _require(not bool(state.get("eventTitleClipped")), "event title is clipped")

    fixture = str(case.get("fixture", ""))
    if fixture in {"selected-event", "selected-long-event-plus-nine"}:
        _require(state.get("contextEventLabel") == "On this date", "selected event meaning is incorrect")
        _require(state.get("editEventTitle") == "Edit event", "selected event does not expose Edit event")
    if fixture == "selected-long-event-plus-nine":
        _require(state.get("eventMoreText") == "+9", "long event fixture did not preserve the +9 count")
        _require(bool(state.get("eventTitleWraps")), "long narrow event title did not wrap")
    if fixture == "next-event-future":
        _require(state.get("contextEventLabel") == "No event on this date", "empty selected-date meaning is incorrect")
        _require(state.get("editEventTitle") == "Add event", "empty selected date does not expose Add event")
        _require(state.get("primaryActionText") == "Due cards", "future Due action changed")
    if special == "localized-date":
        _require(state.get("contextDateLocalized") == "true", "localized date fixture is missing")
        _require(
            state.get("contextDateText") == "Sonntag, den 23. August 2026",
            "long localized date text changed",
        )

    if case.get("view") == "year":
        _require(int(state.get("calendarCellCount", 0)) in {365, 366}, "Year view is incomplete")
        _require(len(state.get("yearMonthLabels", [])) == 12, "Year month labels are incomplete")
        overflow = float(state.get("frameOverflowX", 0))
        if root_width >= 480:
            _require(overflow <= 1, "Year scrolls horizontally at 480px or wider")
        else:
            _require(overflow > 1, "sub-480 Year view lacks its internal scroll region")
            _require(state.get("frameOverflowMode") in {"auto", "scroll"}, "Year scroll region is not explicit")
        scroll_left = float(state.get("yearScrollLeft", 0))
        scroll_max = float(state.get("yearScrollMaximum", 0))
        if special == "year-january":
            _require(scroll_left <= 2, "January is not reachable at the start of Year")
        elif special == "year-december":
            _require(abs(scroll_left - scroll_max) <= 2, "December is not reachable at the end of Year")
        elif special == "year-current":
            frame = state.get("frame") or {}
            current = state.get("currentMonthCell") or {}
            frame_center = (float(frame.get("left", 0)) + float(frame.get("right", 0))) / 2
            current_center = (float(current.get("left", 0)) + float(current.get("right", 0))) / 2
            _require(abs(frame_center - current_center) <= 18, "Today did not center the current month")

    if special == "scroll-bottom":
        _require(float(state.get("documentScrollMaximum", 0)) > 0, "dashboard did not create a page scroll range")
        _require(bool(state.get("documentBottomReached")), "dashboard did not reach the bottom above native controls")

    if special == "retry-retained":
        _require(state.get("refreshStatus") == "", "inline refresh failure status was not removed")
        _require(int(state.get("refreshWarningCount", 0)) == 1, "refresh failure did not use one banner")
        _require("last updated at" in str(state.get("refreshWarning", "")), "refresh banner lacks its timestamp")
        _require(state.get("lastUpdatedAt") == "2026-08-23T20:14:00-05:00", "last_updated_at identity changed")
        _require(bool(state.get("refreshRetryVisible")), "refresh Retry control is hidden")

    if fixture == "long-verse":
        _require(not bool(state.get("bibleOverflow")), "long Bible card overflows")
        _require(
            float(str(state.get("bibleFontSize", "0")).replace("px", "")) >= 14,
            "long Bible text shrank below 14px",
        )
    if special == "bible-long-narrow":
        bible = state.get("bible") or {}
        viewport = state.get("viewport") or {}
        _require(
            float(bible.get("top", -1)) >= 0
            and float(bible.get("bottom", 0)) <= float(viewport.get("height", 0)) - 42,
            "long narrow Bible card is not fully visible above native controls",
        )
    if special in {"background", "background-opacity"}:
        _require("linear-gradient" in str(state.get("bodyBackgroundImage", "")), "external background was altered")
    if special == "restart":
        _require(case.get("view") == "year", "restart did not preserve Year view")
def _poll_case(case: dict[str, Any], attempt: int) -> None:
    try:
        web = getattr(getattr(mw, "deckBrowser", None), "web", None)
        _require(web is not None, "Deck Browser web view is unavailable")

        def inspected(value: object) -> None:
            try:
                state = value if isinstance(value, dict) else {"ready": False}
                if not state.get("ready") and attempt < 30:
                    QTimer.singleShot(200, lambda: _poll_case(case, attempt + 1))
                    return
                _prepare_dom(case, lambda: _inspect_and_capture(case))
            except Exception as exc:
                _error(str(case.get("id", "poll")), exc)

        web.evalWithCallback(
            "(function(){var r=document.getElementById('hdo-dashboard');return r?{ready:true,loading:r.classList.contains('hdo-dashboard--loading')}:{ready:false,loading:false};})()",
            inspected,
        )
    except Exception as exc:
        _error(str(case.get("id", "poll")), exc)


def _inspect_and_capture(case: dict[str, Any], attempt: int = 0) -> None:
    try:
        web = mw.deckBrowser.web

        def inspected(value: object) -> None:
            try:
                state = value if isinstance(value, dict) else {"ready": False}
                _validate_dom(case, state)
                _capture(case, state)
                QTimer.singleShot(160, _next_case)
            except Exception as exc:
                REPORT["last_failed_case"] = {
                    "case": dict(case),
                    "dom": dict(state) if isinstance(state, dict) else {"ready": False},
                    "error": "{}: {}".format(type(exc).__name__, exc),
                }
                _write_report()
                if attempt < 8:
                    QTimer.singleShot(250, lambda: _inspect_and_capture(case, attempt + 1))
                    return
                _error(str(case.get("id", "inspect")), exc)

        web.evalWithCallback(DOM_REPORT_SCRIPT, inspected)
    except Exception as exc:
        _error(str(case.get("id", "inspect")), exc)


def _sample_color_count(pixmap: Any) -> int:
    image = pixmap.toImage()
    width = image.width()
    height = image.height()
    colors: set[int] = set()
    step_x = max(1, width // 32)
    step_y = max(1, height // 24)
    for x in range(step_x // 2, width, step_x):
        for y in range(step_y // 2, height, step_y):
            colors.add(int(image.pixel(x, y)))
            if len(colors) >= 24:
                return len(colors)
    return len(colors)


def _capture(case: Mapping[str, Any], state: Mapping[str, Any]) -> None:
    QApplication.processEvents()
    frame = mw.frameGeometry()
    screen = _qa_screen()
    if STAGE == "restart":
        pixmap = mw.grab()
        method = "QMainWindow.grab-isolated-restart"
    else:
        pixmap = screen.grabWindow(0, frame.x(), frame.y(), frame.width(), frame.height())
        method = "QScreen.grabWindow-screen-crop"
    if pixmap.isNull():
        pixmap = mw.grab()
        method = "QMainWindow.grab-fallback"
    color_count = _sample_color_count(pixmap)
    if color_count < 12:
        fallback = mw.grab()
        fallback_color_count = 0 if fallback.isNull() else _sample_color_count(fallback)
        if fallback_color_count > color_count:
            pixmap = fallback
            color_count = fallback_color_count
            method = "QMainWindow.grab-low-color-fallback"
    minimum_colors = 6 if case.get("theme") == "High Contrast" else 12
    _require(color_count >= minimum_colors, "native Deck Browser capture appears blank")
    CAPTURE_ROOT.mkdir(parents=True, exist_ok=True)
    path = CAPTURE_ROOT / "{}.png".format(case["id"])
    _require(bool(pixmap.save(str(path), "PNG")), "could not save native capture")
    title = str(mw.windowTitle())
    _require(EXPECTED_PROFILE in title, "capture window title lost isolated identity")
    REPORT["captures"][str(case["id"])] = {
        "file": str(path.relative_to(OUTPUT_ROOT)),
        "sha256": _sha256(path),
        "theme": case.get("theme"),
        "mode": case.get("mode"),
        "view": case.get("view"),
        "fixture": case.get("fixture"),
        "layout": case.get("layout"),
        "state_label": "Failure" if case.get("id") == "RUNTIME-FAILURE" else "",
        "tags": list(case.get("tags", [])),
        "ui_scale_percent": 100,
        "text_scale_percent": 100,
        "native_window_dimensions": [frame.width(), frame.height()],
        "dashboard_container_width": round(float((state.get("root") or {}).get("width", 0))),
        "density": state.get("density"),
        "capture_method": method,
        "sampled_color_count": color_count,
        "logical_frame": {
            "x": frame.x(),
            "y": frame.y(),
            "width": frame.width(),
            "height": frame.height(),
        },
        "physical_pixels": [pixmap.width(), pixmap.height()],
        "device_pixel_ratio": pixmap.devicePixelRatio(),
        "window_title": title,
        "window_title_matches_profile": True,
        "production_deck_browser_mount": True,
        "dom": dict(state),
    }
    container_width = case.get("container_width")
    if isinstance(container_width, int):
        REPORT.setdefault("responsive_assertions", {})[str(container_width)] = {
            "view": case.get("view"),
            "root_width": (state.get("root") or {}).get("width"),
            "document_overflow_x": state.get("documentOverflowX"),
            "metric_columns": state.get("statisticColumns"),
            "document_scroll_maximum": state.get("documentScrollMaximum"),
            "document_bottom_reached": state.get("documentBottomReached"),
            "bottom_clearance": state.get("rootPaddingBottom"),
            "document_scroll_padding": state.get("documentScrollPaddingBlockEnd"),
            "density": state.get("density"),
            "frame_overflow_x": state.get("frameOverflowX"),
            "frame_overflow_mode": state.get("frameOverflowMode"),
            "footer_rows": state.get("footerRowCount"),
            "status": "passed",
        }
    _write_report()


def _next_case() -> None:
    global _case_index
    if _case_index >= len(_cases):
        _finish_stage()
        return
    case = _cases[_case_index]
    _case_index += 1
    _fit_native_frame(case, lambda: _mount_case(case))


def _persistence_config() -> dict[str, Any]:
    config = _base_config("Sapphire Glass", "dark", "year")
    return config


def _finish_stage() -> None:
    try:
        smoke = REPORT.get("multi_deck_new_limit_smoke", {})
        _require(smoke.get("status") == "passed", "multi-deck new-limit smoke did not pass")
        smoke_labels = {
            str(item.get("label"))
            for item in smoke.get("assertions", [])
            if isinstance(item, dict)
        }
        if STAGE == "initial":
            _require(
                smoke_labels == {"active-a-unexcluded", "excluding-head-b"},
                "initial multi-deck new-limit assertions are incomplete",
            )
            expected_ids = {case["id"] for case in _cases}
            _require(len(expected_ids) == 55, "initial evidence matrix must contain 55 distinct frames")
            _require(set(REPORT["captures"]) == expected_ids, "initial evidence matrix is incomplete")
            _require(
                set(REPORT.get("responsive_assertions", {}))
                == {"1240", "1100", "1040", "1039", "620", "479", "419", "320", "319"},
                "representative responsive assertion set is incomplete",
            )
            required_smoke = {
                "PRIMARY-SG-L-M",
                "RESP-SG-D-INTERMEDIATE-SCROLLED-BOTTOM",
                "RESP-HC-D-NARROW-SCROLLED-BOTTOM",
                "RESP-YEAR-NARROW-JANUARY",
                "RESP-YEAR-NARROW-CURRENT-MONTH",
                "RESP-YEAR-NARROW-DECEMBER",
                "STATE-NARROW-LONG-EVENT-PLUS-9",
                "STATE-NARROW-LONG-LOCALIZED-DATE",
                "RUNTIME-RETRY",
            }
            _require(required_smoke <= expected_ids, "bounded live smoke coverage is incomplete")

            persisted = _persistence_config()
            mw.addonManager.writeConfig(_controller.package, persisted)
            readback = normalize_config(mw.addonManager.getConfig(_controller.package))
            _require(readback.get("schema_version") == 8, "configuration schema changed")
            _require(readback["heatmap"]["calendar_view"] == "year", "Year view did not save")
            _require(readback == normalize_config(readback), "persisted settings are not normalized")
            REPORT["persistence_write"] = {
                "status": "passed",
                "expected_restart": {
                    "calendar_view": "year",
                    "schema_version": 8,
                    "settings_state": "clean",
                },
            }
        else:
            _require(
                smoke_labels == {"restart-unexcluded"},
                "restart multi-deck new-limit assertion is incomplete",
            )
            _require(
                set(REPORT["captures"]) == {"RUNTIME-RESTART-PERSISTENCE"},
                "restart evidence frame is missing",
            )
        REPORT["status"] = "passed"
        _write_report()
        QTimer.singleShot(450, QApplication.instance().quit)
    except Exception as exc:
        _error("finish-{}".format(STAGE), exc)


def _start_case_matrix() -> None:
    global _cases
    try:
        if STAGE == "restart":
            raw = normalize_config(mw.addonManager.getConfig(_controller.package))
            _require(raw.get("schema_version") == 8, "configuration schema changed after restart")
            _require(raw["heatmap"]["calendar_view"] == "year", "Year view did not persist after restart")
            _require(raw == normalize_config(raw), "Settings state is dirty after restart")
            REPORT["persistence_readback"] = {
                "status": "passed",
                "calendar_view": raw["heatmap"]["calendar_view"],
                "calendar_view_expected": "year",
                "calendar_view_matches_expected": raw["heatmap"]["calendar_view"] == "year",
                "schema_version": raw["schema_version"],
                "settings_state": "clean",
            }
            _cases = [_restart_case(str(raw["heatmap"]["calendar_view"]))]
        else:
            _cases = _build_initial_cases()
            _require(len(_cases) == 55, "native evidence matrix must contain 55 initial frames")
            primary = [case for case in _cases if "primary_native" in case["tags"]]
            _require(len(primary) == 16, "primary matrix must contain exactly 16 distinct frames")
        REPORT["matrix"] = {
            "case_count": len(_cases),
            "primary_count": sum("primary_native" in case["tags"] for case in _cases),
            "case_ids": [case["id"] for case in _cases],
            "all_100_percent": all(case["ui_scale_percent"] == 100 and case["text_scale_percent"] == 100 for case in _cases),
            "host": "actual isolated Anki main Deck Browser",
            "renderer": "exact installed production controller and renderer",
        }
        _write_report()
        QTimer.singleShot(200, _next_case)
    except Exception as exc:
        _error("case-matrix-{}".format(STAGE), exc)


def _begin() -> None:
    global _started, _controller, _live_snapshot
    if not ENABLED or _started:
        return
    if getattr(mw, "col", None) is None or getattr(mw, "deckBrowser", None) is None:
        QTimer.singleShot(250, _begin)
        return
    controller = getattr(mw, "_home_dashboard_overhaul_controller", None)
    if controller is None or controller.snapshot is None:
        QTimer.singleShot(250, _begin)
        return
    _started = True
    try:
        _controller = controller
        _live_snapshot = controller.snapshot
        _identity_gate()
        screen = _qa_screen()
        REPORT["screen"] = {
            "name": screen.name(),
            "available_geometry": [
                screen.availableGeometry().x(),
                screen.availableGeometry().y(),
                screen.availableGeometry().width(),
                screen.availableGeometry().height(),
            ],
            "device_pixel_ratio": screen.devicePixelRatio(),
        }
        _write_report()
        _run_multi_deck_smoke(_start_case_matrix)
    except Exception as exc:
        _error("begin-{}".format(STAGE), exc)


def _profile_opened(*_args: object) -> None:
    QTimer.singleShot(700, _begin)


if ENABLED:
    gui_hooks.profile_did_open.append(_profile_opened)
    QTimer.singleShot(1100, _begin)
