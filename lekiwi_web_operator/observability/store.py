"""SQLite raw event persistence. Evaluation and Alert logic deliberately absent."""

import sqlite3
import threading
from contextlib import closing
from pathlib import Path

from .events import StructuredEvent, canonical_json, identifier, timestamp

_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
 record_id INTEGER PRIMARY KEY AUTOINCREMENT,
 event_id TEXT NOT NULL UNIQUE, source TEXT NOT NULL, run_id TEXT NOT NULL,
 sequence INTEGER NOT NULL, occurred_at TEXT NOT NULL, observed_at TEXT NOT NULL,
 trace_id TEXT, command_id TEXT, stage TEXT NOT NULL, outcome TEXT NOT NULL,
 reason_code TEXT, schema_version INTEGER NOT NULL, event_json TEXT NOT NULL,
 content_hash TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS events_time ON events(occurred_at,record_id);
CREATE INDEX IF NOT EXISTS events_source ON events(source,run_id,sequence);
CREATE INDEX IF NOT EXISTS events_trace ON events(trace_id,record_id);
CREATE TRIGGER IF NOT EXISTS events_no_update BEFORE UPDATE ON events
 BEGIN SELECT RAISE(ABORT,'raw_events_are_immutable'); END;
CREATE TRIGGER IF NOT EXISTS events_no_delete BEFORE DELETE ON events
 BEGIN SELECT RAISE(ABORT,'raw_events_are_immutable'); END;
CREATE TABLE IF NOT EXISTS event_conflicts (
 conflict_id INTEGER PRIMARY KEY AUTOINCREMENT,
 event_id TEXT NOT NULL, existing_record_id INTEGER NOT NULL,
 observed_at TEXT NOT NULL, incoming_json TEXT NOT NULL, incoming_hash TEXT NOT NULL,
 UNIQUE(event_id,incoming_hash)
);
CREATE TABLE IF NOT EXISTS sequence_state (
 source TEXT NOT NULL, run_id TEXT NOT NULL, last_sequence INTEGER NOT NULL,
 PRIMARY KEY(source,run_id)
);
CREATE TABLE IF NOT EXISTS sequence_diagnostics (
 diagnostic_id INTEGER PRIMARY KEY AUTOINCREMENT,
 kind TEXT NOT NULL, source TEXT NOT NULL, run_id TEXT NOT NULL,
 sequence INTEGER NOT NULL, previous_sequence INTEGER,
 event_id TEXT NOT NULL, observed_at TEXT NOT NULL
);
"""
_SCHEMA_LOCK = threading.Lock()


class EventStore:
    """One thread owns append's writer; reads use separate short-lived connections.

    Public methods return only already-redacted event dictionaries. Cursor order
    is local record_id receipt order, not source sequence or wall-clock order.
    """

    def __init__(self, dbpath, *, initialize=True):
        self.path = Path(dbpath)
        self._writer = None
        if initialize:
            with _SCHEMA_LOCK:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with closing(sqlite3.connect(self.path, timeout=0.2)) as connection:
                    version = connection.execute("PRAGMA user_version").fetchone()[0]
                    if version == 0:
                        connection.execute("PRAGMA journal_mode=WAL")
                        connection.execute("PRAGMA synchronous=FULL")
                        connection.executescript(_SCHEMA)
                        connection.execute("PRAGMA user_version=1")
                    elif version != 1:
                        raise ValueError("unsupported_store_version")

    def _connection(self):
        if self._writer is None:
            self._writer = sqlite3.connect(self.path, timeout=0.2)
            self._writer.execute("PRAGMA synchronous=FULL")
        return self._writer

    def append(self, event):
        # Revalidate even dataclass callers: frozen doesn't freeze nested dicts.
        event = StructuredEvent.from_dict(
            event.to_dict() if isinstance(event, StructuredEvent) else event
        )
        data, digest = event.to_dict(), event.content_hash()
        connection = self._connection()
        try:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT record_id,content_hash FROM events WHERE event_id=?",
                (event.event_id,),
            ).fetchone()
            if existing:
                result = "duplicate" if existing[1] == digest else "conflict"
                if result == "conflict":
                    connection.execute(
                        "INSERT OR IGNORE INTO event_conflicts(event_id,existing_record_id,observed_at,incoming_json,incoming_hash) VALUES(?,?,?,?,?)",
                        (
                            event.event_id,
                            existing[0],
                            event.observed_at,
                            canonical_json(data),
                            digest,
                        ),
                    )
                connection.commit()
                return result
            previous_row = connection.execute(
                "SELECT last_sequence FROM sequence_state WHERE source=? AND run_id=?",
                (event.source, event.run_id),
            ).fetchone()
            previous = previous_row[0] if previous_row else None
            kind = None
            if previous is not None:
                if event.sequence > previous + 1:
                    kind = "sequence_gap"
                elif event.sequence <= previous:
                    same_sequence = connection.execute(
                        "SELECT 1 FROM events WHERE source=? AND run_id=? AND sequence=? LIMIT 1",
                        (event.source, event.run_id, event.sequence),
                    ).fetchone()
                    kind = "sequence_duplicate" if same_sequence else "out_of_order"
            connection.execute(
                "INSERT INTO events(event_id,source,run_id,sequence,occurred_at,observed_at,trace_id,command_id,stage,outcome,reason_code,schema_version,event_json,content_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    event.event_id,
                    event.source,
                    event.run_id,
                    event.sequence,
                    event.occurred_at,
                    event.observed_at,
                    event.trace_id,
                    event.command_id,
                    event.stage,
                    event.outcome,
                    event.reason_code,
                    event.schema_version,
                    canonical_json(data),
                    digest,
                ),
            )
            if kind:
                connection.execute(
                    "INSERT INTO sequence_diagnostics(kind,source,run_id,sequence,previous_sequence,event_id,observed_at) VALUES(?,?,?,?,?,?,?)",
                    (
                        kind,
                        event.source,
                        event.run_id,
                        event.sequence,
                        previous,
                        event.event_id,
                        event.observed_at,
                    ),
                )
            if previous is None or event.sequence > previous:
                connection.execute(
                    "INSERT INTO sequence_state(source,run_id,last_sequence) VALUES(?,?,?) ON CONFLICT(source,run_id) DO UPDATE SET last_sequence=excluded.last_sequence",
                    (event.source, event.run_id, event.sequence),
                )
            connection.commit()
            return "written"
        except Exception:
            connection.rollback()
            raise

    def _read(self):
        connection = sqlite3.connect(
            self.path.resolve().as_uri() + "?mode=ro", uri=True, timeout=0.2
        )
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _event(row):
        import json

        return {"record_id": row["record_id"], **json.loads(row["event_json"])}

    def list_events(
        self, *, limit=100, after=0, source=None, since=None, until=None, trace_id=None
    ):
        if (
            type(limit) is not int
            or not 1 <= limit <= 500
            or type(after) is not int
            or not 0 <= after <= 9_223_372_036_854_775_807
        ):
            raise ValueError("invalid_pagination")
        clauses, parameters = ["record_id> ?"], [after]
        for column, value, operator in (
            ("source", source, "="),
            ("trace_id", trace_id, "="),
            ("occurred_at", timestamp(since) if since is not None else None, ">="),
            ("occurred_at", timestamp(until) if until is not None else None, "<="),
        ):
            if value is not None:
                clauses.append(column + operator + "?")
                parameters.append(identifier(value))
        if (
            since is not None
            and until is not None
            and timestamp(since) > timestamp(until)
        ):
            raise ValueError("invalid_time_range")
        connection = self._read()
        try:
            rows = connection.execute(
                "SELECT record_id,event_json FROM events WHERE "
                + " AND ".join(clauses)
                + " ORDER BY record_id LIMIT ?",
                [*parameters, limit + 1],
            ).fetchall()
            events = [self._event(row) for row in rows[:limit]]
            return {
                "events": events,
                "next_cursor": events[-1]["record_id"] if len(rows) > limit else None,
            }
        finally:
            connection.close()

    def get_event(self, event_id):
        event_id = identifier(event_id)
        connection = self._read()
        try:
            row = connection.execute(
                "SELECT record_id,event_json FROM events WHERE event_id=?", (event_id,)
            ).fetchone()
            return self._event(row) if row else None
        finally:
            connection.close()

    def stats(self):
        connection = self._read()
        try:
            return {
                "events": connection.execute("SELECT COUNT(*) FROM events").fetchone()[
                    0
                ],
                "conflicts": connection.execute(
                    "SELECT COUNT(*) FROM event_conflicts"
                ).fetchone()[0],
                "sequence_diagnostics": connection.execute(
                    "SELECT COUNT(*) FROM sequence_diagnostics"
                ).fetchone()[0],
            }
        finally:
            connection.close()

    def diagnostics(self, *, limit=100, after=0):
        if (
            type(limit) is not int
            or not 1 <= limit <= 500
            or type(after) is not int
            or not 0 <= after <= 9_223_372_036_854_775_807
        ):
            raise ValueError("invalid_pagination")
        connection = self._read()
        try:
            return [
                dict(row)
                for row in connection.execute(
                    "SELECT * FROM sequence_diagnostics WHERE diagnostic_id>? ORDER BY diagnostic_id LIMIT ?",
                    (after, limit),
                )
            ]
        finally:
            connection.close()

    def close(self):
        if self._writer is not None:
            self._writer.close()
            self._writer = None
