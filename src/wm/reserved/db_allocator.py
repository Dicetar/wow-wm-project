from __future__ import annotations

import json
import subprocess
from typing import Any

from wm.config import Settings
from wm.db.mysql_cli import MysqlCliClient, MysqlCliError
from wm.reserved.models import ReservedSlot


class ReservedSlotDbAllocator:
    def __init__(self, client: MysqlCliClient, settings: Settings) -> None:
        self.client = client
        self.settings = settings

    def allocate_next_free_slot(
        self,
        *,
        entity_type: str,
        arc_key: str | None = None,
        character_guid: int | None = None,
        source_quest_id: int | None = None,
        notes: list[str] | None = None,
    ) -> ReservedSlot | None:
        rows = self.client.query(
            host=self.settings.world_db_host,
            port=self.settings.world_db_port,
            user=self.settings.world_db_user,
            password=self.settings.world_db_password,
            database=self.settings.world_db_name,
            sql=(
                "SELECT EntityType, ReservedID, SlotStatus, ArcKey, CharacterGUID, SourceQuestID, NotesJSON "
                "FROM wm_reserved_slot "
                f"WHERE EntityType = {_sql_string(entity_type)} AND SlotStatus = 'free' "
                "ORDER BY ReservedID LIMIT 1"
            ),
        )
        if not rows:
            return None

        reserved_id = int(rows[0]["ReservedID"])
        notes_json = _json_or_null(notes or [])
        sql = (
            "UPDATE wm_reserved_slot SET "
            "SlotStatus = 'staged', "
            f"ArcKey = {_sql_string_or_null(arc_key)}, "
            f"CharacterGUID = {_sql_int_or_null(character_guid)}, "
            f"SourceQuestID = {_sql_int_or_null(source_quest_id)}, "
            f"NotesJSON = {notes_json} "
            f"WHERE EntityType = {_sql_string(entity_type)} "
            f"AND ReservedID = {reserved_id} "
            "AND SlotStatus = 'free'"
        )
        self._execute(sql)
        return self.get_slot(entity_type=entity_type, reserved_id=reserved_id)

    def transition_slot(
        self,
        *,
        entity_type: str,
        reserved_id: int,
        new_status: str,
    ) -> ReservedSlot | None:
        sql = (
            "UPDATE wm_reserved_slot SET "
            f"SlotStatus = {_sql_string(new_status)} "
            f"WHERE EntityType = {_sql_string(entity_type)} AND ReservedID = {int(reserved_id)}"
        )
        self._execute(sql)
        return self.get_slot(entity_type=entity_type, reserved_id=reserved_id)

    def release_slot(
        self,
        *,
        entity_type: str,
        reserved_id: int,
        archive: bool = False,
    ) -> ReservedSlot | None:
        new_status = "archived" if archive else "retired"
        sql = (
            "UPDATE wm_reserved_slot SET "
            f"SlotStatus = {_sql_string(new_status)}, "
            "ArcKey = NULL, CharacterGUID = NULL, SourceQuestID = NULL, NotesJSON = NULL "
            f"WHERE EntityType = {_sql_string(entity_type)} AND ReservedID = {int(reserved_id)}"
        )
        self._execute(sql)
        return self.get_slot(entity_type=entity_type, reserved_id=reserved_id)

    def get_slot(self, *, entity_type: str, reserved_id: int) -> ReservedSlot | None:
        rows = self.client.query(
            host=self.settings.world_db_host,
            port=self.settings.world_db_port,
            user=self.settings.world_db_user,
            password=self.settings.world_db_password,
            database=self.settings.world_db_name,
            sql=(
                "SELECT EntityType, ReservedID, SlotStatus, ArcKey, CharacterGUID, SourceQuestID, NotesJSON "
                "FROM wm_reserved_slot "
                f"WHERE EntityType = {_sql_string(entity_type)} AND ReservedID = {int(reserved_id)}"
            ),
        )
        if not rows:
            return None
        return _build_slot(rows[0])

    def summarize(self) -> list[dict[str, Any]]:
        return self.client.query(
            host=self.settings.world_db_host,
            port=self.settings.world_db_port,
            user=self.settings.world_db_user,
            password=self.settings.world_db_password,
            database=self.settings.world_db_name,
            sql=(
                "SELECT EntityType, SlotStatus, COUNT(*) AS CountRows "
                "FROM wm_reserved_slot GROUP BY EntityType, SlotStatus ORDER BY EntityType, SlotStatus"
            ),
        )

    def _execute(self, sql: str) -> None:
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


def _build_slot(row: dict[str, Any]) -> ReservedSlot:
    notes: list[str] = []
    if row.get("NotesJSON") not in (None, ""):
        try:
            parsed = json.loads(str(row["NotesJSON"]))
            if isinstance(parsed, list):
                notes = [str(x) for x in parsed]
        except json.JSONDecodeError:
            notes = []
    return ReservedSlot(
        entity_type=str(row["EntityType"]),
        reserved_id=int(row["ReservedID"]),
        slot_status=str(row["SlotStatus"]),
        arc_key=row.get("ArcKey"),
        character_guid=int(row["CharacterGUID"]) if row.get("CharacterGUID") not in (None, "") else None,
        source_quest_id=int(row["SourceQuestID"]) if row.get("SourceQuestID") not in (None, "") else None,
        notes=notes,
    )


def _sql_string(value: str) -> str:
    escaped = value.replace("'", "''")
    return f"'{escaped}'"


def _sql_string_or_null(value: str | None) -> str:
    return "NULL" if value is None else _sql_string(value)


def _sql_int_or_null(value: int | None) -> str:
    return "NULL" if value is None else str(int(value))


def _json_or_null(value: Any) -> str:
    if value is None:
        return "NULL"
    payload = json.dumps(value, ensure_ascii=False).replace("'", "''")
    return f"'{payload}'"
