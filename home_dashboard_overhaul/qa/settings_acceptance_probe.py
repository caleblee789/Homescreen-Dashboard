"""Disposable-only settings UI capture and identity probe.

Copy this file into a fresh sync-disabled Anki base as
``addons21/zz_hdo_settings_probe/__init__.py``.  It is never shipped in the
Home Dashboard archive.  The probe verifies the isolated process, window,
filesystem, sync state, and installed candidate bytes before opening or
capturing any add-on UI.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime
import hashlib
import json
import os
from pathlib import Path
import sys
import traceback
from typing import Any, Callable
from zipfile import ZipFile

from aqt import mw
from aqt.qt import QApplication, QDialogButtonBox, QMessageBox, QTimer, QWidget, Qt


PROBE_ROOT = Path(__file__).resolve().parent
RUN_ROOT = PROBE_ROOT.parent.parent
PHASE = os.environ.get("HDO_SETTINGS_QA_PHASE", "run").strip() or "run"
EVIDENCE = RUN_ROOT / "settings-evidence" / PHASE
RESULT_PATH = RUN_ROOT / "settings-audit-result-{}.json".format(PHASE)
PERSISTENCE_PATH = RUN_ROOT / "settings-persistence-state.json"
IDENTITY_PATH = RUN_ROOT / "QA_IDENTITY.json"
PACKAGE_ROOT = RUN_ROOT / "addons21" / "home_dashboard_overhaul"
ROTATION_PATH = PACKAGE_ROOT / "user_files" / "rotation_state.json"
IDENTITY = json.loads(IDENTITY_PATH.read_text(encoding="utf-8"))
EXPECTED_PROFILE = str(IDENTITY["profile"])
EXPECTED_KEY = str(IDENTITY["single_instance_key"])
EXPECTED_HASH = str(IDENTITY["candidate_sha256"])
EXPECTED_CANDIDATE = Path(str(IDENTITY["candidate"]))
EXCLUDED_PID = int(os.environ.get("HDO_QA_EXCLUDED_PID", "0") or 0)

EVIDENCE.mkdir(parents=True, exist_ok=True)
RESULTS: dict[str, Any] = {
    "phase": PHASE,
    "candidate_sha256": EXPECTED_HASH,
    "captures": [],
    "errors": [],
    "runtime_checks": [],
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


def fail(stage: str, exc: Any) -> None:
    RESULTS["errors"].append(
        {"stage": stage, "error": str(exc), "traceback": traceback.format_exc()}
    )
    save()


def check(name: str, passed: bool, details: Any = None) -> None:
    RESULTS["runtime_checks"].append(
        {"name": name, "passed": bool(passed), "details": details}
    )
    save()


def focus_chain_reaches(start: QWidget, target: QWidget, limit: int = 400) -> bool:
    current = start
    for _index in range(limit):
        current = current.nextInFocusChain()
        if current is target:
            return True
        if current is start:
            break
    return False


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
            and relative not in {"meta.json", "user_files/rotation_state.json"}
            and "__pycache__" not in installed.parts
        ):
            extras.append(relative)
    return {
        "candidate_hash": sha256(EXPECTED_CANDIDATE),
        "candidate_hash_matches": sha256(EXPECTED_CANDIDATE) == EXPECTED_HASH,
        "archive_file_count": len(expected_names),
        "byte_mismatches": sorted(mismatches),
        "unexpected_files": sorted(extras),
        "passed": not mismatches and not extras and sha256(EXPECTED_CANDIDATE) == EXPECTED_HASH,
    }


def identity_gate() -> bool:
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
    gate = {
        "pid": os.getpid(),
        "excluded_pid": EXCLUDED_PID,
        "excluded_pid_unchanged_and_running": excluded_alive if EXCLUDED_PID > 0 else None,
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
            and manifest.get("package") == "home_dashboard_overhaul"
            and PACKAGE_ROOT.is_dir()
        ),
        "sync_gate": (
            not bool(sync_auth)
            and not bool(profile.get("syncKey"))
            and not bool(profile.get("syncUser"))
            and not bool(profile.get("autoSync", False))
            and not bool(profile.get("syncMedia", profile.get("mediaSync", False)))
        ),
    }
    gate["all_gates"] = all(
        gate[key] for key in ("process_gate", "window_gate", "filesystem_gate", "sync_gate")
    ) and (EXCLUDED_PID <= 0 or excluded_alive)
    RESULTS["identity_gate"] = gate
    RESULTS["package_integrity"] = package_integrity()
    save()
    return bool(gate["all_gates"] and RESULTS["package_integrity"]["passed"])


def capture(name: str, widget: QWidget) -> None:
    QApplication.processEvents()
    pixmap = widget.grab()
    path = EVIDENCE / (name + ".png")
    if not pixmap.save(str(path), "PNG"):
        raise RuntimeError("Qt could not save {}".format(path))
    RESULTS["captures"].append(
        {
            "name": name,
            "path": str(path),
            "width": pixmap.width(),
            "height": pixmap.height(),
            "logical_width": int(widget.width()),
            "logical_height": int(widget.height()),
            "device_pixel_ratio": float(pixmap.devicePixelRatio()),
        }
    )
    save()


PAGES = (
    ("theme-layout", "appearance"),
    ("home-screen", "dashboard"),
    ("calendar-data", "calendar"),
    ("events", "events"),
    ("bible-verse", "bible verse"),
    ("about", "about & credits"),
)


def capture_pages(dialog: Any, prefix: str, index: int, callback: Callable[[], None]) -> None:
    if index >= len(PAGES):
        callback()
        return
    slug, alias = PAGES[index]
    dialog.open_page(alias)
    QTimer.singleShot(
        240,
        lambda: _capture_page(dialog, prefix, index, slug, callback),
    )


def _capture_page(
    dialog: Any,
    prefix: str,
    index: int,
    slug: str,
    callback: Callable[[], None],
) -> None:
    capture("{}-{}".format(prefix, slug), dialog)
    capture_pages(dialog, prefix, index + 1, callback)


def _widget_inside_dialog(dialog: QWidget, widget: QWidget) -> bool:
    top_left = widget.mapTo(dialog, widget.rect().topLeft())
    bottom_right = widget.mapTo(dialog, widget.rect().bottomRight())
    return dialog.rect().contains(top_left) and dialog.rect().contains(bottom_right)


def _editor_geometry_checks(
    editor: QWidget,
    label: str,
    expected_width: int,
    expected_height: int,
) -> None:
    QApplication.processEvents()
    button_box = editor.findChild(QDialogButtonBox)
    action_buttons = button_box.buttons() if button_box is not None else []
    visible_children = [
        child
        for child in editor.findChildren(QWidget)
        if child.isVisible()
        and not child.isWindow()
        # QSizeGrip belongs to the native resize frame and can intentionally
        # straddle the client rect by a few pixels.  It is not editor content.
        and not child.inherits("QSizeGrip")
    ]
    screen = editor.screen()
    screen_geometry = screen.availableGeometry() if screen is not None else None
    check(
        "{} uses its intended capture geometry".format(label),
        editor.width() == expected_width and editor.height() == expected_height,
        {
            "expected": [expected_width, expected_height],
            "actual": [editor.width(), editor.height()],
        },
    )
    check(
        "{} content remains inside the editor".format(label),
        bool(visible_children)
        and all(_widget_inside_dialog(editor, child) for child in visible_children),
        {
            "outside": [
                child.objectName() or child.metaObject().className()
                for child in visible_children
                if not _widget_inside_dialog(editor, child)
            ]
        },
    )
    check(
        "{} actions remain visible and inside the editor".format(label),
        bool(action_buttons)
        and all(
            button.isVisible() and _widget_inside_dialog(editor, button)
            for button in action_buttons
        ),
        [button.text() for button in action_buttons],
    )
    check(
        "{} remains inside the available screen".format(label),
        screen_geometry is not None and screen_geometry.contains(editor.frameGeometry()),
        {
            "screen": (
                [
                    screen_geometry.x(),
                    screen_geometry.y(),
                    screen_geometry.width(),
                    screen_geometry.height(),
                ]
                if screen_geometry is not None
                else None
            ),
            "editor": [
                editor.frameGeometry().x(),
                editor.frameGeometry().y(),
                editor.frameGeometry().width(),
                editor.frameGeometry().height(),
            ],
        },
    )


def capture_editors(
    dialog: Any,
    prefix: str,
    size_mode: str,
    callback: Callable[[], None],
) -> None:
    from home_dashboard_overhaul.settings import EventEditDialog, TextEditDialog

    if size_mode not in {"default", "minimum"}:
        raise ValueError("unsupported editor capture size: {}".format(size_mode))

    event = EventEditDialog(
        dialog,
        {
            "id": "probe-event",
            "name": "A long board-examination event name that demonstrates the complete editor",
            "date": date.today().isoformat(),
            "archived": False,
        },
    )
    if size_mode == "minimum":
        event.resize(event.minimumSize().expandedTo(event.minimumSizeHint()))
    event_target = event.size()
    event.show()

    def event_ready() -> None:
        _editor_geometry_checks(
            event,
            "{} event editor".format(prefix),
            event_target.width(),
            event_target.height(),
        )
        capture("{}-event-editor".format(prefix), event)
        event.reject()
        verse = TextEditDialog(
            "Edit Bible verse",
            "For this is how God loved the world. <br>- John 3:16 (NLT)",
            dialog,
        )
        if size_mode == "minimum":
            verse.resize(verse.minimumSize().expandedTo(verse.minimumSizeHint()))
        verse_target = verse.size()
        verse.show()

        def verse_ready() -> None:
            _editor_geometry_checks(
                verse,
                "{} verse editor".format(prefix),
                verse_target.width(),
                verse_target.height(),
            )
            capture("{}-verse-editor".format(prefix), verse)
            verse.reject()
            callback()

        QTimer.singleShot(240, verse_ready)

    QTimer.singleShot(240, event_ready)


def open_settings(attempt: int = 0) -> None:
    try:
        controller = getattr(mw, "_home_dashboard_overhaul_controller", None)
        if getattr(mw, "state", "") != "deckBrowser" or controller is None:
            if attempt >= 50:
                raise RuntimeError("Home Dashboard controller did not become ready")
            QTimer.singleShot(200, lambda: open_settings(attempt + 1))
            return
        if not identity_gate():
            raise RuntimeError("Disposable Anki identity or exact-package gate failed")
        controller.open_settings("appearance")
        QTimer.singleShot(300, lambda: wait_for_dialog(0))
    except Exception as exc:
        fail("open_settings", exc)
        QTimer.singleShot(300, mw.close)


def wait_for_dialog(attempt: int) -> None:
    dialog = mw._home_dashboard_overhaul_controller.settings_dialog
    if dialog is None or not dialog.isVisible():
        if attempt >= 40:
            fail("wait_for_dialog", RuntimeError("Settings dialog did not open"))
            QTimer.singleShot(300, mw.close)
            return
        QTimer.singleShot(200, lambda: wait_for_dialog(attempt + 1))
        return
    dialog.resize(1280, 820)
    QTimer.singleShot(350, lambda: begin_capture(dialog))


def begin_capture(dialog: Any) -> None:
    check("initial draft is clean", not dialog.draft.dirty, sorted("/".join(path) for path in dialog.draft.changed_paths))
    check("save disabled while clean", not dialog.save_button.isEnabled())
    check("unsaved indicator hidden while clean", not dialog.dirty_badge.isVisible())
    check("wide navigation rail visible", dialog.nav.isVisible() and not dialog.section_selector_wrap.isVisible())
    check("wide contextual preview visible", dialog.preview_wrap.isVisible())
    named_widgets = (
        dialog.nav,
        dialog.section_selector,
        dialog.preview,
        dialog.preset,
        dialog.calendar_view,
        dialog.event_search,
        dialog.quote_list,
        dialog.save_button,
    )
    check(
        "representative controls have accessible names",
        all(bool(widget.accessibleName().strip()) for widget in named_widgets),
        [widget.accessibleName() for widget in named_widgets],
    )
    check(
        "interactive controls accept keyboard focus",
        all(widget.focusPolicy() != Qt.FocusPolicy.NoFocus for widget in named_widgets if widget is not dialog.preview),
    )
    cancel_button = dialog.buttons.button(QDialogButtonBox.StandardButton.Cancel)
    check(
        "tab order reaches fixed action bar",
        cancel_button is not None and focus_chain_reaches(dialog.nav, cancel_button),
    )
    capture_pages(
        dialog,
        "desktop",
        0,
        lambda: capture_editors(
            dialog,
            "desktop",
            "default",
            lambda: capture_desktop_variants(dialog),
        ),
    )


def capture_desktop_variants(dialog: Any) -> None:
    baseline_preset = dialog.preset.currentData()
    baseline_mode = dialog.mode.currentData()
    dialog._set_combo_data(dialog.mode, "light")
    dialog.open_page("calendar")

    def light_ready() -> None:
        capture("desktop-light-calendar", dialog)
        dialog._set_combo_data(dialog.mode, "dark")
        dialog.open_page("events")
        QTimer.singleShot(350, dark_ready)

    def dark_ready() -> None:
        capture("desktop-dark-events", dialog)
        dialog._set_combo_data(dialog.preset, baseline_preset)
        dialog._set_combo_data(dialog.mode, baseline_mode)
        dialog._sync_draft()
        capture_minimum(dialog)

    QTimer.singleShot(350, light_ready)


def capture_minimum(dialog: Any) -> None:
    dialog.resize(760, 560)
    QTimer.singleShot(
        350,
        lambda: capture_pages(
            dialog,
            "minimum",
            0,
            lambda: capture_editors(
                dialog,
                "minimum",
                "minimum",
                lambda: capture_scaled_variants(dialog),
            ),
        ),
    )


def capture_scaled_variants(dialog: Any) -> None:
    baseline_preset = dialog.preset.currentData()
    baseline_mode = dialog.mode.currentData()
    original_font = dialog.font()
    original_size = original_font.pointSizeF()
    if original_size <= 0:
        original_size = 13.0
    scaled = dialog.font()
    scaled.setPointSizeF(original_size * 1.5)
    dialog.setFont(scaled)
    dialog._set_combo_data(dialog.mode, "dark")
    dialog.open_page("calendar")

    def scale_150_ready() -> None:
        capture("scale-150-dark-calendar", dialog)
        larger = dialog.font()
        larger.setPointSizeF(original_size * 2.0)
        dialog.setFont(larger)
        dialog._set_combo_data(dialog.preset, "High Contrast")
        dialog._set_combo_data(dialog.mode, "light")
        dialog.open_page("dashboard")
        QTimer.singleShot(400, scale_200_ready)

    def scale_200_ready() -> None:
        capture("scale-200-high-contrast-home", dialog)
        dialog.setFont(original_font)
        dialog._set_combo_data(dialog.preset, baseline_preset)
        dialog._set_combo_data(dialog.mode, baseline_mode)
        dialog._sync_draft()
        QTimer.singleShot(300, lambda: interaction_checks(dialog))

    QTimer.singleShot(400, scale_150_ready)


def interaction_checks(dialog: Any) -> None:
    try:
        dialog.resize(760, 560)
        QApplication.processEvents()
        check("compact top selector visible", dialog.section_selector_wrap.isVisible() and not dialog.nav.isVisible())
        check("compact preview collapsed by default", not dialog.preview_wrap.isVisible())
        horizontal_overflow = {}
        for _slug, alias in PAGES:
            dialog.open_page(alias)
            QApplication.processEvents()
            page_scroll = dialog.stack.currentWidget()
            horizontal_overflow[alias] = int(page_scroll.horizontalScrollBar().maximum())
        check(
            "all compact pages avoid horizontal overflow",
            all(value == 0 for value in horizontal_overflow.values()),
            horizontal_overflow,
        )
        dialog.open_page("events")
        cancel_button = dialog.buttons.button(QDialogButtonBox.StandardButton.Cancel)
        action_buttons = (dialog.preview_toggle, cancel_button, dialog.save_button)
        check(
            "fixed compact actions remain fully inside the window",
            all(
                button is not None
                and button.isVisible()
                and dialog.rect().contains(button.mapTo(dialog, button.rect().topLeft()))
                and dialog.rect().contains(button.mapTo(dialog, button.rect().bottomRight()))
                for button in action_buttons
            ),
        )

        dialog.open_page("dashboard")
        calendar_box = dialog.visibility["heatmap"]
        events_box = dialog.visibility["events"]
        original_calendar = calendar_box.isChecked()
        original_events = events_box.isChecked()
        calendar_box.setChecked(False)
        QApplication.processEvents()
        check("event dependency disables without erasing", not events_box.isEnabled() and events_box.isChecked() == original_events)
        calendar_box.setChecked(original_calendar)

        today_box = dialog.visibility["today"]
        original_today = today_box.isChecked()
        original_eta = dialog.show_eta.isChecked()
        today_box.setChecked(False)
        QApplication.processEvents()
        check("ETA dependency disables without erasing", not dialog.show_eta.isEnabled() and dialog.show_eta.isChecked() == original_eta)
        today_box.setChecked(original_today)

        dialog.open_page("calendar")
        original_forecast = dialog.show_forecast.isChecked()
        dialog.show_forecast.setChecked(False)
        QApplication.processEvents()
        check("forecast master disables range", not dialog.forecast_days.isEnabled())
        dialog.show_forecast.setChecked(original_forecast)

        dialog.open_page("bible")
        original_theme_color = dialog.theme_color.isChecked()
        dialog.theme_color.setChecked(True)
        QApplication.processEvents()
        check("theme-aware verse color disables custom control", not dialog.font_color.isEnabled())
        dialog.theme_color.setChecked(original_theme_color)
        check("verse library enforces a non-empty bounded count", 1 <= len(dialog.quotes) <= 500)

        dialog.open_page("events")
        check("event tables use Date and Event only", dialog.active_events.columnCount() == 2)
        check("empty event actions start disabled", not dialog.event_edit.isEnabled() and not dialog.event_delete.isEnabled())

        dialog.open_page("about")
        QApplication.processEvents()
        check("About uses full editor width", not dialog.preview_wrap.isVisible())

        dialog.open_page("appearance")
        dialog.preview_toggle.setChecked(True)
        QApplication.processEvents()
        check("compact preview toggle opens below editor", dialog.preview_wrap.isVisible() and dialog.splitter.orientation() == Qt.Orientation.Vertical)
        dialog.preview_toggle.setChecked(False)

        controller = dialog.controller
        cached_snapshot = controller.snapshot
        controller.snapshot = None
        dialog.preview_toggle.setChecked(True)
        dialog._render_preview()
        check("missing live snapshot is marked as sample data", dialog.preview_data_badge.text() == "Sample data")
        controller.snapshot = cached_snapshot
        dialog._render_preview()
        dialog.preview_toggle.setChecked(False)

        saved_event_count = len(controller.config["events"]["items"])
        saved_quote_count = len(controller.config["bible"]["quotes"])
        dialog.staged["events"]["items"].append(
            {
                "id": "qa-cancel-event",
                "name": "Discarded QA event",
                "date": date.today().isoformat(),
                "archived": False,
                "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                "archived_at": "",
            }
        )
        dialog.quotes.append("Discarded QA verse <br>- QA 1:1")
        dialog._refresh_event_lists()
        dialog._refresh_quote_list()
        original_opacity = dialog.opacity.value()
        changed_opacity = original_opacity - 1 if original_opacity > dialog.opacity.minimum() else original_opacity + 1
        dialog.opacity.setValue(changed_opacity)
        QApplication.processEvents()
        check("editing enables Save and dirty indicator", dialog.draft.dirty and dialog.save_button.isEnabled() and dialog.dirty_badge.isVisible())

        QTimer.singleShot(80, lambda: click_message_button(QMessageBox.StandardButton.Cancel))
        dialog.reject()
        check("Cancel keeps a dirty editor open", dialog.isVisible() and dialog.draft.dirty)

        QTimer.singleShot(80, lambda: click_message_button(QMessageBox.StandardButton.Discard))
        dialog.reject()
        check("Discard closes the dirty editor", not dialog.isVisible())
        check(
            "Discard preserves saved events and verses",
            len(controller.config["events"]["items"]) == saved_event_count
            and len(controller.config["bible"]["quotes"]) == saved_quote_count
            and all(item.get("id") != "qa-cancel-event" for item in controller.config["events"]["items"]),
        )
        QTimer.singleShot(250, lambda: begin_persistence_write(dialog))
    except Exception as exc:
        fail("interaction_checks", exc)
        try:
            dialog._allow_close = True
            dialog.reject()
        except Exception:
            pass
        QTimer.singleShot(300, mw.close)


def click_message_button(standard_button: QMessageBox.StandardButton) -> None:
    for widget in QApplication.topLevelWidgets():
        if isinstance(widget, QMessageBox) and widget.isVisible():
            button = widget.button(standard_button)
            if button is not None:
                button.click()
                return


def inspect_and_keep_conflict() -> None:
    for widget in QApplication.topLevelWidgets():
        if not isinstance(widget, QMessageBox) or not widget.isVisible():
            continue
        labels = [
            button.text().replace("&", "")
            for button in widget.buttons()
        ]
        check(
            "conflict prompt offers reload, keep, and cancel recovery",
            {"Reload latest", "Keep my staged value", "Cancel"}.issubset(set(labels)),
            labels,
        )
        for button in widget.buttons():
            if button.text().replace("&", "") == "Keep my staged value":
                button.click()
                return


def verse_identity(verse: Any) -> list[str]:
    return [str(verse.body_html), str(verse.reference_html)]


def rotation_bytes() -> bytes:
    return ROTATION_PATH.read_bytes() if ROTATION_PATH.is_file() else b""


def begin_persistence_write(original_dialog: Any) -> None:
    try:
        controller = mw._home_dashboard_overhaul_controller
        selected_before = controller._selected_verse()
        before_bytes = rotation_bytes()
        RESULTS["appearance_persistence_before"] = {
            "selected_verse": verse_identity(selected_before),
            "rotation_sha256": hashlib.sha256(before_bytes).hexdigest(),
            "data_generation": int(controller.data_generation),
            "opacity": int(controller.config["appearance"]["opacity"]),
        }
        controller.open_settings("appearance")
        QTimer.singleShot(
            300,
            lambda: wait_for_persistence_dialog(original_dialog, before_bytes, 0),
        )
    except Exception as exc:
        fail("begin_persistence_write", exc)
        QTimer.singleShot(300, mw.close)


def wait_for_persistence_dialog(
    original_dialog: Any,
    before_bytes: bytes,
    attempt: int,
) -> None:
    controller = mw._home_dashboard_overhaul_controller
    dialog = controller.settings_dialog
    if dialog is None or not dialog.isVisible():
        if attempt >= 40:
            fail("wait_for_persistence_dialog", RuntimeError("Appearance persistence dialog did not open"))
            QTimer.singleShot(300, mw.close)
            return
        QTimer.singleShot(
            150,
            lambda: wait_for_persistence_dialog(original_dialog, before_bytes, attempt + 1),
        )
        return
    before_generation = int(controller.data_generation)
    original_opacity = int(dialog.opacity.value())
    changed_opacity = (
        original_opacity - 1
        if original_opacity > dialog.opacity.minimum()
        else original_opacity + 1
    )
    dialog.opacity.setValue(changed_opacity)
    QApplication.processEvents()
    check("appearance-only edit becomes dirty", dialog.draft.dirty and dialog.save_button.isEnabled())
    external = deepcopy(controller.config)
    external_opacity = (
        changed_opacity - 1
        if changed_opacity > dialog.opacity.minimum()
        else changed_opacity + 1
    )
    external_density = (
        "compact"
        if external["appearance"]["density"] != "compact"
        else "spacious"
    )
    external["appearance"]["opacity"] = external_opacity
    external["appearance"]["density"] = external_density
    mw.addonManager.writeConfig(controller.package, external)
    QTimer.singleShot(80, inspect_and_keep_conflict)
    dialog._save()
    QTimer.singleShot(
        300,
        lambda: verify_appearance_save(
            original_dialog,
            before_bytes,
            before_generation,
            changed_opacity,
            external_density,
        ),
    )


def verify_appearance_save(
    original_dialog: Any,
    before_bytes: bytes,
    before_generation: int,
    changed_opacity: int,
    external_density: str,
) -> None:
    try:
        controller = mw._home_dashboard_overhaul_controller
        selected_after = controller._selected_verse()
        stored = mw.addonManager.getConfig(controller.package)
        check(
            "appearance-only Save persists its value",
            int(controller.config["appearance"]["opacity"]) == changed_opacity
            and int(stored["appearance"]["opacity"]) == changed_opacity
            and controller.config["appearance"]["density"] == external_density
            and stored["appearance"]["density"] == external_density,
            {
                "kept_local_opacity": int(controller.config["appearance"]["opacity"]),
                "merged_external_density": controller.config["appearance"]["density"],
            },
        )
        check(
            "appearance-only Save does not invalidate analytics",
            int(controller.data_generation) == before_generation,
            {"before": before_generation, "after": int(controller.data_generation)},
        )
        check(
            "appearance-only Save preserves selected verse and rotation bytes",
            verse_identity(selected_after)
            == RESULTS["appearance_persistence_before"]["selected_verse"]
            and rotation_bytes() == before_bytes,
        )
        controller.open_settings("events")
        QTimer.singleShot(
            300,
            lambda: wait_for_content_dialog(original_dialog, changed_opacity, 0),
        )
    except Exception as exc:
        fail("verify_appearance_save", exc)
        QTimer.singleShot(300, mw.close)


def wait_for_content_dialog(
    original_dialog: Any,
    changed_opacity: int,
    attempt: int,
) -> None:
    controller = mw._home_dashboard_overhaul_controller
    dialog = controller.settings_dialog
    if dialog is None or not dialog.isVisible():
        if attempt >= 40:
            fail("wait_for_content_dialog", RuntimeError("Content persistence dialog did not open"))
            QTimer.singleShot(300, mw.close)
            return
        QTimer.singleShot(
            150,
            lambda: wait_for_content_dialog(original_dialog, changed_opacity, attempt + 1),
        )
        return
    check("reopened editor is clean after appearance Save", not dialog.draft.dirty and not dialog.save_button.isEnabled())
    event_id = "qa-persist-event"
    quote = "Persistent QA verse <br>- QA 2:2"
    dialog.staged["events"]["items"] = [
        item
        for item in dialog.staged["events"]["items"]
        if item.get("id") != event_id
    ]
    dialog.staged["events"]["items"].append(
        {
            "id": event_id,
            "name": "Persistent QA event",
            "date": date.today().isoformat(),
            "archived": False,
            "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "archived_at": "",
        }
    )
    if quote not in dialog.quotes:
        dialog.quotes.append(quote)
    dialog._refresh_event_lists()
    dialog._refresh_quote_list()
    dialog._sync_draft()
    check("staged event and verse edits enable Save", dialog.draft.dirty and dialog.save_button.isEnabled())
    dialog._save()
    QTimer.singleShot(
        350,
        lambda: finish_persistence_write(
            original_dialog,
            changed_opacity,
            event_id,
            quote,
        ),
    )


def finish_persistence_write(
    original_dialog: Any,
    changed_opacity: int,
    event_id: str,
    quote: str,
) -> None:
    try:
        controller = mw._home_dashboard_overhaul_controller
        selected = controller._selected_verse()
        saved_rotation = rotation_bytes()
        state = {
            "opacity": changed_opacity,
            "density": str(controller.config["appearance"]["density"]),
            "event_id": event_id,
            "quote": quote,
            "selected_verse": verse_identity(selected),
            "rotation_sha256": hashlib.sha256(saved_rotation).hexdigest(),
        }
        write_json(PERSISTENCE_PATH, state)
        check(
            "event and verse library Save updates staged content",
            any(item.get("id") == event_id for item in controller.config["events"]["items"])
            and quote in controller.config["bible"]["quotes"],
        )
        check("rotation state is valid after verse library Save", bool(saved_rotation))
        RESULTS["persistence_state"] = state
        complete(original_dialog)
    except Exception as exc:
        fail("finish_persistence_write", exc)
        QTimer.singleShot(300, mw.close)


def open_restart(attempt: int = 0) -> None:
    try:
        controller = getattr(mw, "_home_dashboard_overhaul_controller", None)
        if getattr(mw, "state", "") != "deckBrowser" or controller is None:
            if attempt >= 50:
                raise RuntimeError("Home Dashboard controller did not become ready after restart")
            QTimer.singleShot(200, lambda: open_restart(attempt + 1))
            return
        if not identity_gate():
            raise RuntimeError("Restart identity or exact-package gate failed")
        expected = json.loads(PERSISTENCE_PATH.read_text(encoding="utf-8"))
        before_bytes = rotation_bytes()
        selected = controller._selected_verse()
        after_bytes = rotation_bytes()
        check(
            "appearance, event, and verse library persist after restart",
            int(controller.config["appearance"]["opacity"]) == int(expected["opacity"])
            and controller.config["appearance"]["density"] == expected["density"]
            and any(
                item.get("id") == expected["event_id"]
                for item in controller.config["events"]["items"]
            )
            and expected["quote"] in controller.config["bible"]["quotes"],
        )
        check(
            "selected verse and rotation state persist after restart",
            verse_identity(selected) == expected["selected_verse"]
            and hashlib.sha256(before_bytes).hexdigest() == expected["rotation_sha256"]
            and before_bytes == after_bytes,
        )
        controller.open_settings("events")
        QTimer.singleShot(300, lambda: wait_for_restart_dialog(expected, 0))
    except Exception as exc:
        fail("open_restart", exc)
        QTimer.singleShot(300, mw.close)


def wait_for_restart_dialog(expected: dict[str, Any], attempt: int) -> None:
    controller = mw._home_dashboard_overhaul_controller
    dialog = controller.settings_dialog
    if dialog is None or not dialog.isVisible():
        if attempt >= 40:
            fail("wait_for_restart_dialog", RuntimeError("Restart settings dialog did not open"))
            QTimer.singleShot(300, mw.close)
            return
        QTimer.singleShot(150, lambda: wait_for_restart_dialog(expected, attempt + 1))
        return
    dialog.resize(760, 560)
    QApplication.processEvents()
    check("settings editor reopens clean after restart", not dialog.draft.dirty and not dialog.save_button.isEnabled())
    check(
        "reopened editor contains persisted content",
        any(item.get("id") == expected["event_id"] for item in dialog.staged["events"]["items"])
        and expected["quote"] in dialog.quotes,
    )
    capture("restart-persistence", dialog)
    RESULTS["complete"] = (
        not RESULTS["errors"]
        and bool(RESULTS.get("identity_gate", {}).get("all_gates"))
        and bool(RESULTS.get("package_integrity", {}).get("passed"))
        and len(RESULTS["captures"]) == 1
        and RESULTS["runtime_checks"]
        and all(item["passed"] for item in RESULTS["runtime_checks"])
    )
    save()
    dialog._allow_close = True
    dialog.reject()
    QTimer.singleShot(450, mw.close)


def complete(dialog: Any) -> None:
    RESULTS["navigation_items"] = [
        dialog.nav.item(index).text() for index in range(dialog.nav.count())
    ] if hasattr(dialog, "nav") else []
    RESULTS["complete"] = (
        not RESULTS["errors"]
        and bool(RESULTS.get("identity_gate", {}).get("all_gates"))
        and bool(RESULTS.get("package_integrity", {}).get("passed"))
        and len(RESULTS["captures"]) == 20
        and RESULTS["runtime_checks"]
        and all(item["passed"] for item in RESULTS["runtime_checks"])
    )
    save()
    QTimer.singleShot(450, mw.close)


QTimer.singleShot(
    2400,
    open_restart if PHASE.endswith("-restart") else open_settings,
)
