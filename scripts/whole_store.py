#!/usr/bin/env python3
"""Whole's redacted SQLite evidence store.

The privacy boundary is deliberately before every durable database write.
Raw observations are accepted in memory, normalized, redacted, and only then
inserted. Original sensitive values are never stored in SQLite.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


class RedactionFailure(ValueError):
    """Raised when an observation cannot be sanitized safely."""


# Conservative, high-signal credential families. Whole's tests are the contract;
# extend this list as providers appear rather than importing Hermes at runtime.
_PREFIX_RE = re.compile(
    r"(?:"
    r"sk-(?:or-v1-)?[A-Za-z0-9_-]{10,}|"
    r"github_pat_[A-Za-z0-9_]{10,}|gh[pousr]_[A-Za-z0-9]{10,}|"
    r"xox[baprs]-[A-Za-z0-9-]{10,}|"
    r"AIza[A-Za-z0-9_-]{30,}|xai-[A-Za-z0-9]{20,}|"
    r"hf_[A-Za-z0-9]{10,}|npm_[A-Za-z0-9]{10,}|pypi-[A-Za-z0-9_-]{10,}|"
    r"AKIA[A-Z0-9]{16}|sk_(?:live|test)_[A-Za-z0-9]{10,}"
    r")"
)
_EMAIL_RE = re.compile(r"(?<![\w.+-])[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}(?![\w.-])", re.I)
_PHONE_RE = re.compile(r"(?<!\w)(?:\+?1[ .()-]*)?(?:\(?\d{3}\)?[ .-]*)\d{3}[ .-]*\d{4}(?!\w)")
_ENV_RE = re.compile(
    r"\b([A-Z][A-Z0-9_]{0,64}(?:API_?KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL|AUTH)[A-Z0-9_]*)\s*=\s*([^\s]+)"
)
_SENSITIVE_QUERY = {
    "access_token": "ACCESS_TOKEN",
    "refresh_token": "REFRESH_TOKEN",
    "id_token": "ID_TOKEN",
    "token": "TOKEN",
    "api_key": "API_KEY",
    "apikey": "API_KEY",
    "client_secret": "CLIENT_SECRET",
    "password": "PASSWORD",
    "auth": "AUTHORIZATION",
    "jwt": "JWT",
    "secret": "SECRET",
    "code": "OAUTH_CODE",
    "signature": "SIGNATURE",
    "x-amz-signature": "SIGNATURE",
}
_SURFACES = (
    (("touch id", "password"), "credential_settings", "[CREDENTIAL_SETTINGS]"),
    (("autofill",), "autofill", "[AUTOFILL]"),
    (("stripe checkout",), "payment_flow", "[PAYMENT_FLOW]"),
    (("authorize",), "authorization_flow", "[AUTHORIZATION_FLOW]"),
    (("wants additional access",), "authorization_flow", "[AUTHORIZATION_FLOW]"),
)
_EVENT_TEXT_FIELDS = ("title", "detail", "session_id", "path")


def _redact_urls(text: str) -> Tuple[str, Set[str]]:
    kinds: Set[str] = set()
    # Window titles may contain prose around a URL. Replace URL tokens in place.
    url_re = re.compile(r"https?://[^\s]+")

    def replace(match: re.Match) -> str:
        raw = match.group(0)
        try:
            parts = urlsplit(raw)
            changed = False
            query = []
            for key, value in parse_qsl(parts.query, keep_blank_values=True):
                marker = _SENSITIVE_QUERY.get(key.lower())
                if marker is not None:
                    value = f"[{marker}]"
                    kinds.add(marker.lower())
                    changed = True
                query.append((key, value))
            if not changed:
                return raw
            return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query, safe="[]"), parts.fragment))
        except Exception as exc:
            raise RedactionFailure(f"URL sanitization failed: {exc}")

    return url_re.sub(replace, text), kinds


def sanitize_text(value: str) -> Tuple[str, Set[str]]:
    if not isinstance(value, str):
        raise RedactionFailure("text field was not a string")
    text, kinds = _redact_urls(value)

    def env_replace(match: re.Match) -> str:
        name = match.group(1)
        upper = name.upper()
        if "API_KEY" in upper or "APIKEY" in upper or upper.endswith("_KEY"):
            kind, marker = "api_key", "API_KEY"
        elif "TOKEN" in upper:
            kind, marker = "token", "TOKEN"
        elif "PASSWORD" in upper or "PASSWD" in upper:
            kind, marker = "password", "PASSWORD"
        else:
            kind, marker = "credential", "CREDENTIAL"
        kinds.add(kind)
        return f"{name}=[{marker}]"

    text = _ENV_RE.sub(env_replace, text)
    if _PREFIX_RE.search(text):
        text = _PREFIX_RE.sub("[API_KEY]", text)
        kinds.add("api_key")
    if _EMAIL_RE.search(text):
        text = _EMAIL_RE.sub("[EMAIL]", text)
        kinds.add("email")
    if _PHONE_RE.search(text):
        text = _PHONE_RE.sub("[PHONE_NUMBER]", text)
        kinds.add("phone_number")
    return text, kinds


def redact_event(raw: Dict[str, Any]) -> Tuple[Dict[str, Any], List[Dict[str, str]]]:
    if not isinstance(raw, dict):
        raise RedactionFailure("event was not an object")
    event = dict(raw)
    redactions: List[Dict[str, str]] = []
    app = event.get("app")
    title = event.get("title")
    if app is not None and not isinstance(app, str):
        raise RedactionFailure("app field was not a string")

    # Source-aware replacement prevents contact identifiers from becoming a
    # durable title while preserving the fact that Messages was foreground.
    if (
        app == "com.apple.MobileSMS"
        and isinstance(title, str)
        and title.strip()
        and title != "[CONTACT]"
    ):
        event["title"] = "[CONTACT]"
        redactions.append({"field": "title", "kind": "contact", "replacement": "[CONTACT]"})
    elif (
        isinstance(title, str)
        and not (title.startswith("[") and title.endswith("]"))
    ):
        lowered = title.lower()
        for tokens, kind, replacement in _SURFACES:
            if all(token in lowered for token in tokens):
                event["title"] = replacement
                redactions.append({"field": "title", "kind": kind, "replacement": replacement})
                break

    for field in _EVENT_TEXT_FIELDS:
        value = event.get(field)
        if value is None:
            continue
        if not isinstance(value, str):
            raise RedactionFailure(f"{field} field was not a string")
        sanitized, kinds = sanitize_text(value)
        event[field] = sanitized
        for kind in sorted(kinds):
            redactions.append({"field": field, "kind": kind, "replacement": f"[{kind.upper()}]"})

    ts = event.get("ts")
    source = event.get("source")
    if not isinstance(ts, str) or not ts.strip():
        raise RedactionFailure("event has no timestamp")
    try:
        datetime.fromisoformat(ts)
    except ValueError as exc:
        raise RedactionFailure(f"invalid timestamp: {exc}")
    if not isinstance(source, str) or not source.strip():
        raise RedactionFailure("event has no source")
    return event, redactions


_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sources (
    source_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS events (
    event_id INTEGER PRIMARY KEY,
    observed_at TEXT NOT NULL,
    source_id INTEGER NOT NULL REFERENCES sources(source_id),
    app TEXT,
    title TEXT,
    detail TEXT,
    session_id TEXT,
    path TEXT,
    provenance TEXT NOT NULL DEFAULT 'observed' CHECK (provenance IN ('observed','normalized','redacted','inferred')),
    event_hash TEXT NOT NULL UNIQUE,
    redaction_count INTEGER NOT NULL DEFAULT 0,
    imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_events_time ON events(observed_at);
CREATE INDEX IF NOT EXISTS idx_events_app_time ON events(app, observed_at);
CREATE TABLE IF NOT EXISTS redactions (
    redaction_id INTEGER PRIMARY KEY,
    event_id INTEGER NOT NULL REFERENCES events(event_id) ON DELETE CASCADE,
    field TEXT NOT NULL,
    kind TEXT NOT NULL,
    replacement TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_redactions_event ON redactions(event_id);
CREATE TABLE IF NOT EXISTS segments (
    segment_id INTEGER PRIMARY KEY,
    event_id INTEGER NOT NULL REFERENCES events(event_id) ON DELETE CASCADE,
    start_at TEXT NOT NULL,
    end_at TEXT NOT NULL,
    duration_seconds INTEGER NOT NULL CHECK (duration_seconds >= 0),
    state TEXT NOT NULL CHECK (state IN ('active','unknown')),
    app TEXT,
    title TEXT
);
CREATE INDEX IF NOT EXISTS idx_segments_time ON segments(start_at, end_at);
CREATE VIRTUAL TABLE IF NOT EXISTS events_fts USING fts5(
    event_id UNINDEXED,
    app,
    title,
    detail,
    path
);
"""


class Store:
    def __init__(self, path: Path):
        self.path = Path(path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path), timeout=10.0)
        self.conn.execute("PRAGMA foreign_keys=ON")
        try:
            self.conn.execute("PRAGMA journal_mode=WAL")
        except sqlite3.DatabaseError:
            self.conn.execute("PRAGMA journal_mode=DELETE")
        self.conn.executescript(_SCHEMA)
        self.conn.execute("INSERT OR REPLACE INTO schema_meta(key,value) VALUES('schema_version','1')")
        self.conn.commit()

    def close(self) -> None:
        if self.conn is not None:
            self.conn.close()
            self.conn = None  # type: ignore[assignment]

    @staticmethod
    def _event_hash(event: Dict[str, Any]) -> str:
        """Stable idempotency key derived only from sanitized persisted fields."""
        persisted = {
            key: event.get(key)
            for key in ("ts", "source", "app", "title", "detail", "session_id", "path")
        }
        canonical = json.dumps(persisted, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def ingest(self, raw: Dict[str, Any]) -> int:
        # Sanitization must complete before BEGIN: any redaction failure leaves
        # no partial row, raw-derived hash, or raw text in SQLite's journal/WAL.
        event, redactions = redact_event(raw)
        event_hash = self._event_hash(event)
        existing = self.conn.execute("SELECT event_id FROM events WHERE event_hash=?", (event_hash,)).fetchone()
        if existing:
            return int(existing[0])
        source = event["source"]
        provenance = "redacted" if redactions else "observed"
        with self.conn:
            self.conn.execute("INSERT OR IGNORE INTO sources(name) VALUES(?)", (source,))
            source_id = self.conn.execute("SELECT source_id FROM sources WHERE name=?", (source,)).fetchone()[0]
            cur = self.conn.execute(
                """INSERT INTO events(
                    observed_at,source_id,app,title,detail,session_id,path,
                    provenance,event_hash,redaction_count
                ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (
                    event["ts"], source_id, event.get("app"), event.get("title"),
                    event.get("detail"), event.get("session_id"), event.get("path"),
                    provenance, event_hash, len(redactions),
                ),
            )
            event_id = int(cur.lastrowid)
            for item in redactions:
                self.conn.execute(
                    "INSERT INTO redactions(event_id,field,kind,replacement) VALUES(?,?,?,?)",
                    (event_id, item["field"], item["kind"], item["replacement"]),
                )
            self.conn.execute(
                "INSERT INTO events_fts(event_id,app,title,detail,path) VALUES(?,?,?,?,?)",
                (event_id, event.get("app") or "", event.get("title") or "", event.get("detail") or "", event.get("path") or ""),
            )
        return event_id

    def import_jsonl(self, path: Path) -> Dict[str, int]:
        counts = {"read": 0, "inserted": 0, "duplicates": 0, "malformed": 0}
        with Path(path).open(encoding="utf-8", errors="strict") as handle:
            for line in handle:
                if not line.strip():
                    continue
                counts["read"] += 1
                try:
                    raw = json.loads(line)
                    sanitized, _ = redact_event(raw)
                    event_hash = self._event_hash(sanitized)
                    before = self.conn.execute("SELECT 1 FROM events WHERE event_hash=?", (event_hash,)).fetchone()
                    self.ingest(raw)
                    if before:
                        counts["duplicates"] += 1
                    else:
                        counts["inserted"] += 1
                except (json.JSONDecodeError, UnicodeError, RedactionFailure, TypeError, ValueError):
                    counts["malformed"] += 1
        return counts

    @staticmethod
    def _effective_events(events: List[Tuple[Any, ...]], null_flicker_seconds: int) -> List[Tuple[Any, ...]]:
        filtered: List[Tuple[Any, ...]] = []
        for index, event in enumerate(events):
            if 0 < index < len(events) - 1 and event[3] is None:
                previous, following = events[index - 1], events[index + 1]
                span = (datetime.fromisoformat(following[1]) - datetime.fromisoformat(previous[1])).total_seconds()
                if previous[2] == event[2] == following[2] and previous[3] == following[3] and span <= null_flicker_seconds:
                    continue
            if filtered and filtered[-1][2:] == event[2:]:
                continue
            filtered.append(event)
        return filtered

    def rebuild_segments(self, idle_threshold_seconds: int = 1800, null_flicker_seconds: int = 20) -> None:
        events = self.conn.execute(
            "SELECT event_id,observed_at,app,title FROM events ORDER BY observed_at,event_id"
        ).fetchall()
        events = self._effective_events(events, null_flicker_seconds)
        with self.conn:
            self.conn.execute("DELETE FROM segments")
            for current, following in zip(events, events[1:]):
                start = datetime.fromisoformat(current[1])
                end = datetime.fromisoformat(following[1])
                duration = max(0, int((end - start).total_seconds()))
                state = "active" if duration <= idle_threshold_seconds else "unknown"
                self.conn.execute(
                    """INSERT INTO segments(event_id,start_at,end_at,duration_seconds,state,app,title)
                       VALUES(?,?,?,?,?,?,?)""",
                    (current[0], current[1], following[1], duration, state, current[2], current[3]),
                )

    def integrity_check(self) -> str:
        return str(self.conn.execute("PRAGMA integrity_check").fetchone()[0])

    def scalar(self, sql: str, params: Tuple[Any, ...] = ()) -> Any:
        row = self.conn.execute(sql, params).fetchone()
        return None if row is None else row[0]

    def rows(self, sql: str, params: Tuple[Any, ...] = ()) -> List[Tuple[Any, ...]]:
        return [tuple(row) for row in self.conn.execute(sql, params).fetchall()]

    def search(self, query: str) -> List[Dict[str, Any]]:
        rows = self.conn.execute(
            """SELECT e.event_id,e.observed_at,e.app,e.title,e.detail,e.path
               FROM events_fts f JOIN events e ON e.event_id=f.event_id
               WHERE events_fts MATCH ? ORDER BY e.observed_at""",
            (query,),
        ).fetchall()
        keys = ("event_id", "observed_at", "app", "title", "detail", "path")
        return [dict(zip(keys, row)) for row in rows]

    def report(self) -> Dict[str, Any]:
        event_count = int(self.scalar("SELECT count(*) FROM events") or 0)
        redacted_events = int(self.scalar("SELECT count(*) FROM events WHERE redaction_count>0") or 0)
        redaction_fields = int(self.scalar("SELECT count(*) FROM redactions") or 0)
        segment_count = int(self.scalar("SELECT count(*) FROM segments") or 0)
        active = int(self.scalar("SELECT coalesce(sum(duration_seconds),0) FROM segments WHERE state='active'") or 0)
        unknown = int(self.scalar("SELECT coalesce(sum(duration_seconds),0) FROM segments WHERE state='unknown'") or 0)
        active_seconds_by_app = {
            app or "[UNKNOWN_APP]": int(seconds)
            for app, seconds in self.conn.execute(
                """SELECT app,sum(duration_seconds) FROM segments
                   WHERE state='active' GROUP BY app ORDER BY sum(duration_seconds) DESC"""
            ).fetchall()
        }
        bounds = self.conn.execute("SELECT min(observed_at),max(observed_at) FROM events").fetchone()
        by_kind = {
            kind: count for kind, count in self.conn.execute(
                "SELECT kind,count(*) FROM redactions GROUP BY kind ORDER BY kind"
            ).fetchall()
        }
        residual_sensitive_fields = 0
        for row in self.conn.execute(
            """SELECT e.observed_at,s.name,e.app,e.title,e.detail,e.session_id,e.path
               FROM events e JOIN sources s ON s.source_id=e.source_id"""
        ).fetchall():
            stored = dict(zip(("ts", "source", "app", "title", "detail", "session_id", "path"), row))
            _, residual = redact_event(stored)
            residual_sensitive_fields += len(residual)
        return {
            "schema_version": self.scalar("SELECT value FROM schema_meta WHERE key='schema_version'"),
            "events": event_count,
            "redacted_events": redacted_events,
            "redaction_fields": redaction_fields,
            "redactions_by_kind": by_kind,
            "residual_sensitive_fields": residual_sensitive_fields,
            "segments": segment_count,
            "active_seconds_lower_bound": active,
            "active_seconds_by_app": active_seconds_by_app,
            "unknown_gap_seconds": unknown,
            "first_observed_at": bounds[0],
            "last_observed_at": bounds[1],
            "integrity": self.integrity_check(),
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Whole redacted SQLite evidence store")
    parser.add_argument("--db", default=str(Path.home() / ".hermes/whole/whole.db"))
    sub = parser.add_subparsers(dest="command", required=True)
    imp = sub.add_parser("import-jsonl")
    imp.add_argument("trail")
    imp.add_argument("--idle-threshold", type=int, default=1800)
    sub.add_parser("report")
    args = parser.parse_args()

    store = Store(Path(args.db))
    try:
        if args.command == "import-jsonl":
            result = store.import_jsonl(Path(args.trail))
            store.rebuild_segments(args.idle_threshold)
            result["report"] = store.report()
            print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        elif args.command == "report":
            store.rebuild_segments()
            print(json.dumps(store.report(), ensure_ascii=False, indent=2, sort_keys=True))
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
