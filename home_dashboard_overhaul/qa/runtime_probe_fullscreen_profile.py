"""Full-screen capture behavior layered over the plan-driven release probe."""

from __future__ import annotations

from typing import Any, Mapping

from aqt import mw
from aqt.qt import QApplication, QTimer

from . import _release_probe as probe


base = probe.base
PROFILE_ID = probe.CAPTURE_PROFILE
PROFILE_SPEC = probe.PROFILE_SPEC
FRAME_MARGIN = 48

base._require(bool(PROFILE_SPEC.get("full_screen")), "fullscreen adapter used by a non-fullscreen profile")

_release_capture_production = base._capture
_release_capture_settings = probe._capture_settings
_release_prepare_settings = probe._prepare_settings_case
_release_settings_state = probe._settings_state


def _fullscreen_geometry() -> dict[str, Any]:
    screen = base._qa_screen()
    geometry = screen.geometry()
    frame = mw.frameGeometry()
    return {
        "screen_name": screen.name(),
        "device_pixel_ratio": screen.devicePixelRatio(),
        "screen_geometry": [
            geometry.x(), geometry.y(), geometry.width(), geometry.height()
        ],
        "window_frame": [frame.x(), frame.y(), frame.width(), frame.height()],
        "is_full_screen": bool(mw.isFullScreen()),
    }


def _fit_fullscreen(case: Mapping[str, Any], continuation: Any, attempt: int = 0) -> None:
    try:
        screen = base._qa_screen()
        handle = mw.windowHandle()
        handle_screen = handle.screen() if handle is not None else mw.screen()
        base._require(
            handle_screen is None or handle_screen.name() == screen.name(),
            "isolated Anki window must already be on the capture display before fullscreen",
        )
        # Enter full screen in place. Moving, raising, or activating an already
        # visible native window can cross macOS Spaces and would invalidate the
        # exact behavior this profile is intended to observe.
        if not mw.isFullScreen():
            mw.showFullScreen()
        QApplication.processEvents()
        handle = mw.windowHandle()
        handle_screen = handle.screen() if handle is not None else mw.screen()
        settled = (
            bool(mw.isFullScreen())
            and handle_screen is not None
            and handle_screen.name() == screen.name()
        )
        if not settled and attempt < 12:
            QTimer.singleShot(300, lambda: _fit_fullscreen(case, continuation, attempt + 1))
            return
        base._require(bool(mw.isFullScreen()), "isolated Anki main window did not enter fullscreen")
        base._require(
            handle_screen is not None and handle_screen.name() == screen.name(),
            "fullscreen window settled on the wrong display",
        )
        geometry = _fullscreen_geometry()
        base.REPORT["capture_display"] = geometry
        base._require(
            geometry["window_frame"][2] >= geometry["screen_geometry"][2] - 4,
            "fullscreen frame does not span the capture display width",
        )
        base._write_report()
        continuation()
    except Exception as exc:
        base._error(str(case.get("id", "fullscreen-frame")), exc)


def _capture_fullscreen(case: Mapping[str, Any], state: Mapping[str, Any]) -> None:
    base._require(bool(mw.isFullScreen()), "production capture lost fullscreen state")
    _release_capture_production(case, state)
    record = base.REPORT["captures"][str(case["id"])]
    record["full_screen"] = True
    record["capture_display"] = _fullscreen_geometry()
    record["capture_profile"] = PROFILE_ID
    record["capture_plan_sha256"] = probe.CAPTURE_PLAN.sha256
    base._write_report()


def _settings_state(dialog: Any, case: Mapping[str, Any]) -> dict[str, Any]:
    state = _release_settings_state(dialog, case)
    state["parent_full_screen"] = bool(mw.isFullScreen())
    state["display_class"] = "wide"
    state["fullscreen_safe_margin"] = int(
        dialog.property("hdoFullscreenSafeMargin") or 0
    )
    return state


def _prepare_settings_case(case: Mapping[str, Any]) -> Any:
    """Fit the settled decorated Settings frame inside its full-screen Space."""

    dialog = _release_prepare_settings(case)
    screen = probe._settings_screen(dialog)
    available = screen.availableGeometry()
    target_width = max(1, available.width() - (2 * FRAME_MARGIN))
    target_height = max(1, available.height() - (2 * FRAME_MARGIN))
    base._require(
        target_width >= 1200 and target_height >= 700,
        "capture display cannot support the wide Settings profile with safe margins",
    )
    special = str(case.get("special", ""))
    if special in {"window-fresh-open", "window-clamp"}:
        dialog.setMaximumSize(16777215, 16777215)
        dialog.resize(target_width, target_height)
    else:
        dialog.setFixedSize(target_width, target_height)
    dialog.setProperty("hdoFullscreenSafeMargin", FRAME_MARGIN)
    QApplication.processEvents()
    for _attempt in range(3):
        frame = dialog.frameGeometry()
        target_x = available.x() + (available.width() - frame.width()) // 2
        target_y = available.y() + (available.height() - frame.height()) // 2
        dialog.move(
            dialog.x() + target_x - frame.x(),
            dialog.y() + target_y - frame.y(),
        )
        QApplication.processEvents()
    frame = dialog.frameGeometry()
    base._require(
        frame.left() >= available.left()
        and frame.top() >= available.top()
        and frame.right() <= available.right()
        and frame.bottom() <= available.bottom(),
        "fullscreen-safe Settings frame escaped the capture display",
    )
    return dialog


def _capture_settings(
    dialog: Any,
    case: Mapping[str, Any],
    state: Mapping[str, Any],
) -> None:
    QApplication.processEvents()
    base._require(bool(mw.isFullScreen()), "Settings parent lost fullscreen state")
    base._require(state.get("font_percent") == 100, "Settings capture is not 100 percent text")
    base._require(state.get("display_class") == "wide", "Settings capture is not wide")
    if str(case.get("special", "")) == "window-fresh-open":
        _release_capture_settings(dialog, case, state)
        record = base.REPORT["captures"][str(case["id"])]
        record["capture_profile"] = PROFILE_ID
        record["capture_plan_sha256"] = probe.CAPTURE_PLAN.sha256
        record["full_screen_parent"] = True
        record["capture_display"] = _fullscreen_geometry()
        base._write_report()
        return

    pixmap = dialog.grab()
    base._require(not pixmap.isNull(), "native Settings client capture is null")
    color_count = base._sample_color_count(pixmap)
    base._require(color_count >= 3, "native Settings client capture appears blank")
    ratio = max(1.0, float(pixmap.devicePixelRatio()))
    logical_width = pixmap.width() / ratio
    logical_height = pixmap.height() / ratio
    base._require(
        abs(logical_width - dialog.width()) <= 4,
        "Settings client capture width differs from its fullscreen dialog",
    )
    base._require(
        abs(logical_height - dialog.height()) <= 4,
        "Settings client capture height differs from its fullscreen dialog",
    )
    probe.CAPTURE_ROOT.mkdir(parents=True, exist_ok=True)
    path = probe.CAPTURE_ROOT / "{}.png".format(case["id"])
    base._require(bool(pixmap.save(str(path), "PNG")), "could not save Settings capture")
    base.REPORT["captures"][str(case["id"])] = {
        "file": str(path.relative_to(probe.OUTPUT_ROOT)),
        "sha256": base._sha256(path),
        "component": "canonical-settings",
        "page": state.get("section"),
        "font_percent": 100,
        "display_class": "wide",
        "full_screen_parent": True,
        "capture_profile": PROFILE_ID,
        "capture_plan_sha256": probe.CAPTURE_PLAN.sha256,
        "capture_method": "QDialog.grab-full-width-client",
        "sampled_color_count": color_count,
        "logical_frame": {"width": dialog.width(), "height": dialog.height()},
        "physical_pixels": [pixmap.width(), pixmap.height()],
        "device_pixel_ratio": pixmap.devicePixelRatio(),
        "parent_window_title": str(mw.windowTitle()),
        "parent_window_title_matches_profile": base.EXPECTED_PROFILE in str(mw.windowTitle()),
        "capture_display": _fullscreen_geometry(),
        "state": dict(state),
    }
    base._write_report()


probe._settings_state = _settings_state
probe._prepare_settings_case = _prepare_settings_case
probe._capture_settings = _capture_settings
base._fit_native_frame = _fit_fullscreen
base._capture = _capture_fullscreen
base.REPORT["scale_policy"] = {
    "production_ui_percent": 100,
    "production_text_percent": 100,
    "settings_application_font_percent": [100],
    "dpr_1_acceptance": "unrun",
    "os_display_scaling_acceptance": "unrun",
}
base.REPORT["capture_profile"].update({
    "full_screen": True,
    "display_class": "wide",
    "ui_scale_percent": 100,
    "text_scale_percent": 100,
    "settings_application_font_percent": 100,
})
