from __future__ import annotations

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


class StaticAssetTests(unittest.TestCase):
    def test_web_assets_are_namespaced_and_dependency_free(self) -> None:
        css = (ROOT / "web" / "dashboard.css").read_text(encoding="utf-8")
        js = (ROOT / "web" / "dashboard.js").read_text(encoding="utf-8")
        self.assertNotIn("d3", js.lower())
        self.assertNotIn("cal-heatmap", js.lower())
        self.assertNotIn("window.reviewHeatmap", js)
        self.assertNotRegex(css, r"(?m)^\s*(?:body|html|\.night_mode)\s*\{")
        for selector in (line.strip() for line in css.splitlines() if line.strip().endswith("{")):
            if selector.startswith(("from", "to", "@")):
                continue
            self.assertTrue("#hdo-dashboard" in selector or selector.startswith(("0%", "100%")), selector)
        self.assertNotIn("center:has(", css)
        self.assertNotIn("overflow-x: clip", css)
        self.assertIn("max-width: 1680px", css)
        self.assertIn("grid-template-columns: minmax(720px, 2fr) minmax(320px, 1fr)", css)
        self.assertIn('data-hdo-calendar-view="month"] .hdo-calendar-layout', css)
        self.assertIn("grid-template-columns: repeat(2, minmax(0, 1fr))", css)
        self.assertIn(".hdo-stat-group:last-child:nth-child(odd)", css)
        self.assertIn("grid-column: 1 / -1", css)
        self.assertIn("data-hdo-sidebar-collapsed=\"true\"", css)
        self.assertIn("repeat(var(--hdo-month-rows), clamp(var(--hdo-month-cell-min), 7vh, 82px))", css)
        self.assertIn("height: 6px", css)
        self.assertIn("max-width: 64ch", css)
        self.assertIn("linear-gradient(var(--hdo-surface), var(--hdo-surface)), var(--hdo-bg)", css)
        self.assertNotIn("backdrop-filter", css)
        self.assertNotIn("--hdo-blur", css)
        self.assertIn("background: var(--hdo-surface-solid);", css)
        self.assertRegex(
            css,
            r"\.hdo-data-warning span \{\s+color: var\(--hdo-text\);",
        )
        self.assertNotIn("opacity: .46", css)
        self.assertNotIn("#22a7d6", css.lower())
        self.assertNotIn("font-size: clamp(18px, 5.1vw, 24px) !important", css)
        self.assertIn(".hdo-day-preview", css)
        self.assertIn("width: max-content", css)
        self.assertIn(".hdo-progress-bar", css)
        self.assertIn(".hdo-progress-segment--completed", css)
        self.assertIn(".hdo-progress-segment--new", css)
        self.assertIn(".hdo-progress-segment--learning", css)
        self.assertIn(".hdo-progress-segment--review", css)
        self.assertIn(".hdo-insight-list", css)
        self.assertIn("-webkit-line-clamp: 2", css)
        self.assertIn(".hdo-progress-segment--completed { background-color: var(--hdo-accent); }", css)
        self.assertIn("color: var(--hdo-progress-percent);", css)
        self.assertIn('data-hdo-progress-state="unavailable"', css)
        self.assertIn("repeating-linear-gradient", css)
        self.assertIn('.hdo-stat-group[aria-labelledby="hdo-today-title"] dl', css)
        self.assertIn('.hdo-stat-group[aria-labelledby="hdo-remaining-title"] dl', css)
        self.assertIn("grid-template-columns: minmax(0, 1fr) auto", css)
        self.assertNotIn("hdo-date-popover", css)
        self.assertNotIn("hdo-date-popover--sheet", css)
        self.assertNotIn("position: fixed", css)
        self.assertNotIn("hdo-progress", js)

    def test_only_external_executable_javascript_is_used(self) -> None:
        renderer = (ROOT / "renderer.py").read_text(encoding="utf-8")
        self.assertNotIn('<script>', renderer)
        self.assertIn('type="application/json"', renderer)

    def test_current_hook_objects_are_not_treated_as_iterables(self) -> None:
        controller = (ROOT / "controller.py").read_text(encoding="utf-8")
        self.assertNotIn("callback not in hook", controller)

    def test_a_stale_startup_snapshot_requests_the_current_generation(self) -> None:
        controller = (ROOT / "controller.py").read_text(encoding="utf-8")
        stale_branch = controller.split("def success(snapshot: DashboardSnapshot)", 1)[1].split(
            "self.snapshot = snapshot", 1
        )[0]
        self.assertIn("self._refresh_deck_browser()", stale_branch)

    def test_native_settings_section_picker_is_accessibly_named(self) -> None:
        settings = (ROOT / "settings.py").read_text(encoding="utf-8")
        self.assertIn('self.nav.setAccessibleName("Settings sections")', settings)
        self.assertIn("Qt.ItemDataRole.AccessibleTextRole", settings)
        self.assertNotIn("Background blur", settings)
        self.assertIn('"verse_card": composite_color(', settings)
        self.assertIn('tokens["verse_card"]', settings)

    def test_view_only_bridge_path_does_not_refresh_analytics_or_select_a_verse(self) -> None:
        controller = (ROOT / "controller.py").read_text(encoding="utf-8")
        view_handler = controller.split("def set_calendar_view", 1)[1].split("def request_day_insight", 1)[0]
        self.assertNotIn("invalidate(", view_handler)
        self.assertNotIn("_selected_verse", view_handler)
        self.assertNotIn("_refresh_deck_browser", view_handler)

    def test_bridge_and_config_contracts_remain_exact(self) -> None:
        js = (ROOT / "web" / "dashboard.js").read_text(encoding="utf-8")
        for command in (
            'command("calendar_view_changed", { view: next })',
            'command("date_insight", { date: iso, request_id: requestedId })',
            'command("open_day", { date: browseButton.dataset.date })',
            'command("settings", { page: "events", date: manageButton.dataset.date })',
        ):
            self.assertIn(command, js)
        self.assertNotIn('command("open_insight"', js)
        self.assertNotIn('command("manage_events"', js)
        self.assertNotIn('command("calendar_events_range"', js)
        config = (ROOT / "config.json").read_text(encoding="utf-8")
        manifest = (ROOT / "manifest.json").read_text(encoding="utf-8")
        self.assertIn('"schema_version": 3', config)
        self.assertIn('"human_version": "1.5.3"', manifest)
        self.assertNotIn('"calendar_mode"', config)

    def test_day_insight_bridge_keeps_targets_controller_side_and_discards_stale_work(self) -> None:
        controller = (ROOT / "controller.py").read_text(encoding="utf-8")
        renderer = (ROOT / "renderer.py").read_text(encoding="utf-8")
        js = (ROOT / "web" / "dashboard.js").read_text(encoding="utf-8")
        self.assertIn("self.insight_cache", controller)
        self.assertIn("self.inflight_insights", controller)
        self.assertIn("if key != self._key():", controller)
        self.assertIn("self.insight_cache.clear()", controller)
        self.assertNotIn("self.insight_cache[(key, snapshot.today_insight.date)]", controller)
        self.assertIn("browser_search_for_day", controller)
        self.assertIn("def open_day_in_browser", controller)
        self.assertIn("abs((parsed - date.today()).days) > 36500", controller)
        self.assertIn("_valid_request_id", controller)
        self.assertIn("receiveDayInsight", controller)
        self.assertIn("response.date !== state.selectedDate", js)
        self.assertIn("Number(response.request_id) !== state.activeRequestId", js)
        self.assertIn('if (typeof pycmd !== "function") return false;', js)
        self.assertIn("dispatchWhenReady(", js)
        self.assertIn("return command(\"date_insight\", { date: iso, request_id: requestedId });", js)
        self.assertIn("global.setTimeout(renderUnavailableIfCurrent, 8000)", js)
        self.assertIn("state.selectedDate === iso", js)
        close_block = js.split("function closeDetails", 1)[1].split("function setBrowseButton", 1)[0]
        self.assertIn('state.pendingInsightDate = ""', close_block)
        self.assertIn("primary.textContent", js)
        self.assertIn("secondaryText.textContent", js)
        payload_function = renderer.split("def day_insight_payload", 1)[1].split("def _calendar_controls", 1)[0]
        self.assertNotIn("browser_query", payload_function)
        self.assertNotIn("study_date", payload_function)
        self.assertNotIn("card_id", payload_function)

    def test_exact_day_insight_empty_copy_is_present_once(self) -> None:
        js = (ROOT / "web" / "dashboard.js").read_text(encoding="utf-8")
        for copy in (
            "Cards most missed today",
            "Cards most missed on this date",
            "No cards studied today yet.",
            "Start reviewing to see cards that you are missing repeatedly.",
            "No cards were studied on this date.",
            "No cards were missed today.",
            "No cards were missed on this date.",
            "Cards missed today are no longer available.",
            "Cards missed on this date are no longer available.",
            "No review cards are due on this date.",
            "Study insight unavailable.",
        ):
            self.assertEqual(js.count(copy), 1, copy)
        for forbidden in ("Anki " + "day", "Anki-" + "day"):
            self.assertNotIn(forbidden, js)

    def test_calendar_and_event_settings_are_discoverable(self) -> None:
        settings = (ROOT / "settings.py").read_text(encoding="utf-8")
        self.assertIn('[("Month", "month"), ("Year", "year")]', settings)
        self.assertNotIn("Continuous 9 months", settings)
        self.assertIn('"Study counts and due forecasts follow the configured rollover, "', settings)
        self.assertIn('"not calendar midnight. Events continue to use their civil-calendar date."', settings)
        self.assertIn('"Buried Cards"', settings)
        self.assertIn('"Today’s Progress"', settings)
        self.assertIn('"Show estimated completion time"', settings)
        self.assertNotIn('Show ETA in Today’s Progress', settings)
        self.assertIn('_section_title("New Cards Studied")', settings)
        self.assertNotIn("Pace history window", settings)
        self.assertNotIn("New-card time multiplier", settings)
        self.assertNotIn("Custom Anki search", settings)
        self.assertIn("def open_page", settings)
        self.assertIn("self._build_events_page()", settings)
        self.assertNotIn('QPushButton("Manage events & calendars")', settings)

    def test_settings_preview_uses_cached_live_snapshot_and_editors_are_themed(self) -> None:
        settings = (ROOT / "settings.py").read_text(encoding="utf-8")
        js = (ROOT / "web" / "dashboard.js").read_text(encoding="utf-8")
        self.assertIn("self.controller.snapshot or sample_snapshot()", settings)
        self.assertIn('self.preview_data_badge.setText("Cached live snapshot" if is_live else "Sample data")', settings)
        self.assertIn('self.setObjectName("HomeDashboardEditor")', settings)
        self.assertIn("QDialog#HomeDashboardEditor QLabel", settings)
        self.assertNotIn("self.setMinimumSize(1000, 680)", settings)
        self.assertIn('root.dataset.hdoPreview === "true"', js)
        self.assertIn('empty_reason: "preview_only"', js)
        self.assertIn("Already in Home Dashboard settings", js)

    def test_native_settings_use_palette_and_native_control_states(self) -> None:
        settings = (ROOT / "settings.py").read_text(encoding="utf-8")
        self.assertIn("QApplication.instance()", settings)
        self.assertIn('brush_color("highlight", "text")', settings)
        self.assertNotIn("palette.color(QPalette.ColorRole", settings)
        self.assertIn("def changeEvent", settings)
        self.assertIn("def _reapply_palette_style", settings)
        self.assertIn('getattr(widget, "_hdo_palette_style_active", False)', settings)
        self.assertIn("def _queue_palette_style", settings)
        self.assertIn("QTimer.singleShot(0, apply)", settings)
        self.assertIn("def _install_palette_watcher", settings)
        self.assertIn("timer.setInterval(250)", settings)
        self.assertNotIn("QCheckBox::indicator", settings)
        self.assertIn("QPushButton:disabled", settings)
        self.assertIn("QTreeWidget#ManagerTree::item:selected", settings)
        self.assertIn("QPushButton#DangerButton", settings)
        self.assertIn("QPushButton#DangerButton:disabled", settings)
        self.assertIn("QTreeWidget#ManagerTree QHeaderView::section", settings)
        self.assertIn("tree.setAlternatingRowColors(False)", settings)
        self.assertNotIn("tree.setAlternatingRowColors(True)", settings)

    def test_settings_full_screen_and_local_event_contracts(self) -> None:
        settings = (ROOT / "settings.py").read_text(encoding="utf-8")
        self.assertIn("if self.width() >= 1180", settings)
        self.assertIn("if self.width() >= 900", settings)
        self.assertIn("self.splitter.setStretchFactor(0, 56)", settings)
        self.assertIn("self.splitter.setStretchFactor(1, 44)", settings)
        self.assertIn('tree.setHeaderLabels(["Date", "Event"])', settings)
        self.assertIn('self.event_tabs.addTab(self.active_events, "Active (0)")', settings)
        self.assertIn('self.event_tabs.addTab(self.archived_events, "Archived (0)")', settings)
        self.assertIn('self.setMinimumWidth(680)', settings)
        self.assertIn("QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow", settings)
        self.assertIn('QPushButton("Use selected as current")', settings)
        self.assertIn('self.name.setCursorPosition(0)', settings)
        self.assertIn('self.quote_detail.setAccessibleName("Full selected verse")', settings)
        for section in ("Study metrics", "Pace & ETA", "New Cards Studied", "Compatibility", "Migration status", "Data & privacy", "Credits", "Rollback"):
            self.assertIn(section, settings)

    def test_calendar_lifecycle_and_keyboard_contracts_are_present(self) -> None:
        js = (ROOT / "web" / "dashboard.js").read_text(encoding="utf-8")
        for key in ("Home", "End", "PageUp", "PageDown", "Escape"):
            self.assertIn(key, js)
        self.assertIn("namespace.observer.disconnect()", js)
        self.assertIn("detailsPresentation(state.view, dashboardWidth(), calendarRegionWidth())", js)
        self.assertIn("var WIDE_DASHBOARD_MIN = 1150", js)
        self.assertIn("var WIDE_REGION_MIN = 1054", js)
        self.assertNotIn("detailsPresentation(state.view, global.innerWidth", js)
        self.assertIn("sidebarCollapsed(", js)
        self.assertNotIn("HDOOutsideClickHandler", js)
        self.assertNotIn("outsideClickHandler", js)
        self.assertNotIn("positionPopover", js)
        self.assertNotIn("rolloverExplanation", js)
        self.assertNotIn("focus()", js.split("function showDetails", 1)[1].split("function dayLabel", 1)[0])

    def test_calendar_polish_tokens_context_and_qa_hooks_are_present(self) -> None:
        renderer = (ROOT / "renderer.py").read_text(encoding="utf-8")
        css = (ROOT / "web" / "dashboard.css").read_text(encoding="utf-8")
        js = (ROOT / "web" / "dashboard.js").read_text(encoding="utf-8")
        for token in (
            "--hdo-control-height",
            "--hdo-calendar-gap",
            "--hdo-calendar-cell-radius",
            "--hdo-calendar-label-size",
            "--hdo-calendar-state-border",
            "--hdo-year-cell",
            "--hdo-month-cell-min",
        ):
            self.assertIn(token, renderer)
            self.assertIn(token, css)
        for field in (
            "data-hdo-summary-completed",
            "data-hdo-summary-new",
            "data-hdo-summary-due",
            "data-hdo-details-announcement",
        ):
            self.assertIn(field, renderer)
            self.assertIn(field, js)
        for field in (
            "data-hdo-day-insight",
            "data-hdo-insight-status",
            "data-hdo-insight-items",
        ):
            self.assertIn(field, renderer)
            self.assertIn(field, js)
        self.assertIn("dateDetailsViewModel", js)
        self.assertIn("namespace.qaSnapshot", js)
        self.assertIn("namespace.qaSetCalendarState", js)
        self.assertIn("global.__HDO_QA_ACTIVE__", js)
        self.assertIn("horizontalOverflow", js)
        self.assertIn("duplicateDates", js)

    def test_calendar_settings_and_events_use_requested_professional_hierarchy(self) -> None:
        settings = (ROOT / "settings.py").read_text(encoding="utf-8")
        for heading in ("Display", "Range & Forecast", "History Rules", "Deck Exclusions"):
            self.assertIn('_section_title("{}")'.format(heading), settings)
        self.assertIn('QPushButton("Exclude all shown")', settings)
        self.assertIn('QPushButton("Include all shown")', settings)
        self.assertIn('self.forecast_days.setEnabled(self.show_forecast.isChecked())', settings)
        self.assertIn('self.deck_exclusion_summary.setAccessibleName("Deck exclusion count")', settings)
        self.assertIn('self.event_add.setObjectName("PrimaryButton")', settings)
        self.assertIn('self.event_empty_state.setObjectName("EmptyState")', settings)
        self.assertIn('self.event_action_feedback.setAccessibleName("Event action confirmation")', settings)
        self.assertIn('self.event_add.setText("Add event for {}".format(display_date))', settings)
        self.assertIn('_display_date(event["date"])', settings)

    def test_external_calendar_work_is_source_only_and_package_excluded(self) -> None:
        controller = (ROOT / "controller.py").read_text(encoding="utf-8")
        manager = (ROOT / "event_manager.py").read_text(encoding="utf-8")
        repository = (ROOT / "calendar_repository.py").read_text(encoding="utf-8")
        js = (ROOT / "web" / "dashboard.js").read_text(encoding="utf-8")
        build = (ROOT / "tools" / "build_ankiaddon.py").read_text(encoding="utf-8")
        self.assertNotIn("calendar_repository", controller)
        self.assertNotIn("event_manager", controller)
        self.assertNotIn('command == "calendar_events_range"', controller)
        self.assertNotIn("namespace.receiveCalendarEvents", js)
        self.assertNotIn("sourceName.textContent", js)
        self.assertIn("calendar_sources.json", repository)
        self.assertIn("MAX_FEED_BYTES = 10 * 1024 * 1024", repository)
        self.assertIn("MAX_COMPONENTS = 50_000", repository)
        self.assertIn("MAX_RANGE_DAYS = 3660", repository)
        self.assertIn("_HttpsOnlyRedirectHandler", repository)
        self.assertIn("If-None-Match", repository)
        self.assertIn("If-Modified-Since", repository)
        self.assertIn('self.tabs.addTab(self.events_page, "Events")', manager)
        self.assertIn('self.tabs.addTab(self.calendars_page, "Calendars")', manager)
        self.assertIn("Every action is saved immediately", manager)
        self.assertIn("DEFERRED_SOURCE_FILES", build)
        self.assertIn('"calendar_repository.py"', build)
        self.assertIn('"event_manager.py"', build)
        self.assertIn('("_vendor/",)', build)
        package_allowlist = build.split("PACKAGE_FILES = [", 1)[1].split("]", 1)[0]
        self.assertNotIn('"calendar_repository.py"', package_allowlist)
        self.assertNotIn('"event_manager.py"', package_allowlist)
        self.assertNotIn('"vendor-requirements.lock"', package_allowlist)


if __name__ == "__main__":
    unittest.main()
