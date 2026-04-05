from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from wm.character.models import ArcState, CharacterProfile, CharacterUnlock, PromptQueueEntry, RewardInstance
from wm.config import Settings
from wm.db.mysql_cli import MysqlCliClient


@dataclass(slots=True)
class CharacterStateBundle:
    profile: CharacterProfile | None
    arc_states: list[ArcState]
    unlocks: list[CharacterUnlock]
    rewards: list[RewardInstance]
    prompt_queue: list[PromptQueueEntry]


def load_character_state(
    *,
    client: MysqlCliClient,
    settings: Settings,
    character_guid: int,
) -> CharacterStateBundle:
    guid = int(character_guid)

    profile_rows = client.query(
        host=settings.char_db_host,
        port=settings.char_db_port,
        user=settings.char_db_user,
        password=settings.char_db_password,
        database=settings.char_db_name,
        sql=(
            "SELECT CharacterGUID, CharacterName, WMPersona, Tone, PreferredThemesJSON, AvoidedThemesJSON "
            f"FROM wm_character_profile WHERE CharacterGUID = {guid}"
        ),
    )

    arc_rows = client.query(
        host=settings.char_db_host,
        port=settings.char_db_port,
        user=settings.char_db_user,
        password=settings.char_db_password,
        database=settings.char_db_name,
        sql=(
            "SELECT CharacterGUID, ArcKey, StageKey, Status, BranchKey, Summary "
            f"FROM wm_character_arc_state WHERE CharacterGUID = {guid} ORDER BY ArcKey"
        ),
    )

    unlock_rows = client.query(
        host=settings.char_db_host,
        port=settings.char_db_port,
        user=settings.char_db_user,
        password=settings.char_db_password,
        database=settings.char_db_name,
        sql=(
            "SELECT CharacterGUID, UnlockKind, UnlockID, SourceArcKey, SourceQuestID, GrantMethod, BotEligible "
            f"FROM wm_character_unlock WHERE CharacterGUID = {guid} ORDER BY UnlockKind, UnlockID"
        ),
    )

    reward_rows = client.query(
        host=settings.char_db_host,
        port=settings.char_db_port,
        user=settings.char_db_user,
        password=settings.char_db_password,
        database=settings.char_db_name,
        sql=(
            "SELECT CharacterGUID, RewardKind, TemplateID, SourceArcKey, SourceQuestID, IsEquippedGate "
            f"FROM wm_character_reward_instance WHERE CharacterGUID = {guid} ORDER BY GrantedAt DESC"
        ),
    )

    prompt_rows = client.query(
        host=settings.char_db_host,
        port=settings.char_db_port,
        user=settings.char_db_user,
        password=settings.char_db_password,
        database=settings.char_db_name,
        sql=(
            "SELECT CharacterGUID, PromptKind, Body "
            f"FROM wm_character_prompt_queue WHERE CharacterGUID = {guid} AND IsConsumed = 0 ORDER BY QueueID"
        ),
    )

    profile = _build_profile(profile_rows[0]) if profile_rows else None
    arc_states = [_build_arc_state(row) for row in arc_rows]
    unlocks = [_build_unlock(row) for row in unlock_rows]
    rewards = [_build_reward(row) for row in reward_rows]
    prompt_queue = [_build_prompt_queue_entry(row) for row in prompt_rows]

    return CharacterStateBundle(
        profile=profile,
        arc_states=arc_states,
        unlocks=unlocks,
        rewards=rewards,
        prompt_queue=prompt_queue,
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
        grant_method=str(row.get("GrantMethod") or "gm_command"),
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


def _build_prompt_queue_entry(row: dict[str, Any]) -> PromptQueueEntry:
    return PromptQueueEntry(
        character_guid=int(row["CharacterGUID"]),
        prompt_kind=str(row["PromptKind"]),
        body=str(row["Body"]),
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
