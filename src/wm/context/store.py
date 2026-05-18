from __future__ import annotations

import hashlib
import json
from typing import Any


def save_pack(db_client: Any, player_guid: int, pack_dict: dict,
              source_event_id: int | None = None) -> str:
    """Persist a context pack to wm_context_pack_log. Returns the 16-char hash."""
    pack_json = json.dumps(pack_dict, default=str)
    pack_hash = hashlib.sha256(pack_json.encode()).hexdigest()[:16]
    version = pack_dict.get("version", "wm.context_pack.v2")
    db_client.execute(
        """
        INSERT INTO wm_context_pack_log
            (player_guid, pack_hash, pack_json, pack_version, source_event_id)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (player_guid, pack_hash, pack_json, version, source_event_id),
    )
    return pack_hash


def load_latest_pack(db_client: Any, player_guid: int) -> dict | None:
    rows = db_client.query(
        "SELECT pack_json FROM wm_context_pack_log "
        "WHERE player_guid = %s ORDER BY generated_at DESC LIMIT 1",
        (player_guid,),
    )
    if not rows:
        return None
    return json.loads(rows[0]["pack_json"])
