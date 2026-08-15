"""Professional staged settings editor integrated into the Caleb M. menu."""

from __future__ import annotations

from copy import deepcopy
import html as html_module
import json
from pathlib import Path
import re
from typing import Any, Callable, Dict, List, Mapping, Optional

from aqt import mw
from aqt.qt import (
    QAction,
    QApplication,
    QCheckBox,
    QComboBox,
    QColorDialog,
    QDate,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFontComboBox,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QEvent,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QTimer,
    QVBoxLayout,
    QWidget,
    Qt,
)
from aqt.webview import AnkiWebView

from .config_schema import normalize_config
from .renderer import render_dashboard, sample_snapshot
from .themes import PRESETS
from .verse import verse_content


CALEB_MENU_TITLE = "Caleb M. Add-ons Settings"
CALEB_MENU_OBJECT_NAME = "caleb_m_addons_menu"
ACTION_TEXT = "Home Dashboard - Overhaul settings"
EVENT_MANAGER_ACTION_TEXT = "Manage events & calendars"


def _palette_tokens() -> Dict[str, str]:
    """Resolve native dialog colors from Anki's current application palette."""
    application = QApplication.instance()
    palette = application.palette() if application is not None else mw.palette()

    # QPalette's native brush accessors avoid enum-identity mismatches between
    # Anki's Qt compatibility layer and the live application palette.
    def brush_color(method_name: str, fallback: str = "text") -> str:
        method = getattr(palette, method_name, None)
        if not callable(method):
            method = getattr(palette, fallback)
        return method().color().name()

    window_name = brush_color("window")
    window = getattr(palette, "window")().color()
    dark = window.lightness() < 128
    return {
        "window": window_name,
        "base": brush_color("base"),
        "alternate": brush_color("alternateBase", "base"),
        "text": brush_color("text"),
        "muted": brush_color("placeholderText", "text"),
        "button": brush_color("button"),
        "button_text": brush_color("buttonText", "text"),
        "border": brush_color("mid", "text"),
        "highlight": brush_color("highlight", "text"),
        "highlight_text": brush_color("highlightedText", "base"),
        "disabled": brush_color("placeholderText", "text"),
        "danger": "#ff8f8f" if dark else "#b42318",
        "danger_bg": "#4a2020" if dark else "#fff0ee",
    }


def _settings_style() -> str:
    values = _palette_tokens()
    return """
QDialog#HomeDashboardSettings {{ background: {window}; color: {text}; }}
QDialog#HomeDashboardSettings QLabel,
QDialog#HomeDashboardSettings QCheckBox {{ color: {text}; }}
QDialog#HomeDashboardSettings QListWidget#SettingsNav {{ background: {alternate}; border: 1px solid {border}; border-radius: 10px; color: {text}; padding: 6px; font-weight: 600; }}
QDialog#HomeDashboardSettings QListWidget#SettingsNav::item {{ border-radius: 7px; color: {text}; margin: 2px; padding: 10px 12px; }}
QDialog#HomeDashboardSettings QListWidget#SettingsNav::item:selected {{ background: {highlight}; color: {highlight_text}; }}
QDialog#HomeDashboardSettings QListWidget#SettingsNav::item:focus {{ border: 2px solid {highlight}; }}
QDialog#HomeDashboardSettings QScrollArea {{ background: transparent; border: 0; }}
QDialog#HomeDashboardSettings QWidget#SettingsPage {{ background: {base}; border: 1px solid {border}; border-radius: 12px; }}
QDialog#HomeDashboardSettings QLabel#PageTitle {{ font-size: 20px; font-weight: 750; color: {text}; }}
QDialog#HomeDashboardSettings QLabel#SectionTitle {{ color: {text}; font-size: 14px; font-weight: 750; padding-top: 10px; }}
QDialog#HomeDashboardSettings QLabel#PageHelp {{ color: {muted}; }}
QDialog#HomeDashboardSettings QWidget#AboutSection {{ background: {alternate}; border: 1px solid {border}; border-radius: 8px; }}
QDialog#HomeDashboardSettings QLineEdit,
QDialog#HomeDashboardSettings QComboBox,
QDialog#HomeDashboardSettings QSpinBox,
QDialog#HomeDashboardSettings QDoubleSpinBox,
QDialog#HomeDashboardSettings QDateEdit,
QDialog#HomeDashboardSettings QPlainTextEdit,
QDialog#HomeDashboardSettings QListWidget#ManagerList,
QDialog#HomeDashboardSettings QTreeWidget#ManagerTree {{
  background: {base}; border: 1px solid {border}; border-radius: 7px; color: {text}; min-height: 28px; padding: 3px;
}}
QDialog#HomeDashboardSettings QLineEdit:focus,
QDialog#HomeDashboardSettings QComboBox:focus,
QDialog#HomeDashboardSettings QSpinBox:focus,
QDialog#HomeDashboardSettings QDoubleSpinBox:focus,
QDialog#HomeDashboardSettings QDateEdit:focus,
QDialog#HomeDashboardSettings QPlainTextEdit:focus,
QDialog#HomeDashboardSettings QListWidget#ManagerList:focus,
QDialog#HomeDashboardSettings QTreeWidget#ManagerTree:focus {{ border: 2px solid {highlight}; }}
QDialog#HomeDashboardSettings QComboBox QAbstractItemView,
QDialog#HomeDashboardSettings QTreeWidget#ManagerTree::item {{ background: {base}; color: {text}; }}
QDialog#HomeDashboardSettings QComboBox QAbstractItemView {{ selection-background-color: {highlight}; selection-color: {highlight_text}; }}
QDialog#HomeDashboardSettings QTreeWidget#ManagerTree::item:selected {{ background: {highlight}; color: {highlight_text}; }}
QDialog#HomeDashboardSettings QPushButton {{ background: {button}; border: 1px solid {border}; border-radius: 7px; color: {button_text}; min-height: 29px; padding: 4px 10px; }}
QDialog#HomeDashboardSettings QPushButton:hover {{ border-color: {highlight}; background: {alternate}; }}
QDialog#HomeDashboardSettings QPushButton:focus {{ border: 2px solid {highlight}; }}
QDialog#HomeDashboardSettings QPushButton#DangerButton {{ background: {danger_bg}; border-color: {danger}; color: {danger}; font-weight: 650; }}
QDialog#HomeDashboardSettings QTabWidget::pane {{ border: 1px solid {border}; border-radius: 8px; background: {base}; }}
QDialog#HomeDashboardSettings QTabBar::tab {{ background: {alternate}; color: {text}; border: 1px solid {border}; padding: 7px 14px; }}
QDialog#HomeDashboardSettings QTabBar::tab:selected {{ background: {highlight}; color: {highlight_text}; font-weight: 700; }}
QDialog#HomeDashboardSettings QTabBar::tab:focus {{ border: 2px solid {highlight}; }}
QDialog#HomeDashboardSettings QWidget:disabled,
QDialog#HomeDashboardSettings QPushButton:disabled {{ background: {alternate}; color: {disabled}; border-color: {border}; }}
""".format(**values)


def _editor_style() -> str:
    values = _palette_tokens()
    return """
QDialog#HomeDashboardEditor {{ background: {window}; color: {text}; }}
QDialog#HomeDashboardEditor QLabel {{ color: {text}; }}
QDialog#HomeDashboardEditor QLabel#EditorHelp {{ color: {muted}; }}
QDialog#HomeDashboardEditor QLabel#PageTitle {{ color: {text}; font-size: 18px; font-weight: 750; }}
QDialog#HomeDashboardEditor QLineEdit,
QDialog#HomeDashboardEditor QDateEdit,
QDialog#HomeDashboardEditor QPlainTextEdit {{ background: {base}; border: 1px solid {border}; border-radius: 7px; color: {text}; padding: 5px 7px; }}
QDialog#HomeDashboardEditor QLineEdit:focus,
QDialog#HomeDashboardEditor QDateEdit:focus,
QDialog#HomeDashboardEditor QPlainTextEdit:focus {{ border: 2px solid {highlight}; }}
QDialog#HomeDashboardEditor QPushButton {{ background: {button}; border: 1px solid {border}; border-radius: 7px; color: {button_text}; min-height: 30px; padding: 4px 11px; }}
QDialog#HomeDashboardEditor QPushButton:focus {{ border: 2px solid {highlight}; }}
QDialog#HomeDashboardEditor QPushButton:disabled {{ background: {alternate}; color: {disabled}; }}
""".format(**values)


def _is_palette_change(event: Any) -> bool:
    event_type = event.type()
    names = ("PaletteChange", "ApplicationPaletteChange", "ThemeChange")
    return any(event_type == getattr(QEvent.Type, name, None) for name in names)


def _reapply_palette_style(widget: QWidget, factory: Callable[[], str]) -> bool:
    """Apply a changed application-palette stylesheet without event recursion."""
    if getattr(widget, "_hdo_palette_style_active", False):
        return False
    stylesheet = factory()
    if widget.styleSheet() == stylesheet:
        return False
    widget._hdo_palette_style_active = True
    try:
        widget.setStyleSheet(stylesheet)
    finally:
        widget._hdo_palette_style_active = False
    return True


def _queue_palette_style(
    widget: QWidget,
    factory: Callable[[], str],
    after_change: Optional[Callable[[], None]] = None,
) -> None:
    """Refresh after Qt finishes applying the new application palette."""
    if getattr(widget, "_hdo_palette_style_pending", False):
        return
    widget._hdo_palette_style_pending = True

    def apply() -> None:
        try:
            changed = _reapply_palette_style(widget, factory)
            if changed and after_change is not None:
                after_change()
        finally:
            widget._hdo_palette_style_pending = False

    QTimer.singleShot(0, apply)


def _install_palette_watcher(
    widget: QWidget,
    factory: Callable[[], str],
    after_change: Optional[Callable[[], None]] = None,
) -> None:
    """Track Anki application-palette changes while a dialog remains open."""
    timer = QTimer(widget)
    timer.setInterval(250)

    def poll() -> None:
        changed = _reapply_palette_style(widget, factory)
        if changed and after_change is not None:
            after_change()

    timer.timeout.connect(poll)
    timer.start()
    widget._hdo_palette_watcher = timer


def _page(title: str, help_text: str) -> tuple[QWidget, QVBoxLayout, QFormLayout]:
    page = QWidget()
    page.setObjectName("SettingsPage")
    page.setMaximumWidth(720)
    page.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    layout = QVBoxLayout(page)
    layout.setContentsMargins(22, 20, 22, 22)
    layout.setAlignment(Qt.AlignmentFlag.AlignTop)
    heading = QLabel(title)
    heading.setObjectName("PageTitle")
    help_label = QLabel(help_text)
    help_label.setObjectName("PageHelp")
    help_label.setWordWrap(True)
    layout.addWidget(heading)
    layout.addWidget(help_label)
    form = QFormLayout()
    form.setVerticalSpacing(12)
    form.setHorizontalSpacing(18)
    form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
    form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
    layout.addLayout(form)
    return page, layout, form


def _section_title(value: str) -> QLabel:
    label = QLabel(value)
    label.setObjectName("SectionTitle")
    return label


def _combo(items: List[tuple[str, str]], current: str) -> QComboBox:
    combo = QComboBox()
    for label, value in items:
        combo.addItem(label, value)
    index = combo.findData(current)
    combo.setCurrentIndex(max(0, index))
    return combo


def _combo_value(combo: QComboBox, default: str) -> str:
    value = combo.currentData()
    return value if isinstance(value, str) else default


class TextEditDialog(QDialog):
    def __init__(self, title: str, value: str, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("HomeDashboardEditor")
        self.setStyleSheet(_editor_style())
        _install_palette_watcher(self, _editor_style)
        self.setWindowTitle(title)
        self.resize(650, 330)
        layout = QVBoxLayout(self)
        heading = QLabel(title)
        heading.setObjectName("PageTitle")
        layout.addWidget(heading)
        label = QLabel("Use plain text or attribute-free <br>, <b>, <strong>, <i>, and <em> tags. Other markup is displayed as text.")
        label.setTextFormat(Qt.TextFormat.PlainText)
        label.setObjectName("EditorHelp")
        label.setWordWrap(True)
        layout.addWidget(label)
        self.editor = QPlainTextEdit(value)
        layout.addWidget(self.editor, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def changeEvent(self, event: Any) -> None:
        if _is_palette_change(event):
            _queue_palette_style(self, _editor_style)
        super().changeEvent(event)

    def value(self) -> str:
        return self.editor.toPlainText().strip()


class EventEditDialog(QDialog):
    def __init__(
        self,
        parent: QWidget,
        item: Optional[Mapping[str, Any]] = None,
        initial_date: str = "",
    ) -> None:
        super().__init__(parent)
        self.setObjectName("HomeDashboardEditor")
        self.setStyleSheet(_editor_style())
        _install_palette_watcher(self, _editor_style)
        self.setWindowTitle("Edit event" if item else "Add event")
        self.setMinimumWidth(680)
        self.resize(720, 260)
        self.setSizeGripEnabled(True)
        layout = QVBoxLayout(self)
        heading = QLabel("Edit calendar event" if item else "Add calendar event")
        heading.setObjectName("PageTitle")
        layout.addWidget(heading)
        form = QFormLayout()
        self.name = QLineEdit(str(item.get("name", "")) if item else "")
        self.name.setMaxLength(160)
        self.name.setMinimumWidth(480)
        self.name.setCursorPosition(0)
        self.name_count = QLabel()
        self.name_count.setObjectName("EditorHelp")
        self.name.textChanged.connect(self._update_name_count)
        self.date = QDateEdit()
        self.date.setCalendarPopup(True)
        self.date.setDisplayFormat("dddd, MMMM d, yyyy")
        value = str(item.get("date", "")) if item else initial_date
        parsed = QDate.fromString(value, "yyyy-MM-dd") if value else QDate.currentDate()
        self.date.setDate(parsed if parsed.isValid() else QDate.currentDate())
        form.addRow("Name", self.name)
        form.addRow("", self.name_count)
        form.addRow("Date", self.date)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._update_name_count(self.name.text())

    def changeEvent(self, event: Any) -> None:
        if _is_palette_change(event):
            _queue_palette_style(self, _editor_style)
        super().changeEvent(event)

    def _update_name_count(self, value: str) -> None:
        self.name_count.setText("{} of 160 characters · Long names are shortened in calendar cells.".format(len(value)))

    def _accept_if_valid(self) -> None:
        if not self.name.text().strip():
            QMessageBox.warning(self, "Event name required", "Enter a concise event name.")
            return
        self.accept()

    def values(self) -> tuple[str, str]:
        return self.name.text().strip(), self.date.date().toString("yyyy-MM-dd")


class SettingsDialog(QDialog):
    def __init__(self, controller: Any, initial_page: str = "", selected_event_date: str = "") -> None:
        super().__init__(mw)
        self.controller = controller
        self.staged = deepcopy(controller.config)
        self.quotes = list(self.staged["bible"]["quotes"])
        self.page_indices: Dict[str, int] = {}
        self.selected_event_date = selected_event_date
        self.setObjectName("HomeDashboardSettings")
        self.setWindowTitle("Home Dashboard - Overhaul settings")
        self.resize(1280, 820)
        self.setMinimumSize(760, 560)
        self.setStyleSheet(_settings_style())
        outer = QVBoxLayout(self)
        title = QLabel("Home Dashboard - Overhaul")
        title.setObjectName("PageTitle")
        subtitle = QLabel(
            "Dashboard settings are staged until Save. Event Manager actions save immediately."
        )
        subtitle.setObjectName("PageHelp")
        outer.addWidget(title)
        outer.addWidget(subtitle)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.editor_wrap = QWidget()
        editor_layout = QHBoxLayout(self.editor_wrap)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        self.nav = QListWidget()
        self.nav.setObjectName("SettingsNav")
        self.nav.setAccessibleName("Settings sections")
        self.nav.setAccessibleDescription("Choose a Home Dashboard settings section")
        self.nav.setMinimumWidth(138)
        self.nav.setMaximumWidth(174)
        self.stack = QStackedWidget()
        editor_layout.addWidget(self.nav)
        editor_layout.addWidget(self.stack, 1)
        self.splitter.addWidget(self.editor_wrap)

        self.preview_wrap = QWidget()
        preview_layout = QVBoxLayout(self.preview_wrap)
        preview_layout.setContentsMargins(8, 0, 0, 0)
        self.preview_label = QLabel("Live preview")
        self.preview_label.setObjectName("PageTitle")
        preview_layout.addWidget(self.preview_label)
        self.preview = AnkiWebView(self.preview_wrap, title="Home Dashboard preview")
        preview_layout.addWidget(self.preview, 1)
        self.splitter.addWidget(self.preview_wrap)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setStretchFactor(0, 56)
        self.splitter.setStretchFactor(1, 44)
        self.splitter.setSizes([716, 564])
        outer.addWidget(self.splitter, 1)

        self._build_appearance_page()
        self._build_dashboard_page()
        self._build_calendar_page()
        self._build_bible_page()
        self._build_about_page()
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav.setCurrentRow(0)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)
        self.preview_timer = QTimer(self)
        self.preview_timer.setSingleShot(True)
        self.preview_timer.setInterval(120)
        self.preview_timer.timeout.connect(self._render_preview)
        self._connect_preview_signals()
        self._refresh_quote_list()
        self.open_page(initial_page, selected_event_date)
        self._render_preview()
        _install_palette_watcher(self, _settings_style, self._schedule_preview)

    def resizeEvent(self, event: Any) -> None:
        if hasattr(self, "splitter"):
            next_orientation = Qt.Orientation.Vertical if self.width() < 1180 else Qt.Orientation.Horizontal
            if self.splitter.orientation() != next_orientation:
                self.splitter.setOrientation(next_orientation)
                if next_orientation == Qt.Orientation.Horizontal:
                    available = max(2, self.width() - 36)
                    self.splitter.setSizes([int(available * .56), int(available * .44)])
                else:
                    available = max(2, self.height() - 100)
                    self.splitter.setSizes([int(available * .58), int(available * .42)])
        super().resizeEvent(event)

    def changeEvent(self, event: Any) -> None:
        if _is_palette_change(event):
            callback = self._schedule_preview if hasattr(self, "preview_timer") else None
            _queue_palette_style(self, _settings_style, callback)
        super().changeEvent(event)

    def _add_page(self, name: str, page: QWidget) -> None:
        item = QListWidgetItem(name)
        item.setData(Qt.ItemDataRole.AccessibleTextRole, name)
        self.nav.addItem(item)
        self.page_indices[name.casefold()] = self.nav.count() - 1
        page.setAccessibleName("{} settings".format(name))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(page)
        self.stack.addWidget(scroll)

    def open_page(self, page: str = "", selected_event_date: str = "") -> None:
        key = str(page or "").strip().casefold()
        if key == "activity":
            key = "calendar"
        if key == "events":
            self.controller.open_event_manager(selected_event_date)
            key = "calendar"
        row = self.page_indices.get(key)
        if row is not None:
            self.nav.setCurrentRow(row)

    def _build_appearance_page(self) -> None:
        page, layout, form = _page("Appearance", "Choose a professionally balanced preset, then adjust only the high-impact presentation controls.")
        self.preset = _combo([(name, name) for name in PRESETS], self.staged["appearance"]["preset"])
        self.mode = _combo([("Follow Anki", "auto"), ("Light", "light"), ("Dark", "dark")], self.staged["appearance"]["mode"])
        self.opacity = QSlider(Qt.Orientation.Horizontal)
        self.opacity.setRange(70, 100)
        self.opacity.setValue(self.staged["appearance"]["opacity"])
        self.opacity_value = QLabel("{}%".format(self.opacity.value()))
        opacity_row = QWidget(); opacity_layout = QHBoxLayout(opacity_row); opacity_layout.setContentsMargins(0, 0, 0, 0); opacity_layout.addWidget(self.opacity, 1); opacity_layout.addWidget(self.opacity_value)
        self.blur = QSpinBox(); self.blur.setRange(0, 32); self.blur.setSuffix(" px"); self.blur.setValue(self.staged["appearance"]["blur"])
        self.density = _combo([("Compact", "compact"), ("Comfortable", "comfortable"), ("Spacious", "spacious")], self.staged["appearance"]["density"])
        self.text_scale = QSpinBox(); self.text_scale.setRange(90, 125); self.text_scale.setSuffix("%"); self.text_scale.setValue(self.staged["appearance"]["text_scale"])
        form.addRow("Color preset", self.preset)
        form.addRow("Color mode", self.mode)
        form.addRow("Panel opacity", opacity_row)
        form.addRow("Background blur", self.blur)
        form.addRow("Spacing", self.density)
        form.addRow("Text scale", self.text_scale)
        layout.addStretch()
        self._add_page("Appearance", page)

    def _build_dashboard_page(self) -> None:
        page, layout, form = _page("Dashboard", "Choose the compact metric groups shown beneath the calendar. Today’s Progress uses completed answers and the live actionable queue.")
        self.visibility: Dict[str, QCheckBox] = {}
        labels = {
            "heatmap": "Calendar",
            "today": "Today",
            "remaining": "Today’s Progress",
            "buried": "Buried Cards",
            "heatmap_metrics": "Consistency",
            "events": "Event markers and date details",
            "bible": "Bible verse",
        }
        form.addRow(_section_title("Visibility"))
        checks = QWidget(); checks_layout = QVBoxLayout(checks); checks_layout.setContentsMargins(0, 0, 0, 0)
        for key, label in labels.items():
            box = QCheckBox(label); box.setChecked(self.staged["visibility"][key]); checks_layout.addWidget(box); self.visibility[key] = box
        form.addRow("Visible sections", checks)
        form.addRow(_section_title("Pace & ETA"))
        self.pace_unit = _combo([("Seconds per card", "seconds_per_card"), ("Cards per minute", "cards_per_minute")], self.staged["study"]["pace_unit"])
        self.show_eta = QCheckBox("Show ETA"); self.show_eta.setChecked(self.staged["study"]["show_eta"])
        form.addRow("Pace display", self.pace_unit)
        form.addRow("Completion estimate", self.show_eta)
        form.addRow(_section_title("New Cards Studied"))
        self.include_rescheduled = QCheckBox("Include rescheduled cards"); self.include_rescheduled.setChecked(self.staged["new_cards"]["include_rescheduled"])
        form.addRow("Rescheduled cards", self.include_rescheduled)
        layout.addStretch()
        self._add_page("Dashboard", page)

    def _build_calendar_page(self) -> None:
        page, layout, form = _page("Calendar", "Switch between a complete Year heatmap and a conventional Month calendar. Completed reviews, due forecast, and event markers remain distinct.")
        heatmap = self.staged["heatmap"]
        self.calendar_view = _combo([("Month", "month"), ("Year", "year")], heatmap["calendar_view"])
        self.week_start = _combo([("Monday", "0"), ("Tuesday", "1"), ("Wednesday", "2"), ("Thursday", "3"), ("Friday", "4"), ("Saturday", "5"), ("Sunday", "6")], str(heatmap["week_start"]))
        self.history_days = QSpinBox(); self.history_days.setRange(0, 36500); self.history_days.setSpecialValueText("All history"); self.history_days.setValue(heatmap["history_days"])
        self.forecast_days = QSpinBox(); self.forecast_days.setRange(0, 730); self.forecast_days.setSpecialValueText("Off"); self.forecast_days.setSuffix(" days"); self.forecast_days.setValue(heatmap["forecast_days"])
        self.ignore_before_enabled = QCheckBox("Enabled")
        self.ignore_before = QDateEdit(); self.ignore_before.setCalendarPopup(True); self.ignore_before.setDisplayFormat("MMMM d, yyyy")
        parsed_ignore = QDate.fromString(heatmap["ignore_before"], "yyyy-MM-dd")
        self.ignore_before.setDate(parsed_ignore if parsed_ignore.isValid() else QDate.currentDate())
        self.ignore_before_enabled.setChecked(parsed_ignore.isValid())
        self.ignore_before.setEnabled(parsed_ignore.isValid())
        self.ignore_before_enabled.toggled.connect(self.ignore_before.setEnabled)
        ignore_row = QWidget(); ignore_layout = QHBoxLayout(ignore_row); ignore_layout.setContentsMargins(0, 0, 0, 0); ignore_layout.addWidget(self.ignore_before_enabled); ignore_layout.addWidget(self.ignore_before, 1)
        self.exclude_reschedules = QCheckBox("Exclude manual changes"); self.exclude_reschedules.setToolTip("Ignore manual reschedule and forget log entries."); self.exclude_reschedules.setChecked(heatmap["exclude_manual_reschedules"])
        self.exclude_deleted = QCheckBox("Exclude deleted cards"); self.exclude_deleted.setToolTip("Ignore review logs for cards that no longer exist."); self.exclude_deleted.setChecked(heatmap["exclude_deleted_cards"])
        self.show_forecast = QCheckBox("Show due forecast"); self.show_forecast.setChecked(heatmap["show_due_forecast"])
        form.addRow("Default view", self.calendar_view)
        form.addRow("Week starts", self.week_start)
        form.addRow("Visible history", self.history_days)
        form.addRow("Forecast range", self.forecast_days)
        form.addRow("History start", ignore_row)
        form.addRow("History cleanup", self.exclude_reschedules)
        form.addRow("Deleted cards", self.exclude_deleted)
        form.addRow("Forecast", self.show_forecast)
        scheduling_note = QLabel(
            "Study counts and due forecasts follow the active day rollover, "
            "not calendar midnight. Events continue to use their civil-calendar date."
        )
        scheduling_note.setObjectName("PageHelp")
        scheduling_note.setWordWrap(True)
        form.addRow("Date semantics", scheduling_note)
        self.deck_search = QLineEdit(); self.deck_search.setPlaceholderText("Filter decks…")
        self.deck_list = QListWidget(); self.deck_list.setObjectName("ManagerList"); self.deck_list.setMinimumHeight(120)
        excluded = set(heatmap["excluded_deck_ids"])
        found: set[int] = set()
        try:
            decks = mw.col.decks.all_names_and_ids() if mw.col else []
        except Exception:
            decks = []
        for deck in sorted(decks, key=lambda item: str(getattr(item, "name", "")).casefold()):
            deck_id = int(getattr(deck, "id", 0)); found.add(deck_id)
            item = QListWidgetItem(str(getattr(deck, "name", deck_id))); item.setData(Qt.ItemDataRole.UserRole, deck_id); item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable); item.setCheckState(Qt.CheckState.Checked if deck_id in excluded else Qt.CheckState.Unchecked); self.deck_list.addItem(item)
        for deck_id in sorted(excluded - found):
            item = QListWidgetItem("Unavailable deck ({})".format(deck_id)); item.setData(Qt.ItemDataRole.UserRole, deck_id); item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable); item.setCheckState(Qt.CheckState.Checked); self.deck_list.addItem(item)
        deck_controls = QWidget(); deck_controls_layout = QHBoxLayout(deck_controls); deck_controls_layout.setContentsMargins(0, 0, 0, 0)
        select_all = QPushButton("Select all"); select_all.clicked.connect(lambda: self._set_all_decks(Qt.CheckState.Checked))
        clear_all = QPushButton("Clear"); clear_all.clicked.connect(lambda: self._set_all_decks(Qt.CheckState.Unchecked))
        deck_controls_layout.addWidget(select_all); deck_controls_layout.addWidget(clear_all); deck_controls_layout.addStretch()
        deck_wrap = QWidget(); deck_layout = QVBoxLayout(deck_wrap); deck_layout.setContentsMargins(0, 0, 0, 0); deck_layout.addWidget(self.deck_search); deck_layout.addWidget(self.deck_list); deck_layout.addWidget(deck_controls)
        self.deck_search.textChanged.connect(self._filter_decks)
        form.addRow("Exclude decks and children", deck_wrap)
        form.addRow(_section_title("Events & external calendars"))
        self.calendar_source_summary = QLabel()
        self.calendar_source_summary.setObjectName("PageHelp")
        self.calendar_source_summary.setWordWrap(True)
        self.manage_events_button = QPushButton("Manage events & calendars")
        self.manage_events_button.setAccessibleName("Open Event Manager")
        self.manage_events_button.clicked.connect(self.controller.open_event_manager)
        form.addRow("Calendar sources", self.calendar_source_summary)
        form.addRow("", self.manage_events_button)
        self.refresh_calendar_summary()
        layout.addStretch()
        self._add_page("Calendar", page)

    def refresh_calendar_summary(self) -> None:
        if not hasattr(self, "calendar_source_summary"):
            return
        local = len(self.controller.config.get("events", {}).get("items", []))
        sources = self.controller.calendar_repository.list_sources()
        enabled = sum(1 for source in sources if source.get("enabled", True))
        errors = sum(1 for source in sources if source.get("last_error"))
        self.calendar_source_summary.setText(
            "{} local event{} · {} external calendar{} ({} enabled){}".format(
                local,
                "" if local == 1 else "s",
                len(sources),
                "" if len(sources) == 1 else "s",
                enabled,
                " · {} need attention".format(errors) if errors else "",
            )
        )

    def _build_bible_page(self) -> None:
        page, layout, form = _page("Bible Verse", "The verse is always displayed below all statistics. Text is sanitized before rendering, and visual-only saves do not advance rotation.")
        bible = self.staged["bible"]
        self.font_family = QFontComboBox(); self.font_family.setCurrentFont(self.font_family.currentFont())
        family_name = str(bible["font_family"]).split(",", 1)[0].strip().strip('"\'')
        index = self.font_family.findText(family_name); self.font_family.setCurrentIndex(max(0, index))
        self.font_size = QSpinBox(); self.font_size.setRange(8, 96); self.font_size.setSuffix(" px"); self.font_size.setValue(int(str(bible["font_size"]).replace("px", "")))
        self.font_color_value = bible["font_color"]
        self.font_color = QPushButton(self.font_color_value)
        self.font_color.clicked.connect(self._choose_font_color)
        self.theme_color = QCheckBox("Use theme-aware text color"); self.theme_color.setChecked(bible["theme_aware_color"])
        self.rotation = _combo([("Daily", "daily"), ("Every render", "every render"), ("Manual", "manual")], bible["rotation_mode"])
        form.addRow("Font family", self.font_family)
        form.addRow("Font size", self.font_size)
        form.addRow("Custom color", self.font_color)
        form.addRow("Color behavior", self.theme_color)
        form.addRow("Rotation", self.rotation)
        self.rotation_help = QLabel("Daily changes once per civil day; Every render changes on each dashboard render; Manual changes only when you select a verse.")
        self.rotation_help.setObjectName("PageHelp"); self.rotation_help.setWordWrap(True); form.addRow("", self.rotation_help)
        self.quote_search = QLineEdit(); self.quote_search.setPlaceholderText("Search the verse library…")
        self.quote_count = QLabel(); self.quote_count.setObjectName("PageHelp")
        self.quote_detail = QPlainTextEdit()
        self.quote_detail.setObjectName("SelectedVerseDetail")
        self.quote_detail.setAccessibleName("Full selected verse")
        self.quote_detail.setReadOnly(True)
        self.quote_detail.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.quote_detail.setMaximumHeight(112)
        self.quote_list = QListWidget(); self.quote_list.setObjectName("ManagerList"); self.quote_list.setMinimumHeight(220); self.quote_list.setTextElideMode(Qt.TextElideMode.ElideRight); self.quote_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout.addWidget(self.quote_search)
        layout.addWidget(self.quote_count)
        layout.addWidget(_section_title("Selected verse"))
        layout.addWidget(self.quote_detail)
        layout.addWidget(_section_title("Scripture library"))
        layout.addWidget(self.quote_list, 1)
        controls = QHBoxLayout()
        for label, handler in (("Add", self._add_quote), ("Edit", self._edit_quote), ("Duplicate", self._duplicate_quote), ("Delete", self._delete_quote), ("Import", self._import_quotes), ("Export", self._export_quotes)):
            button = QPushButton(label); button.clicked.connect(handler); controls.addWidget(button)
        controls.addStretch(); layout.addLayout(controls)
        self._add_page("Bible Verse", page)

    def _build_about_page(self) -> None:
        page, layout, _form = _page("About & Credits", "Home Dashboard - Overhaul 1.6.0 targets Anki Desktop 26.8 and is licensed under AGPL-3.0-or-later.")
        sections = (
            ("Integration", "This independently authored dashboard combines analytics, calendar events, and the Bible library in one Deck Browser surface. Existing bridge and configuration contracts remain stable."),
            ("Credits", 'Based on the Anki add-on <a href="https://github.com/glutanimate/review-heatmap">Review Heatmap by Glutanimate</a>. <a href="https://www.patreon.com/glutanimate">Click here to support Glutanimate\'s work.</a>'),
            ("Scripture library", "The supplied New Living Translation (NLT) library contains 483 verses. Edited libraries remain capped at 500 entries."),
            ("Migration / rollback", "Migration reads the five original add-ons but never edits, moves, or deletes them. Disable this add-on and re-enable the originals to roll back."),
        )
        for heading, body in sections:
            card = QWidget(); card.setObjectName("AboutSection")
            card_layout = QVBoxLayout(card); card_layout.setContentsMargins(12, 9, 12, 10); card_layout.setSpacing(3)
            card_layout.addWidget(_section_title(heading))
            label = QLabel(body); label.setWordWrap(True); label.setOpenExternalLinks(True); label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
            card_layout.addWidget(label)
            layout.addWidget(card)
        layout.addStretch()
        self._add_page("About & Credits", page)

    def _connect_preview_signals(self) -> None:
        widgets = [self.preset, self.mode, self.blur, self.density, self.text_scale, self.pace_unit, self.week_start, self.calendar_view, self.history_days, self.forecast_days, self.ignore_before, self.font_family, self.font_size, self.rotation]
        for widget in widgets:
            for signal_name in ("currentIndexChanged", "valueChanged", "textChanged"):
                signal = getattr(widget, signal_name, None)
                if signal is not None:
                    try: signal.connect(self._schedule_preview)
                    except TypeError: pass
        checks = list(self.visibility.values()) + [self.show_eta, self.include_rescheduled, self.exclude_reschedules, self.exclude_deleted, self.show_forecast, self.theme_color, self.ignore_before_enabled]
        for check in checks: check.toggled.connect(self._schedule_preview)
        self.opacity.valueChanged.connect(self._opacity_changed)
        self.ignore_before.dateChanged.connect(self._schedule_preview)
        self.font_family.currentFontChanged.connect(self._schedule_preview)
        self.quote_search.textChanged.connect(self._refresh_quote_list)
        self.quote_list.currentRowChanged.connect(self._schedule_preview)
        self.quote_list.currentRowChanged.connect(self._update_quote_detail)

    def _opacity_changed(self, value: int) -> None:
        self.opacity_value.setText("{}%".format(value)); self._schedule_preview()

    def _set_all_decks(self, state: Qt.CheckState) -> None:
        for row in range(self.deck_list.count()):
            self.deck_list.item(row).setCheckState(state)

    def _filter_decks(self, value: str) -> None:
        needle = value.strip().casefold()
        for row in range(self.deck_list.count()):
            item = self.deck_list.item(row)
            item.setHidden(bool(needle and needle not in item.text().casefold()))

    def _choose_font_color(self) -> None:
        selected = QColorDialog.getColor(parent=self, title="Choose Bible verse color")
        if not selected.isValid():
            return
        self.font_color_value = selected.name()
        self.font_color.setText(self.font_color_value)
        self._schedule_preview()

    def _schedule_preview(self, *_args: object) -> None:
        self.preview_timer.start()

    def _gather(self) -> Dict[str, Any]:
        config = deepcopy(self.staged)
        config["appearance"].update(preset=_combo_value(self.preset, "Sapphire Glass"), mode=_combo_value(self.mode, "auto"), opacity=self.opacity.value(), blur=self.blur.value(), density=_combo_value(self.density, "comfortable"), text_scale=self.text_scale.value())
        for key, box in self.visibility.items(): config["visibility"][key] = box.isChecked()
        config["study"].update(pace_unit=_combo_value(self.pace_unit, "seconds_per_card"), show_eta=self.show_eta.isChecked())
        config["new_cards"].update(include_rescheduled=self.include_rescheduled.isChecked())
        excluded = []
        for row in range(self.deck_list.count()):
            item = self.deck_list.item(row)
            if item.checkState() == Qt.CheckState.Checked: excluded.append(int(item.data(Qt.ItemDataRole.UserRole)))
        config["heatmap"].update(calendar_view=_combo_value(self.calendar_view, "year"), week_start=int(_combo_value(self.week_start, "0")), history_days=self.history_days.value(), forecast_days=self.forecast_days.value(), ignore_before=self.ignore_before.date().toString("yyyy-MM-dd") if self.ignore_before_enabled.isChecked() else "", exclude_manual_reschedules=self.exclude_reschedules.isChecked(), exclude_deleted_cards=self.exclude_deleted.isChecked(), excluded_deck_ids=excluded, show_due_forecast=self.show_forecast.isChecked())
        config["events"] = deepcopy(self.controller.config.get("events", config["events"]))
        config["bible"].update(quotes=list(self.quotes), font_family=self.font_family.currentFont().family(), font_size="{}px".format(self.font_size.value()), font_color=self.font_color_value, theme_aware_color=self.theme_color.isChecked(), rotation_mode=_combo_value(self.rotation, "daily"))
        return normalize_config(config)

    def _render_preview(self) -> None:
        config = self._gather()
        snapshot = self.controller.snapshot or sample_snapshot()
        self.preview_label.setText("Live preview" if self.controller.snapshot is not None else "Example preview · live data unavailable")
        package = mw.addonManager.addonFromModule(__name__)
        base = "/_addons/{}/web/".format(package)
        self.preview.stdHtml(render_dashboard(snapshot, config, anki_dark=self.controller.is_dark(), preview=True), css=[base + "dashboard.css"], js=[base + "dashboard.js"], context=self)

    def _selected_quote_index(self) -> Optional[int]:
        item = self.quote_list.currentItem()
        value = item.data(Qt.ItemDataRole.UserRole) if item else None
        return int(value) if isinstance(value, int) and 0 <= value < len(self.quotes) else None

    def _update_quote_detail(self, *_args: object) -> None:
        index = self._selected_quote_index()
        if index is None:
            self.quote_detail.clear()
            return
        content = verse_content(self.quotes[index])
        body = html_module.unescape(re.sub(r"<[^>]+>", "", content.body_html)).strip()
        reference = html_module.unescape(re.sub(r"<[^>]+>", "", content.reference_html)).strip()
        self.quote_detail.setPlainText("{}\n\n{}".format(body, reference).strip())

    def _refresh_quote_list(self, *_args: object) -> None:
        selected = self._selected_quote_index()
        needle = self.quote_search.text().strip().casefold() if hasattr(self, "quote_search") else ""
        self.quote_list.clear()
        selected_row = -1
        for index, quote in enumerate(self.quotes):
            if needle and needle not in quote.casefold(): continue
            content = verse_content(quote)
            body = html_module.unescape(re.sub(r"<[^>]+>", "", content.body_html)).strip()
            reference = html_module.unescape(re.sub(r"<[^>]+>", "", content.reference_html)).strip()
            plain = "{} — {}".format(reference, body) if reference else body
            item = QListWidgetItem(plain[:160] + ("…" if len(plain) > 160 else "")); item.setToolTip(plain); item.setData(Qt.ItemDataRole.UserRole, index); self.quote_list.addItem(item)
            if index == selected: selected_row = self.quote_list.count() - 1
        if selected_row >= 0: self.quote_list.setCurrentRow(selected_row)
        elif self.quote_list.count(): self.quote_list.setCurrentRow(0)
        self.quote_count.setText("Showing {} of {} verses".format(self.quote_list.count(), len(self.quotes)))
        self._update_quote_detail()
        self._schedule_preview()

    def _add_quote(self) -> None:
        dialog = TextEditDialog("Add Bible verse", "", self)
        if dialog.exec() != QDialog.DialogCode.Accepted or not dialog.value(): return
        if len(self.quotes) >= 500: QMessageBox.warning(self, "Verse limit", "The bundled NLT library is limited to 500 quoted verses."); return
        self.quotes.append(dialog.value()); self._refresh_quote_list()

    def _edit_quote(self) -> None:
        index = self._selected_quote_index()
        if index is None: return
        dialog = TextEditDialog("Edit Bible verse", self.quotes[index], self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.value(): self.quotes[index] = dialog.value(); self._refresh_quote_list()

    def _duplicate_quote(self) -> None:
        index = self._selected_quote_index()
        if index is None: return
        if len(self.quotes) >= 500: QMessageBox.warning(self, "Verse limit", "The library is limited to 500 quoted verses."); return
        self.quotes.insert(index + 1, self.quotes[index]); self._refresh_quote_list()

    def _delete_quote(self) -> None:
        index = self._selected_quote_index()
        if index is None: return
        if len(self.quotes) <= 1: QMessageBox.warning(self, "Verse required", "Keep at least one Bible verse in the library."); return
        if QMessageBox.question(self, "Delete verse?", "Delete the selected verse? This cannot be undone.") == QMessageBox.StandardButton.Yes: self.quotes.pop(index); self._refresh_quote_list()

    def _import_quotes(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Import Bible verses", "", "Verse files (*.json *.txt);;All files (*)")
        if not path: return
        try:
            text = Path(path).read_text(encoding="utf-8")
            if path.lower().endswith(".json"):
                parsed = json.loads(text); parsed = parsed.get("quotes", parsed.get("quote", [])) if isinstance(parsed, dict) else parsed
                values = [value.strip() for value in parsed if isinstance(value, str) and value.strip()] if isinstance(parsed, list) else []
            else:
                values = [value.strip() for value in text.split("\n\n") if value.strip()]
        except (OSError, ValueError, TypeError) as exc:
            QMessageBox.critical(self, "Import failed", str(exc)); return
        if not values: QMessageBox.warning(self, "No verses found", "The selected file did not contain any non-empty verses."); return
        room = max(0, 500 - len(self.quotes)); self.quotes.extend(values[:room]); self._refresh_quote_list()
        if len(values) > room: QMessageBox.information(self, "Verse limit", "Imported {} verses; {} were skipped at the 500-verse limit.".format(room, len(values) - room))

    def _export_quotes(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export Bible verses", "bible-verses.json", "JSON (*.json)")
        if not path: return
        try: Path(path).write_text(json.dumps({"quotes": self.quotes}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        except OSError as exc: QMessageBox.critical(self, "Export failed", str(exc))

    def _save(self) -> None:
        config = self._gather()
        self.controller.save_config(config)
        self.accept()

    def done(self, result: int) -> None:
        try:
            self.preview.cleanup()
        except Exception:
            pass
        super().done(result)


def _object_name(menu: Any) -> str:
    getter = getattr(menu, "objectName", None)
    try: return str(getter() if callable(getter) else getter or "")
    except Exception: return ""


def _title(menu: Any) -> str:
    getter = getattr(menu, "title", None)
    try: return str(getter() if callable(getter) else getter or "")
    except Exception: return ""


def _actions(menu: Any) -> List[Any]:
    getter = getattr(menu, "actions", None)
    try: return list(getter() if callable(getter) else getter or [])
    except Exception: return []


def _submenus(menu: Any):
    for action in _actions(menu):
        getter = getattr(action, "menu", None)
        try: submenu = getter() if callable(getter) else None
        except Exception: submenu = None
        if submenu is not None: yield submenu


def _caleb_menu(menu_bar: Any) -> Any:
    cached = getattr(mw, "_caleb_m_addons_menu", None)
    if cached is not None: return cached
    for submenu in _submenus(menu_bar):
        if _object_name(submenu) == CALEB_MENU_OBJECT_NAME or _title(submenu) == CALEB_MENU_TITLE:
            submenu.setObjectName(CALEB_MENU_OBJECT_NAME); mw._caleb_m_addons_menu = submenu; return submenu
    submenu = menu_bar.addMenu(CALEB_MENU_TITLE); submenu.setObjectName(CALEB_MENU_OBJECT_NAME); mw._caleb_m_addons_menu = submenu; return submenu


def install_settings_menu(controller: Any) -> None:
    menu_bar = getattr(getattr(mw, "form", None), "menubar", None)
    if menu_bar is None:
        getter = getattr(mw, "menuBar", None); menu_bar = getter() if callable(getter) else None
    if menu_bar is None: return
    submenu = _caleb_menu(menu_bar)
    settings_action = getattr(mw, "_home_dashboard_overhaul_settings_action", None)
    manager_action = getattr(mw, "_home_dashboard_overhaul_event_manager_action", None)
    for action in _actions(submenu):
        text = action.text() if callable(getattr(action, "text", None)) else ""
        if text == ACTION_TEXT:
            settings_action = action
        elif text == EVENT_MANAGER_ACTION_TEXT:
            manager_action = action
    if settings_action is None:
        settings_action = QAction(ACTION_TEXT, mw)
        settings_action.triggered.connect(controller.open_settings)
        submenu.addAction(settings_action)
    if manager_action is None:
        manager_action = QAction(EVENT_MANAGER_ACTION_TEXT, mw)
        manager_action.triggered.connect(controller.open_event_manager)
        submenu.addAction(manager_action)
    mw._home_dashboard_overhaul_settings_action = settings_action
    mw._home_dashboard_overhaul_event_manager_action = manager_action
