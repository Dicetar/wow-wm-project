"""Zone ecology evaluator: tracks creature population pressure and proposes adjustments."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

EcologyActionKind = Literal[
    "spawn_reinforcements",
    "depopulate_zone",
    "shift_patrol_routes",
    "escalate_aggression",
    "none",
]


@dataclass(slots=True)
class EcologyAction:
    kind: EcologyActionKind
    zone_id: int
    subject_entry: int | None
    reason: str
    magnitude: int = 1  # 1-5 scale

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "zone_id": self.zone_id,
            "subject_entry": self.subject_entry,
            "reason": self.reason,
            "magnitude": self.magnitude,
        }


@dataclass(slots=True)
class EcologyReport:
    zone_id: int
    total_kills: int
    distinct_species: int
    pressure_level: int     # 0-5
    actions: list[EcologyAction] = field(default_factory=list)
    dry_run: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "total_kills": self.total_kills,
            "distinct_species": self.distinct_species,
            "pressure_level": self.pressure_level,
            "dry_run": self.dry_run,
            "actions": [a.to_dict() for a in self.actions],
        }


def _pressure_level(total_kills: int) -> int:
    if total_kills >= 100:
        return 5
    if total_kills >= 50:
        return 4
    if total_kills >= 20:
        return 3
    if total_kills >= 8:
        return 2
    if total_kills >= 2:
        return 1
    return 0


def _propose_actions(
    zone_id: int,
    pressure: int,
    kill_counts: dict[int, int],  # subject_entry -> kill_count
) -> list[EcologyAction]:
    actions: list[EcologyAction] = []
    if pressure == 0:
        return actions

    # Species under heaviest pressure get reinforcements
    if pressure >= 2:
        heaviest = max(kill_counts, key=kill_counts.__getitem__, default=None)
        if heaviest is not None:
            actions.append(EcologyAction(
                kind="spawn_reinforcements",
                zone_id=zone_id,
                subject_entry=heaviest,
                reason=f"{kill_counts[heaviest]} kills of entry {heaviest}",
                magnitude=min(pressure, 5),
            ))

    # High pressure escalates aggression zone-wide
    if pressure >= 4:
        actions.append(EcologyAction(
            kind="escalate_aggression",
            zone_id=zone_id,
            subject_entry=None,
            reason=f"pressure level {pressure} — zone-wide escalation",
            magnitude=pressure,
        ))

    return actions


class EcologyEvaluator:
    def __init__(self, db_client: Any = None, dry_run: bool = True):
        self._db = db_client
        self.dry_run = dry_run

    def evaluate_zone(self, zone_id: int, player_guid: int) -> EcologyReport:
        """Read kill counters for the player in zone and propose ecology actions."""
        kill_counts: dict[int, int] = {}

        if self._db is not None:
            rows = self._db.query(
                """
                SELECT jc.subject_entry, SUM(jc.count) AS total
                FROM wm_journal_counter jc
                WHERE jc.player_guid = %s AND jc.counter_key = 'kills'
                GROUP BY jc.subject_entry
                """,
                (player_guid,),
            )
            for r in rows:
                entry = int(r["subject_entry"])
                count = int(r.get("total") or 0)
                if count > 0:
                    kill_counts[entry] = count

        total_kills = sum(kill_counts.values())
        distinct = len(kill_counts)
        pressure = _pressure_level(total_kills)
        actions = _propose_actions(zone_id, pressure, kill_counts)

        return EcologyReport(
            zone_id=zone_id,
            total_kills=total_kills,
            distinct_species=distinct,
            pressure_level=pressure,
            actions=actions,
            dry_run=self.dry_run,
        )

    def apply_ecology_actions(self, report: EcologyReport, native_client: Any = None) -> int:
        """Submit non-dry-run ecology actions via native_client; returns count applied."""
        if self.dry_run or native_client is None:
            return 0
        applied = 0
        for action in report.actions:
            if action.kind == "none":
                continue
            try:
                native_client.send_action(
                    action_kind=action.kind,
                    payload={"zone_id": action.zone_id, "subject_entry": action.subject_entry,
                             "magnitude": action.magnitude},
                    player_guid=0,
                )
                applied += 1
            except Exception:
                pass
        return applied
