from __future__ import annotations

import json

from wm.config import Settings
from wm.db.mysql_cli import MysqlCliClient
from wm.events.store import _sql_datetime_or_expression
from wm.events.store import _sql_int_or_null
from wm.events.store import _sql_string
from wm.events.store import _str_or_none
from wm.refs import CreatureRef
from wm.refs import NpcRef
from wm.refs import PlayerRef
from wm.refs import QuestRef
from wm.refs import creature_ref_from_value
from wm.refs import npc_ref_from_value
from wm.refs import player_ref_from_value
from wm.refs import quest_ref_from_value
from wm.reactive.models import PlayerQuestRuntimeState
from wm.reactive.models import ReactiveQuestRule


class ReactiveQuestStore:
    def __init__(self, *, client: MysqlCliClient, settings: Settings) -> None:
        self.client = client
        self.settings = settings

    def upsert_rule(self, rule: ReactiveQuestRule) -> None:
        metadata_payload = dict(rule.metadata)
        metadata_payload["player_scope"] = (
            rule.player_scope.to_dict()
            if rule.player_scope is not None
            else (player_ref_from_value(metadata_payload.get("player_scope")) or PlayerRef(guid=int(rule.player_guid_scope or 0))).to_dict()
            if rule.player_guid_scope is not None
            else None
        )
        metadata_payload["subject"] = (
            rule.subject.to_dict()
            if rule.subject is not None
            else CreatureRef(entry=int(rule.subject_entry)).to_dict()
        )
        metadata_payload["quest"] = (
            rule.quest.to_dict()
            if rule.quest is not None
            else QuestRef(id=int(rule.quest_id)).to_dict()
        )
        metadata_payload["turn_in_npc"] = (
            rule.turn_in_npc.to_dict()
            if rule.turn_in_npc is not None
            else NpcRef(entry=int(rule.turn_in_npc_entry)).to_dict()
        )
        metadata_json = json.dumps(metadata_payload, ensure_ascii=False, sort_keys=True)
        notes_json = json.dumps(rule.notes, ensure_ascii=False)
        sql = (
            "INSERT INTO wm_reactive_quest_rule ("
            "RuleKey, IsActive, PlayerGUIDScope, SubjectType, SubjectEntry, TriggerEventType, "
            "KillThreshold, WindowSeconds, QuestID, TurnInNpcEntry, GrantMode, PostRewardCooldownSeconds, "
            "MetadataJSON, NotesJSON"
            ") VALUES ("
            f"{_sql_string(rule.rule_key)}, "
            f"{1 if rule.is_active else 0}, "
            f"{_sql_int_or_null(rule.player_guid_scope)}, "
            f"{_sql_string(rule.subject_type)}, "
            f"{int(rule.subject_entry)}, "
            f"{_sql_string(rule.trigger_event_type)}, "
            f"{int(rule.kill_threshold)}, "
            f"{int(rule.window_seconds)}, "
            f"{int(rule.quest_id)}, "
            f"{int(rule.turn_in_npc_entry)}, "
            f"{_sql_string(rule.grant_mode)}, "
            f"{int(rule.post_reward_cooldown_seconds)}, "
            f"{_sql_string(metadata_json)}, "
            f"{_sql_string(notes_json)}"
            ") ON DUPLICATE KEY UPDATE "
            "IsActive = VALUES(IsActive), "
            "PlayerGUIDScope = VALUES(PlayerGUIDScope), "
            "SubjectType = VALUES(SubjectType), "
            "SubjectEntry = VALUES(SubjectEntry), "
            "TriggerEventType = VALUES(TriggerEventType), "
            "KillThreshold = VALUES(KillThreshold), "
            "WindowSeconds = VALUES(WindowSeconds), "
            "QuestID = VALUES(QuestID), "
            "TurnInNpcEntry = VALUES(TurnInNpcEntry), "
            "GrantMode = VALUES(GrantMode), "
            "PostRewardCooldownSeconds = VALUES(PostRewardCooldownSeconds), "
            "MetadataJSON = VALUES(MetadataJSON), "
            "NotesJSON = VALUES(NotesJSON), "
            "UpdatedAt = CURRENT_TIMESTAMP"
        )
        self._execute_world(sql)

    def list_active_rules(
        self,
        *,
        subject_type: str | None = None,
        subject_entry: int | None = None,
        trigger_event_type: str | None = None,
        player_guid: int | None = None,
    ) -> list[ReactiveQuestRule]:
        predicates = ["IsActive = 1"]
        if subject_type is not None:
            predicates.append(f"SubjectType = {_sql_string(subject_type)}")
        if subject_entry is not None:
            predicates.append(f"SubjectEntry = {int(subject_entry)}")
        if trigger_event_type is not None:
            predicates.append(f"TriggerEventType = {_sql_string(trigger_event_type)}")
        if player_guid is not None:
            predicates.append(
                f"(PlayerGUIDScope IS NULL OR PlayerGUIDScope = {int(player_guid)})"
            )
        rows = self.client.query(
            host=self.settings.world_db_host,
            port=self.settings.world_db_port,
            user=self.settings.world_db_user,
            password=self.settings.world_db_password,
            database=self.settings.world_db_name,
            sql=(
                "SELECT RuleKey, IsActive, PlayerGUIDScope, SubjectType, SubjectEntry, TriggerEventType, KillThreshold, "
                "WindowSeconds, QuestID, TurnInNpcEntry, GrantMode, PostRewardCooldownSeconds, MetadataJSON, NotesJSON "
                "FROM wm_reactive_quest_rule "
                f"WHERE {' AND '.join(predicates)} "
                "ORDER BY RuleKey"
            ),
        )
        return [self._row_to_rule(row) for row in rows]

    def get_rule_by_quest_id(self, *, quest_id: int) -> ReactiveQuestRule | None:
        rows = self.client.query(
            host=self.settings.world_db_host,
            port=self.settings.world_db_port,
            user=self.settings.world_db_user,
            password=self.settings.world_db_password,
            database=self.settings.world_db_name,
            sql=(
                "SELECT RuleKey, IsActive, PlayerGUIDScope, SubjectType, SubjectEntry, TriggerEventType, KillThreshold, "
                "WindowSeconds, QuestID, TurnInNpcEntry, GrantMode, PostRewardCooldownSeconds, MetadataJSON, NotesJSON "
                "FROM wm_reactive_quest_rule "
                f"WHERE QuestID = {int(quest_id)} AND IsActive = 1 "
                "ORDER BY RuleKey LIMIT 1"
            ),
        )
        if not rows:
            return None
        return self._row_to_rule(rows[0])

    def get_rule_by_key(self, *, rule_key: str) -> ReactiveQuestRule | None:
        rows = self.client.query(
            host=self.settings.world_db_host,
            port=self.settings.world_db_port,
            user=self.settings.world_db_user,
            password=self.settings.world_db_password,
            database=self.settings.world_db_name,
            sql=(
                "SELECT RuleKey, IsActive, PlayerGUIDScope, SubjectType, SubjectEntry, TriggerEventType, KillThreshold, "
                "WindowSeconds, QuestID, TurnInNpcEntry, GrantMode, PostRewardCooldownSeconds, MetadataJSON, NotesJSON "
                "FROM wm_reactive_quest_rule "
                f"WHERE RuleKey = {_sql_string(rule_key)} "
                "LIMIT 1"
            ),
        )
        if not rows:
            return None
        return self._row_to_rule(rows[0])

    def list_active_quest_ids(self) -> set[int]:
        rows = self.client.query(
            host=self.settings.world_db_host,
            port=self.settings.world_db_port,
            user=self.settings.world_db_user,
            password=self.settings.world_db_password,
            database=self.settings.world_db_name,
            sql="SELECT QuestID FROM wm_reactive_quest_rule WHERE IsActive = 1 ORDER BY QuestID",
        )
        return {
            int(row["QuestID"])
            for row in rows
            if row.get("QuestID") not in (None, "")
        }

    def deactivate_player_quest_rules(
        self,
        *,
        player_guid: int,
        quest_id: int,
        except_rule_key: str | None = None,
    ) -> None:
        predicates = [
            f"PlayerGUIDScope = {int(player_guid)}",
            f"QuestID = {int(quest_id)}",
        ]
        if except_rule_key not in (None, ""):
            predicates.append(f"RuleKey <> {_sql_string(str(except_rule_key))}")
        sql = (
            "UPDATE wm_reactive_quest_rule "
            "SET IsActive = 0, UpdatedAt = CURRENT_TIMESTAMP "
            f"WHERE {' AND '.join(predicates)}"
        )
        self._execute_world(sql)

    def deactivate_player_bounty_rules(
        self,
        *,
        player_guid: int,
        except_rule_key: str | None = None,
    ) -> None:
        predicates = [
            f"PlayerGUIDScope = {int(player_guid)}",
            "RuleKey LIKE 'reactive_bounty:%'",
        ]
        if except_rule_key not in (None, ""):
            predicates.append(f"RuleKey <> {_sql_string(str(except_rule_key))}")
        sql = (
            "UPDATE wm_reactive_quest_rule "
            "SET IsActive = 0, UpdatedAt = CURRENT_TIMESTAMP "
            f"WHERE {' AND '.join(predicates)}"
        )
        self._execute_world(sql)

    def deactivate_player_auto_bounty_rules(
        self,
        *,
        player_guid: int,
        except_rule_key: str | None = None,
    ) -> None:
        predicates = [
            f"PlayerGUIDScope = {int(player_guid)}",
            "RuleKey LIKE 'reactive_bounty:auto:%'",
        ]
        if except_rule_key not in (None, ""):
            predicates.append(f"RuleKey <> {_sql_string(str(except_rule_key))}")
        sql = (
            "UPDATE wm_reactive_quest_rule "
            "SET IsActive = 0, UpdatedAt = CURRENT_TIMESTAMP "
            f"WHERE {' AND '.join(predicates)}"
        )
        self._execute_world(sql)

    def get_player_quest_runtime_state(self, *, player_guid: int, quest_id: int) -> PlayerQuestRuntimeState | None:
        rows = self.client.query(
            host=self.settings.world_db_host,
            port=self.settings.world_db_port,
            user=self.settings.world_db_user,
            password=self.settings.world_db_password,
            database=self.settings.world_db_name,
            sql=(
                "SELECT CurrentState, LastTransitionAt, LastObservedAt, MetadataJSON "
                "FROM wm_player_quest_runtime_state "
                f"WHERE PlayerGUID = {int(player_guid)} AND QuestID = {int(quest_id)}"
            ),
        )
        if not rows:
            return None
        row = rows[0]
        return PlayerQuestRuntimeState(
            player_guid=int(player_guid),
            quest_id=int(quest_id),
            current_state=str(row["CurrentState"]),
            last_transition_at=_str_or_none(row.get("LastTransitionAt")),
            last_observed_at=_str_or_none(row.get("LastObservedAt")),
            metadata=_json_dict(row.get("MetadataJSON")),
        )

    def set_player_quest_runtime_state(self, state: PlayerQuestRuntimeState) -> None:
        metadata_json = json.dumps(state.metadata, ensure_ascii=False, sort_keys=True)
        last_transition_sql = (
            "CURRENT_TIMESTAMP"
            if state.last_transition_at in (None, "")
            else _sql_datetime_or_expression(str(state.last_transition_at))
        )
        last_observed_sql = (
            "CURRENT_TIMESTAMP"
            if state.last_observed_at in (None, "")
            else _sql_datetime_or_expression(str(state.last_observed_at))
        )
        sql = (
            "INSERT INTO wm_player_quest_runtime_state ("
            "PlayerGUID, QuestID, CurrentState, LastTransitionAt, LastObservedAt, MetadataJSON"
            ") VALUES ("
            f"{int(state.player_guid)}, "
            f"{int(state.quest_id)}, "
            f"{_sql_string(state.current_state)}, "
            f"{last_transition_sql}, "
            f"{last_observed_sql}, "
            f"{_sql_string(metadata_json)}"
            ") ON DUPLICATE KEY UPDATE "
            "CurrentState = VALUES(CurrentState), "
            "LastTransitionAt = VALUES(LastTransitionAt), "
            "LastObservedAt = VALUES(LastObservedAt), "
            "MetadataJSON = VALUES(MetadataJSON)"
        )
        self._execute_world(sql)

    def fetch_character_quest_status(self, *, player_guid: int, quest_id: int) -> str:
        active_rows = self.client.query(
            host=self.settings.char_db_host,
            port=self.settings.char_db_port,
            user=self.settings.char_db_user,
            password=self.settings.char_db_password,
            database=self.settings.char_db_name,
            sql=(
                "SELECT status FROM character_queststatus "
                f"WHERE guid = {int(player_guid)} AND quest = {int(quest_id)} LIMIT 1"
            ),
        )
        if active_rows:
            status = int(active_rows[0].get("status") or 0)
            if status == 1:
                return "complete"
            if status == 3:
                return "incomplete"
            return "incomplete"

        rewarded_rows = self.client.query(
            host=self.settings.char_db_host,
            port=self.settings.char_db_port,
            user=self.settings.char_db_user,
            password=self.settings.char_db_password,
            database=self.settings.char_db_name,
            sql=(
                "SELECT quest FROM character_queststatus_rewarded "
                f"WHERE guid = {int(player_guid)} AND quest = {int(quest_id)} LIMIT 1"
            ),
        )
        if rewarded_rows:
            return "rewarded"
        return "none"

    def fetch_character_name(self, *, player_guid: int) -> str | None:
        rows = self.client.query(
            host=self.settings.char_db_host,
            port=self.settings.char_db_port,
            user=self.settings.char_db_user,
            password=self.settings.char_db_password,
            database=self.settings.char_db_name,
            sql=(
                "SELECT name FROM characters "
                f"WHERE guid = {int(player_guid)} LIMIT 1"
            ),
        )
        if not rows:
            return None
        value = rows[0].get("name")
        if value in (None, ""):
            return None
        return str(value)

    def _row_to_rule(self, row: dict[str, object]) -> ReactiveQuestRule:
        metadata = _json_dict(row.get("MetadataJSON"))
        return ReactiveQuestRule(
            rule_key=str(row["RuleKey"]),
            is_active=int(row.get("IsActive") or 0) == 1,
            player_guid_scope=int(row["PlayerGUIDScope"]) if row.get("PlayerGUIDScope") not in (None, "") else None,
            subject_type=str(row["SubjectType"]),
            subject_entry=int(row["SubjectEntry"]),
            trigger_event_type=str(row["TriggerEventType"]),
            kill_threshold=int(row["KillThreshold"]),
            window_seconds=int(row["WindowSeconds"]),
            quest_id=int(row["QuestID"]),
            turn_in_npc_entry=int(row["TurnInNpcEntry"]),
            grant_mode=str(row["GrantMode"]),
            post_reward_cooldown_seconds=int(row["PostRewardCooldownSeconds"]),
            metadata=metadata,
            notes=_json_list(row.get("NotesJSON")),
            player_scope=player_ref_from_value(metadata.get("player_scope")),
            subject=creature_ref_from_value(metadata.get("subject")),
            quest=quest_ref_from_value(metadata.get("quest")),
            turn_in_npc=npc_ref_from_value(metadata.get("turn_in_npc")),
        )

    def _execute_world(self, sql: str) -> None:
        self.client.query(
            host=self.settings.world_db_host,
            port=self.settings.world_db_port,
            user=self.settings.world_db_user,
            password=self.settings.world_db_password,
            database=self.settings.world_db_name,
            sql=sql,
        )

def _json_dict(value: object) -> dict[str, object]:
    if value in (None, ""):
        return {}
    try:
        parsed = json.loads(str(value))
    except json.JSONDecodeError:
        return {"raw": str(value)}
    if isinstance(parsed, dict):
        return parsed
    return {"value": parsed}


def _json_list(value: object) -> list[str]:
    if value in (None, ""):
        return []
    try:
        parsed = json.loads(str(value))
    except json.JSONDecodeError:
        return [str(value)]
    if isinstance(parsed, list):
        return [str(item) for item in parsed]
    return [str(parsed)]
