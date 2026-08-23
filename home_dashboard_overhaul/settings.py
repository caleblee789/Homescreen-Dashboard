"""Professional staged settings editor integrated into the Caleb M. menu."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import date, datetime
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
    QBoxLayout,
    QButtonGroup,
    QBrush,
    QCheckBox,
    QComboBox,
    QColor,
    QColorDialog,
    QDate,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QFontMetrics,
    QFontComboBox,
    QFormLayout,
    QGridLayout,
    QHeaderView,
    QHBoxLayout,
    QInputDialog,
    QKeySequence,
    QLabel,
    QLineEdit,
    QLocale,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPainter,
    QPlainTextEdit,
    QPoint,
    QPen,
    QPushButton,
    QEvent,
    QScrollArea,
    QSize,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QStyle,
    QStyledItemDelegate,
    QTabWidget,
    QTabBar,
    QTimer,
    QVBoxLayout,
    QWidget,
    QTreeWidget,
    QTreeWidgetItem,
    Qt,
)
from aqt.webview import AnkiWebView

from .analytics import representative_preview_snapshot
from .config_schema import normalize_config
from .renderer import render_dashboard
from .settings_model import (
    SECTION_LABELS,
    SettingsLayoutMetrics,
    SettingsDraft,
    font_family_value,
    history_range_choice,
    history_range_values,
    import_quotes,
    preview_snapshot_with_staged_events,
    resolve_section_target,
    settings_content_mode,
)
from .themes import DEFAULT_HEATMAP_PRESETS, HEATMAP_PRESETS, PRESETS, composite_color, resolve_theme
from .ui_primitives import (
    CONTENT_MODE_EXTRA_WIDE,
    CONTENT_MODE_INTERMEDIATE,
    CONTENT_MODE_NARROW,
    FOCUS_RING_OFFSET_PX,
    FOCUS_RING_PX,
    INTERACTION_TARGET_MIN_PX,
    SETTINGS_PRIMITIVES,
    VISUAL_CHROME_PX,
    normalize_content_mode,
)
from .verse import MAX_VERSE_BYTES, MAX_VERSE_CHARS, verse_content, verse_within_limit


CALEB_MENU_TITLE = "Caleb M. Add-ons Settings"
CALEB_MENU_OBJECT_NAME = "caleb_m_addons_menu"
ACTION_TEXT = "Home Screen Dashboard settings"
PROJECT_URL = "https://github.com/caleblee789/Homescreen-Dashboard"
ISSUES_URL = "https://github.com/caleblee789/Homescreen-Dashboard/issues"

SETTINGS_ROW_PRIMITIVE_ROLE = Qt.ItemDataRole.UserRole + 1
SETTINGS_ROW_TARGET_ROLE = Qt.ItemDataRole.UserRole + 2
SETTINGS_ROW_FOCUS_RING_ROLE = Qt.ItemDataRole.UserRole + 3
SETTINGS_ROW_FOCUS_OFFSET_ROLE = Qt.ItemDataRole.UserRole + 4
DECK_PATH_ROLE = Qt.ItemDataRole.UserRole + 10
DECK_FILTER_MATCH_ROLE = Qt.ItemDataRole.UserRole + 11
DECK_UNAVAILABLE_ROLE = Qt.ItemDataRole.UserRole + 12
EVENT_DATE_ROLE = Qt.ItemDataRole.UserRole + 20
EVENT_NAME_ROLE = Qt.ItemDataRole.UserRole + 21
EVENT_STATUS_ROLE = Qt.ItemDataRole.UserRole + 22


def _settings_primitive(name: str) -> str:
    if name not in SETTINGS_PRIMITIVES:
        raise ValueError("unknown Settings primitive: {}".format(name))
    return name


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
    semantic_fallback = resolve_theme(
        "Sapphire Glass",
        "dark" if dark else "light",
        dark,
    )
    highlight = brush_color("highlight", "text")
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
        "highlight": highlight,
        # Native highlightedText is commonly white even when Anki's active
        # accent is the pale #93C5FD blue.  Resolve the foreground from the
        # actual fill so every primary action remains contrast safe.
        "highlight_text": _foreground_for(highlight),
        "focus": semantic_fallback["focus"],
        "disabled": brush_color("placeholderText", "text"),
        "success": semantic_fallback["success"],
        "warning": semantic_fallback["warning"],
        "danger": semantic_fallback["danger"],
        "danger_bg": semantic_fallback["danger_soft"],
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
        "focus": theme["focus"],
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
    light = QColor(Qt.GlobalColor.white).name()
    dark = QColor(Qt.GlobalColor.black).name()
    return light if _color_contrast(light, background) >= _color_contrast(dark, background) else dark


def _settings_style(
    config: Optional[Mapping[str, Any]] = None,
    anki_dark: Optional[bool] = None,
) -> str:
    # Settings is application chrome. Dashboard presets affect only swatches
    # and previews, never the editor itself.
    values = _palette_tokens()
    values.update(
        visual_chrome=str(VISUAL_CHROME_PX),
        focus_ring=str(FOCUS_RING_PX),
        focus_offset=str(FOCUS_RING_OFFSET_PX),
    )
    return """
QDialog#HomeDashboardSettings {{ background: {window}; color: {text}; }}
QDialog#HomeDashboardSettings QLabel,
QDialog#HomeDashboardSettings QCheckBox {{ color: {text}; }}
QDialog#HomeDashboardSettings QListWidget#SettingsNav {{ background: transparent; border: 0; color: {text}; padding: 0; font-weight: 600; }}
QDialog#HomeDashboardSettings QListWidget#SettingsNav::item {{ border: 0; border-left: 3px solid transparent; border-radius: 6px; color: {text}; margin: 4px 0; min-height: 38px; padding: 0 11px; }}
QDialog#HomeDashboardSettings QListWidget#SettingsNav::item:selected {{ background: {alternate}; border-left-color: {highlight}; color: {text}; font-weight: 750; }}
QDialog#HomeDashboardSettings QListWidget#SettingsNav::item:focus {{ border: {focus_ring}px solid {focus}; }}
QDialog#HomeDashboardSettings QScrollArea {{ background: transparent; border: 0; }}
QDialog#HomeDashboardSettings QWidget#SettingsPage {{ background: transparent; border: 0; }}
QDialog#HomeDashboardSettings QWidget#SettingsCard {{ background: {alternate}; border: 1px solid {border}; border-radius: 10px; }}
QDialog#HomeDashboardSettings QWidget#SettingsHeader {{ background: {window}; border: 0; }}
QDialog#HomeDashboardSettings QLabel#PageTitle {{ font-size: 20px; font-weight: 750; color: {text}; }}
QDialog#HomeDashboardSettings[hdoContentMode="narrow"] QLabel#PageTitle {{ font-size: 18px; }}
QDialog#HomeDashboardSettings QLabel#CardTitle {{ font-size: 15px; font-weight: 750; color: {text}; }}
QDialog#HomeDashboardSettings QLabel#SectionTitle {{ color: {text}; font-size: 14px; font-weight: 750; padding-top: 10px; }}
QDialog#HomeDashboardSettings QLabel#PageHelp,
QDialog#HomeDashboardSettings QLabel#FieldHelp {{ color: {muted}; }}
QDialog#HomeDashboardSettings QWidget#SettingsRow {{ background: transparent; border: 0; }}
QDialog#HomeDashboardSettings QWidget#AboutDefinitionList {{ background: transparent; border: 0; }}
QDialog#HomeDashboardSettings QFrame#AboutDivider {{ color: {border}; }}
QDialog#HomeDashboardSettings QWidget#ActionBar {{ background: {base}; border-top: 1px solid {border}; border-radius: 0; }}
QDialog#HomeDashboardSettings QWidget#UndoToast {{ background: {alternate}; border: 1px solid {highlight}; border-radius: 8px; }}
QDialog#HomeDashboardSettings QWidget#SettingsSectionSelector,
QDialog#HomeDashboardSettings QWidget#ContextualActionGroup {{ background: transparent; border: 0; }}
QDialog#HomeDashboardSettings QLabel#DirtyBadge {{ background: {alternate}; border: 1px solid {border}; border-radius: 9px; color: {muted}; font-size: 12px; font-weight: 700; padding: 3px 7px; }}
QDialog#HomeDashboardSettings QLabel#DirtyBadge[state="dirty"] {{ color: {warning}; }}
QDialog#HomeDashboardSettings QLabel#DirtyBadge[state="saved"] {{ color: {success}; }}
QDialog#HomeDashboardSettings QLabel#DirtyBadge[state="error"] {{ color: {danger}; }}
QDialog#HomeDashboardSettings QLabel#DataBadge {{ background: {alternate}; border-radius: 8px; color: {text}; font-weight: 650; padding: 3px 7px; }}
QDialog#HomeDashboardSettings QPushButton#HeatmapPresetCard {{ background: {base}; border: 1px solid {border}; border-radius: 9px; margin: 0; min-height: 64px; padding: 7px 9px; text-align: left; }}
QDialog#HomeDashboardSettings QPushButton#HeatmapPresetCard[active="true"] {{ background: {alternate}; border: 2px solid {highlight}; color: {text}; }}
QDialog#HomeDashboardSettings QWidget#SegmentedControl {{ background: {alternate}; border: 1px solid {border}; border-radius: 8px; }}
QDialog#HomeDashboardSettings QPushButton#SegmentButton {{ background: transparent; border: 0; border-radius: 6px; margin: 2px; min-height: 32px; padding: 0 12px; }}
QDialog#HomeDashboardSettings QPushButton#SegmentButton:checked {{ background: {highlight}; border: 0; color: {highlight_text}; font-weight: 700; }}
QDialog#HomeDashboardSettings QPushButton#SegmentButton:focus {{ border: 2px solid {focus}; margin: 0; }}
QDialog#HomeDashboardSettings QPushButton#SettingsSwitch {{ background: transparent; border: 0; margin: 0; min-height: 32px; min-width: 44px; max-height: 32px; max-width: 44px; padding: 0; }}
QDialog#HomeDashboardSettings QPushButton#LinkButton {{ background: transparent; border: 0; color: {highlight}; min-height: 30px; padding: 0 4px; }}
QDialog#HomeDashboardSettings QLineEdit,
QDialog#HomeDashboardSettings QComboBox,
QDialog#HomeDashboardSettings QSpinBox,
QDialog#HomeDashboardSettings QDoubleSpinBox,
QDialog#HomeDashboardSettings QDateEdit {{
  background: {base}; border: 1px solid {border}; border-radius: 7px; color: {text}; min-height: {visual_chrome}px; margin: {focus_offset}px 0; padding: 0 7px;
}}
QDialog#HomeDashboardSettings QPlainTextEdit,
QDialog#HomeDashboardSettings QListWidget#ManagerList,
QDialog#HomeDashboardSettings QTreeWidget#ManagerTree {{
  background: {base}; border: 1px solid {border}; border-radius: 7px; color: {text}; padding: 3px;
}}
QDialog#HomeDashboardSettings QLineEdit:focus,
QDialog#HomeDashboardSettings QComboBox:focus,
QDialog#HomeDashboardSettings QSpinBox:focus,
QDialog#HomeDashboardSettings QDoubleSpinBox:focus,
QDialog#HomeDashboardSettings QDateEdit:focus,
QDialog#HomeDashboardSettings QPlainTextEdit:focus,
QDialog#HomeDashboardSettings QListWidget#ManagerList:focus,
QDialog#HomeDashboardSettings QTreeWidget#ManagerTree:focus {{ border: {focus_ring}px solid {focus}; }}
QDialog#HomeDashboardSettings QComboBox QAbstractItemView,
QDialog#HomeDashboardSettings QTreeWidget#ManagerTree::item {{ background: {base}; border-bottom: 1px solid {alternate}; color: {text}; padding: 4px 5px; }}
QDialog#HomeDashboardSettings QTreeWidget#ManagerTree QHeaderView::section {{ background: {alternate}; border: 0; border-bottom: 1px solid {border}; color: {text}; font-weight: 700; padding: 4px 6px; }}
QDialog#HomeDashboardSettings QComboBox QAbstractItemView {{ selection-background-color: {highlight}; selection-color: {highlight_text}; }}
QDialog#HomeDashboardSettings QComboBox::drop-down {{ border: 0; width: 24px; }}
QDialog#HomeDashboardSettings QComboBox::down-arrow {{ image: none; height: 0; width: 0; }}
QDialog#HomeDashboardSettings QSpinBox::up-button,
QDialog#HomeDashboardSettings QSpinBox::down-button {{ width: 30px; }}
QDialog#HomeDashboardSettings QTreeWidget#ManagerTree::item:selected {{ background: {highlight}; color: {highlight_text}; }}
QDialog#HomeDashboardSettings QTreeWidget#ManagerTree[narrowCards="true"] {{ background: transparent; border: 0; padding: 0; }}
QDialog#HomeDashboardSettings QTreeWidget#ManagerTree[narrowCards="true"]::item {{ background: {alternate}; border: 1px solid {border}; border-radius: 7px; margin: 3px 0; padding: 7px 9px; }}
QDialog#HomeDashboardSettings QCheckBox {{ min-height: {visual_chrome}px; margin: {focus_offset}px 0; }}
QDialog#HomeDashboardSettings QCheckBox:focus {{ border: {focus_ring}px solid {focus}; border-radius: 6px; }}
QDialog#HomeDashboardSettings QSlider:focus {{ border: {focus_ring}px solid {focus}; border-radius: 6px; }}
QDialog#HomeDashboardSettings QSlider::groove:horizontal {{ background: {alternate}; border: 1px solid {border}; border-radius: 3px; height: 5px; }}
QDialog#HomeDashboardSettings QSlider::handle:horizontal {{ background: {highlight}; border: 2px solid {base}; border-radius: 8px; height: 14px; margin: -6px 0; width: 14px; }}
QDialog#HomeDashboardSettings QPushButton {{ background: {button}; border: 1px solid {border}; border-radius: 7px; color: {button_text}; min-height: {visual_chrome}px; margin: {focus_offset}px 0; padding: 0 10px; }}
QDialog#HomeDashboardSettings QPushButton:hover {{ border-color: {highlight}; background: {alternate}; }}
QDialog#HomeDashboardSettings QPushButton:focus {{ border: {focus_ring}px solid {focus}; }}
QDialog#HomeDashboardSettings QPushButton#PrimaryButton {{ background: {highlight}; border-color: {highlight}; color: {highlight_text}; font-weight: 750; }}
QDialog#HomeDashboardSettings QPushButton#PrimaryButton:disabled {{ background: {alternate}; border-color: {border}; color: {disabled}; }}
QDialog#HomeDashboardSettings QPushButton#DangerButton {{ background: {danger_bg}; border-color: {danger}; color: {danger}; font-weight: 650; }}
QDialog#HomeDashboardSettings QPushButton#DangerButton:disabled {{ background: {alternate}; border-color: {border}; color: {disabled}; }}
QDialog#HomeDashboardSettings QWidget#EmptyState {{ background: transparent; border: 0; }}
QDialog#HomeDashboardSettings QLabel#EmptyStateTitle {{ color: {text}; font-size: 17px; font-weight: 750; }}
QDialog#HomeDashboardSettings QLabel#EmptyStateCopy {{ color: {muted}; }}
QDialog#HomeDashboardSettings QLabel#EmptyState {{ background: {alternate}; border: 1px solid {border}; border-radius: 7px; color: {text}; padding: 8px 10px; }}
QDialog#HomeDashboardSettings QLabel#SelectedVerseCard {{ background: {base}; border: 1px solid {border}; border-radius: 9px; color: {text}; padding: 11px 12px; }}
QDialog#HomeDashboardSettings QPushButton#DisclosureButton {{ background: transparent; border: 0; border-top: 1px solid {border}; border-radius: 0; color: {text}; font-weight: 650; min-height: 38px; padding: 0 2px; text-align: left; }}
QDialog#HomeDashboardSettings QTabWidget::pane {{ border: 1px solid {border}; border-radius: 8px; background: {base}; }}
QDialog#HomeDashboardSettings QTabBar#SettingsTabs {{ background: transparent; }}
QDialog#HomeDashboardSettings QTabBar::tab {{ background: {alternate}; color: {text}; border: 1px solid {border}; margin: {focus_offset}px; padding: 7px 14px; }}
QDialog#HomeDashboardSettings QTabBar::tab:selected {{ background: {alternate}; border-bottom: 3px solid {highlight}; color: {text}; font-weight: 700; }}
QDialog#HomeDashboardSettings QTabBar::tab:focus {{ border: {focus_ring}px solid {focus}; }}
QDialog#HomeDashboardSettings QWidget:disabled,
QDialog#HomeDashboardSettings QPushButton:disabled {{ background: {alternate}; color: {disabled}; border-color: {border}; }}
""".format(**values)


def _editor_style(tokens: Optional[Mapping[str, str]] = None) -> str:
    values = dict(tokens) if isinstance(tokens, Mapping) else _palette_tokens()
    values.update(
        visual_chrome=str(VISUAL_CHROME_PX),
        focus_ring=str(FOCUS_RING_PX),
        focus_offset=str(FOCUS_RING_OFFSET_PX),
    )
    return """
QDialog#HomeDashboardEditor {{ background: {window}; color: {text}; }}
QDialog#HomeDashboardEditor QLabel {{ color: {text}; }}
QDialog#HomeDashboardEditor QLabel#EditorHelp {{ color: {muted}; }}
QDialog#HomeDashboardEditor QLabel#PageTitle {{ color: {text}; font-size: 18px; font-weight: 750; }}
QDialog#HomeDashboardEditor QLineEdit,
QDialog#HomeDashboardEditor QDateEdit {{ background: {base}; border: 1px solid {border}; border-radius: 7px; color: {text}; min-height: {visual_chrome}px; margin: {focus_offset}px 0; padding: 0 7px; }}
QDialog#HomeDashboardEditor QPlainTextEdit {{ background: {base}; border: 1px solid {border}; border-radius: 7px; color: {text}; padding: 5px 7px; }}
QDialog#HomeDashboardEditor QLineEdit:focus,
QDialog#HomeDashboardEditor QDateEdit:focus,
QDialog#HomeDashboardEditor QPlainTextEdit:focus {{ border: {focus_ring}px solid {focus}; }}
QDialog#HomeDashboardEditor QPushButton {{ background: {button}; border: 1px solid {border}; border-radius: 7px; color: {button_text}; min-height: {visual_chrome}px; margin: {focus_offset}px 0; padding: 0 11px; }}
QDialog#HomeDashboardEditor QPushButton:focus {{ border: {focus_ring}px solid {focus}; }}
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
    layout.setContentsMargins(2, 2, 8, 20)
    layout.setSpacing(10)
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
    form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
    # Kept for compatibility with the manager pages. Dashboard and Bible use
    # explicit cards instead of placing controls in this root form.
    layout.addLayout(form)
    return page, layout, form


def _section_title(value: str) -> QLabel:
    label = QLabel(value)
    label.setObjectName("SectionTitle")
    return label


class WrappingFieldLabel(QWidget):
    """Two-line form label whose height tracks its assigned column width."""

    def __init__(self, title: str, description: str) -> None:
        super().__init__()
        self._name = QLabel(title)
        self._name.setWordWrap(True)
        self._name.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self._help: Optional[QLabel] = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.addWidget(self._name)
        if description:
            self._help = QLabel(description)
            self._help.setObjectName("FieldHelp")
            self._help.setWordWrap(True)
            self._help.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
            layout.addWidget(self._help)
        policy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)
        # QFormLayout can query a compound label before assigning its final
        # column width.  Seed a safe two-column height, then keep it exact as
        # the responsive form changes width.
        self._sync_minimum_height(220)

    @staticmethod
    def _label_height(label: QLabel, width: int) -> int:
        measured = label.heightForWidth(max(1, width))
        return measured if measured > 0 else label.sizeHint().height()

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        height = self._label_height(self._name, width)
        if self._help is not None:
            height += 2 + self._label_height(self._help, width)
        return height

    def sizeHint(self) -> QSize:
        width = min(
            330,
            max(
                220,
                self._name.sizeHint().width(),
                self._help.sizeHint().width() if self._help is not None else 0,
            ),
        )
        return QSize(width, self.heightForWidth(width))

    def minimumSizeHint(self) -> QSize:
        width = 180
        return QSize(width, self.heightForWidth(width))

    def _sync_minimum_height(self, width: int) -> None:
        target = self.heightForWidth(max(1, width))
        # QFormLayout may briefly assign a generous label width, then narrow
        # it after sizing the field column. Never collapse the conservative
        # first-pass height: doing so can clip the final wrapped help line.
        if self.minimumHeight() < target:
            self.setMinimumHeight(target)
            self.updateGeometry()

    def resizeEvent(self, event: Any) -> None:
        self._sync_minimum_height(event.size().width())
        super().resizeEvent(event)

    def changeEvent(self, event: Any) -> None:
        if event.type() in {
            getattr(QEvent.Type, "FontChange", None),
            getattr(QEvent.Type, "StyleChange", None),
        }:
            QTimer.singleShot(0, lambda: self._sync_minimum_height(self.width()))
        super().changeEvent(event)


def _field_label(title: str, description: str = "") -> QWidget:
    return WrappingFieldLabel(title, description)


def _stacked_field(title: str, description: str, field: QWidget) -> QWidget:
    """Build a full-width field for controls that should never be squeezed."""

    wrap = QWidget()
    wrap.setObjectName("SettingsRow")
    layout = QVBoxLayout(wrap)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(6)
    layout.addWidget(_field_label(title, description))
    layout.addWidget(field)
    return wrap


def _description_checkbox(title: str, description: str, checked: bool) -> tuple[QWidget, QCheckBox]:
    """Return a compact, wrapping setting row without card-like chrome."""

    wrap = QWidget()
    wrap.setObjectName("SettingsRow")
    layout = QVBoxLayout(wrap)
    layout.setContentsMargins(0, 0, 0, 4)
    layout.setSpacing(1)
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
    slider.setMaximumWidth(660)
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


class SelectChevron(QWidget):
    """Font-independent vector chevron overlaid on a native combo box."""

    def __init__(self, combo: QComboBox) -> None:
        super().__init__(combo)
        self.combo = combo
        self.setObjectName("SelectChevron")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        combo.installEventFilter(self)
        self._place()
        self.show()
        self.raise_()

    def _place(self) -> None:
        size = 16
        right = 10
        self.setGeometry(
            max(0, self.combo.width() - right - size),
            max(0, (self.combo.height() - size) // 2),
            size,
            size,
        )

    def eventFilter(self, watched: object, event: Any) -> bool:
        if watched is self.combo and event.type() in {
            getattr(QEvent.Type, "Resize", None),
            getattr(QEvent.Type, "Show", None),
            getattr(QEvent.Type, "FontChange", None),
            getattr(QEvent.Type, "PaletteChange", None),
            getattr(QEvent.Type, "StyleChange", None),
        }:
            self._place()
            self.raise_()
            self.update()
        return False

    def paintEvent(self, event: Any) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pen = QPen(QColor(_palette_tokens()["text"]))
        pen.setWidthF(1.8)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.drawLine(3, 6, 8, 11)
        painter.drawLine(8, 11, 13, 6)


def _install_select_chevron(combo: QComboBox) -> None:
    if getattr(combo, "_hdo_select_chevron", None) is None:
        combo._hdo_select_chevron = SelectChevron(combo)


class SegmentButton(QPushButton):
    """One segment with radio-style arrow-key navigation."""

    def __init__(self, label: str, owner: "SegmentedControl") -> None:
        super().__init__(label, owner)
        self.owner = owner

    def keyPressEvent(self, event: Any) -> None:
        key = event.key()
        if key in {
            Qt.Key.Key_Left,
            Qt.Key.Key_Up,
            Qt.Key.Key_Right,
            Qt.Key.Key_Down,
        }:
            offset = -1 if key in {Qt.Key.Key_Left, Qt.Key.Key_Up} else 1
            self.owner.move_selection(self, offset)
            event.accept()
            return
        super().keyPressEvent(event)


class SegmentedControl(QWidget):
    """Native, keyboard-operable mutually exclusive choice group."""

    def __init__(
        self,
        options: List[tuple[str, str]],
        current: str,
        accessible_name: str,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("SegmentedControl")
        self.setAccessibleName(accessible_name)
        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)
        self._buttons: Dict[str, QPushButton] = {}
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        for label, value in options:
            button = SegmentButton(label, self)
            button.setObjectName("SegmentButton")
            button.setCheckable(True)
            button.setProperty("hdoValue", value)
            button.setAccessibleName("{}: {}".format(accessible_name, label))
            self.button_group.addButton(button)
            self._buttons[value] = button
            layout.addWidget(button, 1)
        self.setValue(current)

    def value(self, fallback: str = "") -> str:
        checked = self.button_group.checkedButton()
        value = checked.property("hdoValue") if checked is not None else fallback
        return value if isinstance(value, str) else fallback

    def setValue(self, value: object) -> None:
        button = self._buttons.get(str(value))
        if button is None and self._buttons:
            button = next(iter(self._buttons.values()))
        if button is not None:
            button.setChecked(True)

    def connect_changed(self, callback: Callable[..., None]) -> None:
        self.button_group.buttonClicked.connect(callback)

    def move_selection(self, current: QPushButton, offset: int) -> None:
        buttons = list(self._buttons.values())
        if current not in buttons or not buttons:
            return
        index = buttons.index(current)
        for step in range(1, len(buttons) + 1):
            candidate = buttons[(index + (offset * step)) % len(buttons)]
            if candidate.isEnabled() and candidate.isVisible():
                candidate.setFocus(Qt.FocusReason.TabFocusReason)
                candidate.click()
                return


class SettingsSwitch(QPushButton):
    """Compact accessible switch with a visible positional knob."""

    def __init__(self, checked: bool, parent: Optional[QWidget] = None) -> None:
        super().__init__("", parent)
        self.setObjectName("SettingsSwitch")
        self.setCheckable(True)
        self.setChecked(checked)
        self.setFixedSize(44, 32)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggled.connect(lambda _state: self.update())

    def paintEvent(self, event: Any) -> None:
        del event
        tokens = _palette_tokens()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if not self.isEnabled():
            track = QColor(tokens["alternate"])
            border = QColor(tokens["border"])
            knob = QColor(tokens["disabled"])
        else:
            track = QColor(tokens["highlight"] if self.isChecked() else tokens["alternate"])
            border = QColor(tokens["highlight"] if self.isChecked() else tokens["border"])
            knob = QColor(tokens["highlight_text"] if self.isChecked() else tokens["text"])
        painter.setPen(QPen(border, 1.2))
        painter.setBrush(QBrush(track))
        painter.drawRoundedRect(2, 4, 40, 24, 12, 12)
        painter.setPen(QPen(Qt.PenStyle.NoPen))
        painter.setBrush(QBrush(knob))
        knob_x = 22 if self.isChecked() else 6
        painter.drawEllipse(knob_x, 8, 16, 16)
        if self.hasFocus():
            focus_pen = QPen(QColor(tokens["focus"]), FOCUS_RING_PX)
            painter.setPen(focus_pen)
            painter.setBrush(QBrush(Qt.BrushStyle.NoBrush))
            painter.drawRoundedRect(1, 1, 42, 30, 8, 8)


class SettingsCard(QWidget):
    """Quiet bordered Settings group with an optional scoped reset action."""

    def __init__(
        self,
        title: str,
        description: str = "",
        reset_text: str = "",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("SettingsCard")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        self.outer = QVBoxLayout(self)
        self.outer.setContentsMargins(16, 14, 16, 16)
        self.outer.setSpacing(10)
        header = QHBoxLayout()
        self.heading = QLabel(title)
        self.heading.setObjectName("CardTitle")
        self.heading.setAccessibleName(title)
        self.heading.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        header.addWidget(self.heading)
        header.addStretch()
        self.reset_button: Optional[QPushButton] = None
        if reset_text:
            self.reset_button = QPushButton(reset_text)
            self.reset_button.setObjectName("LinkButton")
            self.reset_button.setAccessibleName(reset_text)
            header.addWidget(self.reset_button)
        self.outer.addLayout(header)
        if description:
            help_label = QLabel(description)
            help_label.setObjectName("PageHelp")
            help_label.setWordWrap(True)
            self.outer.addWidget(help_label)

    def add_widget(self, widget: QWidget, stretch: int = 0) -> None:
        self.outer.addWidget(widget, stretch)

    def add_layout(self, layout: Any) -> None:
        self.outer.addLayout(layout)

    def add_form(self) -> QFormLayout:
        form = QFormLayout()
        form.setVerticalSpacing(10)
        form.setHorizontalSpacing(18)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.outer.addLayout(form)
        return form


def _switch_row(
    title: str,
    description: str,
    checked: bool,
) -> tuple[QWidget, SettingsSwitch]:
    row = QWidget()
    row.setObjectName("SettingsRow")
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 2, 0, 2)
    layout.setSpacing(12)
    copy = QVBoxLayout()
    copy.setSpacing(2)
    name = QLabel(title)
    help_label = QLabel(description)
    help_label.setObjectName("FieldHelp")
    help_label.setWordWrap(True)
    copy.addWidget(name)
    copy.addWidget(help_label)
    switch = SettingsSwitch(checked)
    switch.setAccessibleName(title)
    switch.setAccessibleDescription(description)
    switch.setToolTip("On" if checked else "Off")
    switch.toggled.connect(lambda state: switch.setToolTip("On" if state else "Off"))
    layout.addLayout(copy, 1)
    layout.addWidget(switch, 0, Qt.AlignmentFlag.AlignVCenter)
    return row, switch


def _info_button(title: str, text: str) -> QPushButton:
    button = QPushButton("ⓘ")
    button.setObjectName("LinkButton")
    button.setToolTip(text)
    button.setAccessibleName(title)
    button.setAccessibleDescription(text)
    button.setFixedWidth(34)
    return button


def _form_control(widget: QWidget) -> QWidget:
    """Mark a native field as the shared compact-control primitive."""
    widget.setProperty("hdoPrimitive", _settings_primitive("form-control"))
    widget.setProperty("hdoFocusRingWidth", FOCUS_RING_PX)
    widget.setProperty("hdoFocusRingOffset", FOCUS_RING_OFFSET_PX)
    if isinstance(widget, QComboBox):
        _install_select_chevron(widget)
    if isinstance(widget, SettingsSwitch):
        return widget
    target = max(40, INTERACTION_TARGET_MIN_PX, widget.fontMetrics().lineSpacing() + 12)
    widget.setMinimumHeight(target)
    return widget


def _row_target_height(view: QAbstractItemView) -> int:
    return max(INTERACTION_TARGET_MIN_PX, view.fontMetrics().lineSpacing() + 12)


class SettingsRowDelegate(QStyledItemDelegate):
    """Give managed rows a usable target and a deterministic focus ring."""

    def __init__(self, parent: QAbstractItemView) -> None:
        super().__init__(parent)
        self.setProperty("hdoRowTargetMin", INTERACTION_TARGET_MIN_PX)
        self.setProperty("hdoFocusRingWidth", FOCUS_RING_PX)
        self.setProperty("hdoFocusRingOffset", FOCUS_RING_OFFSET_PX)
        self.setProperty("hdoLastFocusPaintRow", -1)
        self.setProperty("hdoLastFocusPaintColumn", -1)

    def sizeHint(self, option: Any, index: Any) -> QSize:
        hint = super().sizeHint(option, index)
        target = max(
            INTERACTION_TARGET_MIN_PX,
            option.fontMetrics.lineSpacing() + 12,
        )
        return QSize(max(0, hint.width()), max(target, hint.height()))

    def paint(self, painter: Any, option: Any, index: Any) -> None:
        super().paint(painter, option, index)
        option_has_focus = bool(option.state & QStyle.StateFlag.State_HasFocus)
        view = self.parent()
        current_index = (
            view.currentIndex() if isinstance(view, QAbstractItemView) else None
        )
        # QListWidget may omit State_HasFocus from the delegate option even
        # while its view owns focus.  Match the complete model index so the
        # fallback never decorates another row or column.
        view_has_current_focus = bool(
            isinstance(view, QAbstractItemView)
            and view.hasFocus()
            and index.isValid()
            and current_index is not None
            and current_index.isValid()
            and index == current_index
        )
        if not (option_has_focus or view_has_current_focus):
            return
        self.setProperty("hdoLastFocusPaintRow", int(index.row()))
        self.setProperty("hdoLastFocusPaintColumn", int(index.column()))
        painter.save()
        focus_color = _editor_tokens(view)["focus"]
        pen = QPen(QColor(focus_color))
        pen.setWidth(FOCUS_RING_PX)
        painter.setPen(pen)
        painter.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        inset = FOCUS_RING_OFFSET_PX + ((FOCUS_RING_PX + 1) // 2)
        focus_rect = option.rect.adjusted(inset, inset, -inset, -inset)
        if focus_rect.isValid():
            painter.drawRoundedRect(focus_rect, 4.0, 4.0)
        painter.restore()


def _install_settings_row_delegate(view: QAbstractItemView) -> None:
    delegate = SettingsRowDelegate(view)
    view.setItemDelegate(delegate)
    view.setProperty("hdoRowTargetMin", INTERACTION_TARGET_MIN_PX)
    view.setProperty("hdoFocusRingWidth", FOCUS_RING_PX)
    view.setProperty("hdoFocusRingOffset", FOCUS_RING_OFFSET_PX)
    view.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    if isinstance(view, QTreeWidget):
        view.setUniformRowHeights(True)


def _apply_view_row_targets(view: QAbstractItemView) -> None:
    if not isinstance(view.itemDelegate(), SettingsRowDelegate):
        return
    target = _row_target_height(view)
    view.setProperty("hdoRowTargetHeight", target)
    if isinstance(view, QListWidget):
        for row in range(view.count()):
            item = view.item(row)
            if item.data(SETTINGS_ROW_PRIMITIVE_ROLE) != "list-or-table-row":
                continue
            item.setData(SETTINGS_ROW_TARGET_ROLE, target)
            width = (
                view.fontMetrics().horizontalAdvance(item.text())
                + (2 * view.fontMetrics().lineSpacing())
            )
            item.setSizeHint(QSize(max(1, width), target))
    elif isinstance(view, QTreeWidget):
        pending = [
            view.topLevelItem(row)
            for row in range(view.topLevelItemCount())
        ]
        while pending:
            item = pending.pop()
            if item.data(0, SETTINGS_ROW_PRIMITIVE_ROLE) == "list-or-table-row":
                item.setData(0, SETTINGS_ROW_TARGET_ROLE, target)
                for column in range(view.columnCount()):
                    width = (
                        view.fontMetrics().horizontalAdvance(item.text(column))
                        + (2 * view.fontMetrics().lineSpacing())
                    )
                    item.setSizeHint(column, QSize(max(1, width), target))
            pending.extend(
                item.child(row) for row in range(item.childCount())
            )
    view.doItemsLayout()


def _apply_item_row_targets(root: QWidget) -> None:
    """Refresh explicit item hints after a live application-font change."""

    for view in root.findChildren(QAbstractItemView):
        _apply_view_row_targets(view)


def _apply_control_targets(root: QWidget) -> None:
    """Recompute usable targets after application-font or theme changes."""
    control_types = (QPushButton, QCheckBox, QLineEdit, QComboBox, QSpinBox, QDateEdit, QSlider)
    for widget in root.findChildren(QWidget):
        if isinstance(widget, control_types):
            _form_control(widget)
    _apply_item_row_targets(root)


def _set_accessibility(widget: QWidget, name: str, description: str = "") -> None:
    _form_control(widget)
    widget.setAccessibleName(name)
    if description:
        widget.setAccessibleDescription(description)


class SettingsSidebar(QListWidget):
    """Shared section rail whose width follows its live label metrics."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setProperty("hdoPrimitive", _settings_primitive("settings-sidebar"))
        self.setObjectName("SettingsNav")
        self.setAccessibleName("Settings sections")
        self.setAccessibleDescription("Choose a Home Screen Dashboard settings section")
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Maximum)

    def measured_width(self) -> int:
        font_metrics = self.fontMetrics()
        content = max(
            self.sizeHintForColumn(0),
            font_metrics.horizontalAdvance("About & support"),
            font_metrics.horizontalAdvance("Bible verse"),
        )
        return max(INTERACTION_TARGET_MIN_PX * 4, content + (2 * font_metrics.lineSpacing()))


class SettingsSectionSelector(QWidget):
    """Shared labeled selector kept outside the scrolling settings body."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setProperty("hdoPrimitive", _settings_primitive("settings-section-selector"))
        self.setObjectName("SettingsSectionSelector")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.label = QLabel("Section")
        self.combo = QComboBox()
        _set_accessibility(
            self.combo,
            "Settings section",
            "Choose which Home Screen Dashboard settings section to edit.",
        )
        layout.addWidget(self.label)
        layout.addWidget(self.combo, 1)


class SettingsFooter(QWidget):
    """Normal-grid action footer; it never overlays the scrolling content."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setProperty("hdoPrimitive", _settings_primitive("settings-footer"))
        self.setObjectName("ActionBar")
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(9, 7, 9, 7)
        self.grid.setHorizontalSpacing(8)
        self.grid.setVerticalSpacing(4)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        self.grid.addWidget(self.buttons, 0, 1, Qt.AlignmentFlag.AlignRight)
        self.grid.setColumnStretch(0, 1)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(60)

    def inline_width_hint(self) -> int:
        margins = self.grid.contentsMargins()
        return margins.left() + margins.right() + self.buttons.sizeHint().width()

    def set_mode(self, mode: str, available_width: int = 0) -> None:
        mode = normalize_content_mode(mode)
        self.setProperty("hdoContentMode", mode)
        self.style().unpolish(self)
        self.style().polish(self)
        self.setFixedHeight(66 if mode == CONTENT_MODE_NARROW else 60)
        for button in self.buttons.buttons():
            button.setMinimumHeight(44 if mode == CONTENT_MODE_NARROW else 40)


class SettingsListRow(QListWidgetItem):
    """Shared safe-text list row for deck and verse management."""

    def __init__(
        self,
        text: str,
        identity: object = None,
        tooltip: str = "",
    ) -> None:
        super().__init__(str(text))
        application = QApplication.instance()
        metrics = QFontMetrics(application.font()) if application is not None else None
        target = max(
            INTERACTION_TARGET_MIN_PX,
            metrics.lineSpacing() + 12 if metrics is not None else 0,
        )
        width = (
            metrics.horizontalAdvance(str(text)) + (2 * metrics.lineSpacing())
            if metrics is not None
            else 1
        )
        self.setData(SETTINGS_ROW_PRIMITIVE_ROLE, _settings_primitive("list-or-table-row"))
        self.setData(SETTINGS_ROW_TARGET_ROLE, target)
        self.setData(SETTINGS_ROW_FOCUS_RING_ROLE, FOCUS_RING_PX)
        self.setData(SETTINGS_ROW_FOCUS_OFFSET_ROLE, FOCUS_RING_OFFSET_PX)
        self.setSizeHint(QSize(max(1, width), target))
        if identity is not None:
            self.setData(Qt.ItemDataRole.UserRole, identity)
        if tooltip:
            self.setToolTip(tooltip)


class SettingsTableRow(QTreeWidgetItem):
    """Shared safe-text table row with a stable, non-visible identity."""

    def __init__(
        self,
        values: List[str],
        identity: object = None,
        tooltips: Optional[List[str]] = None,
    ) -> None:
        super().__init__([str(value) for value in values])
        application = QApplication.instance()
        metrics = QFontMetrics(application.font()) if application is not None else None
        target = max(
            INTERACTION_TARGET_MIN_PX,
            metrics.lineSpacing() + 12 if metrics is not None else 0,
        )
        self.setData(0, SETTINGS_ROW_PRIMITIVE_ROLE, _settings_primitive("list-or-table-row"))
        self.setData(0, SETTINGS_ROW_TARGET_ROLE, target)
        self.setData(0, SETTINGS_ROW_FOCUS_RING_ROLE, FOCUS_RING_PX)
        self.setData(0, SETTINGS_ROW_FOCUS_OFFSET_ROLE, FOCUS_RING_OFFSET_PX)
        for column, value in enumerate(values):
            width = (
                metrics.horizontalAdvance(str(value)) + (2 * metrics.lineSpacing())
                if metrics is not None
                else 1
            )
            self.setSizeHint(column, QSize(max(1, width), target))
        if identity is not None:
            self.setData(0, Qt.ItemDataRole.UserRole, identity)
        for column, tooltip in enumerate(tooltips or []):
            if tooltip:
                self.setToolTip(column, tooltip)


class ContextualActionGroup(QWidget):
    """Reusable action group that stacks when content is effectively narrow."""

    def __init__(
        self,
        direction: QBoxLayout.Direction = QBoxLayout.Direction.LeftToRight,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("ContextualActionGroup")
        self.setProperty(
            "hdoPrimitive",
            _settings_primitive("contextual-action-group"),
        )
        self._preferred_direction = direction
        self.box = QBoxLayout(direction, self)
        self.box.setContentsMargins(0, 0, 0, 0)
        self.box.setSpacing(6)

    def add_widget(self, widget: QWidget, stretch: int = 0) -> None:
        self.box.addWidget(widget, stretch)

    def add_stretch(self) -> None:
        self.box.addStretch()

    def set_mode(self, mode: str) -> None:
        mode = normalize_content_mode(mode)
        direction = (
            QBoxLayout.Direction.TopToBottom
            if mode == CONTENT_MODE_NARROW
            else self._preferred_direction
        )
        self.box.setDirection(direction)


class WrappingActionGroup(QWidget):
    """Horizontal actions that wrap to a second row at minimum width."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("ContextualActionGroup")
        self.setProperty(
            "hdoPrimitive",
            _settings_primitive("contextual-action-group"),
        )
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(6)
        self.grid.setVerticalSpacing(6)
        self.widgets: List[QWidget] = []
        self._mode = ""

    def add_widget(self, widget: QWidget) -> None:
        self.widgets.append(widget)
        self.set_mode(self._mode or CONTENT_MODE_EXTRA_WIDE, force=True)

    def set_mode(self, mode: str, force: bool = False) -> None:
        mode = normalize_content_mode(mode)
        if not force and mode == self._mode:
            return
        self._mode = mode
        for widget in self.widgets:
            self.grid.removeWidget(widget)
        columns = 2 if mode == CONTENT_MODE_NARROW else max(1, len(self.widgets))
        for index, widget in enumerate(self.widgets):
            self.grid.addWidget(widget, index // columns, index % columns)
        for column in range(max(1, len(self.widgets))):
            self.grid.setColumnStretch(column, 1 if column < columns else 0)
        self.grid.invalidate()


class SettingsEditorDialog(QDialog):
    """Shared themed, contained editor shell for Settings-owned modals."""

    def __init__(self, parent: QWidget, window_title: str, heading: str) -> None:
        super().__init__(parent)
        self.setObjectName("HomeDashboardEditor")
        self.setProperty("hdoPrimitive", _settings_primitive("editor-dialog"))
        self._style_factory = lambda: _editor_style(_editor_tokens(parent))
        self.setStyleSheet(self._style_factory())
        _install_palette_watcher(self, self._style_factory)
        self.setWindowTitle(window_title)
        self.setSizeGripEnabled(True)
        self.body_layout = QVBoxLayout(self)
        title = QLabel(heading)
        title.setObjectName("PageTitle")
        self.body_layout.addWidget(title)

    def _fit_editor(
        self,
        preferred_columns: int,
        minimum_columns: int,
        preferred_lines: int,
        minimum_lines: int,
    ) -> None:
        _apply_control_targets(self)
        metrics = self.fontMetrics()
        column_width = max(1, metrics.averageCharWidth())
        line_height = max(1, metrics.lineSpacing())
        parent = self.parentWidget()
        parent_width = parent.width() if parent is not None else preferred_columns * column_width
        parent_height = parent.height() if parent is not None else preferred_lines * line_height
        screen = self.screen()
        screen_geometry = screen.availableGeometry() if screen is not None else None
        available_width = max(
            INTERACTION_TARGET_MIN_PX * 10,
            min(parent_width, screen_geometry.width() if screen_geometry is not None else parent_width)
            - (3 * line_height),
        )
        available_height = max(
            INTERACTION_TARGET_MIN_PX * 6,
            min(parent_height, screen_geometry.height() if screen_geometry is not None else parent_height)
            - (3 * line_height),
        )
        preferred_width = (preferred_columns * column_width) + (4 * line_height)
        minimum_width = (minimum_columns * column_width) + (4 * line_height)
        preferred_height = preferred_lines * line_height
        minimum_height = minimum_lines * line_height
        width = min(available_width, max(minimum_width, preferred_width))
        height = min(available_height, max(minimum_height, preferred_height))
        self.setMinimumSize(min(width, minimum_width), min(height, minimum_height))
        self.resize(width, height)

    def changeEvent(self, event: Any) -> None:
        if _is_palette_change(event):
            _queue_palette_style(self, self._style_factory)
        if event.type() == getattr(QEvent.Type, "FontChange", None):
            _apply_control_targets(self)
        super().changeEvent(event)


def _manifest_metadata() -> Dict[str, Any]:
    try:
        parsed = json.loads((Path(__file__).resolve().parent / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _anki_version_label(point_version: object) -> str:
    try:
        point = int(point_version)
    except (TypeError, ValueError):
        return "Unknown"
    if point <= 0:
        return "Unknown"
    major = point // 10000
    minor = (point % 10000) // 100
    patch = point % 100
    return "{}.{}.{}".format(major, minor, patch) if patch else "{}.{}".format(major, minor)


def _manifest_compatibility(manifest: Mapping[str, Any]) -> str:
    minimum = _anki_version_label(manifest.get("min_point_version"))
    maximum = _anki_version_label(manifest.get("max_point_version"))
    if maximum not in {"Unknown", minimum}:
        return "{}–{}".format(minimum, maximum)
    return minimum


def _editor_tokens(parent: QWidget) -> Dict[str, str]:
    # Native Settings dialogs follow Anki even while a dashboard preset is
    # staged. Preset colors are confined to preview/swatch surfaces.
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


def _combo_value(combo: QWidget, default: str) -> str:
    if isinstance(combo, SegmentedControl):
        return combo.value(default)
    value = combo.currentData()
    return value if isinstance(value, str) else default


class HistoryRangeCombo(QComboBox):
    """Human range choices with a small compatibility surface for QA probes."""

    def value(self) -> int:
        value = self.currentData()
        return int(value) if value in {"90", "180", "365"} else 0

    def setValue(self, value: object) -> None:
        try:
            candidate = str(int(value))
        except (TypeError, ValueError, OverflowError):
            candidate = "all"
        index = self.findData(candidate if candidate in {"90", "180", "365"} else "all")
        self.setCurrentIndex(max(0, index))


class TextEditDialog(SettingsEditorDialog):
    def __init__(self, title: str, value: str, parent: QWidget) -> None:
        super().__init__(parent, title, title)
        label = QLabel(
            "Use plain text. Optional line breaks and simple bold or italic emphasis are supported; other markup is shown safely as text."
        )
        label.setTextFormat(Qt.TextFormat.PlainText)
        label.setObjectName("EditorHelp")
        label.setWordWrap(True)
        self.body_layout.addWidget(label)
        self.editor = QPlainTextEdit(value)
        _set_accessibility(
            self.editor,
            "Bible verse text",
            "Enter the verse body and reference. Supported simple emphasis tags are sanitized before display.",
        )
        self.body_layout.addWidget(self.editor, 1)
        self.editor_count = QLabel("")
        self.editor_count.setObjectName("EditorHelp")
        self.editor_count.setAccessibleName("Verse entry size")
        self.body_layout.addWidget(self.editor_count)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        save_button = buttons.button(QDialogButtonBox.StandardButton.Save)
        if save_button is not None:
            save_button.setObjectName("PrimaryButton")
            save_button.setText("Save verse")
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        self.body_layout.addWidget(buttons)
        self.editor.textChanged.connect(self._update_count)
        self._update_count()
        self._fit_editor(72, 52, 22, 16)

    def value(self) -> str:
        return self.editor.toPlainText().strip()

    def _update_count(self) -> None:
        value = self.value()
        encoded_size = len(value.encode("utf-8"))
        self.editor_count.setText(
            "{} / {} characters · {} / {} UTF-8 bytes".format(
                len(value), MAX_VERSE_CHARS, encoded_size, MAX_VERSE_BYTES
            )
        )
        self.editor_count.setVisible(
            encoded_size >= int(MAX_VERSE_BYTES * 0.8)
            or len(value) >= int(MAX_VERSE_CHARS * 0.8)
            or not verse_within_limit(value)
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


class EventEditDialog(SettingsEditorDialog):
    def __init__(
        self,
        parent: QWidget,
        item: Optional[Mapping[str, Any]] = None,
        initial_date: str = "",
    ) -> None:
        super().__init__(
            parent,
            "Edit event" if item else "Add event",
            "Edit calendar event" if item else "Add calendar event",
        )
        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.name = QLineEdit(str(item.get("name", "")) if item else "")
        self.name.setMaxLength(160)
        self.name.setMinimumWidth(280)
        self.name.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.name.setCursorPosition(0)
        _set_accessibility(self.name, "Event name", "Required. Up to 160 characters.")
        self.name_help = QLabel(
            "Calendar cells display an event marker. The full event name appears in the context bar and calendar tooltip."
        )
        self.name_help.setObjectName("EditorHelp")
        self.name_help.setWordWrap(True)
        self.name_help.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.name_help.setMinimumHeight(
            (3 * self.name_help.fontMetrics().lineSpacing()) + 2
        )
        self.name_help.setAccessibleName("Event display behavior")
        self.name_count = QLabel()
        self.name_count.setObjectName("EditorHelp")
        self.name_count.setAccessibleName("Event name length")
        self.name.textChanged.connect(self._update_name_count)
        self.date = QDateEdit()
        self.date.setCalendarPopup(True)
        self.date.setDisplayFormat("dddd, MMMM d, yyyy")
        _set_accessibility(self.date, "Event date", "Choose the civil-calendar date for this local event.")
        value = str(item.get("date", "")) if item else initial_date
        parsed = QDate.fromString(value, "yyyy-MM-dd") if value else QDate.currentDate()
        self.date.setDate(parsed if parsed.isValid() else QDate.currentDate())
        form.addRow("Name", self.name)
        form.addRow("", self.name_help)
        form.addRow("", self.name_count)
        form.addRow("Date", self.date)
        form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.body_layout.addLayout(form)
        self.body_layout.addStretch(1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        save_button = buttons.button(QDialogButtonBox.StandardButton.Save)
        if save_button is not None:
            save_button.setObjectName("PrimaryButton")
            save_button.setText("Save event")
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        self.body_layout.addWidget(buttons)
        self._update_name_count(self.name.text())
        self._fit_editor(78, 50, 16, 12)

    def _update_name_count(self, value: str) -> None:
        self.name_count.setText("{} of 160 characters.".format(len(value)))

    def _accept_if_valid(self) -> None:
        if not self.name.text().strip():
            QMessageBox.warning(self, "Event name required", "Enter a concise event name.")
            return
        self.accept()

    def values(self) -> tuple[str, str]:
        return self.name.text().strip(), self.date.date().toString("yyyy-MM-dd")


class SettingsDialog(QDialog):
    def __init__(
        self,
        controller: Any,
        initial_page: str = "",
        selected_event_date: str = "",
        selected_event_id: str = "",
    ) -> None:
        super().__init__(mw)
        self.controller = controller
        self.draft = SettingsDraft(controller.config)
        self.staged = deepcopy(self.draft.values)
        self._heatmap_preset_preferences = deepcopy(
            self.staged.get("heatmap", {}).get("presets_by_theme", {})
        )
        self._heatmap_theme = str(self.staged.get("appearance", {}).get("preset", "Sapphire Glass"))
        self.quotes = list(self.staged["bible"]["quotes"])
        self.pending_manual_quote: Optional[str] = None
        self._staged_new_event_ids: set[str] = set()
        self._staged_edited_event_ids: set[str] = set()
        self._staged_archived_event_ids: set[str] = set()
        self._font_family_touched = False
        self._font_color_invalid = False
        self.page_indices: Dict[str, int] = {}
        self.nav_rows: Dict[str, int] = {}
        self.selected_event_date = selected_event_date
        self.selected_event_id = selected_event_id
        self.current_section = "dashboard"
        self._requested_dashboard_anchor = ""
        self._responsive_bucket = ""
        self._preview_fit_mode = "fit"
        self._preview_scope_mode = "context"
        self._preview_context = "appearance"
        self._building = True
        self._allow_close = False
        self._saving = False
        self._reset_undo_values: Optional[Dict[str, Any]] = None
        self._undo_event_status_id = ""
        self._settings_scroll_base_margins: Dict[
            QScrollArea, tuple[int, int, int, int]
        ] = {}
        self.setObjectName("HomeDashboardSettings")
        self.setWindowTitle("Home Screen Dashboard settings")
        self.resize(1240, 860)
        self.setMinimumSize(560, 560)
        self.setMaximumWidth(1320)
        screen = self.screen() or QApplication.primaryScreen()
        if screen is not None:
            available = screen.availableGeometry()
            maximum_width = max(560, min(1320, available.width() - 32))
            maximum_height = max(560, available.height() - 32)
            self.setMaximumSize(maximum_width, maximum_height)
            self.resize(
                min(1240, maximum_width),
                min(860, maximum_height),
            )
        self._hdo_theme_tokens = _theme_tokens(self.staged, self.controller.is_dark())
        self._preview_content_size = QSize()
        self.setStyleSheet(_settings_style())
        outer = QGridLayout(self)
        outer.setContentsMargins(16, 12, 16, 0)
        outer.setHorizontalSpacing(0)
        outer.setVerticalSpacing(8)
        outer.setRowStretch(0, 0)
        outer.setRowStretch(1, 1)
        outer.setRowStretch(2, 0)

        self.header_shell = QWidget()
        self.header_shell.setObjectName("SettingsHeader")
        header_shell_layout = QVBoxLayout(self.header_shell)
        header_shell_layout.setContentsMargins(0, 0, 0, 0)
        header_shell_layout.setSpacing(8)
        self.header_grid = QGridLayout()
        self.header_grid.setContentsMargins(0, 0, 0, 0)
        self.header_grid.setHorizontalSpacing(12)
        self.header_grid.setVerticalSpacing(4)
        header_text = QVBoxLayout()
        header_text.setSpacing(2)
        self.header_title = QLabel("Home Screen Dashboard")
        self.header_title.setObjectName("PageTitle")
        self.header_subtitle = QLabel("Preview changes immediately; save to apply.")
        self.header_subtitle.setObjectName("PageHelp")
        self.header_subtitle.setWordWrap(True)
        header_text.addWidget(self.header_title)
        header_text.addWidget(self.header_subtitle)
        self.header_grid.addLayout(header_text, 0, 0)
        self.header_grid.setColumnStretch(0, 1)
        self.dirty_badge = QLabel("")
        self.dirty_badge.setObjectName("DirtyBadge")
        self.dirty_badge.setAccessibleName("Settings save status")
        self.dirty_badge.setProperty("hdoLiveRegion", "polite")
        self.dirty_badge.hide()
        self.header_grid.addWidget(
            self.dirty_badge,
            0,
            1,
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight,
        )
        header_shell_layout.addLayout(self.header_grid)

        self.section_tabs = QTabBar()
        self.section_tabs.setObjectName("SettingsTabs")
        self.section_tabs.setAccessibleName("Settings sections")
        self.section_tabs.setExpanding(True)
        self.section_tabs.hide()
        header_shell_layout.addWidget(self.section_tabs)

        self.section_selector_wrap = SettingsSectionSelector()
        self.section_selector = self.section_selector_wrap.combo
        self.section_selector_wrap.hide()
        self.compact_toolbar = QWidget()
        self.compact_toolbar_layout = QBoxLayout(
            QBoxLayout.Direction.LeftToRight,
            self.compact_toolbar,
        )
        self.compact_toolbar_layout.setContentsMargins(0, 0, 0, 0)
        self.compact_toolbar_layout.setSpacing(8)
        self.compact_toolbar_layout.addWidget(self.section_selector_wrap, 1)
        self.compact_preview_wrap = QWidget()
        compact_preview_layout = QHBoxLayout(self.compact_preview_wrap)
        compact_preview_layout.setContentsMargins(0, 0, 0, 0)
        self.compact_preview_button = QPushButton("Preview")
        self.compact_preview_button.clicked.connect(self._open_full_preview)
        _set_accessibility(
            self.compact_preview_button,
            "Open contextual preview",
            "Open the staged Dashboard or Bible verse preview in a separate window.",
        )
        compact_preview_layout.addWidget(self.compact_preview_button)
        self.compact_preview_wrap.hide()
        self.compact_toolbar_layout.addWidget(self.compact_preview_wrap, 0)
        self.compact_toolbar.hide()
        header_shell_layout.addWidget(self.compact_toolbar)
        outer.addWidget(self.header_shell, 0, 0)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.editor_wrap = QWidget()
        self.editor_layout = QHBoxLayout(self.editor_wrap)
        self.editor_layout.setContentsMargins(0, 0, 0, 0)
        self.editor_layout.setSpacing(10)
        self.nav = SettingsSidebar()
        self.stack = QStackedWidget()
        self.editor_layout.addWidget(self.nav, 0, Qt.AlignmentFlag.AlignTop)
        self.editor_layout.addWidget(self.stack, 1)
        self.splitter.addWidget(self.editor_wrap)

        self.preview_wrap = QWidget()
        self.preview_wrap.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        self.preview_wrap.setMaximumWidth(460)
        preview_layout = QVBoxLayout(self.preview_wrap)
        preview_layout.setContentsMargins(8, 0, 0, 0)
        preview_header = QHBoxLayout()
        self.preview_label = QLabel("Dashboard preview")
        self.preview_label.setObjectName("PageTitle")
        preview_header.addWidget(self.preview_label)
        self.preview_sample_badge = QLabel("Sample data")
        self.preview_sample_badge.setObjectName("DataBadge")
        self.preview_sample_badge.setAccessibleName("Deterministic sample study data")
        self.preview_sample_badge.setVisible(self.controller.snapshot is None)
        preview_header.addWidget(self.preview_sample_badge)
        preview_header.addStretch()
        preview_layout.addLayout(preview_header)
        self.preview_scope = SegmentedControl(
            [("Current section", "context"), ("Full dashboard", "full")],
            "context",
            "Preview content",
        )
        self.preview_scope.connect_changed(self._set_preview_scope_mode)
        preview_layout.addWidget(self.preview_scope)
        preview_actions = QHBoxLayout()
        self.preview_scale = SegmentedControl(
            [("Fit", "fit"), ("Actual size", "actual")],
            "fit",
            "Preview scale",
        )
        self.preview_scale.connect_changed(
            lambda *_args: self._set_preview_fit_mode(self.preview_scale.value("fit"))
        )
        preview_actions.addWidget(self.preview_scale)
        self.preview_full_button = QPushButton("Open full preview")
        self.preview_full_button.clicked.connect(self._open_full_preview)
        _set_accessibility(
            self.preview_full_button,
            "Open full preview",
            "Open the production-rendered preview in a separate resizable window.",
        )
        preview_actions.addWidget(self.preview_full_button)
        preview_actions.addStretch()
        preview_layout.addLayout(preview_actions)
        self.preview_empty_label = QLabel("Select a verse to preview")
        self.preview_empty_label.setObjectName("EmptyState")
        self.preview_empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_empty_label.setMinimumHeight(120)
        self.preview_empty_label.hide()
        preview_layout.addWidget(self.preview_empty_label)
        self.preview = AnkiWebView(self.preview_wrap, title="Home Screen Dashboard preview")
        self.preview.setAccessibleName("Home Screen Dashboard contextual preview")
        self.preview.setAccessibleDescription("A production-rendered preview of the current settings section.")
        self.preview.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.preview.setMinimumHeight(0)
        self.preview.setMaximumHeight(520)
        self.preview.setFixedHeight(320)
        preview_layout.addWidget(self.preview)
        self.preview_column = QWidget()
        preview_column_layout = QVBoxLayout(self.preview_column)
        preview_column_layout.setContentsMargins(0, 0, 0, 0)
        preview_column_layout.addWidget(
            self.preview_wrap,
            0,
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight,
        )
        preview_column_layout.addStretch(1)
        self.splitter.addWidget(self.preview_column)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setHandleWidth(0)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)
        outer.addWidget(self.splitter, 1, 0)

        self.preview_timer = QTimer(self)
        self.preview_timer.setSingleShot(True)
        self.preview_timer.setInterval(140)
        self.preview_timer.timeout.connect(self._render_preview)

        self._build_dashboard_page()
        self._build_events_page()
        self._build_bible_page()
        self._build_about_page()
        self.nav.currentRowChanged.connect(self._nav_changed)
        self.section_selector.currentIndexChanged.connect(self._selector_changed)
        self.section_tabs.currentChanged.connect(self._tabs_changed)

        self.footer = SettingsFooter()
        self.buttons = self.footer.buttons
        self.save_button = self.buttons.button(QDialogButtonBox.StandardButton.Save)
        if self.save_button is not None:
            self.save_button.setText("Save changes")
            self.save_button.setObjectName("PrimaryButton")
            self.save_button.setMinimumWidth(112)
            self.save_button.setEnabled(False)
            _set_accessibility(
                self.save_button,
                "Save changes",
                "Apply all staged changes without closing Settings.",
            )
        self.close_button = self.buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if self.close_button is not None:
            self.close_button.setText("Close")
            _set_accessibility(self.close_button, "Close", "Close Settings when clean, or discard staged changes after confirmation.")
        self.buttons.accepted.connect(self._save)
        self.buttons.rejected.connect(self.reject)

        self.undo_toast = QWidget()
        self.undo_toast.setObjectName("UndoToast")
        undo_layout = QHBoxLayout(self.undo_toast)
        undo_layout.setContentsMargins(10, 6, 8, 6)
        self.undo_message = QLabel("")
        self.undo_message.setWordWrap(True)
        self.undo_button = QPushButton("Undo")
        self.undo_button.setObjectName("LinkButton")
        self.undo_button.clicked.connect(self._undo_reset)
        undo_layout.addWidget(self.undo_message, 1)
        undo_layout.addWidget(self.undo_button)
        self.undo_toast.hide()
        self.undo_timer = QTimer(self)
        self.undo_timer.setSingleShot(True)
        self.undo_timer.setInterval(8000)
        self.undo_timer.timeout.connect(self.undo_toast.hide)
        self.footer_shell = QWidget()
        footer_shell_layout = QVBoxLayout(self.footer_shell)
        footer_shell_layout.setContentsMargins(0, 0, 0, 0)
        footer_shell_layout.setSpacing(4)
        footer_shell_layout.addWidget(self.undo_toast)
        footer_shell_layout.addWidget(self.footer)
        outer.addWidget(self.footer_shell, 2, 0)

        self.save_shortcut = QAction("Save changes", self)
        self.save_shortcut.setShortcut(QKeySequence.StandardKey.Save)
        self.save_shortcut.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.save_shortcut.triggered.connect(self._save)
        self.addAction(self.save_shortcut)

        application = QApplication.instance()
        if application is not None:
            application.focusChanged.connect(self._ensure_settings_focus_visible)

        self._connect_preview_signals()
        self._refresh_event_lists()
        self._refresh_quote_list()
        self._building = False
        self.open_page(initial_page, selected_event_date, selected_event_id)
        self._sync_draft()
        _apply_control_targets(self)
        self._apply_responsive(force=True)
        self._render_preview()
        _install_palette_watcher(self, self._current_stylesheet, self._schedule_preview)

    def resizeEvent(self, event: Any) -> None:
        if hasattr(self, "splitter"):
            self._apply_responsive()
        super().resizeEvent(event)
        if hasattr(self, "heatmap_preset_grid"):
            QTimer.singleShot(0, self._reflow_heatmap_grid)
        if hasattr(self, "appearance_grid"):
            QTimer.singleShot(0, self._reflow_compact_grids)

    def changeEvent(self, event: Any) -> None:
        if _is_palette_change(event):
            callback = self._schedule_preview if hasattr(self, "preview_timer") else None
            _queue_palette_style(self, self._current_stylesheet, callback)
        if event.type() in {
            getattr(QEvent.Type, "FontChange", None),
            getattr(QEvent.Type, "ApplicationFontChange", None),
        }:
            _apply_control_targets(self)
            if hasattr(self, "splitter"):
                QTimer.singleShot(0, lambda: self._apply_responsive(force=True))
        super().changeEvent(event)

    def _current_stylesheet(self) -> str:
        return _settings_style()

    def _add_page(self, section_id: str, page: QWidget) -> None:
        name = SECTION_LABELS[section_id]
        item = QListWidgetItem(name)
        item.setData(Qt.ItemDataRole.UserRole, section_id)
        item.setData(Qt.ItemDataRole.AccessibleTextRole, name)
        self.nav.addItem(item)
        self.nav_rows[section_id] = self.nav.count() - 1
        self.nav.setMaximumHeight(self.nav.count() * 48)
        self.section_selector.addItem(name, section_id)
        # QTabBar treats a single ampersand as a mnemonic marker.  Doubling it
        # preserves the visible "About & support" label on every platform.
        tab_index = self.section_tabs.addTab(name.replace("&", "&&"))
        self.section_tabs.setTabData(tab_index, section_id)
        self.page_indices[section_id] = self.stack.count()
        page.setAccessibleName("{} settings".format(name))
        scroll = QScrollArea()
        scroll.setObjectName("SettingsScrollBody")
        scroll.setAccessibleName("{} settings content".format(name))
        scroll.setWidgetResizable(True)
        scroll.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(page)
        page_layout = page.layout()
        if page_layout is not None:
            margins = page_layout.contentsMargins()
            self._settings_scroll_base_margins[scroll] = (
                margins.left(),
                margins.top(),
                margins.right(),
                margins.bottom(),
            )
        self.stack.addWidget(scroll)

    def open_page(
        self,
        page: str = "",
        selected_event_date: str = "",
        selected_event_id: str = "",
    ) -> None:
        section_id, anchor = resolve_section_target(page)
        self._requested_dashboard_anchor = anchor
        row = self.nav_rows.get(section_id)
        if row is not None:
            self.nav.setCurrentRow(row)
        if section_id == "dashboard" and anchor:
            self._normalized_route = "dashboard#{}".format(anchor)
            self._schedule_dashboard_anchor(anchor)
        if section_id == "events" and selected_event_date:
            self._select_event_date(selected_event_date)
        if section_id == "events" and selected_event_id:
            self._refresh_event_lists(select_event_id=selected_event_id)
            QTimer.singleShot(0, self._edit_event)

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

    def _tabs_changed(self, index: int) -> None:
        section_id = self.section_tabs.tabData(index)
        if isinstance(section_id, str) and section_id in self.page_indices:
            self._show_section(section_id, source="tabs")

    def _show_section(self, section_id: str, source: str = "") -> None:
        self.current_section = section_id
        if section_id == "bible_verse":
            self._preview_context = "bible_verse"
            self._preview_fit_mode = "actual"
            if hasattr(self, "preview_scale"):
                self.preview_scale.setValue("actual")
        elif section_id == "dashboard" and self._preview_fit_mode == "actual":
            self._preview_fit_mode = "fit"
            if hasattr(self, "preview_scale"):
                self.preview_scale.setValue("fit")
        self.stack.setCurrentIndex(self.page_indices[section_id])
        if source != "nav":
            self.nav.setCurrentRow(self.nav_rows[section_id])
        if source != "selector":
            index = self.section_selector.findData(section_id)
            if index >= 0 and self.section_selector.currentIndex() != index:
                self.section_selector.blockSignals(True)
                self.section_selector.setCurrentIndex(index)
                self.section_selector.blockSignals(False)
        if source != "tabs":
            for index in range(self.section_tabs.count()):
                if self.section_tabs.tabData(index) == section_id:
                    if self.section_tabs.currentIndex() != index:
                        self.section_tabs.blockSignals(True)
                        self.section_tabs.setCurrentIndex(index)
                        self.section_tabs.blockSignals(False)
                    break
        self._apply_responsive(force=True)
        self._update_section_chrome()
        self._schedule_preview()

    def _schedule_dashboard_anchor(self, anchor: str) -> None:
        """Resolve a legacy anchor only after responsive geometry has settled."""

        self._requested_dashboard_anchor = anchor
        self._preview_context = {
            "appearance": "appearance",
            "content": "visible_sections",
            "dashboard_sections": "visible_sections",
            "calendar": "calendar",
        }.get(anchor, self._preview_context)
        if hasattr(self, "preview_timer"):
            self._schedule_preview()
        QTimer.singleShot(0, lambda: self._settle_dashboard_anchor(anchor, -1, 0))

    def _settle_dashboard_anchor(
        self,
        anchor: str,
        previous_y: int,
        attempt: int,
    ) -> None:
        if self.current_section != "dashboard":
            return
        target = getattr(self, "dashboard_anchors", {}).get(anchor)
        scroll = self.stack.currentWidget()
        if target is None or not isinstance(scroll, QScrollArea):
            return
        page = scroll.widget()
        if page is None:
            return
        page_layout = page.layout()
        if page_layout is not None:
            page_layout.activate()
        target_y = target.mapTo(page, QPoint(0, 0)).y()
        if attempt < 4 and (target_y <= 0 or target_y != previous_y):
            QTimer.singleShot(
                40,
                lambda: self._settle_dashboard_anchor(anchor, target_y, attempt + 1),
            )
            return
        self._scroll_dashboard_anchor(anchor)

    def _scroll_dashboard_anchor(self, anchor: str) -> None:
        if self.current_section != "dashboard":
            return
        target = getattr(self, "dashboard_anchors", {}).get(anchor)
        scroll = self.stack.currentWidget()
        if target is None or not isinstance(scroll, QScrollArea):
            return
        page = scroll.widget()
        if page is None:
            return
        target_y = target.mapTo(page, QPoint(0, 0)).y()
        value = max(0, target_y - 16)
        scroll.verticalScrollBar().setValue(value)
        target.setProperty("hdoScrollMarginTop", 16)
        heading = getattr(target, "heading", None)
        if isinstance(heading, QLabel):
            # Focusing the anchor must not enqueue the generic focus-visibility
            # adjustment: QScrollArea can otherwise move a final tall card to
            # its bottom edge after this method returns and clip the heading.
            self._dashboard_anchor_focus_active = True
            try:
                heading.setFocus(Qt.FocusReason.OtherFocusReason)
            finally:
                self._dashboard_anchor_focus_active = False
            scroll.verticalScrollBar().setValue(value)

    def _settings_layout_metrics(self) -> SettingsLayoutMetrics:
        font_metrics = self.fontMetrics()
        font_height = max(1, font_metrics.lineSpacing())
        average_character = max(1, font_metrics.averageCharWidth())
        layout = self.layout()
        margins = layout.contentsMargins() if layout is not None else None
        fallback_width = self.width()
        if margins is not None:
            fallback_width -= margins.left() + margins.right()
        available_width = max(0, self.splitter.width(), fallback_width)

        current_scroll = self.stack.currentWidget()
        current_page = current_scroll.widget() if isinstance(current_scroll, QScrollArea) else None
        field_width = 0
        if current_page is not None:
            field_types = (
                QPushButton,
                QLineEdit,
                QComboBox,
                QSpinBox,
                QDateEdit,
                QListWidget,
                QTreeWidget,
                QTabWidget,
            )
            for widget in current_page.findChildren(QWidget):
                if isinstance(widget, field_types):
                    field_width = max(field_width, widget.minimumSizeHint().width())

        # A readable form line and a useful preview are typographic minimums;
        # their pixel values grow with the live application font.
        editor_width = max(
            field_width + (4 * font_height),
            (72 * average_character) + (4 * font_height),
        )
        preview_header_width = (
            self.preview_label.sizeHint().width()
            + (3 * font_height)
        )
        preview_width = max(
            preview_header_width,
            (44 * average_character) + (4 * font_height),
        )
        footer_width = self.footer.inline_width_hint() if hasattr(self, "footer") else 0
        spacing = max(self.editor_layout.spacing(), self.splitter.handleWidth())
        return SettingsLayoutMetrics(
            available_width=available_width,
            font_height=font_height,
            sidebar_width=self.nav.measured_width(),
            editor_width=editor_width,
            preview_width=preview_width,
            footer_width=footer_width,
            spacing=spacing,
        )

    def _responsive_mode(self) -> str:
        return settings_content_mode(self._settings_layout_metrics())

    def _apply_responsive(self, force: bool = False) -> None:
        if not hasattr(self, "footer"):
            return
        metrics = self._settings_layout_metrics()
        mode = self._responsive_mode()
        changed = force or mode != self._responsive_bucket
        if not changed:
            self._update_section_chrome()
            return
        self._responsive_bucket = mode
        self.setProperty("hdoContentMode", mode)
        self.style().unpolish(self)
        self.style().polish(self)
        extra_wide = mode == CONTENT_MODE_EXTRA_WIDE
        narrow = mode == CONTENT_MODE_NARROW
        self.nav.setFixedWidth(metrics.sidebar_width)
        self.nav.setVisible(extra_wide)
        self.section_tabs.setVisible(mode == CONTENT_MODE_INTERMEDIATE)
        self.section_selector_wrap.setVisible(narrow)
        status_wraps = narrow or metrics.font_height >= 22
        self.header_grid.removeWidget(self.dirty_badge)
        if status_wraps:
            self.header_grid.addWidget(
                self.dirty_badge,
                1,
                0,
                1,
                2,
                Qt.AlignmentFlag.AlignLeft,
            )
        else:
            self.header_grid.addWidget(
                self.dirty_badge,
                0,
                1,
                Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight,
            )
        compact_stacks = narrow and (
            metrics.available_width < 560 or metrics.font_height >= 22
        )
        self.compact_toolbar_layout.setDirection(
            QBoxLayout.Direction.TopToBottom
            if compact_stacks
            else QBoxLayout.Direction.LeftToRight
        )
        for form in self.findChildren(QFormLayout):
            form.setRowWrapPolicy(
                QFormLayout.RowWrapPolicy.WrapAllRows
                if narrow
                else QFormLayout.RowWrapPolicy.WrapLongRows
            )
        self.footer.set_mode(mode, metrics.available_width)
        for action_group_name in (
            "deck_actions",
            "event_actions",
            "quote_current_actions",
            "quote_actions",
        ):
            action_group = getattr(self, action_group_name, None)
            if isinstance(action_group, (ContextualActionGroup, WrappingActionGroup)):
                action_group.set_mode(mode)
        if hasattr(self, "active_events"):
            self._apply_event_layout(mode)
        for index in range(self.stack.count()):
            scroll = self.stack.widget(index)
            if not isinstance(scroll, QScrollArea):
                continue
            page = scroll.widget()
            if page is None:
                continue
            page.setMaximumWidth(
                680 if extra_wide else 900 if mode == CONTENT_MODE_INTERMEDIATE else 16777215
            )
            scroll.setAlignment(
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop
                if not narrow
                else Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
            )
        maximum_field_width = 16777215 if narrow or extra_wide else 360
        for combo in self.findChildren(QComboBox):
            if combo is not self.section_selector:
                combo.setMaximumWidth(maximum_field_width)
        for spin in self.findChildren(QSpinBox):
            spin.setMaximumWidth(16777215 if narrow else 140)
        for segmented in self.findChildren(SegmentedControl):
            segmented.setMaximumWidth(16777215 if narrow else 420)
        regular_controls = (
            QPushButton,
            QCheckBox,
            QLineEdit,
            QComboBox,
            QSpinBox,
            QDateEdit,
        )
        target_height = 44 if narrow else 40
        for control in self.findChildren(QWidget):
            if isinstance(control, regular_controls) and not isinstance(control, SettingsSwitch):
                control.setMinimumHeight(target_height)
        self.splitter.setOrientation(Qt.Orientation.Horizontal)
        self._update_preview_visibility()
        if extra_wide:
            available = max(2, self.splitter.width(), metrics.available_width)
            desired_preview = min(460, max(380, round(available * .35)))
            preview_size = min(desired_preview, max(1, available - 560))
            self.splitter.setSizes([max(1, available - preview_size), preview_size])
        else:
            self.splitter.setSizes([max(1, self.splitter.width()), 0])
        if hasattr(self, "heatmap_preset_grid"):
            QTimer.singleShot(0, self._reflow_heatmap_grid)
        if hasattr(self, "appearance_grid"):
            QTimer.singleShot(0, self._reflow_compact_grids)
        self._update_section_chrome()
        if self.current_section == "dashboard" and self._requested_dashboard_anchor:
            anchor = self._requested_dashboard_anchor
            QTimer.singleShot(
                0,
                lambda: self._settle_dashboard_anchor(anchor, -1, 0),
            )

    def _apply_settings_footer_clearance(self) -> int:
        """The footer is a normal grid row, so no overlay clearance is needed."""
        for scroll, base in self._settings_scroll_base_margins.items():
            page = scroll.widget()
            page_layout = page.layout() if page is not None else None
            if page_layout is not None:
                page_layout.setContentsMargins(*base)
        return 0

    def _toggle_preview(self, checked: bool) -> None:
        if checked:
            self._open_full_preview()

    def _set_preview_fit_mode(self, mode: str) -> None:
        self._preview_fit_mode = "actual" if mode == "actual" else "fit"
        self.preview_scale.setValue(self._preview_fit_mode)
        self._fit_inline_preview()

    def _set_preview_scope_mode(self, *_args: object) -> None:
        self._preview_scope_mode = self.preview_scope.value("context")
        self._schedule_preview()

    def _update_section_chrome(self) -> None:
        preview_section = self.current_section in {"dashboard", "bible_verse"}
        self.compact_preview_wrap.setVisible(
            preview_section and self._responsive_bucket != CONTENT_MODE_EXTRA_WIDE
        )
        self.compact_toolbar.setVisible(
            self._responsive_bucket == CONTENT_MODE_NARROW
            or (
                preview_section
                and self._responsive_bucket == CONTENT_MODE_INTERMEDIATE
            )
        )
        self.preview_label.setText(
            "Bible verse preview" if self.current_section == "bible_verse" else "Dashboard preview"
        )
        self.preview_sample_badge.setVisible(
            self.current_section == "dashboard" and self.controller.snapshot is None
        )
        self.preview_scope.setVisible(self.current_section == "dashboard")
        self._update_preview_visibility()

    def _ensure_settings_focus_visible(
        self,
        _previous: Optional[QWidget],
        current: Optional[QWidget],
    ) -> None:
        """Keep the focused control above the measured persistent footer."""

        if (
            current is None
            or not self.isAncestorOf(current)
            or getattr(self, "_dashboard_anchor_focus_active", False)
        ):
            return
        if self.current_section == "dashboard":
            candidate: Optional[QWidget] = current
            context = ""
            while candidate is not None and candidate is not self:
                value = candidate.property("hdoPreviewContext")
                if isinstance(value, str) and value:
                    context = value
                    break
                candidate = candidate.parentWidget()
            if context and context != self._preview_context:
                self._preview_context = context
                if self._preview_scope_mode == "context":
                    self._schedule_preview()
        scroll = self.stack.currentWidget() if hasattr(self, "stack") else None
        if not isinstance(scroll, QScrollArea):
            return
        page = scroll.widget()
        if page is None or (current is not page and not page.isAncestorOf(current)):
            return
        focus_margin = FOCUS_RING_PX + FOCUS_RING_OFFSET_PX + 8
        QTimer.singleShot(
            0,
            lambda: scroll.ensureWidgetVisible(
                current,
                focus_margin,
                focus_margin,
            ),
        )

    def _update_preview_visibility(self) -> None:
        visible = (
            self._responsive_bucket == CONTENT_MODE_EXTRA_WIDE
            and self.current_section in {"dashboard", "bible_verse"}
        )
        self.preview_column.setVisible(visible)
        self.preview_wrap.setVisible(visible)

    def _create_appearance_card(self) -> SettingsCard:
        card = SettingsCard(
            "Appearance",
            "Choose the dashboard palette and scale. The Settings editor continues to follow Anki’s application theme.",
            "Reset appearance",
        )
        self.appearance_card = card
        card.setProperty("hdoPreviewContext", "appearance")
        if card.reset_button is not None:
            card.reset_button.clicked.connect(
                lambda: self._reset_card("appearance", "Appearance")
            )
        appearance = self.staged["appearance"]
        self.preset = _combo([(name, name) for name in PRESETS], appearance["preset"])
        _set_accessibility(
            self.preset,
            "Color preset",
            "Choose one of four fully audited dashboard palettes.",
        )
        preset_wrap = QWidget()
        preset_layout = QHBoxLayout(preset_wrap)
        preset_layout.setContentsMargins(0, 0, 0, 0)
        preset_layout.setSpacing(6)
        self.preset_swatch = QLabel()
        self.preset_swatch.setObjectName("DataBadge")
        self.preset_swatch.setTextFormat(Qt.TextFormat.RichText)
        self.preset_swatch.setAccessibleName("Selected preset colors")
        preset_layout.addWidget(self.preset, 1)
        preset_layout.addWidget(self.preset_swatch, 0)
        self.mode = SegmentedControl(
            [("Follow Anki", "auto"), ("Light", "light"), ("Dark", "dark")],
            appearance["mode"],
            "Appearance mode",
        )
        self.mode.setMinimumWidth(0)
        _set_accessibility(
            self.mode,
            "Color mode",
            "Follow Anki automatically, or keep the dashboard in light or dark mode.",
        )
        self.preset.currentIndexChanged.connect(self._dashboard_theme_changed)
        self.mode.connect_changed(self._refresh_heatmap_preset_cards)
        opacity_row, self.opacity_slider, self.opacity = _paired_slider(
            70, 100, appearance["opacity"], " %"
        )
        _set_accessibility(
            self.opacity_slider,
            "Panel opacity slider",
            "Higher values make dashboard cards more solid and easier to separate from the background.",
        )
        _set_accessibility(self.opacity, "Panel opacity value")
        text_scale_row, self.text_scale_slider, self.text_scale = _paired_slider(
            90, 150, appearance["text_scale"], " %"
        )
        _set_accessibility(
            self.text_scale_slider,
            "Dashboard text scale slider",
            "Scales dashboard text while retaining responsive layout.",
        )
        _set_accessibility(self.text_scale, "Dashboard text scale value")
        self.appearance_fields = [
            _stacked_field(
                "Theme preset",
                "Coordinated dashboard colors.",
                preset_wrap,
            ),
            _stacked_field(
                "Appearance mode",
                "Follow Anki, or keep a light or dark dashboard.",
                self.mode,
            ),
            _stacked_field(
                "Card background opacity",
                "Controls how solid dashboard cards appear.",
                opacity_row,
            ),
            _stacked_field(
                "Text scale",
                "Adjusts dashboard typography.",
                text_scale_row,
            ),
        ]
        self.appearance_grid = QGridLayout()
        self.appearance_grid.setContentsMargins(0, 0, 0, 0)
        self.appearance_grid.setHorizontalSpacing(14)
        self.appearance_grid.setVerticalSpacing(10)
        card.add_layout(self.appearance_grid)
        self.appearance_advanced_button = QPushButton("Advanced appearance  ›")
        self.appearance_advanced_button.setCheckable(True)
        self.appearance_advanced_button.setObjectName("DisclosureButton")
        self.appearance_advanced_button.setAccessibleDescription(
            "Show blur and add-on panel placement controls."
        )
        self.appearance_advanced = QWidget()
        advanced_form = QFormLayout(self.appearance_advanced)
        advanced_form.setContentsMargins(0, 0, 0, 0)
        advanced_form.setVerticalSpacing(10)
        blur_row, self.blur_slider, self.blur = _paired_slider(
            0, 32, int(appearance.get("blur", 18)), " px"
        )
        _set_accessibility(self.blur_slider, "Card blur slider")
        _set_accessibility(self.blur, "Card blur value")
        self.home_screen_position = _combo(
            [("Top of add-on stack", "top"), ("Bottom of add-on stack", "bottom")],
            self.staged["home_screen"]["position"],
        )
        _set_accessibility(
            self.home_screen_position,
            "Dashboard panel position",
            "Place the dashboard first or last among injected add-on panels.",
        )
        advanced_form.addRow(
            _field_label("Card blur", "Controls the dashboard’s glass blur effect."),
            blur_row,
        )
        advanced_form.addRow(
            _field_label("Panel placement", "Anki’s deck list remains above injected add-on panels."),
            self.home_screen_position,
        )
        self.appearance_advanced.hide()
        self.appearance_advanced_button.toggled.connect(self.appearance_advanced.setVisible)
        self.appearance_advanced_button.toggled.connect(
            lambda expanded: self.appearance_advanced_button.setText(
                "Advanced appearance  ⌄" if expanded else "Advanced appearance  ›"
            )
        )
        card.add_widget(self.appearance_advanced_button)
        card.add_widget(self.appearance_advanced)
        self._reflow_compact_grids()
        self._update_preset_swatch()
        return card

    def _build_dashboard_page(self) -> None:
        page, layout, form = _page(
            "Dashboard",
            "Personalize the dashboard, choose its sections, and control calendar data in one place.",
        )
        # The page root never owns fields; each group has a quiet, resettable
        # card. Remove the empty compatibility form inserted by ``_page``.
        layout.removeItem(form)
        self.dashboard_anchors: Dict[str, QWidget] = {}
        self.dashboard_jump_links = QWidget()
        dashboard_jump_layout = QHBoxLayout(self.dashboard_jump_links)
        dashboard_jump_layout.setContentsMargins(0, 0, 0, 0)
        dashboard_jump_layout.setSpacing(6)
        for label, anchor in (
            ("Appearance", "appearance"),
            ("Content & metrics", "content"),
            ("Calendar & data", "calendar"),
        ):
            jump = QPushButton(label)
            jump.setObjectName("LinkButton")
            jump.clicked.connect(
                lambda _checked=False, target=anchor: self._schedule_dashboard_anchor(target)
            )
            dashboard_jump_layout.addWidget(jump)
        dashboard_jump_layout.addStretch()
        self.dashboard_jump_selector = _combo(
            [
                ("Appearance", "appearance"),
                ("Content & metrics", "content"),
                ("Calendar & data", "calendar"),
            ],
            "appearance",
        )
        self.dashboard_jump_selector.setAccessibleName("Jump to Dashboard settings area")
        self.dashboard_jump_selector.currentIndexChanged.connect(
            lambda *_args: self._schedule_dashboard_anchor(
                _combo_value(self.dashboard_jump_selector, "appearance")
            )
        )
        self.dashboard_jump_selector.hide()
        layout.addWidget(self.dashboard_jump_links)
        layout.addWidget(self.dashboard_jump_selector)
        appearance_card = self._create_appearance_card()
        appearance_card.setProperty("hdoAnchor", "appearance")
        self.dashboard_anchors["appearance"] = appearance_card
        layout.addWidget(appearance_card)

        sections_card = SettingsCard(
            "Content & study metrics",
            "Disabled dependencies preserve their saved values and return when the required section is enabled.",
            "Reset content & metrics",
        )
        sections_card.setProperty("hdoPreviewContext", "visible_sections")
        if sections_card.reset_button is not None:
            sections_card.reset_button.clicked.connect(
                lambda: self._reset_card("dashboard_sections", "Content & study metrics")
            )
        sections_card.setProperty("hdoAnchor", "content")
        self.dashboard_anchors["content"] = sections_card
        self.dashboard_anchors["dashboard_sections"] = sections_card
        sections_layout = QVBoxLayout()
        sections_layout.setSpacing(8)
        sections_layout.addWidget(_section_title("Visible sections"))
        self.visibility: Dict[str, QPushButton] = {}
        visibility = self.staged["visibility"]

        def add_visibility(key: str, title: str, description: str) -> None:
            row, box = _switch_row(title, description, visibility[key])
            box.setProperty("hdoPreviewContext", "visibility_{}".format(key))
            self.visibility[key] = box
            sections_layout.addWidget(row)

        add_visibility(
            "heatmap",
            "Study calendar",
            "Shows completed reviews, due load, and calendar context.",
        )
        add_visibility(
            "remaining",
            "Today’s progress",
            "Completion, remaining workload, and a compact buried-card summary.",
        )
        add_visibility(
            "today",
            "Today’s session",
            "Cards studied, new cards, time, pace, and the optional completion estimate.",
        )
        add_visibility(
            "heatmap_metrics",
            "Recent and lifetime statistics",
            "Shows seven-day and lifetime study trends.",
        )
        bible_row, bible_switch = _switch_row(
            "Bible verse",
            "Shows the selected verse card after the study dashboard.",
            visibility["bible"],
        )
        self.visibility["bible"] = bible_switch
        bible_switch.setProperty("hdoPreviewContext", "visibility_bible")
        configure_bible = QPushButton("Configure")
        configure_bible.setObjectName("LinkButton")
        configure_bible.clicked.connect(lambda: self._show_section("bible_verse"))
        bible_row.layout().insertWidget(1, configure_bible, 0, Qt.AlignmentFlag.AlignVCenter)
        sections_layout.addWidget(bible_row)

        study_divider = QFrame()
        study_divider.setObjectName("AboutDivider")
        study_divider.setFrameShape(QFrame.Shape.HLine)
        sections_layout.addWidget(study_divider)
        study_heading = _section_title("Study calculations")
        study_heading.setProperty("hdoPreviewContext", "study_calculations")
        sections_layout.addWidget(study_heading)

        dependent_form = QFormLayout()
        dependent_form.setVerticalSpacing(10)
        dependent_form.setHorizontalSpacing(18)
        self.pace_unit = _combo(
            [("Seconds per card", "seconds_per_card"), ("Cards per minute", "cards_per_minute")],
            self.staged["study"]["pace_unit"],
        )
        _set_accessibility(
            self.pace_unit,
            "Pace display",
            "Choose how the same pace calculation is presented.",
        )
        dependent_form.addRow(
            _field_label("Pace display", "Changes presentation only; the underlying study history is unchanged."),
            self.pace_unit,
        )
        eta_row, self.show_eta = _switch_row(
            "Show estimated completion time",
            "Uses the same filtered workload and current pace. Requires Today’s session.",
            self.staged["study"]["show_eta"],
        )
        dependent_form.addRow(eta_row)
        self.eta_dependency = QLabel(
            "Requires Today’s session. Your preference remains saved while unavailable."
        )
        self.eta_dependency.setObjectName("FieldHelp")
        self.eta_dependency.setWordWrap(True)
        self.eta_dependency.setBuddy(self.show_eta)
        dependent_form.addRow(self.eta_dependency)
        self.retention_target = QSpinBox()
        self.retention_target.setRange(50, 100)
        self.retention_target.setSuffix(" %")
        self.retention_target.setValue(int(self.staged["study"].get("retention_target", 80)))
        _set_accessibility(
            self.retention_target,
            "Retention status target",
            "Retention is styled as success only when it reaches this target.",
        )
        dependent_form.addRow(
            _field_label("Retention status target", "Changes status colors; it does not change scheduling."),
            self.retention_target,
        )
        new_row, self.include_rescheduled = _switch_row(
            "Count manually rescheduled cards as newly studied",
            "Counts a card as newly studied when its first qualifying answer follows a manual reschedule.",
            self.staged["new_cards"]["include_rescheduled"],
        )
        for control in (
            self.pace_unit,
            self.show_eta,
            self.retention_target,
            self.include_rescheduled,
        ):
            control.setProperty("hdoPreviewContext", "study_calculations")
        dependent_form.addRow(new_row)
        sections_layout.addLayout(dependent_form)
        sections_card.add_layout(sections_layout)
        layout.addWidget(sections_card)

        calendar_card = self._create_calendar_card()
        calendar_card.setProperty("hdoPreviewContext", "calendar")
        calendar_card.setProperty("hdoAnchor", "calendar")
        self.dashboard_anchors["calendar"] = calendar_card
        layout.addWidget(calendar_card)
        layout.addStretch()
        self._add_page("dashboard", page)

    def _create_calendar_card(self) -> SettingsCard:
        card = SettingsCard(
            "Calendar & data",
            "Choose the default view, history, future range, and heatmap palette.",
            "Reset calendar & data",
        )
        if card.reset_button is not None:
            card.reset_button.clicked.connect(
                lambda: self._reset_card("calendar", "Calendar & data")
            )
        form = card.add_form()
        heatmap = self.staged["heatmap"]

        self.collection_updates_notice = QLabel(
            "Study totals and due dates recalculate after saving."
        )
        self.collection_updates_notice.setObjectName("PageHelp")
        self.collection_updates_notice.setAccessibleName(
            "Study totals and due dates recalculate after saving"
        )
        collection_info = QWidget()
        collection_info_layout = QHBoxLayout(collection_info)
        collection_info_layout.setContentsMargins(0, 0, 0, 0)
        collection_info_layout.addWidget(self.collection_updates_notice)
        collection_info_layout.addWidget(
            _info_button(
                "Recalculation details",
                "History filters and deck exclusions are recalculated from the collection after saving.",
            )
        )
        collection_info_layout.addStretch()
        form.addRow(collection_info)

        self.calendar_view = SegmentedControl(
            [("Month", "month"), ("Year", "year")],
            heatmap["calendar_view"],
            "Default calendar view",
        )
        self._week_start_touched = False
        self._legacy_week_start_value = str(heatmap["week_start"])
        self.week_start = SegmentedControl(
            [("Sunday", "6"), ("Monday", "0")],
            self._legacy_week_start_value,
            "First day of week",
        )
        self.week_start.connect_changed(self._week_start_changed)
        _set_accessibility(self.calendar_view, "Default calendar view", "Choose Month or Year view.")
        _set_accessibility(self.week_start, "First day of week", "Choose the weekday used to start calendar rows.")
        form.addRow(_field_label("Default view", "Month is conventional; Year emphasizes long-term consistency."), self.calendar_view)
        form.addRow(_field_label("Week starts", "Applied consistently to Month and Year layouts."), self.week_start)

        event_row, event_switch = _switch_row(
            "Event markers",
            "Adds local event diamonds and nearest-event context. Requires Study calendar.",
            self.staged["visibility"]["events"],
        )
        self.visibility["events"] = event_switch
        form.addRow(event_row)
        self.events_dependency = QLabel(
            "Requires Study calendar. Your event preference remains saved while unavailable."
        )
        self.events_dependency.setObjectName("FieldHelp")
        self.events_dependency.setWordWrap(True)
        self.events_dependency.setBuddy(event_switch)
        form.addRow(self.events_dependency)

        self.heatmap_preset_wrap = QWidget()
        self.heatmap_preset_grid = QGridLayout(self.heatmap_preset_wrap)
        self.heatmap_preset_grid.setContentsMargins(0, 0, 0, 0)
        self.heatmap_preset_grid.setHorizontalSpacing(8)
        self.heatmap_preset_grid.setVerticalSpacing(8)
        self.heatmap_preset_buttons: Dict[str, QPushButton] = {}
        self._refresh_heatmap_preset_cards()
        form.addRow(
            _stacked_field(
                "Heatmap palette",
                "Each card previews an empty cell and all five authored intensity levels. The choice is remembered separately for every dashboard theme.",
                self.heatmap_preset_wrap,
            )
        )

        self.history_range = HistoryRangeCombo()
        for label, value in (
            ("All history", "all"),
            ("Last 90 days", "90"),
            ("Last 180 days", "180"),
            ("Last 365 days", "365"),
            ("Custom", "custom"),
        ):
            self.history_range.addItem(label, value)
        initial_history_choice = history_range_choice(
            heatmap.get("history_days", 0), heatmap.get("ignore_before", "")
        )
        self.history_range.setCurrentIndex(
            max(0, self.history_range.findData(initial_history_choice))
        )
        # Retain the attribute used by existing runtime probes while exposing
        # the approved compact choice instead of a raw day-count spin box.
        self.history_days = self.history_range
        self.forecast_days = QSpinBox(); self.forecast_days.setRange(0, 730); self.forecast_days.setSpecialValueText("Off"); self.forecast_days.setSuffix(" days"); self.forecast_days.setValue(heatmap["forecast_days"])
        _set_accessibility(
            self.history_range,
            "History range",
            "Choose all history, a common rolling range, or a custom start date.",
        )
        _set_accessibility(self.forecast_days, "Due forecast range", "The number of future scheduling dates to show.")
        forecast_row, self.show_forecast = _switch_row(
            "Future due dates",
            "Adds due-card markers without combining them with completed-review intensity.",
            heatmap["show_due_forecast"],
        )
        form.addRow(
            _field_label("History range", "Choose a familiar range; Custom reveals an earliest study date."),
            self.history_range,
        )
        form.addRow(forecast_row)
        self.forecast_range_label = _field_label(
            "Future range",
            "Choose how many future scheduling dates to show.",
        )
        form.addRow(self.forecast_range_label, self.forecast_days)
        semantics = QPushButton("How dates are calculated  ›")
        semantics.setCheckable(True)
        semantics.setObjectName("DisclosureButton")
        semantics.setAccessibleDescription("Show the date and rollover rules.")
        semantics_copy = QLabel(
            "Study counts and due forecasts follow Anki’s configured rollover, not calendar midnight. Events use their civil-calendar date."
        )
        semantics_copy.setObjectName("FieldHelp")
        semantics_copy.setWordWrap(True)
        semantics_copy.hide()
        semantics.toggled.connect(semantics_copy.setVisible)
        semantics.toggled.connect(
            lambda expanded: semantics.setText(
                "How dates are calculated  ⌄" if expanded else "How dates are calculated  ›"
            )
        )
        form.addRow(semantics)
        form.addRow(semantics_copy)

        self.calendar_advanced_button = QPushButton("Advanced calendar data  ›")
        self.calendar_advanced_button.setCheckable(True)
        self.calendar_advanced_button.setObjectName("DisclosureButton")
        self.calendar_advanced_button.setAccessibleDescription(
            "Show custom history rules and deck exclusions."
        )
        card.add_widget(self.calendar_advanced_button)
        self.calendar_advanced = QWidget()
        advanced_form = QFormLayout(self.calendar_advanced)
        advanced_form.setContentsMargins(0, 0, 0, 0)
        advanced_form.setVerticalSpacing(10)
        advanced_form.setHorizontalSpacing(18)
        self.ignore_before = QDateEdit(); self.ignore_before.setCalendarPopup(True); self.ignore_before.setDisplayFormat("MMMM d, yyyy")
        parsed_ignore = QDate.fromString(heatmap["ignore_before"], "yyyy-MM-dd")
        self.ignore_before.setDate(parsed_ignore if parsed_ignore.isValid() else QDate.currentDate())
        _set_accessibility(self.ignore_before, "History start date", "Reviews before this date are ignored after Save.")
        self.exclude_reschedules = QCheckBox("Exclude manual changes"); self.exclude_reschedules.setToolTip("Ignore manual reschedule and forget log entries."); self.exclude_reschedules.setChecked(heatmap["exclude_manual_reschedules"])
        self.exclude_deleted = QCheckBox("Exclude deleted cards"); self.exclude_deleted.setToolTip("Ignore review logs for cards that no longer exist."); self.exclude_deleted.setChecked(heatmap["exclude_deleted_cards"])
        _set_accessibility(self.exclude_reschedules, "Exclude manual changes", "Ignore manual reschedule and forget log entries after Save.")
        _set_accessibility(self.exclude_deleted, "Exclude deleted cards", "Ignore review logs for cards that no longer exist after Save.")
        self.history_start_label = _field_label(
            "Custom start",
            "Reviews before this date are ignored after Save.",
        )
        advanced_form.addRow(self.history_start_label, self.ignore_before)
        advanced_form.addRow(_field_label("Manual changes", "Filters manual reschedule and forget log entries."), self.exclude_reschedules)
        advanced_form.addRow(_field_label("Deleted cards", "Filters logs whose cards no longer exist."), self.exclude_deleted)

        self.deck_search = QLineEdit(); self.deck_search.setPlaceholderText("Filter decks…")
        _set_accessibility(self.deck_search, "Filter decks", "Filter by full deck path without changing exclusions.")
        self.deck_tree = QTreeWidget()
        self.deck_tree.setObjectName("ManagerTree")
        self.deck_tree.setHeaderLabels(["Deck"])
        self.deck_tree.setHeaderHidden(True)
        self.deck_tree.setRootIsDecorated(True)
        self.deck_tree.setUniformRowHeights(True)
        self.deck_tree.setMinimumHeight(180)
        self.deck_tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.deck_tree.setAccessibleName("Deck exclusions")
        self.deck_tree.setAccessibleDescription(
            "A collapsed hierarchical deck tree. Checked parents exclude their descendants; partially checked parents contain child-only exclusions."
        )
        _install_settings_row_delegate(self.deck_tree)
        self._updating_deck_tree = False
        self._deck_items_by_id: Dict[int, QTreeWidgetItem] = {}
        self._deck_unavailable_group: Optional[QTreeWidgetItem] = None
        self._populate_deck_tree(heatmap["excluded_deck_ids"])
        self.deck_exclusion_summary = QLabel()
        self.deck_exclusion_summary.setObjectName("PageHelp")
        self.deck_exclusion_summary.setAccessibleName("Deck exclusion count")
        self.deck_actions = ContextualActionGroup()
        exclude_shown = QPushButton("Exclude all filtered decks"); exclude_shown.clicked.connect(lambda: self._set_visible_decks(Qt.CheckState.Checked))
        include_shown = QPushButton("Include all filtered decks"); include_shown.clicked.connect(lambda: self._set_visible_decks(Qt.CheckState.Unchecked))
        self.remove_unavailable_decks = QPushButton("Remove unavailable")
        self.remove_unavailable_decks.clicked.connect(self._remove_unavailable_deck_exclusions)
        _set_accessibility(exclude_shown, "Exclude all filtered decks", "Exclude every deck currently visible in the filtered list.")
        _set_accessibility(include_shown, "Include all filtered decks", "Remove the exclusion from every deck currently visible in the filtered list.")
        _set_accessibility(
            self.remove_unavailable_decks,
            "Remove unavailable deck exclusions",
            "Remove every saved exclusion whose deck is unavailable in this collection.",
        )
        self.deck_actions.add_widget(exclude_shown); self.deck_actions.add_widget(include_shown); self.deck_actions.add_widget(self.remove_unavailable_decks); self.deck_actions.add_stretch()
        deck_wrap = QWidget(); deck_layout = QVBoxLayout(deck_wrap); deck_layout.setContentsMargins(0, 0, 0, 0); deck_layout.addWidget(self.deck_search); deck_layout.addWidget(self.deck_exclusion_summary); deck_layout.addWidget(self.deck_tree); deck_layout.addWidget(self.deck_actions)
        self.deck_search.textChanged.connect(self._filter_decks)
        self.deck_tree.itemChanged.connect(self._deck_item_changed)
        self._update_deck_exclusion_summary()
        advanced_form.addRow(
            _field_label("Excluded decks", "A checked parent excludes its descendants across dashboard study data; full deck paths are retained."),
            deck_wrap,
        )
        self.calendar_advanced.hide()
        self.calendar_advanced_button.toggled.connect(self.calendar_advanced.setVisible)
        self.calendar_advanced_button.toggled.connect(
            lambda expanded: self.calendar_advanced_button.setText(
                "Advanced calendar data  ⌄" if expanded else "Advanced calendar data  ›"
            )
        )
        card.add_widget(self.calendar_advanced)
        self.show_forecast.toggled.connect(self._update_forecast_range_visibility)
        self.history_range.currentIndexChanged.connect(self._update_history_range_visibility)
        self._update_forecast_range_visibility()
        self._update_history_range_visibility()
        return card

    def _build_events_page(self) -> None:
        page, layout, form = _page(
            "Events",
            "Manage local dashboard events. Past events move to Archived automatically; archive and restore are reversible.",
        )
        layout.removeItem(form)
        event_heading_actions = QHBoxLayout()
        event_heading_actions.addStretch()
        self.event_add = QPushButton("Add event")
        self.event_add.setObjectName("PrimaryButton")
        self.event_add.clicked.connect(self._add_event)
        _set_accessibility(self.event_add, "Add event", "Open the local event editor.")
        event_heading_actions.addWidget(self.event_add, 0)
        layout.addLayout(event_heading_actions)
        self.event_date_context = QLabel("")
        self.event_date_context.setTextFormat(Qt.TextFormat.PlainText)
        self.event_date_context.setObjectName("PageHelp")
        self.event_date_context.setAccessibleName("Selected calendar date")
        self.event_date_context.hide()
        layout.addWidget(self.event_date_context)
        event_toolbar = QHBoxLayout()
        self.event_search = QLineEdit(); self.event_search.setPlaceholderText("Search events…")
        _set_accessibility(self.event_search, "Search events", "Search by event name or date.")
        self.event_sort = _combo([("Soonest first", "ascending"), ("Latest first", "descending")], self.staged["events"].get("sort", "ascending"))
        self.event_sort.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.event_sort.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        _set_accessibility(self.event_sort, "Event sort order", "Sort active and archived events by date.")
        event_toolbar.addWidget(self.event_search, 1)
        event_toolbar.addWidget(self.event_sort, 0)
        self.event_toolbar_wrap = QWidget()
        self.event_toolbar_wrap.setLayout(event_toolbar)
        layout.addWidget(self.event_toolbar_wrap)
        self.event_tabs = QTabWidget()
        self.event_tabs.tabBar().setExpanding(True)
        _set_accessibility(self.event_tabs, "Active and archived events", "Switch between active and archived local events.")
        self.active_events = self._event_tree("Active calendar events")
        self.archived_events = self._event_tree("Archived calendar events")
        self.event_tabs.addTab(self.active_events, "Active (0)")
        self.event_tabs.addTab(self.archived_events, "Archived (0)")
        self.event_tabs.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        layout.addWidget(self.event_tabs)
        self.event_empty_state = QWidget()
        self.event_empty_state.setObjectName("EmptyState")
        self.event_empty_state.setMinimumHeight(280)
        empty_layout = QVBoxLayout(self.event_empty_state)
        empty_layout.setContentsMargins(24, 28, 24, 28)
        empty_layout.setSpacing(8)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.event_empty_icon = QLabel("◇")
        self.event_empty_icon.setAccessibleName("Calendar event")
        self.event_empty_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.event_empty_title = QLabel("No events yet")
        self.event_empty_title.setObjectName("EmptyStateTitle")
        self.event_empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.event_empty_copy = QLabel(
            "Add an event to show a marker and upcoming-event context on the dashboard calendar."
        )
        self.event_empty_copy.setObjectName("EmptyStateCopy")
        self.event_empty_copy.setWordWrap(True)
        self.event_empty_copy.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.event_empty_copy.setMaximumWidth(360)
        self.event_empty_add = QPushButton("Add event")
        self.event_empty_add.setObjectName("PrimaryButton")
        self.event_empty_add.clicked.connect(self._add_event)
        _set_accessibility(self.event_empty_add, "Add event", "Open the local event editor.")
        empty_layout.addWidget(self.event_empty_icon, 0, Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(self.event_empty_title, 0, Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(self.event_empty_copy, 0, Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(self.event_empty_add, 0, Qt.AlignmentFlag.AlignCenter)
        self.event_empty_state.hide()
        layout.addWidget(self.event_empty_state)
        self.event_action_feedback = QLabel("")
        self.event_action_feedback.setTextFormat(Qt.TextFormat.PlainText)
        self.event_action_feedback.setObjectName("PageHelp")
        self.event_action_feedback.setAccessibleName("Event action confirmation")
        self.event_action_feedback.setProperty("hdoLiveRegion", "polite")
        self.event_action_feedback.setWordWrap(True)
        layout.addWidget(self.event_action_feedback)
        self.event_search.textChanged.connect(self._refresh_event_lists)
        self.event_sort.currentIndexChanged.connect(self._refresh_event_lists)
        self.event_tabs.currentChanged.connect(self._update_event_actions)
        self.active_events.itemDoubleClicked.connect(lambda *_args: self._edit_event())
        self.archived_events.itemDoubleClicked.connect(lambda *_args: self._edit_event())
        layout.addStretch()
        self._add_page("events", page)

    def _event_tree(self, accessible_name: str) -> QTreeWidget:
        tree = QTreeWidget()
        tree.setObjectName("ManagerTree")
        tree.setAccessibleName(accessible_name)
        tree.setHeaderLabels(["Date", "Event", "Actions"])
        tree.setRootIsDecorated(False)
        # Qt can paint native alternate-base stripes through an otherwise empty
        # tree, especially when the staged dashboard theme differs from Anki's
        # current mode. A solid viewport keeps the empty state calm and avoids
        # implying phantom rows; real rows retain explicit separators above.
        tree.setAlternatingRowColors(False)
        tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        tree.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        _install_settings_row_delegate(tree)
        tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        tree.setMinimumHeight(0)
        tree.setMaximumHeight(max(300, 14 * tree.fontMetrics().lineSpacing()))
        tree.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        return tree

    def _apply_event_layout(self, mode: str) -> None:
        """Turn event table rows into stacked, full-width cards when narrow."""

        narrow = normalize_content_mode(mode) == CONTENT_MODE_NARROW
        for tree in (self.active_events, self.archived_events):
            tree.setProperty("narrowCards", narrow)
            tree.setHeaderHidden(narrow)
            tree.setColumnHidden(1, narrow)
            tree.setColumnHidden(2, False)
            tree.header().setSectionResizeMode(
                0,
                QHeaderView.ResizeMode.Stretch
                if narrow
                else QHeaderView.ResizeMode.ResizeToContents,
            )
            for row in range(tree.topLevelItemCount()):
                item = tree.topLevelItem(row)
                event_date = str(item.data(0, EVENT_DATE_ROLE) or "")
                event_name = str(item.data(0, EVENT_NAME_ROLE) or "")
                status = str(item.data(0, EVENT_STATUS_ROLE) or "")
                if narrow:
                    item.setText(
                        0,
                        "{}\n{}{}".format(
                            event_name,
                            event_date,
                            " · {}".format(status) if status else "",
                        ),
                    )
                    item.setSizeHint(
                        0,
                        QSize(
                            max(1, tree.viewport().width()),
                            max(58, 3 * tree.fontMetrics().lineSpacing()),
                        ),
                    )
                else:
                    item.setText(0, event_date)
                    item.setText(
                        1,
                        "{}{}".format(
                            event_name,
                            " · {}".format(status) if status else "",
                        ),
                    )
            tree.style().unpolish(tree)
            tree.style().polish(tree)
            tree.doItemsLayout()

    def _build_bible_page(self) -> None:
        page, layout, root_form = _page(
            "Bible verse",
            "Customize the verse card separately from its library. Selecting a library item previews that exact verse without changing daily or manual rotation state.",
        )
        layout.removeItem(root_form)
        bible = self.staged["bible"]
        display_card = SettingsCard(
            "Display",
            "Typography and color apply only to the dashboard’s verse card.",
            "Reset verse appearance",
        )
        self.bible_display_card = display_card
        display_card.setProperty("hdoPreviewContext", "bible_verse")
        if display_card.reset_button is not None:
            display_card.reset_button.clicked.connect(
                lambda: self._reset_card("bible_appearance", "Verse appearance")
            )
        self.font_family = QFontComboBox(); self.font_family.setCurrentFont(self.font_family.currentFont())
        family_name = str(bible["font_family"]).split(",", 1)[0].strip().strip('"\'')
        index = self.font_family.findText(family_name); self.font_family.setCurrentIndex(max(0, index))
        self.font_size = QSpinBox(); self.font_size.setRange(8, 96); self.font_size.setSuffix(" px"); self.font_size.setValue(int(str(bible["font_size"]).replace("px", "")))
        self.font_color_value = bible["font_color"]
        self.font_color = QLineEdit(self.font_color_value.upper())
        self.font_color.setMaxLength(7)
        self.font_color.setPlaceholderText("#1E90FF")
        self.font_color.textChanged.connect(self._font_color_text_changed)
        self.font_color.editingFinished.connect(self._font_color_edited)
        self.font_color_swatch = QPushButton("")
        self.font_color_swatch.setFixedSize(38, 38)
        self.font_color_swatch.clicked.connect(self._choose_font_color)
        self.font_color_swatch.setAccessibleName("Choose custom verse color")
        color_row = QWidget()
        color_layout = QHBoxLayout(color_row)
        color_layout.setContentsMargins(0, 0, 0, 0)
        color_layout.addWidget(self.font_color, 1)
        color_layout.addWidget(self.font_color_swatch)
        color_layout.addStretch()
        self.theme_color = SegmentedControl(
            [("Theme color", "theme"), ("Custom color", "custom")],
            "theme" if bible["theme_aware_color"] else "custom",
            "Verse text color source",
        )
        self.rotation = SegmentedControl(
            [
                ("Daily", "daily"),
                ("On refresh", "every render"),
                ("Manual", "manual"),
            ],
            bible["rotation_mode"],
            "Verse rotation",
        )
        _set_accessibility(self.font_family, "Verse font family", "Choose the font used only by the verse card.")
        _set_accessibility(self.font_size, "Verse font size", "Choose a verse-card size from 8 to 96 pixels.")
        _set_accessibility(self.font_color, "Custom verse color hex value", "Enter a six-digit hexadecimal color when theme-aware text color is off.")
        _set_accessibility(self.font_color_swatch, "Choose custom verse color", "Open the color chooser when theme-aware text color is off.")
        _set_accessibility(
            self.rotation,
            "Verse rotation",
            "Choose daily, every dashboard refresh, or manual rotation. Previewing a selection does not rotate it.",
        )
        self.font_family.setToolTip("Applies only to verse body and reference text.")
        self.font_size.setToolTip("The verse card remains responsive at larger values.")
        self.bible_display_fields = [
            _stacked_field("Font family", "", self.font_family),
            _stacked_field("Font size", "", self.font_size),
        ]
        self.bible_display_grid = QGridLayout()
        self.bible_display_grid.setContentsMargins(0, 0, 0, 0)
        self.bible_display_grid.setHorizontalSpacing(14)
        self.bible_display_grid.setVerticalSpacing(10)
        display_card.add_layout(self.bible_display_grid)
        display_card.add_widget(
            _stacked_field(
                "Text color",
                "Use the dashboard theme or a stored custom color.",
                self.theme_color,
            )
        )
        self.custom_color_container = _stacked_field(
            "Custom color",
            "Enter #RRGGBB. Low contrast is warned about rather than changed.",
            color_row,
        )
        self.font_color_warning = QLabel("")
        self.font_color_warning.setObjectName("FieldHelp")
        self.font_color_warning.setWordWrap(True)
        self.font_color_warning.setAccessibleName("Custom verse color contrast")
        custom_layout = self.custom_color_container.layout()
        if custom_layout is not None:
            custom_layout.addWidget(self.font_color_warning)
        display_card.add_widget(self.custom_color_container)
        self._reflow_compact_grids()
        layout.addWidget(display_card)

        rotation_card = SettingsCard(
            "Rotation",
            "Choose when the dashboard selects another verse.",
            "Reset rotation",
        )
        if rotation_card.reset_button is not None:
            rotation_card.reset_button.clicked.connect(
                lambda: self._reset_card("bible_rotation", "Verse rotation")
            )
        rotation_form = rotation_card.add_form()
        rotation_form.addRow(
            _stacked_field(
                "Rotation",
                "Daily changes once per date. On refresh may change each render. Manual keeps the selected verse.",
                self.rotation,
            )
        )
        layout.addWidget(rotation_card)
        self._update_color_swatch()

        library_card = SettingsCard(
            "Verse library",
            "Select, search, and manage the staged library.",
        )
        self.quote_search = QLineEdit(); self.quote_search.setPlaceholderText("Search the verse library…")
        _set_accessibility(self.quote_search, "Search verse library", "Filter staged verses by their displayed text or reference.")
        self.quote_count = QLabel(); self.quote_count.setObjectName("PageHelp")
        self.quote_detail = QLabel()
        self.quote_detail.setObjectName("SelectedVerseCard")
        self.quote_detail.setAccessibleName("Full selected verse")
        self.quote_detail.setAccessibleDescription("Read the complete text and reference of the selected staged verse.")
        self.quote_detail.setTextFormat(Qt.TextFormat.PlainText)
        self.quote_detail.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        self.quote_detail.setWordWrap(True)
        self.quote_detail.setMinimumHeight(86)
        self.quote_list = QListWidget(); self.quote_list.setObjectName("ManagerList"); self.quote_list.setMinimumHeight(220); self.quote_list.setTextElideMode(Qt.TextElideMode.ElideRight); self.quote_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff); _install_settings_row_delegate(self.quote_list)
        _set_accessibility(self.quote_list, "Verse library", "Choose a staged verse to read, edit, duplicate, delete, or preview.")
        selected_verse_header = QHBoxLayout()
        selected_verse_header.addWidget(_section_title("Selected verse"))
        selected_verse_header.addStretch()
        self.quote_detail_status = QLabel("Previewing")
        self.quote_detail_status.setObjectName("DataBadge")
        selected_verse_header.addWidget(self.quote_detail_status)
        library_card.add_layout(selected_verse_header)
        library_card.add_widget(self.quote_detail)
        library_card.add_widget(self.quote_search)
        library_card.add_widget(self.quote_count)
        library_card.add_widget(self.quote_list, 1)
        self._quote_render_limit = 100
        self.quote_load_more = QPushButton("Load more")
        self.quote_load_more.clicked.connect(self._load_more_quotes)
        self.quote_load_more.hide()
        library_card.add_widget(self.quote_load_more)
        self.quote_current_actions = ContextualActionGroup()
        self.quote_use_current = QPushButton("Use this verse")
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
        self.quote_current_actions.add_widget(self.quote_use_current)
        self.quote_current_actions.add_widget(self.quote_current_feedback, 1)
        library_card.add_widget(self.quote_current_actions)
        self.quote_actions = ContextualActionGroup()
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
            self.quote_actions.add_widget(button)
        import_info = _info_button(
            "Verse import details",
            "Imports trim empty entries, skip exact duplicates, reject oversized entries, and stop at 500 verses.",
        )
        self.quote_actions.add_widget(import_info)
        self.quote_actions.add_stretch()
        library_card.add_widget(self.quote_actions)
        layout.addWidget(library_card)
        layout.addStretch()
        self._add_page("bible_verse", page)

    def _build_about_page(self) -> None:
        page, layout, root_form = _page(
            "About & support",
            "Version information, help, privacy, legal notices, and recovery guidance.",
        )
        layout.removeItem(root_form)
        manifest = _manifest_metadata()
        product_name = str(manifest.get("name") or "Home Screen Dashboard")
        version = str(manifest.get("human_version") or "Unknown")
        compatibility = _manifest_compatibility(manifest)
        notices_url = Path(__file__).resolve().with_name("THIRD_PARTY_NOTICES.md").as_uri()

        def rich_label(value: str) -> QLabel:
            label = QLabel(value)
            label.setWordWrap(True)
            label.setOpenExternalLinks(True)
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
            return label

        version_card = SettingsCard("Version & compatibility")
        version_card.setMaximumWidth(880)
        version_form = version_card.add_form()
        version_form.addRow("Product", QLabel("{} {}".format(product_name, version)))
        version_form.addRow("Compatibility", QLabel("Supports Anki Desktop {}".format(compatibility)))
        copy_diagnostics = QPushButton("Copy diagnostics")
        copy_diagnostics.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        diagnostics = "{} {} | Anki Desktop {} | schema {}".format(
            product_name,
            version,
            compatibility,
            self.staged.get("schema_version", "Unknown"),
        )
        copy_feedback = QLabel("")
        copy_feedback.setObjectName("PageHelp")
        copy_feedback.setProperty("hdoLiveRegion", "polite")

        def copy_about_diagnostics() -> None:
            QApplication.clipboard().setText(diagnostics)
            copy_feedback.setText("Diagnostics copied")

        copy_diagnostics.clicked.connect(copy_about_diagnostics)
        version_card.add_widget(copy_diagnostics)
        version_card.add_widget(copy_feedback)
        layout.addWidget(version_card)

        help_card = SettingsCard("Help")
        help_card.setMaximumWidth(880)
        help_card.add_widget(
            rich_label(
                '<a href="{}">Documentation ↗</a>&nbsp;&nbsp;&nbsp;'
                '<a href="{}">Report an issue ↗</a>'.format(
                    html_module.escape(PROJECT_URL, quote=True),
                    html_module.escape(ISSUES_URL, quote=True),
                )
            )
        )
        layout.addWidget(help_card)

        privacy_card = SettingsCard("Privacy & legal")
        privacy_card.setMaximumWidth(880)
        privacy_callout = QLabel(
            "Your study data stays local. This add-on does not send dashboard data to external services."
        )
        privacy_callout.setObjectName("EmptyState")
        privacy_callout.setWordWrap(True)
        privacy_card.add_widget(privacy_callout)
        def add_about_disclosure(title: str, copy: str) -> None:
            button = QPushButton("{}  ›".format(title))
            button.setObjectName("DisclosureButton")
            button.setCheckable(True)
            detail = rich_label(copy)
            detail.hide()
            button.toggled.connect(detail.setVisible)
            button.toggled.connect(
                lambda expanded, control=button, label=title: control.setText(
                    "{}  {}".format(label, "⌄" if expanded else "›")
                )
            )
            privacy_card.add_widget(button)
            privacy_card.add_widget(detail)

        add_about_disclosure(
            "What is stored locally",
            "Preferences, deck exclusions, local events, the verse library, and rotation state are stored in Anki’s add-on data on this device.",
        )
        add_about_disclosure(
            "License",
            "GNU Affero General Public License, version 3 or later (AGPL-3.0-or-later).",
        )
        privacy_card.add_widget(
            rich_label(
                "<b>Scripture attribution</b><br>Scripture quotations are taken from the Holy Bible, New Living Translation, copyright ©1996, 2004, 2015 by Tyndale House Foundation. Used by permission of Tyndale House Publishers. All rights reserved."
            )
        )
        privacy_card.add_widget(
            rich_label(
                '<a href="{}">Read required third-party notices</a>'.format(
                    html_module.escape(notices_url, quote=True)
                )
            )
        )
        layout.addWidget(privacy_card)

        recovery_card = SettingsCard("Recovery")
        recovery_card.setMaximumWidth(880)
        recovery = QLabel(
            "⚠ Recovery steps\n\n"
            "1. Export edited Bible verse entries.\n"
            "2. Back up add-on settings.\n"
            "3. Disable the current version before installing an earlier package.\n"
            "4. Restore compatible settings if needed.\n"
            "5. Restart Anki.\n\n"
            "Dashboard settings do not change collection cards or review history."
        )
        recovery.setWordWrap(True)
        recovery_card.add_widget(recovery)
        layout.addWidget(recovery_card)
        layout.addStretch()
        self._add_page("about_support", page)

    def _connect_preview_signals(self) -> None:
        for combo in (
            self.preset,
            self.home_screen_position,
            self.pace_unit,
            self.history_range,
        ):
            combo.currentIndexChanged.connect(self._schedule_preview)
        for segmented in (
            self.mode,
            self.week_start,
            self.calendar_view,
            self.rotation,
            self.theme_color,
        ):
            segmented.connect_changed(self._schedule_preview)
        for spin in (
            self.opacity,
            self.blur,
            self.text_scale,
            self.forecast_days,
            self.font_size,
            self.retention_target,
        ):
            spin.valueChanged.connect(self._schedule_preview)
        checks = list(self.visibility.values()) + [
            self.show_eta,
            self.include_rescheduled,
            self.exclude_reschedules,
            self.exclude_deleted,
            self.show_forecast,
        ]
        for check in checks:
            check.toggled.connect(self._schedule_preview)
        self.ignore_before.dateChanged.connect(self._schedule_preview)
        self.font_family.currentFontChanged.connect(self._font_family_changed)
        self.quote_search.textChanged.connect(self._quote_search_changed)
        self.quote_list.currentRowChanged.connect(self._schedule_preview)
        self.quote_list.currentRowChanged.connect(self._update_quote_detail)
        self.rotation.connect_changed(self._update_quote_actions)

    @staticmethod
    def _place_grid_widgets(
        grid: QGridLayout,
        widgets: List[QWidget],
        columns: int,
    ) -> None:
        while grid.count():
            grid.takeAt(0)
        columns = max(1, columns)
        for index, widget in enumerate(widgets):
            grid.addWidget(widget, index // columns, index % columns)
        for column in range(2):
            grid.setColumnStretch(column, 1 if column < columns else 0)
        grid.invalidate()

    def _reflow_compact_grids(self) -> None:
        large_text = self.fontMetrics().lineSpacing() >= 22
        narrow = self._responsive_bucket == CONTENT_MODE_NARROW
        if hasattr(self, "appearance_grid"):
            width = self.appearance_card.width() if hasattr(self, "appearance_card") else 0
            columns = 1 if narrow or large_text or width < 520 else 2
            self._place_grid_widgets(self.appearance_grid, self.appearance_fields, columns)
        if hasattr(self, "bible_display_grid"):
            width = self.bible_display_card.width()
            columns = 1 if narrow or large_text or width < 520 else 2
            self._place_grid_widgets(self.bible_display_grid, self.bible_display_fields, columns)
        if hasattr(self, "dashboard_jump_links"):
            self.dashboard_jump_links.setVisible(not narrow)
            self.dashboard_jump_selector.setVisible(narrow)

    def _reflow_heatmap_grid(self) -> None:
        if not hasattr(self, "heatmap_preset_grid"):
            return
        large_text = self.fontMetrics().lineSpacing() >= 22
        width = self.heatmap_preset_wrap.width()
        columns = 1 if (
            self._responsive_bucket == CONTENT_MODE_NARROW
            or large_text
            or width < 520
        ) else 2
        buttons = list(self.heatmap_preset_buttons.values())
        self._place_grid_widgets(self.heatmap_preset_grid, buttons, columns)

    def _update_preset_swatch(self) -> None:
        name = _combo_value(self.preset, "Sapphire Glass")
        mode = _combo_value(self.mode, "auto")
        heatmap_name = self._heatmap_preset_preferences.get(
            name,
            DEFAULT_HEATMAP_PRESETS[name],
        )
        tokens = resolve_theme(name, mode, self.controller.is_dark(), heatmap_name)
        colors = [tokens[key] for key in ("background", "surface", "accent", "text")]
        squares = " ".join(
            '<span style="background:{}; border:1px solid {}; color:{};">&nbsp;&nbsp;&nbsp;&nbsp;</span>'.format(
                color, tokens["control_border"], color
            )
            for color in colors
        )
        self.preset_swatch.setText(squares)
        self.preset_swatch.setAccessibleDescription(
            "{} palette: background {}, surface {}, accent {}, and text {}.".format(name, *colors)
        )

    def _dashboard_theme_changed(self, *_args: object) -> None:
        next_theme = _combo_value(self.preset, "Sapphire Glass")
        self._heatmap_theme = next_theme
        self._refresh_heatmap_preset_cards()

    def _select_heatmap_preset(self, preset_name: str) -> None:
        theme_name = _combo_value(self.preset, "Sapphire Glass")
        if preset_name not in HEATMAP_PRESETS[theme_name]:
            preset_name = DEFAULT_HEATMAP_PRESETS[theme_name]
        self._heatmap_preset_preferences[theme_name] = preset_name
        for name, button in self.heatmap_preset_buttons.items():
            active = name == preset_name
            button.setChecked(active)
            button.setProperty("active", active)
            indicator = getattr(self, "heatmap_preset_indicators", {}).get(name)
            if indicator is not None:
                indicator.setVisible(active)
            button.style().unpolish(button)
            button.style().polish(button)
        self._schedule_preview()

    def _refresh_heatmap_preset_cards(self, *_args: object) -> None:
        if not hasattr(self, "heatmap_preset_grid"):
            return
        while self.heatmap_preset_grid.count():
            item = self.heatmap_preset_grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.heatmap_preset_buttons = {}
        self.heatmap_preset_indicators: Dict[str, QLabel] = {}
        theme_name = _combo_value(self.preset, "Sapphire Glass")
        self._heatmap_theme = theme_name
        selected = self._heatmap_preset_preferences.get(
            theme_name,
            DEFAULT_HEATMAP_PRESETS[theme_name],
        )
        if selected not in HEATMAP_PRESETS[theme_name]:
            selected = DEFAULT_HEATMAP_PRESETS[theme_name]
            self._heatmap_preset_preferences[theme_name] = selected
        requested_mode = _combo_value(self.mode, "auto") if hasattr(self, "mode") else "auto"
        variant = "dark" if (
            requested_mode == "dark"
            or (requested_mode == "auto" and self.controller.is_dark())
        ) else "light"
        for preset_name, variants in HEATMAP_PRESETS[theme_name].items():
            button = QPushButton("")
            button.setObjectName("HeatmapPresetCard")
            button.setCheckable(True)
            button.setChecked(preset_name == selected)
            button.setProperty("active", preset_name == selected)
            card_layout = QVBoxLayout(button)
            card_layout.setContentsMargins(4, 3, 4, 3)
            card_layout.setSpacing(6)
            swatches = QHBoxLayout()
            swatches.setSpacing(2)
            tokens = variants[variant]
            for token in ("heatmap_empty", "heatmap_1", "heatmap_2", "heatmap_3", "heatmap_4", "heatmap_5"):
                swatch = QLabel()
                swatch.setFixedSize(22, 18)
                swatch.setStyleSheet(
                    "background: {}; border: 1px solid {}; border-radius: 3px;".format(
                        tokens[token],
                        self._hdo_theme_tokens["border"],
                    )
                )
                swatches.addWidget(swatch)
            swatches.addStretch()
            selected_indicator = QLabel("✓")
            selected_indicator.setAccessibleName("Selected")
            selected_indicator.setVisible(preset_name == selected)
            swatches.addWidget(selected_indicator)
            button.clicked.connect(
                lambda _checked=False, name=preset_name: self._select_heatmap_preset(name)
            )
            _set_accessibility(
                button,
                "{} heat map colors".format(preset_name),
                "Select the {} heatmap palette for {}.".format(preset_name, theme_name),
            )
            card_layout.addLayout(swatches)
            name_label = QLabel(preset_name)
            name_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            card_layout.addWidget(name_label)
            self.heatmap_preset_buttons[preset_name] = button
            self.heatmap_preset_indicators[preset_name] = selected_indicator
        self._reflow_heatmap_grid()

    def _update_color_swatch(self) -> None:
        if not hasattr(self, "font_color_swatch"):
            return
        tokens = getattr(self, "_hdo_theme_tokens", _palette_tokens())
        if (
            not self._font_color_invalid
            and self.font_color.text().strip().upper() != self.font_color_value.upper()
        ):
            self.font_color.setText(self.font_color_value.upper())
        self.font_color_swatch.setText("")
        self.font_color_swatch.setStyleSheet(
            "background: {}; border: 2px solid {}; border-radius: 7px;".format(
                self.font_color_value,
                tokens["border"],
            )
        )
        ratio = _color_contrast(self.font_color_value, tokens["verse_card"])
        custom_enabled = (
            hasattr(self, "theme_color")
            and self.theme_color.value("theme") == "custom"
        )
        if hasattr(self, "font_color_warning"):
            if self._font_color_invalid and custom_enabled:
                self.font_color_warning.setVisible(True)
                self.font_color_warning.setText(
                    "Enter a color in #RRGGBB format before saving."
                )
            else:
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
        stylesheet = _settings_style()
        if self.styleSheet() != stylesheet:
            self.setStyleSheet(stylesheet)
        self._update_preset_swatch()
        self._refresh_heatmap_preset_cards()
        self._update_color_swatch()

    def _update_forecast_range_visibility(self, *_args: object) -> None:
        """Expose the forecast range only while its parent feature is on."""

        visible = self.show_forecast.isChecked()
        self.forecast_days.setEnabled(self.show_forecast.isChecked())
        self.forecast_days.setVisible(visible)
        self.forecast_range_label.setVisible(visible)

    def _update_history_range_visibility(self, *_args: object) -> None:
        """Reveal the custom date only for the explicit Custom range."""

        visible = _combo_value(self.history_range, "all") == "custom"
        self.ignore_before.setEnabled(visible)
        self.ignore_before.setVisible(visible)
        self.history_start_label.setVisible(visible)

    def _update_dependencies(self) -> None:
        state = self.draft.dependency_state
        if not state["bible.font_color"]:
            self._font_color_invalid = False
        self.show_eta.setEnabled(state["study.show_eta"])
        self.visibility["events"].setEnabled(state["visibility.events"])
        self._update_forecast_range_visibility()
        self.font_color.setEnabled(state["bible.font_color"])
        self.font_color_swatch.setEnabled(state["bible.font_color"])
        focus_policy = (
            Qt.FocusPolicy.StrongFocus
            if state["bible.font_color"]
            else Qt.FocusPolicy.NoFocus
        )
        self.font_color.setFocusPolicy(focus_policy)
        self.font_color_swatch.setFocusPolicy(focus_policy)
        if hasattr(self, "custom_color_container"):
            self.custom_color_container.setVisible(state["bible.font_color"])
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
        dirty = (
            self.draft.dirty
            or self.pending_manual_quote is not None
            or self._font_color_invalid
        )
        if self._saving:
            return
        if self.save_button is not None:
            self.save_button.setEnabled(dirty and not self._font_color_invalid)
        if hasattr(self, "save_shortcut"):
            self.save_shortcut.setEnabled(dirty and not self._font_color_invalid)
        if self.close_button is not None:
            self.close_button.setText("Discard changes" if dirty else "Close")
        if dirty:
            if self._font_color_invalid:
                self._set_status("error", "Enter a valid #RRGGBB color")
                return
            count = self.draft.changed_leaf_count + (1 if self.pending_manual_quote is not None else 0)
            self._set_status(
                "dirty",
                "● {} unsaved change{}".format(count, "" if count == 1 else "s"),
            )
        else:
            self.dirty_badge.hide()

    def _set_status(self, state: str, text: str) -> None:
        self.dirty_badge.setProperty("state", state)
        self.dirty_badge.setText(text)
        self.dirty_badge.setAccessibleDescription(text)
        self.dirty_badge.show()
        self.dirty_badge.style().unpolish(self.dirty_badge)
        self.dirty_badge.style().polish(self.dirty_badge)

    def _reset_current_section(self) -> None:
        self._reset_card(self.current_section, SECTION_LABELS.get(self.current_section, "Section"))

    def _reset_card(self, scope: str, label: str) -> None:
        self._sync_draft()
        before = deepcopy(self.draft.values)
        if not self.draft.reset_card(scope):
            return
        self._reset_undo_values = before
        self._undo_event_status_id = ""
        self.staged = deepcopy(self.draft.values)
        self.quotes = list(self.staged["bible"]["quotes"])
        self._apply_config_to_widgets(self.staged)
        self._sync_draft()
        self.undo_message.setText("{} reset to defaults.".format(label))
        self.undo_toast.show()
        self.undo_timer.start()
        self._schedule_preview()

    def _undo_reset(self) -> None:
        if self._reset_undo_values is None:
            return
        self.draft.replace_values(self._reset_undo_values)
        self._reset_undo_values = None
        if self._undo_event_status_id:
            self._staged_archived_event_ids.discard(self._undo_event_status_id)
            self._undo_event_status_id = ""
        self.staged = deepcopy(self.draft.values)
        self.quotes = list(self.staged["bible"]["quotes"])
        self._apply_config_to_widgets(self.staged)
        self.undo_toast.hide()
        self._sync_draft()
        self._schedule_preview()

    def _week_start_changed(self, *_args: object) -> None:
        if not self._building:
            self._week_start_touched = True

    @staticmethod
    def _set_combo_data(combo: QWidget, value: object) -> None:
        if isinstance(combo, SegmentedControl):
            combo.setValue(value)
            return
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
            self.blur.setValue(int(appearance.get("blur", 18)))
            self.text_scale.setValue(int(appearance["text_scale"]))
            self._set_combo_data(
                self.home_screen_position,
                config["home_screen"]["position"],
            )
            for key, box in self.visibility.items():
                box.setChecked(bool(config["visibility"][key]))
            self._set_combo_data(self.pace_unit, config["study"]["pace_unit"])
            self.show_eta.setChecked(bool(config["study"]["show_eta"]))
            self.retention_target.setValue(int(config["study"].get("retention_target", 80)))
            self.include_rescheduled.setChecked(
                bool(config["new_cards"]["include_rescheduled"])
            )
            heatmap = config["heatmap"]
            self._heatmap_preset_preferences = deepcopy(
                heatmap.get("presets_by_theme", {})
            )
            self._set_combo_data(self.calendar_view, heatmap["calendar_view"])
            self._legacy_week_start_value = str(heatmap["week_start"])
            self._week_start_touched = False
            self._set_combo_data(self.week_start, self._legacy_week_start_value)
            history_choice = history_range_choice(
                heatmap.get("history_days", 0), heatmap.get("ignore_before", "")
            )
            self._set_combo_data(self.history_range, history_choice)
            self.forecast_days.setValue(int(heatmap["forecast_days"]))
            self.show_forecast.setChecked(bool(heatmap["show_due_forecast"]))
            parsed = QDate.fromString(str(heatmap["ignore_before"]), "yyyy-MM-dd")
            if parsed.isValid():
                self.ignore_before.setDate(parsed)
            self._update_forecast_range_visibility()
            self._update_history_range_visibility()
            self.exclude_reschedules.setChecked(bool(heatmap["exclude_manual_reschedules"]))
            self.exclude_deleted.setChecked(bool(heatmap["exclude_deleted_cards"]))
            self._apply_deck_exclusions(heatmap["excluded_deck_ids"])
            self._refresh_heatmap_preset_cards()
            self._set_combo_data(self.event_sort, config["events"]["sort"])
            bible = config["bible"]
            family_name = str(bible["font_family"]).split(",", 1)[0].strip().strip('"\'')
            family_index = self.font_family.findText(family_name)
            if family_index >= 0:
                self.font_family.setCurrentIndex(family_index)
            self.font_size.setValue(int(str(bible["font_size"]).replace("px", "")))
            self.font_color_value = str(bible["font_color"])
            self._font_color_invalid = False
            self.font_color.setText(self.font_color_value.upper())
            self.theme_color.setValue(
                "theme" if bible["theme_aware_color"] else "custom"
            )
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

    def _walk_deck_items(self) -> List[QTreeWidgetItem]:
        items: List[QTreeWidgetItem] = []
        pending = [
            self.deck_tree.topLevelItem(row)
            for row in range(self.deck_tree.topLevelItemCount() - 1, -1, -1)
        ]
        while pending:
            item = pending.pop()
            items.append(item)
            pending.extend(
                item.child(row) for row in range(item.childCount() - 1, -1, -1)
            )
        return items

    @staticmethod
    def _deck_item_is_checkable(item: QTreeWidgetItem) -> bool:
        return bool(item.flags() & Qt.ItemFlag.ItemIsUserCheckable)

    def _new_deck_item(
        self,
        parent: Optional[QTreeWidgetItem],
        label: str,
        path: str,
    ) -> QTreeWidgetItem:
        item = QTreeWidgetItem(parent if parent is not None else self.deck_tree, [label])
        item.setFlags(
            item.flags()
            | Qt.ItemFlag.ItemIsUserCheckable
            | Qt.ItemFlag.ItemIsEnabled
            | Qt.ItemFlag.ItemIsSelectable
        )
        item.setCheckState(0, Qt.CheckState.Unchecked)
        item.setData(0, DECK_PATH_ROLE, path)
        item.setData(0, DECK_FILTER_MATCH_ROLE, True)
        accessible_path = path.replace("::", " › ")
        item.setData(0, Qt.ItemDataRole.AccessibleTextRole, accessible_path)
        item.setData(
            0,
            Qt.ItemDataRole.AccessibleDescriptionRole,
            "Full deck path: {}".format(accessible_path),
        )
        item.setData(0, SETTINGS_ROW_PRIMITIVE_ROLE, _settings_primitive("list-or-table-row"))
        item.setData(0, SETTINGS_ROW_FOCUS_RING_ROLE, FOCUS_RING_PX)
        item.setData(0, SETTINGS_ROW_FOCUS_OFFSET_ROLE, FOCUS_RING_OFFSET_PX)
        item.setToolTip(0, path)
        return item

    def _populate_deck_tree(self, excluded_ids: object) -> None:
        self.deck_tree.clear()
        self._deck_items_by_id.clear()
        self._deck_unavailable_group = None
        by_path: Dict[str, QTreeWidgetItem] = {}
        try:
            decks = mw.col.decks.all_names_and_ids() if mw.col else []
        except Exception:
            decks = []
        for deck in sorted(
            decks,
            key=lambda value: str(getattr(value, "name", "")).casefold(),
        ):
            full_name = str(getattr(deck, "name", "")).strip()
            try:
                deck_id = int(getattr(deck, "id", 0))
            except (TypeError, ValueError, OverflowError):
                continue
            if not full_name or deck_id <= 0:
                continue
            parent: Optional[QTreeWidgetItem] = None
            path_parts: List[str] = []
            for part in full_name.split("::"):
                path_parts.append(part)
                path = "::".join(path_parts)
                item = by_path.get(path)
                if item is None:
                    item = self._new_deck_item(parent, part, path)
                    by_path[path] = item
                parent = item
            if parent is not None:
                parent.setData(0, Qt.ItemDataRole.UserRole, deck_id)
                self._deck_items_by_id[deck_id] = parent
        self._apply_deck_exclusions(excluded_ids)
        self.deck_tree.collapseAll()
        _apply_view_row_targets(self.deck_tree)

    def _set_deck_subtree_state(
        self,
        item: QTreeWidgetItem,
        state: Qt.CheckState,
    ) -> None:
        if self._deck_item_is_checkable(item):
            item.setCheckState(0, state)
        for row in range(item.childCount()):
            self._set_deck_subtree_state(item.child(row), state)

    def _recalculate_deck_item(self, item: QTreeWidgetItem) -> Qt.CheckState:
        child_states = [
            self._recalculate_deck_item(item.child(row))
            for row in range(item.childCount())
            if self._deck_item_is_checkable(item.child(row))
        ]
        if child_states and self._deck_item_is_checkable(item):
            if all(state == Qt.CheckState.Checked for state in child_states):
                item.setCheckState(0, Qt.CheckState.Checked)
            elif all(state == Qt.CheckState.Unchecked for state in child_states):
                item.setCheckState(0, Qt.CheckState.Unchecked)
            else:
                item.setCheckState(0, Qt.CheckState.PartiallyChecked)
        return item.checkState(0) if self._deck_item_is_checkable(item) else Qt.CheckState.Unchecked

    def _recalculate_deck_tree(self) -> None:
        for row in range(self.deck_tree.topLevelItemCount()):
            self._recalculate_deck_item(self.deck_tree.topLevelItem(row))

    def _ensure_unavailable_decks(self, deck_ids: List[int]) -> None:
        if self._deck_unavailable_group is not None:
            index = self.deck_tree.indexOfTopLevelItem(self._deck_unavailable_group)
            if index >= 0:
                self.deck_tree.takeTopLevelItem(index)
            self._deck_unavailable_group = None
        if not deck_ids:
            return
        group = QTreeWidgetItem(self.deck_tree, ["Unavailable"])
        group.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        group.setData(0, DECK_PATH_ROLE, "Unavailable")
        group.setData(0, DECK_FILTER_MATCH_ROLE, True)
        group.setData(0, Qt.ItemDataRole.AccessibleTextRole, "Unavailable decks")
        group.setData(
            0,
            Qt.ItemDataRole.AccessibleDescriptionRole,
            "Saved deck exclusions that are unavailable in this collection.",
        )
        group.setData(0, SETTINGS_ROW_PRIMITIVE_ROLE, _settings_primitive("list-or-table-row"))
        group.setData(0, SETTINGS_ROW_FOCUS_RING_ROLE, FOCUS_RING_PX)
        group.setData(0, SETTINGS_ROW_FOCUS_OFFSET_ROLE, FOCUS_RING_OFFSET_PX)
        group.setToolTip(0, "Stored deck identifiers that are not available in this collection")
        for position, deck_id in enumerate(sorted(deck_ids), start=1):
            item = self._new_deck_item(
                group,
                "Unavailable deck {}".format(position),
                "Unavailable deck {}".format(position),
            )
            item.setData(0, Qt.ItemDataRole.UserRole, deck_id)
            item.setData(0, DECK_UNAVAILABLE_ROLE, True)
            item.setCheckState(0, Qt.CheckState.Checked)
        self._deck_unavailable_group = group

    def _apply_deck_exclusions(self, excluded_ids: object) -> None:
        parsed: List[int] = []
        if isinstance(excluded_ids, list):
            for value in excluded_ids:
                try:
                    deck_id = int(value)
                except (TypeError, ValueError, OverflowError):
                    continue
                if deck_id > 0 and deck_id not in parsed:
                    parsed.append(deck_id)
        self._updating_deck_tree = True
        try:
            self._ensure_unavailable_decks(
                [deck_id for deck_id in parsed if deck_id not in self._deck_items_by_id]
            )
            for item in self._walk_deck_items():
                if self._deck_item_is_checkable(item):
                    item.setCheckState(0, Qt.CheckState.Unchecked)
            for deck_id in parsed:
                item = self._deck_items_by_id.get(deck_id)
                if item is None and self._deck_unavailable_group is not None:
                    for row in range(self._deck_unavailable_group.childCount()):
                        candidate = self._deck_unavailable_group.child(row)
                        if int(candidate.data(0, Qt.ItemDataRole.UserRole)) == deck_id:
                            item = candidate
                            break
                if item is not None:
                    self._set_deck_subtree_state(item, Qt.CheckState.Checked)
            self._recalculate_deck_tree()
        finally:
            self._updating_deck_tree = False
        _apply_view_row_targets(self.deck_tree)

    def _deck_item_changed(self, item: QTreeWidgetItem, _column: int) -> None:
        if self._updating_deck_tree or not self._deck_item_is_checkable(item):
            return
        state = item.checkState(0)
        if state == Qt.CheckState.PartiallyChecked:
            return
        self._updating_deck_tree = True
        try:
            self._set_deck_subtree_state(item, state)
            parent = item.parent()
            while parent is not None:
                self._recalculate_deck_item(parent)
                parent = parent.parent()
        finally:
            self._updating_deck_tree = False
        self._update_deck_exclusion_summary()

    def _minimal_excluded_deck_ids(self) -> List[int]:
        selected: List[int] = []
        for item in self._walk_deck_items():
            deck_id = item.data(0, Qt.ItemDataRole.UserRole)
            if not isinstance(deck_id, int) or item.checkState(0) != Qt.CheckState.Checked:
                continue
            parent = item.parent()
            covered = False
            while parent is not None:
                parent_id = parent.data(0, Qt.ItemDataRole.UserRole)
                if isinstance(parent_id, int) and parent.checkState(0) == Qt.CheckState.Checked:
                    covered = True
                    break
                parent = parent.parent()
            if not covered:
                selected.append(deck_id)
        return selected

    def _set_visible_decks(self, state: Qt.CheckState) -> None:
        self._updating_deck_tree = True
        try:
            for item in self._walk_deck_items():
                if (
                    self._deck_item_is_checkable(item)
                    and not item.isHidden()
                    and bool(item.data(0, DECK_FILTER_MATCH_ROLE))
                ):
                    self._set_deck_subtree_state(item, state)
            self._recalculate_deck_tree()
        finally:
            self._updating_deck_tree = False
        self._update_deck_exclusion_summary()

    def _remove_unavailable_deck_exclusions(self) -> None:
        group = self._deck_unavailable_group
        if group is None:
            return
        self._updating_deck_tree = True
        try:
            for row in range(group.childCount()):
                child = group.child(row)
                if self._deck_item_is_checkable(child):
                    child.setCheckState(0, Qt.CheckState.Unchecked)
        finally:
            self._updating_deck_tree = False
        index = self.deck_tree.indexOfTopLevelItem(group)
        if index >= 0:
            self.deck_tree.takeTopLevelItem(index)
        self._deck_unavailable_group = None
        self._update_deck_exclusion_summary()

    def _update_deck_exclusion_summary(self, *_args: object) -> None:
        excluded_ids = self._minimal_excluded_deck_ids()
        shown = 0
        shown_excluded = 0
        for item in self._walk_deck_items():
            deck_id = item.data(0, Qt.ItemDataRole.UserRole)
            if (
                isinstance(deck_id, int)
                and not item.isHidden()
                and bool(item.data(0, DECK_FILTER_MATCH_ROLE))
            ):
                shown += 1
                if item.checkState(0) == Qt.CheckState.Checked:
                    shown_excluded += 1
        self.deck_exclusion_summary.setText(
            "{} deck exclusion{} · {} of {} filtered decks excluded".format(
                len(excluded_ids),
                "" if len(excluded_ids) == 1 else "s",
                shown_excluded,
                shown,
            )
        )
        self.deck_exclusion_summary.setAccessibleDescription(
            self.deck_exclusion_summary.text()
        )
        if hasattr(self, "remove_unavailable_decks"):
            self.remove_unavailable_decks.setVisible(
                self._deck_unavailable_group is not None
                and self._deck_unavailable_group.childCount() > 0
            )
        if hasattr(self, "preview_timer"):
            self._schedule_preview()

    def _filter_decks(self, value: str) -> None:
        needle = value.strip().casefold()

        def visit(item: QTreeWidgetItem) -> bool:
            path = str(item.data(0, DECK_PATH_ROLE) or item.text(0))
            own_match = not needle or needle in path.casefold()
            child_match = False
            for row in range(item.childCount()):
                child_match = visit(item.child(row)) or child_match
            visible = own_match or child_match
            item.setHidden(not visible)
            item.setData(0, DECK_FILTER_MATCH_ROLE, own_match)
            if needle and child_match:
                item.setExpanded(True)
            return visible

        for row in range(self.deck_tree.topLevelItemCount()):
            visit(self.deck_tree.topLevelItem(row))
        if not needle:
            self.deck_tree.collapseAll()
        self._update_deck_exclusion_summary()

    def _choose_font_color(self) -> None:
        selected = QColorDialog.getColor(parent=self, title="Choose Bible verse color")
        if not selected.isValid():
            return
        self._font_color_invalid = False
        self.font_color_value = selected.name()
        self.font_color.setText(self.font_color_value.upper())
        self._update_color_swatch()
        self._schedule_preview()

    def _font_color_edited(self) -> None:
        candidate = self.font_color.text().strip()
        if re.fullmatch(r"#[0-9A-Fa-f]{6}", candidate):
            self._font_color_invalid = False
            self.font_color_value = candidate.lower()
            self.font_color.setText(candidate.upper())
            self._update_color_swatch()
            self._schedule_preview()
        else:
            self._font_color_invalid = True
            self.font_color_warning.setVisible(True)
            self.font_color_warning.setText("Enter a color in #RRGGBB format before saving.")
            self._update_dirty_state()

    def _font_color_text_changed(self, value: str) -> None:
        if self._building:
            return
        if not re.fullmatch(r"#[0-9A-Fa-f]{6}", value.strip()):
            self._font_color_invalid = self.theme_color.value("theme") == "custom"
            self._update_dirty_state()
            return
        self._font_color_invalid = False
        candidate = value.strip().lower()
        if candidate == self.font_color_value.lower():
            return
        self.font_color_value = candidate
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
            blur=self.blur.value(),
            text_scale=self.text_scale.value(),
        )
        config["home_screen"]["position"] = _combo_value(
            self.home_screen_position,
            "top",
        )
        for key, box in self.visibility.items():
            config["visibility"][key] = box.isChecked()
        config["study"].update(
            pace_unit=_combo_value(self.pace_unit, "seconds_per_card"),
            show_eta=self.show_eta.isChecked(),
            retention_target=self.retention_target.value(),
        )
        config["new_cards"].update(include_rescheduled=self.include_rescheduled.isChecked())
        excluded = self._minimal_excluded_deck_ids()
        history_days, ignore_before = history_range_values(
            _combo_value(self.history_range, "all"),
            self.ignore_before.date().toString("yyyy-MM-dd"),
        )
        config["heatmap"].update(
            calendar_view=_combo_value(self.calendar_view, "year"),
            week_start=int(
                _combo_value(self.week_start, "0")
                if self._week_start_touched
                else self._legacy_week_start_value
            ),
            history_days=history_days,
            forecast_days=self.forecast_days.value(),
            ignore_before=ignore_before,
            exclude_manual_reschedules=self.exclude_reschedules.isChecked(),
            exclude_deleted_cards=self.exclude_deleted.isChecked(),
            excluded_deck_ids=excluded,
            show_due_forecast=self.show_forecast.isChecked(),
            presets_by_theme=deepcopy(self._heatmap_preset_preferences),
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
            theme_aware_color=self.theme_color.value("theme") == "theme",
            rotation_mode=_combo_value(self.rotation, "daily"),
        )
        return normalize_config(config)

    def _contextual_preview_config(self) -> Dict[str, Any]:
        config = deepcopy(self.draft.values)
        config["_preview_variant"] = (
            "complete"
            if self._preview_scope_mode == "full"
            else self._preview_context
        )
        if self.current_section == "events":
            selected = self._selected_event()
            selected_date = (
                str(selected.get("date")) if selected is not None else self.selected_event_date
            )
            if selected_date:
                config["_preview_selected_date"] = selected_date
        return config

    def _render_preview(self) -> None:
        if self.current_section in {"events", "about_support"} or not self.preview_wrap.isVisible():
            return
        self._sync_draft()
        config = self._contextual_preview_config()
        snapshot = self.controller.snapshot
        preview_date = date.today().isoformat()
        if snapshot is not None:
            for candidate in (
                snapshot.facts.scheduling_date,
                snapshot.facts.calendar_date,
            ):
                try:
                    preview_date = date.fromisoformat(str(candidate)).isoformat()
                    break
                except (TypeError, ValueError):
                    continue
        if snapshot is None:
            snapshot = representative_preview_snapshot(preview_date)
        snapshot = preview_snapshot_with_staged_events(snapshot, config, preview_date)
        selected_quote = self._selected_quote_index()
        bible_missing = self.current_section == "bible_verse" and selected_quote is None
        self.preview_empty_label.setVisible(bible_missing)
        self.preview.setVisible(not bible_missing)
        if bible_missing:
            return
        if self.current_section == "bible_verse":
            snapshot = replace(snapshot, verse=verse_content(self.quotes[selected_quote]))
        self.preview_label.setText(
            "Bible verse preview" if self.current_section == "bible_verse" else "Dashboard preview"
        )
        self.preview_sample_badge.setVisible(
            self.current_section == "dashboard" and self.controller.snapshot is None
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
        QTimer.singleShot(180, self._fit_inline_preview)
        QTimer.singleShot(260, self._measure_preview_content)

    def _open_full_preview(self) -> None:
        """Open a temporary full-size production preview from cached facts."""

        self._sync_draft()
        config = self._contextual_preview_config()
        config.pop("_preview_variant", None)
        snapshot = self.controller.snapshot
        preview_date = date.today().isoformat()
        if snapshot is not None:
            for candidate in (snapshot.facts.scheduling_date, snapshot.facts.calendar_date):
                try:
                    preview_date = date.fromisoformat(str(candidate)).isoformat()
                    break
                except (TypeError, ValueError):
                    continue
        if snapshot is None:
            snapshot = representative_preview_snapshot(preview_date)
        snapshot = preview_snapshot_with_staged_events(snapshot, config, preview_date)
        selected_quote = self._selected_quote_index()
        if self.current_section == "bible_verse" and selected_quote is not None:
            snapshot = replace(snapshot, verse=verse_content(self.quotes[selected_quote]))
        return_focus = QApplication.focusWidget()
        dialog = QDialog(self)
        dialog.setWindowTitle("Home Screen Dashboard full preview")
        dialog.setObjectName("HomeDashboardSettings")
        dialog.setModal(True)
        screen = self.screen() or QApplication.primaryScreen()
        available = screen.availableGeometry() if screen is not None else None
        if available is not None:
            dialog.resize(
                max(720, round(available.width() * .9)),
                max(560, round(available.height() * .9)),
            )
        else:
            dialog.resize(980, 720)
        outer = QVBoxLayout(dialog)
        web = AnkiWebView(dialog, title="Home Screen Dashboard full preview")
        web.setAccessibleName("Full Home Screen Dashboard preview")
        package = mw.addonManager.addonFromModule(__name__)
        base = "/_addons/{}/web/".format(package)
        web.stdHtml(
            render_dashboard(
                snapshot,
                config,
                anki_dark=self.controller.is_dark(),
                preview=True,
            ),
            css=[base + "dashboard.css"],
            js=[base + "dashboard.js"],
            context=dialog,
        )
        outer.addWidget(web, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.reject)
        outer.addWidget(buttons)
        dialog.setStyleSheet(self._current_stylesheet())
        dialog.exec()
        if isinstance(return_focus, QWidget) and return_focus.isVisible():
            return_focus.setFocus(Qt.FocusReason.OtherFocusReason)

    def _inline_preview_script(self) -> str:
        use_actual = "true" if self._preview_fit_mode == "actual" else "false"
        variant = (
            "complete"
            if self._preview_scope_mode == "full"
            else "bible_verse" if self.current_section == "bible_verse" else self._preview_context
        )
        section_selector = {
            "calendar": ".hdo-calendar-card",
            "study_calculations": ".hdo-summary-metrics-grid",
            "bible_verse": ".hdo-bible-card",
        }.get(variant, "")
        emphasis_selector = {
            "visibility_heatmap": ".hdo-calendar-card",
            "visibility_remaining": 'section[aria-labelledby="hdo-progress-title"]',
            "visibility_today": 'section[aria-labelledby="hdo-session-title"]',
            "visibility_heatmap_metrics": 'section[aria-labelledby="hdo-last-seven-title"], section[aria-labelledby="hdo-all-time-title"]',
            "visibility_bible": ".hdo-bible-card",
        }.get(variant, "")
        return """
(function () {
  var root = document.getElementById('hdo-dashboard');
  var stack = root && root.querySelector('.hdo-stack');
  if (!root || !stack) return null;
  document.documentElement.style.overflowX = 'hidden';
  document.documentElement.style.overflowY = 'auto';
  document.body.style.overflowX = 'hidden';
  document.body.style.overflowY = 'auto';
  document.body.style.margin = '0';
  document.body.style.minHeight = '0';
  document.body.style.background = getComputedStyle(root).getPropertyValue('--hdo-bg');
  root.style.zoom = '1';
  root.style.maxWidth = 'none';
  root.style.minHeight = '0';
  var selector = %s;
  var emphasisSelector = %s;
  var target = selector ? document.querySelector(selector) : null;
  var focusOnly = Boolean(target);
  var viewportWidth = Math.max(1, document.documentElement.clientWidth);
  var useActual = %s;
  var naturalWidth = focusOnly ? viewportWidth : (useActual ? 1000 : viewportWidth);
  root.style.width = naturalWidth + 'px';
  if (focusOnly && target) {
    Array.prototype.forEach.call(stack.children, function (child) {
      child.style.display = child === target ? '' : 'none';
    });
  }
  if (emphasisSelector) {
    Array.prototype.forEach.call(document.querySelectorAll(emphasisSelector), function (node) {
      node.style.outline = '3px solid var(--hdo-accent)';
      node.style.outlineOffset = '3px';
    });
  }
  var naturalHeight = Math.ceil(Math.max(120, stack.scrollHeight + 12));
  root.dataset.hdoSettingsPreviewFit = useActual ? 'actual-size' : 'fit';
  return {
    width: naturalWidth,
    height: naturalHeight,
    renderedWidth: naturalWidth,
    renderedHeight: naturalHeight,
    scale: 1
  };
})()
""" % (
            json.dumps(section_selector),
            json.dumps(emphasis_selector),
            use_actual,
        )

    def _fit_inline_preview(self) -> None:
        if not self.preview_wrap.isVisible():
            return
        try:
            self.preview.eval(self._inline_preview_script())
        except Exception:
            return

    def _measure_preview_content(self) -> None:
        if not self.preview_wrap.isVisible():
            return
        script = self._inline_preview_script()

        def measured(value: object) -> None:
            if not isinstance(value, Mapping):
                return
            try:
                width = max(1, int(value.get("width", 0)))
                height = max(1, int(value.get("renderedHeight", value.get("height", 0))))
            except (TypeError, ValueError, OverflowError):
                return
            next_size = QSize(width, height)
            if next_size == self._preview_content_size:
                return
            self._preview_content_size = next_size
            self.preview.setFixedHeight(max(160, min(520, height)))
            self.preview_wrap.updateGeometry()
            QTimer.singleShot(0, self._fit_inline_preview)

        try:
            self.preview.evalWithCallback(script, measured)
        except Exception:
            return

    def _selected_event(self) -> Optional[MutableMapping[str, Any]]:
        widget = self.active_events if self.event_tabs.currentIndex() == 0 else self.archived_events
        item = widget.currentItem()
        event_id = item.data(0, Qt.ItemDataRole.UserRole) if item else None
        for event in self.staged["events"]["items"]:
            if str(event.get("id")) == str(event_id): return event
        return None

    def _refresh_event_lists(
        self,
        *_args: object,
        select_event_id: Optional[str] = None,
        select_archived: Optional[bool] = None,
    ) -> None:
        previously_selected = self._selected_event() if hasattr(self, "event_tabs") else None
        if select_event_id is None and previously_selected is not None:
            select_event_id = str(previously_selected.get("id"))
            select_archived = bool(previously_selected.get("archived"))
        self.active_events.clear(); self.archived_events.clear()
        needle = self.event_search.text().strip().casefold() if hasattr(self, "event_search") else ""
        reverse = _combo_value(self.event_sort, "ascending") == "descending" if hasattr(self, "event_sort") else False
        events = sorted(self.staged["events"]["items"], key=lambda item: (item["date"], item["name"].casefold()), reverse=reverse)
        for event in events:
            if needle and needle not in event["name"].casefold() and needle not in event["date"]: continue
            event_id = str(event["id"])
            if event_id in self._staged_new_event_ids:
                status = "New"
            elif event_id in self._staged_edited_event_ids:
                status = "Edited"
            elif event_id in self._staged_archived_event_ids:
                status = "Archived" if event.get("archived") else "Restored"
            else:
                status = ""
            item = SettingsTableRow(
                [_display_date(event["date"]), event["name"], ""],
                event["id"],
                [
                    "{} ({})".format(_display_date(event["date"]), event["date"]),
                    event["name"],
                    "Event actions",
                ],
            )
            item.setData(0, EVENT_DATE_ROLE, _display_date(event["date"]))
            item.setData(0, EVENT_NAME_ROLE, event["name"])
            item.setData(0, EVENT_STATUS_ROLE, status)
            tree = self.archived_events if event.get("archived") else self.active_events
            tree.addTopLevelItem(item)
            self._attach_event_menu(tree, item, event_id, bool(event.get("archived")))
        _apply_view_row_targets(self.active_events)
        _apply_view_row_targets(self.archived_events)
        self.event_tabs.setTabText(0, "Active ({})".format(self.active_events.topLevelItemCount()))
        self.event_tabs.setTabText(1, "Archived ({})".format(self.archived_events.topLevelItemCount()))
        if hasattr(self, "event_toolbar_wrap"):
            self.event_toolbar_wrap.setVisible(bool(self.staged["events"]["items"]))
        if select_event_id is not None:
            self._select_event_id(select_event_id, bool(select_archived))
        self._apply_event_layout(self._responsive_bucket or CONTENT_MODE_EXTRA_WIDE)
        self._schedule_preview()
        self._update_event_actions()

    def _attach_event_menu(
        self,
        tree: QTreeWidget,
        item: QTreeWidgetItem,
        event_id: str,
        archived: bool,
    ) -> None:
        button = QPushButton("•••")
        button.setObjectName("LinkButton")
        button.setFixedWidth(42)
        _set_accessibility(
            button,
            "Actions for {}".format(item.data(0, EVENT_NAME_ROLE)),
            "Edit, {}, or delete this event.".format("restore" if archived else "archive"),
        )

        def open_menu() -> None:
            tree.setCurrentItem(item)
            menu = QMenu(button)
            edit_action = menu.addAction("Edit")
            archive_action = menu.addAction("Restore" if archived else "Archive")
            menu.addSeparator()
            delete_action = menu.addAction("Delete")
            edit_action.triggered.connect(
                lambda: self._invoke_event_action(event_id, archived, "edit")
            )
            archive_action.triggered.connect(
                lambda: self._invoke_event_action(event_id, archived, "archive")
            )
            delete_action.triggered.connect(
                lambda: self._invoke_event_action(event_id, archived, "delete")
            )
            menu.exec(button.mapToGlobal(QPoint(0, button.height())))

        button.clicked.connect(open_menu)
        tree.setItemWidget(item, 2, button)

    def _invoke_event_action(self, event_id: str, archived: bool, action: str) -> None:
        if not self._select_event_id(event_id, archived):
            return
        if action == "edit":
            self._edit_event()
        elif action == "archive":
            self._toggle_event_archive()
        elif action == "delete":
            self._delete_event()

    def _select_event_id(self, event_id: str, archived: bool) -> bool:
        self.event_tabs.setCurrentIndex(1 if archived else 0)
        widget = self.archived_events if archived else self.active_events
        for row in range(widget.topLevelItemCount()):
            item = widget.topLevelItem(row)
            if str(item.data(0, Qt.ItemDataRole.UserRole)) == str(event_id):
                widget.setCurrentItem(item)
                widget.scrollToItem(item)
                return True
        return False

    def _update_event_actions(self, *_args: object) -> None:
        archived = self.event_tabs.currentIndex() == 1
        current_tree = self.archived_events if archived else self.active_events
        row_count = current_tree.topLevelItemCount()
        current_tree.setVisible(row_count > 0)
        tab_height = self.event_tabs.tabBar().sizeHint().height()
        if row_count:
            row_height = (
                max(58, 3 * current_tree.fontMetrics().lineSpacing())
                if self._responsive_bucket == CONTENT_MODE_NARROW
                else _row_target_height(current_tree)
            )
            table_height = (
                (0 if self._responsive_bucket == CONTENT_MODE_NARROW else current_tree.header().sizeHint().height())
                + min(row_count, 6) * row_height
                + self.fontMetrics().lineSpacing()
            )
        else:
            table_height = 2
        self.event_tabs.setMaximumHeight(tab_height + table_height)
        if row_count == 0:
            kind = "archived" if archived else "active"
            if self.event_search.text().strip():
                self.event_empty_title.setText("No matching events")
                self.event_empty_copy.setText(
                    "No {} events match this search. Clear the search to see all events.".format(kind)
                )
                self.event_empty_icon.setText("⌕")
                self.event_empty_add.hide()
            elif not self.staged["events"]["items"]:
                self.event_empty_title.setText("No events yet")
                self.event_empty_copy.setText(
                    "Add an event to show a marker and upcoming-event context on the dashboard calendar."
                )
                self.event_empty_icon.setText("◇")
                self.event_empty_add.show()
            else:
                self.event_empty_title.setText("No {} events".format(kind))
                self.event_empty_copy.setText(
                    "{} events will appear here.".format(kind.capitalize())
                )
                self.event_empty_icon.setText("◇")
                self.event_empty_add.hide()
            self.event_empty_state.show()
        else:
            self.event_empty_state.hide()
        empty_library = not bool(self.staged["events"]["items"])
        self.event_add.setVisible(not empty_library)
        self._schedule_preview()

    def _select_event_date(self, selected_date: str) -> None:
        self.selected_event_date = selected_date
        display_date = _display_date(selected_date)
        self.event_date_context.setText("Selected date · {}".format(display_date))
        self.event_date_context.show()
        self.event_add.setText("Add Event")
        self.event_add.setAccessibleName("Add Event for {}".format(display_date))
        matching_id = None
        archived = False
        for event in self.staged["events"]["items"]:
            if event.get("date") == selected_date:
                matching_id = str(event.get("id"))
                archived = bool(event.get("archived"))
                break
        if matching_id is None:
            self.event_tabs.setCurrentIndex(0)
            widget = self.active_events
            widget.clearSelection()
            return
        self._select_event_id(matching_id, archived)

    def _add_event(self) -> None:
        dialog = EventEditDialog(self, initial_date=self.selected_event_date)
        if dialog.exec() != QDialog.DialogCode.Accepted: return
        name, event_date = dialog.values()
        self.selected_event_date = event_date
        event_id = "event-{}".format(time.time_ns())
        self.staged["events"]["items"].append({"id": event_id, "name": name, "date": event_date, "archived": False, "created_at": datetime.now().astimezone().isoformat(timespec="seconds"), "archived_at": ""})
        self._staged_new_event_ids.add(event_id)
        self._refresh_event_lists(select_event_id=event_id, select_archived=False)
        self._set_event_feedback("Added ‘{}’ for {}. Save to keep this change.".format(name, _display_date(event_date)))

    def _edit_event(self) -> None:
        event = self._selected_event()
        if event is None: return
        dialog = EventEditDialog(self, event)
        if dialog.exec() != QDialog.DialogCode.Accepted: return
        event_id = str(event["id"])
        event["name"], event["date"] = dialog.values()
        if event_id not in self._staged_new_event_ids:
            self._staged_edited_event_ids.add(event_id)
        self._refresh_event_lists(select_event_id=event_id, select_archived=bool(event.get("archived")))
        self._set_event_feedback("Updated ‘{}’. Save to keep this change.".format(event["name"]))

    def _toggle_event_archive(self) -> None:
        event = self._selected_event()
        if event is None: return
        event_id = str(event["id"])
        self._reset_undo_values = deepcopy(self.staged)
        self._undo_event_status_id = event_id
        self._staged_archived_event_ids.add(event_id)
        event["archived"] = not bool(event.get("archived")); event["archived_at"] = datetime.now().astimezone().isoformat(timespec="seconds") if event["archived"] else ""; self._refresh_event_lists(select_event_id=event_id, select_archived=bool(event["archived"]))
        action = "Archived" if event["archived"] else "Restored"
        destination = "Archived" if event["archived"] else "Active"
        self._set_event_feedback("{} ‘{}’. Moved to {}. Save to keep this change.".format(action, event["name"], destination))
        self.undo_message.setText("{} ‘{}’.".format(action, event["name"]))
        self.undo_toast.show()
        self.undo_timer.start()

    def _delete_event(self) -> None:
        event = self._selected_event()
        if event is None: return
        if QMessageBox.question(
            self,
            "Delete event?",
            "Delete ‘{}’? This destructive change remains staged until you choose Save changes.".format(event["name"]),
        ) != QMessageBox.StandardButton.Yes:
            return
        name = event["name"]
        self.staged["events"]["items"].remove(event); self._refresh_event_lists()
        self._set_event_feedback("Deleted ‘{}’. Save to keep this change.".format(name))

    def _set_event_feedback(self, message: str) -> None:
        self.event_action_feedback.setText(message)
        self.event_action_feedback.setAccessibleName(message)
        self.event_action_feedback.setAccessibleDescription(message)

    def _selected_quote_index(self) -> Optional[int]:
        item = self.quote_list.currentItem()
        value = item.data(Qt.ItemDataRole.UserRole) if item else None
        return int(value) if isinstance(value, int) and 0 <= value < len(self.quotes) else None

    def _update_quote_detail(self, *_args: object) -> None:
        index = self._selected_quote_index()
        if index is None:
            self.quote_detail.clear()
            self.quote_detail_status.setText("Previewing")
            return
        content = verse_content(self.quotes[index])
        body = html_module.unescape(re.sub(r"<[^>]+>", "", content.body_html)).strip()
        reference = html_module.unescape(re.sub(r"<[^>]+>", "", content.reference_html)).strip()
        self.quote_detail.setText("{}\n\n{}".format(body, reference).strip())
        self.quote_detail_status.setText(
            "Current after save"
            if self.pending_manual_quote == self.quotes[index]
            else "Previewing"
        )

    def _quote_search_changed(self, *_args: object) -> None:
        self._quote_render_limit = 100
        self._refresh_quote_list()

    def _load_more_quotes(self) -> None:
        self._quote_render_limit += 100
        self._refresh_quote_list()

    def _refresh_quote_list(self, *_args: object) -> None:
        if self.pending_manual_quote is not None and self.pending_manual_quote not in self.quotes:
            self.pending_manual_quote = None
            if not self._building:
                self._update_dirty_state()
        selected = self._selected_quote_index()
        needle = self.quote_search.text().strip().casefold() if hasattr(self, "quote_search") else ""
        self.quote_list.clear()
        selected_row = -1
        matches: List[tuple[int, str]] = []
        for index, quote in enumerate(self.quotes):
            if needle and needle not in quote.casefold(): continue
            content = verse_content(quote)
            body = html_module.unescape(re.sub(r"<[^>]+>", "", content.body_html)).strip()
            reference = html_module.unescape(re.sub(r"<[^>]+>", "", content.reference_html)).strip()
            plain = "{} — {}".format(reference, body) if reference else body
            matches.append((index, plain))
        for index, plain in matches[:self._quote_render_limit]:
            item = SettingsListRow(
                plain[:160] + ("…" if len(plain) > 160 else ""),
                index,
                plain,
            ); self.quote_list.addItem(item)
            if index == selected: selected_row = self.quote_list.count() - 1
        _apply_view_row_targets(self.quote_list)
        if selected_row >= 0: self.quote_list.setCurrentRow(selected_row)
        elif self.quote_list.count(): self.quote_list.setCurrentRow(0)
        rendered = self.quote_list.count()
        total = len(matches)
        self.quote_count.setVisible(bool(needle) or rendered < total)
        self.quote_count.setText(
            "Showing {} of {} matching verses".format(rendered, total)
            if needle
            else "Showing {} of {} verses".format(rendered, total)
        )
        self.quote_load_more.setVisible(rendered < total)
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
        self._update_quote_detail()
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
        if self._saving:
            return
        self._sync_draft()
        if self._font_color_invalid:
            self._set_status("error", "Enter a valid #RRGGBB color")
            self.font_color.setFocus(Qt.FocusReason.OtherFocusReason)
            return
        if not self.draft.dirty and self.pending_manual_quote is None:
            return
        self._saving = True
        self._set_status("saving", "Saving…")
        if self.save_button is not None:
            self.save_button.setEnabled(False)
        if self.close_button is not None:
            self.close_button.setEnabled(False)
        self.save_shortcut.setEnabled(False)
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
                self._saving = False
                if self.close_button is not None:
                    self.close_button.setEnabled(True)
                self._update_dirty_state()
                return
            if clicked is not keep_button:
                self.draft.baseline = original_baseline
                self.draft.values = original_values
                self.staged = deepcopy(original_values)
                self._saving = False
                if self.close_button is not None:
                    self.close_button.setEnabled(True)
                self._update_dirty_state()
                return
        try:
            self.controller.save_config(
                self.draft.values,
                preferred_verse=self.pending_manual_quote,
            )
        except Exception as exc:
            self._saving = False
            if self.close_button is not None:
                self.close_button.setEnabled(True)
            self._set_status("error", "Couldn’t save")
            if self.save_button is not None:
                self.save_button.setEnabled(True)
            self.save_shortcut.setEnabled(True)
            QMessageBox.critical(
                self,
                "Could not save settings",
                "Your staged changes are still available.\n\n{}".format(exc),
            )
            return
        self.pending_manual_quote = None
        latest_saved = getattr(self.controller, "config", self.draft.values)
        self.draft.replace_all(latest_saved)
        self.staged = deepcopy(self.draft.values)
        self._staged_new_event_ids.clear()
        self._staged_edited_event_ids.clear()
        self._staged_archived_event_ids.clear()
        self._saving = False
        self._refresh_event_lists()
        if self.close_button is not None:
            self.close_button.setEnabled(True)
        self._update_dirty_state()
        self._set_status("saved", "✓ Saved")

        def clear_saved_status() -> None:
            if self.dirty_badge.property("state") == "saved":
                self.dirty_badge.hide()

        QTimer.singleShot(2000, clear_saved_status)

    def _confirm_discard(self) -> bool:
        if self._saving:
            return False
        self._sync_draft()
        if not self.draft.dirty and self.pending_manual_quote is None and not self._font_color_invalid:
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
        if self._saving:
            return
        if self._allow_close or self._confirm_discard():
            self._allow_close = True
            super().reject()

    def closeEvent(self, event: Any) -> None:
        if self._saving:
            event.ignore()
            return
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
