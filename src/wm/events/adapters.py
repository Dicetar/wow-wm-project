from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from typing import Protocol

from wm.config import Settings
from wm.db.mysql_cli import MysqlCliClient
from wm.events.models import OBSERVED_EVENT_TYPES
from wm.events.models import WMEvent
from wm.events.store import EventStore
from wm.reactive.store import ReactiveQuestStore
from wm.sources.addon_log import AddonLogTailAdapter
from wm.sources.combat_log import CombatLogTailAdapter


ADAPTER_CHOICES = ("db", "addon_log", "combat_log")


class EventAdapter(Protocol):
    name: str

    def poll(self) -> list[WMEvent]:
        ...


@dataclass(slots=True)
class DBPollingAdapter:
    client: MysqlCliClient
    settings: Settings
    store: EventStore
    name: str = "db_poll"
    cursor_key: str = "last_seen"
    batch_size: int = 100
    player_guid_filter: int | None = None
    last_cursor_value: str | None = field(default=None, init=False)

    def poll(self) -> list[WMEvent]:
        cursor = self.store.get_cursor(adapter_name=self.name, cursor_key=self.cursor_key)
        last_seen = int(cursor.cursor_value) if cursor is not None else 0
        player_filter_sql = ""
        if self.player_guid_filter is not None:
            player_filter_sql = f" AND e.PlayerGUID = {int(self.player_guid_filter)}"

        rows = self.client.query(
            host=self.settings.world_db_host,
            port=self.settings.world_db_port,
            user=self.settings.world_db_user,
            password=self.settings.world_db_password,
            database=self.settings.world_db_name,
            sql=(
                "SELECT e.EventID, e.PlayerGUID, e.SubjectID, e.EventType, e.EventValue, e.CreatedAt, "
                "s.SubjectType, s.CreatureEntry, s.JournalName, s.HomeArea "
                "FROM wm_player_subject_event e "
                "JOIN wm_subject_definition s ON s.SubjectID = e.SubjectID "
                f"WHERE e.EventID > {last_seen} "
                f"{player_filter_sql} "
                "ORDER BY e.EventID "
                f"LIMIT {int(self.batch_size)}"
            ),
        )

        events: list[WMEvent] = []
        for row in rows:
            raw_event_type = str(row["EventType"]).strip().lower()
            if raw_event_type not in OBSERVED_EVENT_TYPES:
                continue
            subject_type = str(row["SubjectType"]).strip().lower()
            subject_entry_raw = row.get("CreatureEntry")
            if subject_entry_raw in (None, ""):
                continue

            event_id = int(row["EventID"])
            self.last_cursor_value = str(event_id)
            events.append(
                WMEvent(
                    event_class="observed",
                    event_type=raw_event_type,
                    source=self.name,
                    source_event_key=str(event_id),
                    occurred_at=str(row.get("CreatedAt") or ""),
                    player_guid=int(row["PlayerGUID"]),
                    subject_type=subject_type,
                    subject_entry=int(subject_entry_raw),
                    event_value=_string_or_none(row.get("EventValue")),
                    metadata={
                        "journal_subject_id": int(row["SubjectID"]),
                        "journal_subject_name": _string_or_none(row.get("JournalName")),
                        "home_area": _string_or_none(row.get("HomeArea")),
                        "legacy_event_id": event_id,
                        "raw_history_exists": True,
                    },
                )
            )

        if self.last_cursor_value is None and rows:
            self.last_cursor_value = str(rows[-1]["EventID"])
        return events


def build_event_adapter(
    *,
    adapter_name: str,
    client: MysqlCliClient,
    settings: Settings,
    store: EventStore,
    batch_size: int | None = None,
    player_guid_filter: int | None = None,
    reactive_store: ReactiveQuestStore | None = None,
) -> EventAdapter:
    if adapter_name == "db":
        return DBPollingAdapter(
            client=client,
            settings=settings,
            store=store,
            batch_size=int(batch_size or 100),
            player_guid_filter=player_guid_filter,
        )
    if adapter_name == "addon_log":
        reactive_store = reactive_store or ReactiveQuestStore(client=client, settings=settings)
        return AddonLogTailAdapter(
            client=client,
            settings=settings,
            store=store,
            reactive_store=reactive_store,
            batch_size=(int(batch_size) if batch_size is not None else int(settings.addon_log_batch_size)),
            player_guid_filter=player_guid_filter,
        )
    if adapter_name == "combat_log":
        reactive_store = reactive_store or ReactiveQuestStore(client=client, settings=settings)
        return CombatLogTailAdapter(
            client=client,
            settings=settings,
            store=store,
            reactive_store=reactive_store,
            batch_size=(int(batch_size) if batch_size is not None else int(settings.combat_log_batch_size)),
            player_guid_filter=player_guid_filter,
        )
    raise ValueError(f"Unsupported adapter: {adapter_name}")


def _string_or_none(value: object) -> str | None:
    if value in (None, ""):
        return None
    return str(value)
