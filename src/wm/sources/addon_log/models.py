from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from wm.refs import CreatureRef
from wm.refs import PlayerRef


@dataclass(slots=True)
class AddonLogCursor:
    path: str
    offset: int = 0
    fingerprint: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "offset": int(self.offset),
            "fingerprint": self.fingerprint,
        }

    def to_cursor_value(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True)

    @classmethod
    def from_cursor_value(cls, value: str | None, *, default_path: str) -> "AddonLogCursor":
        if value in (None, ""):
            return cls(path=default_path)
        try:
            parsed = json.loads(str(value))
        except json.JSONDecodeError:
            try:
                return cls(path=default_path, offset=int(str(value)))
            except ValueError:
                return cls(path=default_path)
        if not isinstance(parsed, dict):
            return cls(path=default_path)
        return cls(
            path=str(parsed.get("path") or default_path),
            offset=int(parsed.get("offset") or 0),
            fingerprint=str(parsed.get("fingerprint")) if parsed.get("fingerprint") not in (None, "") else None,
        )


@dataclass(slots=True)
class AddonLogLine:
    byte_offset: int
    raw_line: str

    def to_dict(self) -> dict[str, Any]:
        return {"byte_offset": int(self.byte_offset), "raw_line": self.raw_line}


@dataclass(slots=True)
class AddonLogRecord:
    occurred_at: str
    event_type: str
    payload_fields: dict[str, str]
    raw_payload: str
    raw_line: str
    byte_offset: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "occurred_at": self.occurred_at,
            "event_type": self.event_type,
            "payload_fields": dict(self.payload_fields),
            "raw_payload": self.raw_payload,
            "raw_line": self.raw_line,
            "byte_offset": int(self.byte_offset),
        }


@dataclass(slots=True)
class AddonEventSignal:
    event_type: str
    player_ref: PlayerRef
    occurred_at: str
    raw_line: str
    raw_payload: str
    byte_offset: int
    source_event_key: str
    log_path: str
    resolution_source: str
    subject_ref: CreatureRef | None = None
    channel: str | None = None
    subevent: str | None = None
    target_guid: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "player_ref": self.player_ref.to_dict(),
            "subject_ref": self.subject_ref.to_dict() if self.subject_ref is not None else None,
            "occurred_at": self.occurred_at,
            "raw_line": self.raw_line,
            "raw_payload": self.raw_payload,
            "byte_offset": int(self.byte_offset),
            "source_event_key": self.source_event_key,
            "log_path": self.log_path,
            "resolution_source": self.resolution_source,
            "channel": self.channel,
            "subevent": self.subevent,
            "target_guid": self.target_guid,
        }


@dataclass(slots=True)
class AddonResolutionFailure:
    reason: str
    byte_offset: int
    raw_line: str
    event_type: str | None = None
    occurred_at: str | None = None
    raw_payload: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "reason": self.reason,
            "byte_offset": int(self.byte_offset),
            "raw_line": self.raw_line,
            "event_type": self.event_type,
            "occurred_at": self.occurred_at,
            "raw_payload": self.raw_payload,
            "details": self.details,
        }


@dataclass(slots=True)
class AddonLogTailResult:
    file_exists: bool
    path: str
    cursor: AddonLogCursor
    lines: list[AddonLogLine] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_exists": self.file_exists,
            "path": self.path,
            "cursor": self.cursor.to_dict(),
            "lines": [line.to_dict() for line in self.lines],
        }


@dataclass(slots=True)
class AddonLogScanResult:
    file_exists: bool
    path: str
    cursor: AddonLogCursor
    signals: list[AddonEventSignal] = field(default_factory=list)
    failures: list[AddonResolutionFailure] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_exists": self.file_exists,
            "path": self.path,
            "cursor": self.cursor.to_dict(),
            "signals": [signal.to_dict() for signal in self.signals],
            "failures": [failure.to_dict() for failure in self.failures],
        }


def fingerprint_for_path(path: Path) -> str:
    stat = path.stat()
    return f"{path.resolve()}:{int(stat.st_dev)}:{int(stat.st_ino)}:{int(getattr(stat, 'st_ctime_ns', 0))}"


def payload_timestamp_to_iso(value: str | None) -> str:
    if value in (None, ""):
        return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    try:
        numeric = int(str(value))
    except ValueError:
        return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    seconds = numeric / 1000.0 if numeric > 10_000_000_000 else float(numeric)
    return datetime.fromtimestamp(seconds, tz=timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
