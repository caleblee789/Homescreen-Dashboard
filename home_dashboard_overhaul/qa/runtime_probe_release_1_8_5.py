"""Fail-closed native production and Settings probe for release 1.8.5.

The disposable helper add-on installs this module as ``__init__.py`` and the
retained 1.8.4 production harness as ``_probe_base.py``.  The retained harness
supplies exact-package identity, scheduler-limit, Deck Browser mounting, and
native capture plumbing.  This module replaces its release matrix and
assertions with the canonical 1.8.5 production and Settings contract.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

from aqt import gui_hooks, mw
from aqt.qt import (
    QApplication,
    QDialog,
    QFont,
    QPoint,
    QScrollArea,
    QSettings,
    QSize,
    Qt,
    QTimer,
)

from home_dashboard_overhaul.analytics import representative_preview_snapshot
from home_dashboard_overhaul.config_schema import normalize_config
from home_dashboard_overhaul.settings import SettingsDialog

from . import _probe_base as base


RELEASE = "1.8.5"
OUTPUT_ROOT = base.RUN_ROOT / "hdo-release-evidence-1.8.5"
CAPTURE_ROOT = OUTPUT_ROOT / "captures"
REPORT_PATH = OUTPUT_ROOT / "runtime-report-{}.json".format(base.STAGE)
SETTINGS_SIZE_KEY = "HomeScreenDashboard/settingsWindowSize"
CAPTURE_SCOPE = os.environ.get("HDO_RELEASE_CAPTURE_SCOPE", "full").strip().casefold()

ENABLED = (
    str(base.RUN_ROOT).startswith("/private/tmp/anki-release-qa.")
    and base.EXPECTED_PROFILE.startswith("Codex QA HDO 1.8.5 ")
    and len(base.EXPECTED_SHA256) == 64
    and len(base.EXPECTED_INSTANCE_KEY) >= 24
    and base.STAGE in {"initial", "restart"}
    and CAPTURE_SCOPE in {"full", "settings"}
)

base.RELEASE = RELEASE
base.QA_HEAD_A = "HDO 1.8.5 QA Head A"
base.QA_HEAD_B = "HDO 1.8.5 QA Head B"
base.QA_CONFIG_A = "HDO 1.8.5 QA Limit 3"
base.QA_CONFIG_B = "HDO 1.8.5 QA Limit 7"
base.OUTPUT_ROOT = OUTPUT_ROOT
base.CAPTURE_ROOT = CAPTURE_ROOT
base.REPORT_PATH = REPORT_PATH
base.ENABLED = ENABLED
base.REPORT = {
    "schema_version": 3,
    "release": RELEASE,
    "stage": base.STAGE,
    "status": "running",
    "authority": "native-exact-package-production-and-canonical-settings",
    "errors": [],
    "captures": {},
    "scale_policy": {
        "production_ui_percent": 100,
        "settings_application_font_percent": [100, 150],
        "dpr_1_acceptance": "unrun",
        "os_display_scaling_acceptance": "unrun",
    },
}


PALETTES = {
    "Sapphire Glass": ("SG", ("Sapphire", "Amethyst", "Glacier", "Sea Glass")),
    "Graphite": ("GR", ("Slate", "Steel", "Plum", "Mint")),
    "Emerald": ("EM", ("Emerald", "Jade", "Moss", "Lagoon")),
    "High Contrast": ("HC", ("Cyan", "Gold", "Magenta", "Monochrome")),
}

PRODUCTION_CORE_IDS = (
    "PROD-MONTH-STABLE",
    "PROD-YEAR-STABLE",
    "PROD-MARKERS-COMBINED",
    "PROD-MARKERS-COMPLETION",
    "PROD-MARKERS-DUE",
    "PROD-MARKERS-TODAY",
    "PROD-MARKERS-EVENT",
    "PROD-LEGEND-NO-DUE",
    "PROD-LEGEND-NO-EVENT",
    "PROD-BG-WHITE",
    "PROD-BG-BLACK",
    "PROD-BG-PURPLE",
    "PROD-BG-IMAGE",
    "PROD-SECTIONS-BELOW",
    "PROD-BOTTOM-CLEARANCE",
    "PROD-VERSE-EXACT",
)

SETTINGS_CONTRACT_IDS = (
    "SET-DOCK-SHOWN",
    "SET-DOCK-HIDDEN",
    "SET-PREVIEW-SECTION-FIT",
    "SET-PREVIEW-SECTION-100",
    "SET-PREVIEW-FULL-FIT",
    "SET-PREVIEW-FULL-100",
    "SET-OVERLAY-SUBMIN",
    "SET-EVENTS-EMPTY",
    "SET-EVENTS-POPULATED",
    "SET-EVENTS-SELECTED",
    "SET-EVENTS-SEARCHED",
    "SET-EVENTS-ARCHIVED",
    "SET-BIBLE-SHORT",
    "SET-BIBLE-LONG",
    "SET-BIBLE-CUSTOM",
    "SET-ABOUT-BOTTOM",
    "SET-DIRTY",
    "SET-REVERT",
    "SET-SAVE-SUCCESS",
    "SET-SAVE-ERROR",
    "SET-LEGACY-ROUTE",
    "SET-WINDOW-RESTORE",
    "SET-WINDOW-CLAMP",
)


def _production_case(
    case_id: str,
    *,
    theme: str = "Graphite",
    mode: str = "dark",
    view: str = "month",
    palette: str = "Plum",
    fixture: str = "populated",
    selected: str = base.REFERENCE_DATE,
    special: str = "",
    layout: str = "wide",
    container_width: int | None = None,
    tags: tuple[str, ...] = (),
) -> dict[str, Any]:
    case = base._case(
        case_id,
        theme,
        mode,
        view,
        fixture=fixture,
        selected=selected,
        special=special,
        layout=layout,
        container_width=container_width,
        tags=tags,
    )
    case["palette"] = palette
    return case


def _build_production_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for theme, (prefix, palettes) in PALETTES.items():
        for palette in palettes:
            palette_id = palette.upper().replace(" ", "-")
            for mode, mode_id in (("light", "L"), ("dark", "D")):
                cases.append(_production_case(
                    "PROD-PAL-{}-{}-{}".format(prefix, palette_id, mode_id),
                    theme=theme,
                    palette=palette,
                    mode=mode,
                    tags=("palette", "production_month_tree"),
                ))
    cases.extend((
        _production_case("PROD-MONTH-STABLE", tags=("stable_width_switching", "month_42_cells")),
        _production_case("PROD-YEAR-STABLE", view="year", tags=("stable_width_switching", "year_53_weeks")),
        _production_case("PROD-MARKERS-COMBINED", fixture="combined-today", special="markers-combined", tags=("completion", "selected", "today", "due", "event")),
        _production_case("PROD-MARKERS-COMPLETION", fixture="combined-today", special="markers-completion", tags=("completion",)),
        _production_case("PROD-MARKERS-DUE", fixture="next-event-future", selected="2026-08-29", special="markers-due", tags=("due",)),
        _production_case("PROD-MARKERS-TODAY", fixture="combined-today", special="markers-today", tags=("today",)),
        _production_case("PROD-MARKERS-EVENT", fixture="selected-event", selected="2026-08-27", special="markers-event", tags=("event",)),
        _production_case("PROD-LEGEND-NO-DUE", special="no-due", tags=("conditional_legend",)),
        _production_case("PROD-LEGEND-NO-EVENT", special="no-event", tags=("conditional_legend", "conditional_summary")),
        _production_case("PROD-BG-WHITE", mode="light", special="host-white", tags=("host_background",)),
        _production_case("PROD-BG-BLACK", special="host-black", tags=("host_background",)),
        _production_case("PROD-BG-PURPLE", special="host-purple", tags=("host_background",)),
        _production_case("PROD-BG-IMAGE", special="host-image", tags=("host_background",)),
        _production_case("PROD-SECTIONS-BELOW", layout="intermediate", container_width=720, special="sections-below", tags=("sections_below_calendar",)),
        _production_case("PROD-BOTTOM-CLEARANCE", layout="intermediate", container_width=720, special="scroll-bottom", tags=("measured_bottom_clearance",)),
        _production_case("PROD-VERSE-EXACT", mode="light", special="verse-exact", tags=("exact_verse_font_size_color",)),
    ))
    return cases


def _restart_case(_observed_view: str = "year") -> dict[str, Any]:
    return _production_case(
        "PROD-RESTART-PERSISTENCE",
        theme="Graphite",
        palette="Plum",
        mode="dark",
        view="year",
        special="restart",
        tags=("restart", "no_waiver", "production_persistence"),
    )


_base_config_for = base._config_for


def _config_for(case: Mapping[str, Any]) -> dict[str, Any]:
    config = _base_config_for(case)
    theme = str(case.get("theme", "Graphite"))
    palette = str(case.get("palette", PALETTES[theme][1][0]))
    config["heatmap"]["presets_by_theme"][theme] = palette
    special = str(case.get("special", ""))
    if special in {"no-due", "markers-completion", "markers-today", "markers-event"}:
        config["heatmap"]["show_due_forecast"] = False
    if special in {"no-event", "markers-completion", "markers-due", "markers-today"}:
        config["visibility"]["events"] = False
    if special == "verse-exact":
        config["bible"].update(
            font_family="Avenir Next, sans-serif",
            font_size="36px",
            font_color="#32145F",
            theme_aware_color=False,
        )
    return config


base._build_initial_cases = _build_production_cases
base._restart_case = _restart_case
base._config_for = _config_for


_base_prepare_dom = base._prepare_dom


def _prepare_dom(case: Mapping[str, Any], callback: Any) -> None:
    special = str(case.get("special", ""))

    def prepare_host() -> None:
        backgrounds = {
            "host-white": "linear-gradient(#ffffff,#ffffff)",
            "host-black": "linear-gradient(#050508,#050508)",
            "host-purple": "linear-gradient(135deg,#32145f,#6f3f91)",
            "host-image": "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='800' height='600'%3E%3Cdefs%3E%3ClinearGradient id='g'%3E%3Cstop stop-color='%231f5f78'/%3E%3Cstop offset='1' stop-color='%237c466d'/%3E%3C/linearGradient%3E%3C/defs%3E%3Crect width='800' height='600' fill='url(%23g)'/%3E%3Ccircle cx='620' cy='120' r='90' fill='%23e6b84b' fill-opacity='.55'/%3E%3C/svg%3E\")",
        }
        value = backgrounds.get(special)
        if value is None:
            callback()
            return
        script = (
            "document.body.style.backgroundImage=%s;"
            "var r=document.getElementById('hdo-dashboard');"
            "if(r){r.dataset.hdoQaBackgroundClass=%s;}"
        ) % (json.dumps(value), json.dumps(special))
        mw.deckBrowser.web.eval(script)
        QTimer.singleShot(220, callback)

    _base_prepare_dom(case, prepare_host)


base._prepare_dom = _prepare_dom


base.DOM_REPORT_SCRIPT = r"""
(function () {
  var root=document.getElementById('hdo-dashboard');
  if(!root)return {ready:false};
  function q(s){return root.querySelector(s);}
  function qa(s){return Array.from(root.querySelectorAll(s));}
  function rect(n){if(!n)return null;var r=n.getBoundingClientRect();return {left:r.left,top:r.top,right:r.right,bottom:r.bottom,width:r.width,height:r.height};}
  function visible(n){return !!n&&!n.hidden&&getComputedStyle(n).display!=='none';}
  var calendar=q('.hdo-calendar-card');
  var grid=q('.hdo-calendar-grid');
  var rail=q('.hdo-insight-rail');
  var verse=q('.hdo-verse');
  var scroller=document.scrollingElement;
  var rootStyle=getComputedStyle(root);
  var title=q('#hdo-calendar-heading');
  var controls=qa('.hdo-header-controls button');
  var cells=qa('.hdo-calendar-day');
  var selected=q('.hdo-calendar-day.is-selected');
  var selectedStyle=selected?getComputedStyle(selected):null;
  return {
    ready:true,
    loading:root.classList.contains('hdo-dashboard--loading'),
    theme:root.dataset.hdoTheme||'',
    mode:root.dataset.hdoColorMode||'',
    view:root.dataset.hdoCalendarView||'',
    root:rect(root),
    calendar:rect(calendar),
    rail:rect(rail),
    density:root.dataset.hdoContentMode||'',
    rootPosition:rootStyle.position,
    rootMarginTop:rootStyle.marginTop,
    rootPaddingBottom:rootStyle.paddingBottom,
    rootBackground:rootStyle.backgroundColor,
    rootScrollOwner:root.dataset.hdoScrollOwner||'',
    footerClearance:Number(root.dataset.hdoFooterClearance||0),
    footerClearanceSource:root.dataset.hdoFooterClearanceSource||'',
    nativeFooterHeight:parseFloat(rootStyle.getPropertyValue('--hdo-native-footer-height'))||0,
    documentScrollPaddingBlockEnd:scroller?getComputedStyle(scroller).scrollPaddingBlockEnd:'',
    documentOverflowX:document.documentElement.scrollWidth-document.documentElement.clientWidth,
    bodyOverflowX:document.body.scrollWidth-document.body.clientWidth,
    documentScrollMaximum:scroller?Math.max(0,scroller.scrollHeight-scroller.clientHeight):0,
    documentBottomReached:scroller?Math.abs(scroller.scrollTop-Math.max(0,scroller.scrollHeight-scroller.clientHeight))<=2:false,
    hostPreserved:root.dataset.hdoHostPreserved||'',
    hostBackgroundClass:root.dataset.hdoQaBackgroundClass||'',
    bodyBackgroundImage:getComputedStyle(document.body).backgroundImage,
    calendarCellCount:cells.length,
    monthRows:grid?grid.style.getPropertyValue('--hdo-month-rows'):'',
    yearWeeks:grid?grid.style.getPropertyValue('--hdo-year-weeks'):'',
    titleFontSize:title?getComputedStyle(title).fontSize:'',
    controlHeights:controls.map(function(n){return Math.round(n.getBoundingClientRect().height);}),
    dueLegendCount:qa('.hdo-legend-due').length,
    eventLegendCount:qa('.hdo-legend-event').length,
    eventSummaryCount:qa('[data-hdo-context-event]').length,
    todayCount:qa('.hdo-calendar-day.is-today').length,
    selectedCount:qa('.hdo-calendar-day.is-selected').length,
    dueMarkerCount:qa('.hdo-calendar-day[data-due-level]:not([data-due-level="0"])').length,
    eventMarkerCount:qa('.hdo-calendar-day .hdo-event-marker').length,
    completionCount:qa('.hdo-calendar-day[data-level]:not([data-level="0"])').length,
    selectedOutline:selectedStyle?selectedStyle.outlineWidth:'',
    cellShadowCount:cells.filter(function(n){return getComputedStyle(n).boxShadow!=='none';}).length,
    verseFontSize:verse?getComputedStyle(verse).fontSize:'',
    verseFontFamily:verse?getComputedStyle(verse).fontFamily:'',
    verseColor:verse?getComputedStyle(verse).color:'',
    sectionsBelow:!!calendar&&!!rail&&rect(rail).top>=rect(calendar).bottom-1
  };
})()
"""


def _pixels(value: object) -> float:
    try:
        return float(str(value).replace("px", "").strip())
    except (TypeError, ValueError):
        return 0.0


def _validate_dom(case: Mapping[str, Any], state: Mapping[str, Any]) -> None:
    base._require(bool(state.get("ready")), "production dashboard did not mount")
    base._require(not bool(state.get("loading")), "production dashboard remained in loading state")
    base._require(state.get("theme") == case.get("theme"), "dashboard theme mismatch")
    base._require(state.get("mode") == case.get("mode"), "dashboard mode mismatch")
    base._require(state.get("view") == case.get("view"), "dashboard view mismatch")
    root = state.get("root") or {}
    root_width = float(root.get("width", 0))
    base._require(0 < root_width <= 1120.5, "dashboard exceeds its 1120px maximum")
    base._require(state.get("rootPosition") not in {"fixed", "sticky"}, "dashboard root left document flow")
    base._require(abs(_pixels(state.get("rootMarginTop")) - 24) <= 0.5, "dashboard top margin is not 24px")
    base._require(float(state.get("documentOverflowX", 0)) <= 1, "document has horizontal overflow")
    base._require(float(state.get("bodyOverflowX", 0)) <= 1, "body has horizontal overflow")
    base._require(state.get("hostPreserved") == "true", "host canvas was not preserved")
    base._require(state.get("rootBackground") in {"rgba(0, 0, 0, 0)", "transparent"}, "dashboard root is not transparent")
    base._require(state.get("rootScrollOwner") in {"documentElement", "body"}, "document scroller does not own vertical movement")
    clearance = float(state.get("footerClearance", 0))
    footer_height = float(state.get("nativeFooterHeight", 0))
    base._require(footer_height > 0 and abs(clearance - footer_height - 24) <= 1, "bottom clearance is not measured height plus 24px")
    base._require(abs(_pixels(state.get("rootPaddingBottom")) - clearance) <= 1, "root bottom padding drifted from measured clearance")
    base._require(abs(_pixels(state.get("documentScrollPaddingBlockEnd")) - clearance) <= 1, "document scroll padding drifted from measured clearance")
    base._require(_pixels(state.get("titleFontSize")) == 24, "calendar title is not 24px")
    base._require(len(state.get("controlHeights", [])) >= 5, "calendar header controls are incomplete")
    base._require(all(33 <= int(value) <= 35 for value in state.get("controlHeights", [])), "calendar controls are not 34px")
    base._require(int(state.get("cellShadowCount", 1)) == 0, "calendar cells retain shadows")
    if case.get("view") == "month":
        base._require(int(state.get("calendarCellCount", 0)) == 42, "Month is not 42 cells")
        base._require(str(state.get("monthRows")) == "6", "Month is not six rows")
    else:
        base._require(str(state.get("yearWeeks")) == "53", "Year is not a 53-week grid")
        base._require(int(state.get("calendarCellCount", 0)) in {365, 366}, "Year does not contain the full year")
    special = str(case.get("special", ""))
    if special == "no-due":
        base._require(int(state.get("dueLegendCount", 1)) == 0, "disabled due legend remains")
    if special == "no-event":
        base._require(int(state.get("eventLegendCount", 1)) == 0, "disabled event legend remains")
        base._require(int(state.get("eventSummaryCount", 1)) == 0, "disabled event summary remains")
    if special == "markers-combined":
        base._require(int(state.get("todayCount", 0)) == 1, "today marker is missing")
        base._require(int(state.get("selectedCount", 0)) == 1, "selected marker is missing")
        base._require(int(state.get("completionCount", 0)) > 0, "completion fill is missing")
        base._require(int(state.get("dueMarkerCount", 0)) > 0, "due marker is missing")
        base._require(int(state.get("eventMarkerCount", 0)) > 0, "event marker is missing")
    if special in {"host-white", "host-black", "host-purple", "host-image"}:
        base._require(state.get("hostBackgroundClass") == special, "host background fixture identity is missing")
        base._require(state.get("bodyBackgroundImage") != "none", "host background was removed")
    if special == "sections-below":
        base._require(bool(state.get("sectionsBelow")), "sections below the calendar are not visible")
    if special == "scroll-bottom":
        source = state.get("footerClearanceSource")
        base._require(source in {"measured", "fallback"}, "bottom-action clearance source is unknown")
        if source == "fallback":
            base._require(abs(footer_height - 60) <= 1, "bottom-action fallback is not the specified 60px")
        base._require(float(state.get("documentScrollMaximum", 0)) > 0, "bottom-clearance case has no document scroll range")
        base._require(bool(state.get("documentBottomReached")), "bottom-clearance case did not reach the document bottom")
    if special == "verse-exact":
        base._require(abs(_pixels(state.get("verseFontSize")) - 36) <= 0.1, "configured verse size is not exact")
        base._require("Avenir Next" in str(state.get("verseFontFamily")), "configured verse font is not exact")


base._validate_dom = _validate_dom


_base_font: QFont | None = None
_settings_cases: list[dict[str, Any]] = []
_settings_index = 0
_settings_dialog: SettingsDialog | None = None
_settings_started = False
_saved_controller_config: dict[str, Any] | None = None


def _settings_page_cases() -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    pages = (
        ("DASHBOARD", "dashboard"),
        ("EVENTS", "events"),
        ("BIBLE", "bible_verse"),
        ("ABOUT", "about_support"),
    )
    for page_id, page in pages:
        for width_id, width in (("1040", 1040), ("1200", 1200), ("FULL", "full")):
            for font_percent in (100, 150):
                result.append({
                    "id": "SET-PAGE-{}-{}-{}".format(page_id, width_id, font_percent),
                    "page": page,
                    "width": width,
                    "font_percent": font_percent,
                    "special": "page-axis",
                })
    return result


def _settings_contract_cases() -> list[dict[str, Any]]:
    page_by_id = {
        "SET-DOCK-SHOWN": "dashboard",
        "SET-DOCK-HIDDEN": "dashboard",
        "SET-PREVIEW-SECTION-FIT": "dashboard",
        "SET-PREVIEW-SECTION-100": "dashboard",
        "SET-PREVIEW-FULL-FIT": "dashboard",
        "SET-PREVIEW-FULL-100": "dashboard",
        "SET-OVERLAY-SUBMIN": "dashboard",
        "SET-EVENTS-EMPTY": "events",
        "SET-EVENTS-POPULATED": "events",
        "SET-EVENTS-SELECTED": "events",
        "SET-EVENTS-SEARCHED": "events",
        "SET-EVENTS-ARCHIVED": "events",
        "SET-BIBLE-SHORT": "bible_verse",
        "SET-BIBLE-LONG": "bible_verse",
        "SET-BIBLE-CUSTOM": "bible_verse",
        "SET-ABOUT-BOTTOM": "about_support",
        "SET-DIRTY": "dashboard",
        "SET-REVERT": "dashboard",
        "SET-SAVE-SUCCESS": "dashboard",
        "SET-SAVE-ERROR": "dashboard",
        "SET-LEGACY-ROUTE": "calendar",
        "SET-WINDOW-RESTORE": "dashboard",
        "SET-WINDOW-CLAMP": "dashboard",
    }
    return [
        {
            "id": case_id,
            "page": page_by_id[case_id],
            "width": 1200,
            "font_percent": 100,
            "special": case_id.removeprefix("SET-").casefold(),
        }
        for case_id in SETTINGS_CONTRACT_IDS
    ]


def _events_fixture() -> list[dict[str, Any]]:
    return [
        {"id": "evt-a", "name": "Pediatrics board review", "date": "2026-08-27", "archived": False, "created_at": "2026-08-24T09:00:00-05:00", "archived_at": ""},
        {"id": "evt-b", "name": "Anatomy study group", "date": "2026-08-28", "archived": False, "created_at": "2026-08-24T09:01:00-05:00", "archived_at": ""},
        {"id": "evt-z", "name": "Completed milestone", "date": "2026-08-20", "archived": True, "created_at": "2026-08-20T09:00:00-05:00", "archived_at": "2026-08-24T09:02:00-05:00"},
    ]


def _settings_config(case: Mapping[str, Any]) -> dict[str, Any]:
    config = normalize_config({})
    config["appearance"].update(preset="Graphite", mode="dark")
    config["heatmap"]["calendar_view"] = "year" if base.STAGE == "restart" else "month"
    config["events"]["sort"] = "name"
    special = str(case.get("special", ""))
    if "events-empty" in special:
        config["events"]["items"] = []
    else:
        config["events"]["items"] = _events_fixture()
    if "bible-short" in special:
        config["bible"]["quotes"] = ["Be still, and know that I am God.<br> - Psalm 46:10 (NLT)"]
    elif "bible-long" in special:
        config["bible"]["quotes"] = [
            "Trust in the Lord with all your heart and do not depend on your own understanding. Seek his will in all you do, and he will show you which path to take through every season of learning, service, patience, and faithful practice.<br> - Proverbs 3:5-6 (NLT)"
        ]
    elif "bible-custom" in special:
        config["bible"].update(
            font_family="Avenir Next, sans-serif",
            font_size="36px",
            font_color="#32145F",
            theme_aware_color=False,
            quotes=["The Lord is my strength and my song.<br> - Psalm 118:14 (NLT)"],
        )
    return config


def _set_application_font(percent: int) -> None:
    global _base_font
    application = QApplication.instance()
    base._require(application is not None, "QApplication is unavailable")
    if _base_font is None:
        _base_font = QFont(application.font())
    font = QFont(_base_font)
    if font.pointSizeF() > 0:
        font.setPointSizeF(font.pointSizeF() * percent / 100.0)
    elif font.pixelSize() > 0:
        font.setPixelSize(max(1, round(font.pixelSize() * percent / 100.0)))
    application.setFont(font)


def _isolate_qsettings() -> None:
    settings_root = base.RUN_ROOT / "qt-settings"
    settings_root.mkdir(parents=True, exist_ok=True)
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(settings_root))


def _prepare_settings_case(case: Mapping[str, Any]) -> SettingsDialog:
    _set_application_font(int(case.get("font_percent", 100)))
    settings = QSettings()
    special = str(case.get("special", ""))
    if special != "restart-persistence":
        settings.remove(SETTINGS_SIZE_KEY)
    if special == "window-restore":
        settings.setValue(SETTINGS_SIZE_KEY, QSize(1180, 760))
    elif special == "window-clamp":
        settings.setValue(SETTINGS_SIZE_KEY, QSize(99999, 99999))
    settings.sync()

    config = _settings_config(case)
    base._controller.config = config
    base._controller.snapshot = representative_preview_snapshot(base.REFERENCE_DATE)
    dialog = SettingsDialog(base._controller, initial_page=str(case.get("page", "dashboard")))
    target_width = case.get("width", 1200)
    available = base._qa_screen().availableGeometry()
    width = available.width() if target_width == "full" else int(target_width)
    height = available.height() if target_width == "full" else min(800, available.height())
    # Keep the native Settings window above its parent while the compositor is
    # sampled. This affects only the disposable evidence helper, not product
    # window behavior.
    dialog.setModal(True)
    dialog.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
    dialog.showNormal()
    if special not in {"window-restore", "window-clamp", "restart-persistence"}:
        dialog.resize(min(width, available.width()), min(height, available.height()))
        dialog.move(available.center() - dialog.rect().center())

    if special == "dock-hidden":
        dialog._toggle_preview_visibility(False)
    elif special in {"preview-section-fit", "preview-section-100", "preview-full-fit", "preview-full-100"}:
        dialog.preview_scope.setValue("full" if "preview-full" in special else "context")
        dialog._set_preview_scope_mode()
        dialog._set_preview_fit_mode("actual" if special.endswith("-100") else "fit")
    elif special == "overlay-submin":
        before = id(dialog.preview_wrap)
        dialog._preview_overlay_mode = True
        dialog.body_grid.removeWidget(dialog.preview_wrap)
        dialog.body_grid.addWidget(
            dialog.preview_wrap,
            0,
            1,
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight,
        )
        dialog.setMinimumSize(1, 1)
        dialog.resize(min(900, available.width()), min(680, available.height()))
        dialog.preview_wrap.raise_()
        dialog.setProperty("hdoOverlayPreviewIdentityStable", before == id(dialog.preview_wrap))
    elif special == "events-selected":
        dialog._select_event_id("evt-a", False)
    elif special == "events-searched":
        dialog.event_search.setText("Pediatrics")
        dialog._refresh_event_lists()
    elif special == "events-archived":
        dialog.event_tabs.setCurrentIndex(1)
        dialog._update_event_actions()
    elif special == "about-bottom":
        scroll = dialog.stack.currentWidget()
        if isinstance(scroll, QScrollArea):
            scroll.verticalScrollBar().setValue(scroll.verticalScrollBar().maximum())
    elif special in {"dirty", "revert", "save-success", "save-error"}:
        dialog.retention_target.setValue(81)
        dialog._sync_draft()
        if special == "revert":
            dialog._revert_changes()
        elif special in {"save-success", "save-error"}:
            dialog._latest_stored_config = lambda: deepcopy(dialog.draft.baseline)
            if special == "save-error":
                original = base._controller.save_config

                def fail_save(*_args: object, **_kwargs: object) -> None:
                    raise OSError("simulated transactional write failure")

                base._controller.save_config = fail_save
                try:
                    dialog._save()
                finally:
                    base._controller.save_config = original
            else:
                dialog._save()
    elif special == "legacy-route":
        dialog.open_page("calendar")
    dialog.raise_()
    dialog.activateWindow()
    QApplication.processEvents()
    return dialog


def _settings_state(dialog: SettingsDialog, case: Mapping[str, Any]) -> dict[str, Any]:
    current = dialog.stack.currentWidget()
    active_tree = getattr(dialog, "active_events", None)
    archived_tree = getattr(dialog, "archived_events", None)
    quote_list = getattr(dialog, "quote_list", None)
    deck_tree = getattr(dialog, "deck_tree", None)
    scrollbar_off = Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    available_geometry = base._qa_screen().availableGeometry()
    frame = dialog.frameGeometry()
    calendar_viewport_y = -1
    calendar_anchor = getattr(dialog, "dashboard_anchors", {}).get("calendar")
    if isinstance(current, QScrollArea) and calendar_anchor is not None:
        calendar_viewport_y = calendar_anchor.mapTo(current.viewport(), QPoint(0, 0)).y()
    return {
        "section": dialog.current_section,
        "normalized_route": getattr(dialog, "_normalized_route", ""),
        "window_size": [dialog.width(), dialog.height()],
        "minimum_size": [dialog.minimumWidth(), dialog.minimumHeight()],
        "available_size": [base._qa_screen().availableGeometry().width(), base._qa_screen().availableGeometry().height()],
        "decorated_frame_inside_available": (
            frame.left() >= available_geometry.left()
            and frame.top() >= available_geometry.top()
            and frame.right() <= available_geometry.right()
            and frame.bottom() <= available_geometry.bottom()
        ),
        "font_percent": int(case.get("font_percent", 100)),
        "application_font_point_size": QApplication.font().pointSizeF(),
        "nav_width": dialog.nav.width(),
        "page_count": dialog.stack.count(),
        "main_page_scroller": isinstance(current, QScrollArea),
        "preview_visible": dialog.preview_wrap.isVisible(),
        "preview_overlay": bool(dialog._preview_overlay_mode),
        "preview_identity_stable": dialog.property("hdoOverlayPreviewIdentityStable") is not False,
        "preview_scope": dialog.preview_scope.value("context"),
        "preview_scale": dialog.preview_scale.value("fit"),
        "preview_canvas_height": dialog.preview.height(),
        "preview_dock_height": dialog.preview_wrap.height(),
        "preview_rendered_height": dialog._preview_content_size.height(),
        "body_height": dialog.body_shell.height(),
        "calendar_anchor_viewport_y": calendar_viewport_y,
        "footer_after_body": dialog.footer_shell.geometry().top() >= dialog.body_shell.geometry().bottom() - 1,
        "save_text": dialog.save_button.text() if dialog.save_button is not None else "",
        "close_text": dialog.close_button.text() if dialog.close_button is not None else "",
        "revert_visible": dialog.revert_button.isVisible(),
        "save_error_visible": dialog.save_error.isVisible(),
        "save_error_text": dialog.save_error.text(),
        "status": dialog.dirty_badge.text(),
        "event_active_count": active_tree.topLevelItemCount() if active_tree is not None else 0,
        "event_archived_count": archived_tree.topLevelItemCount() if archived_tree is not None else 0,
        "event_tab": dialog.event_tabs.currentIndex() if hasattr(dialog, "event_tabs") else -1,
        "event_search": dialog.event_search.text() if hasattr(dialog, "event_search") else "",
        "quote_count": quote_list.count() if quote_list is not None else 0,
        "list_vertical_scrollbars_disabled": all(
            view is None or view.verticalScrollBarPolicy() == scrollbar_off
            for view in (active_tree, archived_tree, quote_list, deck_tree)
        ),
        "settings_shell_maximum": dialog.settings_shell.maximumWidth(),
        "settings_shell_width": dialog.settings_shell.width(),
        "settings_shell_center_delta": abs(
            dialog.settings_shell.geometry().center().x() - dialog.rect().center().x()
        ),
    }


def _validate_settings_state(case: Mapping[str, Any], state: Mapping[str, Any]) -> None:
    base._require(state.get("nav_width") == 152, "Settings rail is not 152px")
    base._require(state.get("page_count") == 4, "Settings does not own exactly four pages")
    base._require(bool(state.get("main_page_scroller")), "active Settings page is not the main scroller")
    base._require(bool(state.get("footer_after_body")), "Settings footer is not the final layout row")
    base._require(state.get("save_text") == "Save changes", "Save button label is unstable")
    base._require(state.get("close_text") == "Close", "Close button label is unstable")
    base._require(state.get("settings_shell_maximum") == 1240, "Settings inner shell is not capped at 1240px")
    expected_shell_width = min(int(state.get("window_size", [0])[0]), 1240)
    base._require(
        abs(int(state.get("settings_shell_width", 0)) - expected_shell_width) <= 2,
        "Settings shell does not occupy the available dialog width",
    )
    base._require(
        int(state.get("settings_shell_center_delta", 9999)) <= 2,
        "Settings shell is not centered in the dialog",
    )
    base._require(
        bool(state.get("decorated_frame_inside_available")),
        "decorated Settings window escaped available screen geometry",
    )
    base._require(bool(state.get("list_vertical_scrollbars_disabled")), "managed Settings list has an internal vertical scrollbar")
    special = str(case.get("special", ""))
    if state.get("section") == "about_support":
        base._require(not bool(state.get("preview_visible")), "About incorrectly shows Preview")
    elif special != "dock-hidden":
        base._require(bool(state.get("preview_visible")), "Preview is not open by default")
    if special == "dock-hidden":
        base._require(not bool(state.get("preview_visible")), "Preview did not hide session-locally")
    if bool(state.get("preview_visible")) and state.get("preview_scale") == "fit":
        maximum_canvas = 320 if state.get("preview_scope") == "context" else 420
        base._require(
            int(state.get("preview_canvas_height", 9999)) <= maximum_canvas,
            "Fit Preview retained a dead full-height canvas",
        )
    if special == "overlay-submin":
        base._require(bool(state.get("preview_overlay")), "sub-minimum Preview is not an overlay")
        base._require(bool(state.get("preview_identity_stable")), "overlay created a second Preview instance")
        base._require(state.get("window_size", [9999])[0] <= 900, "sub-minimum Settings width did not settle")
    if special == "events-empty":
        base._require(state.get("event_active_count") == 0 and state.get("event_archived_count") == 0, "empty Events state is populated")
    if special == "events-populated":
        base._require(state.get("event_active_count") == 2, "populated Events state is incomplete")
    if special == "events-searched":
        base._require(state.get("event_search") == "Pediatrics" and state.get("event_active_count") == 1, "Events search state is incorrect")
    if special == "events-archived":
        base._require(state.get("event_tab") == 1 and state.get("event_archived_count") == 1, "Archived Events state is incorrect")
    if special in {"bible-short", "bible-long", "bible-custom"}:
        base._require(state.get("quote_count") == 1, "Bible fixture did not render one compact row")
    if special == "dirty":
        base._require(bool(state.get("revert_visible")), "dirty Settings does not expose Revert")
    if special == "revert":
        base._require(not bool(state.get("revert_visible")), "Revert did not restore the saved baseline")
    if special == "save-success":
        base._require("Saved" in str(state.get("status")), "successful save did not update the baseline/status")
        base._require(not bool(state.get("revert_visible")), "successful save remains dirty")
    if special == "save-error":
        base._require(bool(state.get("save_error_visible")), "save failure is not inline")
        base._require("simulated transactional write failure" in str(state.get("save_error_text")), "save failure is not specific")
    if special == "legacy-route":
        base._require(state.get("section") == "dashboard", "legacy Calendar route did not activate Dashboard")
        base._require(state.get("normalized_route") == "dashboard#calendar", "legacy Calendar route did not settle on Calendar display")
        base._require(
            0 <= int(state.get("calendar_anchor_viewport_y", -1)) <= 4,
            "legacy Calendar route exposes a clipped preceding card",
        )
    if special == "window-restore":
        base._require(abs(state.get("window_size", [0])[0] - 1180) <= 2, "Settings window size did not restore")
    if special == "window-clamp":
        size = state.get("window_size", [0, 0])
        available = state.get("available_size", [0, 0])
        base._require(size[0] <= available[0] and size[1] <= available[1], "Settings window size escaped screen geometry")


def _capture_settings(dialog: SettingsDialog, case: Mapping[str, Any], state: Mapping[str, Any]) -> None:
    QApplication.processEvents()
    screen = base._qa_screen()
    origin = dialog.mapToGlobal(QPoint(0, 0))
    screen_geometry = screen.geometry()
    pixmap = screen.grabWindow(
        0,
        origin.x() - screen_geometry.x(),
        origin.y() - screen_geometry.y(),
        dialog.width(),
        dialog.height(),
    )
    base._require(not pixmap.isNull(), "native Settings screen capture is null")
    color_count = base._sample_color_count(pixmap)
    base._require(color_count >= 3, "native Settings screen capture appears blank")
    dpr = max(1.0, float(pixmap.devicePixelRatio()))
    base._require(
        abs(pixmap.width() - round(dialog.width() * dpr)) <= 4,
        "native Settings capture width does not match the dialog",
    )
    base._require(
        abs(pixmap.height() - round(dialog.height() * dpr)) <= 4,
        "native Settings capture height does not match the dialog",
    )
    method = "QScreen.grabWindow-screen-client-crop"
    CAPTURE_ROOT.mkdir(parents=True, exist_ok=True)
    path = CAPTURE_ROOT / "{}.png".format(case["id"])
    base._require(bool(pixmap.save(str(path), "PNG")), "could not save native Settings capture")
    base.REPORT["captures"][str(case["id"])] = {
        "file": str(path.relative_to(OUTPUT_ROOT)),
        "sha256": base._sha256(path),
        "component": "canonical-settings",
        "page": state.get("section"),
        "font_percent": case.get("font_percent", 100),
        "capture_method": method,
        "sampled_color_count": color_count,
        "logical_frame": {"width": dialog.width(), "height": dialog.height()},
        "physical_pixels": [pixmap.width(), pixmap.height()],
        "device_pixel_ratio": pixmap.devicePixelRatio(),
        "parent_window_title": str(mw.windowTitle()),
        "parent_window_title_matches_profile": base.EXPECTED_PROFILE in str(mw.windowTitle()),
        "state": dict(state),
    }
    base._write_report()


def _close_settings_dialog() -> None:
    global _settings_dialog
    if _settings_dialog is None:
        return
    _settings_dialog._allow_close = True
    _settings_dialog.close()
    _settings_dialog.deleteLater()
    _settings_dialog = None


def _next_settings_case() -> None:
    global _settings_index, _settings_dialog
    try:
        _close_settings_dialog()
        if _settings_index >= len(_settings_cases):
            _complete_stage()
            return
        case = _settings_cases[_settings_index]
        _settings_index += 1
        _settings_dialog = _prepare_settings_case(case)
        QTimer.singleShot(720, lambda: _inspect_settings_case(case))
    except Exception as exc:
        base._error("settings-case-prepare", exc)


def _inspect_settings_case(case: Mapping[str, Any], attempt: int = 0) -> None:
    try:
        base._require(_settings_dialog is not None, "Settings dialog disappeared before capture")
        QApplication.processEvents()
        state = _settings_state(_settings_dialog, case)
        _validate_settings_state(case, state)
        _capture_settings(_settings_dialog, case, state)
        QTimer.singleShot(120, _next_settings_case)
    except Exception as exc:
        if attempt < 5:
            QTimer.singleShot(250, lambda: _inspect_settings_case(case, attempt + 1))
            return
        base.REPORT["last_failed_settings_case"] = {
            "case": dict(case),
            "error": "{}: {}".format(type(exc).__name__, exc),
        }
        base._write_report()
        base._error(str(case.get("id", "settings-inspect")), exc)


def _start_settings() -> None:
    global _settings_cases, _settings_index, _settings_started, _saved_controller_config
    try:
        _settings_started = True
        _settings_index = 0
        _saved_controller_config = deepcopy(base._controller.config)
        _isolate_qsettings()
        if base.STAGE == "initial":
            _settings_cases = _settings_page_cases() + _settings_contract_cases()
            base._require(len(_settings_cases) == 47, "Settings matrix must contain 47 initial frames")
        else:
            _settings_cases = [{
                "id": "SET-RESTART-PERSISTENCE",
                "page": "dashboard",
                "width": 1160,
                "font_percent": 100,
                "special": "restart-persistence",
            }]
        base.REPORT["settings_matrix"] = {
            "case_count": len(_settings_cases),
            "case_ids": [case["id"] for case in _settings_cases],
            "widget_tree": "one-native-qt-tree",
            "preview_instance_policy": "one-shared-instance",
        }
        base._write_report()
        QTimer.singleShot(120, _next_settings_case)
    except Exception as exc:
        base._error("settings-matrix", exc)


def _persist_restart_state() -> None:
    config = normalize_config({})
    config["appearance"].update(preset="Graphite", mode="dark")
    config["heatmap"]["calendar_view"] = "year"
    config["heatmap"]["presets_by_theme"]["Graphite"] = "Plum"
    config["events"]["sort"] = "name"
    mw.addonManager.writeConfig(base._controller.package, config)
    readback = normalize_config(mw.addonManager.getConfig(base._controller.package))
    base._require(readback == config, "restart configuration did not persist exactly")
    QSettings().setValue(SETTINGS_SIZE_KEY, QSize(1160, 760))
    QSettings().sync()
    base.REPORT["persistence_write"] = {
        "status": "passed",
        "calendar_view": "year",
        "theme": "Graphite",
        "palette": "Plum",
        "events_sort": "name",
        "settings_window_size": [1160, 760],
        "preview_visibility_persisted": False,
    }


def _complete_stage() -> None:
    try:
        _close_settings_dialog()
        if _base_font is not None:
            QApplication.instance().setFont(_base_font)
        smoke = base.REPORT.get("multi_deck_new_limit_smoke", {})
        base._require(smoke.get("status") == "passed", "scheduler-authoritative multi-deck smoke did not pass")
        capture_ids = set(base.REPORT.get("captures", {}))
        if base.STAGE == "initial" and CAPTURE_SCOPE == "full":
            expected = {case["id"] for case in _build_production_cases()}
            expected.update(case["id"] for case in _settings_page_cases())
            expected.update(SETTINGS_CONTRACT_IDS)
            base._require(len(expected) == 95, "initial contract does not derive 95 distinct frames")
            base._require(capture_ids == expected, "initial native evidence matrix is incomplete")
            _persist_restart_state()
        elif base.STAGE == "restart" and CAPTURE_SCOPE == "full":
            base._require(capture_ids == {"PROD-RESTART-PERSISTENCE", "SET-RESTART-PERSISTENCE"}, "restart evidence matrix is incomplete")
        elif base.STAGE == "initial":
            expected = {case["id"] for case in _settings_page_cases()}
            expected.update(SETTINGS_CONTRACT_IDS)
            base._require(len(expected) == 47, "Settings-only contract does not derive 47 distinct frames")
            base._require(capture_ids == expected, "Settings-only initial evidence matrix is incomplete")
            _persist_restart_state()
        else:
            base._require(capture_ids == {"SET-RESTART-PERSISTENCE"}, "Settings-only restart evidence is incomplete")

        if base.STAGE == "restart":
            config = normalize_config(mw.addonManager.getConfig(base._controller.package))
            base._require(config["heatmap"]["calendar_view"] == "year", "Year did not persist after restart")
            base._require(config["events"]["sort"] == "name", "name event sort did not persist after restart")
            remembered = QSettings().value(SETTINGS_SIZE_KEY)
            base._require(isinstance(remembered, QSize) and remembered == QSize(1160, 760), "Settings window size did not persist after restart")
            base.REPORT["persistence_readback"] = {
                "status": "passed",
                "calendar_view": "year",
                "events_sort": "name",
                "settings_window_size": [remembered.width(), remembered.height()],
                "settings_state": "clean",
            }
        base.REPORT["status"] = "passed"
        base._write_report()
        QTimer.singleShot(450, QApplication.instance().quit)
    except Exception as exc:
        base._error("finish-{}".format(base.STAGE), exc)


def _finish_production_stage() -> None:
    if not _settings_started:
        _start_settings()
    else:
        _complete_stage()


def _start_case_matrix() -> None:
    try:
        if CAPTURE_SCOPE == "settings":
            base.REPORT["capture_scope"] = "settings-only"
            base.REPORT["production_matrix"] = {
                "case_count": 0,
                "capture_policy": "reuse previously accepted dashboard captures",
                "runtime_smoke": "exact-package scheduler and production DOM smoke still required",
            }
            base._write_report()
            QTimer.singleShot(200, _start_settings)
            return
        if base.STAGE == "restart":
            raw = normalize_config(mw.addonManager.getConfig(base._controller.package))
            base._require(raw.get("schema_version") == 8, "configuration schema changed after restart")
            base._require(raw["heatmap"]["calendar_view"] == "year", "Year view did not persist after restart")
            base._require(raw["events"]["sort"] == "name", "event name sort did not persist after restart")
            base._cases = [_restart_case("year")]
        else:
            base._cases = _build_production_cases()
            base._require(len(base._cases) == 48, "production matrix must contain 48 initial frames")
        base._case_index = 0
        base.REPORT["production_matrix"] = {
            "case_count": len(base._cases),
            "case_ids": [case["id"] for case in base._cases],
            "host": "actual isolated Anki main Deck Browser",
            "renderer": "exact installed production controller and renderer",
        }
        base._write_report()
        QTimer.singleShot(200, base._next_case)
    except Exception as exc:
        base._error("production-matrix-{}".format(base.STAGE), exc)


base._finish_stage = _finish_production_stage
base._start_case_matrix = _start_case_matrix


if ENABLED:
    gui_hooks.profile_did_open.append(base._profile_opened)
    QTimer.singleShot(1100, base._begin)
