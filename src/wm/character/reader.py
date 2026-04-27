from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from wm.character.models import (
    ArcState,
    CharacterProfile,
    CharacterUnlock,
    ConversationSteeringNote,
    PromptQueueEntry,
    RewardInstance,
)
from wm.config import Settings
from wm.db.mysql_cli import MysqlCliClient, MysqlCliError


@dataclass(slots=True)
class CharacterStateBundle:
    profile: CharacterProfile | None = None
    arc_states: list[ArcState] = field(default_factory=list)
    unlocks: list[CharacterUnlock] = field(default_factory=list)
    rewards: list[RewardInstance] = field(default_factory=list)
    conversation_steering: list[ConversationSteeringNote] = field(default_factory=list)
    prompt_queue: list[PromptQueueEntry] = field(default_factory=list)
    status: str = "UNKNOWN"
    notes: list[str] = field(default_factory=list)


def load_character_state(
    *,
    client: MysqlCliClient,
    settings: Settings,
    character_guid: int,
) -> CharacterStateBundle:
    return CharacterStateReader(client=client, settings=settings).load(character_guid=int(character_guid))


class CharacterStateReader:
    def __init__(self, *, client: MysqlCliClient, settings: Settings) -> None:
        self.client = client
        self.settings = settings
        self._table_cache: dict[str, bool] = {}

    def load(self, *, character_guid: int) -> CharacterStateBundle:
        guid = int(character_guid)
        notes: list[str] = []

        profile_rows = self._query_table(
            table_name="wm_character_profile",
            sql=(
                "SELECT CharacterGUID, CharacterName, WMPersona, Tone, PreferredThemesJSON, AvoidedThemesJSON "
                f"FROM wm_character_profile WHERE CharacterGUID = {guid}"
            ),
            notes=notes,
        )
        arc_rows = self._query_table(
            table_name="wm_character_arc_state",
            sql=(
                "SELECT CharacterGUID, ArcKey, StageKey, Status, BranchKey, Summary "
                f"FROM wm_character_arc_state WHERE CharacterGUID = {guid} ORDER BY ArcKey"
            ),
            notes=notes,
        )
        unlock_rows = self._query_table(
            table_name="wm_character_unlock",
            sql=(
                "SELECT CharacterGUID, UnlockKind, UnlockID, SourceArcKey, SourceQuestID, GrantMethod, BotEligible "
                f"FROM wm_character_unlock WHERE CharacterGUID = {guid} ORDER BY UnlockKind, UnlockID"
            ),
            notes=notes,
        )
        reward_rows = self._query_table(
            table_name="wm_character_reward_instance",
            sql=(
                "SELECT CharacterGUID, RewardKind, TemplateID, SourceArcKey, SourceQuestID, IsEquippedGate "
                f"FROM wm_character_reward_instance WHERE CharacterGUID = {guid} ORDER BY GrantedAt DESC"
            ),
            notes=notes,
        )
        steering_rows = self._query_table(
            table_name="wm_character_conversation_steering",
            sql=(
                "SELECT CharacterGUID, SteeringKey, SteeringKind, Body, Priority, Source, IsActive, MetadataJSON "
                "FROM wm_character_conversation_steering "
                f"WHERE CharacterGUID = {guid} AND IsActive = 1 ORDER BY Priority DESC, UpdatedAt DESC, SteeringKey"
            ),
            notes=notes,
        )
        prompt_rows = self._query_table(
            table_name="wm_character_prompt_queue",
            sql=(
                "SELECT QueueID, CharacterGUID, PromptKind, Body, IsConsumed, CreatedAt "
                f"FROM wm_character_prompt_queue WHERE CharacterGUID = {guid} AND IsConsumed = 0 ORDER BY QueueID"
            ),
            notes=notes,
        )

        profile = _build_profile(profile_rows[0]) if profile_rows else None
        arc_states = [_build_arc_state(row) for row in arc_rows]
        unlocks = [_build_unlock(row) for row in unlock_rows]
        rewards = [_build_reward(row) for row in reward_rows]
        conversation_steering = [_build_conversation_steering(row) for row in steering_rows]
        prompt_queue = [_build_prompt_queue_entry(row) for row in prompt_rows]
        if profile is None:
            notes.append("No wm_character_profile row was loaded.")

        return CharacterStateBundle(
            profile=profile,
            arc_states=arc_states,
            unlocks=unlocks,
            rewards=rewards,
            conversation_steering=conversation_steering,
            prompt_queue=prompt_queue,
            status="WORKING" if profile is not None and not notes else "PARTIAL",
            notes=notes,
        )

    def _query_table(self, *, table_name: str, sql: str, notes: list[str]) -> list[dict[str, Any]]:
        if not self._table_exists(table_name):
            notes.append(f"{table_name}: table not found.")
            return []
        try:
            return self._query_char(sql)
        except MysqlCliError as exc:
            notes.append(f"{table_name}: {_safe_error(exc)}")
            return []

    def _table_exists(self, table_name: str) -> bool:
        cached = self._table_cache.get(table_name)
        if cached is not None:
            return cached
        try:
            rows = self.client.query(
                host=self.settings.char_db_host,
                port=self.settings.char_db_port,
                user=self.settings.char_db_user,
                password=self.settings.char_db_password,
                database="information_schema",
                sql=(
                    "SELECT TABLE_NAME FROM information_schema.TABLES "
                    f"WHERE TABLE_SCHEMA = {_sql_string(self.settings.char_db_name)} "
                    f"AND TABLE_NAME = {_sql_string(table_name)} LIMIT 1"
                ),
            )
        except MysqlCliError:
            self._table_cache[table_name] = False
            return False
        exists = bool(rows)
        self._table_cache[table_name] = exists
        return exists

    def _query_char(self, sql: str) -> list[dict[str, Any]]:
        return self.client.query(
            host=self.settings.char_db_host,
            port=self.settings.char_db_port,
            user=self.settings.char_db_user,
            password=self.settings.char_db_password,
            database=self.settings.char_db_name,
            sql=sql,
        )

def _build_profile(row: dict[str, Any]) -> CharacterProfile:
    return CharacterProfile(
        character_guid=int(row["CharacterGUID"]),
        character_name=str(row["CharacterName"]),
        wm_persona=str(row.get("WMPersona") or "default"),
        tone=str(row.get("Tone") or "adaptive"),
        preferred_themes=_parse_json_list(row.get("PreferredThemesJSON")),
        avoided_themes=_parse_json_list(row.get("AvoidedThemesJSON")),
    )


def _build_arc_state(row: dict[str, Any]) -> ArcState:
    return ArcState(
        character_guid=int(row["CharacterGUID"]),
        arc_key=str(row["ArcKey"]),
        stage_key=str(row["StageKey"]),
        status=str(row.get("Status") or "active"),
        branch_key=row.get("BranchKey"),
        summary=row.get("Summary"),
    )


def _build_unlock(row: dict[str, Any]) -> CharacterUnlock:
    return CharacterUnlock(
        character_guid=int(row["CharacterGUID"]),
        unlock_kind=str(row["UnlockKind"]),
        unlock_id=int(row["UnlockID"]),
        source_arc_key=row.get("SourceArcKey"),
        source_quest_id=int(row["SourceQuestID"]) if row.get("SourceQuestID") not in (None, "") else None,
        grant_method=str(row.get("GrantMethod") or "control"),
        bot_eligible=bool(int(row.get("BotEligible") or 0)),
    )


def _build_reward(row: dict[str, Any]) -> RewardInstance:
    return RewardInstance(
        character_guid=int(row["CharacterGUID"]),
        reward_kind=str(row["RewardKind"]),
        template_id=int(row["TemplateID"]),
        source_arc_key=row.get("SourceArcKey"),
        source_quest_id=int(row["SourceQuestID"]) if row.get("SourceQuestID") not in (None, "") else None,
        is_equipped_gate=bool(int(row.get("IsEquippedGate") or 0)),
    )


def _build_conversation_steering(row: dict[str, Any]) -> ConversationSteeringNote:
    return ConversationSteeringNote(
        character_guid=int(row["CharacterGUID"]),
        steering_key=str(row["SteeringKey"]),
        steering_kind=str(row.get("SteeringKind") or "player_preference"),
        body=str(row["Body"]),
        priority=int(row.get("Priority") or 0),
        source=str(row.get("Source") or "operator"),
        is_active=bool(int(row.get("IsActive") or 0)),
        metadata=_parse_json_object(row.get("MetadataJSON")),
    )


def _build_prompt_queue_entry(row: dict[str, Any]) -> PromptQueueEntry:
    return PromptQueueEntry(
        character_guid=int(row["CharacterGUID"]),
        prompt_kind=str(row["PromptKind"]),
        body=str(row["Body"]),
        queue_id=int(row["QueueID"]) if row.get("QueueID") not in (None, "") else None,
        is_consumed=bool(int(row.get("IsConsumed") or 0)),
        created_at=str(row["CreatedAt"]) if row.get("CreatedAt") not in (None, "") else None,
    )


def _parse_json_list(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    try:
        parsed = json.loads(str(value))
        if isinstance(parsed, list):
            return [str(x) for x in parsed]
    except json.JSONDecodeError:
        return []
    return []


def _parse_json_object(value: Any) -> dict[str, Any]:
    if value in (None, ""):
        return {}
    try:
        parsed = json.loads(str(value))
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        return {}
    return {}


def _sql_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("'", "''")
    return f"'{escaped}'"


def _safe_error(exc: Exception) -> str:
    message = str(exc).strip()
    if not message:
        return type(exc).__name__
    return f"{type(exc).__name__}: {message}"
