"""Small immutable event contract, independent of HTTP and robot control.

Payloads are bounded and redacted before they enter either the queue or SQLite.
This is operational metadata capture, not an arbitrary HTTP body/video recorder.
"""

import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone


class EventValidationError(ValueError):
    """Invalid event; messages never echo submitted content."""


def utc_now():
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def timestamp(value):
    if not isinstance(value, str) or len(value) > 64:
        raise EventValidationError("invalid_timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError
        return (
            parsed.astimezone(timezone.utc)
            .isoformat(timespec="microseconds")
            .replace("+00:00", "Z")
        )
    except (ValueError, OverflowError):
        raise EventValidationError("invalid_timestamp") from None


def identifier(value, *, optional=False, limit=128):
    if value is None and optional:
        return None
    if (
        not isinstance(value, str)
        or not 1 <= len(value) <= limit
        or any(ord(c) < 32 for c in value)
    ):
        raise EventValidationError("invalid_identifier")
    return value


_SECRET = re.compile(
    r"(?:token|password|passwd|authorization|cookie|secret|credential|api_key|apikey|access_code|"
    r"private_key|session_key|lease|^pin$|^body$|request_body|response_body|raw_body|^headers$)",
    re.I,
)
_BEARER = re.compile(r"\bBearer\s+[^\s,;]+", re.I)


def redact_payload(payload):
    if not isinstance(payload, dict):
        raise EventValidationError("invalid_payload")
    budget = [1024]

    def visit(value, depth):
        budget[0] -= 1
        if budget[0] < 0 or depth > 8:
            raise EventValidationError("payload_limit")
        if value is None or type(value) is bool or type(value) is int:
            return value
        if type(value) is float:
            if not math.isfinite(value):
                raise EventValidationError("invalid_payload_number")
            return value
        if isinstance(value, str):
            if len(value) > 2048:
                raise EventValidationError("payload_limit")
            return _BEARER.sub("Bearer [REDACTED]", value)
        if isinstance(value, dict):
            if len(value) > 128:
                raise EventValidationError("payload_limit")
            result = {}
            for key, item in value.items():
                if not isinstance(key, str) or not 1 <= len(key) <= 128:
                    raise EventValidationError("invalid_payload_key")
                result[key] = (
                    "[REDACTED]" if _SECRET.search(key) else visit(item, depth + 1)
                )
            return result
        if isinstance(value, (list, tuple)):
            if len(value) > 128:
                raise EventValidationError("payload_limit")
            return [visit(item, depth + 1) for item in value]
        if isinstance(value, (bytes, bytearray, memoryview)):
            return "[BINARY OMITTED]"
        raise EventValidationError("invalid_payload_type")

    result = visit(payload, 0)
    if len(canonical_json(result).encode("utf-8")) > 65536:
        raise EventValidationError("payload_limit")
    return result


def canonical_json(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


@dataclass(frozen=True)
class StructuredEvent:
    event_id: str
    source: str
    run_id: str
    sequence: int
    occurred_at: str
    observed_at: str
    trace_id: str | None
    command_id: str | None
    stage: str
    outcome: str
    reason_code: str | None
    payload: dict
    schema_version: int = 1

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict):
            raise EventValidationError("invalid_event")
        fields = set(cls.__dataclass_fields__)
        if set(data) - fields:
            raise EventValidationError("unknown_event_field")
        if (
            type(data.get("schema_version", 1)) is not int
            or data.get("schema_version", 1) != 1
        ):
            raise EventValidationError("unsupported_schema_version")
        sequence = data.get("sequence")
        if type(sequence) is not int or not 0 <= sequence <= 9_223_372_036_854_775_807:
            raise EventValidationError("invalid_sequence")
        return cls(
            event_id=identifier(data.get("event_id")),
            source=identifier(data.get("source")),
            run_id=identifier(data.get("run_id")),
            sequence=sequence,
            occurred_at=timestamp(data.get("occurred_at")),
            observed_at=timestamp(data.get("observed_at", utc_now())),
            trace_id=identifier(data.get("trace_id"), optional=True),
            command_id=identifier(data.get("command_id"), optional=True),
            stage=identifier(data.get("stage", "observed"), limit=64),
            outcome=identifier(data.get("outcome", "unknown"), limit=64),
            reason_code=identifier(data.get("reason_code"), optional=True),
            payload=redact_payload(data.get("payload", {})),
        )

    def to_dict(self):
        return asdict(self)

    def content_hash(self):
        # Collector receipt time is not producer identity: a retried source event
        # remains idempotent even when it is received at another local time.
        data = self.to_dict()
        data.pop("observed_at")
        return hashlib.sha256(canonical_json(data).encode("utf-8")).hexdigest()


def normalize_event(data):
    """Validate and detach a redacted dictionary for transport boundaries."""
    return StructuredEvent.from_dict(data).to_dict()
