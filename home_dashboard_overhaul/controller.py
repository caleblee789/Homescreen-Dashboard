"""Anki lifecycle, caching, current hooks, and strict webview bridge."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import date, datetime
import json
import os
from pathlib import Path
import re
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import aqt
from aqt import gui_hooks, mw
from aqt.deckbrowser import DeckBrowser
from aqt.operations import QueryOp
from aqt.theme import theme_manager

from .analytics import browser_search_for_day, collect_snapshot, scheduling_today
from .config_schema import analytics_config_fingerprint, archive_expired_events, normalize_config
from .insights import collect_day_insight
from .migration import enabled_legacy_ids, prepare_migration
from .models import DayInsight, DashboardSnapshot
from .renderer import day_insight_payload, render_activation_required, render_dashboard, render_loading
from .verse import QuoteRotator, verse_content


PACKAGE_ROOT = Path(__file__).resolve().parent
ROTATION_STATE_PATH = PACKAGE_ROOT / "user_files" / "rotation_state.json"
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
        self.cache_key: Optional[Tuple[Any, ...]] = None
        self.snapshot: Optional[DashboardSnapshot] = None
        self.inflight_key: Optional[Tuple[Any, ...]] = None
        self.insight_cache: Dict[Tuple[Tuple[Any, ...], str], DayInsight] = {}
        self.inflight_insights: Dict[
            Tuple[Tuple[Any, ...], str],
            List[Tuple[Any, int]],
        ] = {}
        self.settings_dialog: Any = None
        self._hooks_installed = False
        self.last_event_archive_date: Optional[date] = None

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
        self.snapshot = None
        self.cache_key = None
        self.inflight_key = None
        self.insight_cache.clear()
        self.inflight_insights.clear()
        self.last_event_archive_date = None
        self.rotator = QuoteRotator(ROTATION_STATE_PATH)
        self._load_profile_config()

    def on_profile_close(self, *_args: object) -> None:
        self.profile_generation += 1
        self.snapshot = None
        self.cache_key = None
        self.inflight_key = None
        self.insight_cache.clear()
        self.inflight_insights.clear()

    def on_reviewer_answer(self, *_args: object) -> None:
        self.invalidate()

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
        self.insight_cache.clear()
        self.inflight_insights.clear()

    def _selected_verse(self):
        bible = self.config["bible"]
        quote = self.rotator.get_quote(list(bible["quotes"]), str(bible["rotation_mode"]))
        return verse_content(quote)

    def on_deck_browser_render(self, _deck_browser: DeckBrowser, content: Any) -> None:
        if self.last_event_archive_date != date.today():
            if archive_expired_events(self.config):
                mw.addonManager.writeConfig(self.package, self.config)
            self.last_event_archive_date = date.today()
        content.stats = NATIVE_STUDIED_RE.sub("", str(content.stats), count=1)
        legacy = enabled_legacy_ids(mw.addonManager)
        if legacy:
            content.stats += render_activation_required(legacy, self.config, self.is_dark())
            return
        key = self._key()
        if self.snapshot is not None and self.cache_key == key:
            snapshot = self.snapshot
            if self.config["bible"].get("rotation_mode") == "every render":
                snapshot = replace(snapshot, verse=self._selected_verse())
            content.stats += render_dashboard(snapshot, self.config, self.is_dark())
            return
        if self.snapshot is not None:
            snapshot = self.snapshot
            if self.config["bible"].get("rotation_mode") == "every render":
                snapshot = replace(snapshot, verse=self._selected_verse())
            content.stats += render_dashboard(snapshot, self.config, self.is_dark())
            self._request_snapshot(key)
            return
        content.stats += render_loading(self.config, self.is_dark())
        self._request_snapshot(key)

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
                self.open_settings("events", str(selected_date))
        elif command == "date_insight" and isinstance(payload, Mapping):
            selected = self._parse_bridge_date(payload.get("date"))
            request_id = payload.get("request_id")
            if selected is not None and self._valid_request_id(request_id):
                self.request_day_insight(context, selected, int(request_id))
        elif command == "open_day" and isinstance(payload, Mapping):
            self.open_day_in_browser(payload.get("date"))
        elif command == "calendar_view_changed" and isinstance(payload, Mapping):
            self.set_calendar_view(payload.get("view"))
        return (True, None)

    @staticmethod
    def _parse_bridge_date(raw_date: object) -> Optional[date]:
        if not isinstance(raw_date, str):
            return None
        try:
            parsed = date.fromisoformat(raw_date)
        except ValueError:
            return None
        if abs((parsed - date.today()).days) > 36500:
            return None
        return parsed

    @classmethod
    def _valid_bridge_date(cls, raw_date: object) -> bool:
        return cls._parse_bridge_date(raw_date) is not None

    @staticmethod
    def _valid_request_id(value: object) -> bool:
        return isinstance(value, int) and not isinstance(value, bool) and 0 < value <= 2_147_483_647

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
        selected = self._parse_bridge_date(raw_date)
        if selected is None or mw.col is None:
            return
        insight = self.insight_cache.get((self._key(), selected.isoformat()))
        query = insight.browser_query if insight is not None else ""
        if not query:
            query = browser_search_for_day(
                selected,
                scheduling_today(int(mw.col.sched.day_cutoff)),
            )
        self._open_browser_search(query)

    def request_day_insight(self, context: Any, selected: date, request_id: int) -> None:
        if mw.col is None:
            return
        key = self._key()
        selected_iso = selected.isoformat()
        insight_key = (key, selected_iso)
        cached = self.insight_cache.get(insight_key)
        if cached is not None:
            self._deliver_day_insight(context, request_id, cached)
            return
        waiters = self.inflight_insights.get(insight_key)
        if waiters is not None:
            waiters.append((context, request_id))
            return
        frozen_config = deepcopy(self.config)
        scheduling_date = scheduling_today(int(mw.col.sched.day_cutoff))
        calendar_today = date.today()
        self.inflight_insights[insight_key] = [(context, request_id)]

        def operation(col: Any) -> DayInsight:
            return collect_day_insight(
                col,
                frozen_config,
                selected,
                scheduling_date,
                calendar_today,
            )

        def finish(insight: DayInsight) -> None:
            pending = self.inflight_insights.pop(insight_key, [])
            if key != self._key():
                return
            self.insight_cache[insight_key] = insight
            for pending_context, pending_request_id in pending:
                self._deliver_day_insight(pending_context, pending_request_id, insight)

        def failure(_exc: Exception) -> None:
            finish(DayInsight(
                date=selected_iso,
                study_date=(scheduling_date if selected == calendar_today else selected).isoformat(),
                insight_kind="unavailable",
                empty_reason="unavailable",
            ))

        query = QueryOp(parent=mw, op=operation, success=finish)
        failure_method = getattr(query, "failure", None)
        if callable(failure_method):
            query = failure_method(failure)
        query.run_in_background()

    @staticmethod
    def _deliver_day_insight(context: Any, request_id: int, insight: DayInsight) -> None:
        envelope = {
            "date": insight.date,
            "request_id": request_id,
            "insight": day_insight_payload(insight),
        }
        script = (
            "globalThis.HDOHomeDashboard && "
            "globalThis.HDOHomeDashboard.receiveDayInsight({});"
        ).format(json.dumps(envelope, ensure_ascii=True, separators=(",", ":")))
        try:
            context.web.eval(script)
        except Exception:
            pass

    @staticmethod
    def _open_browser_search(query: str) -> None:
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

    def save_config(self, config: Mapping[str, Any], preferred_verse: object = None) -> None:
        normalized = normalize_config(config)
        archive_expired_events(normalized)
        self._adopt_config(normalized, persist=True)
        if (
            normalized["bible"].get("rotation_mode") == "manual"
            and isinstance(preferred_verse, str)
            and self.rotator.set_quote(
                list(normalized["bible"]["quotes"]),
                "manual",
                preferred_verse,
            )
            and self.snapshot is not None
        ):
            self.snapshot = replace(self.snapshot, verse=verse_content(preferred_verse))
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
