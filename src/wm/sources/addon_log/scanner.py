from __future__ import annotations

from pathlib import Path

from wm.config import Settings
from wm.db.mysql_cli import MysqlCliClient
from wm.reactive.store import ReactiveQuestStore
from wm.sources.addon_log.models import AddonLogCursor
from wm.sources.addon_log.models import AddonLogScanResult
from wm.sources.addon_log.parser import AddonLogParser
from wm.sources.addon_log.resolver import AddonLogResolver
from wm.sources.addon_log.tailer import AddonLogTailer


class AddonLogScanner:
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
        self.parser = AddonLogParser()
        self.resolver = AddonLogResolver(client=client, settings=settings, reactive_store=reactive_store)

    def scan(
        self,
        *,
        player_guid: int,
        cursor_value: str | None,
        limit: int | None = None,
    ) -> AddonLogScanResult:
        path = Path(self.settings.addon_log_path)
        cursor = AddonLogCursor.from_cursor_value(cursor_value, default_path=str(path))
        tailer = AddonLogTailer(path=path)
        parsed_limit = max(1, int(limit or self.settings.addon_log_batch_size))
        raw_line_budget = max(parsed_limit * 200, parsed_limit)
        tail_result = tailer.read(
            cursor=cursor,
            max_lines=raw_line_budget,
        )
        result = AddonLogScanResult(
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
            signal, failure = self.resolver.resolve(
                record=record,
                player_guid=int(player_guid),
                log_path=tail_result.path,
                fingerprint=tail_result.cursor.fingerprint,
            )
            if signal is not None:
                result.signals.append(signal)
                if len(result.signals) >= parsed_limit:
                    break
            if failure is not None:
                result.failures.append(failure)
                if len(result.failures) >= parsed_limit and not result.signals:
                    break
        return result
