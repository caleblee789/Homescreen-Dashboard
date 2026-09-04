"""Observe real Settings routes on a disposable native macOS full-screen Space.

Run after the standard capture/restart sequence, with this file copied as
``_workflow_probe.py`` beside the generated helper. Both stages use the same
isolated base and instance key. This is automated native evidence, not human
visual approval. Every interaction is gated by the retained isolation probe.
"""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
from pathlib import Path
import traceback

from aqt import gui_hooks, mw
from aqt.qt import QApplication, QDialog, QEventLoop, QPoint, QRect, QTimer

import home_dashboard_overhaul
from home_dashboard_overhaul.settings import EventEditDialog, TextEditDialog
from . import _probe_base as base


ROOT = Path(os.environ.get("HDO_RELEASE_RUN_ROOT", ""))
STAGE = os.environ.get("HDO_SETTINGS_WORKFLOW_STAGE", "initial")
FULLSCREEN_REQUIRED = os.environ.get("HDO_SETTINGS_WORKFLOW_WINDOWED") != "1"
OUTPUT = ROOT / ("settings-fullscreen-workflow" if FULLSCREEN_REQUIRED else "settings-windowed-workflow")
ENABLED = str(ROOT).startswith("/private/tmp/anki-release-qa.") and STAGE in {"initial", "restart"}
_started = False
observations: list[dict] = []
EVENT_PREFIX = "Release QA {} {}".format(STAGE, os.getpid())


def require(value: object, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def settle(milliseconds: int = 180) -> None:
    loop = QEventLoop()
    QTimer.singleShot(milliseconds, loop.quit)
    loop.exec()


def native_space() -> dict:
    """Read the owning NSWindow, rather than inferring Space from Qt size."""
    objc = ctypes.CDLL("/usr/lib/libobjc.A.dylib")
    selector = objc.sel_registerName
    selector.argtypes = (ctypes.c_char_p,)
    selector.restype = ctypes.c_void_p
    send_pointer = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(("objc_msgSend", objc))
    send_bool = ctypes.CFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)(("objc_msgSend", objc))
    send_uint = ctypes.CFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p, ctypes.c_void_p)(("objc_msgSend", objc))
    window = send_pointer(int(mw.winId()), selector(b"window"))
    require(window, "Anki has no owning NSWindow")
    return {
        "qt_fullscreen": bool(mw.isFullScreen()),
        "native_fullscreen": bool(send_uint(window, selector(b"styleMask")) & (1 << 14)),
        "main_window_on_active_space": bool(send_bool(window, selector(b"isOnActiveSpace"))),
    }


def native_window_diagnostics() -> dict:
    objc = ctypes.CDLL("/usr/lib/libobjc.A.dylib")
    selector = objc.sel_registerName
    selector.argtypes = (ctypes.c_char_p,)
    selector.restype = ctypes.c_void_p
    send = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(("objc_msgSend", objc))
    send_uint = ctypes.CFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p, ctypes.c_void_p)(("objc_msgSend", objc))
    window = send(int(mw.winId()), selector(b"window"))
    return {
        "qt_visible": mw.isVisible(),
        "qt_minimized": mw.isMinimized(),
        "qt_window_state": int(mw.windowState().value),
        "qt_screen": mw.screen().name(),
        **{name: int(send_uint(window, selector(name.encode()))) for name in (
            "styleMask", "collectionBehavior", "isVisible", "isMiniaturized",
            "canBecomeKeyWindow", "isKeyWindow", "isOnActiveSpace",
        )},
    }


def enter_native_fullscreen() -> None:
    """Use AppKit's native fullscreen action on this process's own window."""
    objc = ctypes.CDLL("/usr/lib/libobjc.A.dylib")
    selector = objc.sel_registerName
    selector.argtypes = (ctypes.c_char_p,)
    selector.restype = ctypes.c_void_p
    get_class = objc.objc_getClass
    get_class.argtypes = (ctypes.c_char_p,)
    get_class.restype = ctypes.c_void_p
    send = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(("objc_msgSend", objc))
    activate = ctypes.CFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong)(("objc_msgSend", objc))
    action = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(("objc_msgSend", objc))
    application = send(get_class(b"NSRunningApplication"), selector(b"currentApplication"))
    require(activate(application, selector(b"activateWithOptions:"), 2), "Could not activate the disposable process")
    window = send(int(mw.winId()), selector(b"window"))
    action(window, selector(b"makeKeyAndOrderFront:"), None)
    settle(350)
    action(window, selector(b"toggleFullScreen:"), None)


def observe(route: str, step: str) -> None:
    state = native_space()
    objc = ctypes.CDLL("/usr/lib/libobjc.A.dylib")
    selector = objc.sel_registerName
    selector.argtypes = (ctypes.c_char_p,)
    selector.restype = ctypes.c_void_p
    get_class = objc.objc_getClass
    get_class.argtypes = (ctypes.c_char_p,)
    get_class.restype = ctypes.c_void_p
    send = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(("objc_msgSend", objc))
    send_int = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p)(("objc_msgSend", objc))
    workspace = send(get_class(b"NSWorkspace"), selector(b"sharedWorkspace"))
    front_app = send(workspace, selector(b"frontmostApplication"))
    front_pid = send_int(front_app, selector(b"processIdentifier"))
    main_window = send(int(mw.winId()), selector(b"window"))
    main_screen = send(main_window, selector(b"screen"))
    dialog = home_dashboard_overhaul.controller._active_settings_dialog
    if dialog is not None and dialog.isVisible():
        windows = [("settings", dialog)]
        windows.extend(("editor", w) for w in QApplication.topLevelWidgets()
                       if isinstance(w, (EventEditDialog, TextEditDialog))
                       and w.parentWidget() is dialog and w.isVisible())
        for name, widget in windows:
            window = send(int(widget.winId()), selector(b"window"))
            state[name + "_on_anki_display"] = send(window, selector(b"screen")) == main_screen
            state[name + "_on_active_space"] = bool(send_int(window, selector(b"isOnActiveSpace")))
    observations.append({"route": route, "step": step, **state, "frontmost_pid": front_pid})
    if FULLSCREEN_REQUIRED:
        if not all(state.values()) and front_pid != os.getpid():
            raise RuntimeError("Fullscreen observation interrupted by another foreground application")
        require(all(state.values()), "Native fullscreen was unavailable or lost during {} / {}".format(route, step))


def visible_fields(editor: object) -> None:
    viewport = editor.scroll.viewport()
    fields = (editor.name, editor.date) if isinstance(editor, EventEditDialog) else (editor.reference, editor.editor)
    for field in fields:
        origin = field.mapTo(viewport, QPoint(0, 0))
        rect = field.rect().translated(origin)
        require(field.isVisibleTo(editor) and viewport.rect().contains(rect), "An editor field is clipped")


def capture(dialog: object, label: str) -> None:
    screen = dialog.screen()
    pixmap = screen.grabWindow(0)
    require(not pixmap.isNull(), "Supplemental compositor capture is unavailable")
    frame, bounds = dialog.frameGeometry(), screen.geometry()
    ratio = pixmap.width() / bounds.width()
    rect = QRect(round((frame.x() - bounds.x()) * ratio), round((frame.y() - bounds.y()) * ratio), round(frame.width() * ratio), round(frame.height() * ratio))
    require(pixmap.copy(rect).save(str(OUTPUT / (STAGE + "-" + label + ".png")), "PNG"), "Supplemental capture did not save")


def edit(dialog: object, route: str, kind: str) -> None:
    failures: list[Exception] = []
    cls = EventEditDialog if kind == "event" else TextEditDialog

    def accept_editor() -> None:
        editor = next((w for w in QApplication.topLevelWidgets() if isinstance(w, cls) and w.parentWidget() is dialog and w.isVisible()), None)
        try:
            require(editor, "The requested editor did not open")
            visible_fields(editor)
            if kind == "event":
                editor.name.setText("{} {}".format(EVENT_PREFIX, route))
            else:
                editor.reference.setText("{} {}".format(EVENT_PREFIX, route))
            observe(route, kind + "-edit")
            editor._accept_if_valid()
        except Exception as exc:
            failures.append(exc)
            if editor is not None:
                editor.done(QDialog.DialogCode.Rejected)

    QTimer.singleShot(250, accept_editor)
    if kind == "event":
        dialog._add_event()
    else:
        dialog._edit_quote()
    if failures:
        raise failures[0]


def open_route(route: str, exercise: bool) -> None:
    controller = home_dashboard_overhaul.controller
    failures: list[Exception] = []
    done = QEventLoop()

    def inspect() -> None:
        dialog = controller._active_settings_dialog
        try:
            require(dialog is not None and dialog.isVisible(), "Settings did not open from " + route)
            observe(route, "open" if exercise else "close-reopen")
            if exercise:
                for page in ("dashboard", "appearance", "calendar", "events", "bible_verse", "bible_display", "about_support"):
                    dialog.open_page(page)
                    settle()
                    observe(route, "page:" + page)
                dialog.open_page("events")
                for tab in (1, 0):
                    dialog.event_tabs.setCurrentIndex(tab)
                    settle()
                    observe(route, "events-tabs")
                for size in ((860, 640), (1080, 760)):
                    dialog.resize(*size)
                    settle()
                    observe(route, "resize")
                edit(dialog, route, "event")
                dialog.open_page("bible_verse")
                settle()
                edit(dialog, route, "verse")
                dialog.rotation.setValue("manual")
                dialog._stage_selected_manual_quote()
                settle()
                require(dialog.pending_manual_quote is not None, "Manual verse was not staged")
                capture(dialog, route + "-pending-verse")
                dialog._save()
                settle(450)
                require(not dialog.draft.dirty and not dialog.footer.error_panel.isVisible(), "Settings failed to save")
                observe(route, "save")
                require(dialog.pending_manual_quote is None, "Saved verse is still pending")
                capture(dialog, route + "-current-verse")
            else:
                require(not dialog.draft.dirty, "Reopened Settings is dirty")
                require(any(e["name"] == "{} {}".format(EVENT_PREFIX, route) for e in dialog.staged["events"]["items"]), "Saved event did not persist")
        except Exception as exc:
            failures.append(exc)
        finally:
            if dialog is not None:
                dialog.done(QDialog.DialogCode.Rejected)
            done.quit()

    def launch() -> None:
        QTimer.singleShot(700, inspect)
        if route == "menu":
            mw._home_dashboard_overhaul_settings_action.trigger()
        else:
            mw.web.eval("document.querySelector('#hdo-dashboard button[data-hdo-command=\"calendar-settings\"]').click()")

    QTimer.singleShot(0, launch)
    done.exec()
    settle()
    if failures:
        raise failures[0]
    require(controller._active_settings_dialog is None, "Settings modal lifecycle did not finish")


def run() -> None:
    global _started
    if _started or not ENABLED:
        return
    _started = True
    OUTPUT.mkdir(parents=True, exist_ok=True)
    report: dict = {
        "release": "1.8.7",
        "stage": STAGE,
        "status": "running",
        "package_sha256": os.environ.get("HDO_RELEASE_CANDIDATE_SHA256"),
        "capture_plan_sha256": hashlib.sha256(Path(__file__).with_name("_capture_plan.json").read_bytes()).hexdigest(),
        "observations": observations,
        "input_method": "automated native QAction and production dashboard button",
        "human_visual_approval": False,
        "fullscreen_required": FULLSCREEN_REQUIRED,
        "saved_event_names": {route: "{} {}".format(EVENT_PREFIX, route) for route in ("menu", "dashboard-gear")},
    }
    try:
        base.RELEASE = "1.8.7"
        base.OUTPUT_ROOT = OUTPUT
        base.REPORT_PATH = OUTPUT / ("identity-" + STAGE + ".json")
        base._identity_gate()
        report["identity"] = base.REPORT["identity"]
        screen = base._qa_screen()
        available = screen.availableGeometry()
        # Move only the verified disposable window before entering full screen.
        mw.move(available.center().x() - mw.width() // 2, available.center().y() - mw.height() // 2)
        if STAGE == "restart":
            earlier = json.loads((OUTPUT / "workflow-initial.json").read_text())
            require(earlier["status"] == "passed", "Initial workflow did not pass")
            expected = earlier["saved_event_names"]["dashboard-gear"]
            require(any(e["name"] == expected for e in home_dashboard_overhaul.controller.config["events"]["items"]), "Workflow changes did not survive restart")
        # Establish focus on this verified QA window before measuring the
        # workflow. A background Qt fullscreen flag alone is not native proof.
        mw.raise_()
        mw.activateWindow()
        settle(600)
        report["before_fullscreen"] = native_window_diagnostics()
        if FULLSCREEN_REQUIRED:
            enter_native_fullscreen()
            for _attempt in range(50):
                settle(300)
                if all(native_space().values()):
                    break
            # AppKit publishes the fullscreen style bit before the Space
            # animation finishes. Opening a modal during that transition is
            # not the steady fullscreen workflow this probe is meant to test.
            settle(2000)
        report["after_fullscreen"] = native_window_diagnostics()
        observe("both", "native-fullscreen")
        for route in ("menu", "dashboard-gear"):
            open_route(route, True)
            open_route(route, False)
        report["status"] = "passed"
    except Exception:
        report["status"] = "failed"
        report["error"] = traceback.format_exc()
    finally:
        (OUTPUT / ("workflow-" + STAGE + ".json")).write_text(json.dumps(report, indent=2) + "\n")
        mw.showNormal()
        QTimer.singleShot(700, QApplication.instance().quit)


if ENABLED:
    gui_hooks.profile_did_open.append(lambda: QTimer.singleShot(1800, run))
