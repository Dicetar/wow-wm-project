from __future__ import annotations

from typing import Any

from wm.config import Settings
from wm.db.mysql_cli import MysqlCliClient
from wm.reactive.models import ReactiveQuestRule
from wm.reactive.store import ReactiveQuestStore
from wm.refs import CreatureRef
from wm.refs import PlayerRef
from wm.sources.combat_log.models import CombatKillSignal
from wm.sources.combat_log.models import CombatLogRecord
from wm.sources.combat_log.models import CombatResolutionFailure


class CombatLogResolver:
    def __init__(
        self,
        *,
        client: MysqlCliClient,
        settings: Settings,
        reactive_store: ReactiveQuestStore,
    ) -> None:
        self.client = client
        self.settings = settings
        self.reactive_store = reactive_store
        self._creature_name_cache: dict[int, str | None] = {}

    def resolve_kill(
        self,
        *,
        record: CombatLogRecord,
        player_guid: int,
        log_path: str,
        fingerprint: str | None,
    ) -> tuple[CombatKillSignal | None, CombatResolutionFailure | None]:
        player_name = self.settings.combat_log_player_name or self.reactive_store.fetch_character_name(
            player_guid=int(player_guid)
        )
        source_name = _normalized_name(record.source_actor.name if record.source_actor is not None else None)
        if player_name in (None, ""):
            return None, _failure(
                reason="player_name_unresolved",
                record=record,
                details={"player_guid": int(player_guid)},
            )
        if source_name != _normalized_name(player_name):
            return None, _failure(
                reason="source_player_mismatch",
                record=record,
                details={"expected_player_name": player_name, "source_actor_name": source_name},
            )

        subject_name = record.dest_actor.name if record.dest_actor is not None else None
        subject_ref, resolution_source, failure = self._resolve_subject_ref(
            player_guid=int(player_guid),
            subject_name=subject_name,
            trigger_event_type="kill",
        )
        if failure is not None or subject_ref is None:
            return None, _failure(
                reason=failure or "subject_unresolved",
                record=record,
                details={"subject_name": subject_name},
            )

        source_event_key = f"{fingerprint or 'unknown'}:{int(record.byte_offset)}"
        signal = CombatKillSignal(
            player_ref=PlayerRef(guid=int(player_guid), name=str(player_name)),
            subject_ref=subject_ref,
            occurred_at=record.occurred_at,
            raw_line=record.raw_line,
            byte_offset=int(record.byte_offset),
            source_event_key=source_event_key,
            event_name=record.event_name,
            log_path=log_path,
            resolution_source=resolution_source,
        )
        return signal, None

    def resolve_death(
        self,
        *,
        record: CombatLogRecord,
        player_guid: int,
        log_path: str,
        fingerprint: str | None,
        resolution_source: str,
    ) -> tuple[CombatKillSignal | None, CombatResolutionFailure | None]:
        player_name = self.settings.combat_log_player_name or self.reactive_store.fetch_character_name(
            player_guid=int(player_guid)
        )
        if player_name in (None, ""):
            return None, _failure(
                reason="player_name_unresolved",
                record=record,
                details={"player_guid": int(player_guid)},
            )

        subject_name = record.dest_actor.name if record.dest_actor is not None else None
        subject_ref, _, failure = self._resolve_subject_ref(
            player_guid=int(player_guid),
            subject_name=subject_name,
            trigger_event_type="kill",
        )
        if failure is not None or subject_ref is None:
            return None, _failure(
                reason=failure or "subject_unresolved",
                record=record,
                details={"subject_name": subject_name},
            )

        source_event_key = f"{fingerprint or 'unknown'}:{int(record.byte_offset)}"
        signal = CombatKillSignal(
            player_ref=PlayerRef(guid=int(player_guid), name=str(player_name)),
            subject_ref=subject_ref,
            occurred_at=record.occurred_at,
            raw_line=record.raw_line,
            byte_offset=int(record.byte_offset),
            source_event_key=source_event_key,
            event_name=record.event_name,
            log_path=log_path,
            resolution_source=resolution_source,
        )
        return signal, None

    def _resolve_subject_ref(
        self,
        *,
        player_guid: int,
        subject_name: str | None,
        trigger_event_type: str,
    ) -> tuple[CreatureRef | None, str, str | None]:
        normalized_name = _normalized_name(subject_name)
        if normalized_name in (None, ""):
            return None, "none", "missing_subject_name"

        rules = self.reactive_store.list_active_rules(
            player_guid=int(player_guid),
            trigger_event_type=trigger_event_type,
        )
        for rule in rules:
            hinted_name = self._rule_subject_name(rule)
            if hinted_name is not None and _normalized_name(hinted_name) == normalized_name:
                return CreatureRef(entry=int(rule.subject_entry), name=hinted_name), "rule_hint", None

        rows = self.client.query(
            host=self.settings.world_db_host,
            port=self.settings.world_db_port,
            user=self.settings.world_db_user,
            password=self.settings.world_db_password,
            database=self.settings.world_db_name,
            sql=(
                "SELECT `entry`, `name` FROM `creature_template` "
                f"WHERE `name` = {_sql_string(str(subject_name))} "
                "ORDER BY `entry` LIMIT 2"
            ),
        )
        if len(rows) == 1:
            row = rows[0]
            return CreatureRef(entry=int(row["entry"]), name=str(row["name"])), "creature_exact_name", None
        if len(rows) > 1:
            return None, "creature_exact_name", "ambiguous_creature_name"
        return None, "creature_exact_name", "unknown_creature_name"

    def _rule_subject_name(self, rule: ReactiveQuestRule) -> str | None:
        if rule.subject is not None and rule.subject.name not in (None, ""):
            return rule.subject.name
        cached = self._creature_name_cache.get(int(rule.subject_entry))
        if cached is not None:
            return cached
        rows = self.client.query(
            host=self.settings.world_db_host,
            port=self.settings.world_db_port,
            user=self.settings.world_db_user,
            password=self.settings.world_db_password,
            database=self.settings.world_db_name,
            sql=(
                "SELECT `name` FROM `creature_template` "
                f"WHERE `entry` = {int(rule.subject_entry)} LIMIT 1"
            ),
        )
        if not rows:
            self._creature_name_cache[int(rule.subject_entry)] = None
            return None
        name = str(rows[0]["name"])
        self._creature_name_cache[int(rule.subject_entry)] = name
        return name


def _failure(*, reason: str, record: CombatLogRecord, details: dict[str, Any]) -> CombatResolutionFailure:
    return CombatResolutionFailure(
        reason=reason,
        byte_offset=int(record.byte_offset),
        raw_line=record.raw_line,
        event_name=record.event_name,
        occurred_at=record.occurred_at,
        details=details,
    )


def _normalized_name(value: str | None) -> str | None:
    if value in (None, ""):
        return None
    return str(value).strip().casefold()


def _sql_string(value: str) -> str:
    return "'" + value.replace("\\", "\\\\").replace("'", "''") + "'"
