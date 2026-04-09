from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field

from wm.config import Settings
from wm.db.mysql_cli import MysqlCliClient
from wm.events.models import WMEvent
from wm.events.store import EventStore
from wm.reactive.store import ReactiveQuestStore
from wm.sources.combat_log.models import CombatLogScanResult
from wm.sources.combat_log.scanner import CombatLogScanner


@dataclass(slots=True)
class CombatLogTailAdapter:
    client: MysqlCliClient
    settings: Settings
    store: EventStore
    reactive_store: ReactiveQuestStore
    name: str = "combat_log"
    cursor_key: str = "state"
    batch_size: int | None = None
    player_guid_filter: int | None = None
    last_cursor_value: str | None = field(default=None, init=False)
    last_scan_result: CombatLogScanResult | None = field(default=None, init=False)

    def poll(self) -> list[WMEvent]:
        if self.player_guid_filter is None:
            raise ValueError("Combat log polling requires --player-guid to resolve the source player.")
        cursor = self.store.get_cursor(adapter_name=self.name, cursor_key=self.cursor_key)
        scanner = CombatLogScanner(
            client=self.client,
            settings=self.settings,
            reactive_store=self.reactive_store,
        )
        scan_result = scanner.scan(
            player_guid=int(self.player_guid_filter),
            cursor_value=cursor.cursor_value if cursor is not None else None,
            limit=self.batch_size,
        )
        self.last_scan_result = scan_result
        self.last_cursor_value = scan_result.cursor.to_cursor_value()
        return [
            WMEvent(
                event_class="observed",
                event_type="kill",
                source=self.name,
                source_event_key=signal.source_event_key,
                occurred_at=signal.occurred_at,
                player_guid=signal.player_ref.guid,
                subject_type="creature",
                subject_entry=signal.subject_ref.entry,
                event_value="1",
                metadata={
                    "player_name": signal.player_ref.name,
                    "subject_name": signal.subject_ref.name,
                    "raw_event_name": signal.event_name,
                    "log_path": signal.log_path,
                    "byte_offset": signal.byte_offset,
                    "resolution_source": signal.resolution_source,
                    "raw_line": signal.raw_line,
                },
            )
            for signal in scan_result.signals
        ]
