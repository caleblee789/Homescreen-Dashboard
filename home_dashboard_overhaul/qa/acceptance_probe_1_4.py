"""Disposable-only exact-package acceptance probe for Home Dashboard 1.4.0.

This helper is intentionally not shipped in the add-on archive.  Copy it into a
fresh sync-disabled QA base as ``addons21/zz_hdo_14_acceptance_probe/__init__.py``.
It seeds synthetic collection data, exercises the 9-to-10 answer ETA boundary,
captures the responsive dashboard surfaces, verifies package bytes, and exits.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, time as datetime_time, timedelta
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import traceback
from typing import Any, Callable, Optional
from zipfile import ZipFile

from aqt import mw
from aqt.qt import QApplication, QTimer, QWidget


PROBE_ROOT = Path(__file__).resolve().parent
RUN_ROOT = PROBE_ROOT.parent.parent
EVIDENCE = RUN_ROOT / "evidence"
RESULT_PATH = RUN_ROOT / "acceptance-result-1.4.0.json"
PHASE_PATH = RUN_ROOT / "acceptance-phase-1.4.0.json"
SEED_MARKER = RUN_ROOT / "synthetic-eta-buried-fixture.json"
IDENTITY_PATH = RUN_ROOT / "QA_IDENTITY.json"
PACKAGE_ROOT = RUN_ROOT / "addons21" / "home_dashboard_overhaul"
IDENTITY = json.loads(IDENTITY_PATH.read_text(encoding="utf-8"))
EXPECTED_PROFILE = str(IDENTITY["profile"])
EXPECTED_KEY = str(IDENTITY["single_instance_key"])
EXPECTED_HASH = str(IDENTITY["candidate_sha256"])
EXPECTED_CANDIDATE = Path(IDENTITY["candidate"])
EXCLUDED_PID = int(os.environ.get("HDO_QA_EXCLUDED_PID", "0") or 0)

EVIDENCE.mkdir(parents=True, exist_ok=True)


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError):
        return default


RESULTS = read_json(RESULT_PATH, {})
if not isinstance(RESULTS, dict):
    RESULTS = {}
RESULTS.setdefault("captures", [])
RESULTS.setdefault("errors", [])
RESULTS.setdefault("gates", [])
RESULTS.setdefault("metrics", {})
RESULTS["candidate_sha256"] = EXPECTED_HASH
RESULTS["current_pid"] = os.getpid()


def write_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(str(temporary), str(path))


def save() -> None:
    RESULTS["updated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    write_json(RESULT_PATH, RESULTS)


def record(name: str, value: Any) -> None:
    RESULTS[name] = value
    save()


def fail(stage: str, exc: Any) -> None:
    RESULTS["errors"].append(
        {"stage": stage, "error": str(exc), "traceback": traceback.format_exc()}
    )
    save()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def package_integrity() -> dict[str, Any]:
    candidate_hash = sha256(EXPECTED_CANDIDATE)
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
        if relative not in expected_names and relative not in {
            "meta.json",
            "user_files/rotation_state.json",
        } and "__pycache__" not in installed.parts:
            extras.append(relative)
    return {
        "candidate_hash": candidate_hash,
        "candidate_hash_matches": candidate_hash == EXPECTED_HASH,
        "archive_file_count": len(expected_names),
        "byte_mismatches": sorted(mismatches),
        "unexpected_files": sorted(extras),
        "passed": candidate_hash == EXPECTED_HASH and not mismatches and not extras,
    }


def gate(stage: str) -> bool:
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
    manifest = read_json(PACKAGE_ROOT / "manifest.json", {})
    values = {
        "stage": stage,
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
            and manifest.get("human_version") == "1.4.0"
            and PACKAGE_ROOT.is_dir()
        ),
        "sync_gate": (
            not bool(sync_auth)
            and not bool(profile.get("syncKey"))
            and not bool(profile.get("syncUser"))
            and not bool(profile.get("autoSync", False))
            and not bool(profile.get("mediaSync", False))
        ),
        "installed_addons": sorted(
            item.name for item in (RUN_ROOT / "addons21").iterdir() if item.is_dir()
        ),
    }
    values["all_gates"] = all(
        values[key]
        for key in ("process_gate", "window_gate", "filesystem_gate", "sync_gate")
    ) and excluded_alive
    RESULTS["gates"].append(values)
    RESULTS["package_integrity"] = package_integrity()
    save()
    return bool(values["all_gates"] and RESULTS["package_integrity"]["passed"])


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


def eval_js(script: str, callback: Callable[[Any], None], delay: int = 300) -> None:
    wrapped = """(function(){try{%s}catch(error){return JSON.stringify({error:String(error),stack:String(error.stack||'')});}})()""" % script

    def done(raw: Any) -> None:
        if isinstance(raw, str) and '"error"' in raw:
            RESULTS.setdefault("javascript_errors", []).append(raw)
            save()
        QTimer.singleShot(delay, lambda: callback(raw))

    mw.web.evalWithCallback(wrapped, done)


def dashboard_metrics(label: str, callback: Callable[[], None]) -> None:
    script = r"""
var root=document.getElementById('hdo-dashboard');
var region=root&&root.querySelector('.hdo-calendar-region');
var groups=root?Array.from(root.querySelectorAll('.hdo-stat-group')):[];
var groupGrid=root&&root.querySelector('.hdo-stat-groups');
var today=root&&root.querySelector('#hdo-today-title');
var todayGroup=today&&today.closest('.hdo-stat-group');
var todayStats=todayGroup?Array.from(todayGroup.querySelectorAll('.hdo-stat')):[];
var valueFor=function(label){
  var stat=todayStats.find(function(item){return item.querySelector('dt').textContent.trim()===label;});
  return stat?stat.querySelector('dd').textContent.trim():'';
};
var groupRects=groups.map(function(group){var r=group.getBoundingClientRect();return {title:group.querySelector('h3').textContent.trim(),left:Math.round(r.left),top:Math.round(r.top),right:Math.round(r.right),bottom:Math.round(r.bottom)};});
var clipping=groups.some(function(group){return group.scrollWidth>group.clientWidth+1||group.scrollHeight>group.clientHeight+1;});
var result={
  innerWidth:window.innerWidth,
  innerHeight:window.innerHeight,
  documentClientWidth:document.documentElement.clientWidth,
  documentScrollWidth:document.documentElement.scrollWidth,
  horizontalOverflow:document.documentElement.scrollWidth>document.documentElement.clientWidth+1,
  view:region&&region.dataset.hdoCalendarView,
  presentation:region&&region.dataset.hdoDetailsPresentation,
  groupCount:groups.length,
  groupTitles:groups.map(function(group){return group.querySelector('h3').textContent.trim();}),
  groupRects:groupRects,
  groupGridColumns:groupGrid?getComputedStyle(groupGrid).gridTemplateColumns:'',
  groupClipping:clipping,
  todayMetricCount:todayStats.length,
  todayVisualRows:new Set(todayStats.map(function(item){return Math.round(item.getBoundingClientRect().top);})).size,
  todayLabels:todayStats.map(function(item){return item.querySelector('dt').textContent.trim();}),
  todayValue:valueFor('Total Cards Studied'),
  newCardsStudiedValue:valueFor('New Cards Studied'),
  paceValue:valueFor('Pace'),
  etaValue:valueFor('ETA'),
  buriedLabels:(root?Array.from(root.querySelectorAll('#hdo-buried-title + dl dt')):[]).map(function(item){return item.textContent.trim();}),
  statValuesVisible:groups.every(function(group){return Array.from(group.querySelectorAll('dd')).every(function(value){var r=value.getBoundingClientRect();var g=group.getBoundingClientRect();return r.left>=g.left-1&&r.right<=g.right+1&&r.bottom<=g.bottom+1;});})
};
return JSON.stringify(result);
"""

    def complete(raw: Any) -> None:
        try:
            value = json.loads(raw) if isinstance(raw, str) else raw
        except (TypeError, ValueError):
            value = {"raw": raw}
        RESULTS["metrics"][label] = value
        save()
        callback()

    eval_js(script, complete, 100)


def new_card(label: str, sequence: int) -> int:
    notetype = mw.col.models.current()
    if not notetype:
        raise RuntimeError("Disposable collection has no current note type")
    note = mw.col.new_note(notetype)
    note.fields[0] = "{} {:04d}".format(label, sequence)
    if len(note.fields) > 1:
        note.fields[1] = "Synthetic Home Dashboard 1.4 exact-package fixture"
    note.tags.append("hdo_14_acceptance")
    mw.col.add_note(note, 1)
    card_id = mw.col.db.scalar(
        "SELECT id FROM cards WHERE nid = ? ORDER BY ord LIMIT 1", note.id
    )
    if not card_id:
        raise RuntimeError("Anki did not create a card for synthetic note {}".format(note.id))
    return int(card_id)


def set_card(card_id: int, queue: int, card_type: int, due: int, left: int = 0) -> None:
    mw.col.db.execute(
        "UPDATE cards SET queue=?, type=?, due=?, ivl=?, factor=2500, reps=?, lapses=?, left=? WHERE id=?",
        queue,
        card_type,
        due,
        30 if card_type == 2 else 0,
        12 if card_type == 2 else 1,
        1 if card_type in (2, 3) else 0,
        left,
        card_id,
    )


def seed_collection() -> None:
    if SEED_MARKER.exists():
        refresh_dashboard(lambda: wait_for_answers(10, restart_ready))
        return
    try:
        scheduler_today = int(mw.col.sched.today)
        sequence = 0

        for _index in range(4):
            sequence += 1
            new_card("Active new", sequence)
        for _index in range(2):
            sequence += 1
            card_id = new_card("Active learning", sequence)
            set_card(card_id, 1, 1, int(time.time()) - 60, 1001)
        for _index in range(6):
            sequence += 1
            card_id = new_card("Active review", sequence)
            set_card(card_id, 2, 2, scheduler_today)

        buried_specs = [
            (-2, 0), (-2, 0), (-3, 0),
            (-2, 1), (-3, 1), (-3, 3),
            (-2, 2), (-3, 2),
        ]
        for queue, card_type in buried_specs:
            sequence += 1
            card_id = new_card("Buried", sequence)
            set_card(card_id, queue, card_type, scheduler_today, 1001 if card_type in (1, 3) else 0)
        for card_type in (0, 1, 2, 3):
            sequence += 1
            card_id = new_card("Suspended exclusion", sequence)
            set_card(card_id, -1, card_type, scheduler_today, 1001 if card_type in (1, 3) else 0)

        sequence += 1
        history_card = new_card("History", sequence)
        set_card(history_card, 2, 2, scheduler_today + 100)
        history_new_cards = []
        for _index in range(3):
            sequence += 1
            card_id = new_card("Historical first answer", sequence)
            set_card(card_id, 2, 2, scheduler_today + 100)
            history_new_cards.append(card_id)

        rows = []
        row_id = int(datetime.combine(date.today() - timedelta(days=3), datetime_time(hour=12)).astimezone().timestamp() * 1000)
        for index in range(10):
            rows.append((row_id + index, history_card, -1, 3, 30, 29, 2500, 30000, 1))
        for offset, duration in ((1, 60000), (2, 90000)):
            old_id = int(datetime.combine(date.today() - timedelta(days=offset), datetime_time(hour=13)).astimezone().timestamp() * 1000)
            rows.append((old_id, history_new_cards[offset - 1], -1, 3, 30, 0, 2500, duration, 0))

        today_base = int((datetime.now().astimezone() - timedelta(minutes=20)).timestamp() * 1000)
        rows.append((today_base, history_new_cards[2], -1, 3, 30, 0, 2500, 10000, 0))
        for index in range(1, 9):
            rows.append((today_base + index, history_card, -1, 3, 30, 29, 2500, 10000, 1))
        rows.append((today_base + 50, history_card, -1, 0, 0, 0, 0, 999999, 4))
        mw.col.db.executemany(
            "INSERT INTO revlog (id,cid,usn,ease,ivl,lastIvl,factor,time,type) VALUES (?,?,?,?,?,?,?,?,?)",
            rows,
        )
        try:
            mw.col.save()
        except Exception:
            pass

        controller = mw._home_dashboard_overhaul_controller
        config = deepcopy(controller.config)
        config["appearance"].update(
            preset="Sapphire Glass", mode="dark", density="compact", text_scale=100
        )
        config["study"].update(pace_unit="seconds_per_card", show_eta=True)
        config["new_cards"].update(include_rescheduled=True)
        config["heatmap"].update(
            calendar_view="year", week_start=0, history_days=0,
            forecast_days=90, show_due_forecast=True,
        )
        today_iso = date.today().isoformat()
        config["events"]["items"] = [
            {"id": "qa-1", "name": "Pediatric NBME", "date": today_iso, "archived": False},
            {"id": "qa-2", "name": "Question-bank checkpoint", "date": today_iso, "archived": False},
            {"id": "qa-3", "name": "Review weak topics", "date": today_iso, "archived": False},
            {"id": "qa-4", "name": "A deliberately long fourth event", "date": today_iso, "archived": False},
        ]
        controller.save_config(config)
        marker = {
            "synthetic": True,
            "initial_valid_answers_today": 9,
            "historical_valid_answers": 12,
            "invalid_manual_reschedule_rows": 1,
            "expected_at_9": {
                "new_cards_studied": 1,
                "buried": {"new": 3, "learning": 3, "review": 2},
                "remaining": {"new": 4, "learning": 2, "review": 6, "total": 12},
                "duration_seconds": 420,
            },
            "expected_at_10": {"duration_seconds": 300},
        }
        write_json(SEED_MARKER, marker)
        record("fixture", marker)
        refresh_dashboard(lambda: wait_for_answers(9, first_ready))
    except Exception as exc:
        fail("seed_collection", exc)


def refresh_dashboard(callback: Callable[[], None]) -> None:
    controller = mw._home_dashboard_overhaul_controller
    controller.invalidate()
    controller._refresh_deck_browser()
    QTimer.singleShot(500, callback)


def wait_for_answers(expected: int, callback: Callable[[], None], attempt: int = 0) -> None:
    try:
        controller = mw._home_dashboard_overhaul_controller
        snapshot = controller.snapshot
        facts = snapshot.facts if snapshot is not None else None
        today = facts.today.value if facts is not None and facts.today.is_available else None
        if today is not None and today.answers == expected:
            callback()
            return
        if attempt >= 50:
            raise RuntimeError(
                "Snapshot did not reach {} answers; got {} with availability {}".format(
                    expected,
                    today.answers if today is not None else None,
                    {
                        name: getattr(state.status, "value", str(state.status))
                        for name, state in (
                            ("today", facts.today),
                            ("queue", facts.queue),
                            ("buried", facts.buried),
                            ("events", facts.events),
                            ("long_term", facts.long_term),
                        )
                    } if facts is not None else None,
                )
            )
        if attempt % 6 == 5:
            controller._refresh_deck_browser()
        QTimer.singleShot(300, lambda: wait_for_answers(expected, callback, attempt + 1))
    except Exception as exc:
        fail("wait_for_answers_{}".format(expected), exc)


def snapshot_values() -> dict[str, Any]:
    snapshot = mw._home_dashboard_overhaul_controller.snapshot
    facts = snapshot.facts
    if not all(state.is_available for state in (facts.today, facts.queue, facts.buried)):
        raise RuntimeError("Snapshot metrics are not available")
    today = facts.today.value
    queue = facts.queue.value
    buried = facts.buried.value
    return {
        "today": {
            "answers": today.answers,
            "new_cards_studied": today.new_cards_studied,
            "seconds": today.seconds,
            "pace_value": today.pace_value,
        },
        "remaining": {
            "new": queue.new,
            "learning": queue.learning,
            "review": queue.review,
            "total": queue.total,
            "estimated_duration_seconds": queue.estimated_duration_seconds,
        },
        "buried": {
            "new": buried.new,
            "learning": buried.learning,
            "review": buried.review,
        },
        "day_fact_rows": len(facts.days),
        "revision": facts.revision,
    }


def first_ready() -> None:
    record("snapshot_at_9", snapshot_values())
    mw.showFullScreen()
    QTimer.singleShot(1200, capture_year_at_9)


def capture_year_at_9() -> None:
    capture("01-dashboard-year-at-9-fullscreen")
    dashboard_metrics("01_year_at_9", add_tenth_answer)


def add_tenth_answer() -> None:
    try:
        history_card = int(mw.col.db.scalar(
            "SELECT c.id FROM cards c JOIN notes n ON n.id=c.nid WHERE n.tags LIKE '%hdo_14_acceptance%' AND n.flds LIKE 'History%' ORDER BY c.id LIMIT 1"
        ))
        next_id = int((datetime.now().astimezone() - timedelta(minutes=5)).timestamp() * 1000)
        while mw.col.db.scalar("SELECT 1 FROM revlog WHERE id=?", next_id):
            next_id += 1
        mw.col.db.execute(
            "INSERT INTO revlog (id,cid,usn,ease,ivl,lastIvl,factor,time,type) VALUES (?,?,?,?,?,?,?,?,?)",
            next_id, history_card, -1, 3, 30, 29, 2500, 10000, 1,
        )
        try:
            mw.col.save()
        except Exception:
            pass
        refresh_dashboard(lambda: wait_for_answers(10, tenth_ready))
    except Exception as exc:
        fail("add_tenth_answer", exc)


def tenth_ready() -> None:
    record("snapshot_at_10", snapshot_values())
    QTimer.singleShot(700, capture_year_at_10)


def capture_year_at_10() -> None:
    capture("02-dashboard-year-at-10-fullscreen")
    dashboard_metrics("02_year_at_10", prepare_month)


def click_view(view: str, callback: Callable[[], None]) -> None:
    eval_js(
        "var b=document.querySelector('[data-hdo-view=\"{}\"]');if(b)b.click();window.scrollTo(0,0);return '{}';".format(view, view),
        lambda _raw: callback(),
        650,
    )


def prepare_month() -> None:
    click_view("month", capture_month)


def capture_month() -> None:
    capture("03-dashboard-month-fullscreen")
    dashboard_metrics("03_month_fullscreen", prepare_narrow)


def prepare_narrow() -> None:
    mw.showNormal()
    mw.resize(620, 780)
    QTimer.singleShot(900, lambda: click_view("month", capture_narrow))


def capture_narrow() -> None:
    capture("04-dashboard-month-620x780")
    dashboard_metrics("04_month_620x780", prepare_narrow_stats)


def prepare_narrow_stats() -> None:
    eval_js(
        "var s=document.querySelector('.hdo-stat-groups');if(s)s.scrollIntoView({block:'start'});return !!s;",
        lambda _raw: capture_narrow_stats(),
        450,
    )


def capture_narrow_stats() -> None:
    capture("04b-dashboard-month-620x780-stats")
    dashboard_metrics("04b_month_620x780_stats", prepare_zoom_150)


def set_zoom(value: float) -> None:
    setter = getattr(mw.web, "setZoomFactor", None)
    if callable(setter):
        setter(value)
    else:
        mw.web.page().setZoomFactor(value)


def prepare_zoom_150() -> None:
    mw.resize(1440, 900)
    set_zoom(1.5)
    QTimer.singleShot(900, lambda: click_view("month", capture_zoom_150))


def capture_zoom_150() -> None:
    capture("05-dashboard-month-150-percent")
    dashboard_metrics("05_month_150_percent", prepare_zoom_200)


def prepare_zoom_200() -> None:
    set_zoom(2.0)
    QTimer.singleShot(900, lambda: click_view("month", capture_zoom_200))


def capture_zoom_200() -> None:
    capture("06-dashboard-month-200-percent")
    dashboard_metrics("06_month_200_percent", prepare_settings)


def prepare_settings() -> None:
    set_zoom(1.0)
    mw._home_dashboard_overhaul_controller.open_settings("dashboard")
    QTimer.singleShot(500, lambda: wait_for_settings(0))


def wait_for_settings(attempt: int) -> None:
    dialog = mw._home_dashboard_overhaul_controller.settings_dialog
    if dialog is not None and dialog.isVisible():
        dialog.resize(1280, 820)
        QTimer.singleShot(600, lambda: capture_settings(dialog))
        return
    if attempt >= 30:
        fail("settings", RuntimeError("Settings dialog did not open"))
        return
    QTimer.singleShot(200, lambda: wait_for_settings(attempt + 1))


def capture_settings(dialog: Any) -> None:
    capture("07-settings-dashboard", dialog)
    dashboard_text = " ".join(
        item.text().strip() for item in dialog.findChildren(QWidget)
        if hasattr(item, "text") and callable(item.text) and item.text().strip()
    )
    record("settings_dashboard_text", dashboard_text)
    dialog.open_page("calendar")
    QTimer.singleShot(500, lambda: capture_calendar_settings(dialog))


def capture_calendar_settings(dialog: Any) -> None:
    capture("08-settings-calendar", dialog)
    record("config_before_restart", deepcopy(mw._home_dashboard_overhaul_controller.config))
    dialog.reject()
    write_json(
        PHASE_PATH,
        {
            "phase": 1,
            "completed_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "snapshot_at_10": RESULTS.get("snapshot_at_10"),
        },
    )
    QTimer.singleShot(700, request_quit)


def request_quit() -> None:
    record("first_process_quit_requested", True)
    mw.close()


def restart_ready() -> None:
    record("snapshot_after_restart", snapshot_values())
    controller = mw._home_dashboard_overhaul_controller
    RESULTS["restart_checks"] = {
        "phase_marker_present": read_json(PHASE_PATH, {}).get("phase") == 1,
        "snapshot_persisted": RESULTS.get("snapshot_after_restart") == RESULTS.get("snapshot_at_10"),
        "view_persisted": controller.config["heatmap"]["calendar_view"] == "month",
        "schema_4_persisted": controller.config.get("schema_version") == 4,
        "show_eta_persisted": controller.config["study"].get("show_eta") is True,
        "sync_still_disabled": bool(RESULTS.get("gates", [{}])[-1].get("sync_gate")),
    }
    save()
    mw.showFullScreen()
    QTimer.singleShot(1000, lambda: click_view("month", capture_restart))


def capture_restart() -> None:
    capture("09-dashboard-month-after-restart")
    dashboard_metrics("09_month_after_restart", complete_acceptance)


def complete_acceptance() -> None:
    expected9 = RESULTS["fixture"]["expected_at_9"]
    expected10 = RESULTS["fixture"]["expected_at_10"]
    snapshot9 = RESULTS.get("snapshot_at_9", {})
    snapshot10 = RESULTS.get("snapshot_at_10", {})
    metrics = RESULTS.get("metrics", {})
    required_titles = ["Today", "Remaining", "Buried Cards", "Consistency"]
    required_today_labels = [
        "Total Cards Studied", "New Cards Studied", "Time studied", "Pace", "ETA"
    ]
    responsive = [
        metrics.get("04_month_620x780", {}),
        metrics.get("05_month_150_percent", {}),
        metrics.get("06_month_200_percent", {}),
    ]
    year = metrics.get("02_year_at_10", {})
    month = metrics.get("03_month_fullscreen", {})
    summary = {
        "all_identity_sync_and_filesystem_gates_passed": all(
            item.get("all_gates") for item in RESULTS.get("gates", [])
        ),
        "exact_package_bytes_passed": bool(RESULTS.get("package_integrity", {}).get("passed")),
        "nine_answer_lifetime_fallback_passed": (
            snapshot9.get("today", {}).get("answers") == 9
            and snapshot9.get("today", {}).get("new_cards_studied") == expected9["new_cards_studied"]
            and snapshot9.get("remaining", {}).get("estimated_duration_seconds") == expected9["duration_seconds"]
        ),
        "ten_answer_today_pace_switch_passed": (
            snapshot10.get("today", {}).get("answers") == 10
            and snapshot10.get("remaining", {}).get("estimated_duration_seconds") == expected10["duration_seconds"]
            and snapshot9.get("remaining", {}).get("estimated_duration_seconds")
            != snapshot10.get("remaining", {}).get("estimated_duration_seconds")
        ),
        "buried_counts_passed": snapshot10.get("buried") == expected9["buried"],
        "remaining_counts_passed": {
            key: snapshot10.get("remaining", {}).get(key)
            for key in ("new", "learning", "review", "total")
        } == expected9["remaining"],
        "year_four_column_geometry_passed": (
            year.get("groupCount") == 4
            and year.get("groupTitles") == required_titles
            and len({item.get("top") for item in year.get("groupRects", [])}) == 1
            and len({item.get("left") for item in year.get("groupRects", [])}) == 4
        ),
        "month_two_by_two_rail_passed": (
            month.get("groupCount") == 4
            and month.get("groupTitles") == required_titles
            and month.get("presentation") == "rail"
            and len({item.get("top") for item in month.get("groupRects", [])}) == 2
            and len({item.get("left") for item in month.get("groupRects", [])}) == 2
        ),
        "five_today_entries_responsive_passed": all(
            item.get("todayMetricCount") == 5
            and item.get("todayVisualRows") == 5
            and item.get("todayLabels") == required_today_labels
            and not item.get("horizontalOverflow")
            and not item.get("groupClipping")
            and item.get("statValuesVisible")
            for item in responsive
        ),
        "eta_clock_text_changed_passed": (
            bool(metrics.get("01_year_at_9", {}).get("etaValue"))
            and metrics.get("01_year_at_9", {}).get("etaValue")
            != metrics.get("02_year_at_10", {}).get("etaValue")
        ),
        "new_cards_studied_copy_passed": all(
            item.get("todayLabels") == required_today_labels
            and item.get("buriedLabels") == ["New", "Learning", "Reviews"]
            for item in metrics.values()
        ),
        "restart_persistence_passed": all(RESULTS.get("restart_checks", {}).values()),
        "errors_empty": not RESULTS.get("errors") and not RESULTS.get("javascript_errors"),
    }
    RESULTS["acceptance_summary"] = summary
    RESULTS["complete"] = all(summary.values())
    save()
    QTimer.singleShot(900, mw.close)


def start() -> None:
    try:
        if getattr(mw, "state", "") != "deckBrowser":
            QTimer.singleShot(300, start)
            return
        phase = read_json(PHASE_PATH, {})
        stage = "restart" if phase.get("phase") == 1 else "initial"
        if not gate(stage):
            raise RuntimeError("Disposable Anki identity, package, or sync gate failed")
        if stage == "restart":
            refresh_dashboard(lambda: wait_for_answers(10, restart_ready))
        else:
            seed_collection()
    except Exception as exc:
        fail("start", exc)


QTimer.singleShot(2400, start)
