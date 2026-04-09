from __future__ import annotations

import csv
from datetime import datetime
import re

from wm.sources.combat_log.models import CombatActor
from wm.sources.combat_log.models import CombatLogRecord


_TIMESTAMP_RE = re.compile(
    r"^(?P<timestamp>\d{1,2}/\d{1,2} \d{1,2}:\d{2}:\d{2}(?:\.\d+)?)\s+(?P<payload>.+)$"
)


class CombatLogParser:
    def parse_line(self, *, raw_line: str, byte_offset: int) -> CombatLogRecord | None:
        stripped = raw_line.strip()
        if not stripped:
            return None
        match = _TIMESTAMP_RE.match(stripped)
        if match is None:
            return None
        timestamp_raw = match.group("timestamp")
        payload = match.group("payload")
        row = next(csv.reader([payload], skipinitialspace=False), [])
        if not row:
            return None
        event_name = str(row[0]).strip().upper()
        source_actor, dest_actor = _actors_from_row(row)
        return CombatLogRecord(
            occurred_at=_combat_timestamp_to_iso(timestamp_raw),
            event_name=event_name,
            raw_fields=[str(field) for field in row[1:]],
            source_actor=source_actor,
            dest_actor=dest_actor,
            raw_line=stripped,
            byte_offset=int(byte_offset),
        )


def _actors_from_row(row: list[str]) -> tuple[CombatActor | None, CombatActor | None]:
    if len(row) < 4:
        return None, None
    source = _actor_from_row(row, start_index=1)
    dest = _actor_from_row(row, start_index=4)
    return source, dest


def _actor_from_row(row: list[str], *, start_index: int) -> CombatActor | None:
    if len(row) <= start_index + 2:
        return None
    return CombatActor(
        guid=_str_or_none(row[start_index]),
        name=_str_or_none(row[start_index + 1]),
        flags=_str_or_none(row[start_index + 2]),
        raid_flags=None,
    )


def _combat_timestamp_to_iso(raw_timestamp: str) -> str:
    now_local = datetime.now().astimezone()
    if "." in raw_timestamp:
        parsed = datetime.strptime(raw_timestamp, "%m/%d %H:%M:%S.%f")
    else:
        parsed = datetime.strptime(raw_timestamp, "%m/%d %H:%M:%S")
    parsed = parsed.replace(year=now_local.year, tzinfo=now_local.tzinfo)
    return parsed.isoformat(timespec="milliseconds")


def _str_or_none(value: object) -> str | None:
    if value in (None, ""):
        return None
    return str(value)
