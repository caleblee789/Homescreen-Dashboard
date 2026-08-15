"""Disposable-only exact-package acceptance probe for full-day insights.

Copy this file to ``addons21/zz_hdo_insight_probe/__init__.py`` in a fresh,
sync-disabled run.  It is intentionally excluded from the release archive.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from datetime import date, datetime, timedelta
import hashlib
import json
import os
from pathlib import Path
import sys
import traceback
from typing import Any, Callable
from zipfile import ZipFile

from aqt import mw
from aqt.qt import QApplication, QTimer


PROBE_ROOT = Path(__file__).resolve().parent
RUN_ROOT = PROBE_ROOT.parent.parent
EVIDENCE = RUN_ROOT / "insight-evidence"
RESULT_PATH = RUN_ROOT / "insight-acceptance-result.json"
PHASE_PATH = RUN_ROOT / "insight-acceptance-phase.json"
SEED_PATH = RUN_ROOT / "insight-fixture.json"
IDENTITY_PATH = RUN_ROOT / "QA_IDENTITY.json"
PACKAGE_ROOT = RUN_ROOT / "addons21" / "home_dashboard_overhaul"
IDENTITY = json.loads(IDENTITY_PATH.read_text(encoding="utf-8"))
EXPECTED_PROFILE = str(IDENTITY["profile"])
EXPECTED_KEY = str(IDENTITY["single_instance_key"])
EXPECTED_HASH = str(IDENTITY["candidate_sha256"])
EXPECTED_CANDIDATE = Path(IDENTITY["candidate"])
EXPECTED_CAPTURE_NAMES = (
    "01-current-trouble-dark",
    "02-past-no-miss",
    "03-past-deleted",
    "04-past-empty",
    "05-future-due",
    "06-future-empty",
    "07-current-620x780",
    "08-current-150-percent",
    "09-current-200-percent",
    "10-current-light",
    "11-current-high-contrast",
    "12-current-after-restart",
)
CAPTURE_STATE_KEYS = {
    "01-current-trouble-dark": "current",
    "02-past-no-miss": "no_miss",
    "03-past-deleted": "deleted",
    "04-past-empty": "past_empty",
    "05-future-due": "future_due",
    "06-future-empty": "future_empty",
    "07-current-620x780": "current",
    "08-current-150-percent": "current",
    "09-current-200-percent": "current",
    "10-current-light": "current",
    "11-current-high-contrast": "current",
    "12-current-after-restart": "current",
}
SEMANTIC_CONTRACTS = {
    "current": {
        "title": "Cards most missed today",
        "status": "",
        "browse_label": "Browse these cards",
        "item_count": 3,
        "summary_visible": 3,
    },
    "no_miss": {
        "title": "Study insight",
        "status": "No cards were missed on this date.",
        "browse_label": "Browse this day’s cards",
        "item_count": 0,
        "summary_visible": 2,
    },
    "deleted": {
        "title": "Study insight",
        "status": "Cards missed on this date are no longer available.",
        "browse_label": "Browse this day’s cards",
        "item_count": 0,
        "summary_visible": 2,
    },
    "past_empty": {
        "title": "Study insight",
        "status": "No cards were studied on this date.",
        "browse_label": "Browse this day’s cards",
        "item_count": 0,
        "summary_visible": 2,
    },
    "future_due": {
        "title": "Top due decks",
        "status": "",
        "browse_label": "Browse due cards",
        "item_count": 3,
        "summary_visible": 1,
    },
    "future_empty": {
        "title": "Top due decks",
        "status": "No review cards are due on this date.",
        "browse_label": "Browse due cards",
        "item_count": 0,
        "summary_visible": 1,
    },
}
EXPECTED_GATE_STAGES = ("initial", "restart")
REQUIRED_GATE_FIELDS = (
    "process_gate",
    "window_gate",
    "filesystem_gate",
    "sync_gate",
    "all_gates",
)
with ZipFile(EXPECTED_CANDIDATE) as _candidate_archive:
    EXPECTED_HUMAN_VERSION = str(
        json.loads(_candidate_archive.read("manifest.json"))["human_version"]
    )
EXCLUDED_PIDS = [
    int(value) for value in os.environ.get("HDO_QA_EXCLUDED_PIDS", "").split(",")
    if value.strip().isdigit()
]

EVIDENCE.mkdir(parents=True, exist_ok=True)


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError):
        return default


RESULTS = read_json(RESULT_PATH, {})
if not isinstance(RESULTS, dict):
    RESULTS = {}
RESULTS.setdefault("errors", [])
RESULTS.setdefault("gates", [])
RESULTS.setdefault("captures", [])
RESULTS.setdefault("dom", {})
RESULTS["candidate_sha256"] = EXPECTED_HASH


def evidence_contract() -> dict[str, bool]:
    capture_records = RESULTS.get("captures")
    if isinstance(capture_records, list):
        capture_names = [
            record.get("name") if isinstance(record, dict) else None
            for record in capture_records
        ]
    else:
        capture_names = []
    capture_names_are_strings = all(isinstance(name, str) for name in capture_names)
    dom = RESULTS.get("dom")
    dom_names = tuple(dom) if isinstance(dom, dict) else ()
    capture_contract = (
        isinstance(capture_records, list)
        and tuple(capture_names) == EXPECTED_CAPTURE_NAMES
        and capture_names_are_strings
        and len(set(capture_names)) == len(EXPECTED_CAPTURE_NAMES)
        and dom_names == EXPECTED_CAPTURE_NAMES
    )

    gate_records = RESULTS.get("gates")
    if isinstance(gate_records, list):
        gate_stages = [
            record.get("stage") if isinstance(record, dict) else None
            for record in gate_records
        ]
    else:
        gate_stages = []
    gate_stages_are_strings = all(isinstance(stage, str) for stage in gate_stages)
    gate_contract = (
        isinstance(gate_records, list)
        and tuple(gate_stages) == EXPECTED_GATE_STAGES
        and gate_stages_are_strings
        and len(set(gate_stages)) == len(EXPECTED_GATE_STAGES)
        and all(
            isinstance(record, dict)
            and all(record.get(field) is True for field in REQUIRED_GATE_FIELDS)
            for record in gate_records
        )
    )
    return {
        "capture_contract": capture_contract,
        "gate_contract": gate_contract,
    }


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
    RESULTS["errors"].append({
        "stage": stage,
        "error": str(exc),
        "traceback": traceback.format_exc(),
    })
    save()


def fail_and_close(stage: str, exc: Any) -> None:
    fail(stage, exc)
    RESULTS["complete"] = False
    save()
    QTimer.singleShot(300, mw.close)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def package_integrity() -> dict[str, Any]:
    mismatches = []
    extras = []
    expected = set()
    with ZipFile(EXPECTED_CANDIDATE) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            expected.add(info.filename)
            installed = PACKAGE_ROOT / info.filename
            if not installed.is_file() or installed.read_bytes() != archive.read(info.filename):
                mismatches.append(info.filename)
    for installed in PACKAGE_ROOT.rglob("*"):
        if not installed.is_file() or "__pycache__" in installed.parts:
            continue
        relative = installed.relative_to(PACKAGE_ROOT).as_posix()
        if relative not in expected and relative not in {"meta.json", "user_files/rotation_state.json"}:
            extras.append(relative)
    candidate_hash = sha256(EXPECTED_CANDIDATE)
    return {
        "candidate_hash": candidate_hash,
        "candidate_hash_matches": candidate_hash == EXPECTED_HASH,
        "archive_file_count": len(expected),
        "byte_mismatches": sorted(mismatches),
        "unexpected_files": sorted(extras),
        "passed": candidate_hash == EXPECTED_HASH and not mismatches and not extras,
    }


def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


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
        "excluded_pids": {str(pid): pid_alive(pid) for pid in EXCLUDED_PIDS},
        "process_gate": (
            str(RUN_ROOT) in sys.argv
            and EXPECTED_PROFILE in sys.argv
            and os.environ.get("ANKI_SINGLE_INSTANCE_KEY") == EXPECTED_KEY
            and os.getpid() not in EXCLUDED_PIDS
        ),
        "window_gate": EXPECTED_PROFILE in mw.windowTitle(),
        "filesystem_gate": (
            str(getattr(mw.pm, "base", "")) == str(RUN_ROOT)
            and manifest.get("human_version") == EXPECTED_HUMAN_VERSION
            and PACKAGE_ROOT.is_dir()
        ),
        "sync_gate": (
            not bool(sync_auth)
            and not bool(profile.get("syncKey"))
            and not bool(profile.get("syncUser"))
            and not bool(profile.get("autoSync", False))
            and not bool(profile.get("syncMedia", False))
            and not bool(profile.get("mediaSync", False))
        ),
    }
    values["all_gates"] = all(
        values[key] for key in ("process_gate", "window_gate", "filesystem_gate", "sync_gate")
    ) and all(values["excluded_pids"].values())
    RESULTS["gates"].append(values)
    RESULTS["package_integrity"] = package_integrity()
    save()
    return bool(values["all_gates"] and RESULTS["package_integrity"]["passed"])


def capture(name: str) -> None:
    QApplication.processEvents()
    pixmap = mw.grab()
    path = EVIDENCE / (name + ".png")
    if not pixmap.save(str(path), "PNG"):
        raise RuntimeError("Qt could not save {}".format(path))
    RESULTS["captures"].append({
        "name": name,
        "path": str(path),
        "width": pixmap.width(),
        "height": pixmap.height(),
        "window_width": int(mw.width()),
        "window_height": int(mw.height()),
        "device_pixel_ratio": float(pixmap.devicePixelRatio()),
    })
    save()


def eval_js(script: str, callback: Callable[[Any], None], delay: int = 300) -> None:
    wrapped = "(function(){try{%s}catch(error){return JSON.stringify({error:String(error),stack:String(error.stack||'')});}})()" % script

    def done(raw: Any) -> None:
        if isinstance(raw, str) and '"error"' in raw:
            RESULTS.setdefault("javascript_errors", []).append(raw)
            save()

        def invoke() -> None:
            try:
                callback(raw)
            except Exception as exc:
                fail_and_close("eval_js_callback", exc)

        QTimer.singleShot(delay, invoke)

    mw.web.evalWithCallback(wrapped, done)


DOM_SCRIPT = r"""
var root=document.getElementById('hdo-dashboard');
var details=root&&root.querySelector('[data-hdo-date-details]');
var insight=root&&root.querySelector('[data-hdo-day-insight]');
var list=root?Array.from(root.querySelectorAll('[data-hdo-insight-items] li')):[];
var status=root&&root.querySelector('[data-hdo-insight-status]');
var browse=root&&root.querySelector('[data-hdo-browse-date]');
var manage=root&&root.querySelector('[data-hdo-manage-events]');
var events=root&&root.querySelector('[data-hdo-detail-events-heading]');
var rect=insight?insight.getBoundingClientRect():null;
return JSON.stringify({
  selectedDate:(root&&root.querySelector('.hdo-day[aria-selected="true"]')||{}).dataset?.date||'',
  dateHeading:(root&&root.querySelector('[data-hdo-detail-date]')||{}).textContent||'',
  insightTitle:(root&&root.querySelector('[data-hdo-insight-title]')||{}).textContent||'',
  insightBusy:insight&&insight.getAttribute('aria-busy'),
  itemCount:list.length,
  items:list.map(function(item){return item.innerText.trim();}),
  itemRows:list.map(function(item){return {
    primaryText:(item.querySelector('.hdo-insight-primary')||{}).textContent||'',
    secondaryText:(item.querySelector('.hdo-insight-secondary')||{}).textContent||'',
    countLabel:(item.querySelector('.hdo-insight-count')||{}).textContent||''
  };}),
  status:status?status.innerText.trim():'',
  browseLabel:browse&&!browse.hidden?browse.textContent.trim():'',
  browseHidden:!browse||browse.hidden,
  manageLabel:manage?manage.textContent.trim():'',
  eventsHeading:events?events.textContent.trim():'',
  legacySummaryCount:root?root.querySelectorAll('.hdo-date-summary').length:-1,
  detailsSummaryCount:root?root.querySelectorAll('.hdo-details-summary').length:-1,
  summaryVisible:root?Array.from(root.querySelectorAll('[data-hdo-details-summary]>div')).filter(function(node){return !node.hidden;}).length:-1,
  horizontalOverflow:document.documentElement.scrollWidth>document.documentElement.clientWidth+1,
  insightClipped:rect?rect.right>document.documentElement.clientWidth+1:false,
  innerWidth:window.innerWidth,
  innerHeight:window.innerHeight,
  detailsVisible:details&&!details.hidden
});
"""


def model_dom_items(model: Any) -> list[dict[str, str]]:
    if not isinstance(model, dict) or not isinstance(model.get("items"), list):
        return []
    return [
        {
            "primaryText": str(item.get("primary_text", "")),
            "secondaryText": str(item.get("secondary_text", "")),
            "countLabel": str(item.get("count_label") or item.get("count") or ""),
        }
        for item in model["items"]
        if isinstance(item, dict)
    ]


def semantic_failures(
    capture_name: str,
    iso_date: str,
    value: Any,
    model: Any,
) -> list[str]:
    state_key = CAPTURE_STATE_KEYS.get(capture_name)
    contract = SEMANTIC_CONTRACTS.get(state_key or "")
    if not isinstance(contract, dict):
        return ["unknown capture contract"]
    if not isinstance(value, dict):
        return ["DOM metrics are not an object"]

    failures = []

    def require(condition: bool, message: str) -> None:
        if not condition:
            failures.append(message)

    expected_items = model_dom_items(model)
    require(value.get("selectedDate") == iso_date, "selected date mismatch")
    require(value.get("detailsVisible") is True, "date details are not visible")
    require(value.get("insightBusy") == "false", "insight is still busy")
    require(value.get("insightTitle") == contract["title"], "insight title mismatch")
    require(value.get("status") == contract["status"], "insight status mismatch")
    require(value.get("browseHidden") is False, "Browse action is hidden")
    require(value.get("browseLabel") == contract["browse_label"], "Browse label mismatch")
    require(value.get("itemCount") == contract["item_count"], "insight item count mismatch")
    require(len(expected_items) == contract["item_count"], "backend item count mismatch")
    require(value.get("itemRows") == expected_items, "DOM insight items do not match backend order/content")
    require(isinstance(model, dict) and model.get("date") == iso_date, "backend model date mismatch")
    require(value.get("legacySummaryCount") == 0, "legacy date summary is present")
    require(value.get("detailsSummaryCount") == 1, "canonical details summary count mismatch")
    require(value.get("summaryVisible") == contract["summary_visible"], "contextual summary row count mismatch")
    return failures


def dom_metrics(name: str, callback: Callable[[], None]) -> None:
    def done(raw: Any) -> None:
        try:
            value = json.loads(raw) if isinstance(raw, str) else raw
        except (TypeError, ValueError):
            value = {"raw": raw}
        RESULTS["dom"][name] = value
        save()
        callback()

    eval_js(DOM_SCRIPT, done, 100)


def deck_id(name: str) -> int:
    getter = getattr(mw.col.decks, "id", None)
    if callable(getter):
        return int(getter(name))
    raise RuntimeError("DeckManager.id() is unavailable")


def new_card(label: str, deck: int, back: str = "Synthetic insight fixture") -> int:
    notetype = mw.col.models.current()
    if not notetype:
        raise RuntimeError("Disposable collection has no current note type")
    note = mw.col.new_note(notetype)
    note.fields[0] = label
    if len(note.fields) > 1:
        note.fields[1] = back
    note.tags.append("hdo_insight_acceptance")
    mw.col.add_note(note, deck)
    card_id = mw.col.db.scalar(
        "SELECT id FROM cards WHERE nid=? ORDER BY ord LIMIT 1", note.id
    )
    if not card_id:
        raise RuntimeError("No card created for note {}".format(note.id))
    return int(card_id)


def set_review_card(card_id: int, due: int) -> None:
    mw.col.db.execute(
        "UPDATE cards SET queue=2,type=2,due=?,ivl=30,factor=2500,reps=12,lapses=1 WHERE id=?",
        due,
        card_id,
    )


def day_millis(study_date: date, hour_after_rollover: int, suffix: int) -> int:
    cutoff = datetime.fromtimestamp(int(mw.col.sched.day_cutoff)).astimezone()
    rollover = timedelta(hours=cutoff.hour, minutes=cutoff.minute, seconds=cutoff.second)
    stamp = datetime.combine(study_date, datetime.min.time()).astimezone() + rollover
    return int((stamp + timedelta(hours=hour_after_rollover)).timestamp() * 1000) + suffix


def insert_answer(study_date: date, hour: int, suffix: int, card_id: int, ease: int, answer_type: int = 1) -> None:
    mw.col.db.execute(
        "INSERT INTO revlog (id,cid,usn,ease,ivl,lastIvl,factor,time,type) VALUES (?,?,?,?,?,?,?,?,?)",
        day_millis(study_date, hour, suffix),
        card_id,
        -1,
        ease,
        30,
        29,
        2500,
        10000,
        answer_type,
    )


def seed_collection() -> None:
    from home_dashboard_overhaul.analytics import scheduling_today

    if SEED_PATH.exists():
        refresh_and_wait(after_snapshot_ready)
        return
    scheduling_date = scheduling_today(int(mw.col.sched.day_cutoff))
    anatomy = deck_id("QA Insights::Anatomy")
    pharmacology = deck_id("QA Insights::Pharmacology")
    pathology = deck_id("QA Insights::Pathology")
    due_day = int(mw.col.sched.today) + 1

    card_a = new_card("<div>Which nerve passes here? <b>Card A</b> [sound:missing.mp3]</div>", anatomy)
    card_b = new_card("B" * 240, pharmacology)
    card_c = new_card('<img src="missing.png">', pathology, "Card C fallback field")
    card_d = new_card("Hard and Good only", anatomy)
    card_e = new_card("Tie broken by latest miss", pathology)
    for card_id in (card_a, card_b, card_c, card_d, card_e):
        set_review_card(card_id, int(mw.col.sched.today) + 60)

    for hour, suffix in ((1, 1), (7, 2), (13, 3)):
        insert_answer(scheduling_date, hour, suffix, card_a, 1)
    for hour, suffix in ((5, 4), (12, 5)):
        insert_answer(scheduling_date, hour, suffix, card_b, 1)
    insert_answer(scheduling_date, 14, 6, card_c, 1)
    insert_answer(scheduling_date, 3, 7, card_e, 1)
    insert_answer(scheduling_date, 8, 8, card_d, 2)
    insert_answer(scheduling_date, 9, 9, card_d, 3)
    insert_answer(scheduling_date, 10, 10, card_d, 1, 4)

    # Past selections are civil dates in the UI, while the current selection
    # maps to the active scheduling day.  Base distinct past fixtures on the
    # civil date so an after-midnight rollover can never collide with Today.
    no_miss_date = date.today() - timedelta(days=1)
    deleted_date = date.today() - timedelta(days=2)
    empty_date = date.today() - timedelta(days=3)
    insert_answer(no_miss_date, 6, 11, card_d, 3)
    insert_answer(deleted_date, 6, 12, 9_999_999_991, 1)

    future_cards = []
    for deck, count, prefix in (
        (anatomy, 5, "Future anatomy"),
        (pharmacology, 3, "Future pharmacology"),
        (pathology, 1, "Future pathology"),
    ):
        for index in range(count):
            card_id = new_card("{} {}".format(prefix, index + 1), deck)
            set_review_card(card_id, due_day)
            future_cards.append(card_id)

    try:
        mw.col.save()
    except Exception:
        pass

    controller = mw._home_dashboard_overhaul_controller
    config = deepcopy(controller.config)
    config["appearance"].update(
        preset="Sapphire Glass", mode="dark", density="compact", text_scale=100
    )
    config["heatmap"].update(
        calendar_view="month",
        history_days=0,
        forecast_days=90,
        show_due_forecast=True,
        exclude_manual_reschedules=True,
        exclude_deleted_cards=False,
        excluded_deck_ids=[],
    )
    config["events"]["items"] = [
        {"id": "qa-1", "name": "First event", "date": date.today().isoformat(), "archived": False},
        {"id": "qa-2", "name": "Second event", "date": date.today().isoformat(), "archived": False},
        {"id": "qa-3", "name": "Third event", "date": date.today().isoformat(), "archived": False},
        {"id": "qa-4", "name": "A deliberately long fourth event for layout coverage", "date": date.today().isoformat(), "archived": False},
    ]
    controller.save_config(config)
    fixture = {
        "scheduling_date": scheduling_date.isoformat(),
        "calendar_today": date.today().isoformat(),
        "current_card_ids": [card_a, card_b, card_c, card_d, card_e],
        "expected_ranked_card_ids": [card_a, card_b, card_c],
        "no_miss_date": no_miss_date.isoformat(),
        "deleted_date": deleted_date.isoformat(),
        "empty_date": empty_date.isoformat(),
        "future_due_date": (scheduling_date + timedelta(days=1)).isoformat(),
        "future_empty_date": (scheduling_date + timedelta(days=2)).isoformat(),
        "future_cards": future_cards,
    }
    write_json(SEED_PATH, fixture)
    record("fixture", fixture)
    refresh_and_wait(after_snapshot_ready)


def refresh_and_wait(callback: Callable[[], None]) -> None:
    controller = mw._home_dashboard_overhaul_controller
    controller.invalidate()
    controller._refresh_deck_browser()
    wait_for_insight_ready(callback, 0)


def direct_current_model_ready(snapshot: Any, current: Any) -> bool:
    items = current.get("items") if isinstance(current, dict) else None
    return bool(
        snapshot
        and not getattr(snapshot, "errors", {"snapshot": "unavailable"})
        and isinstance(current, dict)
        and current.get("date") == date.today().isoformat()
        and current.get("valid_answer_count") == 9
        and current.get("again_count") == 7
        and isinstance(items, list)
        and len(items) == 3
    )


def wait_for_insight_ready(callback: Callable[[], None], attempt: int) -> None:
    controller = mw._home_dashboard_overhaul_controller
    snapshot = controller.snapshot
    current = None
    collector_error = ""
    try:
        current = collect_current_model()
    except Exception as exc:
        collector_error = repr(exc)
    if direct_current_model_ready(snapshot, current):
        try:
            callback()
        except Exception as exc:
            fail_and_close("insight_ready_callback", exc)
        return
    if attempt >= 60:
        fail_and_close(
            "wait_for_insight_ready",
            RuntimeError(
                "Direct insight model did not become ready: {}".format({
                    "snapshot_present": bool(snapshot),
                    "snapshot_errors": getattr(snapshot, "errors", None),
                    "current": current,
                    "collector_error": collector_error,
                })
            ),
        )
        return
    if attempt % 8 == 7:
        try:
            controller._refresh_deck_browser()
        except Exception as exc:
            fail_and_close("refresh_deck_browser", exc)
            return
    QTimer.singleShot(250, lambda: wait_for_insight_ready(callback, attempt + 1))


def collect_current_model() -> dict[str, Any]:
    from home_dashboard_overhaul.analytics import scheduling_today
    from home_dashboard_overhaul.insights import collect_day_insight

    controller = mw._home_dashboard_overhaul_controller
    calendar_today = date.today()
    return asdict(collect_day_insight(
        mw.col,
        controller.config,
        calendar_today,
        scheduling_today(int(mw.col.sched.day_cutoff)),
        calendar_today,
    ))


def collect_state_models() -> dict[str, Any]:
    from home_dashboard_overhaul.analytics import scheduling_today
    from home_dashboard_overhaul.insights import collect_day_insight

    fixture = read_json(SEED_PATH, {})
    controller = mw._home_dashboard_overhaul_controller
    scheduling_date = scheduling_today(int(mw.col.sched.day_cutoff))
    calendar_today = date.today()
    values = {}
    dates = {
        "current": calendar_today,
        "no_miss": date.fromisoformat(fixture["no_miss_date"]),
        "deleted": date.fromisoformat(fixture["deleted_date"]),
        "past_empty": date.fromisoformat(fixture["empty_date"]),
        "future_due": date.fromisoformat(fixture["future_due_date"]),
        "future_empty": date.fromisoformat(fixture["future_empty_date"]),
    }
    for name, selected in dates.items():
        values[name] = asdict(collect_day_insight(
            mw.col,
            controller.config,
            selected,
            scheduling_date,
            calendar_today,
        ))
    return values


def after_snapshot_ready() -> None:
    models = collect_state_models()
    record("state_models_initial", models)
    record("today_insight_initial", models["current"])
    mw.showFullScreen()
    QTimer.singleShot(900, select_current)


def model_for_capture(capture_name: str) -> dict[str, Any]:
    state_key = CAPTURE_STATE_KEYS.get(capture_name, "")
    source_key = (
        "state_models_after_restart"
        if capture_name == "12-current-after-restart"
        else "state_models_initial"
    )
    models = RESULTS.get(source_key, {})
    if not isinstance(models, dict):
        return {}
    model = models.get(state_key, {})
    return model if isinstance(model, dict) else {}


def select_date(
    capture_name: str,
    iso_date: str,
    callback: Callable[[], None],
    attempt: int = 0,
) -> None:
    script = "var b=document.querySelector('[data-date=\"{}\"]');if(b)b.click();return !!b;".format(iso_date)

    def clicked(_raw: Any) -> None:
        wait_for_selected(capture_name, iso_date, callback, attempt)

    eval_js(script, clicked, 250)


def wait_for_selected(
    capture_name: str,
    iso_date: str,
    callback: Callable[[], None],
    attempt: int,
) -> None:
    def checked(raw: Any) -> None:
        try:
            value = json.loads(raw) if isinstance(raw, str) else raw
        except (TypeError, ValueError):
            value = {}
        if not isinstance(value, dict):
            value = {"raw": value}
        failures = semantic_failures(
            capture_name,
            iso_date,
            value,
            model_for_capture(capture_name),
        )
        if not failures:
            try:
                callback()
            except Exception as exc:
                fail_and_close("selected_date_callback_{}".format(capture_name), exc)
        elif attempt >= 40:
            fail_and_close(
                "wait_for_selected_{}".format(capture_name),
                RuntimeError(str({"failures": failures, "dom": value})),
            )
        else:
            QTimer.singleShot(
                200,
                lambda: wait_for_selected(
                    capture_name,
                    iso_date,
                    callback,
                    attempt + 1,
                ),
            )

    eval_js(DOM_SCRIPT, checked, 50)


def capture_state(name: str, callback: Callable[[], None]) -> None:
    capture(name)
    dom_metrics(name, callback)


def select_current() -> None:
    select_date(
        "01-current-trouble-dark",
        date.today().isoformat(),
        lambda: capture_state("01-current-trouble-dark", select_no_miss),
    )


def select_no_miss() -> None:
    select_date(
        "02-past-no-miss",
        RESULTS["fixture"]["no_miss_date"],
        lambda: capture_state("02-past-no-miss", select_deleted),
    )


def select_deleted() -> None:
    select_date(
        "03-past-deleted",
        RESULTS["fixture"]["deleted_date"],
        lambda: capture_state("03-past-deleted", select_past_empty),
    )


def select_past_empty() -> None:
    select_date(
        "04-past-empty",
        RESULTS["fixture"]["empty_date"],
        lambda: capture_state("04-past-empty", select_future_due),
    )


def select_future_due() -> None:
    select_date(
        "05-future-due",
        RESULTS["fixture"]["future_due_date"],
        lambda: capture_state("05-future-due", select_future_empty),
    )


def select_future_empty() -> None:
    select_date(
        "06-future-empty",
        RESULTS["fixture"]["future_empty_date"],
        lambda: capture_state("06-future-empty", prepare_narrow),
    )


def prepare_narrow() -> None:
    mw.showNormal()
    mw.resize(620, 780)
    QTimer.singleShot(
        700,
        lambda: select_date(
            "07-current-620x780",
            date.today().isoformat(),
            scroll_narrow,
        ),
    )


def scroll_narrow() -> None:
    eval_js(
        "var d=document.querySelector('[data-hdo-day-insight]');if(d)d.scrollIntoView({block:'start'});return !!d;",
        lambda _raw: capture_state("07-current-620x780", prepare_zoom_150),
        350,
    )


def set_zoom(value: float) -> None:
    setter = getattr(mw.web, "setZoomFactor", None)
    if callable(setter):
        setter(value)
    else:
        mw.web.page().setZoomFactor(value)


def prepare_zoom_150() -> None:
    mw.resize(1440, 900)
    set_zoom(1.5)
    QTimer.singleShot(
        700,
        lambda: select_date(
            "08-current-150-percent",
            date.today().isoformat(),
            lambda: capture_state("08-current-150-percent", prepare_zoom_200),
        ),
    )


def prepare_zoom_200() -> None:
    set_zoom(2.0)
    QTimer.singleShot(
        700,
        lambda: select_date(
            "09-current-200-percent",
            date.today().isoformat(),
            lambda: capture_state("09-current-200-percent", prepare_light),
        ),
    )


def apply_appearance(
    capture_name: str,
    preset: str,
    mode: str,
    callback: Callable[[], None],
) -> None:
    set_zoom(1.0)
    controller = mw._home_dashboard_overhaul_controller
    config = deepcopy(controller.config)
    config["appearance"].update(preset=preset, mode=mode)
    controller.save_config(config)
    QTimer.singleShot(
        700,
        lambda: select_date(
            capture_name,
            date.today().isoformat(),
            callback,
        ),
    )


def prepare_light() -> None:
    apply_appearance(
        "10-current-light",
        "Sapphire Glass",
        "light",
        lambda: capture_state("10-current-light", prepare_high_contrast),
    )


def prepare_high_contrast() -> None:
    apply_appearance(
        "11-current-high-contrast",
        "High Contrast",
        "light",
        lambda: capture_state("11-current-high-contrast", finish_initial),
    )


def finish_initial() -> None:
    record("config_before_restart", deepcopy(mw._home_dashboard_overhaul_controller.config))
    write_json(PHASE_PATH, {
        "phase": 1,
        "completed_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "today_insight": RESULTS.get("today_insight_initial"),
    })
    QTimer.singleShot(500, mw.close)


def restart_ready() -> None:
    models = collect_state_models()
    record("today_insight_after_restart", models["current"])
    record("state_models_after_restart", models)
    mw.showFullScreen()
    QTimer.singleShot(
        700,
        lambda: select_date(
            "12-current-after-restart",
            date.today().isoformat(),
            lambda: capture_state("12-current-after-restart", complete),
        ),
    )


def complete() -> None:
    fixture = RESULTS.get("fixture", read_json(SEED_PATH, {}))
    models = RESULTS.get("state_models_initial", {})
    dom = RESULTS.get("dom", {})
    current = models.get("current", {})
    expected_query = "cid:{}".format(",".join(str(value) for value in fixture.get("expected_ranked_card_ids", [])))
    responsive = [
        dom.get("07-current-620x780", {}),
        dom.get("08-current-150-percent", {}),
        dom.get("09-current-200-percent", {}),
    ]
    capture_dates = {
        "01-current-trouble-dark": fixture.get("calendar_today"),
        "02-past-no-miss": fixture.get("no_miss_date"),
        "03-past-deleted": fixture.get("deleted_date"),
        "04-past-empty": fixture.get("empty_date"),
        "05-future-due": fixture.get("future_due_date"),
        "06-future-empty": fixture.get("future_empty_date"),
        "07-current-620x780": fixture.get("calendar_today"),
        "08-current-150-percent": fixture.get("calendar_today"),
        "09-current-200-percent": fixture.get("calendar_today"),
        "10-current-light": fixture.get("calendar_today"),
        "11-current-high-contrast": fixture.get("calendar_today"),
        "12-current-after-restart": fixture.get("calendar_today"),
    }
    semantic_results = {
        capture_name: semantic_failures(
            capture_name,
            str(capture_dates.get(capture_name) or ""),
            dom.get(capture_name, {}),
            model_for_capture(capture_name),
        )
        for capture_name in EXPECTED_CAPTURE_NAMES
    }
    RESULTS["semantic_failures"] = semantic_results
    current_capture_names = tuple(
        name for name in EXPECTED_CAPTURE_NAMES
        if CAPTURE_STATE_KEYS[name] == "current"
    )
    contracts = evidence_contract()
    summary = {
        "candidate_identity": RESULTS.get("candidate_sha256") == EXPECTED_HASH,
        "capture_contract": contracts["capture_contract"],
        "gate_contract": contracts["gate_contract"],
        "identity_package_sync_gates": contracts["gate_contract"] and RESULTS.get("package_integrity", {}).get("passed") is True,
        "current_full_day_ranking": (
            current.get("valid_answer_count") == 9
            and current.get("again_count") == 7
            and [item.get("count") for item in current.get("items", [])] == [3, 2, 1]
            and current.get("browser_query") == expected_query
        ),
        "hard_and_manual_excluded": (
            str(fixture.get("current_card_ids", [None, None, None, None])[3]) not in current.get("browser_query", "")
            and current.get("valid_answer_count") == 9
        ),
        "prompt_sanitization_and_cap": all(
            "<" not in item.get("primary_text", "")
            and "[sound:" not in item.get("primary_text", "")
            and "[anki:play:" not in item.get("primary_text", "")
            and len(item.get("primary_text", "")) <= 160
            for item in current.get("items", [])
        ) and len(current.get("items", [])) == 3
        and current["items"][2].get("primary_text") == "Card C fallback field",
        "empty_states": (
            models.get("no_miss", {}).get("empty_reason") == "no_again"
            and models.get("deleted", {}).get("empty_reason") == "deleted_misses"
            and models.get("past_empty", {}).get("empty_reason") == "past_no_answers"
            and models.get("future_empty", {}).get("empty_reason") == "no_due"
        ),
        "future_due_grouping": (
            [item.get("count") for item in models.get("future_due", {}).get("items", [])] == [5, 3, 1]
            and models.get("future_due", {}).get("browse_action") == "future_due"
        ),
        "contextual_summary_contract": all(
            dom.get(name, {}).get("legacySummaryCount") == 0
            and dom.get(name, {}).get("detailsSummaryCount") == 1
            and dom.get(name, {}).get("summaryVisible")
            == SEMANTIC_CONTRACTS[CAPTURE_STATE_KEYS[name]]["summary_visible"]
            for name in EXPECTED_CAPTURE_NAMES
        ) and tuple(dom) == EXPECTED_CAPTURE_NAMES,
        "current_dom_matches_backend": all(
            dom.get(name, {}).get("insightTitle") == "Cards most missed today"
            and dom.get(name, {}).get("status") == ""
            and dom.get(name, {}).get("itemCount") == 3
            and dom.get(name, {}).get("itemRows")
            == model_dom_items(model_for_capture(name))
            and dom.get(name, {}).get("browseLabel") == "Browse these cards"
            and dom.get(name, {}).get("browseHidden") is False
            for name in current_capture_names
        ),
        "exact_capture_semantics": all(
            not failures for failures in semantic_results.values()
        ) and tuple(semantic_results) == EXPECTED_CAPTURE_NAMES,
        "exact_actions_and_events": (
            dom.get("01-current-trouble-dark", {}).get("browseLabel") == "Browse these cards"
            and dom.get("02-past-no-miss", {}).get("browseLabel") == "Browse this day’s cards"
            and dom.get("03-past-deleted", {}).get("browseLabel") == "Browse this day’s cards"
            and dom.get("04-past-empty", {}).get("browseLabel") == "Browse this day’s cards"
            and dom.get("04-past-empty", {}).get("browseHidden") is False
            and dom.get("05-future-due", {}).get("browseLabel") == "Browse due cards"
            and dom.get("06-future-empty", {}).get("browseLabel") == "Browse due cards"
            and dom.get("06-future-empty", {}).get("browseHidden") is False
            and dom.get("01-current-trouble-dark", {}).get("manageLabel") == "Manage this date"
            and dom.get("01-current-trouble-dark", {}).get("eventsHeading") == "Events (4)"
        ),
        "exact_visible_copy": (
            dom.get("01-current-trouble-dark", {}).get("insightTitle") == "Cards most missed today"
            and dom.get("01-current-trouble-dark", {}).get("status") == ""
            and dom.get("02-past-no-miss", {}).get("status") == "No cards were missed on this date."
            and dom.get("03-past-deleted", {}).get("status") == "Cards missed on this date are no longer available."
            and dom.get("04-past-empty", {}).get("status") == "No cards were studied on this date."
            and dom.get("05-future-due", {}).get("insightTitle") == "Top due decks"
            and dom.get("05-future-due", {}).get("status") == ""
            and dom.get("06-future-empty", {}).get("status") == "No review cards are due on this date."
        ),
        "responsive_no_horizontal_clipping": all(
            not value.get("horizontalOverflow") and not value.get("insightClipped")
            for value in responsive
        ),
        "restart_persistence": (
            RESULTS.get("today_insight_after_restart") == RESULTS.get("today_insight_initial")
            and RESULTS.get("state_models_after_restart") == RESULTS.get("state_models_initial")
        ),
        "all_capture_states_ready": all(
            value.get("insightBusy") == "false" and value.get("detailsVisible") is True
            for value in dom.values()
        ),
        "errors_empty": not RESULTS.get("errors") and not RESULTS.get("javascript_errors"),
    }
    RESULTS["acceptance_summary"] = summary
    RESULTS["complete"] = all(summary.values())
    save()
    QTimer.singleShot(700, mw.close)


def start(attempt: int = 0) -> None:
    try:
        if getattr(mw, "state", "") != "deckBrowser":
            if attempt >= 60:
                fail_and_close(
                    "wait_for_deck_browser",
                    RuntimeError("Deck Browser did not become ready"),
                )
                return
            QTimer.singleShot(250, lambda: start(attempt + 1))
            return
        phase = read_json(PHASE_PATH, {})
        stage = "restart" if phase.get("phase") == 1 else "initial"
        if not gate(stage):
            raise RuntimeError("Disposable identity, filesystem, package, or sync gate failed")
        if stage == "restart":
            refresh_and_wait(restart_ready)
        else:
            seed_collection()
    except Exception as exc:
        fail_and_close("start", exc)


QTimer.singleShot(2200, start)
