from __future__ import annotations

from pathlib import Path

from wm.config import Settings
from wm.db.mysql_cli import MysqlCliClient
from wm.reactive.store import ReactiveQuestStore
from wm.sources.combat_log.models import CombatLogCursor
from wm.sources.combat_log.models import CombatLogScanResult
from wm.sources.combat_log.parser import CombatLogParser
from wm.sources.combat_log.resolver import CombatLogResolver
from wm.sources.combat_log.tailer import CombatLogTailer


class CombatLogScanner:
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
        self.parser = CombatLogParser()
        self.resolver = CombatLogResolver(client=client, settings=settings, reactive_store=reactive_store)

    def scan(
        self,
        *,
        player_guid: int,
        cursor_value: str | None,
        limit: int | None = None,
    ) -> CombatLogScanResult:
        path = Path(self.settings.combat_log_path)
        cursor = CombatLogCursor.from_cursor_value(cursor_value, default_path=str(path))
        tailer = CombatLogTailer(path=path)
        tail_result = tailer.read(
            cursor=cursor,
            max_lines=int(limit or self.settings.combat_log_batch_size),
        )
        result = CombatLogScanResult(
            file_exists=tail_result.file_exists,
            path=tail_result.path,
            cursor=tail_result.cursor,
        )
        if not tail_result.file_exists:
            return result

        for line in tail_result.lines:
            record = self.parser.parse_line(raw_line=line.raw_line, byte_offset=line.byte_offset)
            if record is None:
                continue
            if record.event_name != "PARTY_KILL":
                continue
            signal, failure = self.resolver.resolve_kill(
                record=record,
                player_guid=int(player_guid),
                log_path=tail_result.path,
                fingerprint=tail_result.cursor.fingerprint,
            )
            if signal is not None:
                result.signals.append(signal)
            if failure is not None:
                result.failures.append(failure)
        return result
