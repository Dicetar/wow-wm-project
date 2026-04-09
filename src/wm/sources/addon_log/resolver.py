from __future__ import annotations

from typing import Any

from wm.config import Settings
from wm.db.mysql_cli import MysqlCliClient
from wm.reactive.models import ReactiveQuestRule
from wm.reactive.store import ReactiveQuestStore
from wm.refs import CreatureRef
from wm.refs import PlayerRef
from wm.sources.addon_log.models import AddonEventSignal
from wm.sources.addon_log.models import AddonLogRecord
from wm.sources.addon_log.models import AddonResolutionFailure


class AddonLogResolver:
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

    def resolve(
        self,
        *,
        record: AddonLogRecord,
        player_guid: int,
        log_path: str,
        fingerprint: str | None,
    ) -> tuple[AddonEventSignal | None, AddonResolutionFailure | None]:
        if record.event_type == "HELLO":
            return self._resolve_hello(
                record=record,
                player_guid=player_guid,
                log_path=log_path,
                fingerprint=fingerprint,
            )
        if record.event_type == "KILL":
            return self._resolve_kill(
                record=record,
                player_guid=player_guid,
                log_path=log_path,
                fingerprint=fingerprint,
            )
        return None, _failure(
            reason="unsupported_event_type",
            record=record,
            details={"event_type": record.event_type},
        )

    def _resolve_hello(
        self,
        *,
        record: AddonLogRecord,
        player_guid: int,
        log_path: str,
        fingerprint: str | None,
    ) -> tuple[AddonEventSignal | None, AddonResolutionFailure | None]:
        player_ref, player_source, failure = self._resolve_player_ref(
            player_guid=int(player_guid),
            payload_player_guid=record.payload_fields.get("player_guid"),
            payload_player_name=record.payload_fields.get("player"),
        )
        if failure is not None or player_ref is None:
            return None, _failure(
                reason=failure or "player_unresolved",
                record=record,
                details={"player_guid": int(player_guid)},
            )

        signal = AddonEventSignal(
            event_type="hello",
            player_ref=player_ref,
            occurred_at=record.occurred_at,
            raw_line=record.raw_line,
            raw_payload=record.raw_payload,
            byte_offset=int(record.byte_offset),
            source_event_key=f"{fingerprint or 'unknown'}:{int(record.byte_offset)}",
            log_path=log_path,
            resolution_source=player_source,
            channel=record.payload_fields.get("channel") or self.settings.addon_channel_name,
        )
        return signal, None

    def _resolve_kill(
        self,
        *,
        record: AddonLogRecord,
        player_guid: int,
        log_path: str,
        fingerprint: str | None,
    ) -> tuple[AddonEventSignal | None, AddonResolutionFailure | None]:
        player_ref, player_source, failure = self._resolve_player_ref(
            player_guid=int(player_guid),
            payload_player_guid=record.payload_fields.get("player_guid"),
            payload_player_name=record.payload_fields.get("player"),
        )
        if failure is not None or player_ref is None:
            return None, _failure(
                reason=failure or "player_unresolved",
                record=record,
                details={"player_guid": int(player_guid)},
            )

        subject_ref, subject_source, subject_failure = self._resolve_subject_ref(
            player_guid=int(player_guid),
            subject_name=record.payload_fields.get("target"),
            trigger_event_type="kill",
        )
        if subject_failure is not None or subject_ref is None:
            return None, _failure(
                reason=subject_failure or "subject_unresolved",
                record=record,
                details={"subject_name": record.payload_fields.get("target")},
            )

        signal = AddonEventSignal(
            event_type="kill",
            player_ref=player_ref,
            subject_ref=subject_ref,
            occurred_at=record.occurred_at,
            raw_line=record.raw_line,
            raw_payload=record.raw_payload,
            byte_offset=int(record.byte_offset),
            source_event_key=f"{fingerprint or 'unknown'}:{int(record.byte_offset)}",
            log_path=log_path,
            resolution_source=f"{player_source}+{subject_source}",
            channel=record.payload_fields.get("channel") or self.settings.addon_channel_name,
            subevent=record.payload_fields.get("subevent"),
            target_guid=record.payload_fields.get("target_guid"),
        )
        return signal, None

    def _resolve_player_ref(
        self,
        *,
        player_guid: int,
        payload_player_guid: str | None,
        payload_player_name: str | None,
    ) -> tuple[PlayerRef | None, str, str | None]:
        if payload_player_guid not in (None, ""):
            try:
                parsed_guid = int(str(payload_player_guid))
            except ValueError:
                return None, "payload_guid", "invalid_player_guid"
            if parsed_guid != int(player_guid):
                return None, "payload_guid", "player_guid_mismatch"
            resolved_name = payload_player_name or self.reactive_store.fetch_character_name(player_guid=int(player_guid))
            return PlayerRef(guid=int(player_guid), name=_str_or_none(resolved_name)), "payload_guid", None

        if payload_player_name in (None, ""):
            return None, "player_name", "missing_player_name"

        rows = self.client.query(
            host=self.settings.char_db_host,
            port=self.settings.char_db_port,
            user=self.settings.char_db_user,
            password=self.settings.char_db_password,
            database=self.settings.char_db_name,
            sql=(
                "SELECT guid, name FROM characters "
                f"WHERE name = {_sql_string(str(payload_player_name))} "
                "ORDER BY guid LIMIT 2"
            ),
        )
        if len(rows) == 0:
            return None, "player_name", "unknown_player_name"
        if len(rows) > 1:
            return None, "player_name", "ambiguous_player_name"
        row = rows[0]
        resolved_guid = int(row["guid"])
        if resolved_guid != int(player_guid):
            return None, "player_name", "player_guid_scope_mismatch"
        return PlayerRef(guid=resolved_guid, name=str(row["name"])), "player_name", None

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


def _failure(*, reason: str, record: AddonLogRecord, details: dict[str, Any]) -> AddonResolutionFailure:
    return AddonResolutionFailure(
        reason=reason,
        byte_offset=int(record.byte_offset),
        raw_line=record.raw_line,
        event_type=record.event_type,
        occurred_at=record.occurred_at,
        raw_payload=record.raw_payload,
        details=details,
    )


def _normalized_name(value: str | None) -> str | None:
    if value in (None, ""):
        return None
    return str(value).strip().casefold()


def _sql_string(value: str) -> str:
    return "'" + value.replace("\\", "\\\\").replace("'", "''") + "'"


def _str_or_none(value: object) -> str | None:
    if value in (None, ""):
        return None
    return str(value)
