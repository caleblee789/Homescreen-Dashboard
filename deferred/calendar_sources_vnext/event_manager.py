"""Dedicated, immediate-save manager for local events and calendar sources."""

from __future__ import annotations

from dataclasses import asdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence

from aqt import mw
from aqt.qt import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDate,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTabWidget,
    QTimer,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
    Qt,
)

from .calendar_repository import CalendarRepositoryError, RefreshResult
from .calendar_manager_model import (
    CalendarManagerRangeError,
    eligible_for_action,
    filter_occurrences,
    manager_date_range,
)
from .models import CalendarOccurrence
from .settings import (
    EventEditDialog,
    _install_palette_watcher,
    _is_palette_change,
    _palette_tokens,
    _queue_palette_style,
)


def _manager_style() -> str:
    values = _palette_tokens()
    return """
QDialog#HomeDashboardEventManager {{ background: {window}; color: {text}; }}
QDialog#HomeDashboardEventManager QLabel,
QDialog#HomeDashboardEventManager QCheckBox {{ color: {text}; }}
QDialog#HomeDashboardEventManager QLabel#ManagerTitle {{ font-size: 21px; font-weight: 750; color: {text}; }}
QDialog#HomeDashboardEventManager QLabel#ManagerSectionTitle {{ font-size: 13px; font-weight: 700; color: {text}; }}
QDialog#HomeDashboardEventManager QLabel#ManagerFieldName {{ color: {muted}; font-weight: 650; }}
QDialog#HomeDashboardEventManager QLabel#ManagerHelp,
QDialog#HomeDashboardEventManager QLabel#ManagerStatus {{ color: {muted}; }}
QDialog#HomeDashboardEventManager QWidget#ManagerDetail {{ background: {alternate}; border: 1px solid {border}; border-radius: 9px; }}
QDialog#HomeDashboardEventManager QLineEdit,
QDialog#HomeDashboardEventManager QComboBox,
QDialog#HomeDashboardEventManager QDateEdit,
QDialog#HomeDashboardEventManager QTreeWidget {{ background: {base}; border: 1px solid {border}; border-radius: 7px; color: {text}; padding: 3px; }}
QDialog#HomeDashboardEventManager QLineEdit:focus,
QDialog#HomeDashboardEventManager QComboBox:focus,
QDialog#HomeDashboardEventManager QDateEdit:focus,
QDialog#HomeDashboardEventManager QTreeWidget:focus {{ border: 2px solid {highlight}; }}
QDialog#HomeDashboardEventManager QTreeWidget::item {{ color: {text}; }}
QDialog#HomeDashboardEventManager QTreeWidget::item:selected {{ background: {highlight}; color: {highlight_text}; }}
QDialog#HomeDashboardEventManager QPushButton {{ background: {button}; border: 1px solid {border}; border-radius: 7px; color: {button_text}; min-height: 29px; padding: 4px 10px; }}
QDialog#HomeDashboardEventManager QPushButton:hover {{ border-color: {highlight}; background: {alternate}; }}
QDialog#HomeDashboardEventManager QPushButton:focus {{ border: 2px solid {highlight}; }}
QDialog#HomeDashboardEventManager QPushButton#DangerButton {{ background: {danger_bg}; border-color: {danger}; color: {danger}; font-weight: 650; }}
QDialog#HomeDashboardEventManager QPushButton:disabled {{ background: {alternate}; color: {disabled}; border-color: {border}; }}
QDialog#HomeDashboardEventManager QTabWidget::pane {{ border: 1px solid {border}; border-radius: 8px; background: {window}; }}
QDialog#HomeDashboardEventManager QTabBar::tab {{ background: {alternate}; color: {text}; border: 1px solid {border}; padding: 7px 14px; }}
QDialog#HomeDashboardEventManager QTabBar::tab:selected {{ background: {highlight}; color: {highlight_text}; font-weight: 700; }}
QDialog#HomeDashboardEventManager QTabBar::tab:focus {{ border: 2px solid {highlight}; }}
""".format(**values)


def _plain_label(value: str = "") -> QLabel:
    label = QLabel(value)
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setWordWrap(True)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    return label


def _qdate(value: date) -> QDate:
    return QDate(value.year, value.month, value.day)


def _date_value(value: QDate) -> date:
    return date.fromisoformat(value.toString("yyyy-MM-dd"))


class CalendarSubscriptionDialog(QDialog):
    """Collect a private URL without retaining or redisplaying an old value."""

    def __init__(self, parent: QWidget, *, replacing: bool = False) -> None:
        super().__init__(parent)
        self.setObjectName("HomeDashboardEventManager")
        self.setStyleSheet(_manager_style())
        self.setWindowTitle("Replace calendar link" if replacing else "Subscribe to calendar")
        self.setMinimumWidth(600)
        layout = QVBoxLayout(self)
        heading = QLabel("Paste a new private iCalendar link" if replacing else "Subscribe to an iCalendar link")
        heading.setObjectName("ManagerTitle")
        layout.addWidget(heading)
        help_label = _plain_label(
            "Use an HTTPS or webcal link, including Google Calendar’s Secret address in iCal format. "
            "The link is stored locally, never shown again, and grants read-only access to anyone who has it."
        )
        help_label.setObjectName("ManagerHelp")
        layout.addWidget(help_label)
        form = QFormLayout()
        self.url = QLineEdit()
        self.url.setAccessibleName("Private iCalendar URL")
        self.url.setPlaceholderText("Paste private HTTPS or webcal link")
        self.url.setEchoMode(QLineEdit.EchoMode.Password)
        self.name = QLineEdit()
        self.name.setMaxLength(120)
        self.name.setPlaceholderText("Optional; feed name is used when available")
        form.addRow("Private link", self.url)
        if not replacing:
            form.addRow("Calendar name", self.name)
        layout.addLayout(form)
        show = QCheckBox("Show pasted link while editing")
        show.toggled.connect(
            lambda checked: self.url.setEchoMode(
                QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
            )
        )
        layout.addWidget(show)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _accept_if_valid(self) -> None:
        if not self.url.text().strip():
            QMessageBox.warning(self, "Calendar link required", "Paste an HTTPS or webcal iCalendar link.")
            return
        self.accept()

    def values(self) -> tuple[str, str]:
        return self.url.text().strip(), self.name.text().strip()


class EventManagerDialog(QDialog):
    """Singleton UI; the controller owns its lifetime and background work."""

    def __init__(self, controller: Any, selected_date: str = "") -> None:
        super().__init__(mw)
        self.controller = controller
        self.repository = controller.calendar_repository
        self._occurrences: List[CalendarOccurrence] = []
        self._query_generation = 0
        self._post_query_status = ""
        self._selected_date = selected_date
        self._source_rows: Dict[str, Dict[str, Any]] = {}
        self.setObjectName("HomeDashboardEventManager")
        self.setWindowTitle("Event Manager — Home Dashboard")
        self.setMinimumSize(760, 560)
        self.resize(1180, 760)
        self.setSizeGripEnabled(True)
        self.setStyleSheet(_manager_style())

        outer = QVBoxLayout(self)
        title = QLabel("Event Manager")
        title.setObjectName("ManagerTitle")
        subtitle = _plain_label(
            "Manage local events and private read-only calendar sources. Every action is saved immediately."
        )
        subtitle.setObjectName("ManagerHelp")
        outer.addWidget(title)
        outer.addWidget(subtitle)

        self.tabs = QTabWidget()
        self.tabs.setAccessibleName("Event Manager sections")
        self.events_page = self._build_events_page()
        self.calendars_page = self._build_calendars_page()
        self.tabs.addTab(self.events_page, "Events")
        self.tabs.addTab(self.calendars_page, "Calendars")
        outer.addWidget(self.tabs, 1)

        footer = QHBoxLayout()
        self.status = _plain_label("Ready")
        self.status.setObjectName("ManagerStatus")
        self.status.setAccessibleName("Event Manager status")
        footer.addWidget(self.status, 1)
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        footer.addWidget(close)
        outer.addLayout(footer)

        self.query_timer = QTimer(self)
        self.query_timer.setSingleShot(True)
        self.query_timer.setInterval(120)
        self.query_timer.timeout.connect(self._query_events)
        self._refresh_sources()
        if selected_date:
            self.open_for_date(selected_date)
        else:
            self._set_preset("upcoming")
            self._schedule_query()
        _install_palette_watcher(self, _manager_style)

    def changeEvent(self, event: Any) -> None:
        if _is_palette_change(event):
            _queue_palette_style(self, _manager_style)
        super().changeEvent(event)

    def resizeEvent(self, event: Any) -> None:
        if hasattr(self, "events_splitter"):
            orientation = Qt.Orientation.Vertical if self.width() < 980 else Qt.Orientation.Horizontal
            if self.events_splitter.orientation() != orientation:
                self.events_splitter.setOrientation(orientation)
            compact = orientation == Qt.Orientation.Vertical
            self._layout_event_detail(compact)
            if compact:
                self.events_splitter.setSizes([110, 66])
            else:
                self.events_splitter.setSizes([700, 320])
        super().resizeEvent(event)

    def _layout_event_detail(self, compact: bool) -> None:
        """Keep every detail field visible when the manager reaches 760x560."""

        if not hasattr(self, "event_detail_layout") or self._detail_is_compact == compact:
            return
        self._detail_is_compact = compact
        widgets = (
            self.detail_title,
            self.detail_event_caption,
            self.detail_name,
            self.detail_date_caption,
            self.detail_date,
            self.detail_source_caption,
            self.detail_source,
            self.detail_status_caption,
            self.detail_status,
            self.read_only_note,
        )
        for widget in widgets:
            self.event_detail_layout.removeWidget(widget)

        if compact:
            self.detail_event_caption.hide()
            self.read_only_note.hide()
            self.event_detail_layout.setContentsMargins(8, 5, 8, 5)
            self.event_detail_layout.setHorizontalSpacing(7)
            self.event_detail_layout.setVerticalSpacing(2)
            self.event_detail_layout.addWidget(self.detail_title, 0, 0)
            self.event_detail_layout.addWidget(self.detail_name, 0, 1)
            self.event_detail_layout.addWidget(self.detail_date_caption, 0, 2)
            self.event_detail_layout.addWidget(self.detail_date, 0, 3)
            self.event_detail_layout.addWidget(self.detail_source_caption, 1, 0)
            self.event_detail_layout.addWidget(self.detail_source, 1, 1)
            self.event_detail_layout.addWidget(self.detail_status_caption, 1, 2)
            self.event_detail_layout.addWidget(self.detail_status, 1, 3)
            for value in (self.detail_name, self.detail_date, self.detail_source, self.detail_status):
                value.setWordWrap(False)
            self.event_detail.setMinimumWidth(0)
            self.event_detail.setMinimumHeight(58)
            self.event_detail.setMaximumHeight(72)
            self.event_detail_layout.setColumnStretch(1, 3)
            self.event_detail_layout.setColumnStretch(3, 2)
        else:
            self.detail_event_caption.show()
            self.read_only_note.show()
            self.event_detail_layout.setContentsMargins(10, 10, 10, 10)
            self.event_detail_layout.setHorizontalSpacing(8)
            self.event_detail_layout.setVerticalSpacing(5)
            self.event_detail_layout.addWidget(self.detail_title, 0, 0, 1, 2)
            self.event_detail_layout.addWidget(self.detail_event_caption, 1, 0)
            self.event_detail_layout.addWidget(self.detail_name, 1, 1)
            self.event_detail_layout.addWidget(self.detail_date_caption, 2, 0)
            self.event_detail_layout.addWidget(self.detail_date, 2, 1)
            self.event_detail_layout.addWidget(self.detail_source_caption, 3, 0)
            self.event_detail_layout.addWidget(self.detail_source, 3, 1)
            self.event_detail_layout.addWidget(self.detail_status_caption, 4, 0)
            self.event_detail_layout.addWidget(self.detail_status, 4, 1)
            self.event_detail_layout.addWidget(self.read_only_note, 5, 0, 1, 2)
            for value in (self.detail_name, self.detail_date, self.detail_source, self.detail_status):
                value.setWordWrap(True)
            self.event_detail.setMinimumWidth(260)
            self.event_detail.setMinimumHeight(0)
            self.event_detail.setMaximumHeight(16777215)
            self.event_detail_layout.setColumnStretch(1, 1)
            self.event_detail_layout.setColumnStretch(3, 0)

    def _build_events_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)
        filters = QGridLayout()
        self.event_search = QLineEdit()
        self.event_search.setPlaceholderText("Search event names, dates, or calendars…")
        self.event_search.setAccessibleName("Search events")
        self.source_filter = QComboBox()
        self.source_filter.setAccessibleName("Filter events by calendar")
        self.range_preset = QComboBox()
        for label, value in (
            ("Upcoming 12 months", "upcoming"),
            ("This month", "month"),
            ("This year", "year"),
            ("Past 12 months", "past"),
            ("Custom range", "custom"),
        ):
            self.range_preset.addItem(label, value)
        self.range_preset.setAccessibleName("Event date range")
        self.custom_start = QDateEdit()
        self.custom_end = QDateEdit()
        for editor, accessible in (
            (self.custom_start, "Custom range start date"),
            (self.custom_end, "Custom range end date"),
        ):
            editor.setCalendarPopup(True)
            editor.setDisplayFormat("MMM d, yyyy")
            editor.setAccessibleName(accessible)
        self.custom_start.setDate(QDate.currentDate())
        self.custom_end.setDate(QDate.currentDate().addYears(1).addDays(-1))
        filters.addWidget(QLabel("Search"), 0, 0)
        filters.addWidget(self.event_search, 0, 1)
        filters.addWidget(QLabel("Calendar"), 0, 2)
        filters.addWidget(self.source_filter, 0, 3)
        filters.addWidget(QLabel("Date range"), 1, 0)
        filters.addWidget(self.range_preset, 1, 1)
        filters.addWidget(self.custom_start, 1, 2)
        filters.addWidget(self.custom_end, 1, 3)
        filters.setColumnStretch(1, 1)
        filters.setColumnStretch(3, 1)
        layout.addLayout(filters)

        self.event_views = QTabWidget()
        self.event_views.setAccessibleName("Event status view")
        for label in ("Upcoming", "Past & Archived", "Hidden"):
            placeholder = QWidget()
            placeholder.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
            self.event_views.addTab(placeholder, label)
        self.event_views.setMaximumHeight(42)
        layout.addWidget(self.event_views)

        self.events_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.events_splitter.setChildrenCollapsible(False)
        self.event_tree = QTreeWidget()
        self.event_tree.setAccessibleName("Filtered calendar events")
        self.event_tree.setHeaderLabels(["Date", "Event", "Calendar", "Status"])
        self.event_tree.setRootIsDecorated(False)
        self.event_tree.setAlternatingRowColors(True)
        self.event_tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.event_tree.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.event_tree.setSortingEnabled(True)
        self.event_tree.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        self.event_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.event_tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.event_tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.event_tree.header().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.events_splitter.addWidget(self.event_tree)

        self.event_detail = QWidget()
        self.event_detail.setObjectName("ManagerDetail")
        self.event_detail_layout = QGridLayout(self.event_detail)
        self.detail_title = QLabel("Selected item")
        self.detail_title.setObjectName("ManagerSectionTitle")
        self.detail_event_caption = QLabel("Event")
        self.detail_date_caption = QLabel("Date")
        self.detail_source_caption = QLabel("Calendar")
        self.detail_status_caption = QLabel("Status")
        for caption in (
            self.detail_event_caption,
            self.detail_date_caption,
            self.detail_source_caption,
            self.detail_status_caption,
        ):
            caption.setObjectName("ManagerFieldName")
        self.detail_name = _plain_label("No event selected")
        self.detail_date = _plain_label("—")
        self.detail_source = _plain_label("—")
        self.detail_status = _plain_label("—")
        self.read_only_note = _plain_label("")
        self.read_only_note.setObjectName("ManagerHelp")
        self._detail_is_compact: Optional[bool] = None
        self._layout_event_detail(False)
        self.events_splitter.addWidget(self.event_detail)
        self.events_splitter.setStretchFactor(0, 3)
        self.events_splitter.setStretchFactor(1, 1)
        self.events_splitter.setSizes([760, 310])
        layout.addWidget(self.events_splitter, 1)

        actions = QGridLayout()
        self.add_event_button = QPushButton("Add local event")
        self.edit_event_button = QPushButton("Edit")
        self.duplicate_event_button = QPushButton("Duplicate")
        self.archive_event_button = QPushButton("Archive")
        self.hide_event_button = QPushButton("Hide")
        self.refresh_event_button = QPushButton("Refresh calendar")
        self.manage_calendar_button = QPushButton("Manage calendar")
        self.delete_event_button = QPushButton("Delete")
        self.delete_event_button.setObjectName("DangerButton")
        buttons = (
            self.add_event_button,
            self.edit_event_button,
            self.duplicate_event_button,
            self.archive_event_button,
            self.hide_event_button,
            self.refresh_event_button,
            self.manage_calendar_button,
            self.delete_event_button,
        )
        for index, button in enumerate(buttons):
            actions.addWidget(button, index // 4, index % 4)
        layout.addLayout(actions)

        self.event_search.textChanged.connect(self._apply_event_filters)
        self.source_filter.currentIndexChanged.connect(self._apply_event_filters)
        self.range_preset.currentIndexChanged.connect(self._range_changed)
        self.custom_start.dateChanged.connect(self._custom_range_changed)
        self.custom_end.dateChanged.connect(self._custom_range_changed)
        self.event_views.currentChanged.connect(self._event_view_changed)
        self.event_tree.itemSelectionChanged.connect(self._update_event_detail)
        self.event_tree.itemDoubleClicked.connect(lambda *_args: self._edit_local_event())
        self.add_event_button.clicked.connect(self._add_local_event)
        self.edit_event_button.clicked.connect(self._edit_local_event)
        self.duplicate_event_button.clicked.connect(self._duplicate_local_events)
        self.archive_event_button.clicked.connect(self._archive_or_restore_events)
        self.hide_event_button.clicked.connect(self._hide_or_unhide_events)
        self.refresh_event_button.clicked.connect(self._refresh_selected_calendars)
        self.manage_calendar_button.clicked.connect(self._manage_selected_calendar)
        self.delete_event_button.clicked.connect(self._delete_local_events)
        return page

    def _build_calendars_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)
        help_label = _plain_label(
            "Imported files are managed snapshots. URL subscriptions refresh at profile startup, every six hours, and on demand. "
            "Cached data and private links stay on this computer and do not sync through Anki."
        )
        help_label.setObjectName("ManagerHelp")
        layout.addWidget(help_label)
        self.calendar_tree = QTreeWidget()
        self.calendar_tree.setAccessibleName("Managed calendar sources")
        self.calendar_tree.setHeaderLabels(
            ["Calendar", "Source", "Enabled", "Last successful refresh", "Current error", "Events"]
        )
        self.calendar_tree.setRootIsDecorated(False)
        self.calendar_tree.setAlternatingRowColors(True)
        self.calendar_tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.calendar_tree.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.calendar_tree.setSortingEnabled(True)
        self.calendar_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in (1, 2, 3, 5):
            self.calendar_tree.header().setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        self.calendar_tree.header().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.calendar_tree, 1)
        self.calendar_detail = _plain_label("Select a calendar to see its safe, redacted source location.")
        self.calendar_detail.setObjectName("ManagerHelp")
        layout.addWidget(self.calendar_detail)
        actions = QGridLayout()
        self.import_button = QPushButton("Import .ics file")
        self.subscribe_button = QPushButton("Subscribe to link")
        self.refresh_source_button = QPushButton("Refresh")
        self.rename_source_button = QPushButton("Rename")
        self.replace_source_button = QPushButton("Replace file")
        self.enable_source_button = QPushButton("Disable")
        self.reset_hidden_button = QPushButton("Reset hidden events")
        self.remove_source_button = QPushButton("Remove")
        self.remove_source_button.setObjectName("DangerButton")
        calendar_buttons = (
            self.import_button,
            self.subscribe_button,
            self.refresh_source_button,
            self.rename_source_button,
            self.replace_source_button,
            self.enable_source_button,
            self.reset_hidden_button,
            self.remove_source_button,
        )
        for index, button in enumerate(calendar_buttons):
            actions.addWidget(button, index // 4, index % 4)
        layout.addLayout(actions)
        self.calendar_tree.itemSelectionChanged.connect(self._update_calendar_actions)
        self.import_button.clicked.connect(self._import_calendar)
        self.subscribe_button.clicked.connect(self._subscribe_calendar)
        self.refresh_source_button.clicked.connect(self._refresh_calendar_source)
        self.rename_source_button.clicked.connect(self._rename_calendar_source)
        self.replace_source_button.clicked.connect(self._replace_calendar_source)
        self.enable_source_button.clicked.connect(self._toggle_calendar_source)
        self.reset_hidden_button.clicked.connect(self._reset_hidden_events)
        self.remove_source_button.clicked.connect(self._remove_calendar_source)
        return page

    def open_for_date(self, raw_date: str) -> None:
        try:
            selected = date.fromisoformat(raw_date)
        except (TypeError, ValueError):
            return
        self.tabs.setCurrentIndex(0)
        self.event_views.setCurrentIndex(0 if selected >= date.today() else 1)
        self.custom_start.setDate(_qdate(selected))
        self.custom_end.setDate(_qdate(selected))
        self._set_preset("custom")
        self._selected_date = selected.isoformat()
        self._schedule_query()

    def show_calendars(self) -> None:
        self.tabs.setCurrentIndex(1)

    def on_repository_changed(self) -> None:
        self._refresh_sources()
        self._schedule_query()

    def _set_status(self, text: str, error: bool = False) -> None:
        self.status.setText(text)
        self.status.setAccessibleDescription(("Error: " if error else "Status: ") + text)
        if error:
            QApplication.alert(self)

    def _set_preset(self, value: str) -> None:
        index = self.range_preset.findData(value)
        if index >= 0:
            self.range_preset.setCurrentIndex(index)
        self._update_custom_visibility()

    def _update_custom_visibility(self) -> None:
        custom = self.range_preset.currentData() == "custom"
        self.custom_start.setVisible(custom)
        self.custom_end.setVisible(custom)

    def _range_changed(self, *_args: object) -> None:
        self._update_custom_visibility()
        self._schedule_query()

    def _custom_range_changed(self, *_args: object) -> None:
        if self.range_preset.currentData() == "custom":
            self._schedule_query()

    def _event_view_changed(self, index: int) -> None:
        current = self.range_preset.currentData()
        if index == 0 and current == "past":
            self._set_preset("upcoming")
        elif index == 1 and current == "upcoming":
            self._set_preset("past")
        self._apply_event_filters()

    def _date_range(self) -> tuple[date, date]:
        today = date.today()
        preset = str(self.range_preset.currentData() or "upcoming")
        return manager_date_range(
            preset,
            today,
            _date_value(self.custom_start.date()) if preset == "custom" else None,
            _date_value(self.custom_end.date()) if preset == "custom" else None,
        )

    def _schedule_query(self) -> None:
        if hasattr(self, "query_timer"):
            self.query_timer.start()

    def _query_events(self) -> None:
        self.controller.archive_expired_local_events()
        try:
            start, end = self._date_range()
        except (CalendarRepositoryError, CalendarManagerRangeError) as exc:
            self._occurrences = []
            self._apply_event_filters()
            self._set_status(str(exc), error=True)
            return
        self._query_generation += 1
        generation = self._query_generation
        self._set_status("Loading calendar events…")

        def operation() -> List[CalendarOccurrence]:
            return self.repository.occurrences_between(
                start,
                end,
                include_archived=True,
                include_hidden=True,
                include_disabled=True,
                cached_only=False,
            )

        def success(values: Sequence[CalendarOccurrence]) -> None:
            if generation != self._query_generation:
                return
            self._occurrences = list(values)
            self._apply_event_filters()
            message = self._post_query_status or "Loaded {} event occurrence{}".format(
                len(values), "" if len(values) == 1 else "s"
            )
            self._post_query_status = ""
            self._set_status(message)

        def failure(exc: Exception) -> None:
            if generation != self._query_generation:
                return
            self._occurrences = []
            self._apply_event_filters()
            self._set_status(str(exc), error=True)

        self.controller.run_calendar_task(operation, success, failure)

    def _refresh_sources(self, selected_id: str = "") -> None:
        previous = selected_id or self._selected_source_id()
        sources = self.repository.list_sources()
        self._source_rows = {str(source["id"]): source for source in sources}
        current_filter = self.source_filter.currentData() if hasattr(self, "source_filter") else ""
        if hasattr(self, "source_filter"):
            self.source_filter.blockSignals(True)
            self.source_filter.clear()
            self.source_filter.addItem("All calendars", "")
            self.source_filter.addItem("Local", "local")
            for source in sorted(sources, key=lambda value: str(value.get("name", "")).casefold()):
                self.source_filter.addItem(str(source.get("name", "Imported calendar")), str(source["id"]))
            index = self.source_filter.findData(current_filter)
            self.source_filter.setCurrentIndex(max(0, index))
            self.source_filter.blockSignals(False)
        if not hasattr(self, "calendar_tree"):
            return
        self.calendar_tree.setSortingEnabled(False)
        self.calendar_tree.clear()
        selected_item = None
        for source in sources:
            kind = "Imported .ics" if source.get("kind") == "ics_file" else "iCalendar URL"
            item = QTreeWidgetItem(
                [
                    str(source.get("name", "Imported calendar")),
                    kind,
                    "Yes" if source.get("enabled", True) else "No",
                    str(source.get("last_success_at") or "Never"),
                    str(source.get("last_error") or ""),
                    str(source.get("event_count", 0)),
                ]
            )
            item.setData(0, Qt.ItemDataRole.UserRole, str(source["id"]))
            item.setToolTip(4, str(source.get("last_error") or "No current error"))
            self.calendar_tree.addTopLevelItem(item)
            if str(source["id"]) == previous:
                selected_item = item
        self.calendar_tree.setSortingEnabled(True)
        self.calendar_tree.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        if selected_item is not None:
            self.calendar_tree.setCurrentItem(selected_item)
        elif self.calendar_tree.topLevelItemCount():
            self.calendar_tree.setCurrentItem(self.calendar_tree.topLevelItem(0))
        self._update_calendar_actions()

    def _source_status(self, occurrence: CalendarOccurrence) -> str:
        if occurrence.source_id == "local":
            return "Archived" if occurrence.archived else "Active"
        source = self._source_rows.get(occurrence.source_id, {})
        if occurrence.hidden:
            return "Hidden"
        if not source.get("enabled", True):
            return "Disabled"
        if source.get("last_error"):
            return "Read-only · stale"
        return "Read-only"

    def _apply_event_filters(self, *_args: object) -> None:
        if not hasattr(self, "event_tree"):
            return
        source_filter = str(self.source_filter.currentData() or "")
        view = self.event_views.currentIndex()
        visible_values = filter_occurrences(
            self._occurrences,
            view=("upcoming", "past", "hidden")[view],
            today=date.today(),
            source_id=source_filter,
            search=self.event_search.text(),
        )
        selected_id = self._selected_occurrences()[0].occurrence_id if len(self._selected_occurrences()) == 1 else ""
        self.event_tree.setSortingEnabled(False)
        self.event_tree.clear()
        selected_item = None
        visible = 0
        for occurrence in visible_values:
            display_date = occurrence.start_date
            if occurrence.end_date_exclusive != (date.fromisoformat(occurrence.start_date) + timedelta(days=1)).isoformat():
                display_date += " → " + (date.fromisoformat(occurrence.end_date_exclusive) - timedelta(days=1)).isoformat()
            item = QTreeWidgetItem(
                [display_date, occurrence.name, occurrence.source_name, self._source_status(occurrence)]
            )
            item.setData(0, Qt.ItemDataRole.UserRole, occurrence)
            item.setToolTip(1, occurrence.name)
            item.setToolTip(2, occurrence.source_name)
            self.event_tree.addTopLevelItem(item)
            visible += 1
            if occurrence.occurrence_id == selected_id:
                selected_item = item
        self.event_tree.setSortingEnabled(True)
        self.event_tree.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        if selected_item is not None:
            self.event_tree.setCurrentItem(selected_item)
        self.event_views.setTabText(view, ("Upcoming", "Past & Archived", "Hidden")[view] + " ({})".format(visible))
        self._update_event_detail()

    def _selected_occurrences(self) -> List[CalendarOccurrence]:
        if not hasattr(self, "event_tree"):
            return []
        result = []
        for item in self.event_tree.selectedItems():
            value = item.data(0, Qt.ItemDataRole.UserRole)
            if isinstance(value, CalendarOccurrence):
                result.append(value)
        return result

    def _update_event_detail(self) -> None:
        values = self._selected_occurrences()
        local, _local_skipped = eligible_for_action(values, "archive")
        external, _external_skipped = eligible_for_action(values, "hide")
        if not values:
            self.detail_name.setText("No event selected")
            self.detail_date.setText("—")
            self.detail_source.setText("—")
            self.detail_status.setText("—")
            self.read_only_note.setText("")
        elif len(values) > 1:
            self.detail_name.setText("{} events selected".format(len(values)))
            self.detail_date.setText("Multiple dates")
            self.detail_source.setText("{} local · {} external".format(len(local), len(external)))
            self.detail_status.setText("Eligible actions affect matching items only")
            self.read_only_note.setText("Bulk results report both affected and skipped selections.")
        else:
            value = values[0]
            self.detail_name.setText(value.name)
            end = date.fromisoformat(value.end_date_exclusive) - timedelta(days=1)
            self.detail_date.setText(value.start_date if end.isoformat() == value.start_date else "{} through {}".format(value.start_date, end.isoformat()))
            self.detail_source.setText(value.source_name)
            self.detail_status.setText(self._source_status(value))
            self.read_only_note.setText(
                "External calendar events are read-only. Hide this occurrence or manage its calendar source."
                if external
                else "Local event changes are saved immediately."
            )
        self.detail_name.setToolTip(self.detail_name.text())
        self.detail_date.setToolTip(self.detail_date.text())
        self.detail_source.setToolTip(self.detail_source.text())
        self.detail_status.setToolTip(
            " · ".join(part for part in (self.detail_status.text(), self.read_only_note.text()) if part)
        )
        editable, _skipped = eligible_for_action(values, "edit")
        manageable, _skipped = eligible_for_action(values, "manage")
        self.edit_event_button.setEnabled(len(editable) == 1)
        self.duplicate_event_button.setEnabled(bool(local))
        self.archive_event_button.setEnabled(bool(local))
        self.delete_event_button.setEnabled(bool(local))
        self.hide_event_button.setEnabled(bool(external))
        self.refresh_event_button.setEnabled(bool(external))
        self.manage_calendar_button.setEnabled(len(manageable) == 1)
        self.archive_event_button.setText("Restore" if local and all(value.archived for value in local) else "Archive")
        self.hide_event_button.setText("Unhide" if external and all(value.hidden for value in external) else "Hide")

    def _report_bulk(self, action: str, affected: int, selected: int) -> None:
        skipped = max(0, selected - affected)
        message = "{}: {} affected, {} skipped".format(action, affected, skipped)
        self._post_query_status = message
        self._set_status(message)

    def _after_mutation(self, message: str = "Changes saved") -> None:
        self._post_query_status = message
        self.controller.calendar_data_changed()
        self._refresh_sources()
        self._schedule_query()
        self._set_status(message)

    def _add_local_event(self) -> None:
        dialog = EventEditDialog(self, initial_date=self._selected_date)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        name, event_date = dialog.values()
        self.repository.add_local(name, event_date)
        self._selected_date = event_date
        self._after_mutation("Local event added and saved")

    def _edit_local_event(self) -> None:
        values = self._selected_occurrences()
        eligible, _skipped = eligible_for_action(values, "edit")
        if len(eligible) != 1:
            return
        value = eligible[0]
        dialog = EventEditDialog(self, asdict(value) | {"id": value.occurrence_id, "date": value.start_date})
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        name, event_date = dialog.values()
        self.repository.edit_local(value.occurrence_id, name, event_date)
        self._after_mutation("Local event updated and saved")

    def _duplicate_local_events(self) -> None:
        values = self._selected_occurrences()
        eligible, _skipped = eligible_for_action(values, "duplicate")
        affected = sum(
            1
            for value in eligible
            if self.repository.duplicate_local(value.occurrence_id)
        )
        self._after_mutation()
        self._report_bulk("Duplicate", affected, len(values))

    def _archive_or_restore_events(self) -> None:
        values = self._selected_occurrences()
        local, _skipped = eligible_for_action(values, "archive")
        archived = not (local and all(value.archived for value in local))
        affected = self.repository.set_local_archived(
            [value.occurrence_id for value in local], archived
        )
        self._after_mutation()
        self._report_bulk("Restore" if not archived else "Archive", affected, len(values))

    def _delete_local_events(self) -> None:
        values = self._selected_occurrences()
        local, _skipped = eligible_for_action(values, "delete")
        if not local:
            return
        if QMessageBox.question(
            self,
            "Delete local events?",
            "Delete {} local event{}? This cannot be undone. External selections will be skipped.".format(
                len(local), "" if len(local) == 1 else "s"
            ),
        ) != QMessageBox.StandardButton.Yes:
            return
        affected = self.repository.delete_local([value.occurrence_id for value in local])
        self._after_mutation()
        self._report_bulk("Delete", affected, len(values))

    def _hide_or_unhide_events(self) -> None:
        values = self._selected_occurrences()
        external, _skipped = eligible_for_action(values, "hide")
        hidden = not (external and all(value.hidden for value in external))
        affected = sum(1 for value in external if self.repository.set_hidden(value, hidden))
        self._after_mutation()
        self._report_bulk("Unhide" if not hidden else "Hide", affected, len(values))

    def _refresh_selected_calendars(self) -> None:
        values = self._selected_occurrences()
        external, _skipped = eligible_for_action(values, "refresh")
        source_ids = sorted({value.source_id for value in external})
        selected = len(values)
        if not source_ids:
            return
        self._set_status("Refreshing selected calendars…")

        def operation() -> List[RefreshResult]:
            return [self.repository.refresh_source(source_id) for source_id in source_ids]

        def success(results: Sequence[RefreshResult]) -> None:
            affected = sum(1 for result in results if result.success)
            errors = [result.message for result in results if not result.success]
            self._after_mutation()
            self._report_bulk("Refresh", affected, selected)
            if errors:
                self._set_status("; ".join(errors), error=True)

        self.controller.run_calendar_task(operation, success, self._task_failure)

    def _manage_selected_calendar(self) -> None:
        values = self._selected_occurrences()
        eligible, _skipped = eligible_for_action(values, "manage")
        if len(eligible) != 1:
            return
        source_id = eligible[0].source_id
        self.tabs.setCurrentIndex(1)
        self._refresh_sources(source_id)

    def _selected_source_id(self) -> str:
        if not hasattr(self, "calendar_tree"):
            return ""
        item = self.calendar_tree.currentItem()
        return str(item.data(0, Qt.ItemDataRole.UserRole) or "") if item else ""

    def _selected_source(self) -> Optional[Dict[str, Any]]:
        return self.repository.source(self._selected_source_id())

    def _update_calendar_actions(self) -> None:
        source = self._selected_source()
        selected = source is not None
        for button in (
            self.refresh_source_button,
            self.rename_source_button,
            self.replace_source_button,
            self.enable_source_button,
            self.reset_hidden_button,
            self.remove_source_button,
        ):
            button.setEnabled(selected)
        if not source:
            self.calendar_detail.setText("Select a calendar to see its safe, redacted source location.")
            return
        self.replace_source_button.setText(
            "Replace file" if source.get("kind") == "ics_file" else "Replace link"
        )
        self.refresh_source_button.setEnabled(source.get("kind") == "ics_url")
        self.enable_source_button.setText("Disable" if source.get("enabled", True) else "Enable")
        detail = "{} · {} · {} cached occurrences".format(
            source.get("display_location", "Private calendar source"),
            "Enabled" if source.get("enabled", True) else "Disabled",
            source.get("occurrence_count", 0),
        )
        if source.get("last_error"):
            detail += " · Stale cache retained: " + str(source["last_error"])
        self.calendar_detail.setText(detail)

    def _run_source_task(
        self,
        status: str,
        operation: Callable[[], Any],
        success_message: str,
        selected_id: str = "",
    ) -> None:
        self._set_status(status)

        def success(_value: Any) -> None:
            self._post_query_status = success_message
            self.controller.calendar_data_changed()
            self._refresh_sources(selected_id)
            self._schedule_query()
            self._set_status(success_message)

        self.controller.run_calendar_task(operation, success, self._task_failure)

    def _task_failure(self, exc: Exception) -> None:
        self._refresh_sources()
        self._set_status(str(exc), error=True)

    def _import_calendar(self) -> None:
        path, _filter = QFileDialog.getOpenFileName(
            self, "Import iCalendar snapshot", "", "iCalendar files (*.ics);;All files (*)"
        )
        if not path:
            return
        self._run_source_task(
            "Importing and validating calendar…",
            lambda: self.repository.import_file(Path(path)),
            "Calendar snapshot imported",
        )

    def _subscribe_calendar(self) -> None:
        dialog = CalendarSubscriptionDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        url, name = dialog.values()
        self._run_source_task(
            "Downloading and validating private calendar…",
            lambda: self.repository.subscribe_url(url, name),
            "Calendar subscription added",
        )
        dialog.url.clear()

    def _refresh_calendar_source(self) -> None:
        source_id = self._selected_source_id()
        if not source_id:
            return

        def operation() -> RefreshResult:
            result = self.repository.refresh_source(source_id)
            if not result.success:
                raise CalendarRepositoryError(result.message)
            return result

        self._run_source_task(
            "Refreshing calendar…", operation, "Calendar refreshed", source_id
        )

    def _rename_calendar_source(self) -> None:
        source = self._selected_source()
        if not source:
            return
        name, accepted = QInputDialog.getText(
            self, "Rename calendar", "Calendar name", text=str(source.get("name", ""))
        )
        if not accepted or not name.strip():
            return
        self.repository.rename_source(str(source["id"]), name)
        self._after_mutation("Calendar renamed")
        self._refresh_sources(str(source["id"]))

    def _replace_calendar_source(self) -> None:
        source = self._selected_source()
        if not source:
            return
        source_id = str(source["id"])
        if source.get("kind") == "ics_file":
            path, _filter = QFileDialog.getOpenFileName(
                self, "Replace iCalendar snapshot", "", "iCalendar files (*.ics);;All files (*)"
            )
            if not path:
                return
            operation = lambda: self.repository.refresh_source(
                source_id, replacement_file=Path(path)
            )
        else:
            dialog = CalendarSubscriptionDialog(self, replacing=True)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            url, _name = dialog.values()
            operation = lambda: self.repository.refresh_source(source_id, replacement_url=url)
            dialog.url.clear()

        def checked_operation() -> RefreshResult:
            result = operation()
            if not result.success:
                raise CalendarRepositoryError(result.message)
            return result

        self._run_source_task(
            "Validating replacement calendar…",
            checked_operation,
            "Calendar source replaced",
            source_id,
        )

    def _toggle_calendar_source(self) -> None:
        source = self._selected_source()
        if not source:
            return
        enabled = not bool(source.get("enabled", True))
        self.repository.set_source_enabled(str(source["id"]), enabled)
        self._after_mutation("Calendar {}".format("enabled" if enabled else "disabled"))
        self._refresh_sources(str(source["id"]))

    def _reset_hidden_events(self) -> None:
        source = self._selected_source()
        if not source:
            return
        if QMessageBox.question(
            self,
            "Reset hidden events?",
            "Make every hidden occurrence from ‘{}’ visible again?".format(source.get("name", "this calendar")),
        ) != QMessageBox.StandardButton.Yes:
            return
        count = self.repository.reset_hidden(str(source["id"]))
        self._after_mutation("Reset {} hidden event{}".format(count, "" if count == 1 else "s"))
        self._refresh_sources(str(source["id"]))

    def _remove_calendar_source(self) -> None:
        source = self._selected_source()
        if not source:
            return
        if QMessageBox.question(
            self,
            "Remove calendar?",
            "Remove ‘{}’, its local cache, and its hidden-event state? Local events will not be changed.".format(
                source.get("name", "this calendar")
            ),
        ) != QMessageBox.StandardButton.Yes:
            return
        self.repository.remove_source(str(source["id"]))
        self._after_mutation("Calendar removed; local events were left unchanged")
