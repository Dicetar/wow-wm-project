"""Journal V2: project wm_event_log rows into per-player/subject/zone counters.

The journal reader (read side) already exists; this is the missing write side.
It is idempotent (only rows with ProjectedAt IS NULL are consumed, and each is
stamped), dry-runnable (emits SQL without mutating), and auto-materializes a
`wm_subject_definition` row the first time a subject is seen.

Pure SQL builders are unit-tested with a fake client; nothing here bypasses
the WM ownership rules - it only writes WM-owned journal tables.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# event_type -> wm_player_subject_journal counter column
EVENT_COUNTER: dict[str, str] = {
    "kill": "KillCount",
    "quest_completed": "QuestCompleteCount",
    "quest_rewarded": "QuestCompleteCount",
    "skin": "SkinCount",
    "feed": "FeedCount",
    "gossip_select": "TalkCount",
}
# event_type -> wm_player_zone_stats column
ZONE_COUNTER: dict[str, str] = {
    "kill": "KillCount",
    "quest_completed": "QuestCompleteCount",
    "quest_rewarded": "QuestCompleteCount",
}


def _sql_str(value: str) -> str:
    return "'" + str(value).replace("\\", "\\\\").replace("'", "''") + "'"


@dataclass(slots=True)
class ProjectionResult:
    considered: int = 0
    projected: int = 0
    skipped: int = 0
    materialized_subjects: int = 0
    statements: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "considered": self.considered,
            "projected": self.projected,
            "skipped": self.skipped,
            "materialized_subjects": self.materialized_subjects,
            "statement_count": len(self.statements),
            "issues": self.issues,
        }


def build_subject_journal_sql(
    *, player_guid: int, subject_id: int, counter_col: str
) -> str:
    return (
        "INSERT INTO wm_player_subject_journal "
        "(PlayerGUID, SubjectID, FirstSeenAt, LastSeenAt, " + counter_col + ") "
        f"VALUES ({int(player_guid)}, {int(subject_id)}, NOW(), NOW(), 1) "
        "ON DUPLICATE KEY UPDATE "
        f"{counter_col} = {counter_col} + 1, LastSeenAt = NOW()"
    )


def build_subject_event_sql(
    *, player_guid: int, subject_id: int, event_type: str, event_value: str | None
) -> str:
    value_sql = "NULL" if event_value in (None, "") else _sql_str(str(event_value))
    return (
        "INSERT INTO wm_player_subject_event "
        "(PlayerGUID, SubjectID, EventType, EventValue, CreatedAt) "
        f"VALUES ({int(player_guid)}, {int(subject_id)}, {_sql_str(event_type)}, {value_sql}, NOW())"
    )


def build_zone_rollup_sql(*, player_guid: int, zone_id: int, zone_col: str) -> str:
    return (
        "INSERT INTO wm_player_zone_stats "
        f"(PlayerGUID, ZoneID, {zone_col}, LastActivityAt) "
        f"VALUES ({int(player_guid)}, {int(zone_id)}, 1, NOW()) "
        "ON DUPLICATE KEY UPDATE "
        f"{zone_col} = {zone_col} + 1, LastActivityAt = NOW()"
    )


def build_mark_projected_sql(*, event_id: int) -> str:
    return f"UPDATE wm_event_log SET ProjectedAt = NOW() WHERE EventID = {int(event_id)}"


def build_materialize_subject_sql(*, subject_type: str, subject_entry: int) -> str:
    return (
        "INSERT INTO wm_subject_definition (SubjectType, CreatureEntry, JournalName, IsActive) "
        f"VALUES ({_sql_str(subject_type)}, {int(subject_entry)}, "
        f"{_sql_str(f'{subject_type}:{subject_entry}')}, 1) "
        "ON DUPLICATE KEY UPDATE SubjectID = LAST_INSERT_ID(SubjectID)"
    )


class JournalProjector:
    def __init__(self, *, client: Any, settings: Any) -> None:
        self.client = client
        self.settings = settings

    def _world(self, sql: str) -> list[dict[str, Any]]:
        return self.client.query(
            host=self.settings.world_db_host,
            port=self.settings.world_db_port,
            user=self.settings.world_db_user,
            password=self.settings.world_db_password,
            database=self.settings.world_db_name,
            sql=sql,
        )

    def _resolve_subject_id(self, *, subject_type: str, subject_entry: int, result: ProjectionResult, mode: str) -> int | None:
        rows = self._world(
            "SELECT SubjectID FROM wm_subject_definition "
            f"WHERE SubjectType = {_sql_str(subject_type)} AND CreatureEntry = {int(subject_entry)} LIMIT 1"
        )
        if rows:
            return int(next(iter(rows[0].values())))
        mat = build_materialize_subject_sql(subject_type=subject_type, subject_entry=subject_entry)
        result.statements.append(mat)
        result.materialized_subjects += 1
        if mode == "dry-run":
            return None  # unknown id until applied; dry-run reports intent only
        self._world(mat)
        again = self._world(
            "SELECT SubjectID FROM wm_subject_definition "
            f"WHERE SubjectType = {_sql_str(subject_type)} AND CreatureEntry = {int(subject_entry)} LIMIT 1"
        )
        return int(next(iter(again[0].values()))) if again else None

    def project_unprojected(
        self, *, player_guid: int | None = None, limit: int = 200, mode: str = "dry-run"
    ) -> ProjectionResult:
        if mode not in {"dry-run", "apply"}:
            raise ValueError(f"unsupported mode: {mode}")
        result = ProjectionResult()
        scope = f" AND PlayerGUID = {int(player_guid)}" if player_guid is not None else ""
        rows = self._world(
            "SELECT EventID, EventType, PlayerGUID, SubjectType, SubjectEntry, ZoneID, EventValue "
            "FROM wm_event_log "
            f"WHERE ProjectedAt IS NULL{scope} "
            f"ORDER BY EventID ASC LIMIT {int(limit)}"
        )
        result.considered = len(rows)
        for row in rows:
            event_id = int(row.get("EventID"))
            event_type = str(row.get("EventType") or "")
            pg = row.get("PlayerGUID")
            counter_col = EVENT_COUNTER.get(event_type)
            if pg in (None, "", 0) or counter_col is None:
                result.skipped += 1
                result.statements.append(build_mark_projected_sql(event_id=event_id))
                if mode == "apply":
                    self._world(build_mark_projected_sql(event_id=event_id))
                continue
            player = int(pg)
            subject_type = str(row.get("SubjectType") or "creature")
            subject_entry = int(row.get("SubjectEntry") or 0)
            subject_id = self._resolve_subject_id(
                subject_type=subject_type, subject_entry=subject_entry, result=result, mode=mode
            )
            stmts: list[str] = []
            if subject_id is not None:
                stmts.append(build_subject_journal_sql(player_guid=player, subject_id=subject_id, counter_col=counter_col))
                stmts.append(
                    build_subject_event_sql(
                        player_guid=player,
                        subject_id=subject_id,
                        event_type=event_type,
                        event_value=row.get("EventValue"),
                    )
                )
            zone_id = row.get("ZoneID")
            zone_col = ZONE_COUNTER.get(event_type)
            if zone_id not in (None, "", 0) and zone_col is not None:
                stmts.append(build_zone_rollup_sql(player_guid=player, zone_id=int(zone_id), zone_col=zone_col))
            stmts.append(build_mark_projected_sql(event_id=event_id))
            result.statements.extend(stmts)
            if mode == "apply":
                for s in stmts:
                    self._world(s)
            result.projected += 1
        return result
