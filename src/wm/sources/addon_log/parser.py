from __future__ import annotations

from wm.sources.addon_log.models import AddonLogRecord
from wm.sources.addon_log.models import payload_timestamp_to_iso


class AddonLogParser:
    marker = "WMB1|"

    def parse_line(self, *, raw_line: str, byte_offset: int) -> AddonLogRecord | None:
        marker_index = raw_line.find(self.marker)
        if marker_index < 0:
            return None
        raw_payload = raw_line[marker_index:].strip()
        if not raw_payload.startswith(self.marker):
            return None

        parts = raw_payload.split("|")
        if len(parts) < 2:
            return None

        payload_fields: dict[str, str] = {}
        for segment in parts[1:]:
            if "=" not in segment:
                continue
            key, value = segment.split("=", 1)
            key = str(key).strip().lower()
            if not key:
                continue
            payload_fields[key] = str(value).strip()

        event_type = str(payload_fields.get("type") or "").strip().upper()
        if event_type == "":
            return None

        return AddonLogRecord(
            occurred_at=payload_timestamp_to_iso(payload_fields.get("ts")),
            event_type=event_type,
            payload_fields=payload_fields,
            raw_payload=raw_payload,
            raw_line=raw_line.rstrip("\r\n"),
            byte_offset=int(byte_offset),
        )
