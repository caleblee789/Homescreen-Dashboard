"""Anki lifecycle, caching, current hooks, and strict webview bridge."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, replace
from datetime import date, datetime, timedelta
import json
import os
from pathlib import Path
import re
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

import aqt
from aqt import gui_hooks, mw
from aqt.deckbrowser import DeckBrowser
from aqt.operations import QueryOp
from aqt.qt import QTimer
from aqt.theme import theme_manager

from .analytics import browser_search_for_day, collect_snapshot, scheduling_today
from .calendar_repository import CalendarRepository, RefreshResult
from .config_schema import analytics_config_fingerprint, archive_expired_events, normalize_config
from .migration import enabled_legacy_ids, prepare_migration
from .models import DashboardSnapshot
from .renderer import render_activation_required, render_dashboard, render_loading
from .verse import QuoteRotator, verse_content


PACKAGE_ROOT = Path(__file__).resolve().parent
ROTATION_STATE_PATH = PACKAGE_ROOT / "user_files" / "rotation_state.json"
CALENDAR_USER_FILES_PATH = PACKAGE_ROOT / "user_files"
CALENDAR_REFRESH_INTERVAL_MS = 6 * 60 * 60 * 1000
NATIVE_STUDIED_RE = re.compile(r'<div\s+id=["\']studiedToday["\'][^>]*>.*?</div>', re.IGNORECASE | re.DOTALL)


def _write_json_atomic(path: Path, value: Mapping[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(json.dumps(dict(value), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(str(temporary), str(path))


class DashboardController:
    def __init__(self) -> None:
        self.package = mw.addonManager.addonFromModule(__name__)
        self.config: Dict[str, Any] = normalize_config(mw.addonManager.getConfig(self.package))
        self.rotator = QuoteRotator(ROTATION_STATE_PATH)
        self.profile_generation = 0
        self.data_generation = 0
        self.calendar_render_generation = 0
        self.cache_key: Optional[Tuple[Any, ...]] = None
        self.snapshot: Optional[DashboardSnapshot] = None
        self.inflight_key: Optional[Tuple[Any, ...]] = None
        self.settings_dialog: Any = None
        self.event_manager_dialog: Any = None
        self._hooks_installed = False
        self.last_event_archive_date: Optional[date] = None
        self.calendar_repository = self._new_calendar_repository()
        self.calendar_refresh_timer = QTimer(mw)
        self.calendar_refresh_timer.setInterval(CALENDAR_REFRESH_INTERVAL_MS)
        self.calendar_refresh_timer.timeout.connect(self.refresh_calendar_subscriptions)

    def start(self) -> None:
        mw.addonManager.setWebExports(self.package, r"web/.*\.(css|js)")
        self._install_hooks()
        try:
            mw.addonManager.setConfigUpdatedAction(self.package, self._external_config_update)
        except Exception:
            pass
        from .settings import install_settings_menu

        install_settings_menu(self)
        if getattr(mw, "col", None) is not None:
            self._load_profile_config()
            self._start_calendar_lifecycle()

    def _new_calendar_repository(self) -> CalendarRepository:
        return CalendarRepository(
            CALENDAR_USER_FILES_PATH,
            config_getter=lambda: self.config,
            config_writer=self._write_calendar_config,
        )

    def _install_hooks(self) -> None:
        if self._hooks_installed:
            return
        gui_hooks.deck_browser_will_render_content.append(self.on_deck_browser_render)
        gui_hooks.webview_will_set_content.append(self.on_web_content)
        gui_hooks.webview_did_receive_js_message.append(self.on_bridge_message)
        for name, callback in (
            ("profile_did_open", self.on_profile_open),
            ("profile_will_close", self.on_profile_close),
            ("reviewer_did_answer_card", self.on_reviewer_answer),
        ):
            hook = getattr(gui_hooks, name, None)
            if hook is not None:
                hook.append(callback)
        self._hooks_installed = True

    def _load_profile_config(self) -> None:
        raw = mw.addonManager.getConfig(self.package)
        migrated, rotation_state = prepare_migration(mw, raw)
        if rotation_state:
            _write_json_atomic(ROTATION_STATE_PATH, rotation_state)
        if not isinstance(raw, Mapping) or dict(raw) != migrated:
            # Persist schema upgrades (including removal of calendar_mode) as
            # soon as the normalized profile configuration is loaded.
            mw.addonManager.writeConfig(self.package, migrated)
        self.config = migrated
        if archive_expired_events(self.config):
            mw.addonManager.writeConfig(self.package, self.config)
        self.last_event_archive_date = date.today()
        self.invalidate()

    def on_profile_open(self, *_args: object) -> None:
        self.profile_generation += 1
        self.calendar_render_generation += 1
        self.snapshot = None
        self.cache_key = None
        self.inflight_key = None
        self.last_event_archive_date = None
        self.rotator = QuoteRotator(ROTATION_STATE_PATH)
        self._load_profile_config()
        self.calendar_repository = self._new_calendar_repository()
        self._start_calendar_lifecycle()

    def on_profile_close(self, *_args: object) -> None:
        self.profile_generation += 1
        self.calendar_render_generation += 1
        self.snapshot = None
        self.cache_key = None
        self.inflight_key = None
        self.calendar_refresh_timer.stop()
        if self.event_manager_dialog is not None:
            self.event_manager_dialog.close()
            self.event_manager_dialog = None

    def on_reviewer_answer(self, *_args: object) -> None:
        self.invalidate()

    def _start_calendar_lifecycle(self) -> None:
        self.calendar_refresh_timer.start()
        QTimer.singleShot(0, self.refresh_calendar_subscriptions)

    def _external_config_update(self, raw: object) -> None:
        self._adopt_config(normalize_config(raw), persist=False)
        self._refresh_deck_browser()

    def is_dark(self) -> bool:
        return bool(getattr(theme_manager, "night_mode", False))

    def _key(self) -> Tuple[Any, ...]:
        col = mw.col
        scheduler_day = int(getattr(col.sched, "today", 0)) if col else -1
        collection_mod = getattr(col, "mod", 0) if col else 0
        if callable(collection_mod):
            try:
                collection_mod = collection_mod()
            except Exception:
                collection_mod = 0
        return (
            self.profile_generation,
            self.data_generation,
            id(col),
            collection_mod,
            scheduler_day,
            analytics_config_fingerprint(self.config),
        )

    def invalidate(self) -> None:
        self.data_generation += 1
        self.cache_key = None

    def _selected_verse(self):
        bible = self.config["bible"]
        quote = self.rotator.get_quote(list(bible["quotes"]), str(bible["rotation_mode"]))
        return verse_content(quote)

    def on_deck_browser_render(self, _deck_browser: DeckBrowser, content: Any) -> None:
        self.archive_expired_local_events()
        content.stats = NATIVE_STUDIED_RE.sub("", str(content.stats), count=1)
        legacy = enabled_legacy_ids(mw.addonManager)
        if legacy:
            content.stats += render_activation_required(legacy, self.config, self.is_dark())
            return
        key = self._key()
        self.calendar_render_generation += 1
        calendar_generation = self.calendar_render_generation
        calendar_events, calendar_start, calendar_end = self._initial_calendar_events()
        if self.snapshot is not None and self.cache_key == key:
            snapshot = self.snapshot
            if self.config["bible"].get("rotation_mode") == "every render":
                snapshot = replace(snapshot, verse=self._selected_verse())
            content.stats += render_dashboard(
                snapshot,
                self.config,
                self.is_dark(),
                calendar_events=calendar_events,
                calendar_generation=calendar_generation,
                calendar_range=(calendar_start, calendar_end),
                calendar_sources=self.calendar_repository.list_sources(),
            )
            return
        if self.snapshot is not None:
            snapshot = self.snapshot
            if self.config["bible"].get("rotation_mode") == "every render":
                snapshot = replace(snapshot, verse=self._selected_verse())
            content.stats += render_dashboard(
                snapshot,
                self.config,
                self.is_dark(),
                calendar_events=calendar_events,
                calendar_generation=calendar_generation,
                calendar_range=(calendar_start, calendar_end),
                calendar_sources=self.calendar_repository.list_sources(),
            )
            self._request_snapshot(key)
            return
        content.stats += render_loading(self.config, self.is_dark())
        self._request_snapshot(key)

    def _initial_calendar_events(self) -> Tuple[List[Any], str, str]:
        today = date.today()
        if self.config.get("heatmap", {}).get("calendar_view") == "month":
            period_start = today.replace(day=1)
            period_end = (period_start.replace(day=28) + timedelta(days=4)).replace(day=1)
        else:
            period_start = date(today.year, 1, 1)
            period_end = date(today.year + 1, 1, 1)
        start = period_start - timedelta(days=7)
        end = period_end + timedelta(days=7)
        try:
            events = self.calendar_repository.day_events_between(start, end, cached_only=True)
        except Exception:
            events = []
        return events, start.isoformat(), end.isoformat()

    def _request_snapshot(self, key: Tuple[Any, ...]) -> None:
        if self.inflight_key == key or mw.col is None:
            return
        generation = self.profile_generation
        frozen_config = deepcopy(self.config)
        selected_verse = self._selected_verse()
        self.inflight_key = key

        def operation(col: Any) -> DashboardSnapshot:
            return collect_snapshot(col, frozen_config, selected_verse)

        def success(snapshot: DashboardSnapshot) -> None:
            if generation != self.profile_generation or key != self._key():
                if self.inflight_key == key:
                    self.inflight_key = None
                # A profile-open/configuration hook can invalidate the very first
                # request while Anki is still constructing the deck browser.  The
                # stale result is intentionally discarded, but the visible loading
                # state must trigger a request for the now-current generation.
                self._refresh_deck_browser()
                return
            self.snapshot = snapshot
            self.cache_key = key
            self.inflight_key = None
            self._refresh_deck_browser()

        def failure(exc: Exception) -> None:
            if generation != self.profile_generation or key != self._key():
                if self.inflight_key == key:
                    self.inflight_key = None
                self._refresh_deck_browser()
                return
            self.inflight_key = None
            self.snapshot = DashboardSnapshot(
                verse=selected_verse,
                generated_at=datetime.now().astimezone().isoformat(timespec="seconds"),
                errors={"dashboard": str(exc)},
            )
            self.cache_key = key
            self._refresh_deck_browser()

        query = QueryOp(parent=mw, op=operation, success=success)
        failure_method = getattr(query, "failure", None)
        if callable(failure_method):
            query = failure_method(failure)
        query.run_in_background()

    def _refresh_deck_browser(self) -> None:
        if getattr(mw, "state", "") == "deckBrowser" and getattr(mw, "deckBrowser", None):
            mw.deckBrowser.refresh()

    def on_web_content(self, web_content: Any, context: Any) -> None:
        if not isinstance(context, DeckBrowser):
            return
        base = "/_addons/{}/web/".format(self.package)
        css = base + "dashboard.css"
        js = base + "dashboard.js"
        if css not in web_content.css:
            web_content.css.append(css)
        if js not in web_content.js:
            web_content.js.append(js)

    def on_bridge_message(self, handled: Tuple[bool, Any], message: str, context: Any) -> Tuple[bool, Any]:
        if not isinstance(message, str) or not message.startswith("hdo:") or not isinstance(context, DeckBrowser):
            return handled
        if len(message) > 2048:
            return (True, None)
        try:
            parsed = json.loads(message[4:])
        except (ValueError, TypeError):
            return (True, None)
        if not isinstance(parsed, Mapping):
            return (True, None)
        command = parsed.get("command")
        payload = parsed.get("payload", {})
        if command == "settings" and isinstance(payload, Mapping):
            page = payload.get("page")
            selected_date = payload.get("date")
            if page is None:
                self.open_settings()
            elif page == "events" and self._valid_bridge_date(selected_date):
                self.open_event_manager(str(selected_date))
        elif command == "manage_events" and isinstance(payload, Mapping):
            selected_date = payload.get("date")
            self.open_event_manager(str(selected_date) if self._valid_bridge_date(selected_date) else "")
            if payload.get("section") == "calendars" and self.event_manager_dialog is not None:
                self.event_manager_dialog.show_calendars()
        elif command == "calendar_events_range" and isinstance(payload, Mapping):
            self._request_calendar_range(payload, context)
        elif command == "open_day" and isinstance(payload, Mapping):
            self.open_day_in_browser(payload.get("date"))
        elif command == "calendar_view_changed" and isinstance(payload, Mapping):
            self.set_calendar_view(payload.get("view"))
        return (True, None)

    def _request_calendar_range(self, payload: Mapping[str, Any], context: DeckBrowser) -> None:
        raw_start = payload.get("start")
        raw_end = payload.get("end")
        request_id = payload.get("request_id")
        generation = payload.get("generation")
        if (
            not self._valid_bridge_date(raw_start)
            or not self._valid_bridge_date(raw_end)
            or not isinstance(request_id, int)
            or not 0 <= request_id <= 1_000_000_000
            or generation != self.calendar_render_generation
        ):
            return
        start = date.fromisoformat(str(raw_start))
        end = date.fromisoformat(str(raw_end))
        if end <= start or (end - start).days > 3660:
            return
        profile_generation = self.profile_generation
        calendar_generation = self.calendar_render_generation

        def operation() -> List[Any]:
            return self.calendar_repository.day_events_between(start, end, cached_only=False)

        def send(values: Sequence[Any], error: str = "") -> None:
            if (
                profile_generation != self.profile_generation
                or calendar_generation != self.calendar_render_generation
            ):
                return
            response = {
                "generation": calendar_generation,
                "request_id": request_id,
                "start": start.isoformat(),
                "end": end.isoformat(),
                "events": [asdict(value) for value in values],
                "error": error[:300],
            }
            encoded = json.dumps(response, ensure_ascii=False, separators=(",", ":"))
            encoded = encoded.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
            web = getattr(context, "web", None)
            if web is not None:
                web.eval(
                    "window.HDOHomeDashboard&&window.HDOHomeDashboard.receiveCalendarEvents({});".format(
                        encoded
                    )
                )

        self.run_calendar_task(operation, lambda values: send(values), lambda exc: send([], str(exc)))

    @staticmethod
    def _valid_bridge_date(raw_date: object) -> bool:
        if not isinstance(raw_date, str):
            return False
        try:
            date.fromisoformat(raw_date)
        except ValueError:
            return False
        return True

    def set_calendar_view(self, raw_view: object) -> None:
        if raw_view not in {"month", "year"} or raw_view == self.config["heatmap"].get("calendar_view"):
            return
        updated = deepcopy(self.config)
        updated["heatmap"]["calendar_view"] = str(raw_view)
        # This is intentionally a render-state write only: the live JavaScript
        # has already switched views, and no SQL refresh or verse selection is
        # needed to remember the choice for the next visit.
        normalized = normalize_config(updated)
        mw.addonManager.writeConfig(self.package, normalized)
        self.config = normalized

    def open_day_in_browser(self, raw_date: object) -> None:
        if not isinstance(raw_date, str) or mw.col is None:
            return
        try:
            selected = date.fromisoformat(raw_date)
        except ValueError:
            return
        today = scheduling_today(int(mw.col.sched.day_cutoff))
        offset = (selected - today).days
        if abs(offset) > 36500:
            return
        query = browser_search_for_day(selected, today)
        browser = aqt.dialogs.open("Browser", mw)
        search_for = getattr(browser, "search_for", None)
        if callable(search_for):
            search_for(query)

    def open_settings(self, page: object = None, selected_date: object = None, *_args: object) -> None:
        from .settings import SettingsDialog

        page_name = page if isinstance(page, str) else ""
        date_value = selected_date if self._valid_bridge_date(selected_date) else ""
        if self.settings_dialog is not None and self.settings_dialog.isVisible():
            self.settings_dialog.open_page(page_name, date_value)
            self.settings_dialog.raise_()
            self.settings_dialog.activateWindow()
            return
        self.settings_dialog = SettingsDialog(self, page_name, date_value)
        self.settings_dialog.finished.connect(lambda _result: setattr(self, "settings_dialog", None))
        self.settings_dialog.show()

    def open_event_manager(self, selected_date: object = None, *_args: object) -> None:
        from .event_manager import EventManagerDialog

        date_value = str(selected_date) if self._valid_bridge_date(selected_date) else ""
        if self.event_manager_dialog is not None and self.event_manager_dialog.isVisible():
            if date_value:
                self.event_manager_dialog.open_for_date(date_value)
            self.event_manager_dialog.raise_()
            self.event_manager_dialog.activateWindow()
            return
        self.event_manager_dialog = EventManagerDialog(self, date_value)
        self.event_manager_dialog.finished.connect(
            lambda _result: setattr(self, "event_manager_dialog", None)
        )
        self.event_manager_dialog.show()

    def run_calendar_task(
        self,
        operation: Callable[[], Any],
        success: Callable[[Any], None],
        failure: Optional[Callable[[Exception], None]] = None,
    ) -> None:
        generation = self.profile_generation

        def query_operation(_col: Any) -> Any:
            return operation()

        def query_success(value: Any) -> None:
            if generation == self.profile_generation:
                success(value)

        def query_failure(exc: Exception) -> None:
            if generation == self.profile_generation and failure is not None:
                failure(exc)

        query = QueryOp(parent=mw, op=query_operation, success=query_success)
        failure_method = getattr(query, "failure", None)
        if callable(failure_method):
            query = failure_method(query_failure)
        query.run_in_background()

    def refresh_calendar_subscriptions(self, *_args: object) -> None:
        def success(results: Sequence[RefreshResult]) -> None:
            if results:
                self.calendar_data_changed()

        self.run_calendar_task(
            self.calendar_repository.refresh_subscriptions,
            success,
            lambda _exc: self.calendar_data_changed(),
        )

    def calendar_data_changed(self) -> None:
        # Calendar-only writes intentionally preserve the collection analytics
        # snapshot and its cache key.
        self._refresh_deck_browser()
        dialog = self.event_manager_dialog
        if dialog is not None and dialog.isVisible():
            dialog.on_repository_changed()
        settings = self.settings_dialog
        if settings is not None and settings.isVisible():
            refresh_summary = getattr(settings, "refresh_calendar_summary", None)
            if callable(refresh_summary):
                refresh_summary()

    def archive_expired_local_events(self) -> None:
        if self.last_event_archive_date == date.today():
            return
        if archive_expired_events(self.config):
            mw.addonManager.writeConfig(self.package, self.config)
        self.last_event_archive_date = date.today()

    def _write_calendar_config(self, config: Mapping[str, Any]) -> None:
        normalized = normalize_config(config)
        archive_expired_events(normalized)
        self._adopt_config(normalized, persist=True)
        self.last_event_archive_date = date.today()
        self._refresh_deck_browser()

    def save_config(self, config: Mapping[str, Any]) -> None:
        # Settings is a staged editor, while the Event Manager saves at once.
        # Merge the current event collection at commit time so an older open
        # Settings window cannot overwrite concurrent manager changes.
        merged = deepcopy(dict(config))
        merged.setdefault("events", {})["items"] = deepcopy(
            self.config.get("events", {}).get("items", [])
        )
        normalized = normalize_config(merged)
        archive_expired_events(normalized)
        self._adopt_config(normalized, persist=True)
        self.last_event_archive_date = date.today()
        self._refresh_deck_browser()

    def _adopt_config(self, normalized: Mapping[str, Any], persist: bool) -> None:
        normalized_config = normalize_config(normalized)
        analytics_changed = analytics_config_fingerprint(self.config) != analytics_config_fingerprint(normalized_config)
        previous_bible = self.config.get("bible", {})
        next_bible = normalized_config["bible"]
        rotation_changed = (
            previous_bible.get("quotes") != next_bible.get("quotes")
            or previous_bible.get("rotation_mode") != next_bible.get("rotation_mode")
        )
        if persist:
            mw.addonManager.writeConfig(self.package, normalized_config)
        self.config = normalized_config
        if rotation_changed:
            self.rotator.clear(persistent=True)
            if self.snapshot is not None:
                self.snapshot = replace(self.snapshot, verse=self._selected_verse())
        if analytics_changed:
            self.invalidate()
