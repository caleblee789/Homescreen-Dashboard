"""Professional staged settings editor integrated into the Caleb M. menu."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import datetime
import html as html_module
import json
from pathlib import Path
import re
import time
from typing import Any, Callable, Dict, List, Mapping, MutableMapping, Optional

from aqt import mw
from aqt.qt import (
    QAction,
    QAbstractItemView,
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
    QHeaderView,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QLocale,
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
    QTabWidget,
    QTimer,
    QVBoxLayout,
    QWidget,
    QTreeWidget,
    QTreeWidgetItem,
    Qt,
)
from aqt.webview import AnkiWebView

from .config_schema import normalize_config
from .renderer import render_dashboard, sample_snapshot
from .settings_model import (
    SECTION_GROUPS,
    SECTION_LABELS,
    SettingsDraft,
    font_family_value,
    import_quotes,
    resolve_section,
)
from .themes import PRESETS, composite_color, resolve_theme
from .verse import MAX_VERSE_BYTES, MAX_VERSE_CHARS, verse_content, verse_within_limit


CALEB_MENU_TITLE = "Caleb M. Add-ons Settings"
CALEB_MENU_OBJECT_NAME = "caleb_m_addons_menu"
ACTION_TEXT = "Home Dashboard - Overhaul settings"


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
        "verse_card": brush_color("base"),
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


def _theme_tokens(
    config: Optional[Mapping[str, Any]] = None,
    anki_dark: Optional[bool] = None,
) -> Dict[str, str]:
    """Translate the staged dashboard theme into editor design tokens."""
    if not isinstance(config, Mapping):
        return _palette_tokens()
    appearance = config.get("appearance", {})
    if not isinstance(appearance, Mapping):
        return _palette_tokens()
    if anki_dark is None:
        application = QApplication.instance()
        palette = application.palette() if application is not None else mw.palette()
        anki_dark = palette.window().color().lightness() < 128
    theme = resolve_theme(
        appearance.get("preset"),
        appearance.get("mode"),
        bool(anki_dark),
    )
    return {
        "window": theme["background"],
        "base": theme["surface"],
        "verse_card": composite_color(
            theme["surface"],
            theme["background"],
            int(appearance.get("opacity", 88)) / 100,
        ),
        "alternate": theme["accent_soft"],
        "text": theme["text"],
        "muted": theme["muted"],
        "button": theme["surface"],
        "button_text": theme["text"],
        "border": theme["control_border"],
        "highlight": theme["accent"],
        "highlight_text": theme["on_accent"],
        "disabled": theme["disabled"],
        "danger": theme["danger"],
        "danger_bg": theme["danger_soft"],
    }


def _color_contrast(left: str, right: str) -> float:
    def luminance(value: str) -> float:
        raw = value.lstrip("#")
        channels = [int(raw[index:index + 2], 16) / 255 for index in (0, 2, 4)]
        linear = [
            channel / 12.92 if channel <= .04045 else ((channel + .055) / 1.055) ** 2.4
            for channel in channels
        ]
        return .2126 * linear[0] + .7152 * linear[1] + .0722 * linear[2]

    try:
        high, low = sorted((luminance(left), luminance(right)), reverse=True)
    except (ValueError, IndexError):
        return 1.0
    return (high + .05) / (low + .05)


def _foreground_for(background: str) -> str:
    return "#ffffff" if _color_contrast("#ffffff", background) >= _color_contrast("#000000", background) else "#000000"


def _settings_style(
    config: Optional[Mapping[str, Any]] = None,
    anki_dark: Optional[bool] = None,
) -> str:
    values = _theme_tokens(config, anki_dark)
    return """
QDialog#HomeDashboardSettings {{ background: {window}; color: {text}; }}
QDialog#HomeDashboardSettings QLabel,
QDialog#HomeDashboardSettings QCheckBox {{ color: {text}; }}
QDialog#HomeDashboardSettings QListWidget#SettingsNav {{ background: {base}; border: 1px solid {border}; border-radius: 12px; color: {text}; padding: 7px; font-weight: 600; }}
QDialog#HomeDashboardSettings QListWidget#SettingsNav::item {{ border-radius: 7px; color: {text}; margin: 2px; padding: 9px 11px; }}
QDialog#HomeDashboardSettings QListWidget#SettingsNav::item:disabled {{ color: {muted}; background: transparent; font-size: 11px; font-weight: 750; padding-top: 14px; padding-bottom: 3px; }}
QDialog#HomeDashboardSettings QListWidget#SettingsNav::item:selected {{ background: {highlight}; color: {highlight_text}; }}
QDialog#HomeDashboardSettings QListWidget#SettingsNav::item:focus {{ border: 2px solid {highlight}; }}
QDialog#HomeDashboardSettings QScrollArea {{ background: transparent; border: 0; }}
QDialog#HomeDashboardSettings QWidget#SettingsPage {{ background: {base}; border: 1px solid {border}; border-radius: 12px; }}
QDialog#HomeDashboardSettings QLabel#PageTitle {{ font-size: 20px; font-weight: 750; color: {text}; }}
QDialog#HomeDashboardSettings QLabel#SectionTitle {{ color: {text}; font-size: 14px; font-weight: 750; padding-top: 10px; }}
QDialog#HomeDashboardSettings QLabel#PageHelp,
QDialog#HomeDashboardSettings QLabel#FieldHelp {{ color: {muted}; }}
QDialog#HomeDashboardSettings QWidget#SettingsRow,
QDialog#HomeDashboardSettings QWidget#AboutSection {{ background: {window}; border: 1px solid {border}; border-radius: 9px; }}
QDialog#HomeDashboardSettings QWidget#ActionBar {{ background: {base}; border: 1px solid {border}; border-radius: 10px; }}
QDialog#HomeDashboardSettings QLabel#DirtyBadge {{ background: {alternate}; border: 1px solid {highlight}; border-radius: 9px; color: {text}; font-weight: 700; padding: 3px 8px; }}
QDialog#HomeDashboardSettings QLabel#DataBadge {{ background: {alternate}; border-radius: 8px; color: {text}; font-weight: 650; padding: 3px 7px; }}
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
QDialog#HomeDashboardSettings QTreeWidget#ManagerTree::item {{ background: {base}; border-bottom: 1px solid {alternate}; color: {text}; padding: 4px 5px; }}
QDialog#HomeDashboardSettings QTreeWidget#ManagerTree QHeaderView::section {{ background: {alternate}; border: 0; border-bottom: 1px solid {border}; color: {text}; font-weight: 700; padding: 4px 6px; }}
QDialog#HomeDashboardSettings QComboBox QAbstractItemView {{ selection-background-color: {highlight}; selection-color: {highlight_text}; }}
QDialog#HomeDashboardSettings QTreeWidget#ManagerTree::item:selected {{ background: {highlight}; color: {highlight_text}; }}
QDialog#HomeDashboardSettings QPushButton {{ background: {button}; border: 1px solid {border}; border-radius: 7px; color: {button_text}; min-height: 29px; padding: 4px 10px; }}
QDialog#HomeDashboardSettings QPushButton:hover {{ border-color: {highlight}; background: {alternate}; }}
QDialog#HomeDashboardSettings QPushButton:focus {{ border: 2px solid {highlight}; }}
QDialog#HomeDashboardSettings QPushButton#PrimaryButton {{ background: {highlight}; border-color: {highlight}; color: {highlight_text}; font-weight: 750; }}
QDialog#HomeDashboardSettings QPushButton#PrimaryButton:disabled {{ background: {alternate}; border-color: {border}; color: {disabled}; }}
QDialog#HomeDashboardSettings QPushButton#DangerButton {{ background: {danger_bg}; border-color: {danger}; color: {danger}; font-weight: 650; }}
QDialog#HomeDashboardSettings QPushButton#DangerButton:disabled {{ background: {alternate}; border-color: {border}; color: {disabled}; }}
QDialog#HomeDashboardSettings QLabel#EmptyState {{ background: {alternate}; border: 1px solid {border}; border-radius: 7px; color: {text}; padding: 8px 10px; }}
QDialog#HomeDashboardSettings QTabWidget::pane {{ border: 1px solid {border}; border-radius: 8px; background: {base}; }}
QDialog#HomeDashboardSettings QTabBar::tab {{ background: {alternate}; color: {text}; border: 1px solid {border}; padding: 7px 14px; }}
QDialog#HomeDashboardSettings QTabBar::tab:selected {{ background: {highlight}; color: {highlight_text}; font-weight: 700; }}
QDialog#HomeDashboardSettings QTabBar::tab:focus {{ border: 2px solid {highlight}; }}
QDialog#HomeDashboardSettings QWidget:disabled,
QDialog#HomeDashboardSettings QPushButton:disabled {{ background: {alternate}; color: {disabled}; border-color: {border}; }}
""".format(**values)


def _editor_style(tokens: Optional[Mapping[str, str]] = None) -> str:
    values = dict(tokens) if isinstance(tokens, Mapping) else _palette_tokens()
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
QDialog#HomeDashboardEditor QPushButton#PrimaryButton {{ background: {highlight}; border-color: {highlight}; color: {highlight_text}; font-weight: 750; }}
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
    form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
    layout.addLayout(form)
    return page, layout, form


def _section_title(value: str) -> QLabel:
    label = QLabel(value)
    label.setObjectName("SectionTitle")
    return label


def _field_label(title: str, description: str = "") -> QWidget:
    wrap = QWidget()
    layout = QVBoxLayout(wrap)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(2)
    name = QLabel(title)
    name.setWordWrap(True)
    layout.addWidget(name)
    if description:
        help_label = QLabel(description)
        help_label.setObjectName("FieldHelp")
        help_label.setWordWrap(True)
        layout.addWidget(help_label)
    return wrap


def _description_checkbox(title: str, description: str, checked: bool) -> tuple[QWidget, QCheckBox]:
    wrap = QWidget()
    wrap.setObjectName("SettingsRow")
    layout = QVBoxLayout(wrap)
    layout.setContentsMargins(11, 8, 11, 9)
    layout.setSpacing(3)
    box = QCheckBox(title)
    box.setChecked(checked)
    box.setAccessibleName(title)
    box.setAccessibleDescription(description)
    help_label = QLabel(description)
    help_label.setObjectName("FieldHelp")
    help_label.setWordWrap(True)
    layout.addWidget(box)
    layout.addWidget(help_label)
    return wrap, box


def _paired_slider(
    minimum: int,
    maximum: int,
    value: int,
    suffix: str,
) -> tuple[QWidget, QSlider, QSpinBox]:
    wrap = QWidget()
    layout = QHBoxLayout(wrap)
    layout.setContentsMargins(0, 0, 0, 0)
    slider = QSlider(Qt.Orientation.Horizontal)
    slider.setRange(minimum, maximum)
    slider.setValue(value)
    spin = QSpinBox()
    spin.setRange(minimum, maximum)
    spin.setSuffix(suffix)
    spin.setValue(value)
    spin.setMinimumWidth(86)
    slider.valueChanged.connect(spin.setValue)
    spin.valueChanged.connect(slider.setValue)
    layout.addWidget(slider, 1)
    layout.addWidget(spin)
    return wrap, slider, spin


def _set_accessibility(widget: QWidget, name: str, description: str = "") -> None:
    widget.setAccessibleName(name)
    if description:
        widget.setAccessibleDescription(description)


def _manifest_metadata() -> Dict[str, Any]:
    try:
        parsed = json.loads((Path(__file__).resolve().parent / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _editor_tokens(parent: QWidget) -> Dict[str, str]:
    candidate: Optional[QWidget] = parent
    while candidate is not None:
        tokens = getattr(candidate, "_hdo_theme_tokens", None)
        if isinstance(tokens, Mapping):
            return dict(tokens)
        candidate = candidate.parentWidget()
    return _palette_tokens()


def _display_date(value: str) -> str:
    parsed = QDate.fromString(str(value), "yyyy-MM-dd")
    if not parsed.isValid():
        return str(value)
    return QLocale.system().toString(parsed, "MMM d, yyyy")


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
        self._style_factory = lambda: _editor_style(_editor_tokens(parent))
        self.setStyleSheet(self._style_factory())
        _install_palette_watcher(self, self._style_factory)
        self.setWindowTitle(title)
        self.setMinimumSize(520, 300)
        self.resize(650, 360)
        layout = QVBoxLayout(self)
        heading = QLabel(title)
        heading.setObjectName("PageTitle")
        layout.addWidget(heading)
        label = QLabel("Use plain text or attribute-free <br>, <b>, <strong>, <i>, and <em> tags. Other markup is displayed as text. Each entry is limited to 4,000 characters and 16,000 UTF-8 bytes.")
        label.setTextFormat(Qt.TextFormat.PlainText)
        label.setObjectName("EditorHelp")
        label.setWordWrap(True)
        layout.addWidget(label)
        self.editor = QPlainTextEdit(value)
        _set_accessibility(
            self.editor,
            "Bible verse text",
            "Enter the verse body and reference. Supported simple emphasis tags are sanitized before display.",
        )
        layout.addWidget(self.editor, 1)
        self.editor_count = QLabel("")
        self.editor_count.setObjectName("EditorHelp")
        self.editor_count.setAccessibleName("Verse entry size")
        layout.addWidget(self.editor_count)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        save_button = buttons.button(QDialogButtonBox.StandardButton.Save)
        if save_button is not None:
            save_button.setObjectName("PrimaryButton")
            save_button.setText("Save verse")
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.editor.textChanged.connect(self._update_count)
        self._update_count()

    def changeEvent(self, event: Any) -> None:
        if _is_palette_change(event):
            _queue_palette_style(self, self._style_factory)
        super().changeEvent(event)

    def value(self) -> str:
        return self.editor.toPlainText().strip()

    def _update_count(self) -> None:
        value = self.value()
        self.editor_count.setText(
            "{} / {} characters · {} / {} UTF-8 bytes".format(
                len(value), MAX_VERSE_CHARS, len(value.encode("utf-8")), MAX_VERSE_BYTES
            )
        )

    def _accept_if_valid(self) -> None:
        value = self.value()
        if not value:
            QMessageBox.warning(self, "Verse text required", "Enter a Bible verse before saving.")
            return
        if not verse_within_limit(value):
            QMessageBox.warning(
                self,
                "Verse entry is too long",
                "Shorten this entry to at most 4,000 characters and 16,000 UTF-8 bytes.",
            )
            return
        self.accept()


class EventEditDialog(QDialog):
    def __init__(
        self,
        parent: QWidget,
        item: Optional[Mapping[str, Any]] = None,
        initial_date: str = "",
    ) -> None:
        super().__init__(parent)
        self.setObjectName("HomeDashboardEditor")
        self._style_factory = lambda: _editor_style(_editor_tokens(parent))
        self.setStyleSheet(self._style_factory())
        _install_palette_watcher(self, self._style_factory)
        self.setWindowTitle("Edit event" if item else "Add event")
        self.setMinimumWidth(680)
        self.resize(720, 260)
        self.setSizeGripEnabled(True)
        layout = QVBoxLayout(self)
        heading = QLabel("Edit calendar event" if item else "Add calendar event")
        heading.setObjectName("PageTitle")
        layout.addWidget(heading)
        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.name = QLineEdit(str(item.get("name", "")) if item else "")
        self.name.setMaxLength(160)
        self.name.setMinimumWidth(280)
        self.name.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.name.setCursorPosition(0)
        _set_accessibility(self.name, "Event name", "Required. Up to 160 characters.")
        self.name_count = QLabel()
        self.name_count.setObjectName("EditorHelp")
        self.name.textChanged.connect(self._update_name_count)
        self.date = QDateEdit()
        self.date.setCalendarPopup(True)
        self.date.setDisplayFormat("dddd, MMMM d, yyyy")
        _set_accessibility(self.date, "Event date", "Choose the civil-calendar date for this local event.")
        value = str(item.get("date", "")) if item else initial_date
        parsed = QDate.fromString(value, "yyyy-MM-dd") if value else QDate.currentDate()
        self.date.setDate(parsed if parsed.isValid() else QDate.currentDate())
        form.addRow("Name", self.name)
        form.addRow("", self.name_count)
        form.addRow("Date", self.date)
        form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        layout.addLayout(form)
        layout.addStretch(1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        save_button = buttons.button(QDialogButtonBox.StandardButton.Save)
        if save_button is not None:
            save_button.setObjectName("PrimaryButton")
            save_button.setText("Save event")
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._update_name_count(self.name.text())

    def changeEvent(self, event: Any) -> None:
        if _is_palette_change(event):
            _queue_palette_style(self, self._style_factory)
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
        self.draft = SettingsDraft(controller.config)
        self.staged = deepcopy(self.draft.values)
        self.quotes = list(self.staged["bible"]["quotes"])
        self.pending_manual_quote: Optional[str] = None
        self._font_family_touched = False
        self.page_indices: Dict[str, int] = {}
        self.nav_rows: Dict[str, int] = {}
        self.selected_event_date = selected_event_date
        self.current_section = "theme_layout"
        self._last_nav_group = ""
        self._responsive_bucket = ""
        self._preview_requested = False
        self._building = True
        self._allow_close = False
        self.setObjectName("HomeDashboardSettings")
        self.setWindowTitle("Home Dashboard settings")
        self.resize(1280, 820)
        self.setMinimumSize(760, 560)
        self._hdo_theme_tokens = _theme_tokens(self.staged, self.controller.is_dark())
        self.setStyleSheet(_settings_style(self.staged, self.controller.is_dark()))
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 14, 16, 14)
        outer.setSpacing(10)

        header = QHBoxLayout()
        header_text = QVBoxLayout()
        header_text.setSpacing(2)
        title = QLabel("Home Dashboard settings")
        title.setObjectName("PageTitle")
        subtitle = QLabel("Preview changes as you work. Nothing is applied until you choose Save.")
        subtitle.setObjectName("PageHelp")
        subtitle.setWordWrap(True)
        header_text.addWidget(title)
        header_text.addWidget(subtitle)
        header.addLayout(header_text, 1)
        self.dirty_badge = QLabel("Unsaved changes")
        self.dirty_badge.setObjectName("DirtyBadge")
        self.dirty_badge.setAccessibleName("Unsaved changes")
        self.dirty_badge.hide()
        header.addWidget(self.dirty_badge, 0, Qt.AlignmentFlag.AlignTop)
        outer.addLayout(header)

        self.section_selector_wrap = QWidget()
        selector_layout = QHBoxLayout(self.section_selector_wrap)
        selector_layout.setContentsMargins(0, 0, 0, 0)
        selector_label = QLabel("Section")
        self.section_selector = QComboBox()
        _set_accessibility(
            self.section_selector,
            "Settings section",
            "Choose which Home Dashboard settings section to edit.",
        )
        selector_layout.addWidget(selector_label)
        selector_layout.addWidget(self.section_selector, 1)
        self.section_selector_wrap.hide()
        outer.addWidget(self.section_selector_wrap)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.editor_wrap = QWidget()
        self.editor_layout = QHBoxLayout(self.editor_wrap)
        self.editor_layout.setContentsMargins(0, 0, 0, 0)
        self.editor_layout.setSpacing(10)
        self.nav = QListWidget()
        self.nav.setObjectName("SettingsNav")
        self.nav.setAccessibleName("Settings sections")
        self.nav.setAccessibleDescription("Choose a Home Dashboard settings section")
        self.nav.setMinimumWidth(176)
        self.nav.setMaximumWidth(210)
        self.nav.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.stack = QStackedWidget()
        self.editor_layout.addWidget(self.nav)
        self.editor_layout.addWidget(self.stack, 1)
        self.splitter.addWidget(self.editor_wrap)

        self.preview_wrap = QWidget()
        preview_layout = QVBoxLayout(self.preview_wrap)
        preview_layout.setContentsMargins(8, 0, 0, 0)
        preview_header = QHBoxLayout()
        self.preview_label = QLabel("Contextual preview")
        self.preview_label.setObjectName("PageTitle")
        self.preview_data_badge = QLabel("Sample data")
        self.preview_data_badge.setObjectName("DataBadge")
        preview_header.addWidget(self.preview_label)
        preview_header.addStretch()
        preview_header.addWidget(self.preview_data_badge)
        preview_layout.addLayout(preview_header)
        self.preview = AnkiWebView(self.preview_wrap, title="Home Dashboard preview")
        self.preview.setAccessibleName("Home Dashboard contextual preview")
        self.preview.setAccessibleDescription("A production-rendered preview of the current settings section.")
        preview_layout.addWidget(self.preview, 1)
        self.splitter.addWidget(self.preview_wrap)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setStretchFactor(0, 56)
        self.splitter.setStretchFactor(1, 44)
        self.splitter.setSizes([716, 564])
        outer.addWidget(self.splitter, 1)

        self.preview_timer = QTimer(self)
        self.preview_timer.setSingleShot(True)
        self.preview_timer.setInterval(140)
        self.preview_timer.timeout.connect(self._render_preview)

        self._build_appearance_page()
        self._build_dashboard_page()
        self._build_calendar_page()
        self._build_events_page()
        self._build_bible_page()
        self._build_about_page()
        self.nav.currentRowChanged.connect(self._nav_changed)
        self.section_selector.currentIndexChanged.connect(self._selector_changed)

        action_bar = QWidget()
        action_bar.setObjectName("ActionBar")
        action_layout = QHBoxLayout(action_bar)
        action_layout.setContentsMargins(9, 7, 9, 7)
        self.reset_button = QPushButton("Restore section defaults")
        _set_accessibility(
            self.reset_button,
            "Restore section defaults",
            "Restore only this section's display preferences. Events and the verse library are never erased.",
        )
        self.reset_button.clicked.connect(self._reset_current_section)
        action_layout.addWidget(self.reset_button)
        self.preview_toggle = QPushButton("Show preview")
        self.preview_toggle.setCheckable(True)
        _set_accessibility(
            self.preview_toggle,
            "Show contextual preview",
            "Show or hide the production-rendered preview below the editor.",
        )
        self.preview_toggle.toggled.connect(self._toggle_preview)
        action_layout.addWidget(self.preview_toggle)
        action_layout.addStretch()
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        self.save_button = self.buttons.button(QDialogButtonBox.StandardButton.Save)
        if self.save_button is not None:
            self.save_button.setText("Save changes")
            self.save_button.setObjectName("PrimaryButton")
            self.save_button.setEnabled(False)
            _set_accessibility(
                self.save_button,
                "Save changes",
                "Apply all staged changes and close settings.",
            )
        cancel_button = self.buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel_button is not None:
            _set_accessibility(cancel_button, "Cancel", "Close settings without applying staged changes.")
        self.buttons.accepted.connect(self._save)
        self.buttons.rejected.connect(self.reject)
        action_layout.addWidget(self.buttons)
        outer.addWidget(action_bar)

        self._connect_preview_signals()
        self._refresh_event_lists()
        self._refresh_quote_list()
        self._building = False
        self.open_page(initial_page, selected_event_date)
        self._sync_draft()
        self._apply_responsive(force=True)
        self._render_preview()
        _install_palette_watcher(self, self._current_stylesheet, self._schedule_preview)

    def resizeEvent(self, event: Any) -> None:
        if hasattr(self, "splitter"):
            self._apply_responsive()
        super().resizeEvent(event)

    def changeEvent(self, event: Any) -> None:
        if _is_palette_change(event):
            callback = self._schedule_preview if hasattr(self, "preview_timer") else None
            _queue_palette_style(self, self._current_stylesheet, callback)
        super().changeEvent(event)

    def _current_stylesheet(self) -> str:
        config = self.draft.values if hasattr(self, "draft") else self.staged
        return _settings_style(config, self.controller.is_dark())

    def _add_page(self, section_id: str, page: QWidget) -> None:
        name = SECTION_LABELS[section_id]
        group = SECTION_GROUPS[section_id]
        if group != self._last_nav_group:
            header = QListWidgetItem(group.upper())
            header.setFlags(Qt.ItemFlag.NoItemFlags)
            header.setData(Qt.ItemDataRole.AccessibleTextRole, "{} settings".format(group))
            self.nav.addItem(header)
            self._last_nav_group = group
        item = QListWidgetItem(name)
        item.setData(Qt.ItemDataRole.UserRole, section_id)
        item.setData(Qt.ItemDataRole.AccessibleTextRole, "{}: {}".format(group, name))
        self.nav.addItem(item)
        self.nav_rows[section_id] = self.nav.count() - 1
        self.section_selector.addItem("{} — {}".format(group, name), section_id)
        self.page_indices[section_id] = self.stack.count()
        page.setAccessibleName("{} settings".format(name))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(page)
        self.stack.addWidget(scroll)

    def open_page(self, page: str = "", selected_event_date: str = "") -> None:
        section_id = resolve_section(page)
        row = self.nav_rows.get(section_id)
        if row is not None:
            self.nav.setCurrentRow(row)
        if section_id == "events" and selected_event_date:
            self._select_event_date(selected_event_date)

    def _nav_changed(self, row: int) -> None:
        item = self.nav.item(row)
        section_id = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        if not isinstance(section_id, str) or section_id not in self.page_indices:
            return
        self._show_section(section_id, source="nav")

    def _selector_changed(self, index: int) -> None:
        section_id = self.section_selector.itemData(index)
        if isinstance(section_id, str) and section_id in self.page_indices:
            self._show_section(section_id, source="selector")

    def _show_section(self, section_id: str, source: str = "") -> None:
        self.current_section = section_id
        self.stack.setCurrentIndex(self.page_indices[section_id])
        if source != "nav":
            self.nav.setCurrentRow(self.nav_rows[section_id])
        if source != "selector":
            index = self.section_selector.findData(section_id)
            if index >= 0 and self.section_selector.currentIndex() != index:
                self.section_selector.blockSignals(True)
                self.section_selector.setCurrentIndex(index)
                self.section_selector.blockSignals(False)
        self._update_section_chrome()
        self._schedule_preview()

    def _responsive_mode(self) -> str:
        if self.width() >= 1180:
            return "wide"
        if self.width() >= 900:
            return "medium"
        return "compact"

    def _apply_responsive(self, force: bool = False) -> None:
        mode = self._responsive_mode()
        changed = force or mode != self._responsive_bucket
        if not changed:
            return
        self._responsive_bucket = mode
        wide = mode == "wide"
        compact = mode == "compact"
        self.nav.setVisible(not compact)
        self.section_selector_wrap.setVisible(compact)
        self.splitter.setOrientation(
            Qt.Orientation.Horizontal if wide else Qt.Orientation.Vertical
        )
        if wide:
            self._preview_requested = True
            available = max(2, self.width() - 36)
            self.splitter.setSizes([int(available * .57), int(available * .43)])
        else:
            self._preview_requested = False
            self.preview_toggle.blockSignals(True)
            self.preview_toggle.setChecked(False)
            self.preview_toggle.blockSignals(False)
            available = max(2, self.height() - 150)
            self.splitter.setSizes([available, max(260, int(available * .42))])
        self._update_section_chrome()

    def _toggle_preview(self, checked: bool) -> None:
        self._preview_requested = bool(checked)
        self.preview_toggle.setText("Hide preview" if checked else "Show preview")
        self._update_preview_visibility()
        if checked:
            self._schedule_preview()

    def _update_section_chrome(self) -> None:
        resettable = self.current_section in {
            "theme_layout",
            "home_screen",
            "calendar_data",
            "bible_verse",
        }
        self.reset_button.setVisible(resettable)
        self.preview_toggle.setVisible(
            self._responsive_bucket != "wide" and self.current_section != "about"
        )
        self._update_preview_visibility()

    def _update_preview_visibility(self) -> None:
        visible = self.current_section != "about" and (
            self._responsive_bucket == "wide" or self._preview_requested
        )
        self.preview_wrap.setVisible(visible)

    def _build_appearance_page(self) -> None:
        page, layout, form = _page(
            "Theme & layout",
            "Choose the dashboard’s visual system, then tune its spacing and scale. The editor and preview follow these staged choices immediately.",
        )
        appearance = self.staged["appearance"]
        self.preset = _combo([(name, name) for name in PRESETS], appearance["preset"])
        _set_accessibility(
            self.preset,
            "Color preset",
            "Choose one of twelve contrast-checked dashboard palettes.",
        )
        preset_wrap = QWidget()
        preset_layout = QVBoxLayout(preset_wrap)
        preset_layout.setContentsMargins(0, 0, 0, 0)
        preset_layout.setSpacing(6)
        self.preset_swatch = QLabel()
        self.preset_swatch.setObjectName("DataBadge")
        self.preset_swatch.setTextFormat(Qt.TextFormat.RichText)
        self.preset_swatch.setAccessibleName("Selected preset colors")
        preset_layout.addWidget(self.preset)
        preset_layout.addWidget(self.preset_swatch)
        self.mode = _combo(
            [("Follow Anki", "auto"), ("Always light", "light"), ("Always dark", "dark")],
            appearance["mode"],
        )
        _set_accessibility(
            self.mode,
            "Color mode",
            "Follow Anki automatically, or keep the dashboard in light or dark mode.",
        )
        opacity_row, self.opacity_slider, self.opacity = _paired_slider(
            70, 100, appearance["opacity"], "%"
        )
        _set_accessibility(
            self.opacity_slider,
            "Panel opacity slider",
            "Higher values make dashboard cards more solid and easier to separate from the background.",
        )
        _set_accessibility(self.opacity, "Panel opacity value")
        self.density = _combo(
            [("Compact", "compact"), ("Comfortable", "comfortable"), ("Spacious", "spacious")],
            appearance["density"],
        )
        _set_accessibility(self.density, "Layout density", "Controls the space between dashboard elements.")
        text_scale_row, self.text_scale_slider, self.text_scale = _paired_slider(
            90, 125, appearance["text_scale"], "%"
        )
        _set_accessibility(
            self.text_scale_slider,
            "Dashboard text scale slider",
            "Scales dashboard text while retaining responsive layout.",
        )
        _set_accessibility(self.text_scale, "Dashboard text scale value")
        form.addRow(
            _field_label("Color preset", "Coordinated surfaces, text, borders, focus, and status colors."),
            preset_wrap,
        )
        form.addRow(
            _field_label("Color mode", "Follow Anki responds to the application theme without rewriting your preference."),
            self.mode,
        )
        form.addRow(
            _field_label("Panel opacity", "Controls how solid the dashboard cards appear."),
            opacity_row,
        )
        form.addRow(
            _field_label("Layout density", "Compact fits more information; Spacious adds breathing room."),
            self.density,
        )
        form.addRow(
            _field_label("Text scale", "Adjusts dashboard typography independently of Anki’s interface scale."),
            text_scale_row,
        )
        layout.addStretch()
        self._update_preset_swatch()
        self._add_page("theme_layout", page)

    def _build_dashboard_page(self) -> None:
        page, layout, form = _page(
            "Home screen",
            "Choose what appears on the Deck Browser. Disabled dependencies preserve your stored preference and become available again when their requirement is restored.",
        )
        self.visibility: Dict[str, QCheckBox] = {}
        visibility = self.staged["visibility"]

        def add_visibility(group: str, key: str, title: str, description: str) -> None:
            form.addRow(_section_title(group)) if group else None
            row, box = _description_checkbox(title, description, visibility[key])
            self.visibility[key] = box
            form.addRow(row)

        add_visibility(
            "Calendar",
            "heatmap",
            "Study calendar",
            "Shows completed reviews, due forecasts, and date details in Month or Year view.",
        )
        add_visibility(
            "",
            "events",
            "Event markers and date details",
            "Adds your local event markers to the calendar. Requires Study calendar.",
        )
        self.events_dependency = QLabel("Requires Study calendar. Your event preference remains saved while unavailable.")
        self.events_dependency.setObjectName("FieldHelp")
        self.events_dependency.setWordWrap(True)
        form.addRow(self.events_dependency)
        add_visibility(
            "Study metrics",
            "today",
            "Today",
            "Total answers, new cards studied, time studied, pace, and the optional ETA.",
        )
        add_visibility(
            "",
            "remaining",
            "Today’s Progress",
            "Completed percentage and the live actionable new, learning, and review queues.",
        )
        add_visibility(
            "Supporting information",
            "buried",
            "Buried Cards",
            "Counts buried new, learning, and review cards without changing them.",
        )
        add_visibility(
            "",
            "heatmap_metrics",
            "Consistency",
            "Average active-day reviews, active-day percentage, and streaks.",
        )
        add_visibility(
            "",
            "bible",
            "Bible verse",
            "Shows the selected verse card after the study dashboard.",
        )
        form.addRow(_section_title("Pace & ETA"))
        self.pace_unit = _combo(
            [("Seconds per card", "seconds_per_card"), ("Cards per minute", "cards_per_minute")],
            self.staged["study"]["pace_unit"],
        )
        _set_accessibility(
            self.pace_unit,
            "Pace display",
            "Choose how the same pace calculation is presented.",
        )
        form.addRow(
            _field_label("Pace display", "Changes presentation only; the underlying study history is unchanged."),
            self.pace_unit,
        )
        eta_row, self.show_eta = _description_checkbox(
            "Show estimated completion time",
            "Uses the live actionable queue and current pace. Requires Today.",
            self.staged["study"]["show_eta"],
        )
        form.addRow(eta_row)
        self.eta_dependency = QLabel("Requires Today. Your ETA preference remains saved while unavailable.")
        self.eta_dependency.setObjectName("FieldHelp")
        self.eta_dependency.setWordWrap(True)
        form.addRow(self.eta_dependency)
        form.addRow(_section_title("New Cards Studied"))
        new_row, self.include_rescheduled = _description_checkbox(
            "Include manually rescheduled cards",
            "Counts a card as newly studied when its first qualifying answer follows a manual reschedule.",
            self.staged["new_cards"]["include_rescheduled"],
        )
        form.addRow(new_row)
        layout.addStretch()
        self._add_page("home_screen", page)

    def _build_calendar_page(self) -> None:
        page, layout, form = _page(
            "Calendar & data",
            "Control the calendar display and which collection history contributes to it. Collection-backed changes are staged now and recalculated only after Save.",
        )
        heatmap = self.staged["heatmap"]

        updates_badge = QLabel("Collection-dependent options · Updates after Save")
        updates_badge.setObjectName("DataBadge")
        updates_badge.setAccessibleName("Collection options update after Save")
        form.addRow(updates_badge)

        form.addRow(_section_title("Display"))
        self.calendar_view = _combo([("Month", "month"), ("Year", "year")], heatmap["calendar_view"])
        self.week_start = _combo([("Monday", "0"), ("Tuesday", "1"), ("Wednesday", "2"), ("Thursday", "3"), ("Friday", "4"), ("Saturday", "5"), ("Sunday", "6")], str(heatmap["week_start"]))
        _set_accessibility(self.calendar_view, "Default calendar view", "Choose Month or Year view.")
        _set_accessibility(self.week_start, "First day of week", "Choose the weekday used to start calendar rows.")
        form.addRow(_field_label("Default view", "Month is conventional; Year emphasizes long-term consistency."), self.calendar_view)
        form.addRow(_field_label("Week starts", "Applied consistently to Month and Year layouts."), self.week_start)

        form.addRow(_section_title("Range & Forecast"))
        self.history_days = QSpinBox(); self.history_days.setRange(0, 36500); self.history_days.setSpecialValueText("All history"); self.history_days.setValue(heatmap["history_days"])
        self.forecast_days = QSpinBox(); self.forecast_days.setRange(0, 730); self.forecast_days.setSpecialValueText("Off"); self.forecast_days.setSuffix(" days"); self.forecast_days.setValue(heatmap["forecast_days"])
        _set_accessibility(self.history_days, "Visible history", "Zero means all available history.")
        _set_accessibility(self.forecast_days, "Due forecast range", "The number of future scheduling dates to show.")
        forecast_row, self.show_forecast = _description_checkbox(
            "Show due forecast",
            "Adds due-card markers without combining them with completed-review intensity.",
            heatmap["show_due_forecast"],
        )
        self.forecast_days.setEnabled(self.show_forecast.isChecked())
        self.show_forecast.toggled.connect(self.forecast_days.setEnabled)
        form.addRow(
            _field_label("Visible history", "Choose All history or a rolling day limit. A History start date can narrow it further."),
            self.history_days,
        )
        form.addRow(forecast_row)
        form.addRow(_field_label("Forecast range", "Available only while Show due forecast is enabled."), self.forecast_days)
        scheduling_note = QLabel(
            "Study counts and due forecasts follow the configured rollover, "
            "not calendar midnight. Events continue to use their civil-calendar date."
        )
        scheduling_note.setObjectName("PageHelp")
        scheduling_note.setWordWrap(True)
        form.addRow(_field_label("Date semantics"), scheduling_note)

        form.addRow(_section_title("History Rules"))
        self.ignore_before_enabled = QCheckBox("Enabled")
        self.ignore_before = QDateEdit(); self.ignore_before.setCalendarPopup(True); self.ignore_before.setDisplayFormat("MMMM d, yyyy")
        parsed_ignore = QDate.fromString(heatmap["ignore_before"], "yyyy-MM-dd")
        self.ignore_before.setDate(parsed_ignore if parsed_ignore.isValid() else QDate.currentDate())
        self.ignore_before_enabled.setChecked(parsed_ignore.isValid())
        self.ignore_before.setEnabled(parsed_ignore.isValid())
        self.ignore_before_enabled.toggled.connect(self.ignore_before.setEnabled)
        _set_accessibility(self.ignore_before_enabled, "Use history start date", "Enable a fixed earliest history date.")
        _set_accessibility(self.ignore_before, "History start date", "Reviews before this date are ignored after Save.")
        ignore_row = QWidget(); ignore_layout = QHBoxLayout(ignore_row); ignore_layout.setContentsMargins(0, 0, 0, 0); ignore_layout.addWidget(self.ignore_before_enabled); ignore_layout.addWidget(self.ignore_before, 1)
        self.exclude_reschedules = QCheckBox("Exclude manual changes"); self.exclude_reschedules.setToolTip("Ignore manual reschedule and forget log entries."); self.exclude_reschedules.setChecked(heatmap["exclude_manual_reschedules"])
        self.exclude_deleted = QCheckBox("Exclude deleted cards"); self.exclude_deleted.setToolTip("Ignore review logs for cards that no longer exist."); self.exclude_deleted.setChecked(heatmap["exclude_deleted_cards"])
        _set_accessibility(self.exclude_reschedules, "Exclude manual changes", "Ignore manual reschedule and forget log entries after Save.")
        _set_accessibility(self.exclude_deleted, "Exclude deleted cards", "Ignore review logs for cards that no longer exist after Save.")
        form.addRow(
            _field_label("History start", "When both controls are set, the later of this date and the rolling day limit wins."),
            ignore_row,
        )
        form.addRow(_field_label("Manual changes", "Filters manual reschedule and forget log entries."), self.exclude_reschedules)
        form.addRow(_field_label("Deleted cards", "Filters logs whose cards no longer exist."), self.exclude_deleted)

        form.addRow(_section_title("Deck Exclusions"))
        self.deck_search = QLineEdit(); self.deck_search.setPlaceholderText("Filter decks…")
        _set_accessibility(self.deck_search, "Filter decks", "Filter by full deck path without changing exclusions.")
        self.deck_list = QListWidget(); self.deck_list.setObjectName("ManagerList"); self.deck_list.setMinimumHeight(120)
        self.deck_list.setAccessibleName("Deck exclusions")
        self.deck_list.setAccessibleDescription("Checked decks and all of their child decks are excluded from calendar analytics.")
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
        self.deck_exclusion_summary = QLabel()
        self.deck_exclusion_summary.setObjectName("PageHelp")
        self.deck_exclusion_summary.setAccessibleName("Deck exclusion count")
        deck_controls = QWidget(); deck_controls_layout = QHBoxLayout(deck_controls); deck_controls_layout.setContentsMargins(0, 0, 0, 0)
        exclude_shown = QPushButton("Exclude all shown"); exclude_shown.clicked.connect(lambda: self._set_visible_decks(Qt.CheckState.Checked))
        include_shown = QPushButton("Include all shown"); include_shown.clicked.connect(lambda: self._set_visible_decks(Qt.CheckState.Unchecked))
        _set_accessibility(exclude_shown, "Exclude shown decks", "Exclude every deck currently visible in the filtered list.")
        _set_accessibility(include_shown, "Include shown decks", "Remove the exclusion from every deck currently visible in the filtered list.")
        deck_controls_layout.addWidget(exclude_shown); deck_controls_layout.addWidget(include_shown); deck_controls_layout.addStretch()
        deck_wrap = QWidget(); deck_layout = QVBoxLayout(deck_wrap); deck_layout.setContentsMargins(0, 0, 0, 0); deck_layout.addWidget(self.deck_search); deck_layout.addWidget(self.deck_exclusion_summary); deck_layout.addWidget(self.deck_list); deck_layout.addWidget(deck_controls)
        self.deck_search.textChanged.connect(self._filter_decks)
        self.deck_list.itemChanged.connect(self._update_deck_exclusion_summary)
        self._update_deck_exclusion_summary()
        form.addRow(
            _field_label("Excluded decks", "A checked parent excludes its descendants during collection analytics; full deck paths are retained."),
            deck_wrap,
        )
        layout.addStretch()
        self._add_page("calendar_data", page)

    def _build_events_page(self) -> None:
        page, layout, _form = _page(
            "Events",
            "Manage local dashboard events. Past events move to Archived automatically; archive and restore are reversible.",
        )
        save_note = QLabel("All event changes remain staged until you choose Save changes.")
        save_note.setObjectName("DataBadge")
        save_note.setAccessibleName("Event changes are staged")
        layout.addWidget(save_note)
        self.event_date_context = QLabel("")
        self.event_date_context.setObjectName("PageHelp")
        self.event_date_context.setAccessibleName("Selected calendar date")
        self.event_date_context.hide()
        layout.addWidget(self.event_date_context)
        event_toolbar = QHBoxLayout()
        self.event_search = QLineEdit(); self.event_search.setPlaceholderText("Filter events…")
        _set_accessibility(self.event_search, "Filter events", "Filter by event name or ISO date.")
        self.event_sort = _combo([("Soonest first", "ascending"), ("Latest first", "descending")], self.staged["events"].get("sort", "ascending"))
        _set_accessibility(self.event_sort, "Event sort order", "Sort active and archived events by date.")
        event_toolbar.addWidget(self.event_search, 1); event_toolbar.addWidget(self.event_sort)
        layout.addLayout(event_toolbar)
        self.event_tabs = QTabWidget()
        _set_accessibility(self.event_tabs, "Active and archived events", "Switch between active and archived local events.")
        self.active_events = self._event_tree("Active calendar events")
        self.archived_events = self._event_tree("Archived calendar events")
        self.event_tabs.addTab(self.active_events, "Active (0)")
        self.event_tabs.addTab(self.archived_events, "Archived (0)")
        manager_row = QHBoxLayout()
        manager_row.addWidget(self.event_tabs, 1)
        controls = QVBoxLayout()
        controls.setSpacing(6)
        self.event_add = QPushButton("Add event"); self.event_add.setObjectName("PrimaryButton"); self.event_add.clicked.connect(self._add_event); controls.addWidget(self.event_add)
        self.event_edit = QPushButton("Edit"); self.event_edit.clicked.connect(self._edit_event); controls.addWidget(self.event_edit)
        self.event_archive = QPushButton("Archive"); self.event_archive.clicked.connect(self._toggle_event_archive); controls.addWidget(self.event_archive)
        self.event_delete = QPushButton("Delete"); self.event_delete.setObjectName("DangerButton"); self.event_delete.clicked.connect(self._delete_event); controls.addWidget(self.event_delete)
        controls.addStretch()
        for button, name, description in (
            (self.event_add, "Add event", "Open the local event editor."),
            (self.event_edit, "Edit selected event", "Edit the selected event without saving it yet."),
            (self.event_archive, "Archive selected event", "Archive or restore the selected event without saving it yet."),
            (self.event_delete, "Delete selected event", "Stage deletion of the selected event."),
        ):
            _set_accessibility(button, name, description)
        manager_row.addLayout(controls)
        layout.addLayout(manager_row, 1)
        self.event_empty_state = QLabel("")
        self.event_empty_state.setObjectName("EmptyState")
        self.event_empty_state.setWordWrap(True)
        self.event_empty_state.hide()
        layout.addWidget(self.event_empty_state)
        self.event_selection_state = QLabel("Select an event to edit, archive, restore, or delete it.")
        self.event_selection_state.setObjectName("PageHelp")
        self.event_selection_state.setWordWrap(True)
        self.event_selection_state.setAccessibleName("Event selection status")
        layout.addWidget(self.event_selection_state)
        self.event_action_feedback = QLabel("")
        self.event_action_feedback.setObjectName("PageHelp")
        self.event_action_feedback.setAccessibleName("Event action confirmation")
        self.event_action_feedback.setWordWrap(True)
        layout.addWidget(self.event_action_feedback)
        self.event_search.textChanged.connect(self._refresh_event_lists)
        self.event_sort.currentIndexChanged.connect(self._refresh_event_lists)
        self.event_tabs.currentChanged.connect(self._update_event_actions)
        self.active_events.itemSelectionChanged.connect(self._update_event_actions)
        self.archived_events.itemSelectionChanged.connect(self._update_event_actions)
        self.active_events.itemDoubleClicked.connect(lambda *_args: self._edit_event())
        self.archived_events.itemDoubleClicked.connect(lambda *_args: self._edit_event())
        self._add_page("events", page)

    def _event_tree(self, accessible_name: str) -> QTreeWidget:
        tree = QTreeWidget()
        tree.setObjectName("ManagerTree")
        tree.setAccessibleName(accessible_name)
        tree.setHeaderLabels(["Date", "Event"])
        tree.setRootIsDecorated(False)
        # Qt can paint native alternate-base stripes through an otherwise empty
        # tree, especially when the staged dashboard theme differs from Anki's
        # current mode. A solid viewport keeps the empty state calm and avoids
        # implying phantom rows; real rows retain explicit separators above.
        tree.setAlternatingRowColors(False)
        tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        tree.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        tree.setMinimumHeight(210)
        return tree

    def _build_bible_page(self) -> None:
        page, layout, form = _page(
            "Bible verse",
            "Customize the verse card separately from its library. Selecting a library item previews that exact verse without changing daily or manual rotation state.",
        )
        bible = self.staged["bible"]
        form.addRow(_section_title("Display"))
        self.font_family = QFontComboBox(); self.font_family.setCurrentFont(self.font_family.currentFont())
        family_name = str(bible["font_family"]).split(",", 1)[0].strip().strip('"\'')
        index = self.font_family.findText(family_name); self.font_family.setCurrentIndex(max(0, index))
        self.font_size = QSpinBox(); self.font_size.setRange(8, 96); self.font_size.setSuffix(" px"); self.font_size.setValue(int(str(bible["font_size"]).replace("px", "")))
        self.font_color_value = bible["font_color"]
        self.font_color = QPushButton("Choose custom color…")
        self.font_color.clicked.connect(self._choose_font_color)
        self.font_color_swatch = QLabel()
        self.font_color_swatch.setFixedWidth(94)
        self.font_color_swatch.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.font_color_swatch.setAccessibleName("Current custom verse color")
        color_row = QWidget()
        color_layout = QHBoxLayout(color_row)
        color_layout.setContentsMargins(0, 0, 0, 0)
        color_layout.addWidget(self.font_color, 1)
        color_layout.addWidget(self.font_color_swatch)
        theme_row, self.theme_color = _description_checkbox(
            "Use theme-aware text color",
            "Uses the preset’s readable text token and disables the custom color control.",
            bible["theme_aware_color"],
        )
        self.rotation = _combo(
            [
                ("Once per day", "daily"),
                ("Each dashboard refresh", "every render"),
                ("Only when changed manually", "manual"),
            ],
            bible["rotation_mode"],
        )
        _set_accessibility(self.font_family, "Verse font family", "Choose the font used only by the verse card.")
        _set_accessibility(self.font_size, "Verse font size", "Choose a verse-card size from 8 to 96 pixels.")
        _set_accessibility(self.font_color, "Choose custom verse color", "Available when theme-aware text color is off.")
        _set_accessibility(
            self.rotation,
            "Verse rotation",
            "Choose daily, every dashboard refresh, or manual rotation. Previewing a selection does not rotate it.",
        )
        form.addRow(_field_label("Font family", "Applies only to verse body and reference text."), self.font_family)
        form.addRow(_field_label("Font size", "The dashboard remains responsive at larger values."), self.font_size)
        form.addRow(_field_label("Custom color", "Used only when theme-aware color is turned off."), color_row)
        self.font_color_warning = QLabel("")
        self.font_color_warning.setObjectName("FieldHelp")
        self.font_color_warning.setWordWrap(True)
        self.font_color_warning.setAccessibleName("Custom verse color contrast")
        form.addRow(self.font_color_warning)
        form.addRow(theme_row)
        form.addRow(
            _field_label("Rotation", "Daily uses the civil date; refresh can change each render; manual preserves the current stored choice."),
            self.rotation,
        )
        self._update_color_swatch()

        layout.addWidget(_section_title("Verse library"))
        library_help = QLabel(
            "The library is staged with the rest of settings. Imports trim empty entries, skip exact duplicates, and stop at 500 verses."
        )
        library_help.setObjectName("PageHelp")
        library_help.setWordWrap(True)
        layout.addWidget(library_help)
        self.quote_search = QLineEdit(); self.quote_search.setPlaceholderText("Search the verse library…")
        _set_accessibility(self.quote_search, "Search verse library", "Filter staged verses by their displayed text or reference.")
        self.quote_count = QLabel(); self.quote_count.setObjectName("PageHelp")
        self.quote_detail = QPlainTextEdit()
        self.quote_detail.setObjectName("SelectedVerseDetail")
        self.quote_detail.setAccessibleName("Full selected verse")
        self.quote_detail.setReadOnly(True)
        self.quote_detail.setAccessibleDescription("Read the complete text and reference of the selected staged verse.")
        self.quote_detail.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.quote_detail.setMaximumHeight(112)
        self.quote_list = QListWidget(); self.quote_list.setObjectName("ManagerList"); self.quote_list.setMinimumHeight(220); self.quote_list.setTextElideMode(Qt.TextElideMode.ElideRight); self.quote_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        _set_accessibility(self.quote_list, "Verse library", "Choose a staged verse to read, edit, duplicate, delete, or preview.")
        layout.addWidget(self.quote_search)
        layout.addWidget(self.quote_count)
        layout.addWidget(_section_title("Selected verse"))
        layout.addWidget(self.quote_detail)
        layout.addWidget(_section_title("Scripture library"))
        layout.addWidget(self.quote_list, 1)
        current_row = QHBoxLayout()
        self.quote_use_current = QPushButton("Use selected as current")
        self.quote_use_current.setObjectName("PrimaryButton")
        self.quote_use_current.clicked.connect(self._stage_selected_manual_quote)
        _set_accessibility(
            self.quote_use_current,
            "Use selected verse as current",
            "With manual rotation selected, stage this verse as the one shown after Save.",
        )
        self.quote_current_feedback = QLabel("Choose manual rotation to set a specific current verse.")
        self.quote_current_feedback.setObjectName("PageHelp")
        self.quote_current_feedback.setWordWrap(True)
        self.quote_current_feedback.setAccessibleName("Current verse selection status")
        current_row.addWidget(self.quote_use_current)
        current_row.addWidget(self.quote_current_feedback, 1)
        layout.addLayout(current_row)
        controls = QHBoxLayout()
        self.quote_add = QPushButton("Add")
        self.quote_edit = QPushButton("Edit")
        self.quote_duplicate = QPushButton("Duplicate")
        self.quote_delete = QPushButton("Delete")
        self.quote_delete.setObjectName("DangerButton")
        self.quote_import = QPushButton("Import")
        self.quote_export = QPushButton("Export")
        for button, handler, description in (
            (self.quote_add, self._add_quote, "Add a verse to the staged library."),
            (self.quote_edit, self._edit_quote, "Edit the selected staged verse."),
            (self.quote_duplicate, self._duplicate_quote, "Duplicate the selected staged verse."),
            (self.quote_delete, self._delete_quote, "Stage deletion of the selected verse."),
            (self.quote_import, self._import_quotes, "Import verses into the staged library."),
            (self.quote_export, self._export_quotes, "Export the current staged library as JSON."),
        ):
            button.clicked.connect(handler)
            _set_accessibility(button, button.text(), description)
            controls.addWidget(button)
        controls.addStretch(); layout.addLayout(controls)
        self._add_page("bible_verse", page)

    def _build_about_page(self) -> None:
        manifest = _manifest_metadata()
        version = str(manifest.get("human_version", "Unknown"))
        minimum = int(manifest.get("min_point_version", 0) or 0)
        maximum = int(manifest.get("max_point_version", 0) or 0)

        def anki_version(point: int) -> str:
            if point <= 0:
                return "Unknown"
            major = point // 10000
            minor = (point % 10000) // 100
            patch = point % 100
            return "{}.{}.{}".format(major, minor, patch) if patch else "{}.{}".format(major, minor)

        compatibility = anki_version(minimum)
        if maximum and maximum != minimum:
            compatibility = "{}–{}".format(compatibility, anki_version(maximum))
        migration = self.staged.get("migration", {})
        warnings = migration.get("warnings", []) if isinstance(migration, Mapping) else []
        if warnings:
            migration_status = "Migration completed with {} warning{}: {}".format(
                len(warnings),
                "" if len(warnings) == 1 else "s",
                " · ".join(str(value) for value in warnings[:3]),
            )
        elif isinstance(migration, Mapping) and migration.get("completed"):
            migration_status = "Migration completed{} with no recorded warnings.".format(
                " on {}".format(migration.get("completed_at")) if migration.get("completed_at") else ""
            )
        else:
            migration_status = "No completed legacy migration is recorded. Original add-ons remain untouched."
        page, layout, _form = _page(
            "About",
            "Home Dashboard - Overhaul {} · Anki Desktop {} · configuration schema 3 · AGPL-3.0-or-later.".format(
                version, compatibility
            ),
        )
        sections = (
            ("Compatibility", "Version {} is packaged for Anki Desktop {}. The Caleb M. settings menu route, dashboard bridge commands, and schema-3 storage remain compatible.".format(version, compatibility)),
            ("Migration status", migration_status),
            ("Data & privacy", "Study analytics, deck exclusions, local events, the verse library, and rotation state remain on this device in Anki’s add-on data. Ordinary previews reuse a cached snapshot, disable Deck Browser-only actions, and do not query the collection or contact an external calendar service."),
            ("Scripture notice", "Scripture quotations are taken from the Holy Bible, New Living Translation, copyright ©1996, 2004, 2015 by Tyndale House Foundation. Used by permission of Tyndale House Publishers, Carol Stream, Illinois 60188. All rights reserved. The bundled 483 entries contain 500 quoted verses."),
            ("Credits", 'Based on the Anki add-on <a href="https://github.com/glutanimate/review-heatmap">Review Heatmap by Glutanimate</a>. <a href="https://www.patreon.com/glutanimate">Click here to support Glutanimate\'s work.</a>'),
            ("Rollback", "Disable Home Dashboard - Overhaul and re-enable the original add-ons. Migration never edits, moves, or deletes their configuration. Keep a copy of exported verses before replacing a heavily edited library."),
        )
        for heading, body in sections:
            card = QWidget(); card.setObjectName("AboutSection")
            card_layout = QVBoxLayout(card); card_layout.setContentsMargins(12, 9, 12, 10); card_layout.setSpacing(3)
            card_layout.addWidget(_section_title(heading))
            label = QLabel(body); label.setWordWrap(True); label.setOpenExternalLinks(True); label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
            card_layout.addWidget(label)
            layout.addWidget(card)
        layout.addStretch()
        self._add_page("about", page)

    def _connect_preview_signals(self) -> None:
        for combo in (
            self.preset,
            self.mode,
            self.density,
            self.pace_unit,
            self.week_start,
            self.calendar_view,
            self.rotation,
        ):
            combo.currentIndexChanged.connect(self._schedule_preview)
        for spin in (
            self.opacity,
            self.text_scale,
            self.history_days,
            self.forecast_days,
            self.font_size,
        ):
            spin.valueChanged.connect(self._schedule_preview)
        checks = list(self.visibility.values()) + [
            self.show_eta,
            self.include_rescheduled,
            self.exclude_reschedules,
            self.exclude_deleted,
            self.show_forecast,
            self.theme_color,
            self.ignore_before_enabled,
        ]
        for check in checks:
            check.toggled.connect(self._schedule_preview)
        self.ignore_before.dateChanged.connect(self._schedule_preview)
        self.font_family.currentFontChanged.connect(self._font_family_changed)
        self.quote_search.textChanged.connect(self._refresh_quote_list)
        self.quote_list.currentRowChanged.connect(self._schedule_preview)
        self.quote_list.currentRowChanged.connect(self._update_quote_detail)
        self.rotation.currentIndexChanged.connect(self._update_quote_actions)

    def _update_preset_swatch(self) -> None:
        name = _combo_value(self.preset, "Sapphire Glass")
        mode = _combo_value(self.mode, "auto")
        tokens = resolve_theme(name, mode, self.controller.is_dark())
        colors = [tokens[key] for key in ("background", "surface", "accent", "text")]
        squares = " ".join(
            '<span style="background:{}; border:1px solid {}; color:{};">&nbsp;&nbsp;&nbsp;&nbsp;</span>'.format(
                color, tokens["control_border"], color
            )
            for color in colors
        )
        self.preset_swatch.setText("{} &nbsp; {}".format(squares, html_module.escape(name)))
        self.preset_swatch.setAccessibleDescription(
            "{} palette: background {}, surface {}, accent {}, and text {}.".format(name, *colors)
        )

    def _update_color_swatch(self) -> None:
        if not hasattr(self, "font_color_swatch"):
            return
        tokens = getattr(self, "_hdo_theme_tokens", _palette_tokens())
        foreground = _foreground_for(self.font_color_value)
        self.font_color_swatch.setText(self.font_color_value.upper())
        self.font_color_swatch.setStyleSheet(
            "background: {}; color: {}; border: 2px solid {}; border-radius: 6px; padding: 5px;".format(
                self.font_color_value,
                foreground,
                tokens["border"],
            )
        )
        ratio = _color_contrast(self.font_color_value, tokens["verse_card"])
        custom_enabled = hasattr(self, "theme_color") and not self.theme_color.isChecked()
        if hasattr(self, "font_color_warning"):
            self.font_color_warning.setVisible(custom_enabled and ratio < 4.5)
            self.font_color_warning.setText(
                "Low contrast ({:.1f}:1) against the current verse card. Choose a darker or lighter color, or use theme-aware text color.".format(
                    ratio
                )
                if custom_enabled and ratio < 4.5
                else ""
            )
        self.font_color_swatch.setAccessibleDescription(
            "Current custom verse color {}. Contrast against the verse card is {:.1f} to 1.".format(
                self.font_color_value.upper(), ratio
            )
        )

    def _apply_theme(self) -> None:
        config = self.draft.values
        self._hdo_theme_tokens = _theme_tokens(config, self.controller.is_dark())
        stylesheet = _settings_style(config, self.controller.is_dark())
        if self.styleSheet() != stylesheet:
            self.setStyleSheet(stylesheet)
        self._update_preset_swatch()
        self._update_color_swatch()

    def _update_dependencies(self) -> None:
        state = self.draft.dependency_state
        self.show_eta.setEnabled(state["study.show_eta"])
        self.visibility["events"].setEnabled(state["visibility.events"])
        self.forecast_days.setEnabled(state["heatmap.forecast_days"])
        self.font_color.setEnabled(state["bible.font_color"])
        self.font_color_swatch.setEnabled(state["bible.font_color"])
        self.events_dependency.setVisible(not state["visibility.events"])
        self.eta_dependency.setVisible(not state["study.show_eta"])

    def _sync_draft(self) -> None:
        if self._building:
            return
        values = self._gather()
        self.draft.replace_values(values)
        self.staged = deepcopy(self.draft.values)
        self._update_dependencies()
        self._update_dirty_state()
        self._apply_theme()

    def _update_dirty_state(self) -> None:
        dirty = self.draft.dirty or self.pending_manual_quote is not None
        self.dirty_badge.setVisible(dirty)
        if self.save_button is not None:
            self.save_button.setEnabled(dirty)
        if dirty:
            count = len(self.draft.changed_paths) + (1 if self.pending_manual_quote is not None else 0)
            self.dirty_badge.setText(
                "Unsaved changes · {} setting{}".format(count, "" if count == 1 else "s")
            )
        else:
            self.dirty_badge.setText("No unsaved changes")

    def _reset_current_section(self) -> None:
        self._sync_draft()
        if not self.draft.reset_section(self.current_section):
            return
        self.staged = deepcopy(self.draft.values)
        self.quotes = list(self.staged["bible"]["quotes"])
        self._apply_config_to_widgets(self.staged)
        self._sync_draft()
        self._schedule_preview()

    @staticmethod
    def _set_combo_data(combo: QComboBox, value: object) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    def _apply_config_to_widgets(self, config: Mapping[str, Any]) -> None:
        previous_building = self._building
        self._building = True
        try:
            appearance = config["appearance"]
            self._set_combo_data(self.preset, appearance["preset"])
            self._set_combo_data(self.mode, appearance["mode"])
            self.opacity.setValue(int(appearance["opacity"]))
            self._set_combo_data(self.density, appearance["density"])
            self.text_scale.setValue(int(appearance["text_scale"]))
            for key, box in self.visibility.items():
                box.setChecked(bool(config["visibility"][key]))
            self._set_combo_data(self.pace_unit, config["study"]["pace_unit"])
            self.show_eta.setChecked(bool(config["study"]["show_eta"]))
            self.include_rescheduled.setChecked(
                bool(config["new_cards"]["include_rescheduled"])
            )
            heatmap = config["heatmap"]
            self._set_combo_data(self.calendar_view, heatmap["calendar_view"])
            self._set_combo_data(self.week_start, str(heatmap["week_start"]))
            self.history_days.setValue(int(heatmap["history_days"]))
            self.forecast_days.setValue(int(heatmap["forecast_days"]))
            self.show_forecast.setChecked(bool(heatmap["show_due_forecast"]))
            parsed = QDate.fromString(str(heatmap["ignore_before"]), "yyyy-MM-dd")
            self.ignore_before_enabled.setChecked(parsed.isValid())
            if parsed.isValid():
                self.ignore_before.setDate(parsed)
            self.exclude_reschedules.setChecked(bool(heatmap["exclude_manual_reschedules"]))
            self.exclude_deleted.setChecked(bool(heatmap["exclude_deleted_cards"]))
            excluded = set(int(value) for value in heatmap["excluded_deck_ids"])
            for row in range(self.deck_list.count()):
                item = self.deck_list.item(row)
                deck_id = int(item.data(Qt.ItemDataRole.UserRole))
                item.setCheckState(
                    Qt.CheckState.Checked if deck_id in excluded else Qt.CheckState.Unchecked
                )
            self._set_combo_data(self.event_sort, config["events"]["sort"])
            bible = config["bible"]
            family_name = str(bible["font_family"]).split(",", 1)[0].strip().strip('"\'')
            family_index = self.font_family.findText(family_name)
            if family_index >= 0:
                self.font_family.setCurrentIndex(family_index)
            self.font_size.setValue(int(str(bible["font_size"]).replace("px", "")))
            self.font_color_value = str(bible["font_color"])
            self.theme_color.setChecked(bool(bible["theme_aware_color"]))
            self._set_combo_data(self.rotation, bible["rotation_mode"])
            self.quotes = list(bible["quotes"])
            self.pending_manual_quote = None
            self._font_family_touched = False
            self._refresh_event_lists()
            self._refresh_quote_list()
            self._update_deck_exclusion_summary()
        finally:
            self._building = previous_building
        self._update_preset_swatch()
        self._update_color_swatch()

    def _set_visible_decks(self, state: Qt.CheckState) -> None:
        for row in range(self.deck_list.count()):
            item = self.deck_list.item(row)
            if not item.isHidden():
                item.setCheckState(state)
        self._update_deck_exclusion_summary()

    def _update_deck_exclusion_summary(self, *_args: object) -> None:
        excluded = 0
        shown = 0
        shown_excluded = 0
        for row in range(self.deck_list.count()):
            item = self.deck_list.item(row)
            is_excluded = item.checkState() == Qt.CheckState.Checked
            if is_excluded:
                excluded += 1
            if not item.isHidden():
                shown += 1
                if is_excluded:
                    shown_excluded += 1
        self.deck_exclusion_summary.setText(
            "{} excluded overall · {} of {} shown excluded".format(
                excluded,
                shown_excluded,
                shown,
            )
        )
        if hasattr(self, "preview_timer"):
            self._schedule_preview()

    def _filter_decks(self, value: str) -> None:
        needle = value.strip().casefold()
        for row in range(self.deck_list.count()):
            item = self.deck_list.item(row)
            item.setHidden(bool(needle and needle not in item.text().casefold()))
        self._update_deck_exclusion_summary()

    def _choose_font_color(self) -> None:
        selected = QColorDialog.getColor(parent=self, title="Choose Bible verse color")
        if not selected.isValid():
            return
        self.font_color_value = selected.name()
        self._update_color_swatch()
        self._schedule_preview()

    def _font_family_changed(self, *_args: object) -> None:
        if self._building:
            return
        self._font_family_touched = True
        self._schedule_preview()

    def _schedule_preview(self, *_args: object) -> None:
        if self._building or not hasattr(self, "preview_timer"):
            return
        self._sync_draft()
        self.preview_timer.start()

    def _gather(self) -> Dict[str, Any]:
        config = deepcopy(self.staged)
        config["appearance"].update(
            preset=_combo_value(self.preset, "Sapphire Glass"),
            mode=_combo_value(self.mode, "auto"),
            opacity=self.opacity.value(),
            density=_combo_value(self.density, "comfortable"),
            text_scale=self.text_scale.value(),
        )
        for key, box in self.visibility.items():
            config["visibility"][key] = box.isChecked()
        config["study"].update(
            pace_unit=_combo_value(self.pace_unit, "seconds_per_card"),
            show_eta=self.show_eta.isChecked(),
        )
        config["new_cards"].update(include_rescheduled=self.include_rescheduled.isChecked())
        excluded = []
        for row in range(self.deck_list.count()):
            item = self.deck_list.item(row)
            if item.checkState() == Qt.CheckState.Checked:
                excluded.append(int(item.data(Qt.ItemDataRole.UserRole)))
        config["heatmap"].update(
            calendar_view=_combo_value(self.calendar_view, "year"),
            week_start=int(_combo_value(self.week_start, "0")),
            history_days=self.history_days.value(),
            forecast_days=self.forecast_days.value(),
            ignore_before=(
                self.ignore_before.date().toString("yyyy-MM-dd")
                if self.ignore_before_enabled.isChecked()
                else ""
            ),
            exclude_manual_reschedules=self.exclude_reschedules.isChecked(),
            exclude_deleted_cards=self.exclude_deleted.isChecked(),
            excluded_deck_ids=excluded,
            show_due_forecast=self.show_forecast.isChecked(),
        )
        config["events"]["sort"] = _combo_value(self.event_sort, "ascending")
        selected_family = self.font_family.currentFont().family()
        staged_family = str(config["bible"].get("font_family", selected_family))
        font_family = font_family_value(
            staged_family,
            selected_family,
            self._font_family_touched,
        )
        config["bible"].update(
            quotes=list(self.quotes),
            font_family=font_family,
            font_size="{}px".format(self.font_size.value()),
            font_color=self.font_color_value,
            theme_aware_color=self.theme_color.isChecked(),
            rotation_mode=_combo_value(self.rotation, "daily"),
        )
        return normalize_config(config)

    def _contextual_preview_config(self) -> Dict[str, Any]:
        config = deepcopy(self.draft.values)
        visibility = config["visibility"]
        if self.current_section == "home_screen":
            visibility["heatmap"] = False
            visibility["bible"] = False
        elif self.current_section in {"calendar_data", "events"}:
            visibility.update(
                heatmap=True,
                today=False,
                remaining=False,
                buried=False,
                heatmap_metrics=False,
                bible=False,
            )
            visibility["events"] = self.current_section == "events"
            if self.current_section == "events":
                config["heatmap"]["calendar_view"] = "month"
                selected = self._selected_event()
                selected_date = (
                    str(selected.get("date")) if selected is not None else self.selected_event_date
                )
                if selected_date:
                    config["_preview_selected_date"] = selected_date
        elif self.current_section == "bible_verse":
            visibility.update(
                heatmap=False,
                today=False,
                remaining=False,
                buried=False,
                heatmap_metrics=False,
                bible=True,
            )
        return config

    def _render_preview(self) -> None:
        if self.current_section == "about" or not self.preview_wrap.isVisible():
            return
        self._sync_draft()
        config = self._contextual_preview_config()
        snapshot = self.controller.snapshot or sample_snapshot()
        selected_quote = self._selected_quote_index()
        if self.current_section == "bible_verse" and selected_quote is not None:
            snapshot = replace(snapshot, verse=verse_content(self.quotes[selected_quote]))
        labels = {
            "theme_layout": "Full dashboard preview",
            "home_screen": "Home screen metrics preview",
            "calendar_data": "Calendar preview",
            "events": "Selected date & event preview",
            "bible_verse": "Selected verse preview",
        }
        self.preview_label.setText(labels.get(self.current_section, "Contextual preview"))
        is_live = self.controller.snapshot is not None
        self.preview_data_badge.setText("Cached live snapshot" if is_live else "Sample data")
        self.preview_data_badge.setAccessibleDescription(
            "Using cached collection data without running collection queries."
            if is_live
            else "Using clearly marked sample data because no live dashboard snapshot exists."
        )
        package = mw.addonManager.addonFromModule(__name__)
        base = "/_addons/{}/web/".format(package)
        self.preview.stdHtml(
            render_dashboard(
                snapshot,
                config,
                anki_dark=self.controller.is_dark(),
                preview=True,
            ),
            css=[base + "dashboard.css"],
            js=[base + "dashboard.js"],
            context=self,
        )
        selected_date = config.get("_preview_selected_date")
        if isinstance(selected_date, str) and selected_date:
            script = """
setTimeout(function () {{
  var cell = document.querySelector('[data-date={}]');
  if (cell) {{ cell.click(); cell.scrollIntoView({{block: 'center', inline: 'center'}}); }}
}}, 180);
""".format(json.dumps(selected_date))
            QTimer.singleShot(220, lambda: self.preview.eval(script))

    def _selected_event(self) -> Optional[MutableMapping[str, Any]]:
        widget = self.active_events if self.event_tabs.currentIndex() == 0 else self.archived_events
        item = widget.currentItem()
        event_id = item.data(0, Qt.ItemDataRole.UserRole) if item else None
        for event in self.staged["events"]["items"]:
            if str(event.get("id")) == str(event_id): return event
        return None

    def _refresh_event_lists(self) -> None:
        self.active_events.clear(); self.archived_events.clear()
        needle = self.event_search.text().strip().casefold() if hasattr(self, "event_search") else ""
        reverse = _combo_value(self.event_sort, "ascending") == "descending" if hasattr(self, "event_sort") else False
        events = sorted(self.staged["events"]["items"], key=lambda item: (item["date"], item["name"].casefold()), reverse=reverse)
        for event in events:
            if needle and needle not in event["name"].casefold() and needle not in event["date"]: continue
            item = QTreeWidgetItem([_display_date(event["date"]), event["name"]])
            item.setData(0, Qt.ItemDataRole.UserRole, event["id"])
            item.setToolTip(0, "{} ({})".format(_display_date(event["date"]), event["date"]))
            item.setToolTip(1, event["name"])
            (self.archived_events if event.get("archived") else self.active_events).addTopLevelItem(item)
        self.event_tabs.setTabText(0, "Active ({})".format(self.active_events.topLevelItemCount()))
        self.event_tabs.setTabText(1, "Archived ({})".format(self.archived_events.topLevelItemCount()))
        if self.selected_event_date:
            self._select_event_date(self.selected_event_date)
        self._schedule_preview()
        self._update_event_actions()

    def _update_event_actions(self, *_args: object) -> None:
        archived = self.event_tabs.currentIndex() == 1
        selected_event = self._selected_event()
        selected = selected_event is not None
        self.event_edit.setEnabled(selected)
        self.event_archive.setEnabled(selected)
        self.event_delete.setEnabled(selected)
        self.event_archive.setText("Restore" if archived else "Archive")
        current_tree = self.archived_events if archived else self.active_events
        if current_tree.topLevelItemCount() == 0:
            kind = "archived" if archived else "active"
            qualifier = " matching this filter" if self.event_search.text().strip() else ""
            self.event_empty_state.setText("No {} events{}.".format(kind, qualifier))
            self.event_empty_state.show()
        else:
            self.event_empty_state.hide()
        if selected_event is None:
            self.event_selection_state.setText("Select an event to edit, archive, restore, or delete it.")
        else:
            self.event_selection_state.setText(
                "Selected: {} · {}".format(selected_event["name"], _display_date(selected_event["date"]))
            )
        self.event_archive.setAccessibleName(
            "Restore selected event" if archived else "Archive selected event"
        )
        self._schedule_preview()

    def _select_event_date(self, selected_date: str) -> None:
        self.selected_event_date = selected_date
        display_date = _display_date(selected_date)
        self.event_date_context.setText("Opened from Calendar · {}".format(display_date))
        self.event_date_context.show()
        self.event_add.setText("Add event for {}".format(display_date))
        self.event_add.setAccessibleName("Add event for {}".format(display_date))
        matching_id = None
        archived = False
        for event in self.staged["events"]["items"]:
            if event.get("date") == selected_date:
                matching_id = str(event.get("id"))
                archived = bool(event.get("archived"))
                break
        self.event_tabs.setCurrentIndex(1 if archived else 0)
        widget = self.archived_events if archived else self.active_events
        if matching_id is None:
            widget.clearSelection()
            return
        for row in range(widget.topLevelItemCount()):
            item = widget.topLevelItem(row)
            if str(item.data(0, Qt.ItemDataRole.UserRole)) == matching_id:
                widget.setCurrentItem(item)
                widget.scrollToItem(item)
                break

    def _add_event(self) -> None:
        dialog = EventEditDialog(self, initial_date=self.selected_event_date)
        if dialog.exec() != QDialog.DialogCode.Accepted: return
        name, event_date = dialog.values()
        self.selected_event_date = event_date
        self.staged["events"]["items"].append({"id": "event-{}".format(time.time_ns()), "name": name, "date": event_date, "archived": False, "created_at": datetime.now().astimezone().isoformat(timespec="seconds"), "archived_at": ""})
        self._refresh_event_lists()
        self._set_event_feedback("Added ‘{}’ for {}. Save to keep this change.".format(name, _display_date(event_date)))

    def _edit_event(self) -> None:
        event = self._selected_event()
        if event is None: return
        dialog = EventEditDialog(self, event)
        if dialog.exec() != QDialog.DialogCode.Accepted: return
        event["name"], event["date"] = dialog.values(); self._refresh_event_lists()
        self._set_event_feedback("Updated ‘{}’. Save to keep this change.".format(event["name"]))

    def _toggle_event_archive(self) -> None:
        event = self._selected_event()
        if event is None: return
        event["archived"] = not bool(event.get("archived")); event["archived_at"] = datetime.now().astimezone().isoformat(timespec="seconds") if event["archived"] else ""; self._refresh_event_lists()
        action = "Archived" if event["archived"] else "Restored"
        self._set_event_feedback("{} ‘{}’. Save to keep this change.".format(action, event["name"]))

    def _delete_event(self) -> None:
        event = self._selected_event()
        if event is None: return
        if QMessageBox.question(
            self,
            "Stage event deletion?",
            "Remove ‘{}’ from the staged event list? The deletion occurs only after you choose Save changes; Cancel keeps the saved event.".format(event["name"]),
        ) != QMessageBox.StandardButton.Yes:
            return
        name = event["name"]
        self.staged["events"]["items"].remove(event); self._refresh_event_lists()
        self._set_event_feedback("Deleted ‘{}’. Save to keep this change.".format(name))

    def _set_event_feedback(self, message: str) -> None:
        self.event_action_feedback.setText(message)
        self.event_action_feedback.setAccessibleDescription(message)

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
        if self.pending_manual_quote is not None and self.pending_manual_quote not in self.quotes:
            self.pending_manual_quote = None
            if not self._building:
                self._update_dirty_state()
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
        self._update_quote_actions()
        self._schedule_preview()

    def _update_quote_actions(self) -> None:
        selected = self._selected_quote_index() is not None
        under_limit = len(self.quotes) < 500
        self.quote_add.setEnabled(under_limit)
        self.quote_edit.setEnabled(selected)
        self.quote_duplicate.setEnabled(selected and under_limit)
        self.quote_delete.setEnabled(selected and len(self.quotes) > 1)
        self.quote_export.setEnabled(bool(self.quotes))
        manual = _combo_value(self.rotation, "daily") == "manual"
        if not manual and self.pending_manual_quote is not None:
            self.pending_manual_quote = None
            if not self._building:
                self._update_dirty_state()
        self.quote_use_current.setEnabled(selected and manual)
        if self.pending_manual_quote is not None:
            self.quote_current_feedback.setText("Selected verse will become current when you Save changes.")
        elif not manual:
            self.quote_current_feedback.setText("Choose manual rotation to set a specific current verse.")
        elif selected:
            self.quote_current_feedback.setText("Use the selected library verse as the current manual verse.")
        else:
            self.quote_current_feedback.setText("Select a verse to make it current.")

    def _stage_selected_manual_quote(self) -> None:
        index = self._selected_quote_index()
        if index is None or _combo_value(self.rotation, "daily") != "manual":
            return
        self.pending_manual_quote = self.quotes[index]
        self._update_quote_actions()
        self._sync_draft()

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
        if QMessageBox.question(
            self,
            "Stage verse deletion?",
            "Remove the selected verse from the staged library? The deletion occurs only after you choose Save changes; Cancel keeps the saved verse.",
        ) == QMessageBox.StandardButton.Yes:
            self.quotes.pop(index)
            self._refresh_quote_list()

    def _import_quotes(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Import Bible verses", "", "Verse files (*.json *.txt);;All files (*)")
        if not path: return
        try:
            text = Path(path).read_text(encoding="utf-8")
            if path.lower().endswith(".json"):
                parsed = json.loads(text); parsed = parsed.get("quotes", parsed.get("quote", [])) if isinstance(parsed, dict) else parsed
                values = list(parsed) if isinstance(parsed, list) else []
            else:
                values = text.split("\n\n")
        except (OSError, ValueError, TypeError) as exc:
            QMessageBox.critical(self, "Import failed", str(exc)); return
        self.quotes, summary = import_quotes(self.quotes, values, limit=500)
        self._refresh_quote_list()
        QMessageBox.information(
            self,
            "Verse import complete",
            "Imported {}. Skipped {} exact duplicate{}, {} empty entr{}, {} oversized entr{}, and {} at the 500-verse limit.".format(
                summary.imported,
                summary.duplicates,
                "" if summary.duplicates == 1 else "s",
                summary.empty,
                "y" if summary.empty == 1 else "ies",
                summary.oversized,
                "y" if summary.oversized == 1 else "ies",
                summary.limited,
            ),
        )

    def _export_quotes(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export Bible verses", "bible-verses.json", "JSON (*.json)")
        if not path: return
        try: Path(path).write_text(json.dumps({"quotes": self.quotes}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        except OSError as exc: QMessageBox.critical(self, "Export failed", str(exc))

    def _latest_stored_config(self) -> Mapping[str, Any]:
        try:
            raw = mw.addonManager.getConfig(self.controller.package)
        except Exception:
            raw = self.controller.config
        return raw if isinstance(raw, Mapping) else self.controller.config

    def _save(self) -> None:
        self._sync_draft()
        if not self.draft.dirty and self.pending_manual_quote is None:
            return
        original_baseline = deepcopy(self.draft.baseline)
        original_values = deepcopy(self.draft.values)
        latest = self._latest_stored_config()
        conflicts = self.draft.rebase(latest)
        if conflicts:
            names = "\n".join("• {}".format(conflict.label) for conflict in conflicts[:6])
            if len(conflicts) > 6:
                names += "\n• …and {} more".format(len(conflicts) - 6)
            message = QMessageBox(self)
            message.setIcon(QMessageBox.Icon.Warning)
            message.setWindowTitle("Settings changed elsewhere")
            message.setText("Some settings changed here and outside this editor.")
            message.setInformativeText(
                "Choose which value to use for these conflicts:\n\n{}\n\nUntouched external changes were merged automatically.".format(
                    names
                )
            )
            reload_button = message.addButton("Reload latest", QMessageBox.ButtonRole.ResetRole)
            keep_button = message.addButton(
                "Keep my staged value", QMessageBox.ButtonRole.AcceptRole
            )
            message.addButton(QMessageBox.StandardButton.Cancel)
            message.exec()
            clicked = message.clickedButton()
            if clicked is reload_button:
                self.draft.replace_all(latest)
                self.staged = deepcopy(self.draft.values)
                self.quotes = list(self.staged["bible"]["quotes"])
                self._apply_config_to_widgets(self.staged)
                self._update_dependencies()
                self._update_dirty_state()
                self._apply_theme()
                self._schedule_preview()
                return
            if clicked is not keep_button:
                self.draft.baseline = original_baseline
                self.draft.values = original_values
                self.staged = deepcopy(original_values)
                self._update_dirty_state()
                return
        self.controller.save_config(
            self.draft.values,
            preferred_verse=self.pending_manual_quote,
        )
        self._allow_close = True
        super().accept()

    def _confirm_discard(self) -> bool:
        self._sync_draft()
        if not self.draft.dirty and self.pending_manual_quote is None:
            return True
        answer = QMessageBox.question(
            self,
            "Discard unsaved changes?",
            "Your staged changes have not been applied. Discard them and close settings?",
            QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        return answer == QMessageBox.StandardButton.Discard

    def reject(self) -> None:
        if self._allow_close or self._confirm_discard():
            self._allow_close = True
            super().reject()

    def closeEvent(self, event: Any) -> None:
        if self._allow_close or self._confirm_discard():
            self._allow_close = True
            super().closeEvent(event)
        else:
            event.ignore()

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
    existing = getattr(mw, "_home_dashboard_overhaul_settings_action", None)
    if existing is not None: return
    menu_bar = getattr(getattr(mw, "form", None), "menubar", None)
    if menu_bar is None:
        getter = getattr(mw, "menuBar", None); menu_bar = getter() if callable(getter) else None
    if menu_bar is None: return
    submenu = _caleb_menu(menu_bar)
    for action in _actions(submenu):
        text = action.text() if callable(getattr(action, "text", None)) else ""
        if text == ACTION_TEXT: mw._home_dashboard_overhaul_settings_action = action; return
    action = QAction(ACTION_TEXT, mw)
    action.triggered.connect(controller.open_settings)
    submenu.addAction(action)
    mw._home_dashboard_overhaul_settings_action = action
