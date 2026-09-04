"""Anki lifecycle, caching, current hooks, and strict webview bridge."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import date, datetime, timedelta
import hashlib
import json
import math
import os
from pathlib import Path
import re
import time
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import aqt
from aqt import gui_hooks, mw
from aqt.deckbrowser import DeckBrowser
from aqt.operations import QueryOp
from aqt.qt import QTimer
from aqt.theme import theme_manager

from .analytics import collect_day_browse_target, collect_snapshot, scheduling_today
from .config_schema import analytics_config_fingerprint, archive_expired_events, normalize_config
from .insights import collect_day_insight, unavailable_day_insight
from .migration import enabled_legacy_ids, prepare_migration
from .models import (
    AvailabilityReason,
    BrowseTarget,
    BrowseTargetKind,
    DashboardSnapshot,
    DayFacts,
    DayInsight,
    DayRelation,
    ValueState,
    ValueStatus,
)
from .renderer import (
    calendar_range_payload,
    dashboard_facts_payload,
    day_insight_payload,
    render_activation_required,
    render_dashboard,
    render_failure,
    render_loading,
)
from .verse import QuoteRotator, verse_content


PACKAGE_ROOT = Path(__file__).resolve().parent
ROTATION_STATE_PATH = PACKAGE_ROOT / "user_files" / "rotation_state.json"
NATIVE_STUDIED_RE = re.compile(r'<div\s+id=["\']studiedToday["\'][^>]*>.*?</div>', re.IGNORECASE | re.DOTALL)
_ROTATION_UNCHANGED = object()


def _write_json_atomic(path: Path, value: Mapping[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(json.dumps(dict(value), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(str(temporary), str(path))


def _read_optional_bytes(path: Path) -> Optional[bytes]:
    try:
        return path.read_bytes()
    except FileNotFoundError:
        return None


def _write_bytes_atomic(path: Path, value: bytes) -> None:
    temporary = path.with_suffix(path.suffix + ".transaction.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary.write_bytes(value)
        os.replace(str(temporary), str(path))
    except OSError:
        try:
            temporary.unlink()
        except OSError:
            pass
        raise


def _restore_optional_bytes(path: Path, previous: Optional[bytes]) -> None:
    if previous is None:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
    else:
        _write_bytes_atomic(path, previous)


def _web_asset_url(package: str, filename: str) -> str:
    """Version exported assets by their packaged bytes to defeat stale WebEngine caches."""

    asset = PACKAGE_ROOT / "web" / filename
    digest = hashlib.sha256(asset.read_bytes()).hexdigest()[:16]
    return "/_addons/{}/web/{}?v={}".format(package, filename, digest)


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
        self.pending_most_missed: set[Tuple[Tuple[Any, ...], str]] = set()
        self.browse_target_cache: Dict[
            Tuple[Tuple[Any, ...], str],
            BrowseTarget,
        ] = {}
        self.inflight_browse_targets: set[Tuple[Tuple[Any, ...], str]] = set()
        self._hooks_installed = False
        self.last_event_archive_date: Optional[date] = None
        self.facts_revision = 0
        self.selected_date = ""
        self.selection_follows_today = True
        self._refresh_pending = False
        self._refresh_reasons: set[str] = set()
        self._refresh_needs_invalidation = False
        self._refresh_token = 0
        self._rollover_token = 0
        self._scheduled_rollover_at: Optional[float] = None
        self._last_scheduler_date: Optional[date] = None
        self.initial_failure = False
        self.refresh_error = False
        self.last_updated_at = ""
        self.year_scroll_left: Optional[float] = None
        self._pending_settings_request: Optional[Tuple[str, str, str]] = None
        self._settings_open_pending = False
        self._settings_request_token = 0
        self._active_settings_dialog: Optional[Any] = None

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
            ("operation_did_execute", self.on_operation_did_execute),
            ("state_did_change", self.on_state_change),
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
        self._reset_session_selection()
        self._schedule_rollover()

    def on_profile_open(self, *_args: object) -> None:
        self.profile_generation += 1
        self.snapshot = None
        self.cache_key = None
        self.inflight_key = None
        self.insight_cache.clear()
        self.inflight_insights.clear()
        self.pending_most_missed.clear()
        self.browse_target_cache.clear()
        self.inflight_browse_targets.clear()
        self.last_event_archive_date = None
        self._refresh_pending = False
        self._refresh_reasons.clear()
        self._refresh_needs_invalidation = False
        self._refresh_token += 1
        self._rollover_token += 1
        self._scheduled_rollover_at = None
        self._last_scheduler_date = None
        self.initial_failure = False
        self.refresh_error = False
        self.last_updated_at = ""
        self.year_scroll_left = None
        self.rotator = QuoteRotator(ROTATION_STATE_PATH)
        self._load_profile_config()
        # The Deck Browser can render its loading shell before ``mw.col`` is
        # available.  That first render cannot start a collection query, so
        # remount once profile opening has completed and the collection is
        # guaranteed to exist.
        self._schedule_refresh(
            "profile_open_ready",
            delay_ms=0,
            invalidate_on_apply=False,
        )

    def on_profile_close(self, *_args: object) -> None:
        self._pending_settings_request = None
        self._settings_open_pending = False
        self._settings_request_token += 1
        self.profile_generation += 1
        self.snapshot = None
        self.cache_key = None
        self.inflight_key = None
        self.insight_cache.clear()
        self.inflight_insights.clear()
        self.pending_most_missed.clear()
        self.browse_target_cache.clear()
        self.inflight_browse_targets.clear()
        self._refresh_pending = False
        self._refresh_reasons.clear()
        self._refresh_needs_invalidation = False
        self._refresh_token += 1
        self._rollover_token += 1
        self._scheduled_rollover_at = None
        self._last_scheduler_date = None
        self.initial_failure = False
        self.refresh_error = False
        self.last_updated_at = ""
        self.year_scroll_left = None

    def on_reviewer_answer(self, *_args: object) -> None:
        self._schedule_refresh("reviewer_answer")

    def on_operation_did_execute(self, changes: object, *_args: object) -> None:
        """Refresh only for operations that can change visible canonical facts."""
        relevant = (
            "card",
            "deck",
            "deck_config",
            "config",
            "study_queues",
            "note",
            "note_text",
        )
        if any(bool(getattr(changes, name, False)) for name in relevant):
            self._schedule_refresh("collection_operation")

    def on_state_change(self, new_state: object, old_state: object = None, *_args: object) -> None:
        if new_state != "deckBrowser" or old_state == "deckBrowser":
            return
        self._check_scheduler_day()
        if self._snapshot_needs_retry() or self._insight_cache_needs_retry():
            self.initial_failure = False
            self._schedule_refresh("view_entry_retry", delay_ms=0)

    def _external_config_update(self, raw: object) -> None:
        data_changed = self._adopt_config(normalize_config(raw), persist=False)
        if data_changed:
            self.initial_failure = False
            self.refresh_error = False
            self.invalidate()
            self._refresh_needs_invalidation = False
            self._schedule_refresh(
                "external_config_save",
                delay_ms=0,
                invalidate_on_apply=False,
            )
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
        self.pending_most_missed.clear()
        self.browse_target_cache.clear()
        self.inflight_browse_targets.clear()

    def _schedule_callback(self, delay_ms: int, callback: Any) -> bool:
        try:
            from aqt.qt import QTimer

            QTimer.singleShot(max(0, int(delay_ms)), callback)
            return True
        except Exception:
            return False

    def _schedule_refresh(
        self,
        reason: str,
        delay_ms: int = 75,
        *,
        invalidate_on_apply: bool = True,
    ) -> None:
        self._refresh_reasons.add(str(reason))
        if invalidate_on_apply:
            self._refresh_needs_invalidation = True
        if self._refresh_pending:
            return
        self._refresh_pending = True
        self._refresh_token += 1
        token = self._refresh_token
        generation = self.profile_generation

        def apply() -> None:
            if token != self._refresh_token or generation != self.profile_generation:
                return
            self._refresh_pending = False
            self._refresh_reasons.clear()
            if self._refresh_needs_invalidation:
                self.invalidate()
            self._refresh_needs_invalidation = False
            if (
                self.snapshot is not None
                and getattr(mw, "state", "") == "deckBrowser"
                and self._has_live_fact_consumers()
            ):
                self._set_dashboard_updating(True)
                self._request_snapshot(self._key())
            else:
                self._refresh_deck_browser()

        if not self._schedule_callback(delay_ms, apply):
            apply()

    def _scheduler_date(self) -> Optional[date]:
        col = getattr(mw, "col", None)
        sched = getattr(col, "sched", None)
        cutoff = getattr(sched, "day_cutoff", None)
        if cutoff is None:
            return None
        try:
            return scheduling_today(int(cutoff))
        except (TypeError, ValueError, OverflowError):
            return None

    def _reset_session_selection(self) -> None:
        current = self._scheduler_date()
        self.selected_date = current.isoformat() if current is not None else ""
        self.selection_follows_today = True
        self._last_scheduler_date = current

    def _check_scheduler_day(self) -> None:
        current = self._scheduler_date()
        if current is None:
            return
        if self._last_scheduler_date is not None and current != self._last_scheduler_date:
            if self.selection_follows_today:
                self.selected_date = current.isoformat()
            self.invalidate()
        self._last_scheduler_date = current
        self._schedule_rollover()

    def _next_rollover_timestamp(self) -> Optional[float]:
        col = getattr(mw, "col", None)
        sched = getattr(col, "sched", None)
        try:
            cutoff = float(getattr(sched, "day_cutoff"))
        except (TypeError, ValueError, AttributeError):
            return None
        now = time.time()
        if cutoff > now + 0.25:
            return cutoff
        # A scheduler reset can update day_cutoff asynchronously.  Keep the
        # same local cutoff on the following civil day without polling.
        local_cutoff = datetime.fromtimestamp(cutoff).astimezone()
        return (local_cutoff + timedelta(days=1)).timestamp()

    def _schedule_rollover(self) -> None:
        cutoff = self._next_rollover_timestamp()
        if cutoff is None:
            return
        if self._scheduled_rollover_at is not None and abs(self._scheduled_rollover_at - cutoff) < 1.0:
            return
        self._rollover_token += 1
        self._scheduled_rollover_at = cutoff
        token = self._rollover_token
        generation = self.profile_generation
        delay_ms = max(250, int((cutoff - time.time()) * 1000) + 250)

        def rollover() -> None:
            if token != self._rollover_token or generation != self.profile_generation:
                return
            self._scheduled_rollover_at = None
            col = getattr(mw, "col", None)
            reset = getattr(getattr(col, "sched", None), "reset", None)
            if callable(reset):
                try:
                    reset()
                except Exception:
                    pass
            current = self._scheduler_date()
            if current is not None:
                self._last_scheduler_date = current
                if self.selection_follows_today:
                    self.selected_date = current.isoformat()
            self._schedule_refresh("day_rollover", delay_ms=0)
            self._schedule_rollover()

        self._schedule_callback(delay_ms, rollover)

    def _snapshot_needs_retry(self) -> bool:
        if self.initial_failure:
            return True
        snapshot = self.snapshot
        if snapshot is None:
            return False
        facts = getattr(snapshot, "facts", None)
        if facts is None:
            return False
        return any(
            getattr(state, "status", None) == ValueStatus.UNAVAILABLE
            and getattr(state, "reason", None) == AvailabilityReason.QUERY_FAILED
            for state in (
                facts.today,
                facts.queue,
                facts.buried,
                facts.events,
                facts.last_seven_days,
                facts.long_term,
                facts.history_coverage,
                facts.forecast_coverage,
            )
        )

    def _insight_cache_needs_retry(self) -> bool:
        """Return whether a selected-date query failed independently.

        A failed lazy detail request is cached so duplicate DOM requests do not
        spin.  It must nevertheless be invalidated on the next Deck Browser
        entry (and by the explicit Retry command) just like a failed dashboard
        value.
        """

        for insight in self.insight_cache.values():
            facts = insight.day_facts
            if facts is None:
                continue
            for state in (
                facts.reviews_completed,
                facts.new_cards_studied,
                facts.reviews_due,
                facts.again_count,
                facts.events,
            ):
                if (
                    state.status == ValueStatus.UNAVAILABLE
                    and state.reason == AvailabilityReason.QUERY_FAILED
                ):
                    return True
        return False

    @staticmethod
    def _background_failure_snapshot(
        previous: Optional[DashboardSnapshot],
        fallback: DashboardSnapshot,
    ) -> DashboardSnapshot:
        """Keep unaffected local events while marking failed study facts.

        ``collect_dashboard_facts()`` isolates ordinary component failures.
        This helper handles the rarer case where the background operation
        itself aborts before returning a result.  Collection-backed values are
        then explicitly unavailable, while the previous canonical local-event
        state remains valid and is carried into the atomic replacement.
        """

        if previous is None:
            return fallback

        previous_facts = previous.facts
        fallback_facts = fallback.facts
        scheduling_date = fallback_facts.scheduling_date
        failed = ValueState.unavailable(AvailabilityReason.QUERY_FAILED)
        dates = set(previous_facts.days)
        if scheduling_date:
            dates.add(scheduling_date)
        if previous_facts.events.is_available:
            dates.update(item.date for item in previous_facts.events.value)

        days: Dict[str, DayFacts] = {}
        for iso_date in sorted(dates):
            relation = (
                DayRelation.PAST
                if scheduling_date and iso_date < scheduling_date
                else DayRelation.FUTURE
                if scheduling_date and iso_date > scheduling_date
                else DayRelation.CURRENT
            )
            if previous_facts.events.is_available:
                day_events = ValueState.available(
                    tuple(
                        item
                        for item in previous_facts.events.value
                        if item.date == iso_date
                    )
                )
            elif previous_facts.events.status == ValueStatus.LOADING:
                day_events = ValueState.loading()
            else:
                day_events = ValueState.unavailable(
                    previous_facts.events.reason
                    if previous_facts.events.reason != AvailabilityReason.NONE
                    else AvailabilityReason.QUERY_FAILED
                )
            days[iso_date] = DayFacts(
                date=iso_date,
                scheduling_date=scheduling_date,
                relation=relation,
                reviews_completed=failed,
                new_cards_studied=failed,
                reviews_due=failed,
                again_count=failed,
                events=day_events,
                browse_target=BrowseTarget(),
                filter_scope=previous_facts.filter_scope,
                domain_state=DayDomainState.UNAVAILABLE,
            )

        return replace(
            fallback,
            facts=replace(
                fallback_facts,
                calendar_date=(
                    fallback_facts.calendar_date
                    or previous_facts.calendar_date
                ),
                filter_scope=previous_facts.filter_scope,
                events=previous_facts.events,
                days=days,
            ),
        )

    def _selected_verse(self):
        bible = self.config["bible"]
        quote = self.rotator.get_quote(list(bible["quotes"]), str(bible["rotation_mode"]))
        return verse_content(quote)

    def _all_sections_hidden(self) -> bool:
        visibility = self.config["visibility"]
        return not any(
            bool(visibility.get(key, True))
            for key in (
                "today",
                "remaining",
                "heatmap",
                "heatmap_metrics",
                "bible",
            )
        )

    def _has_live_fact_consumers(self) -> bool:
        """Return whether the mounted dashboard contains study-data consumers."""
        visibility = self.config["visibility"]
        return any(
            bool(visibility.get(key, True))
            for key in ("today", "remaining", "heatmap", "heatmap_metrics")
        )

    def on_deck_browser_render(self, _deck_browser: DeckBrowser, content: Any) -> None:
        self._check_scheduler_day()
        if self.last_event_archive_date != date.today():
            if archive_expired_events(self.config):
                mw.addonManager.writeConfig(self.package, self.config)
                self.invalidate()
            self.last_event_archive_date = date.today()
        content.stats = NATIVE_STUDIED_RE.sub("", str(content.stats), count=1)
        legacy = enabled_legacy_ids(mw.addonManager)
        if legacy:
            content.stats += render_activation_required(legacy, self.config, self.is_dark())
            return
        # The recovery control does not depend on collection data and therefore
        # precedes the initial loading shell in the release state machine.
        if self._all_sections_hidden():
            content.stats += render_dashboard(
                DashboardSnapshot(verse=self._selected_verse()),
                self.config,
                self.is_dark(),
                facts_revision=self.facts_revision,
                last_updated_at=self.last_updated_at,
                year_scroll_left=self.year_scroll_left,
            )
            return
        if self.initial_failure and self.snapshot is None:
            content.stats += render_failure(self.config, self.is_dark())
            return
        key = self._key()
        if self.snapshot is not None and self.cache_key == key:
            snapshot = self.snapshot
            if self.config["bible"].get("rotation_mode") == "every render":
                snapshot = replace(snapshot, verse=self._selected_verse())
            content.stats += render_dashboard(
                snapshot,
                self.config,
                self.is_dark(),
                selected_date=self.selected_date,
                facts_revision=self.facts_revision,
                refresh_error=self.refresh_error,
                last_updated_at=self.last_updated_at,
                year_scroll_left=self.year_scroll_left,
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
                selected_date=self.selected_date,
                facts_revision=self.facts_revision,
                refresh_error=self.refresh_error,
                last_updated_at=self.last_updated_at,
                year_scroll_left=self.year_scroll_left,
            )
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
                # A newer request already owns the mounted updating state.  An
                # older completion must not remount the page or clear it.
                if self.inflight_key != key:
                    return
                self.inflight_key = None
                # A profile-open/configuration hook can invalidate the very first
                # request while Anki is still constructing the deck browser.  The
                # stale result is intentionally discarded, but the visible loading
                # state must trigger a request for the now-current generation.
                if (
                    generation == self.profile_generation
                    and self.snapshot is not None
                    and getattr(mw, "state", "") == "deckBrowser"
                    and self._has_live_fact_consumers()
                ):
                    self._set_dashboard_updating(True)
                    self._request_snapshot(self._key())
                else:
                    self._refresh_deck_browser()
                return
            had_visible_snapshot = self.snapshot is not None
            self.snapshot = snapshot
            self.last_updated_at = datetime.now().astimezone().isoformat(timespec="seconds")
            self.cache_key = key
            self.inflight_key = None
            self.initial_failure = False
            self.refresh_error = False
            self.facts_revision += 1
            self._schedule_rollover()
            if had_visible_snapshot and self._deliver_dashboard_facts(snapshot):
                return
            self._refresh_deck_browser()

        def failure(_exc: Exception) -> None:
            if generation != self.profile_generation or key != self._key():
                if self.inflight_key != key:
                    return
                self.inflight_key = None
                if (
                    generation == self.profile_generation
                    and self.snapshot is not None
                    and getattr(mw, "state", "") == "deckBrowser"
                    and self._has_live_fact_consumers()
                ):
                    self._set_dashboard_updating(True)
                    self._request_snapshot(self._key())
                else:
                    self._refresh_deck_browser()
                return
            had_visible_snapshot = self.snapshot is not None
            self.inflight_key = None
            if had_visible_snapshot:
                # A failed refresh must never replace known-good study facts.
                # Keep the mounted dashboard intact and expose a retryable
                # status beside the calendar title plus a compact alert.
                self.cache_key = key
                self.refresh_error = True
                if self._set_dashboard_refresh_failed():
                    return
                self._refresh_deck_browser()
                return
            self.initial_failure = True
            self.refresh_error = False
            self.snapshot = None
            self.cache_key = key
            self.facts_revision += 1
            self._refresh_deck_browser()

        query = QueryOp(parent=mw, op=operation, success=success)
        failure_method = getattr(query, "failure", None)
        if callable(failure_method):
            query = failure_method(failure)
        query.run_in_background()

    def _refresh_deck_browser(self) -> None:
        if getattr(mw, "state", "") == "deckBrowser" and getattr(mw, "deckBrowser", None):
            mw.deckBrowser.refresh()

    @staticmethod
    def _dashboard_web() -> Any:
        deck_browser = getattr(mw, "deckBrowser", None)
        return getattr(deck_browser, "web", None) if deck_browser is not None else None

    def _set_dashboard_updating(self, updating: bool) -> bool:
        if not self._has_live_fact_consumers():
            return False
        web = self._dashboard_web()
        if web is None:
            return False
        value = "true" if updating else "false"
        script = (
            "(function apply(attempt){var target=globalThis.HDOHomeDashboard;"
            "if(target&&typeof target.setUpdating==='function'){target.setUpdating(%s);return;}"
            "if(attempt<20){setTimeout(function(){apply(attempt+1);},50);}})(0);"
        ) % value
        try:
            web.eval(script)
            return True
        except Exception:
            return False

    def _set_dashboard_refresh_failed(self) -> bool:
        if not self._has_live_fact_consumers():
            return False
        web = self._dashboard_web()
        if web is None:
            return False
        script = (
            "(function apply(attempt){var target=globalThis.HDOHomeDashboard;"
            "if(target&&typeof target.setRefreshFailed==='function'){target.setRefreshFailed();return;}"
            "if(attempt<20){setTimeout(function(){apply(attempt+1);},50);}})(0);"
        )
        try:
            web.eval(script)
            return True
        except Exception:
            return False

    def _deliver_dashboard_facts(self, snapshot: DashboardSnapshot) -> bool:
        """Atomically refresh the mounted dashboard without replacing its DOM."""
        if (
            getattr(mw, "state", "") != "deckBrowser"
            or not self._has_live_fact_consumers()
        ):
            return False
        web = self._dashboard_web()
        if web is None:
            return False
        facts = dashboard_facts_payload(
            snapshot,
            self.config,
            self.selected_date,
            self.facts_revision,
            self.last_updated_at,
            self.year_scroll_left,
        )
        envelope = {"revision": self.facts_revision, "facts": facts}
        encoded = json.dumps(envelope, ensure_ascii=True, separators=(",", ":"))
        script = (
            "(function deliver(attempt){var target=globalThis.HDOHomeDashboard;"
            "if(target&&typeof target.receiveDashboardFacts==='function'){"
            "target.receiveDashboardFacts(%s);return;}"
            "if(attempt<20){setTimeout(function(){deliver(attempt+1);},50);}})(0);"
        ) % encoded
        try:
            web.eval(script)
            return True
        except Exception:
            return False

    def on_web_content(self, web_content: Any, context: Any) -> None:
        if not isinstance(context, DeckBrowser):
            return
        css = _web_asset_url(self.package, "dashboard.css")
        js = _web_asset_url(self.package, "dashboard.js")
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
            event_id = payload.get("event_id")
            if page is None:
                self.request_settings_open()
            elif page == "calendar_data":
                self.request_settings_open("calendar_data")
            elif page == "events":
                date_value = str(selected_date) if self._valid_bridge_date(selected_date) else ""
                event_value = str(event_id)[:80] if isinstance(event_id, (str, int)) else ""
                self.request_settings_open("events", date_value, event_value)
        elif command == "date_insight" and isinstance(payload, Mapping):
            selected = self._parse_bridge_date(payload.get("date"))
            request_id = payload.get("request_id")
            if selected is not None and self._valid_request_id(request_id):
                self.request_day_insight(context, selected, int(request_id))
        elif command == "calendar_range" and isinstance(payload, Mapping):
            anchor = self._parse_bridge_date(payload.get("anchor"))
            view = payload.get("view")
            request_id = payload.get("request_id")
            revision = payload.get("revision")
            source_revision = payload.get("source_revision")
            if (
                anchor is not None
                and view in {"month", "year"}
                and self._valid_request_id(request_id)
                and self._valid_facts_revision(revision)
                and isinstance(source_revision, str)
            ):
                self.request_calendar_range(
                    context,
                    anchor,
                    str(view),
                    int(request_id),
                    int(revision),
                    source_revision,
                )
        elif command == "open_day" and isinstance(payload, Mapping):
            self.open_day_in_browser(payload.get("date"))
        elif command == "open_most_missed" and isinstance(payload, Mapping):
            self.open_most_missed_in_browser(context, payload.get("date"))
        elif command == "retry" and isinstance(payload, Mapping):
            self.initial_failure = False
            self.refresh_error = False
            self._schedule_refresh("user_retry", delay_ms=0)
        elif command == "diagnostics" and isinstance(payload, Mapping):
            self.request_settings_open("about_support")
        elif command == "calendar_selection_changed" and isinstance(payload, Mapping):
            self.set_calendar_selection(
                payload.get("date"),
                payload.get("follows_today"),
            )
        elif command == "calendar_year_scroll" and isinstance(payload, Mapping):
            left = payload.get("left")
            if (
                isinstance(left, (int, float))
                and not isinstance(left, bool)
                and math.isfinite(float(left))
                and 0 <= float(left) <= 100_000
            ):
                self.year_scroll_left = float(left)
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

    @staticmethod
    def _valid_facts_revision(value: object) -> bool:
        return isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 2_147_483_647

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

    def set_calendar_selection(
        self,
        raw_date: object,
        raw_follows_today: object,
    ) -> None:
        selected = self._parse_bridge_date(raw_date)
        if selected is None:
            return
        current = self._scheduler_date()
        self.selected_date = selected.isoformat()
        self.selection_follows_today = bool(raw_follows_today) and selected == current
        if self.selection_follows_today:
            # A Today action owns one fresh centering pass.  Clearing the
            # stored manual offset prevents the range rerender that follows
            # the click from restoring the pre-Today Year position.
            self.year_scroll_left = None

    def open_day_in_browser(self, raw_date: object) -> None:
        selected = self._parse_bridge_date(raw_date)
        if selected is None or mw.col is None:
            return
        key = self._key()
        selected_iso = selected.isoformat()
        if self.snapshot is None or self.cache_key != key:
            return
        day = self.snapshot.facts.for_date(selected_iso)
        actionable = (
            day.reviews_completed.is_available
            and int(day.reviews_completed.value) > 0
        ) or (
            day.reviews_due.is_available
            and int(day.reviews_due.value) > 0
        )
        if not actionable:
            return
        target_key = (key, selected_iso)
        target = self.browse_target_cache.get(target_key)
        if target is not None:
            if target.exact and target.query:
                self._open_browser_target(target)
            return
        if target_key in self.inflight_browse_targets:
            return
        self.inflight_browse_targets.add(target_key)
        frozen_config = deepcopy(self.config)
        scheduling_date = scheduling_today(int(mw.col.sched.day_cutoff))

        def operation(col: Any) -> BrowseTarget:
            return collect_day_browse_target(
                col,
                frozen_config,
                selected,
                scheduling_date,
            )

        def finish(resolved: BrowseTarget) -> None:
            self.inflight_browse_targets.discard(target_key)
            if key != self._key() or self.cache_key != key:
                return
            self.browse_target_cache[target_key] = resolved
            if resolved.exact and resolved.query:
                self._open_browser_target(resolved)

        def failure(_exc: Exception) -> None:
            self.inflight_browse_targets.discard(target_key)

        query = QueryOp(parent=mw, op=operation, success=finish)
        failure_method = getattr(query, "failure", None)
        if callable(failure_method):
            query = failure_method(failure)
        query.run_in_background()

    def open_most_missed_in_browser(self, context: Any, raw_date: object) -> None:
        """Open the lazy exact Again-ranked set, resolving it in the background."""
        selected = self._parse_bridge_date(raw_date)
        if selected is None or mw.col is None:
            return
        selected_iso = selected.isoformat()
        if selected_iso != self.selected_date:
            return
        insight_key = (self._key(), selected_iso)
        cached = self.insight_cache.get(insight_key)
        if cached is not None:
            target = cached.browse_target
            if target.exact and target.query:
                self._open_browser_target(target)
            return
        self.pending_most_missed.add(insight_key)
        request_id = max(1, (self.facts_revision % 2_147_483_646) + 1)
        self.request_day_insight(context, selected, request_id)

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
        base_day_facts = None
        if self.snapshot is not None and self.cache_key == key:
            base_day_facts = self.snapshot.facts.for_date(selected_iso)
        self.inflight_insights[insight_key] = [(context, request_id)]

        def operation(col: Any) -> DayInsight:
            return collect_day_insight(
                col,
                frozen_config,
                selected,
                scheduling_date,
                calendar_today,
                day_facts=base_day_facts,
            )

        def finish(insight: DayInsight) -> None:
            pending = self.inflight_insights.pop(insight_key, [])
            if key != self._key():
                return
            self.insight_cache[insight_key] = insight
            current_facts = self.snapshot.facts if self.snapshot is not None else None
            base_day = current_facts.for_date(selected_iso) if current_facts is not None else None
            if (
                insight.day_facts is not None
                and self.snapshot is not None
                and self.cache_key == key
                and insight.day_facts.date == selected_iso
                and insight.day_facts.scheduling_date == current_facts.scheduling_date
                and insight.day_facts.filter_scope == current_facts.filter_scope
                and base_day is not None
                and all(
                    getattr(insight.day_facts, field) == getattr(base_day, field)
                    for field in (
                        "reviews_completed",
                        "new_cards_studied",
                        "reviews_due",
                        "again_count",
                        "events",
                    )
                )
            ):
                enriched_days = dict(current_facts.days)
                enriched_days[selected_iso] = insight.day_facts
                self.snapshot = replace(
                    self.snapshot,
                    facts=replace(current_facts, days=enriched_days),
                )
            for pending_context, pending_request_id in pending:
                self._deliver_day_insight(pending_context, pending_request_id, insight)
            if insight_key in self.pending_most_missed:
                self.pending_most_missed.discard(insight_key)
                target = insight.browse_target
                if target.exact and target.query:
                    self._open_browser_target(target)

        def failure(_exc: Exception) -> None:
            finish(unavailable_day_insight(selected, scheduling_date))

        query = QueryOp(parent=mw, op=operation, success=finish)
        failure_method = getattr(query, "failure", None)
        if callable(failure_method):
            query = failure_method(failure)
        query.run_in_background()

    def request_calendar_range(
        self,
        context: Any,
        anchor: date,
        view: str,
        request_id: int,
        revision: int,
        source_revision: str,
    ) -> None:
        """Return a canonical period from the mounted snapshot without recounting."""

        snapshot = self.snapshot
        if (
            snapshot is None
            or revision != self.facts_revision
            or source_revision != snapshot.facts.revision
            or view not in {"month", "year"}
        ):
            return
        generation = self.profile_generation
        payload = calendar_range_payload(
            snapshot,
            anchor.isoformat(),
            view,
            int(self.config["heatmap"].get("week_start", 0)),
        )
        if generation != self.profile_generation or revision != self.facts_revision:
            return
        envelope = {
            "anchor": payload["anchor"],
            "view": payload["view"],
            "request_id": request_id,
            "revision": revision,
            "source_revision": payload["source_revision"],
            "activity": payload["activity"],
        }
        script = (
            "globalThis.HDOHomeDashboard && "
            "globalThis.HDOHomeDashboard.receiveCalendarRange({});"
        ).format(json.dumps(envelope, ensure_ascii=True, separators=(",", ":")))
        try:
            context.web.eval(script)
        except Exception:
            pass

    def _deliver_day_insight(self, context: Any, request_id: int, insight: DayInsight) -> None:
        envelope = {
            "date": insight.date,
            "request_id": request_id,
            "revision": self.facts_revision,
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

    @classmethod
    def _open_browser_target(cls, target: BrowseTarget) -> None:
        cls._open_browser_search(
            str(target.query),
            target.card_ids if target.kind == BrowseTargetKind.MOST_MISSED else (),
        )

    @staticmethod
    def _open_browser_search(query: str, ordered_card_ids: Sequence[int] = ()) -> None:
        """Open an exact search, preserving Most-missed rank in card mode.

        Anki normally re-sorts every Browser search by the user's active
        column.  The public ``browser_will_search`` hook accepts an explicit
        ID sequence, so the contextual Most missed action can retain its
        Again/answer/id rank without adding preview data to the dashboard.
        """
        browser = aqt.dialogs.open("Browser", mw)
        search_for = getattr(browser, "search_for", None)
        if not callable(search_for):
            return

        rank_hook = None
        ids = tuple(int(card_id) for card_id in ordered_card_ids if int(card_id) > 0)
        if ids:
            table = getattr(browser, "table", None)
            is_notes_mode = getattr(table, "is_notes_mode", None)
            if callable(is_notes_mode) and is_notes_mode():
                switch = getattr(browser, "_switch", None)
                set_checked = getattr(switch, "setChecked", None)
                if callable(set_checked):
                    set_checked(False)
            if not callable(is_notes_mode) or not is_notes_mode():
                def inject_rank(context: Any) -> None:
                    if (
                        getattr(context, "browser", None) is browser
                        and getattr(context, "search", None) == query
                    ):
                        context.ids = ids
                        context.order = False
                        context.reverse = False

                rank_hook = inject_rank
                gui_hooks.browser_will_search.append(rank_hook)
        try:
            search_for(query)
        finally:
            if rank_hook is not None:
                try:
                    gui_hooks.browser_will_search.remove(rank_hook)
                except ValueError:
                    pass

    def open_settings(
        self,
        page: object = None,
        selected_date: object = None,
        selected_event_id: object = None,
        *_args: object,
    ) -> None:
        from .settings import SettingsDialog

        request = self._settings_request(page, selected_date, selected_event_id)
        active_dialog = self._active_settings_dialog
        if active_dialog is not None:
            self._route_active_settings_dialog(active_dialog, request)
            return
        dialog = SettingsDialog(
            mw,
            self,
            *request,
        )
        self._active_settings_dialog = dialog
        try:
            dialog.exec()
        finally:
            if self._active_settings_dialog is dialog:
                self._active_settings_dialog = None

    def _settings_request(
        self,
        page: object,
        selected_date: object,
        selected_event_id: object,
    ) -> Tuple[str, str, str]:
        page_name = page if isinstance(page, str) else ""
        date_value = selected_date if self._valid_bridge_date(selected_date) else ""
        event_value = (
            str(selected_event_id)[:80]
            if isinstance(selected_event_id, (str, int))
            else ""
        )
        return page_name, date_value, event_value

    @staticmethod
    def _route_active_settings_dialog(
        dialog: Any,
        request: Tuple[str, str, str],
    ) -> None:
        open_page = getattr(dialog, "open_page", None)
        if callable(open_page):
            open_page(*request)
        is_visible = getattr(dialog, "isVisible", None)
        try:
            visible = bool(is_visible()) if callable(is_visible) else False
        except Exception:
            visible = False
        set_focus = getattr(dialog, "setFocus", None)
        if visible and callable(set_focus):
            set_focus()

    def request_settings_open(
        self,
        page: object = None,
        selected_date: object = None,
        selected_event_id: object = None,
    ) -> None:
        """Leave a WebEngine callback before entering the native dialog."""

        self._pending_settings_request = self._settings_request(
            page,
            selected_date,
            selected_event_id,
        )
        if self._settings_open_pending:
            return
        self._settings_request_token += 1
        token = self._settings_request_token
        self._settings_open_pending = True
        QTimer.singleShot(0, lambda: self._open_pending_settings(token))

    def _open_pending_settings(self, token: int) -> None:
        if token != self._settings_request_token or not self._settings_open_pending:
            return
        request = self._pending_settings_request
        self._pending_settings_request = None
        self._settings_open_pending = False
        self._settings_request_token += 1
        if request is not None:
            self.open_settings(*request)

    def save_config(self, config: Mapping[str, Any], preferred_verse: object = None) -> None:
        normalized = normalize_config(config)
        archive_expired_events(normalized)
        previous_bible = self.config.get("bible", {})
        next_bible = normalized["bible"]
        rotation_changed = (
            previous_bible.get("quotes") != next_bible.get("quotes")
            or previous_bible.get("rotation_mode") != next_bible.get("rotation_mode")
        )
        prepared_rotation: object = _ROTATION_UNCHANGED
        if (
            normalized["bible"].get("rotation_mode") == "manual"
            and isinstance(preferred_verse, str)
        ):
            prepared_rotation = self.rotator.prepare_quote(
                list(normalized["bible"]["quotes"]),
                "manual",
                preferred_verse,
            )
            if prepared_rotation is None:
                raise ValueError("The selected manual verse is no longer in the verse library.")
        elif rotation_changed:
            prepared_rotation = None

        self._persist_settings_transaction(normalized, prepared_rotation)
        data_changed = self._adopt_config(
            normalized,
            persist=False,
            rotation_persisted=prepared_rotation is not _ROTATION_UNCHANGED,
        )
        if isinstance(prepared_rotation, Mapping):
            self.rotator.adopt_prepared(prepared_rotation)
        if isinstance(prepared_rotation, Mapping) and self.snapshot is not None:
            self.snapshot = replace(self.snapshot, verse=verse_content(preferred_verse))
        self.last_event_archive_date = date.today()
        if data_changed:
            self.invalidate()
            self._refresh_needs_invalidation = False
            self._schedule_refresh(
                "settings_save",
                delay_ms=0,
                invalidate_on_apply=False,
            )
        self._refresh_deck_browser()

    def _persist_settings_transaction(
        self,
        normalized: Mapping[str, Any],
        prepared_rotation: object,
    ) -> None:
        """Commit config and manual-verse state with best-effort rollback."""

        try:
            raw_previous = mw.addonManager.getConfig(self.package)
        except Exception:
            raw_previous = self.config
        previous_config = deepcopy(
            dict(raw_previous) if isinstance(raw_previous, Mapping) else self.config
        )
        previous_rotation = (
            _read_optional_bytes(ROTATION_STATE_PATH)
            if prepared_rotation is not _ROTATION_UNCHANGED
            else None
        )
        try:
            mw.addonManager.writeConfig(self.package, normalize_config(normalized))
        except Exception as exc:
            raise RuntimeError("Could not write add-on configuration: {}".format(exc)) from exc

        if prepared_rotation is _ROTATION_UNCHANGED:
            return
        try:
            if isinstance(prepared_rotation, Mapping):
                self.rotator.persist_prepared(prepared_rotation)
            else:
                try:
                    ROTATION_STATE_PATH.unlink()
                except FileNotFoundError:
                    pass
        except Exception as exc:
            rollback_errors = []
            try:
                mw.addonManager.writeConfig(self.package, previous_config)
            except Exception as rollback_exc:
                rollback_errors.append("configuration rollback failed: {}".format(rollback_exc))
            try:
                _restore_optional_bytes(ROTATION_STATE_PATH, previous_rotation)
            except Exception as rollback_exc:
                rollback_errors.append("verse-state rollback failed: {}".format(rollback_exc))
            detail = "Could not save the current manual verse; previous settings were restored."
            if rollback_errors:
                detail = "Could not save the current manual verse; {}.".format(
                    "; ".join(rollback_errors)
                )
            raise RuntimeError("{} {}".format(detail, exc)) from exc

    def _adopt_config(
        self,
        normalized: Mapping[str, Any],
        persist: bool,
        *,
        rotation_persisted: bool = False,
    ) -> bool:
        normalized_config = normalize_config(normalized)
        analytics_changed = analytics_config_fingerprint(self.config) != analytics_config_fingerprint(normalized_config)
        events_changed = self.config.get("events", {}) != normalized_config.get("events", {})
        previous_bible = self.config.get("bible", {})
        next_bible = normalized_config["bible"]
        rotation_changed = (
            previous_bible.get("quotes") != next_bible.get("quotes")
            or previous_bible.get("rotation_mode") != next_bible.get("rotation_mode")
        )
        if persist:
            mw.addonManager.writeConfig(self.package, normalized_config)
        self.config = normalized_config
        if events_changed and self.snapshot is not None:
            from .settings_model import preview_snapshot_with_staged_events

            reference_date = (
                self.snapshot.facts.calendar_date
                or self.snapshot.facts.scheduling_date
                or date.today().isoformat()
            )
            self.snapshot = preview_snapshot_with_staged_events(
                self.snapshot,
                normalized_config,
                reference_date,
            )
        if rotation_changed:
            self.rotator.clear(persistent=not rotation_persisted)
            if self.snapshot is not None:
                self.snapshot = replace(self.snapshot, verse=self._selected_verse())
        return analytics_changed or events_changed
