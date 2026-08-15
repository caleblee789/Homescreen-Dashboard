"""Local event ownership and read-only iCalendar source integration.

This module deliberately has no Qt or Anki imports.  Network and recurrence
expansion are synchronous here so callers can choose the appropriate background
operation primitive.  Registry/cache writes are atomic and subscription URLs are
never included in raised or persisted error text.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, replace
from datetime import date, datetime, time as datetime_time, timedelta
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import threading
import time
from typing import Any, Callable, Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse, urlunparse
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import uuid4


VENDOR_ROOT = Path(__file__).resolve().parent / "_vendor"
if str(VENDOR_ROOT) not in sys.path:
    # The release package carries exact pure-Python calendar dependencies.  They
    # live outside Anki's own package tree so calendar behavior cannot drift with
    # the host application's dependency set.
    sys.path.insert(0, str(VENDOR_ROOT))

try:
    from icalendar import Calendar
    import recurring_ical_events
except Exception as exc:  # pragma: no cover - exercised by exact-package QA.
    raise RuntimeError("Bundled iCalendar dependencies are unavailable") from exc

from .calendar_models import CalendarDayEvent, CalendarOccurrence


REGISTRY_VERSION = 1
CACHE_VERSION = 1
MAX_FEED_BYTES = 10 * 1024 * 1024
MAX_COMPONENTS = 50_000
MAX_OCCURRENCES = 20_000
MAX_RANGE_DAYS = 3660
REQUEST_TIMEOUT_SECONDS = 15
IMPORTED_TITLE_LIMIT = 500
ERROR_LIMIT = 300
CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]+")
URL_RE = re.compile(r"(?:https?|webcal)://[^\s]+", re.IGNORECASE)


class CalendarRepositoryError(RuntimeError):
    """Base error for source, parsing, and persistence failures."""


class CalendarLimitError(CalendarRepositoryError):
    """A source or requested range exceeded a documented safety limit."""


class CalendarSourceError(CalendarRepositoryError):
    """A file or URL source could not be read safely."""


@dataclass(frozen=True)
class FetchResponse:
    status: int
    data: bytes
    headers: Mapping[str, str]
    final_url: str


@dataclass(frozen=True)
class RefreshResult:
    source_id: str
    changed: bool
    success: bool
    message: str = ""


def _synchronized(method: Callable[..., Any]) -> Callable[..., Any]:
    def guarded(self: "CalendarRepository", *args: Any, **kwargs: Any) -> Any:
        with self._lock:
            return method(self, *args, **kwargs)

    guarded.__name__ = method.__name__
    guarded.__doc__ = method.__doc__
    return guarded


class _HttpsOnlyRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> Any:
        try:
            normalize_subscription_url(newurl)
        except CalendarSourceError as exc:
            raise CalendarSourceError("Calendar redirects must remain on HTTPS")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def normalize_subscription_url(raw_url: str) -> str:
    candidate = str(raw_url or "").strip()
    parsed = urlparse(candidate)
    if parsed.scheme.lower() == "webcal":
        parsed = parsed._replace(scheme="https")
        candidate = urlunparse(parsed)
        parsed = urlparse(candidate)
    if parsed.scheme.lower() != "https" or not parsed.netloc:
        raise CalendarSourceError("Calendar subscriptions require an HTTPS or webcal URL")
    if parsed.username or parsed.password:
        raise CalendarSourceError("Usernames and passwords in calendar URLs are not supported")
    return candidate


def redacted_subscription_url(raw_url: str) -> str:
    try:
        parsed = urlparse(normalize_subscription_url(raw_url))
    except CalendarSourceError:
        return "Private calendar URL"
    return "https://{}/…".format(parsed.hostname or parsed.netloc)


def _safe_error(exc: BaseException) -> str:
    if isinstance(exc, URLError):
        raw = "Network request failed: {}".format(getattr(exc, "reason", "connection error"))
    elif isinstance(exc, HTTPError):
        raw = "Calendar server returned HTTP {}".format(exc.code)
    else:
        raw = str(exc) or exc.__class__.__name__
    return URL_RE.sub("[calendar URL]", raw).strip()[:ERROR_LIMIT]


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path.parent, 0o700)
    except OSError:
        pass
    temporary = path.with_name("{}.{}.tmp".format(path.name, uuid4().hex))
    try:
        temporary.write_bytes(data)
        try:
            os.chmod(temporary, 0o600)
        except OSError:
            pass
        os.replace(str(temporary), str(path))
    finally:
        try:
            temporary.unlink()
        except OSError:
            pass


def _atomic_write_json(path: Path, value: Mapping[str, Any]) -> None:
    encoded = (json.dumps(dict(value), ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    _atomic_write_bytes(path, encoded)


def _read_limited(path: Path) -> bytes:
    try:
        with path.open("rb") as handle:
            data = handle.read(MAX_FEED_BYTES + 1)
    except OSError as exc:
        raise CalendarSourceError("Could not read the selected calendar file") from exc
    if len(data) > MAX_FEED_BYTES:
        raise CalendarLimitError("Calendar feeds are limited to 10 MiB")
    return data


def _clean_title(value: object, maximum: int = IMPORTED_TITLE_LIMIT) -> str:
    candidate = CONTROL_RE.sub(" ", str(value or ""))
    candidate = " ".join(candidate.split()).strip()
    return (candidate or "Untitled event")[:maximum]


def _clean_local_title(value: object) -> str:
    candidate = CONTROL_RE.sub(" ", str(value or ""))
    candidate = " ".join(candidate.split()).strip()
    if not candidate:
        raise CalendarRepositoryError("Event name is required")
    return candidate[:160]


def _decoded(component: Any, name: str) -> object:
    try:
        return component.decoded(name)
    except Exception:
        value = component.get(name)
        return getattr(value, "dt", value)


def _local_datetime(value: datetime) -> datetime:
    # astimezone() applies the operating system's rules for the represented
    # date.  For a naive/floating value Python intentionally assumes local time.
    return value.astimezone()


def _civil_span(component: Any) -> tuple[date, date]:
    raw_start = _decoded(component, "DTSTART")
    raw_end = _decoded(component, "DTEND")
    raw_duration = _decoded(component, "DURATION")
    if isinstance(raw_start, datetime):
        start_dt = _local_datetime(raw_start)
        if isinstance(raw_end, datetime):
            end_dt = _local_datetime(raw_end)
        elif isinstance(raw_end, date):
            end_dt = datetime.combine(raw_end, datetime_time.min).astimezone()
        elif isinstance(raw_duration, timedelta):
            end_dt = start_dt + raw_duration
        else:
            end_dt = start_dt
        start_date = start_dt.date()
        if end_dt <= start_dt:
            return start_date, start_date + timedelta(days=1)
        if end_dt.time() == datetime_time.min:
            exclusive = end_dt.date()
        else:
            exclusive = end_dt.date() + timedelta(days=1)
        return start_date, max(start_date + timedelta(days=1), exclusive)
    if isinstance(raw_start, date):
        if isinstance(raw_end, datetime):
            end_date = _local_datetime(raw_end).date()
        elif isinstance(raw_end, date):
            end_date = raw_end
        elif isinstance(raw_duration, timedelta):
            end_date = raw_start + raw_duration
        else:
            end_date = raw_start + timedelta(days=1)
        return raw_start, max(raw_start + timedelta(days=1), end_date)
    raise CalendarSourceError("A calendar event is missing a valid start date")


def _identity_value(value: object) -> str:
    candidate = getattr(value, "dt", value)
    if isinstance(candidate, datetime):
        return candidate.isoformat()
    if isinstance(candidate, date):
        return candidate.isoformat()
    return str(candidate or "")


def _property_values(value: object, key: str) -> List[object]:
    if not isinstance(value, Mapping):
        return []
    raw = value.get(key)
    if raw is None:
        return []
    if isinstance(raw, (list, tuple)):
        return list(raw)
    return [raw]


def _rdate_count(component: Any) -> int:
    values = component.get("RDATE")
    if values is None:
        return 0
    properties = values if isinstance(values, list) else [values]
    count = 0
    for prop in properties:
        dates = getattr(prop, "dts", None)
        count += len(dates) if dates is not None else 1
    return count


def _recurrence_upper_bound(component: Any, start: date, end: date) -> int:
    """Conservatively bound expansion before the recurrence library allocates it."""

    rule = component.get("RRULE")
    if not isinstance(rule, Mapping):
        try:
            component_start, component_end = _civil_span(component)
        except CalendarSourceError:
            return 0
        return (1 if component_start < end and component_end > start else 0) + _rdate_count(component)
    frequency_values = _property_values(rule, "FREQ")
    frequency = str(frequency_values[0]).upper() if frequency_values else "DAILY"
    interval_values = _property_values(rule, "INTERVAL")
    try:
        interval = max(1, int(interval_values[0])) if interval_values else 1
    except (TypeError, ValueError):
        interval = 1
    span_days = max(1, (end - start).days + 2)
    if frequency == "SECONDLY":
        base = span_days * 86_400 // interval + 2
    elif frequency == "MINUTELY":
        base = span_days * 1_440 // interval + 2
    elif frequency == "HOURLY":
        base = span_days * 24 // interval + 2
    elif frequency == "WEEKLY":
        base = (span_days // (7 * interval) + 2) * max(1, len(_property_values(rule, "BYDAY")))
    elif frequency == "MONTHLY":
        months = span_days // 28 + 2
        by_month_day = len(_property_values(rule, "BYMONTHDAY"))
        by_day = len(_property_values(rule, "BYDAY"))
        base = (months // interval + 1) * max(1, by_month_day, by_day * 5)
    elif frequency == "YEARLY":
        years = span_days // 365 + 2
        by_year_day = len(_property_values(rule, "BYYEARDAY"))
        by_month_day = len(_property_values(rule, "BYMONTHDAY"))
        by_day = len(_property_values(rule, "BYDAY"))
        base = (years // interval + 1) * max(1, by_year_day, by_month_day * 12, by_day * 53)
    else:
        base = span_days // interval + 2
    for key in ("BYHOUR", "BYMINUTE", "BYSECOND"):
        values = _property_values(rule, key)
        if values:
            base *= len(values)
    count_values = _property_values(rule, "COUNT")
    if count_values:
        try:
            base = min(base, max(0, int(count_values[0])))
        except (TypeError, ValueError):
            pass
    return base + _rdate_count(component)


class CalendarRepository:
    """Own local events and external, read-only iCalendar sources."""

    def __init__(
        self,
        user_files_dir: Path,
        config_getter: Optional[Callable[[], Mapping[str, Any]]] = None,
        config_writer: Optional[Callable[[Mapping[str, Any]], None]] = None,
        fetcher: Optional[Callable[[str, Mapping[str, str]], FetchResponse]] = None,
        today_provider: Callable[[], date] = date.today,
    ) -> None:
        self.user_files_dir = Path(user_files_dir)
        self.registry_path = self.user_files_dir / "calendar_sources.json"
        self.cache_dir = self.user_files_dir / "calendar_sources"
        self._config_getter = config_getter
        self._config_writer = config_writer
        self._fetcher = fetcher or self._default_fetch
        self._today = today_provider
        self._lock = threading.RLock()
        self._registry = self._load_registry()
        self._memory_cache: Dict[tuple[str, str, str, str], List[CalendarOccurrence]] = {}

    @staticmethod
    def empty_registry() -> Dict[str, Any]:
        return {"version": REGISTRY_VERSION, "sources": [], "hidden_occurrences": {}}

    def _load_registry(self) -> Dict[str, Any]:
        try:
            parsed = json.loads(self.registry_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return self.empty_registry()
        if not isinstance(parsed, Mapping) or parsed.get("version") != REGISTRY_VERSION:
            return self.empty_registry()
        sources = parsed.get("sources", [])
        hidden = parsed.get("hidden_occurrences", {})
        result = self.empty_registry()
        if isinstance(sources, list):
            result["sources"] = [deepcopy(dict(value)) for value in sources if isinstance(value, Mapping)]
        if isinstance(hidden, Mapping):
            result["hidden_occurrences"] = {
                str(key): deepcopy(dict(value))
                for key, value in hidden.items()
                if isinstance(key, str) and isinstance(value, Mapping)
            }
        return result

    def _persist_registry(self) -> None:
        _atomic_write_json(self.registry_path, self._registry)

    @_synchronized
    def list_sources(self) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for source in self._registry["sources"]:
            row = deepcopy(source)
            row["display_location"] = (
                redacted_subscription_url(str(row.get("url", "")))
                if row.get("kind") == "ics_url"
                else "Imported file snapshot"
            )
            row.pop("url", None)
            rows.append(row)
        return rows

    @_synchronized
    def source(self, source_id: str) -> Optional[Dict[str, Any]]:
        source = self._source_by_id(source_id)
        if source is None:
            return None
        row = deepcopy(source)
        row["display_location"] = (
            redacted_subscription_url(str(row.get("url", "")))
            if row.get("kind") == "ics_url"
            else "Imported file snapshot"
        )
        row.pop("url", None)
        return row

    def _source_by_id(self, source_id: str) -> Optional[MutableMapping[str, Any]]:
        for source in self._registry["sources"]:
            if str(source.get("id")) == str(source_id):
                return source
        return None

    def _source_dir(self, source_id: str) -> Path:
        # Source identifiers are registry data.  Hashing them keeps a damaged or
        # manually edited registry from ever influencing a filesystem path.
        directory = hashlib.sha256(str(source_id).encode("utf-8")).hexdigest()[:32]
        return self.cache_dir / directory

    def _generation_dir(self, source_id: str, content_sha256: str) -> Path:
        generation = str(content_sha256 or "uncommitted")
        if not re.fullmatch(r"[0-9a-f]{64}", generation):
            generation = hashlib.sha256(generation.encode("utf-8")).hexdigest()
        return self._source_dir(source_id) / generation

    def _raw_path(self, source_id: str, content_sha256: str) -> Path:
        return self._generation_dir(source_id, content_sha256) / "calendar.ics"

    def _occurrence_path(
        self,
        source_id: str,
        content_sha256: str,
        start: date,
        end: date,
    ) -> Path:
        return self._generation_dir(source_id, content_sha256) / "occurrences-{}-{}.json".format(
            start.isoformat(), end.isoformat()
        )

    def _default_range(self) -> tuple[date, date]:
        today = self._today()
        return today - timedelta(days=366), today + timedelta(days=367)

    @staticmethod
    def _validate_range(start: date, end: date) -> None:
        if end <= start:
            raise CalendarRepositoryError("Calendar date ranges must have a positive length")
        if (end - start).days > MAX_RANGE_DAYS:
            raise CalendarLimitError("Calendar date ranges are limited to ten years")

    def _parse_calendar(self, data: bytes) -> tuple[Any, str, int]:
        if len(data) > MAX_FEED_BYTES:
            raise CalendarLimitError("Calendar feeds are limited to 10 MiB")
        try:
            calendar = Calendar.from_ical(data)
        except Exception as exc:
            raise CalendarSourceError("The calendar data is not a valid iCalendar feed") from exc
        components = list(calendar.walk("VEVENT"))
        if len(components) > MAX_COMPONENTS:
            raise CalendarLimitError("Calendar feeds are limited to 50,000 events")
        raw_name = calendar.get("X-WR-CALNAME")
        calendar_name = _clean_title(raw_name, 120) if raw_name else ""
        return calendar, calendar_name, len(components)

    def _expand_source(
        self,
        data: bytes,
        source: Mapping[str, Any],
        start: date,
        end: date,
    ) -> tuple[str, int, List[CalendarOccurrence]]:
        self._validate_range(start, end)
        calendar, calendar_name, component_count = self._parse_calendar(data)
        expansion_bound = 0
        for component in calendar.walk("VEVENT"):
            expansion_bound += _recurrence_upper_bound(component, start, end)
            if expansion_bound > MAX_OCCURRENCES:
                raise CalendarLimitError(
                    "This calendar could produce more than 20,000 events in the selected range"
                )
        try:
            expanded = recurring_ical_events.of(calendar, skip_bad_series=False).between(start, end)
        except Exception as exc:
            raise CalendarSourceError("The calendar recurrence data could not be expanded") from exc
        if len(expanded) > MAX_OCCURRENCES:
            raise CalendarLimitError("This calendar produces more than 20,000 events in the selected range")
        source_id = str(source["id"])
        source_name = str(source.get("name") or calendar_name or "Imported calendar")
        occurrences: List[CalendarOccurrence] = []
        for component in expanded:
            if str(component.get("STATUS", "")).upper() == "CANCELLED":
                continue
            start_date, end_date = _civil_span(component)
            if start_date >= end or end_date <= start:
                continue
            raw_uid = str(component.get("UID", "")).strip()
            if raw_uid:
                series_id = raw_uid[:500]
            else:
                try:
                    material = component.to_ical()
                except Exception:
                    material = repr(component).encode("utf-8", errors="replace")
                series_id = "missing-uid-{}".format(hashlib.sha256(material).hexdigest()[:24])
            recurrence = component.get("RECURRENCE-ID")
            recurrence_identity = _identity_value(recurrence) or _identity_value(_decoded(component, "DTSTART"))
            occurrence_id = "occ-{}".format(
                hashlib.sha256(
                    "{}\0{}\0{}".format(source_id, series_id, recurrence_identity).encode("utf-8")
                ).hexdigest()[:24]
            )
            occurrences.append(
                CalendarOccurrence(
                    occurrence_id=occurrence_id,
                    name=_clean_title(component.get("SUMMARY")),
                    start_date=start_date.isoformat(),
                    end_date_exclusive=end_date.isoformat(),
                    source_id=source_id,
                    source_name=source_name,
                    series_id=series_id,
                    editable=False,
                )
            )
        occurrences.sort(key=lambda item: (item.start_date, item.name.casefold(), item.occurrence_id))
        return calendar_name, component_count, occurrences

    def _write_occurrence_cache(
        self,
        source: Mapping[str, Any],
        start: date,
        end: date,
        occurrences: Sequence[CalendarOccurrence],
    ) -> None:
        payload = {
            "version": CACHE_VERSION,
            "source_id": str(source["id"]),
            "content_sha256": str(source.get("content_sha256", "")),
            "start": start.isoformat(),
            "end": end.isoformat(),
            "occurrences": [asdict(item) for item in occurrences],
        }
        _atomic_write_json(
            self._occurrence_path(
                str(source["id"]),
                str(source.get("content_sha256", "")),
                start,
                end,
            ),
            payload,
        )

    def _read_occurrence_cache(
        self,
        source: Mapping[str, Any],
        start: date,
        end: date,
    ) -> Optional[List[CalendarOccurrence]]:
        generation_dir = self._generation_dir(
            str(source["id"]), str(source.get("content_sha256", ""))
        )
        exact = self._occurrence_path(
            str(source["id"]), str(source.get("content_sha256", "")), start, end
        )
        try:
            candidates = [exact] + sorted(
                path for path in generation_dir.glob("occurrences-*.json") if path != exact
            )
        except OSError:
            candidates = [exact]
        for candidate in candidates:
            try:
                parsed = json.loads(candidate.read_text(encoding="utf-8"))
                if not isinstance(parsed, Mapping):
                    continue
                cache_start = date.fromisoformat(str(parsed["start"]))
                cache_end = date.fromisoformat(str(parsed["end"]))
            except (OSError, ValueError, TypeError, KeyError):
                continue
            if (
                parsed.get("version") != CACHE_VERSION
                or str(parsed.get("source_id")) != str(source["id"])
                or str(parsed.get("content_sha256", "")) != str(source.get("content_sha256", ""))
                or cache_start > start
                or cache_end < end
            ):
                continue
            values = parsed.get("occurrences", [])
            if not isinstance(values, list):
                continue
            result: List[CalendarOccurrence] = []
            for value in values:
                if not isinstance(value, Mapping):
                    continue
                try:
                    occurrence = CalendarOccurrence(**dict(value))
                    occurrence_start = date.fromisoformat(occurrence.start_date)
                    occurrence_end = date.fromisoformat(occurrence.end_date_exclusive)
                except (TypeError, ValueError):
                    continue
                if occurrence_start < end and occurrence_end > start:
                    result.append(
                        replace(
                            occurrence,
                            source_name=str(source.get("name", occurrence.source_name)),
                        )
                    )
            return result
        return None

    def _query_source(
        self,
        source: Mapping[str, Any],
        start: date,
        end: date,
        cached_only: bool,
    ) -> List[CalendarOccurrence]:
        key = (str(source["id"]), str(source.get("content_sha256", "")), start.isoformat(), end.isoformat())
        if key in self._memory_cache:
            return [replace(item, source_name=str(source.get("name", item.source_name))) for item in self._memory_cache[key]]
        cached = self._read_occurrence_cache(source, start, end)
        if cached is not None:
            self._memory_cache[key] = cached
            return list(cached)
        if cached_only:
            return []
        try:
            data = _read_limited(
                self._raw_path(str(source["id"]), str(source.get("content_sha256", "")))
            )
            _calendar_name, _count, occurrences = self._expand_source(data, source, start, end)
        except CalendarRepositoryError:
            raise
        self._write_occurrence_cache(source, start, end, occurrences)
        self._memory_cache[key] = occurrences
        return list(occurrences)

    def _local_occurrences(self, start: date, end: date, include_archived: bool) -> List[CalendarOccurrence]:
        if self._config_getter is None:
            return []
        config = self._config_getter()
        items = config.get("events", {}).get("items", []) if isinstance(config, Mapping) else []
        result: List[CalendarOccurrence] = []
        for item in items if isinstance(items, list) else []:
            if not isinstance(item, Mapping):
                continue
            archived = bool(item.get("archived"))
            if archived and not include_archived:
                continue
            try:
                event_date = date.fromisoformat(str(item.get("date", "")))
            except ValueError:
                continue
            if not start <= event_date < end:
                continue
            event_id = str(item.get("id", ""))
            result.append(
                CalendarOccurrence(
                    occurrence_id=event_id,
                    name=str(item.get("name", "")),
                    start_date=event_date.isoformat(),
                    end_date_exclusive=(event_date + timedelta(days=1)).isoformat(),
                    source_id="local",
                    source_name="Local",
                    series_id=event_id,
                    editable=True,
                    archived=archived,
                )
            )
        return result

    @_synchronized
    def occurrences_between(
        self,
        start: date,
        end: date,
        *,
        include_archived: bool = True,
        include_hidden: bool = True,
        include_disabled: bool = False,
        cached_only: bool = False,
    ) -> List[CalendarOccurrence]:
        self._validate_range(start, end)
        hidden = self._registry["hidden_occurrences"]
        result = self._local_occurrences(start, end, include_archived)
        for source in self._registry["sources"]:
            if not source.get("enabled", True) and not include_disabled:
                continue
            for occurrence in self._query_source(source, start, end, cached_only):
                is_hidden = occurrence.occurrence_id in hidden
                if is_hidden and not include_hidden:
                    continue
                result.append(replace(occurrence, hidden=is_hidden))
        return sorted(result, key=lambda item: (item.start_date, item.name.casefold(), item.source_name.casefold()))

    @_synchronized
    def day_events_between(
        self,
        start: date,
        end: date,
        *,
        cached_only: bool = False,
        active_only: bool = True,
    ) -> List[CalendarDayEvent]:
        occurrences = self.occurrences_between(
            start,
            end,
            include_archived=False,
            include_hidden=False,
            cached_only=cached_only,
        )
        today = self._today()
        rows: Dict[tuple[str, str, str], CalendarDayEvent] = {}
        for occurrence in occurrences:
            occurrence_start = date.fromisoformat(occurrence.start_date)
            occurrence_end = date.fromisoformat(occurrence.end_date_exclusive)
            if active_only and occurrence_end <= today:
                continue
            cursor = max(start, occurrence_start, today if active_only else start)
            limit = min(end, occurrence_end)
            while cursor < limit:
                collapse_id = occurrence.series_id if occurrence.source_id != "local" else occurrence.occurrence_id
                key = (occurrence.source_id, collapse_id, cursor.isoformat())
                if key not in rows:
                    event_id = "day-{}".format(
                        hashlib.sha256("\0".join(key).encode("utf-8")).hexdigest()[:24]
                    )
                    rows[key] = CalendarDayEvent(
                        event_id=event_id,
                        occurrence_id=occurrence.occurrence_id,
                        name=occurrence.name,
                        date=cursor.isoformat(),
                        source_id=occurrence.source_id,
                        source_name=occurrence.source_name,
                        editable=occurrence.editable,
                    )
                cursor += timedelta(days=1)
        reverse = False
        if self._config_getter is not None:
            config = self._config_getter()
            reverse = config.get("events", {}).get("sort") == "descending" if isinstance(config, Mapping) else False
        return sorted(rows.values(), key=lambda item: (item.date, item.name.casefold()), reverse=reverse)

    def _source_template(self, source_id: str, kind: str, name: str, url: str = "") -> Dict[str, Any]:
        return {
            "id": source_id,
            "kind": kind,
            "name": _clean_title(name, 120),
            "enabled": True,
            "url": url,
            "created_at": _now_iso(),
            "last_checked_at": "",
            "last_success_at": "",
            "last_error": "",
            "etag": "",
            "last_modified": "",
            "content_sha256": "",
            "event_count": 0,
            "occurrence_count": 0,
        }

    def _store_validated_content(
        self,
        source: MutableMapping[str, Any],
        data: bytes,
        start: date,
        end: date,
    ) -> tuple[str, int, List[CalendarOccurrence]]:
        digest = hashlib.sha256(data).hexdigest()
        staged_source = deepcopy(source)
        staged_source["content_sha256"] = digest
        calendar_name, component_count, occurrences = self._expand_source(
            data, staged_source, start, end
        )
        # A complete digest-addressed generation is written before the registry
        # begins pointing at it.  A process interruption therefore leaves the
        # previous generation readable as the last-good cache.
        generation_dir = self._generation_dir(str(source["id"]), digest)
        generation_dir.mkdir(parents=True, exist_ok=True)
        for directory in (self.cache_dir, self._source_dir(str(source["id"])), generation_dir):
            try:
                os.chmod(directory, 0o700)
            except OSError:
                pass
        _atomic_write_bytes(self._raw_path(str(source["id"]), digest), data)
        self._write_occurrence_cache(staged_source, start, end, occurrences)
        source["content_sha256"] = digest
        source["event_count"] = component_count
        source["occurrence_count"] = len(occurrences)
        self._memory_cache.clear()
        return calendar_name, component_count, occurrences

    @_synchronized
    def import_file(self, path: Path, name: str = "") -> Dict[str, Any]:
        source_path = Path(path)
        data = _read_limited(source_path)
        source_id = "source-{}".format(uuid4().hex)
        provisional_name = name.strip() or source_path.stem or "Imported calendar"
        source = self._source_template(source_id, "ics_file", provisional_name)
        start, end = self._default_range()
        calendar_name, _count, _occurrences = self._store_validated_content(source, data, start, end)
        if not name.strip() and calendar_name:
            source["name"] = calendar_name
            # Cache metadata should reflect the final user-visible source name.
            self._write_occurrence_cache(
                source,
                start,
                end,
                [replace(value, source_name=calendar_name) for value in _occurrences],
            )
        stamp = _now_iso()
        source.update(last_checked_at=stamp, last_success_at=stamp, last_error="")
        self._registry["sources"].append(source)
        self._persist_registry()
        return self.source(source_id) or {}

    def _default_fetch(self, url: str, headers: Mapping[str, str]) -> FetchResponse:
        request_headers = {
            "Accept": "text/calendar, application/ics;q=0.9, */*;q=0.1",
            "User-Agent": "Home-Dashboard-Overhaul/1.6.0",
        }
        request_headers.update({str(key): str(value) for key, value in headers.items()})
        request = Request(normalize_subscription_url(url), headers=request_headers, method="GET")
        opener = build_opener(_HttpsOnlyRedirectHandler())
        try:
            with opener.open(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                final_url = response.geturl()
                normalize_subscription_url(final_url)
                data = response.read(MAX_FEED_BYTES + 1)
                if len(data) > MAX_FEED_BYTES:
                    raise CalendarLimitError("Calendar feeds are limited to 10 MiB")
                response_headers = {str(key): str(value) for key, value in response.headers.items()}
                return FetchResponse(int(getattr(response, "status", 200)), data, response_headers, final_url)
        except HTTPError as exc:
            if exc.code == 304:
                return FetchResponse(304, b"", {str(key): str(value) for key, value in exc.headers.items()}, url)
            raise CalendarSourceError(_safe_error(exc)) from exc
        except CalendarRepositoryError:
            raise
        except (OSError, URLError) as exc:
            raise CalendarSourceError(_safe_error(exc)) from exc

    @staticmethod
    def _header(headers: Mapping[str, str], name: str) -> str:
        target = name.casefold()
        for key, value in headers.items():
            if str(key).casefold() == target:
                return str(value)[:500]
        return ""

    @_synchronized
    def subscribe_url(self, url: str, name: str = "") -> Dict[str, Any]:
        try:
            normalized_url = normalize_subscription_url(url)
            response = self._fetcher(normalized_url, {})
            if response.status != 200:
                raise CalendarSourceError("Calendar server returned HTTP {}".format(response.status))
            normalize_subscription_url(response.final_url)
            source_id = "source-{}".format(uuid4().hex)
            host = urlparse(normalized_url).hostname or "Subscribed calendar"
            source = self._source_template(source_id, "ics_url", name.strip() or host, normalized_url)
            start, end = self._default_range()
            calendar_name, _count, occurrences = self._store_validated_content(source, response.data, start, end)
            if not name.strip() and calendar_name:
                source["name"] = calendar_name
                self._write_occurrence_cache(
                    source,
                    start,
                    end,
                    [replace(value, source_name=calendar_name) for value in occurrences],
                )
            stamp = _now_iso()
            source.update(
                last_checked_at=stamp,
                last_success_at=stamp,
                last_error="",
                etag=self._header(response.headers, "ETag"),
                last_modified=self._header(response.headers, "Last-Modified"),
            )
            self._registry["sources"].append(source)
            self._persist_registry()
            return self.source(source_id) or {}
        except CalendarLimitError:
            raise
        except Exception as exc:
            raise CalendarSourceError(_safe_error(exc)) from exc

    @_synchronized
    def refresh_source(
        self,
        source_id: str,
        *,
        replacement_file: Optional[Path] = None,
        replacement_url: str = "",
    ) -> RefreshResult:
        source = self._source_by_id(source_id)
        if source is None:
            return RefreshResult(source_id, False, False, "Calendar source was not found")
        previous_digest = str(source.get("content_sha256", ""))
        checked_at = _now_iso()
        try:
            staged_source = deepcopy(source)
            headers: Dict[str, str] = {}
            if source.get("kind") == "ics_file":
                data = (
                    _read_limited(Path(replacement_file))
                    if replacement_file is not None
                    else _read_limited(
                        self._raw_path(source_id, str(source.get("content_sha256", "")))
                    )
                )
                response_headers: Mapping[str, str] = {}
            else:
                url = normalize_subscription_url(replacement_url) if replacement_url else str(source.get("url", ""))
                if not replacement_url:
                    if source.get("etag"):
                        headers["If-None-Match"] = str(source["etag"])
                    if source.get("last_modified"):
                        headers["If-Modified-Since"] = str(source["last_modified"])
                response = self._fetcher(url, headers)
                normalize_subscription_url(response.final_url)
                if response.status == 304:
                    source.update(last_checked_at=checked_at, last_error="")
                    self._persist_registry()
                    return RefreshResult(source_id, False, True, "Calendar is already up to date")
                if response.status != 200:
                    raise CalendarSourceError("Calendar server returned HTTP {}".format(response.status))
                data = response.data
                response_headers = response.headers
                if replacement_url:
                    staged_source["url"] = url
            start, end = self._default_range()
            self._store_validated_content(staged_source, data, start, end)
            staged_source.update(
                last_checked_at=checked_at,
                last_success_at=checked_at,
                last_error="",
            )
            if staged_source.get("kind") == "ics_url":
                staged_source["etag"] = self._header(response_headers, "ETag")
                staged_source["last_modified"] = self._header(response_headers, "Last-Modified")
            source.clear()
            source.update(staged_source)
            self._persist_registry()
            changed = previous_digest != str(source.get("content_sha256", ""))
            self._remove_inactive_generations(source_id, str(source.get("content_sha256", "")))
            return RefreshResult(source_id, changed, True, "Calendar refreshed")
        except Exception as exc:
            message = _safe_error(exc)
            source.update(last_checked_at=checked_at, last_error=message)
            self._persist_registry()
            return RefreshResult(source_id, False, False, message)

    @_synchronized
    def refresh_subscriptions(self) -> List[RefreshResult]:
        return [
            self.refresh_source(str(source["id"]))
            for source in list(self._registry["sources"])
            if source.get("kind") == "ics_url" and source.get("enabled", True)
        ]

    @_synchronized
    def rename_source(self, source_id: str, name: str) -> bool:
        source = self._source_by_id(source_id)
        cleaned = _clean_title(name, 120)
        if source is None or not cleaned:
            return False
        source["name"] = cleaned
        self._memory_cache.clear()
        self._persist_registry()
        return True

    @_synchronized
    def set_source_enabled(self, source_id: str, enabled: bool) -> bool:
        source = self._source_by_id(source_id)
        if source is None:
            return False
        source["enabled"] = bool(enabled)
        self._persist_registry()
        return True

    @_synchronized
    def remove_source(self, source_id: str) -> bool:
        source = self._source_by_id(source_id)
        if source is None:
            return False
        self._registry["sources"].remove(source)
        hidden = self._registry["hidden_occurrences"]
        for occurrence_id in [key for key, value in hidden.items() if value.get("source_id") == source_id]:
            hidden.pop(occurrence_id, None)
        self._persist_registry()
        try:
            shutil.rmtree(self._source_dir(source_id))
        except OSError:
            pass
        self._memory_cache.clear()
        return True

    def _remove_inactive_generations(self, source_id: str, active_digest: str) -> None:
        source_dir = self._source_dir(source_id)
        try:
            children = list(source_dir.iterdir())
        except OSError:
            return
        for child in children:
            if child.name == active_digest or not child.is_dir():
                continue
            try:
                shutil.rmtree(child)
            except OSError:
                pass

    @_synchronized
    def set_hidden(self, occurrence: CalendarOccurrence, hidden: bool) -> bool:
        if occurrence.source_id == "local":
            return False
        values = self._registry["hidden_occurrences"]
        if hidden:
            values[occurrence.occurrence_id] = {
                "source_id": occurrence.source_id,
                "name": occurrence.name,
                "start_date": occurrence.start_date,
            }
        else:
            values.pop(occurrence.occurrence_id, None)
        self._persist_registry()
        return True

    @_synchronized
    def reset_hidden(self, source_id: str) -> int:
        values = self._registry["hidden_occurrences"]
        targets = [key for key, value in values.items() if value.get("source_id") == source_id]
        for key in targets:
            values.pop(key, None)
        if targets:
            self._persist_registry()
        return len(targets)

    def _mutate_local(self, callback: Callable[[List[Dict[str, Any]]], Any]) -> Any:
        if self._config_getter is None or self._config_writer is None:
            raise CalendarRepositoryError("Local event persistence is unavailable")
        config = deepcopy(dict(self._config_getter()))
        events = config.setdefault("events", {}).setdefault("items", [])
        if not isinstance(events, list):
            events = []
            config["events"]["items"] = events
        result = callback(events)
        self._config_writer(config)
        return result

    @_synchronized
    def add_local(self, name: str, event_date: str) -> str:
        cleaned = _clean_local_title(name)
        parsed_date = date.fromisoformat(event_date).isoformat()
        event_id = "event-{}".format(time.time_ns())

        def mutate(events: List[Dict[str, Any]]) -> None:
            events.append(
                {
                    "id": event_id,
                    "name": cleaned,
                    "date": parsed_date,
                    "archived": False,
                    "created_at": _now_iso(),
                    "archived_at": "",
                }
            )

        self._mutate_local(mutate)
        return event_id

    @_synchronized
    def edit_local(self, event_id: str, name: str, event_date: str) -> bool:
        cleaned = _clean_local_title(name)
        parsed_date = date.fromisoformat(event_date).isoformat()

        def mutate(events: List[Dict[str, Any]]) -> bool:
            for item in events:
                if str(item.get("id")) == str(event_id):
                    item["name"] = cleaned
                    item["date"] = parsed_date
                    return True
            return False

        return bool(self._mutate_local(mutate))

    @_synchronized
    def duplicate_local(self, event_id: str) -> Optional[str]:
        duplicate_id = "event-{}".format(time.time_ns())

        def mutate(events: List[Dict[str, Any]]) -> Optional[str]:
            for item in events:
                if str(item.get("id")) == str(event_id):
                    copied = deepcopy(item)
                    copied.update(id=duplicate_id, archived=False, archived_at="", created_at=_now_iso())
                    events.append(copied)
                    return duplicate_id
            return None

        return self._mutate_local(mutate)

    @_synchronized
    def set_local_archived(self, event_ids: Iterable[str], archived: bool) -> int:
        targets = {str(value) for value in event_ids}

        def mutate(events: List[Dict[str, Any]]) -> int:
            changed = 0
            for item in events:
                if str(item.get("id")) not in targets or bool(item.get("archived")) == archived:
                    continue
                item["archived"] = archived
                item["archived_at"] = _now_iso() if archived else ""
                changed += 1
            return changed

        return int(self._mutate_local(mutate))

    @_synchronized
    def delete_local(self, event_ids: Iterable[str]) -> int:
        targets = {str(value) for value in event_ids}

        def mutate(events: List[Dict[str, Any]]) -> int:
            before = len(events)
            events[:] = [item for item in events if str(item.get("id")) not in targets]
            return before - len(events)

        return int(self._mutate_local(mutate))
