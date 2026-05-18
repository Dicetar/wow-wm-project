"""Rumor propagation: decides whether to dispatch a rumor line and records it."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from wm.living.rumor import RumorTrigger, evaluate_rumor


_DEFAULT_COOLDOWN_SECONDS = 3600


@dataclass(slots=True)
class RumorRecord:
    player_guid: int
    subject_entry: int
    deed_count: int
    line: str
    dispatched_at: str


class RumorDispatcher:
    """Evaluate and dispatch rumor lines with a per-player+subject cooldown."""

    def __init__(self, db_client: Any = None,
                 cooldown_seconds: int = _DEFAULT_COOLDOWN_SECONDS):
        self._db = db_client
        self._cooldown = cooldown_seconds

    def _is_on_cooldown(self, player_guid: int, subject_entry: int) -> bool:
        if self._db is None:
            return False
        rows = self._db.query(
            "SELECT dispatched_at FROM wm_rumor_active "
            "WHERE player_guid = %s AND subject_entry = %s "
            "ORDER BY dispatched_at DESC LIMIT 1",
            (player_guid, subject_entry),
        )
        if not rows:
            return False
        raw = rows[0].get("dispatched_at")
        if raw is None:
            return False
        try:
            last = datetime.fromisoformat(str(raw))
            delta = (datetime.utcnow() - last).total_seconds()
            return delta < self._cooldown
        except Exception:
            return False

    def _record(self, player_guid: int, subject_entry: int,
                deed_count: int, line: str) -> None:
        if self._db is None:
            return
        self._db.execute(
            """
            INSERT INTO wm_rumor_active
                (player_guid, subject_entry, deed_count, line)
            VALUES (%s, %s, %s, %s)
            """,
            (player_guid, subject_entry, deed_count, line),
        )

    def maybe_dispatch_rumor(
        self,
        trigger: RumorTrigger,
        subject_entry: int = 0,
    ) -> RumorRecord | None:
        """Evaluate the trigger; return a RumorRecord if dispatched, else None."""
        if self._is_on_cooldown(trigger.player_guid, subject_entry):
            return None
        decision = evaluate_rumor(trigger)
        if not decision.eligible or decision.plan is None:
            return None
        line = decision.plan.line
        self._record(trigger.player_guid, subject_entry, trigger.deed_count, line)
        return RumorRecord(
            player_guid=trigger.player_guid,
            subject_entry=subject_entry,
            deed_count=trigger.deed_count,
            line=line,
            dispatched_at=datetime.utcnow().isoformat(),
        )
