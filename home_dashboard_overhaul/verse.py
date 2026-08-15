"""Safe Bible verse rendering and restart-safe rotation."""

from __future__ import annotations

from datetime import datetime
import hashlib
import html
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import random
import re
from typing import Callable, Iterable, List, Optional, Tuple

from .models import VerseContent


STATE_VERSION = 1
MAX_VERSE_CHARS = 4000
MAX_VERSE_BYTES = 16000
ALLOWED_CONTAINER_TAGS = {"b", "strong", "i", "em"}
REFERENCE_RE = re.compile(
    r"^(?P<body>.*?)(?:<br\s*/?>|\r?\n)\s*[-\u2013\u2014]?\s*"
    r"(?P<reference>(?:[1-3]\s+)?[A-Za-z][^<\n]{0,80}\s+\d+:\d+"
    r"(?:[-\u2013]\d+)?(?:\s+\([^)]+\))?)\s*$",
    re.IGNORECASE | re.DOTALL,
)


def verse_within_limit(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) <= MAX_VERSE_CHARS
        and len(value.encode("utf-8")) <= MAX_VERSE_BYTES
    )


def bounded_verse_text(value: object) -> str:
    if not isinstance(value, str) or verse_within_limit(value):
        return value if isinstance(value, str) else ""
    candidate = value[:MAX_VERSE_CHARS]
    while candidate and len(candidate.encode("utf-8")) > MAX_VERSE_BYTES - 3:
        candidate = candidate[:-1]
    return candidate.rstrip() + "…"


class _VerseHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.parts: List[str] = []

    def handle_starttag(self, tag: str, attrs: object) -> None:
        normalized = tag.lower()
        if not attrs and normalized == "br":
            self.parts.append("<br>")
        elif not attrs and normalized in ALLOWED_CONTAINER_TAGS:
            self.parts.append("<{}>".format(normalized))
        else:
            self.parts.append(html.escape(self.get_starttag_text() or "", quote=False))

    def handle_startendtag(self, tag: str, attrs: object) -> None:
        if tag.lower() == "br" and not attrs:
            self.parts.append("<br>")
        else:
            self.parts.append(html.escape(self.get_starttag_text() or "", quote=False))

    def handle_endtag(self, tag: str) -> None:
        normalized = tag.lower()
        if normalized in ALLOWED_CONTAINER_TAGS:
            self.parts.append("</{}>".format(normalized))
        else:
            self.parts.append(html.escape("</{}>".format(tag), quote=False))

    def handle_data(self, data: str) -> None:
        self.parts.append(html.escape(data, quote=False))

    def handle_entityref(self, name: str) -> None:
        self.parts.append(html.escape(html.unescape("&{};".format(name)), quote=False))

    def handle_charref(self, name: str) -> None:
        self.parts.append(html.escape(html.unescape("&#{};".format(name)), quote=False))

    def handle_comment(self, data: str) -> None:
        self.parts.append(html.escape("<!--{}-->".format(data), quote=False))


def sanitize_verse_html(value: object) -> str:
    if not isinstance(value, str):
        return ""
    parser = _VerseHTMLParser()
    try:
        parser.feed(value)
        parser.close()
    except (AssertionError, ValueError):
        return html.escape(value, quote=False)
    return "".join(parser.parts)


def split_quote_reference(value: object) -> Tuple[str, str]:
    if not isinstance(value, str):
        return "", ""
    candidate = value.strip()
    match = REFERENCE_RE.match(candidate)
    if not match:
        return candidate, ""
    body = match.group("body").strip()
    reference = match.group("reference").strip()
    return (body, reference) if body and reference else (candidate, "")


def verse_content(value: object) -> VerseContent:
    body, reference = split_quote_reference(bounded_verse_text(value))
    return VerseContent(sanitize_verse_html(body), sanitize_verse_html(reference))


def quote_fingerprint(quotes: Iterable[str]) -> str:
    digest = hashlib.sha256()
    for quote in quotes:
        encoded = quote.encode("utf-8")
        digest.update(str(len(encoded)).encode("ascii"))
        digest.update(b":")
        digest.update(encoded)
    return digest.hexdigest()


class QuoteRotator:
    def __init__(
        self,
        state_path: Path,
        now: Callable[[], datetime] = datetime.now,
        choose: Callable[[List[str]], str] = random.choice,
    ) -> None:
        self.state_path = state_path
        self.now = now
        self.choose = choose
        self._memory_key = ""
        self._memory_quote = ""
        self._memory_fingerprint = ""

    def _refresh_key(self, mode: str) -> str:
        if mode == "daily":
            current = self.now()
            if current.tzinfo is not None:
                current = current.astimezone()
            return "daily:{}".format(current.date().isoformat())
        return "manual"

    def get_quote(self, quotes: List[str], mode: str) -> str:
        if not quotes:
            return ""
        if mode == "every render":
            return self.choose(quotes)
        refresh_key = self._refresh_key(mode)
        fingerprint = quote_fingerprint(quotes)
        if (
            self._memory_quote in quotes
            and self._memory_key == refresh_key
            and self._memory_fingerprint == fingerprint
        ):
            return self._memory_quote
        state = self._load()
        if (
            state
            and state.get("version") == STATE_VERSION
            and state.get("refresh_key") == refresh_key
            and state.get("quote_fingerprint") == fingerprint
            and state.get("quote") in quotes
        ):
            quote = str(state["quote"])
        else:
            quote = self.choose(quotes)
            self._write(refresh_key, fingerprint, quote)
        self._memory_key = refresh_key
        self._memory_fingerprint = fingerprint
        self._memory_quote = quote
        return quote

    def clear(self, persistent: bool = True) -> None:
        self._memory_key = self._memory_quote = self._memory_fingerprint = ""
        if persistent:
            for path in (self.state_path, self.state_path.with_suffix(self.state_path.suffix + ".tmp")):
                try:
                    path.unlink()
                except OSError:
                    pass

    def set_quote(self, quotes: List[str], mode: str, quote: str) -> bool:
        """Persist an explicit current choice for daily or manual rotation."""
        if mode == "every render" or not quotes or quote not in quotes:
            return False
        refresh_key = self._refresh_key(mode)
        fingerprint = quote_fingerprint(quotes)
        self._write(refresh_key, fingerprint, quote)
        self._memory_key = refresh_key
        self._memory_fingerprint = fingerprint
        self._memory_quote = quote
        return True

    def _load(self) -> Optional[dict]:
        try:
            parsed = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return None
        return parsed if isinstance(parsed, dict) else None

    def _write(self, key: str, fingerprint: str, quote: str) -> None:
        state = {
            "version": STATE_VERSION,
            "refresh_key": key,
            "quote_fingerprint": fingerprint,
            "quote": quote,
        }
        temporary = self.state_path.with_suffix(self.state_path.suffix + ".tmp")
        try:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            os.replace(str(temporary), str(self.state_path))
        except OSError:
            try:
                temporary.unlink()
            except OSError:
                pass


def load_default_quotes(path: Path) -> List[str]:
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return []
    if isinstance(parsed, dict):
        parsed = parsed.get("quote", [])
    if not isinstance(parsed, list):
        return []
    return [value.strip() for value in parsed if isinstance(value, str) and value.strip()][:500]
