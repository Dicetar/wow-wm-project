from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from wm.events.normalize import normalize_native_bridge_event


@dataclass
class ReplayResult:
    from_event_id: int
    to_event_id: int
    events_processed: int
    would_trigger: list[str] = field(default_factory=list)
    dry_run: bool = True
    errors: list[str] = field(default_factory=list)


def replay_event_range(
    from_event_id: int,
    to_event_id: int,
    db_client: Any,
    *,
    player_guid: int | None = None,
    dry_run: bool = True,
) -> ReplayResult:
    """
    Replay wm_event_log rows through the normalizer.
    In dry_run mode: never writes to DB, returns what would have been triggered.
    """
    query = (
        "SELECT event_id, event_type, player_guid, target_entry, target_guid, "
        "zone_id, area_id FROM wm_event_log "
        "WHERE event_id BETWEEN %s AND %s"
    )
    params: tuple = (from_event_id, to_event_id)
    if player_guid is not None:
        query += " AND player_guid = %s"
        params = (from_event_id, to_event_id, player_guid)
    query += " ORDER BY event_id"

    rows = db_client.query(query, params)
    events_processed = 0
    would_trigger: list[str] = []
    errors: list[str] = []

    for raw in rows:
        try:
            event = normalize_native_bridge_event(raw)
            events_processed += 1
            would_trigger.append(f"{event.event_type}:entry_{event.target_entry}")
        except Exception as exc:
            errors.append(f"event_id={raw.get('event_id')}: {exc}")

    return ReplayResult(
        from_event_id=from_event_id,
        to_event_id=to_event_id,
        events_processed=events_processed,
        would_trigger=would_trigger,
        dry_run=dry_run,
        errors=errors,
    )
