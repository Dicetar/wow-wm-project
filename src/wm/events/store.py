from __future__ import annotations

import json
import subprocess
from typing import Any

from wm.config import Settings
from wm.db.mysql_cli import MysqlCliClient, MysqlCliError
from wm.events.models import AdapterCursor
from wm.events.models import ProjectionResult
from wm.events.models import ReactionCooldownKey
from wm.events.models import ReactionPlan
from wm.events.models import RecordResult
from wm.events.models import WMEvent


class EventStore:
    def __init__(self, *, client: MysqlCliClient, settings: Settings) -> None:
        self.client = client
        self.settings = settings

    def get_cursor(self, *, adapter_name: str, cursor_key: str = "last_seen") -> AdapterCursor | None:
        rows = self._query_world(
            "SELECT AdapterName, CursorKey, CursorValue "
            "FROM wm_event_cursor "
            f"WHERE AdapterName = {_sql_string(adapter_name)} AND CursorKey = {_sql_string(cursor_key)}"
        )
        if not rows:
            return None
        row = rows[0]
        return AdapterCursor(
            adapter_name=str(row["AdapterName"]),
            cursor_key=str(row["CursorKey"]),
            cursor_value=str(row["CursorValue"]),
        )

    def set_cursor(self, *, adapter_name: str, cursor_key: str = "last_seen", cursor_value: str) -> None:
        sql = (
            "INSERT INTO wm_event_cursor (AdapterName, CursorKey, CursorValue) VALUES ("
            f"{_sql_string(adapter_name)}, {_sql_string(cursor_key)}, {_sql_string(cursor_value)}) "
            "ON DUPLICATE KEY UPDATE CursorValue = VALUES(CursorValue), UpdatedAt = CURRENT_TIMESTAMP"
        )
        self._execute_world(sql)

    def record(self, events: list[WMEvent]) -> RecordResult:
        result = RecordResult()
        for event in events:
            existing_id = self.lookup_event_id(source=event.source, source_event_key=event.source_event_key)
            if existing_id is not None:
                event.event_id = existing_id
                result.skipped.append(event)
                continue

            sql = (
                "INSERT INTO wm_event_log ("
                "EventClass, EventType, Source, SourceEventKey, OccurredAt, PlayerGUID, SubjectType, SubjectEntry, "
                "MapID, ZoneID, AreaID, EventValue, MetadataJSON"
                ") VALUES ("
                f"{_sql_string(event.event_class)}, "
                f"{_sql_string(event.event_type)}, "
                f"{_sql_string(event.source)}, "
                f"{_sql_string(event.source_event_key)}, "
                f"{_sql_string(event.occurred_at)}, "
                f"{_sql_int_or_null(event.player_guid)}, "
                f"{_sql_string_or_null(event.subject_type)}, "
                f"{_sql_int_or_null(event.subject_entry)}, "
                f"{_sql_int_or_null(event.map_id)}, "
                f"{_sql_int_or_null(event.zone_id)}, "
                f"{_sql_int_or_null(event.area_id)}, "
                f"{_sql_string_or_null(event.event_value)}, "
                f"{_sql_string(json.dumps(event.metadata, ensure_ascii=False, sort_keys=True))}"
                ")"
            )
            self._execute_world(sql)
            event.event_id = self.lookup_event_id(source=event.source, source_event_key=event.source_event_key)
            result.recorded.append(event)
        return result

    def lookup_event_id(self, *, source: str, source_event_key: str) -> int | None:
        rows = self._query_world(
            "SELECT EventID FROM wm_event_log "
            f"WHERE Source = {_sql_string(source)} AND SourceEventKey = {_sql_string(source_event_key)} "
            "LIMIT 1"
        )
        if not rows:
            return None
        return int(rows[0]["EventID"])

    def list_unprojected_observed_events(self, *, limit: int = 100) -> list[WMEvent]:
        rows = self._query_world(
            "SELECT EventID, EventClass, EventType, Source, SourceEventKey, OccurredAt, PlayerGUID, SubjectType, "
            "SubjectEntry, MapID, ZoneID, AreaID, EventValue, MetadataJSON "
            "FROM wm_event_log "
            "WHERE EventClass = 'observed' AND ProjectedAt IS NULL "
            "ORDER BY EventID "
            f"LIMIT {int(limit)}"
        )
        return [self._row_to_event(row) for row in rows]

    def list_unevaluated_observed_events(self, *, limit: int = 100) -> list[WMEvent]:
        rows = self._query_world(
            "SELECT EventID, EventClass, EventType, Source, SourceEventKey, OccurredAt, PlayerGUID, SubjectType, "
            "SubjectEntry, MapID, ZoneID, AreaID, EventValue, MetadataJSON "
            "FROM wm_event_log "
            "WHERE EventClass = 'observed' AND EvaluatedAt IS NULL "
            "ORDER BY EventID "
            f"LIMIT {int(limit)}"
        )
        return [self._row_to_event(row) for row in rows]

    def is_projected(self, *, event_id: int) -> bool:
        rows = self._query_world(
            "SELECT EventID FROM wm_event_log "
            f"WHERE EventID = {int(event_id)} AND ProjectedAt IS NOT NULL "
            "LIMIT 1"
        )
        return bool(rows)

    def is_evaluated(self, *, event_id: int) -> bool:
        rows = self._query_world(
            "SELECT EventID FROM wm_event_log "
            f"WHERE EventID = {int(event_id)} AND EvaluatedAt IS NOT NULL "
            "LIMIT 1"
        )
        return bool(rows)

    def mark_projected(self, *, event_id: int) -> None:
        self._execute_world(
            "UPDATE wm_event_log "
            "SET ProjectedAt = CURRENT_TIMESTAMP "
            f"WHERE EventID = {int(event_id)}"
        )

    def mark_evaluated(self, *, event_id: int) -> None:
        self._execute_world(
            "UPDATE wm_event_log "
            "SET EvaluatedAt = CURRENT_TIMESTAMP "
            f"WHERE EventID = {int(event_id)}"
        )

    def is_cooldown_active(self, key: ReactionCooldownKey, *, at: str | None = None) -> bool:
        when = at or "CURRENT_TIMESTAMP"
        rows = self._query_world(
            "SELECT ReactionKey FROM wm_reaction_cooldown "
            f"WHERE ReactionKey = {_sql_string(key.to_reaction_key())} "
            f"AND CooldownUntil > {_sql_datetime_or_expression(when)} "
            "LIMIT 1"
        )
        return bool(rows)

    def set_cooldown(self, *, key: ReactionCooldownKey, cooldown_seconds: int, triggered_at: str | None = None, metadata: dict[str, Any] | None = None) -> None:
        metadata = metadata or {}
        reaction_key = key.to_reaction_key()
        when_sql = _sql_datetime_or_expression(triggered_at or "CURRENT_TIMESTAMP")
        sql = (
            "INSERT INTO wm_reaction_cooldown ("
            "ReactionKey, RuleType, PlayerGUID, SubjectType, SubjectEntry, CooldownUntil, LastTriggeredAt, MetadataJSON"
            ") VALUES ("
            f"{_sql_string(reaction_key)}, "
            f"{_sql_string(key.rule_type)}, "
            f"{int(key.player_guid)}, "
            f"{_sql_string(key.subject_type)}, "
            f"{int(key.subject_entry)}, "
            f"DATE_ADD({when_sql}, INTERVAL {int(cooldown_seconds)} SECOND), "
            f"{when_sql}, "
            f"{_sql_string(json.dumps(metadata, ensure_ascii=False, sort_keys=True))}"
            ") ON DUPLICATE KEY UPDATE "
            f"CooldownUntil = DATE_ADD({when_sql}, INTERVAL {int(cooldown_seconds)} SECOND), "
            f"LastTriggeredAt = {when_sql}, "
            "MetadataJSON = VALUES(MetadataJSON)"
        )
        self._execute_world(sql)

    def log_reaction(self, *, plan: ReactionPlan, status: str, result: dict[str, Any]) -> None:
        reaction_key = plan.cooldown_key.to_reaction_key() if plan.cooldown_key is not None else plan.plan_key
        sql = (
            "INSERT INTO wm_reaction_log ("
            "ReactionKey, RuleType, Status, PlayerGUID, SubjectType, SubjectEntry, PlannedActionsJSON, ResultJSON"
            ") VALUES ("
            f"{_sql_string(reaction_key)}, "
            f"{_sql_string(plan.rule_type)}, "
            f"{_sql_string(status)}, "
            f"{int(plan.player_guid)}, "
            f"{_sql_string(plan.subject.subject_type)}, "
            f"{int(plan.subject.subject_entry)}, "
            f"{_sql_string(json.dumps(plan.to_dict(), ensure_ascii=False, sort_keys=True))}, "
            f"{_sql_string(json.dumps(result, ensure_ascii=False, sort_keys=True))}"
            ")"
        )
        self._execute_world(sql)

    def resolve_subject_id(self, *, subject_type: str, subject_entry: int) -> int | None:
        entry_column = _subject_entry_column(subject_type)
        rows = self._query_world(
            "SELECT SubjectID FROM wm_subject_definition "
            f"WHERE SubjectType = {_sql_string(subject_type)} "
            f"AND {entry_column} = {int(subject_entry)} "
            "AND IsActive = 1 "
            "LIMIT 1"
        )
        if not rows:
            return None
        return int(rows[0]["SubjectID"])

    def insert_journal_event(self, *, player_guid: int, subject_id: int, event_type: str, event_value: str | None = None) -> None:
        self._execute_world(
            "INSERT INTO wm_player_subject_event (PlayerGUID, SubjectID, EventType, EventValue) VALUES ("
            f"{int(player_guid)}, {int(subject_id)}, {_sql_string(event_type)}, {_sql_string_or_null(event_value)})"
        )

    def apply_journal_projection(
        self,
        *,
        player_guid: int,
        subject_id: int,
        event_type: str,
        event_value: str | None,
        occurred_at: str | None,
    ) -> ProjectionResult:
        updates: list[str] = ["LastSeenAt = CURRENT_TIMESTAMP"]
        counters: dict[str, int] = {}

        if event_type == "kill":
            updates.append("KillCount = KillCount + 1")
            counters["KillCount"] = 1
        elif event_type == "talk":
            updates.append("TalkCount = TalkCount + 1")
            counters["TalkCount"] = 1
        elif event_type == "quest_complete":
            updates.append("QuestCompleteCount = QuestCompleteCount + 1")
            counters["QuestCompleteCount"] = 1
            if event_value:
                updates.append(f"LastQuestTitle = {_sql_string(event_value)}")

        sql = (
            "INSERT INTO wm_player_subject_journal ("
            "PlayerGUID, SubjectID, FirstSeenAt, LastSeenAt, KillCount, SkinCount, FeedCount, TalkCount, QuestCompleteCount, LastQuestTitle"
            ") VALUES ("
            f"{int(player_guid)}, {int(subject_id)}, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, "
            f"{1 if event_type == 'kill' else 0}, "
            "0, "
            "0, "
            f"{1 if event_type == 'talk' else 0}, "
            f"{1 if event_type == 'quest_complete' else 0}, "
            f"{_sql_string_or_null(event_value if event_type == 'quest_complete' else None)}"
            ") ON DUPLICATE KEY UPDATE "
            + ", ".join(updates)
        )
        del occurred_at
        self._execute_world(sql)
        return ProjectionResult(
            event_id=None,
            status="projected",
            subject_id=subject_id,
            journal_counter_updates=counters,
        )

    def _row_to_event(self, row: dict[str, Any]) -> WMEvent:
        metadata_raw = row.get("MetadataJSON")
        metadata: dict[str, Any] = {}
        if metadata_raw not in (None, ""):
            try:
                parsed = json.loads(str(metadata_raw))
                if isinstance(parsed, dict):
                    metadata = parsed
            except json.JSONDecodeError:
                metadata = {"raw_metadata": str(metadata_raw)}
        return WMEvent(
            event_id=int(row["EventID"]),
            event_class=str(row["EventClass"]),
            event_type=str(row["EventType"]),
            source=str(row["Source"]),
            source_event_key=str(row["SourceEventKey"]),
            occurred_at=str(row["OccurredAt"]),
            player_guid=_int_or_none(row.get("PlayerGUID")),
            subject_type=_str_or_none(row.get("SubjectType")),
            subject_entry=_int_or_none(row.get("SubjectEntry")),
            map_id=_int_or_none(row.get("MapID")),
            zone_id=_int_or_none(row.get("ZoneID")),
            area_id=_int_or_none(row.get("AreaID")),
            event_value=_str_or_none(row.get("EventValue")),
            metadata=metadata,
        )

    def _query_world(self, sql: str) -> list[dict[str, Any]]:
        return self.client.query(
            host=self.settings.world_db_host,
            port=self.settings.world_db_port,
            user=self.settings.world_db_user,
            password=self.settings.world_db_password,
            database=self.settings.world_db_name,
            sql=sql,
        )

    def _execute_world(self, sql: str) -> None:
        command = [
            str(self.client.mysql_bin_path),
            f"--host={self.settings.world_db_host}",
            f"--port={self.settings.world_db_port}",
            f"--user={self.settings.world_db_user}",
            f"--password={self.settings.world_db_password}",
            f"--database={self.settings.world_db_name}",
            f"--execute={sql}",
        ]
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if completed.returncode != 0:
            raise MysqlCliError(completed.stderr.strip() or completed.stdout.strip() or "mysql execute failed")


def _subject_entry_column(subject_type: str) -> str:
    if subject_type == "creature":
        return "CreatureEntry"
    raise ValueError(f"Unsupported subject type: {subject_type}")


def _sql_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("'", "''")
    return f"'{escaped}'"


def _sql_string_or_null(value: str | None) -> str:
    if value is None:
        return "NULL"
    return _sql_string(value)


def _sql_int_or_null(value: int | None) -> str:
    if value is None:
        return "NULL"
    return str(int(value))


def _sql_datetime_or_expression(value: str) -> str:
    if value == "CURRENT_TIMESTAMP":
        return value
    return _sql_string(value)


def _int_or_none(value: Any) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


def _str_or_none(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)
