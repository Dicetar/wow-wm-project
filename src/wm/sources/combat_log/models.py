from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any

from wm.refs import CreatureRef
from wm.refs import PlayerRef


@dataclass(slots=True)
class CombatActor:
    guid: str | None = None
    name: str | None = None
    flags: str | None = None
    raid_flags: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "guid": self.guid,
            "name": self.name,
            "flags": self.flags,
            "raid_flags": self.raid_flags,
        }


@dataclass(slots=True)
class CombatLogCursor:
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
    def from_cursor_value(cls, value: str | None, *, default_path: str) -> "CombatLogCursor":
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
class CombatLogLine:
    byte_offset: int
    raw_line: str

    def to_dict(self) -> dict[str, Any]:
        return {"byte_offset": int(self.byte_offset), "raw_line": self.raw_line}


@dataclass(slots=True)
class CombatLogRecord:
    occurred_at: str
    event_name: str
    raw_fields: list[str]
    source_actor: CombatActor | None
    dest_actor: CombatActor | None
    raw_line: str
    byte_offset: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "occurred_at": self.occurred_at,
            "event_name": self.event_name,
            "raw_fields": list(self.raw_fields),
            "source_actor": self.source_actor.to_dict() if self.source_actor is not None else None,
            "dest_actor": self.dest_actor.to_dict() if self.dest_actor is not None else None,
            "raw_line": self.raw_line,
            "byte_offset": int(self.byte_offset),
        }


@dataclass(slots=True)
class CombatKillSignal:
    player_ref: PlayerRef
    subject_ref: CreatureRef
    occurred_at: str
    raw_line: str
    byte_offset: int
    source_event_key: str
    event_name: str
    log_path: str
    resolution_source: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "player_ref": self.player_ref.to_dict(),
            "subject_ref": self.subject_ref.to_dict(),
            "occurred_at": self.occurred_at,
            "raw_line": self.raw_line,
            "byte_offset": int(self.byte_offset),
            "source_event_key": self.source_event_key,
            "event_name": self.event_name,
            "log_path": self.log_path,
            "resolution_source": self.resolution_source,
        }


@dataclass(slots=True)
class CombatResolutionFailure:
    reason: str
    byte_offset: int
    raw_line: str
    event_name: str | None = None
    occurred_at: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "reason": self.reason,
            "byte_offset": int(self.byte_offset),
            "raw_line": self.raw_line,
            "event_name": self.event_name,
            "occurred_at": self.occurred_at,
            "details": self.details,
        }


@dataclass(slots=True)
class CombatLogTailResult:
    file_exists: bool
    path: str
    cursor: CombatLogCursor
    lines: list[CombatLogLine] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_exists": self.file_exists,
            "path": self.path,
            "cursor": self.cursor.to_dict(),
            "lines": [line.to_dict() for line in self.lines],
        }


@dataclass(slots=True)
class CombatLogScanResult:
    file_exists: bool
    path: str
    cursor: CombatLogCursor
    signals: list[CombatKillSignal] = field(default_factory=list)
    failures: list[CombatResolutionFailure] = field(default_factory=list)

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
