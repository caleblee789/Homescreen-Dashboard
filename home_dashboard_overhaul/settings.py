"""Professional staged settings editor integrated into the Caleb M. menu."""

from __future__ import annotations

from copy import deepcopy
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
    QAbstractListModel,
    QAbstractItemView,
    QAbstractSpinBox,
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
    QDesktopServices,
    QFileDialog,
    QFrame,
    QFontMetrics,
    QFont,
    QFontComboBox,
    QFormLayout,
    QGridLayout,
    QHeaderView,
    QHBoxLayout,
    QInputDialog,
    QIntValidator,
    QIcon,
    QKeySequence,
    QLabel,
    QLineEdit,
    QLocale,
    QListWidget,
    QListWidgetItem,
    QListView,
    QMenu,
    QMessageBox,
    QPainter,
    QPlainTextEdit,
    QPoint,
    QPen,
    QPixmap,
    QPushButton,
    QEvent,
    QRect,
    QScrollArea,
    QSettings,
    QSize,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QStackedWidget,
    QStackedLayout,
    QStyle,
    QStyledItemDelegate,
    QTabBar,
    QTimer,
    QUrl,
    QVBoxLayout,
    QWidget,
    QTreeWidget,
    QTreeWidgetItem,
    Qt,
    QModelIndex,
)

from .config_schema import normalize_config
from .settings_model import (
    SECTION_LABELS,
    SETTINGS_DEFAULT_SIZE,
    SETTINGS_MINIMUM_SIZE,
    SETTINGS_GEOMETRY_VERSION,
    SETTINGS_PREVIOUS_GEOMETRY_VERSION,
    SETTINGS_SMALL_SCREEN_MARGIN,
    SettingsDraft,
    clamp_window_geometry,
    font_family_value,
    history_range_choice,
    history_range_values,
    import_quotes,
    migrate_saved_window_geometry,
    resolve_section_target,
    saved_window_geometry_is_valid,
    settings_screen_uses_compact_fallback,
)
from .themes import (
    DEFAULT_CUSTOM_BIBLE_COLOR,
    DEFAULT_HEATMAP_PRESETS,
    HEATMAP_PRESETS,
    PRESETS,
    SETTINGS_COLOR_TOKENS,
)
from .ui_primitives import (
    FOCUS_RING_OFFSET_PX,
    FOCUS_RING_PX,
    INTERACTION_TARGET_MIN_PX,
    SETTINGS_PRIMITIVES,
    VISUAL_CHROME_PX,
)
from .verse import (
    MAX_VERSE_BYTES,
    MAX_VERSE_CHARS,
    serialize_quote_reference,
    split_quote_reference,
    verse_within_limit,
)


CALEB_MENU_TITLE = "Caleb M. Add-ons Settings"
CALEB_MENU_OBJECT_NAME = "caleb_m_addons_menu"
ACTION_TEXT = "Home Screen Dashboard settings"
PROJECT_URL = "https://github.com/caleblee789/Homescreen-Dashboard"
ISSUES_URL = "https://github.com/caleblee789/Homescreen-Dashboard/issues"
PACKAGE_ROOT = Path(__file__).resolve().parent

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
VERSE_SOURCE_INDEX_ROLE = Qt.ItemDataRole.UserRole + 30
VERSE_REFERENCE_ROLE = Qt.ItemDataRole.UserRole + 31
VERSE_EXCERPT_ROLE = Qt.ItemDataRole.UserRole + 32
VERSE_CURRENT_ROLE = Qt.ItemDataRole.UserRole + 33
VERSE_PENDING_ROLE = Qt.ItemDataRole.UserRole + 34

SETTINGS_GEOMETRY_KEY = "home_dashboard_overhaul/settings_dialog_geometry/v4"
SETTINGS_GEOMETRY_SCREEN_KEY = "home_dashboard_overhaul/settings_dialog_geometry/v4_screen"
SETTINGS_GEOMETRY_AVAILABLE_KEY = "home_dashboard_overhaul/settings_dialog_geometry/v4_available"
SETTINGS_GEOMETRY_DPR_KEY = "home_dashboard_overhaul/settings_dialog_geometry/v4_dpr"
SETTINGS_PREVIOUS_GEOMETRY_KEY = "home_dashboard_overhaul/settings_dialog_geometry/v3"
SETTINGS_PREVIOUS_GEOMETRY_SCREEN_KEY = "home_dashboard_overhaul/settings_dialog_geometry/v3_screen"
SETTINGS_SHELL_MAX_WIDTH = 1120
SETTINGS_PAGE_MAX_WIDTH = 920
SETTINGS_ABOUT_MAX_WIDTH = 840
SETTINGS_SIDEBAR_WIDTH = 184
# Retain the sidebar only while it leaves at least 680 logical pixels for the
# main region. This makes the 820 px supported minimum use compact navigation.
SETTINGS_COMPACT_BODY_WIDTH = SETTINGS_SIDEBAR_WIDTH + 680
SETTINGS_HEADER_HEIGHT = 72
SETTINGS_FOOTER_MIN_HEIGHT = 60
SETTINGS_SPACING = {
    "tight": 4,
    "control": 8,
    "related": 12,
    "card": 16,
    "compact_page": 20,
    "page": 24,
    "section": 32,
}


def _settings_primitive(name: str) -> str:
    if name not in SETTINGS_PRIMITIVES:
        raise ValueError("unknown Settings primitive: {}".format(name))
    return name


def _palette_tokens() -> Dict[str, str]:
    """Resolve the fixed Settings palette from Anki's application appearance."""
    application = QApplication.instance()
    palette = application.palette() if application is not None else mw.palette()
    window = getattr(palette, "window")().color()
    source = SETTINGS_COLOR_TOKENS["dark" if window.lightness() < 128 else "light"]
    return {
        "window": source["ui_bg"],
        "sidebar": source["ui_sidebar"],
        "base": source["ui_surface"],
        "verse_card": source["ui_surface"],
        "alternate": source["ui_surface_raised"],
        "accent_soft": source["ui_accent_soft"],
        "hover": source["ui_surface_hover"],
        "text": source["ui_text_primary"],
        "secondary": source["ui_text_secondary"],
        "muted": source["ui_text_muted"],
        "button": source["ui_surface_raised"],
        "button_text": source["ui_text_primary"],
        "border": source["ui_border"],
        "border_strong": source["ui_border_strong"],
        "highlight": source["ui_accent"],
        "highlight_hover": source["ui_accent_hover"],
        "highlight_pressed": source["ui_accent_pressed"],
        "highlight_text": source["ui_accent_ink"],
        "focus": source["ui_accent_hover"],
        "disabled": source["ui_text_muted"],
        "success": source["ui_success"],
        "warning": source["ui_warning"],
        "danger": source["ui_danger"],
        "danger_bg": source["ui_surface_hover"],
        "overlay": source["ui_overlay"],
    }


def _theme_tokens(
    config: Optional[Mapping[str, Any]] = None,
    anki_dark: Optional[bool] = None,
) -> Dict[str, str]:
    """Return Settings tokens; staged dashboard themes never recolor Qt."""
    del config
    if anki_dark is None:
        return _palette_tokens()
    source = SETTINGS_COLOR_TOKENS["dark" if anki_dark else "light"]
    return {
        "window": source["ui_bg"],
        "sidebar": source["ui_sidebar"],
        "base": source["ui_surface"],
        "verse_card": source["ui_surface"],
        "alternate": source["ui_surface_raised"],
        "accent_soft": source["ui_accent_soft"],
        "hover": source["ui_surface_hover"],
        "text": source["ui_text_primary"],
        "secondary": source["ui_text_secondary"],
        "muted": source["ui_text_muted"],
        "button": source["ui_surface_raised"],
        "button_text": source["ui_text_primary"],
        "border": source["ui_border"],
        "border_strong": source["ui_border_strong"],
        "highlight": source["ui_accent"],
        "highlight_hover": source["ui_accent_hover"],
        "highlight_pressed": source["ui_accent_pressed"],
        "highlight_text": source["ui_accent_ink"],
        "focus": source["ui_accent_hover"],
        "disabled": source["ui_text_muted"],
        "success": source["ui_success"],
        "warning": source["ui_warning"],
        "danger": source["ui_danger"],
        "danger_bg": source["ui_surface_hover"],
        "overlay": source["ui_overlay"],
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
    values = _theme_tokens(config, anki_dark)
    values.update(
        visual_chrome=str(VISUAL_CHROME_PX),
        focus_ring=str(FOCUS_RING_PX),
        focus_offset=str(FOCUS_RING_OFFSET_PX),
    )
    return """
QDialog#HomeDashboardSettings {{ background: {window}; border: 1px solid {border}; border-radius: 10px; color: {text}; }}
QWidget#HomeDashboardSettings QLabel,
QWidget#HomeDashboardSettings QCheckBox {{ color: {text}; }}
QWidget#HomeDashboardSettings QWidget#SettingsSidebarPanel {{ background: {sidebar}; border: 0; border-right: 1px solid {border}; }}
QWidget#HomeDashboardSettings QListWidget#SettingsNav {{ background: transparent; border: 0; color: {text}; padding: 0; font-weight: 600; }}
QWidget#HomeDashboardSettings QListWidget#SettingsNav::item {{ border: 1px solid transparent; border-left: 3px solid transparent; border-radius: 6px; color: {secondary}; margin: 2px 0; min-height: 44px; padding: 0 8px; }}
QWidget#HomeDashboardSettings QListWidget#SettingsNav::item:hover:!selected {{ background: {hover}; color: {text}; }}
QWidget#HomeDashboardSettings QListWidget#SettingsNav::item:selected {{ background: {accent_soft}; border-color: {border_strong}; border-left-color: {highlight}; color: {text}; font-weight: 650; }}
QWidget#HomeDashboardSettings QListWidget#SettingsNav::item:focus {{ border: {focus_ring}px solid {focus}; }}
QWidget#HomeDashboardSettings QTabBar#CompactSettingsNav {{ background: {sidebar}; border: 1px solid {border}; border-radius: 8px; }}
QWidget#HomeDashboardSettings QTabBar#CompactSettingsNav::tab {{ background: transparent; border: 1px solid transparent; border-bottom: 3px solid transparent; color: {secondary}; min-height: 36px; padding: 0 12px; }}
QWidget#HomeDashboardSettings QTabBar#CompactSettingsNav::tab:hover:!selected {{ background: {hover}; color: {text}; }}
QWidget#HomeDashboardSettings QTabBar#CompactSettingsNav::tab:selected {{ background: {accent_soft}; border-color: {border_strong}; border-bottom-color: {highlight}; color: {text}; font-weight: 650; }}
QWidget#HomeDashboardSettings QScrollArea {{ background: transparent; border: 0; }}
QWidget#HomeDashboardSettings QWidget#SettingsPage {{ background: transparent; border: 0; }}
QWidget#HomeDashboardSettings QWidget#SettingsCard {{ background: {base}; border: 1px solid {border}; border-radius: 8px; }}
QWidget#HomeDashboardSettings QWidget#SettingsSubsection {{ background: transparent; border: 0; }}
QWidget#HomeDashboardSettings QWidget#SettingsHeader {{ background: {window}; border: 0; border-bottom: 1px solid {border}; }}
QWidget#HomeDashboardSettings QLabel#GlobalTitle {{ font-weight: 650; color: {text}; }}
QWidget#HomeDashboardSettings QLabel#SidebarVersion {{ color: {muted}; }}
QWidget#HomeDashboardSettings QLabel#PageTitle {{ font-weight: 600; color: {text}; }}
QWidget#HomeDashboardSettings QLabel#CardTitle {{ font-weight: 600; color: {text}; }}
QWidget#HomeDashboardSettings QLabel#SectionTitle {{ color: {text}; font-weight: 600; padding-top: 10px; }}
QWidget#HomeDashboardSettings QLabel#PageHelp,
QWidget#HomeDashboardSettings QLabel#FieldHelp {{ color: {muted}; }}
QWidget#HomeDashboardSettings QWidget#SettingsRow {{ background: transparent; border: 0; }}
QWidget#HomeDashboardSettings QWidget#AboutDefinitionList {{ background: transparent; border: 0; }}
QWidget#HomeDashboardSettings QFrame#AboutDivider {{ color: {border}; }}
QWidget#HomeDashboardSettings QWidget#ActionBar {{ background: {alternate}; border-top: 1px solid {border}; border-radius: 0; }}
QWidget#HomeDashboardSettings QWidget#UndoToast {{ background: {alternate}; border: 1px solid {highlight}; border-radius: 8px; }}
QWidget#HomeDashboardSettings QWidget#ContextualActionGroup {{ background: transparent; border: 0; }}
QWidget#HomeDashboardSettings QLabel#FooterStatus {{ color: {muted}; font-weight: 600; }}
QWidget#HomeDashboardSettings QLabel#FooterStatus[state="dirty"] {{ color: {warning}; }}
QWidget#HomeDashboardSettings QLabel#FooterStatus[state="saved"] {{ color: {success}; }}
QWidget#HomeDashboardSettings QLabel#FooterStatus[state="saving"] {{ color: {secondary}; }}
QWidget#HomeDashboardSettings QLabel#FooterStatus[state="error"] {{ color: {danger}; }}
QWidget#HomeDashboardSettings QWidget#SaveErrorPanel {{ background: {base}; border: 1px solid {danger}; border-radius: 8px; padding: 8px; }}
QWidget#HomeDashboardSettings QLabel#InlineSaveError {{ color: {danger}; }}
QWidget#HomeDashboardSettings QLabel#WarningText {{ color: {warning}; }}
QWidget#HomeDashboardSettings QLabel#WarningText[state="error"] {{ color: {danger}; }}
QWidget#HomeDashboardSettings QWidget#SegmentedControl {{ background: {alternate}; border: 1px solid {border}; border-radius: 7px; }}
QWidget#HomeDashboardSettings QPushButton#SegmentButton {{ background: transparent; border: 0; border-right: 1px solid {border}; border-radius: 0; margin: 0; min-height: 36px; padding: 0 12px; }}
QWidget#HomeDashboardSettings QPushButton#SegmentButton[last="true"] {{ border-right: 0; }}
QWidget#HomeDashboardSettings QPushButton#SegmentButton:hover:!checked {{ background: {hover}; }}
QWidget#HomeDashboardSettings QPushButton#SegmentButton:pressed {{ background: {highlight_pressed}; color: {highlight_text}; }}
QWidget#HomeDashboardSettings QPushButton#SegmentButton:checked {{ background: {accent_soft}; border: 1px solid {highlight}; color: {text}; font-weight: 650; }}
QWidget#HomeDashboardSettings QPushButton#SegmentButton:focus {{ border: 2px solid {focus}; }}
QWidget#HomeDashboardSettings QPushButton#SettingsSwitch {{ background: transparent; border: 0; margin: 0; min-height: 36px; min-width: 44px; max-height: 36px; max-width: 44px; padding: 0; }}
QWidget#HomeDashboardSettings QPushButton#LinkButton {{ background: transparent; border: 0; color: {highlight}; min-height: 36px; padding: 0 8px; }}
QWidget#HomeDashboardSettings QLineEdit,
QWidget#HomeDashboardSettings QComboBox,
QWidget#HomeDashboardSettings QSpinBox,
QWidget#HomeDashboardSettings QDoubleSpinBox,
QWidget#HomeDashboardSettings QDateEdit {{
  background: {alternate}; border: 1px solid {border}; border-radius: 6px; color: {text}; min-height: {visual_chrome}px; margin: {focus_offset}px 0; padding: 0 8px;
}}
QWidget#HomeDashboardSettings QPlainTextEdit,
QWidget#HomeDashboardSettings QListWidget#ManagerList,
QWidget#HomeDashboardSettings QTreeWidget#ManagerTree {{
  background: {base}; border: 1px solid {border}; border-radius: 7px; color: {text}; padding: 3px;
}}
QWidget#HomeDashboardSettings QLineEdit:focus,
QWidget#HomeDashboardSettings QComboBox:focus,
QWidget#HomeDashboardSettings QSpinBox:focus,
QWidget#HomeDashboardSettings QDoubleSpinBox:focus,
QWidget#HomeDashboardSettings QDateEdit:focus,
QWidget#HomeDashboardSettings QPlainTextEdit:focus,
QWidget#HomeDashboardSettings QListWidget#ManagerList:focus,
QWidget#HomeDashboardSettings QTreeWidget#ManagerTree:focus {{ border: {focus_ring}px solid {focus}; }}
QWidget#HomeDashboardSettings QLineEdit[invalid="true"] {{ border: 2px solid {danger}; }}
QWidget#HomeDashboardSettings QWidget#SuffixNumberField {{ background: {alternate}; border: 1px solid {border}; border-radius: 6px; min-height: 36px; }}
QWidget#HomeDashboardSettings QLineEdit#SuffixNumberEditor {{ background: transparent; border: 0; margin: 0; min-height: 34px; padding: 0 4px 0 8px; }}
QWidget#HomeDashboardSettings QLabel#NumberSuffix {{ color: {secondary}; padding: 0 8px 0 2px; }}
QWidget#HomeDashboardSettings QSpinBox#ValueBadge {{ background: {alternate}; border: 1px solid {border}; color: {secondary}; }}
QWidget#HomeDashboardSettings QComboBox QAbstractItemView,
QWidget#HomeDashboardSettings QTreeWidget#ManagerTree::item {{ background: {base}; border-bottom: 1px solid {alternate}; color: {text}; padding: 4px 5px; }}
QWidget#HomeDashboardSettings QTreeWidget#ManagerTree QHeaderView::section {{ background: {alternate}; border: 0; border-bottom: 1px solid {border}; color: {text}; font-weight: 700; padding: 4px 6px; }}
QWidget#HomeDashboardSettings QComboBox QAbstractItemView {{ selection-background-color: {highlight}; selection-color: {highlight_text}; }}
QWidget#HomeDashboardSettings QComboBox::drop-down {{ border: 0; width: 24px; }}
QWidget#HomeDashboardSettings QComboBox::down-arrow {{ image: none; height: 0; width: 0; }}
QWidget#HomeDashboardSettings QSpinBox::up-button,
QWidget#HomeDashboardSettings QSpinBox::down-button {{ width: 30px; }}
QWidget#HomeDashboardSettings QTreeWidget#ManagerTree::item:selected {{ background: transparent; color: {text}; }}
QWidget#HomeDashboardSettings QWidget#EventRow {{ background: {base}; border: 0; border-bottom: 1px solid {border}; border-radius: 0; }}
QWidget#HomeDashboardSettings QWidget#EventRow:hover {{ background: {hover}; }}
QWidget#HomeDashboardSettings QWidget#EventRow[pressed="true"] {{ background: {accent_soft}; }}
QWidget#HomeDashboardSettings QLabel#EventRowTitle {{ color: {text}; font-weight: 650; }}
QWidget#HomeDashboardSettings QLabel#EventRowMeta {{ color: {secondary}; }}
QWidget#HomeDashboardSettings QPushButton#EventOverflowButton {{ background: transparent; border: 0; min-height: 32px; max-height: 32px; min-width: 32px; max-width: 32px; padding: 0; }}
QWidget#HomeDashboardSettings QPushButton#IconButton {{ background: transparent; border: 0; min-height: 32px; max-height: 32px; min-width: 32px; max-width: 32px; padding: 0; }}
QWidget#HomeDashboardSettings QListView#VerseLibraryView {{ background: {base}; border: 1px solid {border}; border-radius: 7px; color: {text}; }}
QWidget#HomeDashboardSettings QListView#VerseLibraryView::item {{ background: transparent; border: 0; }}
QWidget#HomeDashboardSettings QCheckBox {{ min-height: {visual_chrome}px; margin: {focus_offset}px 0; }}
QWidget#HomeDashboardSettings QCheckBox:focus {{ border: {focus_ring}px solid {focus}; border-radius: 6px; }}
QWidget#HomeDashboardSettings QSlider:focus {{ border: {focus_ring}px solid {focus}; border-radius: 6px; }}
QWidget#HomeDashboardSettings QSlider::groove:horizontal {{ background: {alternate}; border: 1px solid {border}; border-radius: 3px; height: 5px; }}
QWidget#HomeDashboardSettings QSlider::handle:horizontal {{ background: {highlight}; border: 2px solid {base}; border-radius: 8px; height: 14px; margin: -6px 0; width: 14px; }}
QWidget#HomeDashboardSettings QPushButton {{ background: {button}; border: 1px solid {border}; border-radius: 6px; color: {button_text}; min-height: 36px; margin: {focus_offset}px 0; padding: 0 12px; font-weight: 600; }}
QWidget#HomeDashboardSettings QPushButton:hover {{ border-color: {highlight}; background: {hover}; }}
QWidget#HomeDashboardSettings QPushButton:pressed {{ background: {highlight_pressed}; border-color: {highlight_pressed}; color: {highlight_text}; }}
QWidget#HomeDashboardSettings QPushButton:focus {{ border: {focus_ring}px solid {focus}; }}
QWidget#HomeDashboardSettings QPushButton#PrimaryButton {{ background: {highlight}; border-color: {highlight}; color: {highlight_text}; font-weight: 750; }}
QWidget#HomeDashboardSettings QPushButton#PrimaryButton:disabled {{ background: {alternate}; border-color: {border}; color: {disabled}; }}
QWidget#HomeDashboardSettings QPushButton#DangerButton {{ background: {danger_bg}; border-color: {danger}; color: {danger}; font-weight: 650; }}
QWidget#HomeDashboardSettings QPushButton#DangerButton:disabled {{ background: {alternate}; border-color: {border}; color: {disabled}; }}
QWidget#HomeDashboardSettings QWidget#EmptyState {{ background: transparent; border: 0; }}
QWidget#HomeDashboardSettings QLabel#EmptyStateTitle {{ color: {text}; font-weight: 650; }}
QWidget#HomeDashboardSettings QLabel#EmptyStateCopy {{ color: {muted}; }}
QWidget#HomeDashboardSettings QLabel#EmptyState {{ background: {alternate}; border: 1px solid {border}; border-radius: 7px; color: {text}; padding: 8px 10px; }}
QWidget#HomeDashboardSettings QLabel#InfoBanner {{ background: {accent_soft}; border: 1px solid {border_strong}; border-radius: 7px; color: {text}; padding: 10px 12px; }}
QWidget#HomeDashboardSettings QLabel#SelectedVerseCard {{ background: {base}; border: 1px solid {border}; border-radius: 9px; color: {text}; padding: 11px 12px; }}
QWidget#HomeDashboardSettings QPushButton#DisclosureButton {{ background: transparent; border: 0; border-top: 1px solid {border}; border-radius: 0; color: {text}; font-weight: 650; min-height: 40px; padding: 0 4px; text-align: left; }}
QWidget#HomeDashboardSettings QPushButton#DisclosureButton:hover {{ background: {hover}; border-top-color: {border}; }}
QWidget#HomeDashboardSettings QPushButton#DisclosureButton:pressed {{ background: {accent_soft}; border-top-color: {border_strong}; color: {text}; }}
QWidget#HomeDashboardSettings QWidget#EventTabs {{ background: {base}; border: 1px solid {border}; border-radius: 7px; }}
QWidget#HomeDashboardSettings QTabBar#EventTabsBar {{ background: {alternate}; border: 0; border-bottom: 1px solid {border}; }}
QWidget#HomeDashboardSettings QTabBar#EventTabsBar::tab {{ background: {alternate}; border: 1px solid {border}; border-bottom: 3px solid transparent; color: {secondary}; min-height: 36px; padding: 0 14px; }}
QWidget#HomeDashboardSettings QTabBar#EventTabsBar::tab:selected {{ background: {accent_soft}; border-color: {border_strong}; border-bottom-color: {highlight}; color: {text}; font-weight: 650; }}
QWidget#HomeDashboardSettings QWidget:disabled,
QWidget#HomeDashboardSettings QPushButton:disabled {{ background: {alternate}; color: {disabled}; border-color: {border}; }}
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
QDialog#HomeDashboardEditor QLabel#EditorError {{ color: {danger}; }}
QDialog#HomeDashboardEditor QLabel#PageTitle {{ color: {text}; font-weight: 750; }}
QDialog#HomeDashboardEditor QLineEdit,
QDialog#HomeDashboardEditor QDateEdit {{ background: {base}; border: 1px solid {border}; border-radius: 7px; color: {text}; min-height: {visual_chrome}px; margin: {focus_offset}px 0; padding: 0 7px; }}
QDialog#HomeDashboardEditor QPlainTextEdit {{ background: {base}; border: 1px solid {border}; border-radius: 7px; color: {text}; padding: 5px 7px; }}
QDialog#HomeDashboardEditor QLineEdit:focus,
QDialog#HomeDashboardEditor QDateEdit:focus,
QDialog#HomeDashboardEditor QPlainTextEdit:focus {{ border: {focus_ring}px solid {focus}; }}
QDialog#HomeDashboardEditor QPushButton {{ background: {button}; border: 1px solid {border}; border-radius: 7px; color: {button_text}; min-height: {visual_chrome}px; margin: {focus_offset}px 0; padding: 0 11px; }}
QDialog#HomeDashboardEditor QPushButton:hover {{ background: {hover}; border-color: {highlight}; }}
QDialog#HomeDashboardEditor QPushButton:pressed {{ background: {highlight_pressed}; border-color: {highlight_pressed}; color: {highlight_text}; }}
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
        except RuntimeError:
            # A queued palette event can outlive a dialog that has just closed.
            return
        finally:
            try:
                widget._hdo_palette_style_pending = False
            except RuntimeError:
                pass

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
        try:
            changed = _reapply_palette_style(widget, factory)
            if changed and after_change is not None:
                after_change()
        except RuntimeError:
            # The parented timer may deliver one queued timeout during teardown.
            return

    timer.timeout.connect(poll)
    timer.start()
    widget._hdo_palette_watcher = timer


def _apply_role_fonts(root: QWidget) -> None:
    """Scale semantic Settings roles from Anki's live application font."""

    application = QApplication.instance()
    base = application.font() if application is not None else root.font()

    def role_font(pixel_target: float, weight: Optional[QFont.Weight] = None) -> QFont:
        font = QFont(base)
        factor = pixel_target / 13.0
        if font.pixelSize() > 0:
            font.setPixelSize(max(1, round(font.pixelSize() * factor)))
        elif font.pointSizeF() > 0:
            font.setPointSizeF(max(1.0, font.pointSizeF() * factor))
        if weight is not None:
            font.setWeight(weight)
        return font

    roles = {
        "GlobalTitle": role_font(16, QFont.Weight.DemiBold),
        "SidebarVersion": role_font(12),
        "PageTitle": role_font(20, QFont.Weight.DemiBold),
        "CardTitle": role_font(14, QFont.Weight.DemiBold),
        "SectionTitle": role_font(14, QFont.Weight.DemiBold),
        "EmptyStateTitle": role_font(14, QFont.Weight.DemiBold),
        "SettingsPromptTitle": role_font(17.5, QFont.Weight.DemiBold),
        "SettingsPromptMessage": role_font(13),
        "PageHelp": role_font(12),
        "FieldHelp": role_font(12),
        "EventRowTitle": role_font(13, QFont.Weight.DemiBold),
        "EventRowMeta": role_font(12),
        "FooterStatus": role_font(12.5, QFont.Weight.Medium),
    }
    for object_name, font in roles.items():
        for widget in root.findChildren(QWidget, object_name):
            widget.setFont(font)


class DisclosureChevron(QWidget):
    """Font-independent disclosure indicator owned by a parented header."""

    def __init__(self, header: "DisclosureHeader") -> None:
        super().__init__(header)
        self.header = header
        self.setFixedSize(18, 18)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    def paintEvent(self, event: Any) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pen = QPen(QColor(_palette_tokens()["secondary"]))
        pen.setWidthF(1.8)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        if self.header.isChecked():
            painter.drawLine(4, 11, 9, 6)
            painter.drawLine(9, 6, 14, 11)
        else:
            painter.drawLine(6, 4, 11, 9)
            painter.drawLine(11, 9, 6, 14)


class DisclosureHeader(QPushButton):
    """Reusable full-row disclosure with a painted, rotating chevron."""

    def __init__(
        self,
        title: str,
        content: Optional[QWidget] = None,
        description: str = "",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__("", parent)
        self.setObjectName("DisclosureButton")
        self.setCheckable(True)
        self.setAccessibleName(title)
        self.setAccessibleDescription(description)
        self._content: Optional[QWidget] = None
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 6, 0)
        layout.setSpacing(8)
        self.label = QLabel(title, self)
        self.label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        layout.addWidget(self.label, 1)
        self.chevron = DisclosureChevron(self)
        layout.addWidget(self.chevron)
        self.toggled.connect(self._expanded_changed)
        if content is not None:
            self.set_content(content)

    def set_content(self, content: QWidget) -> None:
        self._content = content
        content.setVisible(self.isChecked())

    def _expanded_changed(self, expanded: bool) -> None:
        if self._content is not None:
            self._content.setVisible(expanded)
        self.chevron.update()


def _external_link_icon() -> QIcon:
    pixmap = QPixmap(14, 14)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    pen = QPen(QColor(_palette_tokens()["highlight"]), 1.6)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.drawLine(3, 6, 3, 11)
    painter.drawLine(3, 11, 9, 11)
    painter.drawLine(7, 3, 11, 3)
    painter.drawLine(11, 3, 11, 7)
    painter.drawLine(6, 8, 11, 3)
    painter.end()
    return QIcon(pixmap)


def _settings_vector_icon(kind: str, size: int = 16) -> QIcon:
    """Return a small palette-aware icon without fonts or remote assets."""

    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    tokens = _palette_tokens()
    color_key = "danger" if kind == "error" else "warning" if kind == "warning" else "success" if kind == "success" else "secondary"
    pen = QPen(QColor(tokens[color_key]), max(1.5, size / 9))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    center = size / 2
    if kind == "ellipsis":
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(tokens["secondary"]))
        radius = max(1.2, size / 11)
        for offset in (-size * .27, 0, size * .27):
            painter.drawEllipse(QPoint(int(center + offset), int(center)), int(radius), int(radius))
    elif kind == "clear":
        inset = size * .28
        painter.drawLine(int(inset), int(inset), int(size - inset), int(size - inset))
        painter.drawLine(int(size - inset), int(inset), int(inset), int(size - inset))
    elif kind == "copy":
        painter.drawRoundedRect(QRect(int(size * .32), int(size * .20), int(size * .48), int(size * .56)), 2, 2)
        painter.drawRoundedRect(QRect(int(size * .18), int(size * .34), int(size * .48), int(size * .50)), 2, 2)
    elif kind == "calendar":
        painter.drawRoundedRect(
            QRect(int(size * .16), int(size * .22), int(size * .68), int(size * .62)),
            2,
            2,
        )
        painter.drawLine(
            int(size * .16),
            int(size * .40),
            int(size * .84),
            int(size * .40),
        )
        painter.drawLine(
            int(size * .34),
            int(size * .14),
            int(size * .34),
            int(size * .30),
        )
        painter.drawLine(
            int(size * .66),
            int(size * .14),
            int(size * .66),
            int(size * .30),
        )
    elif kind == "success":
        painter.drawLine(int(size * .20), int(size * .52), int(size * .43), int(size * .73))
        painter.drawLine(int(size * .43), int(size * .73), int(size * .82), int(size * .27))
    elif kind in {"warning", "error", "info"}:
        painter.drawEllipse(QRect(int(size * .15), int(size * .15), int(size * .70), int(size * .70)))
        if kind == "info":
            painter.drawPoint(int(center), int(size * .34))
            painter.drawLine(int(center), int(size * .48), int(center), int(size * .70))
        else:
            painter.drawLine(int(center), int(size * .30), int(center), int(size * .58))
            painter.drawPoint(int(center), int(size * .72))
    painter.end()
    return QIcon(pixmap)


def _icon_button(kind: str, accessible_name: str, parent: Optional[QWidget] = None) -> QPushButton:
    button = QPushButton("", parent)
    button.setObjectName("IconButton")
    button.setIcon(_settings_vector_icon(kind))
    button.setIconSize(QSize(16, 16))
    button.setFixedSize(32, 32)
    button.setAccessibleName(accessible_name)
    button.setToolTip(accessible_name)
    return button


class ExternalLinkButton(QPushButton):
    """Local vector-icon link; no remote icon or browser dependency is added."""

    def __init__(self, label: str, url: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(label, parent)
        self._url = url
        self.setObjectName("LinkButton")
        self.setIcon(_external_link_icon())
        self.setAccessibleName(label)
        self.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(self._url))
        )


def _page(title: str, help_text: str) -> tuple[QWidget, QVBoxLayout, QFormLayout]:
    page = QWidget()
    page.setObjectName("SettingsPage")
    page.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    page.setMinimumWidth(0)
    layout = QVBoxLayout(page)
    layout.setContentsMargins(20, 20, 20, 36)
    layout.setSpacing(16)
    layout.setAlignment(Qt.AlignmentFlag.AlignTop)
    header = QWidget()
    header.setObjectName("SettingsPageHeader")
    header_outer = QHBoxLayout(header)
    # Keep the page header at its 72 px contract even when it owns a standard
    # 36 px action such as the empty-Events Add button.
    header_outer.setContentsMargins(20, 6, 20, 6)
    header_outer.setSpacing(8)
    header_copy = QVBoxLayout()
    header_copy.setContentsMargins(0, 0, 0, 0)
    header_copy.setSpacing(2)
    heading = QLabel(title)
    heading.setObjectName("PageTitle")
    header_copy.addWidget(heading)
    help_label = QLabel(help_text)
    help_label.setObjectName("PageHelp")
    help_label.setWordWrap(True)
    header_copy.addWidget(help_label)
    header_outer.addLayout(header_copy, 1)
    header_actions_host = QWidget(header)
    header_actions_host.setObjectName("SettingsPageHeaderActions")
    header_actions_host.setSizePolicy(
        QSizePolicy.Policy.Maximum,
        QSizePolicy.Policy.Preferred,
    )
    header_actions = QHBoxLayout(header_actions_host)
    header_actions.setContentsMargins(0, 0, 0, 0)
    header_actions.setSpacing(6)
    header_outer.addWidget(
        header_actions_host,
        0,
        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
    )
    page._hdo_header_actions = header_actions
    page._hdo_header_actions_host = header_actions_host
    page._hdo_page_header = header
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
        self._resync_timer = QTimer(self)
        self._resync_timer.setSingleShot(True)
        self._resync_timer.timeout.connect(self._resync_minimum_height)
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
        width = 0
        return QSize(width, self.heightForWidth(width))

    def _sync_minimum_height(self, width: int) -> None:
        target = self.heightForWidth(max(1, width))
        # QFormLayout may briefly assign a generous label width, then narrow
        # it after sizing the field column. Never collapse the conservative
        # first-pass height: doing so can clip the final wrapped help line.
        if self.minimumHeight() < target:
            self.setMinimumHeight(target)
            self.updateGeometry()

    def _resync_minimum_height(self) -> None:
        self._sync_minimum_height(self.width())

    def resizeEvent(self, event: Any) -> None:
        self._sync_minimum_height(event.size().width())
        super().resizeEvent(event)

    def changeEvent(self, event: Any) -> None:
        if event.type() in {
            getattr(QEvent.Type, "FontChange", None),
            getattr(QEvent.Type, "StyleChange", None),
        }:
            self._resync_timer.start(0)
        super().changeEvent(event)


def _field_label(title: str, description: str = "") -> QWidget:
    return WrappingFieldLabel(title, description)


def _stacked_field(title: str, description: str, field: QWidget) -> QWidget:
    """Build a full-width field for controls that should never be squeezed."""

    wrap = QWidget()
    wrap.setObjectName("SettingsRow")
    wrap.setMinimumWidth(0)
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
    wrap.setMinimumWidth(0)
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
    wrap.setMinimumWidth(0)
    layout = QHBoxLayout(wrap)
    layout.setContentsMargins(0, 0, 0, 0)
    slider = QSlider(Qt.Orientation.Horizontal)
    slider.setRange(minimum, maximum)
    slider.setValue(value)
    spin = QSpinBox()
    spin.setRange(minimum, maximum)
    spin.setSuffix(suffix)
    spin.setValue(value)
    spin.setObjectName("ValueBadge")
    spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
    spin.setReadOnly(True)
    spin.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    spin.setMinimumWidth(72)
    spin.setMaximumWidth(92)
    slider.valueChanged.connect(spin.setValue)
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
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.setMaximumWidth(380)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        for option_index, (label, value) in enumerate(options):
            button = SegmentButton(label, self)
            button.setObjectName("SegmentButton")
            button.setCheckable(True)
            button.setProperty("hdoValue", value)
            button.setProperty("last", option_index == len(options) - 1)
            button.setAccessibleName("{}: {}".format(accessible_name, label))
            self.button_group.addButton(button)
            self._buttons[value] = button
            layout.addWidget(button, 1)
        self.setValue(current)

    def set_option_width(self, width: int) -> None:
        for button in self._buttons.values():
            button.setMinimumWidth(max(1, int(width)))
        self.setMinimumWidth(
            min(300, (max(1, int(width)) * len(self._buttons)) + 2)
        )

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
        self.setFixedSize(44, 36)
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
        painter.drawRoundedRect(5, 9, 34, 18, 9, 9)
        painter.setPen(QPen(Qt.PenStyle.NoPen))
        painter.setBrush(QBrush(knob))
        knob_x = 22 if self.isChecked() else 7
        painter.drawEllipse(knob_x, 11, 14, 14)
        if self.hasFocus():
            focus_pen = QPen(QColor(tokens["focus"]), FOCUS_RING_PX)
            painter.setPen(focus_pen)
            painter.setBrush(QBrush(Qt.BrushStyle.NoBrush))
            painter.drawRoundedRect(2, 2, 40, 32, 7, 7)


class SettingsCard(QWidget):
    """Quiet bordered Settings group with an optional scoped reset action."""

    def __init__(
        self,
        title: str = "",
        description: str = "",
        reset_text: str = "",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("SettingsCard")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        self.setMinimumWidth(0)
        self.outer = QVBoxLayout(self)
        self.outer.setContentsMargins(18, 16, 18, 18)
        self.outer.setSpacing(12)
        self.heading = QLabel(title)
        self.heading.setObjectName("CardTitle")
        self.heading.setAccessibleName(title)
        self.heading.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.reset_button: Optional[QPushButton] = None
        if title or reset_text:
            header = QHBoxLayout()
            if title:
                header.addWidget(self.heading)
            header.addStretch()
            if reset_text:
                self.reset_button = QPushButton(reset_text)
                self.reset_button.setObjectName("LinkButton")
                self.reset_button.setAccessibleName(reset_text)
                self.reset_button.hide()
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
    row.setMinimumWidth(0)
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
    layout.addWidget(switch, 0, Qt.AlignmentFlag.AlignTop)
    return row, switch


class ConfigurableSwitchRow(QWidget):
    """Responsive text/action/toggle row used by the Bible section setting."""

    def __init__(
        self,
        title: str,
        description: str,
        checked: bool,
        action_label: str,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("SettingsRow")
        self.setMinimumWidth(0)
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 2, 0, 2)
        self.grid.setHorizontalSpacing(12)
        self.grid.setVerticalSpacing(6)
        copy = QWidget(self)
        copy.setMinimumWidth(0)
        copy_layout = QVBoxLayout(copy)
        copy_layout.setContentsMargins(0, 0, 0, 0)
        copy_layout.setSpacing(2)
        copy_layout.addWidget(QLabel(title))
        help_label = QLabel(description)
        help_label.setObjectName("FieldHelp")
        help_label.setWordWrap(True)
        copy_layout.addWidget(help_label)
        self.copy = copy
        self.action = QPushButton(action_label, self)
        self.switch = SettingsSwitch(checked, self)
        self.switch.setAccessibleName(title)
        self.switch.setAccessibleDescription(description)
        self.switch.toggled.connect(
            lambda state: self.switch.setToolTip("On" if state else "Off")
        )
        self.switch.setToolTip("On" if checked else "Off")
        self.set_compact(False)

    def set_compact(self, compact: bool) -> None:
        for widget in (self.copy, self.action, self.switch):
            self.grid.removeWidget(widget)
        self.grid.addWidget(self.copy, 0, 0)
        if compact:
            self.grid.addWidget(self.action, 1, 0, Qt.AlignmentFlag.AlignLeft)
        else:
            self.grid.addWidget(self.action, 0, 1, Qt.AlignmentFlag.AlignVCenter)
        self.grid.addWidget(self.switch, 0, 2, Qt.AlignmentFlag.AlignTop)
        self.grid.setColumnStretch(0, 1)


def _info_button(title: str, text: str) -> QPushButton:
    button = QPushButton("")
    button.setObjectName("LinkButton")
    button.setIcon(_settings_vector_icon("info"))
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
    target = max(INTERACTION_TARGET_MIN_PX, widget.fontMetrics().lineSpacing() + 10)
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


def _event_row_target_height(
    view: QAbstractItemView,
    row_widget: Optional[QWidget] = None,
) -> int:
    """Keep both event-row text lines visible as the application font grows."""

    title = (
        row_widget.findChild(QLabel, "EventRowTitle")
        if row_widget is not None
        else None
    )
    metadata = (
        row_widget.findChild(QLabel, "EventRowMeta")
        if row_widget is not None
        else None
    )
    title_height = (
        title.fontMetrics().lineSpacing()
        if title is not None
        else view.fontMetrics().lineSpacing()
    )
    metadata_height = (
        metadata.fontMetrics().lineSpacing()
        if metadata is not None
        else view.fontMetrics().lineSpacing()
    )
    return max(54, title_height + metadata_height + 13)


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
            row_widget = view.itemWidget(item)
            item_target = (
                max(56, (2 * view.fontMetrics().lineSpacing()) + 20)
                if row_widget is not None and row_widget.objectName() == "VerseRow"
                else target
            )
            item.setSizeHint(QSize(max(1, width), item_target))
    elif isinstance(view, QTreeWidget):
        pending = [
            view.topLevelItem(row)
            for row in range(view.topLevelItemCount())
        ]
        while pending:
            item = pending.pop()
            if item.data(0, SETTINGS_ROW_PRIMITIVE_ROLE) == "list-or-table-row":
                item.setData(0, SETTINGS_ROW_TARGET_ROLE, target)
                row_widget = view.itemWidget(item, 0)
                item_target = (
                    _event_row_target_height(view, row_widget)
                    if row_widget is not None and row_widget.objectName() == "EventRow"
                    else target
                )
                for column in range(view.columnCount()):
                    width = (
                        view.fontMetrics().horizontalAdvance(item.text(column))
                        + (2 * view.fontMetrics().lineSpacing())
                    )
                    item.setSizeHint(column, QSize(max(1, width), item_target))
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
    """Stable desktop rail; compact navigation takes over before wrapping."""

    _ITEM_HORIZONTAL_INSET = 24
    _ITEM_VERTICAL_INSET = 12

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setProperty("hdoPrimitive", _settings_primitive("settings-sidebar"))
        self.setObjectName("SettingsNav")
        self.setAccessibleName("Settings sections")
        self.setAccessibleDescription("Choose a Home Screen Dashboard settings section")
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setWordWrap(False)
        self.setTextElideMode(Qt.TextElideMode.ElideNone)
        self.setUniformItemSizes(False)
        self.setFixedWidth(SETTINGS_SIDEBAR_WIDTH)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

    def refresh_item_sizes(self) -> None:
        """Keep one consistent row height without wrapping or elision."""
        metrics = self.fontMetrics()
        for row in range(self.count()):
            item = self.item(row)
            if item is None:
                continue
            item.setSizeHint(
                QSize(0, max(36, metrics.lineSpacing() + self._ITEM_VERTICAL_INSET))
            )

    def changeEvent(self, event: QEvent) -> None:
        super().changeEvent(event)
        if event.type() == QEvent.Type.FontChange:
            self.refresh_item_sizes()

    def measured_width(self) -> int:
        return SETTINGS_SIDEBAR_WIDTH

    def labels_fit(self) -> bool:
        available = max(1, self.width() - self._ITEM_HORIZONTAL_INSET)
        metrics = self.fontMetrics()
        return all(
            metrics.horizontalAdvance(self.item(row).text()) <= available
            for row in range(self.count())
            if self.item(row) is not None
        )


class NeutralSettingsTabBar(QTabBar):
    """Paint the unused tab-strip remainder with the Settings surface token."""

    def paintEvent(self, event: Any) -> None:
        super().paintEvent(event)
        last_right = self.tabRect(self.count() - 1).right() + 1 if self.count() else 0
        if last_right >= self.width():
            return
        tokens = getattr(self.window(), "_hdo_theme_tokens", _palette_tokens())
        painter = QPainter(self)
        painter.fillRect(
            QRect(last_right, 0, self.width() - last_right, self.height()),
            QColor(tokens["alternate"]),
        )
        painter.setPen(QColor(tokens["border"]))
        painter.drawLine(last_right, self.height() - 1, self.width(), self.height() - 1)


class SettingsTabPanel(QWidget):
    """Neutral tab strip plus stacked pages without native tab-pane tinting."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("EventTabs")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._tab_bar = NeutralSettingsTabBar(self)
        self._tab_bar.setObjectName("EventTabsBar")
        self._tab_bar.setDocumentMode(True)
        self._tab_bar.setExpanding(False)
        self._tab_bar.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self._pages = QStackedWidget(self)
        self._pages.setObjectName("EventTabPages")
        self._pages.setMinimumWidth(0)
        layout.addWidget(self._tab_bar)
        layout.addWidget(self._pages, 1)
        self._tab_bar.currentChanged.connect(self._pages.setCurrentIndex)

    def addTab(self, widget: QWidget, label: str) -> int:
        page_index = self._pages.addWidget(widget)
        tab_index = self._tab_bar.addTab(label)
        if self._tab_bar.count() == 1:
            self._tab_bar.setCurrentIndex(0)
            self._pages.setCurrentIndex(0)
        return min(page_index, tab_index)

    def tabBar(self) -> QTabBar:
        return self._tab_bar

    def currentIndex(self) -> int:
        return self._tab_bar.currentIndex()

    def setCurrentIndex(self, index: int) -> None:
        self._tab_bar.setCurrentIndex(index)

    def setTabText(self, index: int, text: str) -> None:
        self._tab_bar.setTabText(index, text)


class SettingsStatusIndicator(QWidget):
    """Small animated saving spinner and vector state indicator."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFixedSize(18, 18)
        self._state = ""
        self._angle = 0
        self._timer = QTimer(self)
        self._timer.setInterval(80)
        self._timer.timeout.connect(self._advance)

    def set_state(self, state: str) -> None:
        self._state = str(state)
        if self._state == "saving":
            if not self._timer.isActive():
                self._timer.start()
        else:
            self._timer.stop()
        self.update()

    def _advance(self) -> None:
        self._angle = (self._angle + 30) % 360
        self.update()

    def paintEvent(self, event: Any) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if self._state == "saving":
            pen = QPen(QColor(_palette_tokens()["highlight"]))
            pen.setWidthF(2.2)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.setBrush(QBrush(Qt.BrushStyle.NoBrush))
            painter.drawArc(
                self.rect().adjusted(3, 3, -3, -3),
                self._angle * 16,
                270 * 16,
            )
            return
        icon_kind = {
            "dirty": "warning",
            "validation-error": "error",
            "saved": "success",
            "discarded": "success",
        }.get(self._state, "")
        if icon_kind:
            _settings_vector_icon(icon_kind).paint(painter, self.rect())


class SettingsFooter(QWidget):
    """Sticky action-local feedback footer; it never overlays page content."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setProperty("hdoPrimitive", _settings_primitive("settings-footer"))
        self.setObjectName("ActionBar")
        self.outer = QVBoxLayout(self)
        self.outer.setContentsMargins(16, 8, 16, 8)
        self.outer.setSpacing(8)
        self.error_panel = QWidget(self)
        self.error_panel.setObjectName("SaveErrorPanel")
        error_layout = QGridLayout(self.error_panel)
        error_layout.setContentsMargins(0, 0, 0, 0)
        error_layout.setHorizontalSpacing(8)
        error_layout.setVerticalSpacing(4)
        self.error_label = QLabel("")
        self.error_label.setObjectName("InlineSaveError")
        self.error_label.setWordWrap(True)
        self.error_label.setProperty("hdoLiveRegion", "assertive")
        self.details_button = QPushButton("View details")
        self.details_button.setObjectName("LinkButton")
        self.copy_error_button = QPushButton("Copy error")
        self.copy_error_button.setObjectName("LinkButton")
        self.copy_error_button.setIcon(_settings_vector_icon("copy"))
        self.details_text = QLabel("")
        self.details_text.setObjectName("FieldHelp")
        self.details_text.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.details_text.setWordWrap(True)
        self.details_text.hide()
        self._details_callback: Optional[Callable[[], None]] = None
        self.details_button.clicked.connect(self._show_details)
        self.copy_error_button.clicked.connect(self._copy_error)
        self._copy_reset_timer = QTimer(self)
        self._copy_reset_timer.setSingleShot(True)
        self._copy_reset_timer.timeout.connect(self._reset_copy_error_label)
        error_layout.addWidget(self.error_label, 0, 0, 1, 3)
        error_layout.addWidget(self.details_button, 1, 0, Qt.AlignmentFlag.AlignLeft)
        error_layout.addWidget(self.copy_error_button, 1, 1, Qt.AlignmentFlag.AlignLeft)
        error_layout.setColumnStretch(0, 1)
        self.error_panel.hide()
        self.outer.addWidget(self.error_panel)

        self.grid = QGridLayout()
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(8)
        self.grid.setVerticalSpacing(6)
        self.status_label = QLabel("")
        self.status_label.setObjectName("FooterStatus")
        self.status_label.setAccessibleName("Settings save status")
        self.status_label.setProperty("hdoLiveRegion", "polite")
        self.status_icon = SettingsStatusIndicator(self)
        self.status_container = QWidget(self)
        status_layout = QHBoxLayout(self.status_container)
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setSpacing(6)
        status_layout.addWidget(self.status_icon)
        status_layout.addWidget(self.status_label)
        self.status_container.hide()
        self.left_actions = QHBoxLayout()
        self.left_actions.setContentsMargins(0, 0, 0, 0)
        self.left_actions.setSpacing(8)
        self.left_container = QWidget(self)
        self.left_container.setLayout(self.left_actions)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        self.grid.addWidget(self.status_container, 0, 0)
        self.grid.addWidget(self.left_container, 0, 1)
        self.grid.addWidget(self.buttons, 0, 2, Qt.AlignmentFlag.AlignRight)
        self.grid.setColumnStretch(0, 1)
        self.outer.addLayout(self.grid)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(SETTINGS_FOOTER_MIN_HEIGHT)
        self._compact = False

    def inline_width_hint(self) -> int:
        margins = self.grid.contentsMargins()
        return margins.left() + margins.right() + self.buttons.sizeHint().width()

    def add_left_widget(self, widget: QWidget, stretch: int = 0) -> None:
        self.left_actions.addWidget(widget, stretch)

    def set_compact(self, compact: bool) -> None:
        compact = bool(compact)
        if self._compact == compact:
            return
        self._compact = compact
        for widget in (self.status_container, self.left_container, self.buttons):
            self.grid.removeWidget(widget)
        if compact:
            self.grid.addWidget(self.status_container, 0, 0, 1, 3)
            self.grid.addWidget(self.left_container, 1, 0)
            self.grid.addWidget(self.buttons, 1, 2, Qt.AlignmentFlag.AlignRight)
        else:
            self.grid.addWidget(self.status_container, 0, 0)
            self.grid.addWidget(self.left_container, 0, 1)
            self.grid.addWidget(self.buttons, 0, 2, Qt.AlignmentFlag.AlignRight)

    def set_details_callback(self, callback: Callable[[], None]) -> None:
        self._details_callback = callback

    def _show_details(self) -> None:
        if self._details_callback is not None:
            self._details_callback()

    def _copy_error(self) -> None:
        details = self.details_text.text().strip()
        if details:
            QApplication.clipboard().setText(details)
            self.copy_error_button.setText("Error copied")
            self._copy_reset_timer.start(2000)

    def _reset_copy_error_label(self) -> None:
        self.copy_error_button.setText("Copy error")

    def set_error(self, message: str = "", details: str = "") -> None:
        self.error_label.setText(message)
        self.details_text.setText(details)
        self.details_button.setVisible(bool(details))
        self.copy_error_button.setVisible(bool(details))
        self.error_panel.setVisible(bool(message))
        self.status_container.setVisible(
            bool(self.status_label.text()) and not bool(message)
        )

    def set_status(self, state: str, text: str) -> None:
        self.status_icon.set_state(state)
        self.status_label.setText(text)
        self.status_container.setVisible(bool(text) and self.error_panel.isHidden())


class SettingsFooterShell(QWidget):
    """Report final footer-shell geometry without installing dialog filters."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._geometry_callback: Optional[Callable[[], None]] = None

    def set_geometry_callback(self, callback: Callable[[], None]) -> None:
        self._geometry_callback = callback

    def resizeEvent(self, event: Any) -> None:
        super().resizeEvent(event)
        if self._geometry_callback is not None:
            self._geometry_callback()


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


class ElidingLabel(QLabel):
    """Intentional single-line elision used only for approved row titles."""

    def __init__(self, text: str, parent: Optional[QWidget] = None) -> None:
        super().__init__("", parent)
        self._full_text = str(text)
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self._update_text()

    def _update_text(self) -> None:
        available = max(1, self.width())
        visible = self.fontMetrics().elidedText(
            self._full_text,
            Qt.TextElideMode.ElideRight,
            available,
        )
        super().setText(visible)
        self.setToolTip(self._full_text if visible != self._full_text else "")

    def resizeEvent(self, event: Any) -> None:
        self._update_text()
        super().resizeEvent(event)


class EventRowWidget(QWidget):
    """Shared legible two-line event row with one compact overflow action."""

    def __init__(
        self,
        tree: QTreeWidget,
        item: QTreeWidgetItem,
        title: str,
        metadata: str,
        activate: Optional[Callable[[], None]] = None,
    ) -> None:
        super().__init__(tree)
        self.tree = tree
        self.item = item
        self._activate = activate
        self.setObjectName("EventRow")
        self.setProperty("pressed", False)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 6, 6)
        layout.setSpacing(8)
        copy = QVBoxLayout()
        copy.setContentsMargins(0, 0, 0, 0)
        copy.setSpacing(1)
        self.title = ElidingLabel(title)
        self.title.setObjectName("EventRowTitle")
        self.metadata = QLabel(metadata)
        self.metadata.setObjectName("EventRowMeta")
        for label in (self.title, self.metadata):
            label.setTextFormat(Qt.TextFormat.PlainText)
            label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        copy.addWidget(self.title)
        copy.addWidget(self.metadata)
        layout.addLayout(copy, 1)
        self.overflow = QPushButton("")
        self.overflow.setObjectName("EventOverflowButton")
        self.overflow.setIcon(_settings_vector_icon("ellipsis"))
        self.overflow.setIconSize(QSize(16, 16))
        self.overflow.setFixedSize(32, 32)
        layout.addWidget(self.overflow, 0, Qt.AlignmentFlag.AlignVCenter)

    def mousePressEvent(self, event: Any) -> None:
        self.tree.setCurrentItem(self.item)
        if event.button() == Qt.MouseButton.LeftButton:
            self._set_pressed(True)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: Any) -> None:
        self._set_pressed(False)
        if event.button() == Qt.MouseButton.LeftButton and self._activate is not None:
            self._activate()
        super().mouseReleaseEvent(event)

    def leaveEvent(self, event: Any) -> None:
        self._set_pressed(False)
        super().leaveEvent(event)

    def _set_pressed(self, pressed: bool) -> None:
        if bool(self.property("pressed")) == bool(pressed):
            return
        self.setProperty("pressed", bool(pressed))
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()


class VerseLibraryModel(QAbstractListModel):
    """Complete filtered verse model; rendering never truncates the library."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._quotes: List[str] = []
        self._rows: List[tuple[int, str, str]] = []
        self._filter = ""
        self._current_source_index: Optional[int] = None
        self._pending_source_index: Optional[int] = None

    def set_source(
        self,
        quotes: List[str],
        filter_text: str = "",
        current: str = "",
        pending: str = "",
        pending_source_index: Optional[int] = None,
    ) -> None:
        self.beginResetModel()
        self._quotes = list(quotes)
        self._filter = str(filter_text or "").strip().casefold()
        self._current_source_index = next(
            (
                source_index
                for source_index, quote in enumerate(self._quotes)
                if quote == current
            ),
            None,
        )
        self._pending_source_index = None
        if pending:
            if (
                pending_source_index is not None
                and 0 <= pending_source_index < len(self._quotes)
                and self._quotes[pending_source_index] == pending
            ):
                self._pending_source_index = pending_source_index
            else:
                self._pending_source_index = next(
                    (
                        source_index
                        for source_index, quote in enumerate(self._quotes)
                        if quote == pending
                    ),
                    None,
                )
        self._rows = []
        for source_index, quote in enumerate(self._quotes):
            body_value, reference_value = split_quote_reference(quote)
            body = html_module.unescape(re.sub(r"<[^>]+>", "", body_value)).strip()
            reference = html_module.unescape(
                re.sub(r"<[^>]+>", "", reference_value)
            ).strip() or "Custom verse"
            excerpt = re.sub(r"\s+", " ", body).strip()
            searchable = "{} {}".format(reference, excerpt).casefold()
            if self._filter and self._filter not in searchable:
                continue
            self._rows.append((source_index, reference, excerpt))
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._rows)

    def data(self, index: QModelIndex, role: int = int(Qt.ItemDataRole.DisplayRole)) -> Any:
        if not index.isValid() or not 0 <= index.row() < len(self._rows):
            return None
        source_index, reference, excerpt = self._rows[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return "{} — {}".format(reference, excerpt)
        if role == Qt.ItemDataRole.ToolTipRole:
            return "{}\n{}".format(reference, excerpt)
        if role == VERSE_SOURCE_INDEX_ROLE:
            return source_index
        if role == VERSE_REFERENCE_ROLE:
            return reference
        if role == VERSE_EXCERPT_ROLE:
            return excerpt
        if role == VERSE_CURRENT_ROLE:
            return (
                self._pending_source_index is None
                and source_index == self._current_source_index
            )
        if role == VERSE_PENDING_ROLE:
            return source_index == self._pending_source_index
        return None

    def source_index(self, index: QModelIndex) -> Optional[int]:
        value = self.data(index, VERSE_SOURCE_INDEX_ROLE)
        return int(value) if isinstance(value, int) else None

    def model_index_for_source(self, source_index: object) -> QModelIndex:
        try:
            target = int(source_index)
        except (TypeError, ValueError):
            return QModelIndex()
        for row, (candidate, _reference, _excerpt) in enumerate(self._rows):
            if candidate == target:
                return self.index(row, 0)
        return QModelIndex()

    @property
    def matching_count(self) -> int:
        return len(self._rows)


def _two_line_excerpt(text: str, metrics: QFontMetrics, width: int) -> str:
    """Wrap plain text to two lines and elide only the second line."""

    words = str(text or "").split()
    if not words:
        return ""
    lines: List[str] = []
    remaining = words
    for _line in range(2):
        current: List[str] = []
        while remaining:
            candidate = " ".join(current + [remaining[0]])
            if current and metrics.horizontalAdvance(candidate) > width:
                break
            current.append(remaining.pop(0))
        lines.append(" ".join(current))
        if not remaining:
            break
    if remaining and lines:
        lines[-1] = metrics.elidedText(
            "{} {}".format(lines[-1], " ".join(remaining)).strip(),
            Qt.TextElideMode.ElideRight,
            max(1, width),
        )
    return "\n".join(lines)


class VerseLibraryDelegate(QStyledItemDelegate):
    """Two-line, token-painted rows for the complete verse list model."""

    def sizeHint(self, option: Any, index: QModelIndex) -> QSize:
        del index
        metrics = QFontMetrics(option.font)
        return QSize(max(1, option.rect.width()), max(68, metrics.lineSpacing() * 3 + 20))

    def paint(self, painter: QPainter, option: Any, index: QModelIndex) -> None:
        painter.save()
        tokens = _palette_tokens()
        rect = option.rect
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        semantic = bool(index.data(VERSE_CURRENT_ROLE) or index.data(VERSE_PENDING_ROLE))
        painter.fillRect(rect, QColor(tokens["accent_soft"] if selected or semantic else tokens["base"]))
        if selected or semantic:
            painter.fillRect(QRect(rect.left(), rect.top(), 3, rect.height()), QColor(tokens["highlight"]))
        painter.setPen(QPen(QColor(tokens["border"]), 1))
        painter.drawLine(rect.bottomLeft(), rect.bottomRight())

        content = rect.adjusted(34, 8, -48, -8)
        reference = str(index.data(VERSE_REFERENCE_ROLE) or "Custom verse")
        excerpt = str(index.data(VERSE_EXCERPT_ROLE) or "")
        reference_font = QFont(option.font)
        reference_font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(reference_font)
        reference_metrics = QFontMetrics(reference_font)
        first_line = reference_metrics.elidedText(
            reference,
            Qt.TextElideMode.ElideRight,
            max(1, content.width() - (22 if semantic else 0)),
        )
        painter.setPen(QColor(tokens["text"]))
        painter.drawText(
            QRect(content.left(), content.top(), content.width(), reference_metrics.lineSpacing()),
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            first_line,
        )
        indicator = QRect(rect.left() + 12, content.top() + 2, 12, 12)
        painter.setPen(QPen(QColor(tokens["highlight"] if semantic else tokens["border_strong"]), 1.5))
        painter.setBrush(QBrush(QColor(tokens["highlight"])) if semantic else QBrush(Qt.BrushStyle.NoBrush))
        painter.drawEllipse(indicator)
        if semantic:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(tokens["highlight_text"]))
            painter.drawEllipse(indicator.adjusted(4, 4, -4, -4))

        excerpt_font = QFont(option.font)
        painter.setFont(excerpt_font)
        excerpt_metrics = QFontMetrics(excerpt_font)
        excerpt_top = content.top() + reference_metrics.lineSpacing() + 3
        excerpt_rect = QRect(
            content.left(),
            excerpt_top,
            content.width(),
            excerpt_metrics.lineSpacing() * 2,
        )
        painter.setPen(QColor(tokens["secondary"]))
        painter.drawText(
            excerpt_rect,
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop),
            _two_line_excerpt(excerpt, excerpt_metrics, excerpt_rect.width()),
        )
        menu_rect = QRect(rect.right() - 39, rect.center().y() - 16, 32, 32)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(tokens["secondary"]))
        dot_radius = 2
        for offset in (-6, 0, 6):
            painter.drawEllipse(
                QPoint(menu_rect.center().x() + offset, menu_rect.center().y()),
                dot_radius,
                dot_radius,
            )
        painter.restore()


class VerseLibraryView(QListView):
    """Virtualized list with a real 32 px trailing action target per row."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("VerseLibraryView")
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setItemDelegate(VerseLibraryDelegate(self))
        self.setMinimumHeight(260)
        self.setMaximumHeight(16777215)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._menu_callback: Optional[Callable[[QModelIndex, QPoint], None]] = None

    def set_menu_callback(
        self,
        callback: Callable[[QModelIndex, QPoint], None],
    ) -> None:
        self._menu_callback = callback

    def mousePressEvent(self, event: Any) -> None:
        point = event.position().toPoint() if hasattr(event, "position") else event.pos()
        index = self.indexAt(point)
        if index.isValid() and point.x() >= self.viewport().width() - 44:
            self.setCurrentIndex(index)
            if self._menu_callback is not None:
                self._menu_callback(index, self.viewport().mapToGlobal(point))
            event.accept()
            return
        super().mousePressEvent(event)


class ContextualActionGroup(QWidget):
    """Reusable content-sized action row in the canonical Settings tree."""

    def __init__(
        self,
        direction: QBoxLayout.Direction = QBoxLayout.Direction.LeftToRight,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("ContextualActionGroup")
        self.setMinimumWidth(0)
        self.setProperty(
            "hdoPrimitive",
            _settings_primitive("contextual-action-group"),
        )
        self.box = QBoxLayout(direction, self)
        self.box.setContentsMargins(0, 0, 0, 0)
        self.box.setSpacing(6)

    def add_widget(self, widget: QWidget, stretch: int = 0) -> None:
        self.box.addWidget(widget, stretch)

    def add_stretch(self) -> None:
        self.box.addStretch()

class WrappingActionGroup(QWidget):
    """Horizontal actions that wrap to a second row at minimum width."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("ContextualActionGroup")
        self.setMinimumWidth(0)
        self.setProperty(
            "hdoPrimitive",
            _settings_primitive("contextual-action-group"),
        )
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(6)
        self.grid.setVerticalSpacing(6)
        self.widgets: List[QWidget] = []

    def add_widget(self, widget: QWidget) -> None:
        self.widgets.append(widget)
        for widget in self.widgets:
            self.grid.removeWidget(widget)
        columns = max(1, len(self.widgets))
        for index, widget in enumerate(self.widgets):
            self.grid.addWidget(widget, index // columns, index % columns)
        for column in range(max(1, len(self.widgets))):
            self.grid.setColumnStretch(column, 1 if column < columns else 0)
        self.grid.invalidate()


class SettingsEditorDialog(QDialog):
    """Shared themed, contained editor shell for Settings-owned modals."""

    def __init__(self, parent: QWidget, window_title: str, heading: str) -> None:
        super().__init__(parent)
        del heading
        self.setObjectName("HomeDashboardEditor")
        self.setProperty("hdoPrimitive", _settings_primitive("editor-dialog"))
        self._style_factory = lambda: _editor_style(_editor_tokens(parent))
        self.setStyleSheet(self._style_factory())
        _install_palette_watcher(self, self._style_factory)
        self.setWindowTitle(window_title)
        self.setSizeGripEnabled(True)
        self.body_layout = QVBoxLayout(self)
        _apply_role_fonts(self)

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
    if minimum == "Unknown":
        return "Anki Desktop compatibility unknown"
    if maximum == minimum:
        return "Supports Anki Desktop {}".format(minimum)
    if maximum != "Unknown":
        return "Supports Anki Desktop {}–{}".format(minimum, maximum)
    return "Requires Anki {} or later".format(minimum)


def _editor_tokens(parent: QWidget) -> Dict[str, str]:
    # Native Settings dialogs follow Anki even while a dashboard preset is
    # staged. Preset colors are confined to dashboard and swatch surfaces.
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


class SuffixNumberField(QWidget):
    """Validated integer field with a stable textual unit and no spin chrome."""

    def __init__(
        self,
        minimum: int,
        maximum: int,
        value: int,
        suffix: str,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("SuffixNumberField")
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self._minimum = int(minimum)
        self._maximum = int(maximum)
        self._last_valid = max(self._minimum, min(self._maximum, int(value)))
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.editor = QLineEdit(str(self._last_valid), self)
        self.editor.setObjectName("SuffixNumberEditor")
        self.editor.setValidator(QIntValidator(self._minimum, self._maximum, self.editor))
        self.editor.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.editor.setMinimumWidth(56)
        self.editor.setMaximumWidth(76)
        self.suffix_label = QLabel(suffix, self)
        self.suffix_label.setObjectName("NumberSuffix")
        layout.addWidget(self.editor)
        layout.addWidget(self.suffix_label)
        self.editor.editingFinished.connect(self._commit)
        self.editor.textChanged.connect(self._refresh_validation_state)
        self._refresh_validation_state()

    def value(self) -> int:
        try:
            value = int(self.editor.text())
        except (TypeError, ValueError):
            return self._last_valid
        return max(self._minimum, min(self._maximum, value))

    def setValue(self, value: object) -> None:
        try:
            candidate = int(value)
        except (TypeError, ValueError, OverflowError):
            candidate = self._last_valid
        self._last_valid = max(self._minimum, min(self._maximum, candidate))
        self.editor.setText(str(self._last_valid))

    def is_valid(self) -> bool:
        text = self.editor.text().strip()
        if not text:
            return False
        try:
            value = int(text)
        except ValueError:
            return False
        return self._minimum <= value <= self._maximum

    def connect_changed(self, callback: Callable[..., None]) -> None:
        self.editor.textChanged.connect(callback)

    def setAccessibleName(self, name: str) -> None:
        super().setAccessibleName(name)
        self.editor.setAccessibleName(name)

    def setAccessibleDescription(self, description: str) -> None:
        super().setAccessibleDescription(description)
        self.editor.setAccessibleDescription(description)

    def _commit(self) -> None:
        text = self.editor.text().strip()
        try:
            candidate = int(text)
        except (TypeError, ValueError):
            candidate = self._last_valid
        self._last_valid = max(self._minimum, min(self._maximum, candidate))
        self.editor.setText(str(self._last_valid))

    def _refresh_validation_state(self, *_args: object) -> None:
        invalid = not self.is_valid()
        self.editor.setProperty("invalid", invalid)
        self.editor.setToolTip(
            "Enter a value from {} to {}.".format(self._minimum, self._maximum)
            if invalid
            else ""
        )
        style = self.editor.style()
        style.unpolish(self.editor)
        style.polish(self.editor)


class TextEditDialog(SettingsEditorDialog):
    def __init__(self, title: str, value: str, parent: QWidget) -> None:
        super().__init__(parent, title, "")
        self._reference_required = title.startswith("Add")
        body_value, reference_value = split_quote_reference(value)
        label = QLabel(
            "Body and reference are staged here. Simple bold or italic emphasis is sanitized before display."
        )
        label.setTextFormat(Qt.TextFormat.PlainText)
        label.setObjectName("EditorHelp")
        label.setWordWrap(True)
        self.body_layout.addWidget(label)
        self.editor = QPlainTextEdit(body_value)
        _set_accessibility(
            self.editor,
            "Bible verse text",
            "Enter the Bible verse body. Supported simple emphasis tags are sanitized before display.",
        )
        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.addRow("Body", self.editor)
        self.reference = QLineEdit(reference_value)
        _set_accessibility(
            self.reference,
            "Bible verse reference",
            (
                "Required for new entries. For example, Romans 4:5 (NLT)."
                if self._reference_required
                else "For example, Romans 4:5 (NLT). Legacy entries may leave this blank."
            ),
        )
        form.addRow("Reference", self.reference)
        self.body_layout.addLayout(form, 1)
        self.editor_count = QLabel("")
        self.editor_count.setObjectName("EditorHelp")
        self.editor_count.setAccessibleName("Verse entry size")
        self.body_layout.addWidget(self.editor_count)
        self.validation_label = QLabel("")
        self.validation_label.setObjectName("EditorError")
        self.validation_label.setWordWrap(True)
        self.body_layout.addWidget(self.validation_label)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        save_button = buttons.button(QDialogButtonBox.StandardButton.Save)
        self.apply_button = save_button
        if save_button is not None:
            save_button.setObjectName("PrimaryButton")
            save_button.setText("Add" if title.startswith("Add") else "Apply changes")
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        self.body_layout.addWidget(buttons)
        self.editor.textChanged.connect(self._update_count)
        self.reference.textChanged.connect(self._update_count)
        self._update_count()
        self._fit_editor(72, 52, 22, 16)

    def value(self) -> str:
        return serialize_quote_reference(
            self.editor.toPlainText(),
            self.reference.text(),
        )

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
        has_body = bool(self.editor.toPlainText().strip())
        has_reference = bool(self.reference.text().strip())
        within_limit = verse_within_limit(value)
        if not has_body:
            message = "Enter a Bible verse body."
        elif self._reference_required and not has_reference:
            message = "Enter the verse reference."
        elif not within_limit:
            message = "Shorten this entry to at most 4,000 characters and 16,000 UTF-8 bytes."
        else:
            message = ""
        self.validation_label.setText(message)
        if self.apply_button is not None:
            self.apply_button.setEnabled(not bool(message))

    def _accept_if_valid(self) -> None:
        value = self.value()
        if not self.editor.toPlainText().strip():
            self.validation_label.setText("Enter a Bible verse body.")
            self.editor.setFocus()
            return
        if self._reference_required and not self.reference.text().strip():
            self.validation_label.setText("Enter the verse reference.")
            self.reference.setFocus()
            return
        if not verse_within_limit(value):
            self.validation_label.setText(
                "Shorten this entry to at most 4,000 characters and 16,000 UTF-8 bytes."
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
            "",
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
            "Calendar cells display an event marker. The full event name appears in the integrated calendar footer and calendar tooltip."
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
        self.validation_label = QLabel("")
        self.validation_label.setObjectName("EditorError")
        self.validation_label.setWordWrap(True)
        self.date = QDateEdit()
        self.date.setCalendarPopup(True)
        self.date.setDisplayFormat("dddd, MMMM d, yyyy")
        _set_accessibility(self.date, "Event date", "Choose the civil-calendar date for this local event.")
        value = str(item.get("date", "")) if item else initial_date
        parsed = QDate.fromString(value, "yyyy-MM-dd") if value else QDate.currentDate()
        self.date.setDate(parsed if parsed.isValid() else QDate.currentDate())
        name_label_row = QWidget()
        name_label_layout = QHBoxLayout(name_label_row)
        name_label_layout.setContentsMargins(0, 0, 0, 0)
        name_label_layout.addWidget(QLabel("Name"))
        name_label_layout.addStretch()
        name_label_layout.addWidget(self.name_count)
        form.addRow(name_label_row)
        form.addRow(self.name)
        form.addRow("", self.validation_label)
        form.addRow("", self.name_help)
        form.addRow("Date", self.date)
        form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.body_layout.addLayout(form)
        self.body_layout.addStretch(1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        save_button = buttons.button(QDialogButtonBox.StandardButton.Save)
        self.apply_button = save_button
        if save_button is not None:
            save_button.setObjectName("PrimaryButton")
            save_button.setText("Apply changes" if item else "Add")
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        self.body_layout.addWidget(buttons)
        self._update_name_count(self.name.text())
        self._fit_editor(60, 42, 16, 12)
        screen = self.screen()
        available = screen.availableGeometry() if screen is not None else QRect(0, 0, 560, 320)
        width = max(320, min(440, available.width() - 96))
        height = max(240, min(320, available.height() - 96))
        self.setMinimumSize(min(440, width), min(320, height))
        self.resize(width, height)

    def _update_name_count(self, value: str) -> None:
        self.name_count.setText("{} of 160 characters.".format(len(value)))
        valid = bool(value.strip())
        self.validation_label.setText("" if valid else "Enter an event name.")
        if self.apply_button is not None:
            self.apply_button.setEnabled(valid)

    def _accept_if_valid(self) -> None:
        if not self.name.text().strip():
            self.validation_label.setText("Enter an event name.")
            self.name.setFocus()
            return
        self.accept()

    def values(self) -> tuple[str, str]:
        return self.name.text().strip(), self.date.date().toString("yyyy-MM-dd")


class SettingsPromptPage(QWidget):
    """Layout-managed confirmation page that never creates or stacks a window."""

    def __init__(
        self,
        parent: QWidget,
        owner: "SettingsDialog",
        title: str,
        message: str,
        actions: List[tuple[str, str, Callable[[], None]]],
        dismiss: Callable[[], None],
    ) -> None:
        super().__init__(parent)
        self.owner = owner
        self.setObjectName("SettingsPromptPage")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._dismiss_callback = dismiss
        self._action_buttons: List[QPushButton] = []
        self._default_button: Optional[QPushButton] = None
        self.refresh_palette()

        layout = QGridLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        card = QFrame(self)
        card.setObjectName("SettingsPromptCard")
        card.setMinimumSize(380, 190)
        card.setMaximumWidth(420)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 20, 24, 20)
        card_layout.setSpacing(12)
        heading = QLabel(title)
        heading.setObjectName("SettingsPromptTitle")
        heading.setWordWrap(True)
        copy = QLabel(message)
        copy.setObjectName("SettingsPromptMessage")
        copy.setTextFormat(Qt.TextFormat.PlainText)
        copy.setWordWrap(True)
        card_layout.addWidget(heading)
        card_layout.addWidget(copy)
        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, 4, 0, 0)
        buttons.setSpacing(8)
        buttons.addStretch(1)
        for label, role, callback in actions:
            button = QPushButton(label)
            if role == "primary":
                button.setObjectName("PrimaryButton")
                self._default_button = button
            elif role == "danger":
                button.setObjectName("DangerButton")
            button.clicked.connect(
                lambda _checked=False, selected=callback: self._choose(selected)
            )
            self._action_buttons.append(button)
            buttons.addWidget(button)
        if self._default_button is None and self._action_buttons:
            self._default_button = self._action_buttons[0]
        card_layout.addLayout(buttons)
        layout.addWidget(card, 0, 0, Qt.AlignmentFlag.AlignCenter)
        self.escape_action = QAction("Dismiss confirmation", self)
        self.escape_action.setShortcut(QKeySequence("Esc"))
        self.escape_action.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.escape_action.triggered.connect(self.dismiss)
        self.addAction(self.escape_action)

    def refresh_palette(self) -> None:
        tokens = _palette_tokens()
        self.setStyleSheet(
            """
QWidget#SettingsPromptPage {{ background: {overlay}; }}
QFrame#SettingsPromptCard {{ background: {window}; border: 1px solid {border}; border-radius: 10px; }}
QLabel#SettingsPromptTitle {{ color: {text}; font-weight: 750; }}
QLabel#SettingsPromptMessage {{ color: {secondary}; }}
QPushButton {{ background: {button}; border: 1px solid {border}; border-radius: 7px; color: {button_text}; min-height: 36px; padding: 0 12px; font-weight: 600; }}
QPushButton#PrimaryButton {{ background: {highlight}; border-color: {highlight}; color: {highlight_text}; font-weight: 750; }}
QPushButton#DangerButton {{ background: {danger_bg}; border-color: {danger}; color: {danger}; font-weight: 650; }}
""".format(**tokens)
        )

    def focus_default_action(self) -> None:
        if self._default_button is not None:
            self._default_button.setFocus(Qt.FocusReason.OtherFocusReason)

    def focusNextPrevChild(self, next_child: bool) -> bool:
        if not self._action_buttons:
            return super().focusNextPrevChild(next_child)
        current = QApplication.focusWidget()
        try:
            index = self._action_buttons.index(current)
        except ValueError:
            index = -1 if next_child else 0
        offset = 1 if next_child else -1
        self._action_buttons[(index + offset) % len(self._action_buttons)].setFocus(
            Qt.FocusReason.TabFocusReason
        )
        return True

    def dismiss(self) -> None:
        self._finish(self._dismiss_callback)

    def dismiss_without_callback(self) -> None:
        self._finish(None)

    def _choose(self, callback: Callable[[], None]) -> None:
        self._finish(callback)

    def _finish(self, callback: Optional[Callable[[], None]]) -> None:
        self.owner._finish_prompt(self, callback)


class SettingsDialog(QDialog):
    def __init__(
        self,
        parent: QWidget,
        controller: Any,
        initial_page: str = "",
        selected_event_date: str = "",
        selected_event_id: str = "",
    ) -> None:
        super().__init__(parent)
        self.controller = controller
        self.draft = SettingsDraft(controller.config)
        self.staged = deepcopy(self.draft.values)
        self._heatmap_preset_preferences = deepcopy(
            self.staged.get("heatmap", {}).get("presets_by_theme", {})
        )
        self.quotes = list(self.staged["bible"]["quotes"])
        self._saved_current_quote = self._read_current_quote(self.staged)
        self.pending_manual_quote: Optional[str] = None
        self._pending_manual_quote_index: Optional[int] = None
        self._staged_deleted_quotes: List[str] = []
        self._font_family_touched = False
        self._font_color_invalid = False
        self.page_indices: Dict[str, int] = {}
        self.nav_rows: Dict[str, int] = {}
        self.selected_event_date = selected_event_date
        self.selected_event_id = selected_event_id
        self.current_section = "dashboard"
        self._requested_dashboard_anchor = ""
        self._building = True
        self._allow_close = False
        self._saving = False
        self._pending_close_after_save = False
        self._queued_save_state: Optional[
            tuple[Dict[str, Any], Dict[str, Any], Optional[str]]
        ] = None
        self._save_dispatch_timer = QTimer(self)
        self._save_dispatch_timer.setSingleShot(True)
        self._save_dispatch_timer.timeout.connect(self._continue_save)
        self._theme_palette_refresh_pending = False
        self._theme_palette_stage_timer = QTimer(self)
        self._theme_palette_stage_timer.setSingleShot(True)
        self._theme_palette_stage_timer.timeout.connect(
            self._flush_theme_palette_stage
        )
        self._mutation_enabled_states: Dict[QWidget, bool] = {}
        self._active_prompt: Optional[SettingsPromptPage] = None
        self._focus_before_prompt: Optional[QWidget] = None
        self._last_save_error = ""
        self._last_save_error_detail = ""
        self._last_export_error = ""
        self._export_copy_timer = QTimer(self)
        self._export_copy_timer.setSingleShot(True)
        self._export_copy_timer.timeout.connect(self._reset_export_copy_labels)
        self._undo_record: Optional[Dict[str, Any]] = None
        self._settings_scroll_base_margins: Dict[
            QScrollArea, tuple[int, int, int, int]
        ] = {}
        self._compact_layout = False
        self._screen_compact_fallback = False
        self._post_show_clamp_done = False
        self._syncing_navigation = False
        self._geometry_settings = QSettings()
        self.setObjectName("HomeDashboardSettings")
        self.setWindowTitle("Home Screen Dashboard Settings")
        self._apply_initial_window_geometry(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._hdo_theme_tokens = _theme_tokens(self.staged, self.controller.is_dark())
        self.setStyleSheet(_settings_style(self.staged, self.controller.is_dark()))
        dialog_layout = QHBoxLayout(self)
        dialog_layout.setContentsMargins(0, 0, 0, 0)
        self._dialog_layout = dialog_layout
        self._content_stack = QStackedWidget(self)
        self._content_stack.setObjectName("SettingsContentStack")
        self._content_stack.setMinimumWidth(0)
        stack_layout = self._content_stack.layout()
        if isinstance(stack_layout, QStackedLayout):
            stack_layout.setStackingMode(QStackedLayout.StackingMode.StackAll)
        dialog_layout.addWidget(self._content_stack, 1)
        self.settings_shell = QWidget()
        self.settings_shell.setMaximumWidth(SETTINGS_SHELL_MAX_WIDTH)
        self.settings_shell.setMinimumWidth(0)
        self.settings_shell.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self._content_stack.addWidget(self.settings_shell)
        self._content_stack.setCurrentWidget(self.settings_shell)
        self._update_settings_shell_margins()
        outer = QGridLayout(self.settings_shell)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setHorizontalSpacing(0)
        outer.setVerticalSpacing(0)
        outer.setRowStretch(0, 0)
        outer.setRowStretch(1, 1)
        outer.setRowStretch(2, 0)
        outer.setColumnStretch(0, 0)
        outer.setColumnStretch(1, 1)

        self.sidebar_panel = QWidget(self.settings_shell)
        self.sidebar_panel.setObjectName("SettingsSidebarPanel")
        self.sidebar_panel.setFixedWidth(SETTINGS_SIDEBAR_WIDTH)
        sidebar_layout = QVBoxLayout(self.sidebar_panel)
        sidebar_layout.setContentsMargins(16, 18, 16, 16)
        sidebar_layout.setSpacing(8)
        self.sidebar_title = QLabel("Home Screen Dashboard")
        self.sidebar_title.setObjectName("GlobalTitle")
        self.sidebar_title.setWordWrap(True)
        self.sidebar_version = QLabel(
            "Version {}".format(_manifest_metadata().get("human_version", "1.8.7"))
        )
        self.sidebar_version.setObjectName("SidebarVersion")
        sidebar_layout.addWidget(self.sidebar_title)
        sidebar_layout.addWidget(self.sidebar_version)
        sidebar_layout.addSpacing(12)
        self.nav = SettingsSidebar(self.sidebar_panel)
        sidebar_layout.addWidget(self.nav, 1)
        outer.addWidget(self.sidebar_panel, 0, 0, 3, 1)

        self.header_shell = QWidget()
        self.header_shell.setObjectName("SettingsHeader")
        header_shell_layout = QVBoxLayout(self.header_shell)
        header_shell_layout.setContentsMargins(0, 0, 0, 0)
        header_shell_layout.setSpacing(0)
        self.header_stack = QStackedWidget(self.header_shell)
        self.header_stack.setMinimumHeight(SETTINGS_HEADER_HEIGHT)
        self.header_stack.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Minimum,
        )
        header_shell_layout.addWidget(self.header_stack)
        self.compact_nav = QTabBar(self.header_shell)
        self.compact_nav.setObjectName("CompactSettingsNav")
        self.compact_nav.setAccessibleName("Settings sections")
        self.compact_nav.setDrawBase(False)
        self.compact_nav.setDocumentMode(True)
        self.compact_nav.setExpanding(True)
        self.compact_nav.setUsesScrollButtons(True)
        self.compact_nav.setElideMode(Qt.TextElideMode.ElideNone)
        self.compact_nav.hide()
        header_shell_layout.addWidget(self.compact_nav)
        outer.addWidget(self.header_shell, 0, 1)

        self.body_shell = QWidget()
        body_layout = QVBoxLayout(self.body_shell)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)
        self.stack = QStackedWidget()
        self.stack.setMinimumWidth(0)
        body_layout.addWidget(self.stack, 1)
        outer.addWidget(self.body_shell, 1, 1)

        self._build_dashboard_page()
        self._build_events_page()
        self._build_bible_page()
        self._build_about_page()
        self.nav.currentRowChanged.connect(self._nav_changed)
        self.compact_nav.currentChanged.connect(self._compact_nav_changed)

        self.footer = SettingsFooter()
        self.footer.set_details_callback(self._show_save_error_details)
        self.revert_button = QPushButton("Discard changes")
        self.revert_button.setObjectName("LinkButton")
        self.revert_button.clicked.connect(self._request_revert_changes)
        self.revert_button.hide()
        self.footer.add_left_widget(self.revert_button)
        self.save_error = self.footer.error_label
        self.status_label = self.footer.status_label
        self.buttons = self.footer.buttons
        self.save_button = self.buttons.button(QDialogButtonBox.StandardButton.Save)
        if self.save_button is not None:
            self.save_button.setText("Save changes")
            self.save_button.setObjectName("PrimaryButton")
            self.save_button.setMinimumWidth(124)
            self.save_button.setEnabled(False)
            _set_accessibility(
                self.save_button,
                "Save changes",
                "Apply all changes without closing Settings.",
            )
        self.close_button = self.buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if self.close_button is not None:
            self.close_button.setText("Close")
            _set_accessibility(self.close_button, "Close", "Close Settings, confirming before discarding unsaved changes.")
        self.buttons.accepted.connect(self._save)
        self.buttons.rejected.connect(self.request_close)

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
        self.saved_status_timer = QTimer(self)
        self.saved_status_timer.setSingleShot(True)
        self.saved_status_timer.setInterval(2000)
        self.saved_status_timer.timeout.connect(self._clear_saved_status)
        self.discarded_status_timer = QTimer(self)
        self.discarded_status_timer.setSingleShot(True)
        self.discarded_status_timer.setInterval(2000)
        self.discarded_status_timer.timeout.connect(self._clear_discarded_status)
        self.footer_shell = SettingsFooterShell()
        footer_shell_layout = QVBoxLayout(self.footer_shell)
        footer_shell_layout.setContentsMargins(0, 0, 0, 0)
        footer_shell_layout.setSpacing(4)
        footer_shell_layout.addWidget(self.undo_toast)
        footer_shell_layout.addWidget(self.footer)
        outer.addWidget(self.footer_shell, 2, 1)
        self._footer_clearance_timer = QTimer(self)
        self._footer_clearance_timer.setSingleShot(True)
        self._footer_clearance_timer.timeout.connect(
            self._apply_settings_footer_clearance
        )
        self.footer_shell.set_geometry_callback(
            self._schedule_settings_footer_clearance
        )

        self.save_shortcut = QAction("Save changes", self)
        self.save_shortcut.setShortcut(QKeySequence.StandardKey.Save)
        self.save_shortcut.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.save_shortcut.triggered.connect(self._save)
        self.addAction(self.save_shortcut)
        self.close_shortcut = QAction("Close Settings", self)
        self.close_shortcut.setShortcut(QKeySequence.StandardKey.Close)
        self.close_shortcut.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.close_shortcut.triggered.connect(self.request_close)
        self.addAction(self.close_shortcut)
        self.escape_shortcut = QAction("Close Settings", self)
        self.escape_shortcut.setShortcut(QKeySequence("Esc"))
        self.escape_shortcut.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.escape_shortcut.triggered.connect(self.request_close)
        self.addAction(self.escape_shortcut)

        self._connect_change_signals()
        self._refresh_event_lists()
        self._refresh_quote_list()
        self._building = False
        self.open_page(initial_page, selected_event_date, selected_event_id)
        self._sync_draft()
        _apply_control_targets(self)
        _apply_role_fonts(self)
        self._apply_canonical_layout()
        self._apply_settings_footer_clearance()
        if not self._requested_dashboard_anchor:
            self._settle_initial_scroll_top()
        _install_palette_watcher(
            self,
            self._current_stylesheet,
            self._host_palette_changed,
        )

    @staticmethod
    def _active_screen(parent: QWidget) -> Any:
        """Resolve the logical active screen without realizing a new window."""

        application = QApplication.instance()
        screen = None
        try:
            handle = parent.windowHandle()
            screen = handle.screen() if handle is not None else None
        except Exception:
            screen = None
        if screen is None and application is not None:
            try:
                screen = application.screenAt(parent.frameGeometry().center())
            except Exception:
                screen = None
        if screen is None and application is not None:
            screen = application.primaryScreen()
        return screen

    @staticmethod
    def _rect_tuple(rect: Any) -> Optional[tuple[int, int, int, int]]:
        if isinstance(rect, QRect):
            return rect.x(), rect.y(), rect.width(), rect.height()
        if isinstance(rect, (list, tuple)) and len(rect) >= 4:
            try:
                return tuple(int(rect[index]) for index in range(4))  # type: ignore[return-value]
            except (TypeError, ValueError):
                return None
        return None

    @staticmethod
    def _screen_name(screen: Any) -> str:
        try:
            return str(screen.name() or "")
        except Exception:
            return ""

    @classmethod
    def _connected_screens(
        cls,
    ) -> List[tuple[Any, str, tuple[int, int, int, int]]]:
        application = QApplication.instance()
        records: List[tuple[Any, str, tuple[int, int, int, int]]] = []
        if application is None:
            return records
        try:
            screens = application.screens()
        except Exception:
            screens = []
        for screen in screens:
            try:
                available = cls._rect_tuple(screen.availableGeometry())
            except Exception:
                available = None
            if available is not None:
                records.append((screen, cls._screen_name(screen), available))
        return records

    def _apply_initial_window_geometry(self, parent: QWidget) -> None:
        active_screen = self._active_screen(parent)
        available_rect = active_screen.availableGeometry() if active_screen is not None else QRect(
            0, 0, SETTINGS_DEFAULT_SIZE[0], SETTINGS_DEFAULT_SIZE[1]
        )
        active_available = self._rect_tuple(available_rect) or (
            0, 0, SETTINGS_DEFAULT_SIZE[0], SETTINGS_DEFAULT_SIZE[1]
        )
        connected = self._connected_screens()
        connected_geometries = [record[2] for record in connected] or [active_available]
        parent_rect = self._rect_tuple(parent.frameGeometry())
        saved = self._rect_tuple(self._geometry_settings.value(SETTINGS_GEOMETRY_KEY))
        saved_screen_name = str(self._geometry_settings.value(SETTINGS_GEOMETRY_SCREEN_KEY, "") or "")
        source_version = SETTINGS_GEOMETRY_VERSION
        if saved is None:
            saved = self._rect_tuple(
                self._geometry_settings.value(SETTINGS_PREVIOUS_GEOMETRY_KEY)
            )
            saved_screen_name = str(
                self._geometry_settings.value(SETTINGS_PREVIOUS_GEOMETRY_SCREEN_KEY, "") or ""
            )
            source_version = SETTINGS_PREVIOUS_GEOMETRY_VERSION
        saved_record = next(
            (record for record in connected if record[1] == saved_screen_name),
            None,
        )
        migrated = migrate_saved_window_geometry(
            saved,
            connected_geometries,
            source_version=source_version,
            saved_screen_exists=saved_record is not None,
        )
        saved_valid = migrated is not None
        target_available = saved_record[2] if saved_valid and saved_record is not None else active_available
        self._screen_compact_fallback = settings_screen_uses_compact_fallback(
            (target_available[2], target_available[3])
        )
        geometry = clamp_window_geometry(
            migrated if saved_valid else None,
            target_available,
            parent=parent_rect,
        )
        self.setMinimumSize(
            min(SETTINGS_MINIMUM_SIZE[0], geometry[2]),
            min(SETTINGS_MINIMUM_SIZE[1], geometry[3]),
        )
        self.setGeometry(QRect(*geometry))

    def _persist_window_geometry(self) -> None:
        if self.isMaximized() or self.isFullScreen():
            return
        rect = self.geometry()
        logical = self._rect_tuple(rect)
        connected = self._connected_screens()
        if logical is None or logical[2] < SETTINGS_MINIMUM_SIZE[0] or logical[3] < SETTINGS_MINIMUM_SIZE[1]:
            return
        if not saved_window_geometry_is_valid(
            logical,
            [record[2] for record in connected],
        ):
            return
        application = QApplication.instance()
        screen = None
        if application is not None:
            try:
                screen = application.screenAt(rect.center())
            except Exception:
                screen = None
        if screen is None:
            screen = self._active_screen(self.parentWidget())
        screen_name = self._screen_name(screen)
        if not screen_name:
            return
        self._geometry_settings.setValue(SETTINGS_GEOMETRY_KEY, QRect(rect))
        self._geometry_settings.setValue(SETTINGS_GEOMETRY_SCREEN_KEY, screen_name)
        try:
            available = screen.availableGeometry() if screen is not None else QRect()
            self._geometry_settings.setValue(SETTINGS_GEOMETRY_AVAILABLE_KEY, QRect(available))
            self._geometry_settings.setValue(
                SETTINGS_GEOMETRY_DPR_KEY,
                float(screen.devicePixelRatio()) if screen is not None else 1.0,
            )
        except Exception:
            pass
        self._geometry_settings.sync()

    def showEvent(self, event: Any) -> None:
        super().showEvent(event)
        if not self._post_show_clamp_done:
            self._post_show_clamp_done = True
            QTimer.singleShot(0, self._correct_decorated_frame_if_needed)

    def _correct_decorated_frame_if_needed(self) -> None:
        """Correct only decoration-induced off-screen placement after show."""

        frame = self.frameGeometry()
        screen = self.screen() or self._active_screen(self.parentWidget())
        if screen is None:
            return
        available = screen.availableGeometry()
        if available.contains(frame):
            return
        dx = 0
        dy = 0
        if frame.left() < available.left():
            dx = available.left() - frame.left()
        elif frame.right() > available.right():
            dx = available.right() - frame.right()
        if frame.top() < available.top():
            dy = available.top() - frame.top()
        elif frame.bottom() > available.bottom():
            dy = available.bottom() - frame.bottom()
        if dx or dy:
            self.move(self.pos() + QPoint(dx, dy))

    def resizeEvent(self, event: Any) -> None:
        super().resizeEvent(event)
        if hasattr(self, "_dialog_layout"):
            self._update_settings_shell_margins()
        if hasattr(self, "appearance_grid"):
            QTimer.singleShot(0, self._reflow_compact_grids)
        if hasattr(self, "body_shell"):
            QTimer.singleShot(0, self._apply_responsive_layout)

    def _settle_initial_scroll_top(self) -> None:
        scroll = self.stack.currentWidget() if hasattr(self, "stack") else None
        if isinstance(scroll, QScrollArea):
            scroll.verticalScrollBar().setValue(0)

    def _update_settings_shell_margins(self) -> None:
        """Center the bounded shell without stretching forms across a monitor."""

        inset = max(0, (self.width() - SETTINGS_SHELL_MAX_WIDTH) // 2)
        self._dialog_layout.setContentsMargins(inset, 0, inset, 0)

    def changeEvent(self, event: Any) -> None:
        if _is_palette_change(event):
            _queue_palette_style(
                self,
                self._current_stylesheet,
                self._host_palette_changed,
            )
        if event.type() in {
            getattr(QEvent.Type, "FontChange", None),
            getattr(QEvent.Type, "ApplicationFontChange", None),
        }:
            _apply_role_fonts(self)
            _apply_control_targets(self)
            QTimer.singleShot(0, self._apply_canonical_layout)
        super().changeEvent(event)

    def _current_stylesheet(self) -> str:
        return _settings_style(self.draft.values, self.controller.is_dark())

    def _add_page(self, section_id: str, page: QWidget) -> None:
        name = SECTION_LABELS[section_id]
        item = QListWidgetItem(name)
        item.setData(Qt.ItemDataRole.UserRole, section_id)
        item.setData(Qt.ItemDataRole.AccessibleTextRole, name)
        self.nav.addItem(item)
        self.compact_nav.addTab(name)
        self.nav.refresh_item_sizes()
        self.nav_rows[section_id] = self.nav.count() - 1
        self.page_indices[section_id] = self.stack.count()
        page.setAccessibleName("{} settings".format(name))
        header = getattr(page, "_hdo_page_header", None)
        if isinstance(header, QWidget):
            header.setAccessibleName("{} settings header".format(name))
            self.header_stack.addWidget(header)
        scroll = QScrollArea()
        scroll.setObjectName("SettingsScrollBody")
        scroll.setAccessibleName("{} settings content".format(name))
        scroll.setWidgetResizable(True)
        scroll.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
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
        if self._syncing_navigation:
            return
        item = self.nav.item(row)
        section_id = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        if not isinstance(section_id, str) or section_id not in self.page_indices:
            return
        self._show_section(section_id, source="nav")

    def _compact_nav_changed(self, row: int) -> None:
        if self._syncing_navigation or row < 0:
            return
        item = self.nav.item(row)
        section_id = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        if isinstance(section_id, str) and section_id in self.page_indices:
            self._show_section(section_id, source="compact-nav")

    def _show_section(self, section_id: str, source: str = "") -> None:
        self.current_section = section_id
        page_index = self.page_indices[section_id]
        self.stack.setCurrentIndex(page_index)
        self.header_stack.setCurrentIndex(page_index)
        row = self.nav_rows[section_id]
        self._syncing_navigation = True
        try:
            if self.nav.currentRow() != row:
                self.nav.setCurrentRow(row)
            if self.compact_nav.currentIndex() != row:
                self.compact_nav.setCurrentIndex(row)
        finally:
            self._syncing_navigation = False
        self._fit_header_height()
        if source in {"nav", "compact-nav"}:
            self._settle_initial_scroll_top()

    def _schedule_dashboard_anchor(self, anchor: str) -> None:
        """Resolve a legacy anchor after the canonical page layout settles."""

        self._requested_dashboard_anchor = anchor
        if anchor == "calendar" and hasattr(self, "calendar_display_disclosure"):
            self.calendar_display_disclosure.setChecked(True)
        scroll = self.stack.currentWidget() if hasattr(self, "stack") else None
        if isinstance(scroll, QScrollArea):
            scroll.verticalScrollBar().setValue(0)
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
        # Align the requested card cleanly with the viewport. Leaving a large
        # top offset exposes the bottom border of the preceding card and looks
        # like clipped content on a legacy Calendar route.
        value = max(0, target_y - 2)
        scroll.verticalScrollBar().setValue(value)
        target.setProperty("hdoScrollMarginTop", 16)

    def _apply_canonical_layout(self) -> None:
        """Apply size hints without changing the single Settings composition."""

        self._fit_header_height()
        self.sidebar_panel.setFixedWidth(SETTINGS_SIDEBAR_WIDTH)
        for index in range(self.stack.count()):
            scroll = self.stack.widget(index)
            if not isinstance(scroll, QScrollArea):
                continue
            page = scroll.widget()
            if page is not None:
                page.setMaximumWidth(
                    SETTINGS_ABOUT_MAX_WIDTH
                    if page is getattr(self, "about_page", None)
                    else SETTINGS_PAGE_MAX_WIDTH
                )
                page.setMinimumWidth(0)
            scroll.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        for combo in self.findChildren(QComboBox):
            if combo is getattr(self, "event_sort", None):
                combo.setMaximumWidth(160)
            elif isinstance(combo, QFontComboBox):
                combo.setMaximumWidth(320)
            else:
                combo.setMaximumWidth(420)
        for spin in self.findChildren(QSpinBox):
            spin.setMaximumWidth(120)
        for form in self.findChildren(QFormLayout):
            form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        if hasattr(self, "appearance_grid"):
            self._reflow_compact_grids()
        if hasattr(self, "active_events"):
            self._fit_event_tree(self.active_events)
            self._fit_event_tree(self.archived_events)
        if hasattr(self, "quote_list"):
            self._fit_quote_list()
        if hasattr(self, "deck_tree"):
            self._fit_deck_tree()
        self._apply_responsive_layout()
        if self.current_section == "dashboard" and self._requested_dashboard_anchor:
            anchor = self._requested_dashboard_anchor
            QTimer.singleShot(0, lambda: self._settle_dashboard_anchor(anchor, -1, 0))

    def _fit_header_height(self) -> None:
        """Keep the canonical header at 72 px and grow only for larger fonts."""

        if not hasattr(self, "header_stack"):
            return
        current = self.header_stack.currentWidget()
        natural = current.sizeHint().height() if current is not None else 0
        self.header_stack.setFixedHeight(max(SETTINGS_HEADER_HEIGHT, natural))

    def _apply_settings_footer_clearance(self) -> int:
        """Keep normal page padding; the footer owns a separate grid row."""

        clearance = 36
        for scroll, base in self._settings_scroll_base_margins.items():
            page = scroll.widget()
            page_layout = page.layout() if page is not None else None
            if page_layout is not None:
                page_layout.setContentsMargins(base[0], base[1], base[2], clearance)
        return clearance

    def _schedule_settings_footer_clearance(self) -> None:
        if hasattr(self, "_footer_clearance_timer"):
            self._footer_clearance_timer.start(0)

    def _apply_responsive_layout(self) -> None:
        if not hasattr(self, "body_shell"):
            return
        shell_width = max(0, self.settings_shell.width())
        compact = self._screen_compact_fallback or shell_width < SETTINGS_COMPACT_BODY_WIDTH
        self._compact_layout = compact
        self.sidebar_panel.setVisible(not compact)
        self.compact_nav.setVisible(compact)
        self.footer.set_compact(compact)
        page_padding = 20
        for scroll, base in self._settings_scroll_base_margins.items():
            page = scroll.widget()
            page_layout = page.layout() if page is not None else None
            if page_layout is not None:
                page_layout.setContentsMargins(
                    page_padding,
                    base[1],
                    page_padding,
                    36,
                )
        if hasattr(self, "event_toolbar_grid"):
            self._reflow_event_toolbar()
        if hasattr(self, "quote_toolbar_grid"):
            self._reflow_quote_toolbar()
        if hasattr(self, "bible_section_row"):
            self.bible_section_row.set_compact(compact)
        if hasattr(self, "quote_list"):
            self._fit_quote_list()
        if hasattr(self, "active_events"):
            self._fit_event_tree(self.active_events)
            self._fit_event_tree(self.archived_events)
        self._apply_settings_footer_clearance()
        self._schedule_settings_footer_clearance()

    def _create_appearance_card(self) -> SettingsCard:
        card = SettingsCard(
            "Appearance",
            "",
            "Reset",
        )
        self.appearance_card = card
        if card.reset_button is not None:
            card.reset_button.clicked.connect(
                lambda: self._reset_card("appearance", "Appearance")
            )
        appearance = self.staged["appearance"]
        self.preset = _combo([(name, name) for name in PRESETS], appearance["preset"])
        _set_accessibility(
            self.preset,
            "Dashboard theme",
            "Choose one of four fully audited dashboard palettes.",
        )
        self.heatmap_preset = QComboBox()
        self.heatmap_preset.setAccessibleName("Heatmap palette")
        self.heatmap_preset.setAccessibleDescription(
            "Choose the calendar heatmap colors for the selected dashboard theme."
        )
        self._refresh_heatmap_preset_options()
        self.heatmap_preset.currentIndexChanged.connect(
            self._heatmap_preset_changed
        )
        self.mode = SegmentedControl(
            [("Follow Anki", "auto"), ("Light", "light"), ("Dark", "dark")],
            appearance["mode"],
            "Dashboard color mode",
        )
        self.mode.set_option_width(92)
        self.mode.setMinimumWidth(0)
        _set_accessibility(
            self.mode,
            "Dashboard color mode",
            "Follow Anki automatically, or keep the dashboard in light or dark mode.",
        )
        self.preset.currentIndexChanged.connect(self._dashboard_theme_changed)
        opacity_row, self.opacity_slider, self.opacity = _paired_slider(
            94, 100, appearance["opacity"], " %"
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
        scale_markers = QWidget()
        scale_markers_layout = QHBoxLayout(scale_markers)
        scale_markers_layout.setContentsMargins(0, 0, 76, 0)
        scale_markers_layout.setSpacing(0)
        for index, label_text in enumerate(("90%", "100% default", "150%")):
            marker = QLabel(label_text)
            marker.setObjectName("FieldHelp")
            marker.setAlignment(
                Qt.AlignmentFlag.AlignLeft
                if index == 0
                else Qt.AlignmentFlag.AlignCenter
                if index == 1
                else Qt.AlignmentFlag.AlignRight
            )
            scale_markers_layout.addWidget(marker, 1)
        text_scale_control = QWidget()
        text_scale_control_layout = QVBoxLayout(text_scale_control)
        text_scale_control_layout.setContentsMargins(0, 0, 0, 0)
        text_scale_control_layout.setSpacing(2)
        text_scale_control_layout.addWidget(text_scale_row)
        text_scale_control_layout.addWidget(scale_markers)
        self.dashboard_theme_field = _stacked_field(
            "Dashboard theme",
            "",
            self.preset,
        )
        self.heatmap_palette_field = _stacked_field(
            "Heatmap palette",
            "Colors used for calendar intensity within the selected theme.",
            self.heatmap_preset,
        )
        self.dashboard_mode_field = _stacked_field(
            "Dashboard color mode",
            "",
            self.mode,
        )
        self.dashboard_scale_field = _stacked_field(
            "Dashboard content scale",
            "",
            text_scale_control,
        )
        self.appearance_fields = [
            self.dashboard_theme_field,
            self.heatmap_palette_field,
            self.dashboard_mode_field,
            self.dashboard_scale_field,
        ]
        self.opacity_field = _stacked_field(
            "Card opacity",
            "Affects dashboard cards only.",
            opacity_row,
        )
        self.appearance_grid = QGridLayout()
        self.appearance_grid.setContentsMargins(0, 0, 0, 0)
        self.appearance_grid.setHorizontalSpacing(14)
        self.appearance_grid.setVerticalSpacing(10)
        self.appearance_advanced = QWidget()
        advanced_form = QFormLayout(self.appearance_advanced)
        advanced_form.setContentsMargins(0, 0, 0, 0)
        advanced_form.setVerticalSpacing(10)
        blur_row, self.blur_slider, self.blur = _paired_slider(
            0, 16, int(appearance.get("blur", 12)), " px"
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
        self.blur_field_label = _field_label(
            "Card blur",
            "Affects Sapphire Glass cards only.",
        )
        self.blur_field = blur_row
        advanced_form.addRow(self.opacity_field)
        advanced_form.addRow(self.blur_field_label, self.blur_field)
        advanced_form.addRow(
            _field_label("Panel placement", "Anki’s deck list remains above injected add-on panels."),
            self.home_screen_position,
        )
        self.appearance_advanced_button = DisclosureHeader(
            "Advanced appearance",
            self.appearance_advanced,
            "Show opacity, blur, and add-on panel placement controls.",
        )
        self.appearance_controls = QWidget()
        appearance_controls_layout = QVBoxLayout(self.appearance_controls)
        appearance_controls_layout.setContentsMargins(0, 0, 0, 0)
        appearance_controls_layout.setSpacing(10)
        appearance_controls_layout.addLayout(self.appearance_grid)
        appearance_scope_help = QLabel(
            "These options affect the dashboard, not this settings window."
        )
        appearance_scope_help.setObjectName("FieldHelp")
        appearance_scope_help.setWordWrap(True)
        appearance_controls_layout.addWidget(appearance_scope_help)
        appearance_controls_layout.addWidget(self.appearance_advanced_button)
        appearance_controls_layout.addWidget(self.appearance_advanced)
        card.add_widget(self.appearance_controls)
        self._reflow_compact_grids()
        self._update_glass_controls()
        return card

    def _build_dashboard_page(self) -> None:
        page, layout, form = _page(
            "Dashboard",
            "Customize appearance, sections, metrics, and calendar.",
        )
        # The page root never owns fields; each group has a quiet, resettable
        # card. Remove the empty compatibility form inserted by ``_page``.
        layout.removeItem(form)
        self.dashboard_anchors: Dict[str, QWidget] = {}
        appearance_card = self._create_appearance_card()
        appearance_card.setProperty("hdoAnchor", "appearance")
        self.dashboard_anchors["appearance"] = appearance_card
        layout.addWidget(appearance_card)

        sections_card = SettingsCard(
            "Dashboard sections",
            "",
            "Reset",
        )
        if sections_card.reset_button is not None:
            sections_card.reset_button.clicked.connect(
                lambda: self._reset_card("dashboard_sections", "Dashboard sections")
            )
        self.dashboard_sections_card = sections_card
        sections_card.setProperty("hdoAnchor", "content")
        self.dashboard_anchors["content"] = sections_card
        self.dashboard_anchors["dashboard_sections"] = sections_card
        sections_layout = QVBoxLayout()
        sections_layout.setSpacing(8)
        self.visibility: Dict[str, QPushButton] = {}
        visibility = self.staged["visibility"]

        def add_visibility(key: str, title: str, description: str) -> None:
            row, box = _switch_row(title, description, visibility[key])
            self.visibility[key] = box
            sections_layout.addWidget(row)

        add_visibility(
            "heatmap",
            "Study calendar",
            "History, due load, and events.",
        )
        add_visibility(
            "remaining",
            "Today’s progress",
            "Cards remaining and completion.",
        )
        add_visibility(
            "today",
            "Today’s session",
            "Cards studied, time, pace, and ETA.",
        )
        add_visibility(
            "heatmap_metrics",
            "Recent and lifetime metrics",
            "7-day and lifetime totals.",
        )
        bible_row = ConfigurableSwitchRow(
            "Bible verse",
            "Optional verse card.",
            visibility["bible"],
            "Configure verse",
        )
        bible_switch = bible_row.switch
        self.visibility["bible"] = bible_switch
        self.bible_section_row = bible_row
        self.configure_bible = bible_row.action
        self.configure_bible.clicked.connect(lambda: self._show_section("bible_verse"))
        sections_layout.addWidget(bible_row)
        sections_card.add_layout(sections_layout)
        layout.addWidget(sections_card)

        study_card = SettingsCard("Study metrics", "", "Reset")
        self.study_metrics_card = study_card
        if study_card.reset_button is not None:
            study_card.reset_button.clicked.connect(
                lambda: self._reset_card("study_metrics", "Study metrics")
            )

        self.pace_unit = _combo(
            [("Seconds per card", "seconds_per_card"), ("Cards per minute", "cards_per_minute")],
            self.staged["study"]["pace_unit"],
        )
        _set_accessibility(
            self.pace_unit,
            "Pace format",
            "Changes how pace is displayed.",
        )
        self.retention_target = SuffixNumberField(
            50,
            100,
            int(self.staged["study"].get("retention_target", 80)),
            "%",
        )
        _set_accessibility(
            self.retention_target,
            "Retention goal",
            "Used to color retention status.",
        )
        new_row, self.include_rescheduled = _switch_row(
            "Count manually rescheduled cards as new",
            "Counts the first qualifying answer after a manual reschedule.",
            self.staged["new_cards"]["include_rescheduled"],
        )
        self.study_metric_fields = [
            _stacked_field(
                "Pace format",
                "Changes how pace is displayed.",
                self.pace_unit,
            ),
            _stacked_field(
                "Retention goal",
                "Used to color retention status.",
                self.retention_target,
            ),
        ]
        self.study_metrics_grid = QGridLayout()
        self.study_metrics_grid.setContentsMargins(0, 0, 0, 0)
        self.study_metrics_grid.setHorizontalSpacing(18)
        self.study_metrics_grid.setVerticalSpacing(12)
        self.study_metrics_grid.addWidget(self.study_metric_fields[0], 0, 0)
        self.study_metrics_grid.addWidget(self.study_metric_fields[1], 0, 1)
        self.study_metrics_grid.addWidget(new_row, 1, 0, 1, 2)
        self.study_metrics_grid.setColumnStretch(0, 1)
        self.study_metrics_grid.setColumnStretch(1, 1)
        study_card.add_layout(self.study_metrics_grid)
        layout.addWidget(study_card)

        calendar_cards = self._create_calendar_cards()
        calendar_cards[0].setProperty("hdoAnchor", "calendar")
        self.dashboard_anchors["calendar"] = calendar_cards[0]
        for calendar_card in calendar_cards:
            layout.addWidget(calendar_card)
        layout.addStretch()
        self._add_page("dashboard", page)

    def _create_calendar_cards(self) -> tuple[SettingsCard, SettingsCard]:
        display_card = SettingsCard("Calendar view", "", "Reset")
        display_card.setObjectName("SettingsSubsection")
        self.calendar_display_card = display_card
        if display_card.reset_button is not None:
            display_card.reset_button.clicked.connect(
                lambda: self._reset_card("calendar_display", "Calendar view")
            )
        form = display_card.add_form()
        heatmap = self.staged["heatmap"]

        self.collection_updates_notice = QLabel("Calendar totals update after saving.")
        self.collection_updates_notice.setObjectName("PageHelp")
        self.collection_updates_notice.setAccessibleName(
            "Calendar totals update after saving"
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
        self.calendar_view = SegmentedControl(
            [("Month", "month"), ("Year", "year")],
            heatmap["calendar_view"],
            "Default calendar view",
        )
        self.calendar_view.set_option_width(86)
        self._week_start_touched = False
        self._legacy_week_start_value = str(heatmap["week_start"])
        self.week_start = SegmentedControl(
            [("Sunday", "6"), ("Monday", "0")],
            self._legacy_week_start_value,
            "First day of week",
        )
        self.week_start.set_option_width(86)
        self.week_start.connect_changed(self._week_start_changed)
        _set_accessibility(self.calendar_view, "Default calendar view", "Choose Month or Year view.")
        _set_accessibility(self.week_start, "First day of week", "Choose the weekday used to start calendar rows.")
        form.addRow(_field_label("Default view"), self.calendar_view)
        form.addRow(_field_label("Week starts on"), self.week_start)

        event_row, event_switch = _switch_row(
            "Show event markers",
            "Show event markers on the calendar.",
            self.staged["visibility"]["events"],
        )
        self.visibility["events"] = event_switch
        form.addRow(event_row)
        self.events_dependency = QLabel(
            "Requires Study calendar."
        )
        self.events_dependency.setObjectName("FieldHelp")
        self.events_dependency.setWordWrap(True)
        self.events_dependency.setBuddy(event_switch)
        form.addRow(self.events_dependency)

        range_card = SettingsCard("Calendar range", "", "Reset")
        range_card.setObjectName("SettingsSubsection")
        self.calendar_range_card = range_card
        if range_card.reset_button is not None:
            range_card.reset_button.clicked.connect(
                lambda: self._reset_card("calendar_range", "Calendar range")
            )
        range_card.add_widget(collection_info)
        form = range_card.add_form()

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
        self.forecast_days = SuffixNumberField(
            0,
            730,
            int(heatmap["forecast_days"]),
            "days",
        )
        _set_accessibility(
            self.history_range,
            "History range",
            "Choose how much past study history to show.",
        )
        _set_accessibility(self.forecast_days, "Future range", "Choose how far ahead to display due markers.")
        forecast_row, self.show_forecast = _switch_row(
            "Show future due cards",
            "Show upcoming due-card markers.",
            heatmap["show_due_forecast"],
        )
        form.addRow(
            _field_label("History range", "Choose how much past study history to show."),
            self.history_range,
        )
        form.addRow(forecast_row)
        self.forecast_range_label = _field_label(
            "Future range",
            "Choose how far ahead to display them.",
        )
        form.addRow(self.forecast_range_label, self.forecast_days)

        data_card = SettingsCard("Filters and deck exclusions", "", "Reset")
        data_card.setObjectName("SettingsSubsection")
        self.local_data_card = data_card
        if data_card.reset_button is not None:
            data_card.reset_button.clicked.connect(
                lambda: self._reset_card("local_data", "Local data")
            )
        form = data_card.add_form()
        semantics_copy = QLabel(
            "Study counts and due forecasts follow Anki’s configured rollover, not calendar midnight. Events use their civil-calendar date."
        )
        semantics_copy.setObjectName("FieldHelp")
        semantics_copy.setWordWrap(True)
        semantics = DisclosureHeader(
            "Date calculation",
            semantics_copy,
            "Show the date and rollover rules.",
        )
        form.addRow(semantics)
        form.addRow(semantics_copy)

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
        self.deck_tree.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.deck_tree.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
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
        self.deck_tree.itemExpanded.connect(lambda *_args: self._fit_deck_tree())
        self.deck_tree.itemCollapsed.connect(lambda *_args: self._fit_deck_tree())
        self._update_deck_exclusion_summary()
        advanced_form.addRow(
            _field_label("Excluded decks", "A checked parent excludes its descendants across dashboard study data; full deck paths are retained."),
            deck_wrap,
        )
        self.calendar_advanced_button = DisclosureHeader(
            "Deck exclusions and filters",
            self.calendar_advanced,
            "Show custom history rules and deck exclusions.",
        )
        data_card.add_widget(self.calendar_advanced_button)
        data_card.add_widget(self.calendar_advanced)
        self.show_forecast.toggled.connect(self._update_forecast_range_visibility)
        self.history_range.currentIndexChanged.connect(self._update_history_range_visibility)
        self._update_forecast_range_visibility()
        self._update_history_range_visibility()
        calendar_content = QWidget()
        calendar_content_layout = QVBoxLayout(calendar_content)
        calendar_content_layout.setContentsMargins(0, 0, 0, 0)
        calendar_content_layout.setSpacing(12)
        calendar_content_layout.addWidget(display_card)
        calendar_content_layout.addWidget(range_card)
        calendar_wrapper = SettingsCard()
        self.calendar_display_disclosure = DisclosureHeader(
            "Calendar display",
            calendar_content,
            "Show calendar view and range settings.",
        )
        calendar_wrapper.add_widget(self.calendar_display_disclosure)
        calendar_wrapper.add_widget(calendar_content)

        local_content = QWidget()
        local_layout = QVBoxLayout(local_content)
        local_layout.setContentsMargins(0, 0, 0, 0)
        local_layout.addWidget(data_card)
        local_wrapper = SettingsCard()
        self.local_data_disclosure = DisclosureHeader(
            "Local data",
            local_content,
            "Show date semantics, filters, and deck exclusions.",
        )
        local_wrapper.add_widget(self.local_data_disclosure)
        local_wrapper.add_widget(local_content)
        return calendar_wrapper, local_wrapper

    def _build_events_page(self) -> None:
        page, layout, form = _page(
            "Events",
            "Add, edit, and archive calendar events.",
        )
        layout.removeItem(form)
        self.event_add = QPushButton("Add event")
        self.event_add.setObjectName("PrimaryButton")
        self.event_add.setMinimumWidth(96)
        self.event_add.clicked.connect(self._add_event)
        _set_accessibility(self.event_add, "Add event", "Open the local event editor.")
        page._hdo_header_actions.addWidget(self.event_add)
        self.event_date_context = QLabel("")
        self.event_date_context.setTextFormat(Qt.TextFormat.PlainText)
        self.event_date_context.setObjectName("PageHelp")
        self.event_date_context.setAccessibleName("Selected calendar date")
        self.event_date_context.hide()
        self.event_surface = SettingsCard()
        self.event_surface.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Maximum,
        )
        self.event_surface.add_widget(self.event_date_context)
        self.event_tabs = SettingsTabPanel()
        _set_accessibility(self.event_tabs, "Active and archived events", "Switch between active and archived local events.")
        self.active_events = self._event_tree("Active calendar events")
        self.archived_events = self._event_tree("Archived calendar events")
        self.event_tabs.addTab(self.active_events, "Active (0)")
        self.event_tabs.addTab(self.archived_events, "Archived (0)")

        self.event_search = QLineEdit(); self.event_search.setPlaceholderText("Search events")
        _set_accessibility(self.event_search, "Search events", "Search by event name or date.")
        self.event_search_clear = _icon_button("clear", "Clear event search")
        self.event_search_clear.clicked.connect(self.event_search.clear)
        self.event_search_clear.hide()
        _set_accessibility(self.event_search_clear, "Clear event search")
        search_control = QWidget()
        search_control_layout = QHBoxLayout(search_control)
        search_control_layout.setContentsMargins(0, 0, 0, 0)
        search_control_layout.setSpacing(4)
        search_control_layout.addWidget(self.event_search, 1)
        search_control_layout.addWidget(self.event_search_clear)
        self.event_sort = _combo(
            [
                ("Soonest first", "ascending"),
                ("Latest first", "descending"),
                ("Name", "name"),
            ],
            self.staged["events"].get("sort", "ascending"),
        )
        self.event_sort.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.event_sort.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self.event_sort.setMaximumWidth(160)
        _set_accessibility(self.event_sort, "Event sort order", "Sort active and archived events by date or name.")
        self.event_toolbar_add = QPushButton("Add event")
        self.event_toolbar_add.setObjectName("PrimaryButton")
        self.event_toolbar_add.clicked.connect(self._add_event)
        _set_accessibility(
            self.event_toolbar_add,
            "Add event",
            "Open the local event editor.",
        )
        self.event_toolbar_fields = [
            _stacked_field("Search", "", search_control),
            _stacked_field("Sort by", "", self.event_sort),
            _stacked_field("Actions", "", self.event_toolbar_add),
        ]
        self.event_toolbar_wrap = QWidget()
        self.event_toolbar_grid = QGridLayout(self.event_toolbar_wrap)
        self.event_toolbar_grid.setContentsMargins(0, 0, 0, 0)
        self.event_toolbar_grid.setHorizontalSpacing(12)
        self.event_toolbar_grid.setVerticalSpacing(8)
        self._reflow_event_toolbar()
        self.event_surface.add_widget(self.event_toolbar_wrap)
        self.event_result_summary = QLabel("")
        self.event_result_summary.setObjectName("PageHelp")
        self.event_surface.add_widget(self.event_result_summary)
        self.event_tabs.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Maximum,
        )
        self.event_surface.add_widget(self.event_tabs, 1)
        self.event_empty_state = QWidget()
        self.event_empty_state.setObjectName("EmptyState")
        self.event_empty_state.setMinimumHeight(220)
        self.event_empty_state.setMaximumHeight(260)
        self.event_empty_state.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Minimum,
        )
        self.event_empty_state.setMaximumWidth(360)
        empty_layout = QVBoxLayout(self.event_empty_state)
        empty_layout.setContentsMargins(24, 20, 24, 20)
        empty_layout.setSpacing(8)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.event_empty_icon = QLabel("")
        self.event_empty_icon.setPixmap(_settings_vector_icon("calendar", 32).pixmap(32, 32))
        self.event_empty_icon.setFixedSize(40, 40)
        self.event_empty_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.event_empty_icon.setAccessibleName("Calendar events")
        self.event_empty_title = QLabel("No events yet")
        self.event_empty_title.setObjectName("EmptyStateTitle")
        self.event_empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.event_empty_copy = QLabel(
            "Add an event to show it on the calendar."
        )
        self.event_empty_copy.setObjectName("EmptyStateCopy")
        self.event_empty_copy.setWordWrap(True)
        self.event_empty_copy.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.event_empty_copy.setMaximumWidth(360)
        empty_layout.addWidget(self.event_empty_icon, 0, Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(self.event_empty_title, 0, Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(self.event_empty_copy, 0, Qt.AlignmentFlag.AlignCenter)
        self.event_empty_add = QPushButton("Add event")
        self.event_empty_add.setObjectName("PrimaryButton")
        self.event_empty_add.clicked.connect(self._add_event)
        empty_layout.addWidget(self.event_empty_add, 0, Qt.AlignmentFlag.AlignCenter)
        self.event_empty_clear = QPushButton("Clear search")
        self.event_empty_clear.setObjectName("LinkButton")
        self.event_empty_clear.clicked.connect(self.event_search.clear)
        self.event_empty_clear.hide()
        empty_layout.addWidget(self.event_empty_clear, 0, Qt.AlignmentFlag.AlignCenter)
        self.event_empty_state.hide()
        self.event_surface.add_widget(self.event_empty_state, 0)
        self.event_action_feedback = QLabel("")
        self.event_action_feedback.setTextFormat(Qt.TextFormat.PlainText)
        self.event_action_feedback.setObjectName("PageHelp")
        self.event_action_feedback.setAccessibleName("Event action confirmation")
        self.event_action_feedback.setProperty("hdoLiveRegion", "polite")
        self.event_action_feedback.setWordWrap(True)
        self.event_surface.add_widget(self.event_action_feedback)
        layout.addWidget(self.event_surface)
        self.event_search.textChanged.connect(self._refresh_event_lists)
        self.event_search.textChanged.connect(
            lambda value: self.event_search_clear.setVisible(bool(value.strip()))
        )
        self.event_sort.currentIndexChanged.connect(self._refresh_event_lists)
        self.event_tabs.tabBar().currentChanged.connect(self._update_event_actions)
        self._add_page("events", page)

    def _event_tree(self, accessible_name: str) -> QTreeWidget:
        tree = QTreeWidget()
        tree.setObjectName("ManagerTree")
        tree.setAccessibleName(accessible_name)
        tree.setHeaderLabels(["Event"])
        tree.setHeaderHidden(True)
        tree.setRootIsDecorated(False)
        # Qt can paint native alternate-base stripes through an otherwise empty
        # tree, especially when the staged dashboard theme differs from Anki's
        # current mode. A solid viewport keeps the empty state calm and avoids
        # implying phantom rows; real rows retain explicit separators above.
        tree.setAlternatingRowColors(False)
        tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        tree.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        tree.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        tree.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        _install_settings_row_delegate(tree)
        tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        # ManagerTree QSS adds a 1 px frame and 3 px padding on every edge.
        # Include that chrome so the 54 px row itself is never clipped.
        tree.setMinimumHeight(54 + 8)
        tree.setMaximumHeight((6 * 54) + 8)
        tree.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        return tree

    def _fit_event_tree(self, tree: QTreeWidget) -> None:
        visible_rows = min(6, max(1, tree.topLevelItemCount()))
        row_widget = (
            tree.itemWidget(tree.topLevelItem(0), 0)
            if tree.topLevelItemCount()
            else None
        )
        target = (visible_rows * _event_row_target_height(tree, row_widget)) + 8
        tree.setMinimumHeight(target)
        tree.setMaximumHeight(target)
        tree.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def _event_selection_changed(self) -> None:
        for tree in (self.active_events, self.archived_events):
            tree.viewport().update()

    def _event_row_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        tree = self.sender()
        if isinstance(tree, QTreeWidget):
            tree.setCurrentItem(item)
        self._edit_event()
        if isinstance(tree, QTreeWidget):
            tree.clearSelection()

    def _build_bible_page(self) -> None:
        page, layout, root_form = _page(
            "Bible verse",
            "Customize the verse card and choose how verses rotate.",
        )
        layout.removeItem(root_form)
        bible = self.staged["bible"]
        display_card = SettingsCard(
            "Verse appearance",
            "",
            "Reset",
        )
        self.bible_display_card = display_card
        if display_card.reset_button is not None:
            display_card.reset_button.clicked.connect(
                lambda: self._reset_card("bible_appearance", "Verse appearance")
            )
        self.font_family = QFontComboBox(); self.font_family.setCurrentFont(self.font_family.currentFont())
        self._unavailable_font_label = ""
        family_name = str(bible["font_family"]).split(",", 1)[0].strip().strip('"\'')
        self._select_saved_font_family(family_name)
        self.font_size = SuffixNumberField(
            8,
            96,
            int(str(bible["font_size"]).replace("px", "")),
            "px",
        )
        self.font_color_value = bible["font_color"]
        self.font_color = QLineEdit(self.font_color_value.upper())
        self.font_color.setMaxLength(7)
        self.font_color.setPlaceholderText(DEFAULT_CUSTOM_BIBLE_COLOR)
        self.font_color.textChanged.connect(self._font_color_text_changed)
        self.font_color.editingFinished.connect(self._font_color_edited)
        self.font_color_swatch = QPushButton("")
        self.font_color_swatch.setFixedSize(36, 36)
        self.font_color_swatch.clicked.connect(self._choose_font_color)
        self.font_color_swatch.setAccessibleName("Choose custom verse color")
        color_row = QWidget()
        color_layout = QHBoxLayout(color_row)
        color_layout.setContentsMargins(0, 0, 0, 0)
        color_layout.addWidget(self.font_color, 1)
        color_layout.addWidget(self.font_color_swatch)
        color_layout.addStretch()
        self.theme_color = SegmentedControl(
            [("Theme", "theme"), ("Custom", "custom")],
            "theme" if bible["theme_aware_color"] else "custom",
            "Verse text color source",
        )
        self.theme_color.set_option_width(104)
        self.rotation = SegmentedControl(
            [
                ("Daily", "daily"),
                ("On refresh", "every render"),
                ("Manual", "manual"),
            ],
            bible["rotation_mode"],
            "Verse rotation",
        )
        self.rotation.set_option_width(92)
        _set_accessibility(self.font_family, "Verse font family", "Choose the font used only by the verse card.")
        _set_accessibility(self.font_size, "Verse font size", "Choose a verse-card size from 8 to 96 pixels.")
        _set_accessibility(self.font_color, "Custom verse color hex value", "Enter a six-digit hexadecimal color when theme-aware text color is off.")
        _set_accessibility(self.font_color_swatch, "Choose custom verse color", "Open the color chooser when theme-aware text color is off.")
        _set_accessibility(
            self.rotation,
            "Verse rotation",
            "Choose daily, every dashboard refresh, or manual rotation. Selecting a library row does not rotate it.",
        )
        if not self._unavailable_font_label:
            self.font_family.setToolTip("Applies only to verse body and reference text.")
        self.font_size.setToolTip("The verse card remains responsive at larger values.")
        self.bible_display_fields = [
            _stacked_field("Font", "", self.font_family),
            _stacked_field("Size", "", self.font_size),
        ]
        self.bible_display_grid = QGridLayout()
        self.bible_display_grid.setContentsMargins(0, 0, 0, 0)
        self.bible_display_grid.setHorizontalSpacing(14)
        self.bible_display_grid.setVerticalSpacing(10)
        self.bible_controls = QWidget()
        bible_controls_layout = QVBoxLayout(self.bible_controls)
        bible_controls_layout.setContentsMargins(0, 0, 0, 0)
        bible_controls_layout.setSpacing(10)
        bible_controls_layout.addLayout(self.bible_display_grid)
        bible_controls_layout.addWidget(
            _stacked_field(
                "Text color",
                "",
                self.theme_color,
            )
        )
        self.custom_color_container = _stacked_field(
            "Custom color",
            "Enter #RRGGBB. Low contrast is warned about rather than changed.",
            color_row,
        )
        self.font_color_warning = QLabel("")
        self.font_color_warning.setObjectName("WarningText")
        self.font_color_warning.setWordWrap(True)
        self.font_color_warning.setAccessibleName("Custom verse color contrast")
        custom_layout = self.custom_color_container.layout()
        if custom_layout is not None:
            custom_layout.addWidget(self.font_color_warning)
        bible_controls_layout.addWidget(self.custom_color_container)
        display_card.add_widget(self.bible_controls)
        self._reflow_compact_grids()
        layout.addWidget(display_card)

        rotation_card = SettingsCard(
            "Rotation",
            "Choose when a new verse is selected.",
            "Reset",
        )
        self.bible_rotation_card = rotation_card
        if rotation_card.reset_button is not None:
            rotation_card.reset_button.clicked.connect(
                lambda: self._reset_card("bible_rotation", "Verse rotation")
            )
        rotation_card.add_widget(self.rotation)
        self.rotation_help = QLabel("")
        self.rotation_help.setObjectName("FieldHelp")
        self.rotation_help.setWordWrap(True)
        rotation_card.add_widget(self.rotation_help)
        self.rotation.connect_changed(self._update_rotation_help)
        self._update_rotation_help()
        layout.addWidget(rotation_card)
        self._update_color_swatch()

        library_card = SettingsCard(
            "Verse library",
            "Search, add, edit, and select verses.",
        )
        self.quote_search = QLineEdit(); self.quote_search.setPlaceholderText("Search verses")
        _set_accessibility(self.quote_search, "Search verse library", "Filter staged verses by their displayed text or reference.")
        self.quote_search_clear = _icon_button("clear", "Clear verse search")
        self.quote_search_clear.clicked.connect(self.quote_search.clear)
        self.quote_search_clear.hide()
        quote_search_control = QWidget()
        quote_search_control_layout = QHBoxLayout(quote_search_control)
        quote_search_control_layout.setContentsMargins(0, 0, 0, 0)
        quote_search_control_layout.setSpacing(4)
        quote_search_control_layout.addWidget(self.quote_search, 1)
        quote_search_control_layout.addWidget(self.quote_search_clear)
        self.quote_count = QLabel(); self.quote_count.setObjectName("PageHelp")
        self.quote_add = QPushButton("Add verse")
        self.quote_add.setObjectName("PrimaryButton")
        self.quote_add.clicked.connect(self._add_quote)
        _set_accessibility(self.quote_add, "Add verse", "Add a verse to the library.")
        self.quote_toolbar_wrap = QWidget()
        self.quote_toolbar_grid = QGridLayout(self.quote_toolbar_wrap)
        self.quote_toolbar_grid.setContentsMargins(0, 0, 0, 0)
        self.quote_toolbar_grid.setHorizontalSpacing(8)
        self.quote_toolbar_grid.setVerticalSpacing(8)
        self.quote_toolbar_fields = [quote_search_control, self.quote_add]
        self._reflow_quote_toolbar()
        library_card.add_widget(self.quote_toolbar_wrap)
        self.quote_model = VerseLibraryModel(self)
        self.quote_list = VerseLibraryView()
        self.quote_list.setModel(self.quote_model)
        self.quote_list.set_menu_callback(self._open_quote_menu_for_model)
        _set_accessibility(self.quote_list, "Verse library", "Choose a staged verse to read, edit, duplicate, delete, or select.")
        library_card.add_widget(self.quote_count)
        library_card.add_widget(self.quote_list, 1)
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
        self.quote_export_error = QPushButton("Copy error")
        self.quote_export_error.setObjectName("LinkButton")
        self.quote_export_error.setIcon(_settings_vector_icon("copy"))
        self.quote_export_error.clicked.connect(self._copy_export_error)
        self.quote_export_error.hide()
        self.quote_current_actions.add_widget(self.quote_export_error)
        library_card.add_widget(self.quote_current_actions)
        self.quote_actions = ContextualActionGroup()
        self.quote_edit = QPushButton("Edit")
        self.quote_duplicate = QPushButton("Duplicate")
        self.quote_delete = QPushButton("Delete")
        self.quote_delete.setObjectName("DangerButton")
        self.quote_import = QPushButton("Import")
        self.quote_export = QPushButton("Export")
        for button, handler, description in (
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
            "Version, support, privacy, and backups.",
        )
        self.about_page = page
        page.setMaximumWidth(SETTINGS_ABOUT_MAX_WIDTH)
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

        version_card = SettingsCard("Version and support")
        definition_list = QWidget()
        definition_list.setObjectName("AboutDefinitionList")
        version_form = QFormLayout(definition_list)
        version_form.setContentsMargins(0, 0, 0, 0)
        version_form.setVerticalSpacing(8)
        version_form.addRow("Version", QLabel(version))
        version_form.addRow("Compatibility", QLabel(compatibility))
        version_card.add_widget(definition_list)
        self.copy_diagnostics = QPushButton("Copy diagnostics")
        self.copy_diagnostics.setIcon(_settings_vector_icon("copy"))
        self.copy_diagnostics.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        diagnostics = "{} {} | {} | schema {}".format(
            product_name,
            version,
            compatibility,
            self.staged.get("schema_version", "Unknown"),
        )
        self.copy_diagnostics_timer = QTimer(self.copy_diagnostics)
        self.copy_diagnostics_timer.setSingleShot(True)
        self.copy_diagnostics_timer.setInterval(2000)
        self.copy_diagnostics_timer.timeout.connect(
            lambda: self.copy_diagnostics.setText("Copy diagnostics")
        )

        def copy_about_diagnostics() -> None:
            QApplication.clipboard().setText(diagnostics)
            self.copy_diagnostics.setText("Diagnostics copied")
            self.copy_diagnostics_timer.start()

        self.copy_diagnostics.clicked.connect(copy_about_diagnostics)
        support_actions = QWidget()
        support_actions_layout = QHBoxLayout(support_actions)
        support_actions_layout.setContentsMargins(0, 0, 0, 0)
        support_actions_layout.setSpacing(8)
        support_actions_layout.addWidget(self.copy_diagnostics)
        support_actions_layout.addWidget(ExternalLinkButton("Documentation", PROJECT_URL))
        support_actions_layout.addWidget(ExternalLinkButton("Report an issue", ISSUES_URL))
        support_actions_layout.addStretch()
        version_card.add_widget(support_actions)
        self.about_version_card = version_card
        layout.addWidget(version_card)

        privacy_card = SettingsCard("Privacy and legal")
        privacy_card.setMaximumWidth(880)
        privacy_callout = QLabel(
            "Dashboard data stays on this device and is not sent to external services."
        )
        privacy_callout.setObjectName("InfoBanner")
        privacy_callout.setWordWrap(True)
        privacy_card.add_widget(privacy_callout)
        def add_about_disclosure(title: str, copy: str) -> None:
            detail = rich_label(copy)
            button = DisclosureHeader(title, detail)
            privacy_card.add_widget(button)
            privacy_card.add_widget(detail)

        add_about_disclosure(
            "Local data",
            "Preferences, deck exclusions, local events, the verse library, and rotation state are stored in Anki’s add-on data on this device.",
        )
        add_about_disclosure(
            "License",
            "GNU Affero General Public License, version 3 or later (AGPL-3.0-or-later).",
        )
        add_about_disclosure(
            "Third-party notices",
            'Scripture quotations are taken from the Holy Bible, New Living Translation, copyright ©1996, 2004, 2015 by Tyndale House Foundation. Used by permission of Tyndale House Publishers. All rights reserved.<br><br><a href="{}">Read required third-party notices</a>'.format(
                html_module.escape(notices_url, quote=True)
            ),
        )
        layout.addWidget(privacy_card)

        recovery_card = SettingsCard("Backup and recovery")
        self.about_recovery_card = recovery_card
        recovery_card.setMaximumWidth(880)
        recovery = QLabel(
            "Export verse library edits before updating or reinstalling the add-on.\n\n"
            "For a complete backup, close Anki and copy the add-on data folder.\n\n"
            "Dashboard settings do not change cards or review history."
        )
        recovery.setWordWrap(True)
        recovery_card.add_widget(recovery)
        recovery_export = QPushButton("Export verse library edits")
        self.recovery_export = recovery_export
        recovery_export.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        recovery_export.clicked.connect(self._export_quotes)
        _set_accessibility(
            recovery_export,
            "Export verse library edits",
            "Export the current verse library as JSON.",
        )
        recovery_card.add_widget(recovery_export)
        self.export_feedback = QLabel("")
        self.export_feedback.setObjectName("PageHelp")
        self.export_feedback.setWordWrap(True)
        self.export_feedback.setProperty("hdoLiveRegion", "polite")
        self.export_copy_error = QPushButton("Copy error")
        self.export_copy_error.setObjectName("LinkButton")
        self.export_copy_error.setIcon(_settings_vector_icon("copy"))
        self.export_copy_error.hide()
        self.export_copy_error.clicked.connect(self._copy_export_error)
        recovery_card.add_widget(self.export_feedback)
        recovery_card.add_widget(self.export_copy_error)
        layout.addWidget(recovery_card)
        layout.addStretch()
        self._add_page("about_support", page)

    def _connect_change_signals(self) -> None:
        for combo in (
            self.home_screen_position,
            self.pace_unit,
            self.history_range,
        ):
            combo.currentIndexChanged.connect(self._settings_changed)
        for segmented in (
            self.mode,
            self.week_start,
            self.calendar_view,
            self.rotation,
            self.theme_color,
        ):
            segmented.connect_changed(self._settings_changed)
        for spin in (
            self.opacity,
            self.blur,
            self.text_scale,
        ):
            spin.valueChanged.connect(self._settings_changed)
        for field in (
            self.forecast_days,
            self.font_size,
            self.retention_target,
        ):
            field.connect_changed(self._settings_changed)
        checks = list(self.visibility.values()) + [
            self.include_rescheduled,
            self.exclude_reschedules,
            self.exclude_deleted,
            self.show_forecast,
        ]
        for check in checks:
            check.toggled.connect(self._settings_changed)
        self.ignore_before.dateChanged.connect(self._settings_changed)
        self.font_family.currentFontChanged.connect(self._font_family_changed)
        self.quote_search.textChanged.connect(self._quote_search_changed)
        self.quote_search.textChanged.connect(
            lambda value: self.quote_search_clear.setVisible(bool(value.strip()))
        )
        self.quote_list.selectionModel().currentChanged.connect(self._update_quote_detail)
        self.rotation.connect_changed(self._update_quote_actions)

    @staticmethod
    def _place_grid_widgets(
        grid: QGridLayout,
        widgets: List[QWidget],
        columns: int,
    ) -> None:
        while grid.count():
            grid.takeAt(0)
        host = grid.parentWidget()
        visible_widgets: List[QWidget] = []
        for widget in widgets:
            # A newly-created QWidget is hidden and parentless until a layout
            # adopts it. Filtering on isHidden() first left every initial field
            # parentless. A later setVisible(True) could therefore realize that
            # field as a temporary top-level native window, which moves macOS
            # out of Anki's full-screen Space. Mount new fields as children
            # before showing or filtering them. Already-parented fields retain
            # any intentional hidden state across subsequent reflows.
            if widget.parentWidget() is None:
                if host is None:
                    continue
                widget.setParent(host)
                widget.show()
            if not widget.isHidden():
                visible_widgets.append(widget)
        columns = max(1, columns)
        for index, widget in enumerate(visible_widgets):
            grid.addWidget(widget, index // columns, index % columns)
        for column in range(max(4, columns)):
            grid.setColumnStretch(column, 1 if column < columns else 0)
        grid.invalidate()

    def _reflow_compact_grids(self) -> None:
        large_text = self.fontMetrics().lineSpacing() >= 22
        if hasattr(self, "appearance_grid"):
            width = self.appearance_card.width() if hasattr(self, "appearance_card") else 0
            while self.appearance_grid.count():
                self.appearance_grid.takeAt(0)
            host = self.appearance_grid.parentWidget()
            for field in self.appearance_fields:
                if field.parentWidget() is None and host is not None:
                    field.setParent(host)
                    field.show()
            if large_text or width < 680:
                for row, field in enumerate(self.appearance_fields):
                    self.appearance_grid.addWidget(field, row, 0)
                self.appearance_grid.setColumnStretch(0, 1)
                self.appearance_grid.setColumnStretch(1, 0)
            else:
                self.appearance_grid.addWidget(self.dashboard_theme_field, 0, 0)
                self.appearance_grid.addWidget(self.heatmap_palette_field, 0, 1)
                self.appearance_grid.addWidget(self.dashboard_mode_field, 1, 0, 1, 2)
                self.appearance_grid.addWidget(self.dashboard_scale_field, 2, 0, 1, 2)
                self.appearance_grid.setColumnStretch(0, 1)
                self.appearance_grid.setColumnStretch(1, 1)
            self.appearance_grid.invalidate()
        if hasattr(self, "bible_display_grid"):
            width = self.bible_display_card.width()
            columns = 1 if large_text or width < 520 else 2
            self._place_grid_widgets(self.bible_display_grid, self.bible_display_fields, columns)

    def _reflow_event_toolbar(self) -> None:
        if not hasattr(self, "event_toolbar_grid"):
            return
        for widget in self.event_toolbar_fields:
            self.event_toolbar_grid.removeWidget(widget)
        large_text = self.fontMetrics().lineSpacing() >= 22
        width = self.event_surface.width() if hasattr(self, "event_surface") else 0
        search, sort, add = self.event_toolbar_fields
        if large_text or width < 440:
            self.event_toolbar_grid.addWidget(search, 0, 0)
            self.event_toolbar_grid.addWidget(sort, 1, 0)
            self.event_toolbar_grid.addWidget(add, 2, 0)
            self.event_toolbar_grid.setColumnStretch(0, 1)
            self.event_toolbar_grid.setColumnStretch(1, 0)
            self.event_toolbar_grid.setColumnStretch(2, 0)
        elif width < 680:
            self.event_toolbar_grid.addWidget(search, 0, 0, 1, 2)
            self.event_toolbar_grid.addWidget(sort, 1, 0)
            self.event_toolbar_grid.addWidget(
                add, 1, 1, Qt.AlignmentFlag.AlignRight
            )
            self.event_toolbar_grid.setColumnStretch(0, 1)
            self.event_toolbar_grid.setColumnStretch(1, 0)
            self.event_toolbar_grid.setColumnStretch(2, 0)
        else:
            self.event_toolbar_grid.addWidget(search, 0, 0)
            self.event_toolbar_grid.addWidget(
                sort, 0, 1, Qt.AlignmentFlag.AlignRight
            )
            self.event_toolbar_grid.addWidget(
                add, 0, 2, Qt.AlignmentFlag.AlignRight
            )
            self.event_toolbar_grid.setColumnStretch(0, 1)
            self.event_toolbar_grid.setColumnStretch(1, 0)
            self.event_toolbar_grid.setColumnStretch(2, 0)
        self.event_toolbar_grid.invalidate()

    def _reflow_quote_toolbar(self) -> None:
        if not hasattr(self, "quote_toolbar_grid"):
            return
        for widget in self.quote_toolbar_fields:
            self.quote_toolbar_grid.removeWidget(widget)
        width = self.quote_toolbar_wrap.width()
        compact = self.fontMetrics().lineSpacing() >= 22 or width < 520
        search, add = self.quote_toolbar_fields
        if compact:
            self.quote_toolbar_grid.addWidget(search, 0, 0)
            self.quote_toolbar_grid.addWidget(add, 1, 0, Qt.AlignmentFlag.AlignLeft)
        else:
            self.quote_toolbar_grid.addWidget(search, 0, 0)
            self.quote_toolbar_grid.addWidget(add, 0, 1, Qt.AlignmentFlag.AlignRight)
        self.quote_toolbar_grid.setColumnStretch(0, 1)
        self.quote_toolbar_grid.setColumnStretch(1, 0)

    def _dashboard_theme_changed(self, *_args: object) -> None:
        self._queue_theme_palette_stage(refresh_controls=True)

    def _queue_theme_palette_stage(self, refresh_controls: bool = False) -> None:
        """Finish combo changes after Qt has dismissed the active popup."""

        if self._building:
            return
        self._theme_palette_refresh_pending = (
            self._theme_palette_refresh_pending or refresh_controls
        )
        self._theme_palette_stage_timer.start(0)

    def _flush_theme_palette_stage(self) -> None:
        """Apply dependent controls and dirty feedback outside popup signals."""

        refresh_controls = self._theme_palette_refresh_pending
        self._theme_palette_refresh_pending = False
        if refresh_controls:
            self._update_glass_controls()
            self._refresh_heatmap_preset_options()
        self._stage_theme_palette_choices()

    def _stage_theme_palette_choices(self) -> None:
        """Stage the linked color choices without gathering the whole dialog."""

        if self._building:
            return
        theme_name = _combo_value(self.preset, "Sapphire Glass")
        selected = _combo_value(
            self.heatmap_preset,
            DEFAULT_HEATMAP_PRESETS[theme_name],
        )
        if selected not in HEATMAP_PRESETS[theme_name]:
            selected = DEFAULT_HEATMAP_PRESETS[theme_name]
        self._heatmap_preset_preferences[theme_name] = selected
        preferences = deepcopy(self._heatmap_preset_preferences)
        self.draft.values["appearance"]["preset"] = theme_name
        self.draft.values["heatmap"]["presets_by_theme"] = preferences
        self.staged["appearance"]["preset"] = theme_name
        self.staged["heatmap"]["presets_by_theme"] = deepcopy(preferences)
        if hasattr(self, "font_color_swatch"):
            self._update_color_swatch()
        self._update_dirty_state()

    def _update_glass_controls(self) -> None:
        if not all(hasattr(self, name) for name in ("preset", "opacity_slider", "opacity", "blur_slider", "blur")):
            return
        enabled = _combo_value(self.preset, "Sapphire Glass") == "Sapphire Glass"
        for widget in (self.opacity_slider, self.opacity, self.blur_slider, self.blur):
            widget.setEnabled(enabled)
        if hasattr(self, "opacity_field"):
            self.opacity_field.setVisible(enabled)
        if hasattr(self, "blur_field_label"):
            self.blur_field_label.setVisible(enabled)
        if hasattr(self, "blur_field"):
            self.blur_field.setVisible(enabled)
        self._reflow_compact_grids()

    def _select_heatmap_preset(self, preset_name: str) -> None:
        theme_name = _combo_value(self.preset, "Sapphire Glass")
        if preset_name not in HEATMAP_PRESETS[theme_name]:
            preset_name = DEFAULT_HEATMAP_PRESETS[theme_name]
        self._heatmap_preset_preferences[theme_name] = preset_name
        if hasattr(self, "heatmap_preset"):
            index = self.heatmap_preset.findData(preset_name)
            if index >= 0 and self.heatmap_preset.currentIndex() != index:
                blocked = self.heatmap_preset.blockSignals(True)
                self.heatmap_preset.setCurrentIndex(index)
                self.heatmap_preset.blockSignals(blocked)
        self._queue_theme_palette_stage()

    def _heatmap_preset_changed(self, *_args: object) -> None:
        if not hasattr(self, "heatmap_preset"):
            return
        self._queue_theme_palette_stage()

    def _refresh_heatmap_preset_options(self, *_args: object) -> None:
        if not hasattr(self, "heatmap_preset"):
            return
        theme_name = _combo_value(self.preset, "Sapphire Glass")
        selected = self._heatmap_preset_preferences.get(
            theme_name,
            DEFAULT_HEATMAP_PRESETS[theme_name],
        )
        if selected not in HEATMAP_PRESETS[theme_name]:
            selected = DEFAULT_HEATMAP_PRESETS[theme_name]
            self._heatmap_preset_preferences[theme_name] = selected
        blocked = self.heatmap_preset.blockSignals(True)
        self.heatmap_preset.clear()
        for preset_name in HEATMAP_PRESETS[theme_name]:
            self.heatmap_preset.addItem(preset_name, preset_name)
        index = self.heatmap_preset.findData(selected)
        self.heatmap_preset.setCurrentIndex(max(0, index))
        self.heatmap_preset.blockSignals(blocked)

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
        preset_name = _combo_value(self.preset, "Sapphire Glass") if hasattr(self, "preset") else "Sapphire Glass"
        dashboard_mode = _combo_value(self.mode, "auto") if hasattr(self, "mode") else "auto"
        variants = ("light", "dark") if dashboard_mode == "auto" else (dashboard_mode,)
        dashboard_contrast = {
            variant: _color_contrast(
                self.font_color_value,
                PRESETS.get(preset_name, PRESETS["Sapphire Glass"])[variant]["ui_surface_1"],
            )
            for variant in variants
        }
        ratio = min(dashboard_contrast.values()) if dashboard_contrast else 1.0
        custom_enabled = (
            hasattr(self, "theme_color")
            and self.theme_color.value("theme") == "custom"
        )
        if hasattr(self, "font_color_warning"):
            if self._font_color_invalid and custom_enabled:
                self.font_color_warning.setProperty("state", "error")
                self.font_color_warning.setVisible(True)
                self.font_color_warning.setText(
                    "Enter a valid #RRGGBB color."
                )
            else:
                self.font_color_warning.setProperty("state", "warning")
                low_modes = [
                    "{} ({:.1f}:1)".format(variant.capitalize(), value)
                    for variant, value in dashboard_contrast.items()
                    if value < 4.5
                ]
                self.font_color_warning.setVisible(custom_enabled and bool(low_modes))
                self.font_color_warning.setText(
                    "Low contrast on the {} dashboard background{}. The selected color will not be replaced.".format(
                        " and ".join(low_modes),
                        "s" if len(low_modes) != 1 else "",
                    )
                    if custom_enabled and low_modes
                    else ""
                )
            style = self.font_color_warning.style()
            style.unpolish(self.font_color_warning)
            style.polish(self.font_color_warning)
            self.font_color_warning.update()
        self.font_color_swatch.setAccessibleDescription(
            "Current custom verse color {}. Lowest dashboard-background contrast is {:.1f} to 1.".format(
                self.font_color_value.upper(), ratio,
            )
        )

    def _apply_theme(self) -> None:
        config = self.draft.values
        self._hdo_theme_tokens = _theme_tokens(config, self.controller.is_dark())
        stylesheet = _settings_style(config, self.controller.is_dark())
        if self.styleSheet() != stylesheet:
            self.setStyleSheet(stylesheet)
        _apply_role_fonts(self)
        self._update_color_swatch()
        if self._active_prompt is not None:
            self._active_prompt.refresh_palette()

    def _host_palette_changed(self) -> None:
        """Refresh cached native-palette tokens without disturbing view state."""

        self._hdo_theme_tokens = _theme_tokens(
            self.draft.values,
            self.controller.is_dark(),
        )
        _apply_role_fonts(self)
        self._update_color_swatch()
        if self._active_prompt is not None:
            self._active_prompt.refresh_palette()
        for view in self.findChildren(QAbstractItemView):
            view.viewport().update()

    def _update_forecast_range_visibility(self, *_args: object) -> None:
        """Keep the forecast range stable while reflecting its dependency."""

        self.forecast_days.setEnabled(self.show_forecast.isChecked())
        self.forecast_days.setVisible(True)
        self.forecast_range_label.setVisible(True)

    def _update_rotation_help(self, *_args: object) -> None:
        if not hasattr(self, "rotation_help"):
            return
        self.rotation_help.setText(
            {
                "daily": "Selects one new verse each day.",
                "every render": "Selects another verse whenever the dashboard refreshes.",
                "manual": "Keeps the selected verse until you choose another.",
            }.get(_combo_value(self.rotation, "daily"), "Selects one new verse each day.")
        )

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
        changed_paths = self.draft.changed_paths
        manual_quote_dirty = (
            self.pending_manual_quote is not None
            and self.pending_manual_quote != self._saved_current_quote
        )
        number_invalid = not self._number_fields_are_valid()
        dirty = (
            bool(changed_paths)
            or manual_quote_dirty
            or self._font_color_invalid
            or number_invalid
        )
        if self._saving:
            return
        if self.save_button is not None:
            self.save_button.setEnabled(
                dirty and not self._font_color_invalid and not number_invalid
            )
            self.save_button.setText(
                "Retry" if self._last_save_error else "Save changes"
            )
        if hasattr(self, "save_shortcut"):
            self.save_shortcut.setEnabled(
                dirty and not self._font_color_invalid and not number_invalid
            )
        if hasattr(self, "revert_button"):
            self.revert_button.setVisible(dirty)
        if self._last_save_error:
            self.footer.set_error(
                self._last_save_error,
                self._last_save_error_detail,
            )
        else:
            self.footer.set_error()
        if dirty:
            if self._font_color_invalid or number_invalid:
                count = max(1, len(changed_paths))
                error_count = int(self._font_color_invalid) + sum(
                    1
                    for field in self._number_fields()
                    if not field.is_valid()
                )
                self._set_status(
                    "validation-error",
                    "Fix {} error{} to save".format(
                        max(1, error_count),
                        "" if error_count == 1 else "s",
                    ),
                )
            else:
                count = len(changed_paths) + (1 if manual_quote_dirty else 0)
                self._set_status(
                    "dirty",
                    "{} unsaved change{}".format(count, "" if count == 1 else "s"),
                )
        else:
            self._set_status("clean", "")
        self._update_reset_visibility()

    def _number_fields(self) -> List[SuffixNumberField]:
        return [
            field
            for field in (
                getattr(self, "retention_target", None),
                getattr(self, "forecast_days", None),
                getattr(self, "font_size", None),
            )
            if isinstance(field, SuffixNumberField)
        ]

    def _number_fields_are_valid(self) -> bool:
        return all(field.is_valid() for field in self._number_fields())

    def _set_status(self, state: str, text: str) -> None:
        self.status_label.setProperty("state", state)
        self.footer.set_status(state, text)
        self.status_label.setAccessibleDescription(text)
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)
        self._schedule_settings_footer_clearance()

    def _clear_saved_status(self) -> None:
        """Clear transient save feedback while this dialog still owns the timer."""

        if self.status_label.property("state") == "saved":
            self._set_status("clean", "")

    def _clear_discarded_status(self) -> None:
        if self.status_label.property("state") == "discarded":
            self._set_status("clean", "")

    def _update_reset_visibility(self) -> None:
        scoped_cards = (
            (getattr(self, "appearance_card", None), "appearance"),
            (getattr(self, "dashboard_sections_card", None), "dashboard_sections"),
            (getattr(self, "study_metrics_card", None), "study_metrics"),
            (getattr(self, "calendar_display_card", None), "calendar_display"),
            (getattr(self, "calendar_range_card", None), "calendar_range"),
            (getattr(self, "local_data_card", None), "local_data"),
            (getattr(self, "bible_display_card", None), "bible_appearance"),
            (getattr(self, "bible_rotation_card", None), "bible_rotation"),
        )
        for card, scope in scoped_cards:
            if isinstance(card, SettingsCard) and card.reset_button is not None:
                card.reset_button.setVisible(
                    self.draft.scope_differs_from_defaults(scope)
                    or self._scope_has_visual_error(scope)
                )

    def _scope_has_visual_error(self, scope: str) -> bool:
        """Return whether a card owns an invalid value visible in its controls."""

        if scope == "study_metrics":
            return not self.retention_target.is_valid()
        if scope == "calendar_range":
            return not self.forecast_days.is_valid()
        if scope == "bible_appearance":
            return self._font_color_invalid or not self.font_size.is_valid()
        return False

    def _request_revert_changes(self) -> None:
        if self._saving:
            return
        if not self._has_staged_destructive_deletions():
            self._revert_changes()
            return
        self._show_prompt(
            "Discard deleted items?",
            "Discarding will restore the events or verses deleted in this draft.",
            [
                ("Cancel", "secondary", lambda: None),
                ("Discard changes", "danger", self._revert_changes),
            ],
            lambda: None,
        )

    def _has_staged_destructive_deletions(self) -> bool:
        baseline_events = {
            str(item.get("id", ""))
            for item in self.draft.baseline.get("events", {}).get("items", [])
            if isinstance(item, Mapping)
        }
        staged_events = {
            str(item.get("id", ""))
            for item in self.staged.get("events", {}).get("items", [])
            if isinstance(item, Mapping)
        }
        if baseline_events - staged_events:
            return True
        return bool(self._staged_deleted_quotes)

    def _revert_changes(self) -> None:
        if self._saving:
            return
        view_state = self._capture_transient_view_state()
        quote_feedback = self.quote_current_feedback.text()
        retain_quote_export_feedback = bool(
            quote_feedback.startswith("Exported verse library edits to ")
            or quote_feedback.startswith("Could not export verse library edits.")
        )
        baseline = deepcopy(self.draft.baseline)
        self.pending_manual_quote = None
        self._pending_manual_quote_index = None
        self._font_color_invalid = False
        self._last_save_error = ""
        self._last_save_error_detail = ""
        self._staged_deleted_quotes.clear()
        self._clear_undo_state()
        self._clear_event_feedback()
        self.draft.replace_values(baseline)
        self.staged = deepcopy(self.draft.values)
        self.quotes = list(self.staged["bible"]["quotes"])
        self._saved_current_quote = self._read_current_quote(self.staged)
        self._apply_config_to_widgets(self.staged)
        if retain_quote_export_feedback:
            self.quote_current_feedback.setText(quote_feedback)
        self._restore_transient_view_state(view_state)
        self._sync_draft()
        self._set_status("discarded", "Changes discarded")
        self.discarded_status_timer.start()

    def _reset_current_section(self) -> None:
        self._reset_card(self.current_section, SECTION_LABELS.get(self.current_section, "Section"))

    def _reset_card(self, scope: str, label: str) -> None:
        self._sync_draft()
        view_state = self._capture_transient_view_state()
        snapshot = self.draft.scope_snapshot(scope)
        if not snapshot:
            return
        visual_state = self._capture_reset_visual_state(scope)
        if not self.draft.reset_card(scope):
            return
        self._clear_undo_state()
        self._undo_record = {
            "kind": "reset",
            "scope": scope,
            "snapshot": snapshot,
            "visual_state": visual_state,
        }
        self.staged = deepcopy(self.draft.values)
        self._apply_config_to_widgets(self.staged, scope=scope)
        self._sync_draft()
        self._restore_transient_view_state(view_state)
        self.undo_message.setText("{} reset to defaults.".format(label))
        self.undo_toast.show()

    def _undo_reset(self) -> None:
        if self._saving:
            return
        record = self._undo_record
        if record is None:
            return
        self._sync_draft()
        view_state = self._capture_transient_view_state()
        self._clear_undo_state()
        if record.get("kind") == "reset":
            scope = str(record.get("scope", ""))
            snapshot = record.get("snapshot")
            if not isinstance(snapshot, Mapping):
                return
            if not self.draft.restore_scope(scope, snapshot):
                return
            self.staged = deepcopy(self.draft.values)
            self._apply_config_to_widgets(self.staged, scope=scope)
            visual_state = record.get("visual_state")
            if isinstance(visual_state, Mapping):
                self._restore_reset_visual_state(scope, visual_state)
            if scope in {"bible_rotation", "bible_verse"}:
                self._refresh_quote_list()
            self._sync_draft()
            self._restore_transient_view_state(view_state)
            return
        if record.get("kind") != "event_archive":
            return
        event_id = str(record.get("event_id", ""))
        event = next(
            (
                item
                for item in self.staged["events"]["items"]
                if str(item.get("id", "")) == event_id
            ),
            None,
        )
        values = record.get("values")
        if event is None or not isinstance(values, Mapping):
            return
        event["archived"] = bool(values.get("archived", False))
        event["archived_at"] = str(values.get("archived_at", ""))
        self._refresh_event_lists(
            select_event_id=event_id,
            select_archived=bool(event["archived"]),
        )

    def _clear_undo_state(self) -> None:
        self._undo_record = None
        if hasattr(self, "undo_toast"):
            self.undo_toast.hide()

    def _capture_reset_visual_state(self, scope: str) -> Dict[str, Any]:
        state: Dict[str, Any] = {}
        if scope in {"study_metrics", "dashboard", "home_screen_legacy"}:
            state["retention_text"] = self.retention_target.editor.text()
        if scope in {"calendar_range", "calendar"}:
            state["forecast_text"] = self.forecast_days.editor.text()
        if scope in {"calendar_display", "calendar"}:
            state["week_start_touched"] = self._week_start_touched
        if scope in {"bible_appearance", "bible_verse"}:
            state.update(
                font_size_text=self.font_size.editor.text(),
                font_color_text=self.font_color.text(),
                font_color_invalid=self._font_color_invalid,
                font_family_touched=self._font_family_touched,
            )
        if scope in {"bible_rotation", "bible_verse"}:
            state.update(
                pending_manual_quote=self.pending_manual_quote,
                pending_manual_quote_index=self._pending_manual_quote_index,
            )
        return state

    def _restore_reset_visual_state(
        self,
        scope: str,
        state: Mapping[str, Any],
    ) -> None:
        previous_building = self._building
        self._building = True
        try:
            if "retention_text" in state:
                self.retention_target.editor.setText(str(state["retention_text"]))
            if "forecast_text" in state:
                self.forecast_days.editor.setText(str(state["forecast_text"]))
            if "week_start_touched" in state:
                self._week_start_touched = bool(state["week_start_touched"])
            if scope in {"bible_appearance", "bible_verse"}:
                if "font_size_text" in state:
                    self.font_size.editor.setText(str(state["font_size_text"]))
                if "font_color_text" in state:
                    self.font_color.setText(str(state["font_color_text"]))
                self._font_color_invalid = bool(
                    state.get("font_color_invalid", False)
                )
                self._font_family_touched = bool(
                    state.get("font_family_touched", False)
                )
            if scope in {"bible_rotation", "bible_verse"}:
                pending = state.get("pending_manual_quote")
                self.pending_manual_quote = (
                    str(pending) if isinstance(pending, str) else None
                )
                pending_index = state.get("pending_manual_quote_index")
                self._pending_manual_quote_index = (
                    int(pending_index) if isinstance(pending_index, int) else None
                )
        finally:
            self._building = previous_building
        if scope in {"bible_appearance", "bible_verse"}:
            self._update_color_swatch()

    def _read_current_quote(self, config: Mapping[str, Any]) -> str:
        bible = config.get("bible", {})
        if not isinstance(bible, Mapping):
            return ""
        quotes = bible.get("quotes", [])
        if not isinstance(quotes, list):
            return ""
        accessor = getattr(getattr(self.controller, "rotator", None), "current_quote", None)
        if not callable(accessor):
            return ""
        try:
            return str(accessor(list(quotes), str(bible.get("rotation_mode", "daily"))))
        except Exception:
            return ""

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

    def _apply_config_to_widgets(
        self,
        config: Mapping[str, Any],
        scope: str = "",
    ) -> None:
        """Hydrate all controls, or only the controls owned by one Reset card."""

        full = not scope
        appearance_scopes = {"appearance", "dashboard"}
        section_scopes = {"dashboard_sections", "dashboard", "home_screen_legacy"}
        study_scopes = {"study_metrics", "dashboard", "home_screen_legacy"}
        calendar_display_scopes = {"calendar_display", "calendar"}
        calendar_range_scopes = {"calendar_range", "calendar"}
        local_data_scopes = {"local_data", "calendar"}
        bible_appearance_scopes = {"bible_appearance", "bible_verse"}
        bible_rotation_scopes = {"bible_rotation", "bible_verse"}
        previous_building = self._building
        self._building = True
        try:
            heatmap = config["heatmap"]
            bible = config["bible"]
            if full or scope in appearance_scopes:
                appearance = config["appearance"]
                self._set_combo_data(self.preset, appearance["preset"])
                self._set_combo_data(self.mode, appearance["mode"])
                self.opacity.setValue(int(appearance["opacity"]))
                self.blur.setValue(int(appearance.get("blur", 12)))
                self.text_scale.setValue(int(appearance["text_scale"]))
                self._set_combo_data(
                    self.home_screen_position,
                    config["home_screen"]["position"],
                )
                self._heatmap_preset_preferences = deepcopy(
                    heatmap.get("presets_by_theme", {})
                )
                self._update_glass_controls()
                self._refresh_heatmap_preset_options()
            elif scope == "home_screen_legacy":
                self._set_combo_data(
                    self.home_screen_position,
                    config["home_screen"]["position"],
                )
            if full:
                for key, box in self.visibility.items():
                    box.setChecked(bool(config["visibility"][key]))
            elif scope in section_scopes:
                for key in ("heatmap", "remaining", "today", "heatmap_metrics", "bible"):
                    self.visibility[key].setChecked(bool(config["visibility"][key]))
            if full or scope in study_scopes:
                self._set_combo_data(self.pace_unit, config["study"]["pace_unit"])
                self.retention_target.setValue(
                    int(config["study"].get("retention_target", 80))
                )
                self.include_rescheduled.setChecked(
                    bool(config["new_cards"]["include_rescheduled"])
                )
            if full or scope in calendar_display_scopes:
                self._set_combo_data(self.calendar_view, heatmap["calendar_view"])
                self._legacy_week_start_value = str(heatmap["week_start"])
                self._week_start_touched = False
                self._set_combo_data(self.week_start, self._legacy_week_start_value)
                self.visibility["events"].setChecked(
                    bool(config["visibility"]["events"])
                )
            if full or scope in calendar_range_scopes:
                history_choice = history_range_choice(
                    heatmap.get("history_days", 0),
                    heatmap.get("ignore_before", ""),
                )
                self._set_combo_data(self.history_range, history_choice)
                self.forecast_days.setValue(int(heatmap["forecast_days"]))
                self.show_forecast.setChecked(bool(heatmap["show_due_forecast"]))
                parsed = QDate.fromString(
                    str(heatmap["ignore_before"]),
                    "yyyy-MM-dd",
                )
                self.ignore_before.setDate(
                    parsed if parsed.isValid() else QDate.currentDate()
                )
                self._update_forecast_range_visibility()
                self._update_history_range_visibility()
            if full or scope in local_data_scopes:
                self.exclude_reschedules.setChecked(
                    bool(heatmap["exclude_manual_reschedules"])
                )
                self.exclude_deleted.setChecked(
                    bool(heatmap["exclude_deleted_cards"])
                )
                self._apply_deck_exclusions(heatmap["excluded_deck_ids"])
                self._update_deck_exclusion_summary()
            if full:
                self._set_combo_data(self.event_sort, config["events"]["sort"])
            if full or scope in bible_appearance_scopes:
                family_name = (
                    str(bible["font_family"])
                    .split(",", 1)[0]
                    .strip()
                    .strip('"\'')
                )
                self._select_saved_font_family(family_name)
                self.font_size.setValue(
                    int(str(bible["font_size"]).replace("px", ""))
                )
                self.font_color_value = str(bible["font_color"])
                self._font_color_invalid = False
                self.font_color.setText(self.font_color_value.upper())
                self.theme_color.setValue(
                    "theme" if bible["theme_aware_color"] else "custom"
                )
                self._font_family_touched = False
            if full or scope in bible_rotation_scopes:
                self._set_combo_data(self.rotation, bible["rotation_mode"])
                self._update_rotation_help()
                self._update_quote_actions()
            if full:
                self.quotes = list(bible["quotes"])
                self.pending_manual_quote = None
                self._pending_manual_quote_index = None
                self._refresh_event_lists()
                self._refresh_quote_list()
        finally:
            self._building = previous_building
        if full or scope in appearance_scopes or scope in bible_appearance_scopes:
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
        self._fit_deck_tree()

    def _fit_deck_tree(self) -> None:
        visible_rows = 0

        def visit(item: QTreeWidgetItem, parent_expanded: bool) -> None:
            nonlocal visible_rows
            if item.isHidden() or not parent_expanded:
                return
            visible_rows += 1
            expanded = item.isExpanded()
            for row in range(item.childCount()):
                visit(item.child(row), expanded)

        for row in range(self.deck_tree.topLevelItemCount()):
            visit(self.deck_tree.topLevelItem(row), True)
        row_height = _row_target_height(self.deck_tree)
        self.deck_tree.setFixedHeight(max(row_height + 8, visible_rows * row_height + 8))

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
        if hasattr(self, "deck_tree"):
            self._fit_deck_tree()
        self._settings_changed()

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
        self._fit_deck_tree()
        self._update_deck_exclusion_summary()

    def _choose_font_color(self) -> None:
        selected = QColorDialog.getColor(parent=self, title="Choose Bible verse color")
        if not selected.isValid():
            return
        self._font_color_invalid = False
        self.font_color_value = selected.name().upper()
        self.font_color.setText(self.font_color_value.upper())
        self._update_color_swatch()
        self._settings_changed()

    def _font_color_edited(self) -> None:
        candidate = self.font_color.text().strip()
        if re.fullmatch(r"#[0-9A-Fa-f]{6}", candidate):
            self._font_color_invalid = False
            self.font_color_value = candidate.upper()
            self.font_color.setText(candidate.upper())
            self._update_color_swatch()
            self._settings_changed()
        else:
            self._font_color_invalid = True
            self._update_color_swatch()
            self._update_dirty_state()

    def _font_color_text_changed(self, value: str) -> None:
        if self._building:
            return
        if not re.fullmatch(r"#[0-9A-Fa-f]{6}", value.strip()):
            self._font_color_invalid = self.theme_color.value("theme") == "custom"
            self._update_color_swatch()
            self._update_dirty_state()
            return
        self._font_color_invalid = False
        candidate = value.strip().upper()
        if candidate == self.font_color_value.upper():
            return
        self.font_color_value = candidate
        self._update_color_swatch()
        self._settings_changed()

    def _font_family_changed(self, *_args: object) -> None:
        if self._building:
            return
        self._font_family_touched = True
        self._settings_changed()

    def _select_saved_font_family(self, family_name: str) -> None:
        previous = getattr(self, "_unavailable_font_label", "")
        if previous:
            previous_index = self.font_family.findText(previous)
            if previous_index >= 0:
                self.font_family.removeItem(previous_index)
        self._unavailable_font_label = ""
        index = self.font_family.findText(family_name, Qt.MatchFlag.MatchFixedString)
        if index >= 0:
            self.font_family.setCurrentIndex(index)
            self.font_family.setToolTip(
                "Applies only to verse body and reference text."
            )
            return
        label = "{} — Unavailable on this device".format(family_name or "Saved font")
        try:
            self.font_family.insertItem(0, label)
            self.font_family.setCurrentIndex(0)
            self._unavailable_font_label = label
        except Exception:
            pass
        self.font_family.setToolTip(
            "{}; the dashboard uses its safe Georgia/serif fallback until you choose an installed font.".format(
                label
            )
        )
        self.font_family.setAccessibleDescription(self.font_family.toolTip())

    def _settings_changed(self, *_args: object) -> None:
        """Synchronize native control changes without timers or secondary UI."""

        if self._building:
            return
        self._sync_draft()

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
        sort_value = _combo_value(self.event_sort, "ascending") if hasattr(self, "event_sort") else "ascending"
        if sort_value == "name":
            events = sorted(
                self.staged["events"]["items"],
                key=lambda item: (
                    str(item.get("name", "")).casefold(),
                    str(item.get("date", "")),
                    str(item.get("id", "")),
                ),
            )
        else:
            events = sorted(
                self.staged["events"]["items"],
                key=lambda item: (
                    str(item.get("date", "")),
                    str(item.get("name", "")).casefold(),
                    str(item.get("id", "")),
                ),
                reverse=sort_value == "descending",
            )
        for event in events:
            if needle and needle not in event["name"].casefold() and needle not in event["date"]: continue
            event_id = str(event["id"])
            status = self._event_stage_status(event)
            item = SettingsTableRow([""], event["id"], [event["name"]])
            item.setData(0, EVENT_DATE_ROLE, _display_date(event["date"]))
            item.setData(0, EVENT_NAME_ROLE, event["name"])
            item.setData(0, EVENT_STATUS_ROLE, status)
            tree = self.archived_events if event.get("archived") else self.active_events
            tree.addTopLevelItem(item)
            metadata = "{}{}".format(
                _display_date(event["date"]),
                " · {}".format(status) if status else "",
            )
            row_widget = EventRowWidget(
                tree,
                item,
                str(event["name"]),
                metadata,
                (
                    None
                    if bool(event.get("archived"))
                    else lambda event_key=event_id: self._invoke_event_action(
                        event_key, False, "edit"
                    )
                ),
            )
            _apply_role_fonts(row_widget)
            row_height = _event_row_target_height(tree, row_widget)
            item.setSizeHint(
                0,
                QSize(max(1, tree.viewport().width()), row_height),
            )
            tree.setItemWidget(item, 0, row_widget)
            self._attach_event_menu(tree, item, row_widget, event_id, bool(event.get("archived")))
        _apply_view_row_targets(self.active_events)
        _apply_view_row_targets(self.archived_events)
        self.event_tabs.setTabText(0, "Active ({})".format(self.active_events.topLevelItemCount()))
        self.event_tabs.setTabText(1, "Archived ({})".format(self.archived_events.topLevelItemCount()))
        if hasattr(self, "event_toolbar_wrap"):
            self.event_toolbar_wrap.setVisible(bool(self.staged["events"]["items"]))
        if select_event_id is not None:
            self._select_event_id(select_event_id, bool(select_archived))
        self._fit_event_tree(self.active_events)
        self._fit_event_tree(self.archived_events)
        self._settings_changed()
        self._reconcile_event_feedback()
        self._update_event_actions()

    def _baseline_event(self, event_id: str) -> Optional[Mapping[str, Any]]:
        return next(
            (
                item
                for item in self.draft.baseline.get("events", {}).get("items", [])
                if isinstance(item, Mapping)
                and str(item.get("id", "")) == event_id
            ),
            None,
        )

    def _event_stage_status(self, event: Mapping[str, Any]) -> str:
        baseline = self._baseline_event(str(event.get("id", "")))
        if baseline is None:
            return "New"
        if any(
            str(event.get(key, "")) != str(baseline.get(key, ""))
            for key in ("name", "date")
        ):
            return "Edited"
        if bool(event.get("archived")) != bool(baseline.get("archived")):
            return "Archived" if event.get("archived") else "Restored"
        return ""

    def _event_items_differ_from_baseline(self) -> bool:
        return (
            self.staged.get("events", {}).get("items", [])
            != self.draft.baseline.get("events", {}).get("items", [])
        )

    def _reconcile_event_feedback(self) -> None:
        if (
            hasattr(self, "event_action_feedback")
            and not self._event_items_differ_from_baseline()
            and "Save to keep" in self.event_action_feedback.text()
        ):
            self._clear_event_feedback()

    def _attach_event_menu(
        self,
        tree: QTreeWidget,
        item: QTreeWidgetItem,
        row_widget: EventRowWidget,
        event_id: str,
        archived: bool,
    ) -> None:
        button = row_widget.overflow
        button.setToolTip("Event actions")
        _set_accessibility(
            button,
            "Actions for {}".format(item.data(0, EVENT_NAME_ROLE)),
            (
                "Restore or permanently delete this event."
                if archived
                else "Edit, archive, or delete this event."
            ),
        )

        def open_menu() -> None:
            tree.setCurrentItem(item)
            menu = QMenu(button)
            edit_action = None if archived else menu.addAction("Edit")
            archive_action = menu.addAction("Restore" if archived else "Archive")
            menu.addSeparator()
            delete_action = menu.addAction(
                "Delete permanently" if archived else "Delete"
            )
            if edit_action is not None:
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

    def _invoke_event_action(self, event_id: str, archived: bool, action: str) -> None:
        if self._saving:
            return
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
        row_widget = (
            current_tree.itemWidget(current_tree.topLevelItem(0), 0)
            if row_count
            else None
        )
        list_height = (
            (min(6, row_count) * _event_row_target_height(current_tree, row_widget))
            + 2
            if row_count
            else 2
        )
        panel_height = tab_height + list_height
        self.event_tabs.setMinimumHeight(panel_height)
        self.event_tabs.setMaximumHeight(panel_height)
        query = self.event_search.text().strip()
        if query:
            self.event_result_summary.setText(
                "{} matching event{}".format(row_count, "" if row_count == 1 else "s")
            )
        else:
            self.event_result_summary.clear()
        if row_count == 0:
            kind = "archived" if archived else "active"
            if query:
                self.event_empty_title.setText("No events match “{}”.".format(query))
                self.event_empty_copy.setText(
                    "Clear the search or try another term."
                )
                self.event_empty_clear.show()
                self.event_empty_add.hide()
            elif not self.staged["events"]["items"]:
                self.event_empty_title.setText("No events yet")
                self.event_empty_copy.setText(
                    "Add an event to show it on the calendar."
                )
                self.event_empty_clear.hide()
                self.event_empty_add.show()
            else:
                self.event_empty_title.setText("No {} events".format(kind))
                self.event_empty_copy.setText(
                    "{} events will appear here.".format(kind.capitalize())
                )
                self.event_empty_clear.hide()
                self.event_empty_add.hide()
            self.event_empty_state.show()
        else:
            self.event_empty_state.hide()
        has_events = bool(self.staged["events"]["items"])
        self.event_add.setVisible(not has_events)
        self.event_toolbar_add.setVisible(has_events)
        self._fit_header_height()
        self._event_selection_changed()

    def _select_event_date(self, selected_date: str) -> None:
        self.selected_event_date = selected_date
        display_date = _display_date(selected_date)
        self.event_date_context.setText("Selected date · {}".format(display_date))
        self.event_date_context.show()
        self.event_add.setText("Add event")
        self.event_add.setAccessibleName("Add event for {}".format(display_date))
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
        if self._saving:
            return
        dialog = EventEditDialog(self, initial_date=self.selected_event_date)
        if dialog.exec() != QDialog.DialogCode.Accepted: return
        name, event_date = dialog.values()
        self.selected_event_date = event_date
        event_id = "event-{}".format(time.time_ns())
        self.staged["events"]["items"].append({"id": event_id, "name": name, "date": event_date, "archived": False, "created_at": datetime.now().astimezone().isoformat(timespec="seconds"), "archived_at": ""})
        self._refresh_event_lists(select_event_id=event_id, select_archived=False)
        self._set_event_feedback("Added ‘{}’ for {}. Save to keep this change.".format(name, _display_date(event_date)))

    def _edit_event(self) -> None:
        if self._saving:
            return
        event = self._selected_event()
        if event is None: return
        dialog = EventEditDialog(self, event)
        if dialog.exec() != QDialog.DialogCode.Accepted: return
        event_id = str(event["id"])
        event["name"], event["date"] = dialog.values()
        self._refresh_event_lists(select_event_id=event_id, select_archived=bool(event.get("archived")))
        status = self._event_stage_status(event)
        self._set_event_feedback(
            "Updated ‘{}’. Save to keep this change.".format(event["name"]),
            change_active=status in {"New", "Edited"},
        )

    def _toggle_event_archive(self) -> None:
        if self._saving:
            return
        event = self._selected_event()
        if event is None: return
        event_id = str(event["id"])
        self._clear_undo_state()
        self._undo_record = {
            "kind": "event_archive",
            "event_id": event_id,
            "values": {
                "archived": bool(event.get("archived")),
                "archived_at": str(event.get("archived_at", "")),
            },
        }
        event["archived"] = not bool(event.get("archived"))
        baseline = self._baseline_event(event_id)
        if baseline is not None and bool(event["archived"]) == bool(
            baseline.get("archived")
        ):
            event["archived_at"] = str(baseline.get("archived_at", ""))
        else:
            event["archived_at"] = (
                datetime.now().astimezone().isoformat(timespec="seconds")
                if event["archived"]
                else ""
            )
        self._refresh_event_lists(
            select_event_id=event_id,
            select_archived=bool(event["archived"]),
        )
        action = "Archived" if event["archived"] else "Restored"
        destination = "Archived" if event["archived"] else "Active"
        archive_changed = baseline is None or bool(event["archived"]) != bool(
            baseline.get("archived")
        )
        self._set_event_feedback(
            "{} ‘{}’. Moved to {}. Save to keep this change.".format(
                action,
                event["name"],
                destination,
            ),
            change_active=archive_changed,
        )
        self.undo_message.setText("{} ‘{}’.".format(action, event["name"]))
        self.undo_toast.show()

    def _delete_event(self) -> None:
        if self._saving:
            return
        event = self._selected_event()
        if event is None: return
        permanent = bool(event.get("archived"))
        event_id = str(event.get("id", ""))
        name = str(event.get("name", ""))
        self._show_prompt(
            "Delete event permanently?" if permanent else "Delete event?",
            (
                "Permanently remove ‘{}’? The deletion remains staged until you save."
                if permanent
                else "Delete ‘{}’? The deletion remains staged until you save."
            ).format(name),
            [
                ("Cancel", "secondary", lambda: None),
                (
                    "Delete permanently" if permanent else "Delete",
                    "danger",
                    lambda: self._stage_event_deletion(event_id, name),
                ),
            ],
            lambda: None,
        )

    def _stage_event_deletion(self, event_id: str, name: str) -> None:
        if self._saving:
            return
        target = next(
            (
                item
                for item in self.staged["events"]["items"]
                if str(item.get("id", "")) == event_id
            ),
            None,
        )
        if target is None:
            return
        change_active = self._baseline_event(event_id) is not None
        self.staged["events"]["items"].remove(target)
        self._refresh_event_lists()
        self._set_event_feedback(
            "Deleted ‘{}’. Save to keep this change.".format(name),
            change_active=change_active,
        )

    def _set_event_feedback(
        self,
        message: str,
        *,
        change_active: bool = True,
    ) -> None:
        if not change_active or not self._event_items_differ_from_baseline():
            self._clear_event_feedback()
            return
        self.event_action_feedback.setText(message)
        self.event_action_feedback.setAccessibleName(message)
        self.event_action_feedback.setAccessibleDescription(message)

    def _clear_event_feedback(self) -> None:
        if not hasattr(self, "event_action_feedback"):
            return
        self.event_action_feedback.clear()
        self.event_action_feedback.setAccessibleName("Event action confirmation")
        self.event_action_feedback.setAccessibleDescription("")

    def _selected_quote_index(self) -> Optional[int]:
        value = self.quote_model.source_index(self.quote_list.currentIndex())
        return value if value is not None and 0 <= value < len(self.quotes) else None

    def _update_quote_detail(self, *_args: object) -> None:
        self.quote_list.viewport().update()

    def _quote_search_changed(self, *_args: object) -> None:
        self._refresh_quote_list()

    def _refresh_quote_list(self, *_args: object) -> None:
        pending_index = self._pending_manual_quote_index
        pending_is_valid = bool(
            self.pending_manual_quote is not None
            and pending_index is not None
            and 0 <= pending_index < len(self.quotes)
            and self.quotes[pending_index] == self.pending_manual_quote
        )
        if self.pending_manual_quote is not None and not pending_is_valid:
            self.pending_manual_quote = None
            self._pending_manual_quote_index = None
            if not self._building:
                self._update_dirty_state()
        selected = self._selected_quote_index()
        needle = self.quote_search.text().strip() if hasattr(self, "quote_search") else ""
        self.quote_model.set_source(
            self.quotes,
            needle,
            self._saved_current_quote,
            self.pending_manual_quote or "",
            self._pending_manual_quote_index,
        )
        target = self.quote_model.model_index_for_source(selected)
        if not target.isValid() and self.quote_model.rowCount() > 0:
            target = self.quote_model.index(0, 0)
        self.quote_list.setCurrentIndex(target)
        total = self.quote_model.matching_count
        self.quote_count.setText(
            "{} of {} verses".format(total, len(self.quotes))
            if needle
            else "{} verses".format(len(self.quotes))
        )
        self._update_quote_detail()
        self._update_quote_actions()
        self._settings_changed()

    def _fit_quote_list(self) -> None:
        viewport_height = 0
        bible_index = self.page_indices.get("bible_verse")
        if bible_index is not None:
            scroll = self.stack.widget(bible_index)
            if isinstance(scroll, QScrollArea):
                viewport_height = scroll.viewport().height()
        if viewport_height <= 0:
            viewport_height = self.height()
        target = max(180, min(520, viewport_height - 300))
        self.quote_list.setMinimumHeight(target)
        self.quote_list.setMaximumHeight(target)
        self.quote_list.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

    def _open_quote_menu_for_model(
        self,
        index: QModelIndex,
        global_point: QPoint,
    ) -> None:
        if self._saving:
            return
        self.quote_list.setCurrentIndex(index)

        def invoke(action: str) -> None:
            if action == "current":
                self._stage_selected_manual_quote()
            elif action == "edit":
                self._edit_quote()
            elif action == "duplicate":
                self._duplicate_quote()
            elif action == "delete":
                self._delete_quote()

        menu = QMenu(self.quote_list)
        menu.setAccessibleName("Verse actions")
        current_action = menu.addAction("Use as current")
        current_action.setEnabled(_combo_value(self.rotation, "daily") == "manual")
        edit_action = menu.addAction("Edit")
        duplicate_action = menu.addAction("Duplicate")
        menu.addSeparator()
        delete_action = menu.addAction("Delete")
        current_action.triggered.connect(lambda: invoke("current"))
        edit_action.triggered.connect(lambda: invoke("edit"))
        duplicate_action.triggered.connect(lambda: invoke("duplicate"))
        delete_action.triggered.connect(lambda: invoke("delete"))
        menu.exec(global_point)

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
            selected_index = self._selected_quote_index()
            self.pending_manual_quote = None
            self._pending_manual_quote_index = None
            self.quote_model.set_source(
                self.quotes,
                self.quote_search.text().strip(),
                self._saved_current_quote,
                "",
                None,
            )
            self.quote_list.setCurrentIndex(
                self.quote_model.model_index_for_source(selected_index)
            )
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
        if self._saving:
            return
        index = self._selected_quote_index()
        if index is None or _combo_value(self.rotation, "daily") != "manual":
            return
        selected_quote = self.quotes[index]
        if selected_quote == self._saved_current_quote:
            self.pending_manual_quote = None
            self._pending_manual_quote_index = None
        else:
            self.pending_manual_quote = selected_quote
            self._pending_manual_quote_index = index
        self._refresh_quote_list()

    def _add_quote(self) -> None:
        if self._saving:
            return
        dialog = TextEditDialog("Add verse", "", self)
        if dialog.exec() != QDialog.DialogCode.Accepted or not dialog.value(): return
        if len(self.quotes) >= 500: QMessageBox.warning(self, "Verse limit", "The bundled NLT library is limited to 500 quoted verses."); return
        self.quotes.append(dialog.value()); self._refresh_quote_list()

    def _edit_quote(self) -> None:
        if self._saving:
            return
        index = self._selected_quote_index()
        if index is None: return
        dialog = TextEditDialog("Edit verse", self.quotes[index], self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.value():
            self.quotes[index] = dialog.value()
            if self._pending_manual_quote_index == index:
                self.pending_manual_quote = dialog.value()
            self._refresh_quote_list()

    def _duplicate_quote(self) -> None:
        if self._saving:
            return
        index = self._selected_quote_index()
        if index is None: return
        if len(self.quotes) >= 500: QMessageBox.warning(self, "Verse limit", "The library is limited to 500 quoted verses."); return
        self.quotes.insert(index + 1, self.quotes[index])
        if (
            self._pending_manual_quote_index is not None
            and self._pending_manual_quote_index > index
        ):
            self._pending_manual_quote_index += 1
        self._refresh_quote_list()

    def _delete_quote(self) -> None:
        if self._saving:
            return
        index = self._selected_quote_index()
        if index is None: return
        if len(self.quotes) <= 1: QMessageBox.warning(self, "Verse required", "Keep at least one Bible verse in the library."); return
        quote = self.quotes[index]
        _body, reference = split_quote_reference(quote)
        self._show_prompt(
            "Delete verse?",
            "Remove {}? The deletion remains staged until you save.".format(
                reference or "the selected custom verse"
            ),
            [
                ("Cancel", "secondary", lambda: None),
                ("Delete", "danger", lambda: self._stage_quote_deletion(index)),
            ],
            lambda: None,
        )

    def _stage_quote_deletion(self, index: int) -> None:
        if self._saving:
            return
        if not 0 <= index < len(self.quotes):
            return
        quote = self.quotes.pop(index)
        self._staged_deleted_quotes.append(quote)
        if self._pending_manual_quote_index == index:
            self.pending_manual_quote = None
            self._pending_manual_quote_index = None
        elif (
            self._pending_manual_quote_index is not None
            and self._pending_manual_quote_index > index
        ):
            self._pending_manual_quote_index -= 1
        self._refresh_quote_list()

    def _import_quotes(self) -> None:
        if self._saving:
            return
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
        try:
            Path(path).write_text(
                json.dumps({"quotes": self.quotes}, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        except OSError as exc:
            self._last_export_error = str(exc).strip() or "The export file could not be written."
            self.export_feedback.setText(
                "Could not export verse library edits. Your staged settings were not changed."
            )
            self.export_feedback.setProperty("state", "error")
            self.export_copy_error.show()
            self.quote_current_feedback.setText(
                "Could not export verse library edits. Your staged settings were not changed."
            )
            self.quote_export_error.show()
            return
        self._last_export_error = ""
        self.export_feedback.setProperty("state", "success")
        self.export_feedback.setText(
            "Verse library edits exported to {}.".format(path)
        )
        self.export_copy_error.hide()
        self.quote_export_error.hide()
        self.quote_current_feedback.setText(
            "Exported verse library edits to {}.".format(path)
        )

    def _copy_export_error(self) -> None:
        if not self._last_export_error:
            return
        QApplication.clipboard().setText(self._last_export_error)
        for button in (self.export_copy_error, self.quote_export_error):
            button.setText("Error copied")
        self._export_copy_timer.start(2000)

    def _reset_export_copy_labels(self) -> None:
        for name in ("export_copy_error", "quote_export_error"):
            button = getattr(self, name, None)
            if isinstance(button, QPushButton):
                button.setText("Copy error")

    def _latest_stored_config(self) -> Mapping[str, Any]:
        try:
            raw = mw.addonManager.getConfig(self.controller.package)
        except Exception:
            raw = self.controller.config
        return raw if isinstance(raw, Mapping) else self.controller.config

    def _capture_transient_view_state(self) -> Dict[str, Any]:
        page_scrolls: List[int] = []
        for index in range(self.stack.count()):
            scroll = self.stack.widget(index)
            page_scrolls.append(
                scroll.verticalScrollBar().value()
                if isinstance(scroll, QScrollArea)
                else 0
            )
        event = self._selected_event() if hasattr(self, "event_tabs") else None
        deck_items = self._walk_deck_items() if hasattr(self, "deck_tree") else []
        current_deck = self.deck_tree.currentItem() if hasattr(self, "deck_tree") else None

        def deck_key(item: Optional[QTreeWidgetItem]) -> tuple[str, object]:
            if item is None:
                return "", None
            return (
                str(item.data(0, DECK_PATH_ROLE) or item.text(0)),
                item.data(0, Qt.ItemDataRole.UserRole),
            )

        return {
            "section": self.current_section,
            "page_scrolls": page_scrolls,
            "event_search": self.event_search.text(),
            "deck_search": self.deck_search.text(),
            "quote_search": self.quote_search.text(),
            "calendar_disclosure": self.calendar_display_disclosure.isChecked(),
            "local_data_disclosure": self.local_data_disclosure.isChecked(),
            "event_tab": self.event_tabs.currentIndex(),
            "event_id": str(event.get("id", "")) if event is not None else "",
            "event_archived": bool(event.get("archived")) if event is not None else False,
            "event_scrolls": (
                self.active_events.verticalScrollBar().value(),
                self.archived_events.verticalScrollBar().value(),
            ),
            "quote_source": self._selected_quote_index(),
            "quote_scroll": self.quote_list.verticalScrollBar().value(),
            "deck_current": deck_key(current_deck),
            "deck_expanded": [
                deck_key(item) for item in deck_items if item.isExpanded()
            ],
            "deck_scroll": self.deck_tree.verticalScrollBar().value(),
        }

    def _restore_transient_view_state(self, state: Mapping[str, Any]) -> None:
        for name, key in (
            ("event_search", "event_search"),
            ("deck_search", "deck_search"),
            ("quote_search", "quote_search"),
        ):
            value = state.get(key)
            widget = getattr(self, name, None)
            if isinstance(widget, QLineEdit) and isinstance(value, str):
                widget.setText(value)
        if "calendar_disclosure" in state:
            self.calendar_display_disclosure.setChecked(
                bool(state["calendar_disclosure"])
            )
        if "local_data_disclosure" in state:
            self.local_data_disclosure.setChecked(
                bool(state["local_data_disclosure"])
            )
        section = str(state.get("section", self.current_section))
        if section in self.page_indices:
            self._show_section(section)
        event_tab = int(state.get("event_tab", 0))
        self.event_tabs.setCurrentIndex(max(0, min(1, event_tab)))
        event_id = str(state.get("event_id", ""))
        if event_id:
            self._select_event_id(
                event_id,
                bool(state.get("event_archived", False)),
            )
        quote_source = state.get("quote_source")
        quote_index = self.quote_model.model_index_for_source(quote_source)
        if quote_index.isValid():
            self.quote_list.setCurrentIndex(quote_index)
        expanded_values = state.get("deck_expanded", [])
        expanded = {
            tuple(value)
            for value in expanded_values
            if isinstance(value, (tuple, list)) and len(value) == 2
        }
        current_value = state.get("deck_current", ("", None))
        current_key = (
            tuple(current_value)
            if isinstance(current_value, (tuple, list)) and len(current_value) == 2
            else ("", None)
        )
        current_deck = None
        for item in self._walk_deck_items():
            key = (
                str(item.data(0, DECK_PATH_ROLE) or item.text(0)),
                item.data(0, Qt.ItemDataRole.UserRole),
            )
            item.setExpanded(key in expanded)
            if key == current_key:
                current_deck = item
        if current_deck is not None:
            self.deck_tree.setCurrentItem(current_deck)
        for index, value in enumerate(state.get("page_scrolls", [])):
            scroll = self.stack.widget(index) if index < self.stack.count() else None
            if isinstance(scroll, QScrollArea):
                scroll.verticalScrollBar().setValue(int(value))
        event_scrolls = state.get("event_scrolls", (0, 0))
        if isinstance(event_scrolls, (tuple, list)) and len(event_scrolls) == 2:
            self.active_events.verticalScrollBar().setValue(int(event_scrolls[0]))
            self.archived_events.verticalScrollBar().setValue(int(event_scrolls[1]))
        self.quote_list.verticalScrollBar().setValue(int(state.get("quote_scroll", 0)))
        self.deck_tree.verticalScrollBar().setValue(int(state.get("deck_scroll", 0)))

    def _save(self) -> None:
        if self._saving or self._active_prompt is not None:
            return
        self._sync_draft()
        if self._font_color_invalid or not self._number_fields_are_valid():
            self._update_dirty_state()
            return
        manual_quote_dirty = (
            self.pending_manual_quote is not None
            and self.pending_manual_quote != self._saved_current_quote
        )
        if not self.draft.dirty and not manual_quote_dirty:
            if self._pending_close_after_save:
                self._pending_close_after_save = False
                self._close_dialog()
            return
        self._last_save_error = ""
        self._last_save_error_detail = ""
        self.footer.set_error()
        self._saving = True
        self._set_status("saving", "Saving changes...")
        if self.save_button is not None:
            self.save_button.setText("Save changes")
            self.save_button.setEnabled(False)
        if self.close_button is not None:
            self.close_button.setEnabled(False)
        self.save_shortcut.setEnabled(False)
        self.close_shortcut.setEnabled(False)
        self.escape_shortcut.setEnabled(False)
        self._set_mutation_controls_enabled(False)
        original_baseline = deepcopy(self.draft.baseline)
        original_values = deepcopy(self.draft.values)
        self._queued_save_state = (
            original_baseline,
            original_values,
            self.pending_manual_quote,
        )
        # Give Qt one event turn to paint the spinner and stable disabled
        # actions before the synchronous configuration transaction begins.
        self.footer.repaint()
        self._save_dispatch_timer.start(0)

    def _continue_save(self) -> None:
        queued = self._queued_save_state
        self._queued_save_state = None
        if not self._saving or queued is None:
            return
        original_baseline, original_values, preferred_verse = queued
        latest = self._latest_stored_config()
        conflicts = self.draft.rebase(latest)
        if conflicts:
            names = "\n".join("• {}".format(conflict.label) for conflict in conflicts[:6])
            if len(conflicts) > 6:
                names += "\n• …and {} more".format(len(conflicts) - 6)
            self._show_prompt(
                "Settings changed elsewhere",
                "Some settings changed here and outside this editor. Choose which value to use for these conflicts:\n\n{}\n\nUntouched external changes were merged automatically.".format(names),
                [
                    (
                        "Reload latest",
                        "secondary",
                        lambda: self._reload_after_conflict(latest),
                    ),
                    (
                        "Keep my changes",
                        "primary",
                        lambda: self._commit_save(
                            preferred_verse,
                            original_baseline,
                            original_values,
                        ),
                    ),
                    (
                        "Cancel",
                        "secondary",
                        lambda: self._cancel_conflict(original_baseline, original_values),
                    ),
                ],
                lambda: self._cancel_conflict(original_baseline, original_values),
            )
            return
        self._commit_save(
            preferred_verse,
            original_baseline,
            original_values,
        )

    def _reload_after_conflict(self, latest: Mapping[str, Any]) -> None:
        self._pending_close_after_save = False
        view_state = self._capture_transient_view_state()
        self.draft.replace_all(latest)
        self.staged = deepcopy(self.draft.values)
        self.quotes = list(self.staged["bible"]["quotes"])
        self._staged_deleted_quotes.clear()
        self._clear_undo_state()
        self._clear_event_feedback()
        self._saved_current_quote = self._read_current_quote(self.staged)
        self._apply_config_to_widgets(self.staged)
        self._update_dependencies()
        self._apply_theme()
        self._restore_transient_view_state(view_state)
        self._finish_saving()

    def _cancel_conflict(
        self,
        original_baseline: Mapping[str, Any],
        original_values: Mapping[str, Any],
    ) -> None:
        self._pending_close_after_save = False
        self.draft.baseline = deepcopy(dict(original_baseline))
        self.draft.values = deepcopy(dict(original_values))
        self.staged = deepcopy(self.draft.values)
        self._finish_saving()

    def _finish_saving(self) -> None:
        self._save_dispatch_timer.stop()
        self._queued_save_state = None
        self._saving = False
        self._set_mutation_controls_enabled(True)
        self._update_dependencies()
        self._update_quote_actions()
        self._update_event_actions()
        if self.save_button is not None:
            self.save_button.setText("Save changes")
        if self.close_button is not None:
            self.close_button.setEnabled(True)
        self.save_shortcut.setEnabled(True)
        self.close_shortcut.setEnabled(True)
        self.escape_shortcut.setEnabled(True)
        self._update_dirty_state()

    def _set_mutation_controls_enabled(self, enabled: bool) -> None:
        control_types = (
            QPushButton,
            QLineEdit,
            QComboBox,
            QDateEdit,
            QSlider,
            QCheckBox,
            QPlainTextEdit,
            QListView,
            QTreeWidget,
        )
        if not enabled:
            self._mutation_enabled_states.clear()
            mutation_controls: List[QWidget] = []
            for widget in self.settings_shell.findChildren(QWidget):
                if not isinstance(widget, control_types):
                    continue
                if widget in {
                    self.nav,
                    self.active_events,
                    self.archived_events,
                    self.quote_list,
                }:
                    continue
                mutation_controls.append(widget)
            # Capture every effective state before disabling any parent. Qt
            # combo boxes own popup list views beneath the combo itself; a
            # one-pass snapshot observes those views as disabled immediately
            # after their parent is locked and leaves the popup unusable when
            # saving finishes.
            self._mutation_enabled_states.update(
                (widget, widget.isEnabled()) for widget in mutation_controls
            )
            for widget in mutation_controls:
                widget.setEnabled(False)
            return
        for widget, was_enabled in list(self._mutation_enabled_states.items()):
            try:
                widget.setEnabled(was_enabled)
            except RuntimeError:
                pass
        self._mutation_enabled_states.clear()

    def _commit_save(
        self,
        preferred_verse: Optional[str],
        failure_baseline: Optional[Mapping[str, Any]] = None,
        failure_values: Optional[Mapping[str, Any]] = None,
    ) -> None:
        try:
            self.controller.save_config(
                self.draft.values,
                preferred_verse=preferred_verse,
            )
        except Exception as exc:
            if failure_baseline is not None and failure_values is not None:
                self.draft.baseline = deepcopy(dict(failure_baseline))
                self.draft.values = deepcopy(dict(failure_values))
                self.staged = deepcopy(self.draft.values)
                self.quotes = list(self.staged["bible"]["quotes"])
            detail = str(exc).strip() or "The configuration could not be written."
            self._last_save_error = (
                "Could not save changes. Your draft is still available."
            )
            self._last_save_error_detail = detail
            self._pending_close_after_save = False
            self._finish_saving()
            return
        self.pending_manual_quote = None
        self._pending_manual_quote_index = None
        self._last_save_error = ""
        self._last_save_error_detail = ""
        view_state = self._capture_transient_view_state()
        latest_saved = getattr(self.controller, "config", self.draft.values)
        self.draft.replace_all(latest_saved)
        self.staged = deepcopy(self.draft.values)
        self._staged_deleted_quotes.clear()
        self._clear_undo_state()
        self._saved_current_quote = self._read_current_quote(self.staged)
        self._apply_config_to_widgets(self.staged)
        self._update_dependencies()
        self._apply_theme()
        self._restore_transient_view_state(view_state)
        close_after_save = self._pending_close_after_save
        self._pending_close_after_save = False
        self._finish_saving()
        self.footer.set_error()
        if close_after_save:
            self._close_dialog()
            return
        self._set_status("saved", "Saved")
        self.saved_status_timer.start()

    def _has_unsaved_changes(self) -> bool:
        self._sync_draft()
        return bool(
            self.draft.dirty
            or (
                self.pending_manual_quote is not None
                and self.pending_manual_quote != self._saved_current_quote
            )
            or self._font_color_invalid
            or not self._number_fields_are_valid()
        )

    def _show_prompt(
        self,
        title: str,
        message: str,
        actions: List[tuple[str, str, Callable[[], None]]],
        dismiss: Callable[[], None],
    ) -> None:
        if self._active_prompt is not None:
            return
        focus = QApplication.focusWidget()
        self._focus_before_prompt = focus if isinstance(focus, QWidget) else None
        self.save_shortcut.setEnabled(False)
        self.close_shortcut.setEnabled(False)
        self.escape_shortcut.setEnabled(False)
        prompt = SettingsPromptPage(
            self._content_stack,
            self,
            title,
            message,
            actions,
            dismiss,
        )
        _apply_role_fonts(prompt)
        _apply_control_targets(prompt)
        self._active_prompt = prompt
        self._content_stack.addWidget(prompt)
        self._content_stack.setCurrentWidget(prompt)
        prompt.focus_default_action()

    def _show_save_error_details(self) -> None:
        details = self.footer.details_text.text().strip()
        if not details:
            return
        self._show_prompt(
            "Save error details",
            details,
            [("Close", "primary", lambda: None)],
            lambda: None,
        )

    def _finish_prompt(
        self,
        prompt: SettingsPromptPage,
        callback: Optional[Callable[[], None]],
    ) -> None:
        if self._active_prompt is not prompt:
            return
        self._active_prompt = None
        self._content_stack.setCurrentWidget(self.settings_shell)
        self._content_stack.removeWidget(prompt)
        prompt.deleteLater()
        self.close_shortcut.setEnabled(not self._saving)
        self.escape_shortcut.setEnabled(not self._saving)
        previous_focus = self._focus_before_prompt
        self._focus_before_prompt = None
        if previous_focus is not None:
            try:
                if previous_focus.isVisible() and previous_focus.isEnabled():
                    previous_focus.setFocus(Qt.FocusReason.OtherFocusReason)
            except RuntimeError:
                pass
        if not self._saving:
            self._update_dirty_state()
        if callback is not None:
            callback()

    def request_close(self) -> None:
        if self._saving or self._active_prompt is not None:
            return
        if not self._has_unsaved_changes():
            self._close_dialog()
            return
        self._show_prompt(
            "Unsaved changes",
            "Save your changes before closing?",
            [
                ("Cancel", "secondary", lambda: None),
                ("Discard", "danger", self._close_dialog),
                ("Save and close", "primary", self._save_and_close),
            ],
            lambda: None,
        )

    def _save_and_close(self) -> None:
        if self._saving:
            return
        self._sync_draft()
        if self._font_color_invalid or not self._number_fields_are_valid():
            self._pending_close_after_save = False
            self._update_dirty_state()
            return
        manual_quote_dirty = (
            self.pending_manual_quote is not None
            and self.pending_manual_quote != self._saved_current_quote
        )
        if not self.draft.dirty and not manual_quote_dirty:
            self._pending_close_after_save = False
            self._close_dialog()
            return
        self._pending_close_after_save = True
        self._save()

    def _close_dialog(self) -> None:
        self._persist_window_geometry()
        self._allow_close = True
        super().reject()

    def reject(self) -> None:
        if self._allow_close:
            super().reject()
            return
        self.request_close()

    def closeEvent(self, event: Any) -> None:
        if self._allow_close:
            self._persist_window_geometry()
            super().closeEvent(event)
            return
        event.ignore()
        self.request_close()

    def force_close(self) -> None:
        if self._active_prompt is not None:
            self._active_prompt.dismiss_without_callback()
            self._active_prompt = None
        self._saving = False
        self._close_dialog()


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
    existing = getattr(mw, "_home_dashboard_overhaul_settings_action", None)
    if existing is not None: return
    for action in _actions(submenu):
        text = action.text() if callable(getattr(action, "text", None)) else ""
        if text == ACTION_TEXT:
            mw._home_dashboard_overhaul_settings_action = action
            return
    action = QAction(ACTION_TEXT, mw)
    action.triggered.connect(controller.open_settings)
    submenu.addAction(action)
    mw._home_dashboard_overhaul_settings_action = action
