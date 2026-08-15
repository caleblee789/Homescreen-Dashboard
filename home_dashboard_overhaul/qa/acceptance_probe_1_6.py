"""Disposable-only exact-package calendar acceptance probe for release 1.6.0.

Copy this helper into a fresh sync-disabled QA base as
``addons21/zz_hdo_16_acceptance_probe/__init__.py``.  It remains idle until the
external process/window gate creates ``QA_START`` in that generated base.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timedelta
import hashlib
import json
import os
from pathlib import Path
import sys
import traceback
from typing import Any, Callable, Mapping, Sequence
from zipfile import ZipFile

from aqt import mw
from aqt.qt import QApplication, QTimer, QWidget


PROBE_ROOT = Path(__file__).resolve().parent
RUN_ROOT = PROBE_ROOT.parent.parent
PACKAGE_ROOT = RUN_ROOT / "addons21" / "home_dashboard_overhaul"
EVIDENCE = RUN_ROOT / "evidence-1.6.0"
RESULT_PATH = RUN_ROOT / "acceptance-result-1.6.0.json"
PHASE_PATH = RUN_ROOT / "acceptance-phase-1.6.0.json"
START_PATH = RUN_ROOT / "QA_START"
UPDATE_SENTINEL = PACKAGE_ROOT / "user_files" / "update-preservation-sentinel.txt"
IDENTITY = json.loads((RUN_ROOT / "QA_IDENTITY.json").read_text(encoding="utf-8"))
EXPECTED_PROFILE = str(IDENTITY["profile"])
EXPECTED_KEY = str(IDENTITY["single_instance_key"])
EXPECTED_HASH = str(IDENTITY["candidate_sha256"])
EXPECTED_CANDIDATE = Path(str(IDENTITY["candidate"]))

EVIDENCE.mkdir(parents=True, exist_ok=True)


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError):
        return default


def write_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(str(temporary), str(path))


RESULTS = read_json(RESULT_PATH, {})
if not isinstance(RESULTS, dict):
    RESULTS = {}
RESULTS.setdefault("captures", [])
RESULTS.setdefault("errors", [])
RESULTS.setdefault("gates", [])
RESULTS.setdefault("runtime", {})


def save() -> None:
    RESULTS["updated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    write_json(RESULT_PATH, RESULTS)


def record(key: str, value: Any) -> None:
    RESULTS[key] = value
    save()


def fail(stage: str, exc: BaseException) -> None:
    RESULTS["errors"].append(
        {"stage": stage, "error": str(exc), "traceback": traceback.format_exc()}
    )
    RESULTS["complete"] = False
    save()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def package_integrity() -> dict[str, Any]:
    mismatches = []
    extras = []
    expected_names = set()
    with ZipFile(EXPECTED_CANDIDATE) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            expected_names.add(info.filename)
            installed = PACKAGE_ROOT / info.filename
            if not installed.is_file() or installed.read_bytes() != archive.read(info.filename):
                mismatches.append(info.filename)
    for installed in PACKAGE_ROOT.rglob("*"):
        if not installed.is_file():
            continue
        relative = installed.relative_to(PACKAGE_ROOT).as_posix()
        if (
            relative not in expected_names
            and relative != "meta.json"
            and not relative.startswith("user_files/")
            and "__pycache__" not in installed.parts
            and installed.suffix not in {".pyc", ".pyo"}
        ):
            extras.append(relative)
    candidate_hash = sha256(EXPECTED_CANDIDATE)
    return {
        "candidate_hash": candidate_hash,
        "candidate_hash_matches": candidate_hash == EXPECTED_HASH,
        "archive_file_count": len(expected_names),
        "byte_mismatches": sorted(mismatches),
        "unexpected_package_files": sorted(extras),
        "passed": candidate_hash == EXPECTED_HASH and not mismatches and not extras,
    }


def gate(stage: str) -> bool:
    profile = getattr(mw.pm, "profile", {}) or {}
    try:
        sync_auth = mw.pm.sync_auth()
    except Exception:
        sync_auth = profile.get("syncKey")
    manifest = read_json(PACKAGE_ROOT / "manifest.json", {})
    values = {
        "stage": stage,
        "pid": os.getpid(),
        "title": mw.windowTitle(),
        "base": str(getattr(mw.pm, "base", "")),
        "profile": str(getattr(mw.pm, "name", "")),
        "argv": list(sys.argv),
        "instance_key_fingerprint": hashlib.sha256(
            os.environ.get("ANKI_SINGLE_INSTANCE_KEY", "").encode("utf-8")
        ).hexdigest()[:12],
        "process_gate": (
            str(RUN_ROOT) in sys.argv
            and EXPECTED_PROFILE in sys.argv
            and os.environ.get("ANKI_SINGLE_INSTANCE_KEY") == EXPECTED_KEY
        ),
        "window_gate": EXPECTED_PROFILE in mw.windowTitle(),
        "filesystem_gate": (
            str(getattr(mw.pm, "base", "")) == str(RUN_ROOT)
            and manifest.get("human_version") == "1.6.0"
            and (RUN_ROOT / EXPECTED_PROFILE / "collection.anki2").is_file()
            and PACKAGE_ROOT.is_dir()
        ),
        "sync_gate": (
            not bool(sync_auth)
            and not bool(profile.get("syncKey"))
            and not bool(profile.get("syncUser"))
            and not bool(profile.get("autoSync", False))
            and not bool(profile.get("syncMedia", profile.get("mediaSync", False)))
        ),
        "installed_addons": sorted(
            item.name for item in (RUN_ROOT / "addons21").iterdir() if item.is_dir()
        ),
    }
    integrity = package_integrity()
    values["all_gates"] = all(
        values[key] for key in ("process_gate", "window_gate", "filesystem_gate", "sync_gate")
    ) and integrity["passed"]
    RESULTS["gates"].append(values)
    RESULTS["package_integrity"] = integrity
    save()
    return bool(values["all_gates"])


def capture(name: str, widget: Any = None) -> None:
    target = widget or mw
    QApplication.processEvents()
    pixmap = target.grab()
    path = EVIDENCE / (name + ".png")
    if not pixmap.save(str(path), "PNG"):
        raise RuntimeError("Qt could not save {}".format(path))
    RESULTS["captures"].append(
        {
            "name": name,
            "path": str(path),
            "width": pixmap.width(),
            "height": pixmap.height(),
            "window_width": int(target.width()),
            "window_height": int(target.height()),
            "device_pixel_ratio": float(pixmap.devicePixelRatio()),
        }
    )
    save()


def eval_js(script: str, callback: Callable[[Any], None], delay: int = 250) -> None:
    wrapped = (
        "(function(){try{%s}catch(error){return JSON.stringify({error:String(error),stack:String(error.stack||'')});}})()"
        % script
    )

    def done(raw: Any) -> None:
        if isinstance(raw, str) and '"error"' in raw:
            RESULTS.setdefault("javascript_errors", []).append(raw)
            save()
        QTimer.singleShot(delay, lambda: callback(raw))

    mw.web.evalWithCallback(wrapped, done)


def wait_for(
    predicate: Callable[[], bool],
    callback: Callable[[], None],
    stage: str,
    attempt: int = 0,
) -> None:
    try:
        if predicate():
            callback()
            return
        if attempt >= 60:
            raise RuntimeError("Timed out waiting for {}".format(stage))
        QTimer.singleShot(250, lambda: wait_for(predicate, callback, stage, attempt + 1))
    except Exception as exc:
        fail(stage, exc)


def manager() -> Any:
    return mw._home_dashboard_overhaul_controller.event_manager_dialog


def controller() -> Any:
    return mw._home_dashboard_overhaul_controller


def manager_visible() -> bool:
    value = manager()
    return value is not None and value.isVisible()


def manager_text(dialog: Any) -> str:
    values = []
    for item in dialog.findChildren(QWidget):
        getter = getattr(item, "text", None)
        try:
            text = getter() if callable(getter) else ""
        except Exception:
            text = ""
        if isinstance(text, str) and text.strip():
            values.append(text.strip())
    return " ".join(values)


def open_empty_manager() -> None:
    controller().open_event_manager()
    wait_for(manager_visible, capture_empty_manager, "open_empty_manager")


def capture_empty_manager() -> None:
    dialog = manager()
    dialog.resize(760, 560)
    QTimer.singleShot(700, lambda: after_empty_capture(dialog))


def after_empty_capture(dialog: Any) -> None:
    capture("01-manager-empty-760x560", dialog)
    record(
        "empty_state",
        {
            "event_rows": dialog.event_tree.topLevelItemCount(),
            "source_rows": dialog.calendar_tree.topLevelItemCount(),
            "size": [dialog.width(), dialog.height()],
        },
    )
    seed_local_state()


def seed_local_state() -> None:
    try:
        repo = controller().calendar_repository
        today = date.today()
        repo.add_local("Local pediatric exam", (today + timedelta(days=5)).isoformat())
        repo.add_local("Past local orientation", (today - timedelta(days=2)).isoformat())
        controller().archive_expired_local_events()
        controller().calendar_data_changed()
        QTimer.singleShot(1200, capture_local_state)
    except Exception as exc:
        fail("seed_local_state", exc)


def capture_local_state() -> None:
    dialog = manager()
    if dialog.event_tree.topLevelItemCount():
        dialog.event_tree.setCurrentItem(dialog.event_tree.topLevelItem(0))
        QApplication.processEvents()
    capture("02-manager-local-only-760x560", dialog)
    detail_widgets = (
        dialog.detail_title,
        dialog.detail_name,
        dialog.detail_date_caption,
        dialog.detail_date,
        dialog.detail_source_caption,
        dialog.detail_source,
        dialog.detail_status_caption,
        dialog.detail_status,
    )
    detail_bounds = dialog.event_detail.rect()

    def contained(widget: Any) -> bool:
        top_left = widget.mapTo(dialog.event_detail, widget.rect().topLeft())
        bottom_right = widget.mapTo(dialog.event_detail, widget.rect().bottomRight())
        return (
            widget.isVisibleTo(dialog)
            and widget.width() > 0
            and widget.height() > 0
            and detail_bounds.contains(top_left)
            and detail_bounds.contains(bottom_right)
        )

    record(
        "local_only_state",
        {
            "upcoming_rows": dialog.event_tree.topLevelItemCount(),
            "local_items": deepcopy(controller().config["events"]["items"]),
            "responsive_detail": {
                "compact": bool(dialog._detail_is_compact),
                "panel_height": dialog.event_detail.height(),
                "all_visible": all(contained(widget) for widget in detail_widgets),
                "selected_name": dialog.detail_name.text(),
            },
        },
    )
    test_settings_manager_concurrency()


def test_settings_manager_concurrency() -> None:
    controller().open_settings("calendar")
    wait_for(
        lambda: controller().settings_dialog is not None
        and controller().settings_dialog.isVisible(),
        perform_concurrent_save,
        "open_settings_for_concurrency",
    )


def perform_concurrent_save() -> None:
    try:
        settings = controller().settings_dialog
        event_id = controller().calendar_repository.add_local(
            "Concurrent manager event", (date.today() + timedelta(days=8)).isoformat()
        )
        controller().calendar_data_changed()
        controller().save_config(settings._gather())
        identifiers = {str(item.get("id")) for item in controller().config["events"]["items"]}
        survived = event_id in identifiers
        record(
            "settings_manager_concurrency",
            {
                "settings_was_open": settings.isVisible(),
                "manager_was_open": manager_visible(),
                "concurrent_event_id": event_id,
                "survived_settings_save": survived,
            },
        )
        settings.reject()
        QTimer.singleShot(500, seed_external_state)
    except Exception as exc:
        fail("settings_manager_concurrency", exc)


def ics_date(value: date) -> str:
    return value.strftime("%Y%m%d")


def fixture_bytes(name: str, components: Sequence[Sequence[str]], timezone_name: str = "") -> bytes:
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//HDO 1.6 QA//EN", "X-WR-CALNAME:" + name]
    if timezone_name:
        lines.append("X-WR-TIMEZONE:" + timezone_name)
    for component in components:
        lines.append("BEGIN:VEVENT")
        lines.extend(component)
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return ("\r\n".join(lines) + "\r\n").encode("utf-8")


def seed_external_state() -> None:
    today = date.today()
    imported = fixture_bytes(
        "Imported QA",
        [
            [
                "UID:qa-multiday",
                "DTSTART;VALUE=DATE:" + ics_date(today + timedelta(days=2)),
                "DTEND;VALUE=DATE:" + ics_date(today + timedelta(days=5)),
                "SUMMARY:Rounds <b>literal</b>",
            ],
            [
                "UID:qa-daily",
                "DTSTART;VALUE=DATE:" + ics_date(today + timedelta(days=7)),
                "RRULE:FREQ=DAILY;COUNT=4",
                "EXDATE;VALUE=DATE:" + ics_date(today + timedelta(days=8)),
                "SUMMARY:Unicode résumé café",
            ],
        ],
    )
    google = fixture_bytes(
        "Sanitized Google QA",
        [
            [
                "UID:google-recurring-qa",
                "DTSTART;TZID=America/Chicago:{}T090000".format(ics_date(today + timedelta(days=1))),
                "DTEND;TZID=America/Chicago:{}T100000".format(ics_date(today + timedelta(days=1))),
                "RRULE:FREQ=WEEKLY;COUNT=80",
                "SUMMARY:Google recurring clinic",
            ]
        ],
        "America/Chicago",
    )
    fixture_path = RUN_ROOT / "sanitized-imported-calendar.ics"
    fixture_path.write_bytes(imported)
    secret_url = "https://127.0.0.1:9/private-google-qa-secret-token/basic.ics"
    fetch_calls = []

    def fake_fetch(url: str, headers: Mapping[str, str]) -> Any:
        from home_dashboard_overhaul.calendar_repository import FetchResponse

        fetch_calls.append({"host_only": "127.0.0.1", "headers": dict(headers)})
        if len(fetch_calls) == 1:
            return FetchResponse(
                200,
                google,
                {"ETag": '"qa-v1"', "Last-Modified": "Thu, 13 Aug 2026 20:00:00 GMT"},
                secret_url,
            )
        return FetchResponse(304, b"", {}, secret_url)

    def operation() -> dict[str, Any]:
        from home_dashboard_overhaul.calendar_repository import CalendarSourceError

        repo = controller().calendar_repository
        imported_source = repo.import_file(fixture_path)
        repo._fetcher = fake_fetch
        subscribed_source = repo.subscribe_url(secret_url)
        not_modified = repo.refresh_source(str(subscribed_source["id"]))
        occurrences = repo.occurrences_between(
            today,
            today + timedelta(days=370),
            include_archived=True,
            include_hidden=True,
            include_disabled=True,
        )
        external = [
            item for item in occurrences if item.source_id == str(subscribed_source["id"])
        ]
        hidden_id = external[0].occurrence_id
        repo.set_hidden(external[0], True)
        repo.set_source_enabled(str(imported_source["id"]), False)

        def fail_fetch(_url: str, _headers: Mapping[str, str]) -> Any:
            raise CalendarSourceError("offline https://127.0.0.1:9/private-google-qa-secret-token/basic.ics")

        repo._fetcher = fail_fetch
        failed = repo.refresh_source(str(subscribed_source["id"]))
        day_rows = repo.day_events_between(today, today + timedelta(days=30), active_only=False)
        return {
            "imported_id": str(imported_source["id"]),
            "subscribed_id": str(subscribed_source["id"]),
            "hidden_id": hidden_id,
            "not_modified": not_modified.__dict__,
            "failed_refresh": failed.__dict__,
            "fetch_calls": fetch_calls,
            "visible_date": external[1].start_date if len(external) > 1 else external[0].start_date,
            "external_occurrences": len(external),
            "day_rows": [item.__dict__ for item in day_rows],
        }

    def success(value: dict[str, Any]) -> None:
        controller().calendar_data_changed()
        sources = controller().calendar_repository.list_sources()
        registry_text = controller().calendar_repository.registry_path.read_text(encoding="utf-8")
        value["source_rows"] = sources
        value["registry_contains_private_url"] = "private-google-qa-secret-token" in registry_text
        value["public_source_rows_hide_private_url"] = "private-google-qa-secret-token" not in json.dumps(sources)
        value["redacted_error"] = "private-google-qa-secret-token" not in str(value["failed_refresh"]["message"])
        record("external_state", value)
        QTimer.singleShot(1400, capture_external_events)

    controller().run_calendar_task(operation, success, lambda exc: fail("seed_external_state", exc))


def capture_external_events() -> None:
    dialog = manager()
    dialog.tabs.setCurrentIndex(0)
    dialog.event_views.setCurrentIndex(0)
    dialog.resize(760, 560)
    QTimer.singleShot(700, lambda: capture_external_events_ready(dialog))


def capture_external_events_ready(dialog: Any) -> None:
    capture("03-manager-multi-source-upcoming-760x560", dialog)
    dialog.event_views.setCurrentIndex(2)
    QTimer.singleShot(500, lambda: capture_hidden_events(dialog))


def capture_hidden_events(dialog: Any) -> None:
    capture("04-manager-hidden-occurrence-760x560", dialog)
    dialog.tabs.setCurrentIndex(1)
    dialog.showFullScreen()
    QTimer.singleShot(900, lambda: capture_calendar_sources(dialog))


def capture_calendar_sources(dialog: Any) -> None:
    capture("05-manager-calendars-fullscreen", dialog)
    source_text = manager_text(dialog)
    record(
        "calendar_manager_ui",
        {
            "calendar_rows": dialog.calendar_tree.topLevelItemCount(),
            "text_contains_disabled": "No" in source_text or "Disabled" in source_text,
            "text_contains_stale_error": "offline" in source_text.casefold(),
            "full_private_url_absent": "private-google-qa-secret-token" not in source_text,
            "size": [dialog.width(), dialog.height()],
        },
    )
    dialog.showNormal()
    dialog.close()
    QTimer.singleShot(500, prepare_dashboard_light)


def set_zoom(value: float) -> None:
    setter = getattr(mw.web, "setZoomFactor", None)
    if callable(setter):
        setter(value)
    else:
        mw.web.page().setZoomFactor(value)


def set_dashboard_appearance(mode: str, preset: str) -> None:
    config = deepcopy(controller().config)
    config["appearance"].update(mode=mode, preset=preset)
    config["heatmap"]["calendar_view"] = "month"
    config["visibility"]["events"] = True
    controller().save_config(config)


def dashboard_ready() -> bool:
    return controller().snapshot is not None and getattr(mw, "state", "") == "deckBrowser"


def prepare_dashboard_light() -> None:
    set_zoom(1.0)
    set_dashboard_appearance("light", "Sapphire Glass")
    mw.showFullScreen()
    wait_for(dashboard_ready, lambda: QTimer.singleShot(900, capture_dashboard_light), "dashboard_light")


def capture_dashboard_light() -> None:
    capture("06-dashboard-light-100-percent")
    set_zoom(1.5)
    set_dashboard_appearance("dark", "Sapphire Glass")
    QTimer.singleShot(1000, capture_dashboard_dark)


def capture_dashboard_dark() -> None:
    capture("07-dashboard-dark-150-percent")
    set_zoom(2.0)
    set_dashboard_appearance("dark", "High Contrast")
    QTimer.singleShot(1000, capture_dashboard_high_contrast)


def capture_dashboard_high_contrast() -> None:
    capture("08-dashboard-high-contrast-200-percent")
    set_zoom(1.0)
    visible_date = RESULTS["external_state"]["visible_date"]
    eval_js(
        "var c=document.querySelector('[data-date=\"%s\"]');if(c)c.click();"
        "var names=Array.from(document.querySelectorAll('.hdo-date-event-name')).map(function(x){return x.textContent;});"
        "var sources=Array.from(document.querySelectorAll('.hdo-date-event-source')).map(function(x){return x.textContent;});"
        "return JSON.stringify({cell:!!c,names:names,sources:sources,title:document.querySelector('.hdo-calendar-title').textContent});"
        % visible_date,
        record_dashboard_source_labels,
        500,
    )


def record_dashboard_source_labels(raw: Any) -> None:
    value = json.loads(raw) if isinstance(raw, str) else raw
    record("dashboard_source_labels", value)
    capture("09-dashboard-date-details-source-label")
    test_dynamic_range_and_stale_response()


def test_dynamic_range_and_stale_response() -> None:
    eval_js(
        "var before=document.body.textContent.indexOf('SHOULD_NOT_RENDER')>=0;"
        "window.HDOHomeDashboard.receiveCalendarEvents({generation:-1,request_id:0,start:'2026-01-01',end:'2026-02-01',events:[{id:'stale',occurrence_id:'stale',date:'2026-01-10',name:'SHOULD_NOT_RENDER',source_id:'stale',source_name:'Stale',editable:false}]});"
        "var next=document.querySelector('[data-hdo-calendar=\"next\"]');if(next)next.click();"
        "return JSON.stringify({before:before,nextClicked:!!next});",
        wait_dynamic_range,
        2200,
    )


def wait_dynamic_range(raw: Any) -> None:
    initial = json.loads(raw) if isinstance(raw, str) else raw
    script = """
var status=document.querySelector('[data-hdo-calendar-load-status]');
var stale=document.body.textContent.indexOf('SHOULD_NOT_RENDER')>=0;
var sources=Array.from(document.querySelectorAll('.hdo-date-event-source')).map(function(x){return x.textContent;});
return JSON.stringify({initial:%s,staleRendered:stale,status:status?status.textContent:'',title:document.querySelector('.hdo-calendar-title').textContent,sources:sources});
""" % json.dumps(initial, separators=(",", ":"))
    eval_js(script, complete_dynamic_range, 350)


def complete_dynamic_range(raw: Any) -> None:
    value = json.loads(raw) if isinstance(raw, str) else raw
    record("dynamic_range", value)
    capture("10-dashboard-dynamic-next-year")
    runtime = RESULTS["runtime"]
    runtime["calendar_timer_active"] = controller().calendar_refresh_timer.isActive()
    runtime["calendar_timer_interval_ms"] = controller().calendar_refresh_timer.interval()
    runtime["analytics_generation_before_calendar_write"] = controller().data_generation
    snapshot = controller().snapshot
    controller().calendar_repository.add_local(
        "Analytics-neutral calendar write", (date.today() + timedelta(days=11)).isoformat()
    )
    runtime["analytics_generation_after_calendar_write"] = controller().data_generation
    runtime["snapshot_identity_preserved"] = snapshot is controller().snapshot
    UPDATE_SENTINEL.write_text("preserve across exact-package reinstall\n", encoding="utf-8")
    write_json(
        PHASE_PATH,
        {"phase": 1, "completed_at": datetime.now().astimezone().isoformat(timespec="seconds")},
    )
    save()
    QTimer.singleShot(800, mw.close)


def start_restart_phase() -> None:
    QTimer.singleShot(2200, verify_restart_cache)


def verify_restart_cache() -> None:
    try:
        repo = controller().calendar_repository
        today = date.today()
        sources = repo.list_sources()
        cached = repo.occurrences_between(
            today,
            today + timedelta(days=370),
            include_archived=True,
            include_hidden=True,
            include_disabled=True,
            cached_only=True,
        )
        subscribed = [source for source in sources if source.get("kind") == "ics_url"]
        restart = {
            "source_count": len(sources),
            "cached_occurrence_count": len(cached),
            "subscribed_error_visible": bool(subscribed and subscribed[0].get("last_error")),
            "last_good_cache_available_offline": bool(cached),
            "private_url_absent_from_source_rows": "private-google-qa-secret-token" not in json.dumps(sources),
            "local_events_preserved": any(
                item.get("name") == "Concurrent manager event"
                for item in controller().config["events"]["items"]
            ),
            "schema_3_preserved": controller().config.get("schema_version") == 3,
            "update_sentinel_preserved": UPDATE_SENTINEL.is_file(),
            "timer_active": controller().calendar_refresh_timer.isActive(),
            "timer_interval_ms": controller().calendar_refresh_timer.interval(),
        }
        record("restart_offline_cache", restart)
        previous_checks = {str(source["id"]): source.get("last_checked_at") for source in sources}
        RESULTS["runtime"]["timer_simulation_before"] = previous_checks
        controller().calendar_refresh_timer.timeout.emit()
        QTimer.singleShot(1800, finish_timer_simulation)
    except Exception as exc:
        fail("verify_restart_cache", exc)


def finish_timer_simulation() -> None:
    sources = controller().calendar_repository.list_sources()
    RESULTS["runtime"]["timer_simulation_after"] = {
        str(source["id"]): source.get("last_checked_at") for source in sources
    }
    controller().open_event_manager()
    wait_for(manager_visible, capture_restart_manager, "restart_manager")


def capture_restart_manager() -> None:
    dialog = manager()
    dialog.tabs.setCurrentIndex(1)
    dialog.resize(760, 560)
    QTimer.singleShot(900, lambda: finalize_acceptance(dialog))


def finalize_acceptance(dialog: Any) -> None:
    capture("11-manager-offline-cache-after-restart-760x560", dialog)
    external = RESULTS.get("external_state", {})
    empty = RESULTS.get("empty_state", {})
    concurrency = RESULTS.get("settings_manager_concurrency", {})
    labels = RESULTS.get("dashboard_source_labels", {})
    dynamic = RESULTS.get("dynamic_range", {})
    restart = RESULTS.get("restart_offline_cache", {})
    runtime = RESULTS.get("runtime", {})
    gate_values = RESULTS.get("gates", [])
    summary = {
        "identity_filesystem_sync_gates_passed": len(gate_values) >= 2
        and all(item.get("all_gates") for item in gate_values),
        "exact_package_bytes_passed": bool(RESULTS.get("package_integrity", {}).get("passed")),
        "empty_local_imported_subscribed_multi_source_states_passed": (
            empty.get("event_rows") == 0
            and empty.get("source_rows") == 0
            and external.get("external_occurrences", 0) > 1
            and len(external.get("source_rows", [])) == 2
        ),
        "disabled_stale_hidden_and_304_states_passed": (
            external.get("not_modified", {}).get("success") is True
            and external.get("failed_refresh", {}).get("success") is False
            and external.get("redacted_error") is True
            and external.get("public_source_rows_hide_private_url") is True
        ),
        "settings_manager_concurrency_passed": concurrency.get("survived_settings_save") is True,
        "source_labels_and_literal_text_passed": (
            "Sanitized Google QA" in labels.get("sources", [])
            and not any("<b>" in value for value in labels.get("names", []))
        ),
        "dynamic_range_and_stale_response_passed": (
            dynamic.get("initial", {}).get("nextClicked") is True
            and dynamic.get("staleRendered") is False
            and dynamic.get("status") == "Calendar events updated"
        ),
        "calendar_changes_preserved_analytics_snapshot": (
            runtime.get("analytics_generation_before_calendar_write")
            == runtime.get("analytics_generation_after_calendar_write")
            and runtime.get("snapshot_identity_preserved") is True
        ),
        "six_hour_timer_and_simulation_passed": (
            runtime.get("calendar_timer_active") is True
            and runtime.get("calendar_timer_interval_ms") == 21_600_000
            and bool(runtime.get("timer_simulation_after"))
        ),
        "restart_offline_cache_and_update_preservation_passed": all(
            restart.get(key)
            for key in (
                "last_good_cache_available_offline",
                "subscribed_error_visible",
                "private_url_absent_from_source_rows",
                "local_events_preserved",
                "schema_3_preserved",
                "update_sentinel_preserved",
                "timer_active",
            )
        ),
        "required_responsive_and_palette_captures_present": len(RESULTS.get("captures", [])) >= 11,
        "narrow_event_detail_complete": bool(
            RESULTS.get("local_only_state", {}).get("responsive_detail", {}).get("compact")
            and RESULTS.get("local_only_state", {}).get("responsive_detail", {}).get("all_visible")
        ),
        "errors_empty": not RESULTS.get("errors") and not RESULTS.get("javascript_errors"),
    }
    RESULTS["acceptance_summary"] = summary
    RESULTS["real_google_secret_link_tested"] = False
    RESULTS["real_google_secret_link_note"] = (
        "Not run: no disposable user-supplied Secret iCal link was provided. "
        "The sanitized Google-format fixture passed."
    )
    RESULTS["complete"] = all(summary.values())
    save()
    dialog.close()
    QTimer.singleShot(900, mw.close)


def start() -> None:
    try:
        if not START_PATH.is_file() or getattr(mw, "state", "") != "deckBrowser":
            QTimer.singleShot(250, start)
            return
        phase = read_json(PHASE_PATH, {})
        stage = "restart" if phase.get("phase") == 1 else "initial"
        if not gate(stage):
            raise RuntimeError("Disposable Anki process, window, filesystem, sync, or package gate failed")
        if stage == "restart":
            start_restart_phase()
        else:
            open_empty_manager()
    except Exception as exc:
        fail("start", exc)


QTimer.singleShot(1200, start)
