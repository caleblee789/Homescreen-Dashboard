"""Disposable exact-package probe for the deferred calendar-source boundary.

Copy only into a fresh sync-disabled QA base. The probe verifies the four
isolation gates, exact installed package bytes, absence of deferred calendar
runtime/UI contracts, and presence of the existing local Events settings page.
It leaves the disposable settings window open for visual inspection.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import sys
import traceback
from typing import Any
from zipfile import ZipFile

from aqt import mw
from aqt.qt import QApplication, QTimer


PROBE_ROOT = Path(__file__).resolve().parent
RUN_ROOT = PROBE_ROOT.parent.parent
PACKAGE_ROOT = RUN_ROOT / "addons21" / "home_dashboard_overhaul"
IDENTITY_PATH = RUN_ROOT / "QA_IDENTITY.json"
RESULT_PATH = RUN_ROOT / "acceptance-result-1.5.0-calendar-hidden.json"
SCREENSHOT_PATH = RUN_ROOT / "events-settings-local-only.png"
IDENTITY = json.loads(IDENTITY_PATH.read_text(encoding="utf-8"))
EXPECTED_PROFILE = str(IDENTITY["profile"])
EXPECTED_KEY = str(IDENTITY["single_instance_key"])
EXPECTED_HASH = str(IDENTITY["candidate_sha256"])
EXPECTED_CANDIDATE = Path(IDENTITY["candidate"])
EXCLUDED_PID = int(os.environ.get("HDO_QA_EXCLUDED_PID", "0") or 0)


def write_result(value: dict[str, Any]) -> None:
    temporary = RESULT_PATH.with_suffix(RESULT_PATH.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(str(temporary), str(RESULT_PATH))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def package_integrity() -> dict[str, Any]:
    mismatches = []
    archive_names = []
    forbidden_files = {
        "calendar_manager_model.py",
        "calendar_models.py",
        "calendar_repository.py",
        "event_manager.py",
        "vendor-requirements.lock",
    }
    forbidden_needles = (
        "CalendarRepository",
        "EventManagerDialog",
        "calendar_events_range",
        "receiveCalendarEvents",
        "Manage events & calendars",
        "calendar_sources.json",
        "recurring_ical_events",
    )
    text_hits: dict[str, list[str]] = {needle: [] for needle in forbidden_needles}
    with ZipFile(EXPECTED_CANDIDATE) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            archive_names.append(info.filename)
            installed = PACKAGE_ROOT / info.filename
            data = archive.read(info.filename)
            if not installed.is_file() or installed.read_bytes() != data:
                mismatches.append(info.filename)
            text = data.decode("utf-8", "ignore")
            for needle in forbidden_needles:
                if needle in text:
                    text_hits[needle].append(info.filename)
    deferred_entries = sorted(
        name
        for name in archive_names
        if name in forbidden_files or name.startswith("_vendor/")
    )
    digest = sha256(EXPECTED_CANDIDATE)
    return {
        "archive_file_count": len(archive_names),
        "candidate_hash": digest,
        "candidate_hash_matches": digest == EXPECTED_HASH,
        "byte_mismatches": sorted(mismatches),
        "deferred_entries": deferred_entries,
        "deferred_text_hits": text_hits,
        "passed": (
            digest == EXPECTED_HASH
            and not mismatches
            and not deferred_entries
            and not any(text_hits.values())
        ),
    }


def action_texts(menu: Any) -> list[str]:
    if menu is None:
        return []
    result = []
    for action in menu.actions():
        try:
            result.append(str(action.text()))
        except Exception:
            pass
    return result


def isolation_gates() -> dict[str, Any]:
    profile = getattr(mw.pm, "profile", {}) or {}
    try:
        sync_auth = mw.pm.sync_auth()
    except Exception:
        sync_auth = profile.get("syncKey")
    excluded_alive = False
    if EXCLUDED_PID > 0:
        try:
            os.kill(EXCLUDED_PID, 0)
            excluded_alive = True
        except OSError:
            pass
    manifest = json.loads((PACKAGE_ROOT / "manifest.json").read_text(encoding="utf-8"))
    result = {
        "pid": os.getpid(),
        "excluded_pid": EXCLUDED_PID,
        "excluded_pid_unchanged_and_running": excluded_alive,
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
            and os.getpid() != EXCLUDED_PID
        ),
        "window_gate": EXPECTED_PROFILE in mw.windowTitle(),
        "filesystem_gate": (
            str(getattr(mw.pm, "base", "")) == str(RUN_ROOT)
            and manifest.get("human_version") == "1.5.0"
            and PACKAGE_ROOT.is_dir()
        ),
        "sync_gate": (
            not bool(sync_auth)
            and not bool(profile.get("syncKey"))
            and not bool(profile.get("syncUser"))
            and not bool(profile.get("autoSync", False))
            and not bool(profile.get("mediaSync", False))
        ),
    }
    result["all_gates"] = all(
        result[key]
        for key in ("process_gate", "window_gate", "filesystem_gate", "sync_gate")
    ) and excluded_alive
    return result


def dashboard_probe(callback: Any, attempt: int = 0) -> None:
    script = r"""
(function(){
  var root=document.getElementById('hdo-dashboard');
  if(!root){return JSON.stringify({ready:false,text:document.body.innerText||''});}
  var payloadNode=document.querySelector('.hdo-calendar-data');
  var payload=payloadNode?JSON.parse(payloadNode.textContent):{};
  var text=root.innerText||'';
  return JSON.stringify({
    ready:true,
    hasTodayProgress:text.toLocaleLowerCase().indexOf("today’s progress")>=0,
    hasLocalEvent:((payload.events||[]).some(function(item){return item.name==="Disposable local event";})),
    eventKeys:(payload.events&&payload.events[0])?Object.keys(payload.events[0]).sort():[],
    hasExternalCopy:/Event Manager|Manage events & calendars|Refresh calendar|Calendar source/i.test(text),
    sourceLabelNodes:root.querySelectorAll('[data-hdo-event-source],.hdo-date-event-source').length
  });
})()
"""

    def received(raw: Any) -> None:
        try:
            value = json.loads(str(raw)) if isinstance(raw, str) else {}
        except (TypeError, ValueError):
            value = {}
        if not value.get("ready") and attempt < 30:
            QTimer.singleShot(250, lambda: dashboard_probe(callback, attempt + 1))
            return
        callback(value)

    mw.web.evalWithCallback(script, received)


def inspect_settings(result: dict[str, Any]) -> None:
    try:
        controller = mw._home_dashboard_overhaul_controller
        dialog = controller.settings_dialog
        nav = [dialog.nav.item(row).text() for row in range(dialog.nav.count())]
        headers = [
            dialog.active_events.headerItem().text(column)
            for column in range(dialog.active_events.columnCount())
        ]
        window_titles = [
            widget.windowTitle()
            for widget in QApplication.topLevelWidgets()
            if widget.isVisible()
        ]
        settings_checks = {
            "window_title": dialog.windowTitle(),
            "object_name": dialog.objectName(),
            "navigation": nav,
            "selected_page": dialog.nav.currentItem().text(),
            "event_headers": headers,
            "event_tabs": [dialog.event_tabs.tabText(0), dialog.event_tabs.tabText(1)],
            "local_event_present": dialog.active_events.topLevelItemCount() == 1,
            "event_manager_window_absent": not any(
                "Event Manager" in title for title in window_titles
            ),
            "calendars_tab_absent": "Calendars" not in nav,
        }
        settings_checks["passed"] = (
            settings_checks["window_title"] == "Home Dashboard - Overhaul settings"
            and settings_checks["object_name"] == "HomeDashboardSettings"
            and settings_checks["navigation"]
            == ["Appearance", "Dashboard", "Calendar", "Events", "Bible Verse", "About & Credits"]
            and settings_checks["selected_page"] == "Events"
            and settings_checks["event_headers"] == ["Date", "Event", "Status"]
            and settings_checks["local_event_present"]
            and settings_checks["event_manager_window_absent"]
            and settings_checks["calendars_tab_absent"]
        )
        result["settings_checks"] = settings_checks
        pixmap = dialog.grab()
        result["screenshot_saved"] = bool(pixmap.save(str(SCREENSHOT_PATH), "PNG"))
    except Exception as exc:
        result.setdefault("errors", []).append(
            {"stage": "settings", "error": str(exc), "traceback": traceback.format_exc()}
        )
    result["complete"] = (
        result.get("gates", {}).get("all_gates") is True
        and result.get("package_integrity", {}).get("passed") is True
        and result.get("runtime_checks", {}).get("passed") is True
        and result.get("dashboard_checks", {}).get("passed") is True
        and result.get("settings_checks", {}).get("passed") is True
        and result.get("screenshot_saved") is True
        and not result.get("errors")
    )
    result["finished_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    write_result(result)


def open_settings(result: dict[str, Any]) -> None:
    controller = mw._home_dashboard_overhaul_controller
    controller.open_settings("events", datetime.now().astimezone().date().isoformat())
    QTimer.singleShot(900, lambda: inspect_settings(result))


def after_dashboard(result: dict[str, Any], dashboard: dict[str, Any]) -> None:
    dashboard["passed"] = (
        dashboard.get("ready") is True
        and dashboard.get("hasTodayProgress") is True
        and dashboard.get("hasLocalEvent") is True
        and dashboard.get("eventKeys") == ["date", "id", "name"]
        and dashboard.get("hasExternalCopy") is False
        and dashboard.get("sourceLabelNodes") == 0
    )
    result["dashboard_checks"] = dashboard
    open_settings(result)


def start() -> None:
    if getattr(mw, "state", "") != "deckBrowser":
        QTimer.singleShot(250, start)
        return
    result: dict[str, Any] = {"errors": [], "started_at": datetime.now().astimezone().isoformat(timespec="seconds")}
    try:
        result["gates"] = isolation_gates()
        result["package_integrity"] = package_integrity()
        controller = mw._home_dashboard_overhaul_controller
        menu_actions = action_texts(getattr(mw, "_caleb_m_addons_menu", None))
        runtime_checks = {
            "controller_loaded": controller is not None,
            "schema_version": controller.config.get("schema_version"),
            "calendar_repository_absent": not hasattr(controller, "calendar_repository"),
            "event_manager_dialog_absent": not hasattr(controller, "event_manager_dialog"),
            "event_manager_action_absent": not hasattr(
                mw, "_home_dashboard_overhaul_event_manager_action"
            ),
            "menu_actions": menu_actions,
            "settings_action_present": "Home Dashboard - Overhaul settings" in menu_actions,
            "external_menu_action_absent": "Manage events & calendars" not in menu_actions,
        }
        runtime_checks["passed"] = (
            runtime_checks["controller_loaded"]
            and runtime_checks["schema_version"] == 3
            and runtime_checks["calendar_repository_absent"]
            and runtime_checks["event_manager_dialog_absent"]
            and runtime_checks["event_manager_action_absent"]
            and runtime_checks["settings_action_present"]
            and runtime_checks["external_menu_action_absent"]
        )
        result["runtime_checks"] = runtime_checks
        config = deepcopy(controller.config)
        config["events"]["items"] = [
            {
                "id": "qa-local-event",
                "name": "Disposable local event",
                "date": datetime.now().astimezone().date().isoformat(),
                "archived": False,
                "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                "archived_at": "",
            }
        ]
        controller.save_config(config)
        QTimer.singleShot(900, lambda: dashboard_probe(lambda value: after_dashboard(result, value)))
    except Exception as exc:
        result["errors"].append(
            {"stage": "start", "error": str(exc), "traceback": traceback.format_exc()}
        )
        result["complete"] = False
        write_result(result)


QTimer.singleShot(2400, start)
