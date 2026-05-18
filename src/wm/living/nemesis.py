"""Nemesis — a subject the world remembers killing, that comes back for the player.

Trigger: cumulative kills of one subject cross a threshold (from the journal
counter; passed in here so the scaffold stays deterministic and DB-free).
Decision/state: Python picks the nemesis identity and composes the encounter.
Native: a scoped scene of typed `creature_*` actions (Batch 1 contracts).
Reward: a one-target revenge bounty whose completion feeds an arc reward.

This module is a scaffold: it produces a *validated plan* and never mutates.
Every native step is checked against the enforced payload contracts, so the
plan is provably well-formed even though several Batch-1 C++ bodies are still
`not_implemented` (lab-gated, per docs/NATIVE_CAPABILITY_EXPANSION_V1.md).
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import json
import sys
from typing import Any

from wm.sources.native_bridge.action_kinds import NATIVE_ACTION_KIND_BY_ID
from wm.sources.native_bridge.payload_contract import validate_native_action_payload


@dataclass(slots=True)
class NemesisConfig:
    kill_threshold: int = 10
    hostile_faction_id: int = 14  # AzerothCore "Monster" hostile-to-all template
    elite_health_percent: int = 100
    revenge_post_reward_cooldown_seconds: int = 86400
    name_template: str = "{subject} the Unforgotten"
    taunt_template: str = "You thinned my kin, {player}. Now you answer for it."
    reward_arc_prefix: str = "nemesis"


@dataclass(slots=True)
class NemesisTrigger:
    player_guid: int
    subject_entry: int
    subject_name: str
    kill_count: int
    zone_id: int | None = None
    player_name: str | None = None
    turn_in_npc_entry: int | None = None


@dataclass(slots=True)
class NemesisPlan:
    arc_key: str
    nemesis_name: str
    scene_steps: list[dict[str, Any]]
    revenge_bounty: dict[str, Any]
    reward_arc_ref: str
    native_readiness: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "arc_key": self.arc_key,
            "nemesis_name": self.nemesis_name,
            "scene": {"schema_version": "control.scene.v1", "steps": self.scene_steps},
            "revenge_bounty": self.revenge_bounty,
            "reward_arc_ref": self.reward_arc_ref,
            "native_readiness": self.native_readiness,
        }


@dataclass(slots=True)
class NemesisDecision:
    eligible: bool
    reason: str
    plan: NemesisPlan | None = None
    contract_issues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "eligible": self.eligible,
            "reason": self.reason,
            "plan": self.plan.to_dict() if self.plan else None,
            "contract_issues": self.contract_issues,
        }


def _arc_key(prefix: str, player_guid: int, subject_entry: int) -> str:
    return f"{prefix}:{player_guid}:{subject_entry}"


def _native_readiness(step_kinds: list[str]) -> dict[str, Any]:
    impl = [k for k in step_kinds if NATIVE_ACTION_KIND_BY_ID[k].implemented]
    pending = [k for k in step_kinds if not NATIVE_ACTION_KIND_BY_ID[k].implemented]
    return {
        "implemented": impl,
        "not_implemented": pending,
        "live_ready": not pending,
        "note": "Scene is contract-valid; not_implemented verbs are lab-gated C++ work.",
    }


def build_nemesis_plan(trigger: NemesisTrigger, config: NemesisConfig | None = None) -> tuple[NemesisPlan, list[str]]:
    config = config or NemesisConfig()
    arc_key = _arc_key(config.reward_arc_prefix, trigger.player_guid, trigger.subject_entry)
    nemesis_name = config.name_template.format(subject=trigger.subject_name)
    taunt = config.taunt_template.format(player=trigger.player_name or "mortal")

    # Every follow-up step targets the spawned creature by the shared arc_key,
    # which satisfies each contract's required_any selector.
    steps: list[dict[str, Any]] = [
        {
            "native_action_kind": "creature_spawn",
            "payload": {"creature_entry": trigger.subject_entry, "arc_key": arc_key, "follow_player": False},
            "expected_effect": "WM-owned nemesis base creature spawned near the player",
        },
        {
            "native_action_kind": "creature_set_name",
            "payload": {"name": nemesis_name, "arc_key": arc_key},
            "expected_effect": "creature renamed to the remembered nemesis identity",
        },
        {
            "native_action_kind": "creature_set_faction",
            "payload": {"faction_id": config.hostile_faction_id, "arc_key": arc_key},
            "expected_effect": "creature becomes hostile to the player",
        },
        {
            "native_action_kind": "creature_set_health_pct",
            "payload": {"health_percent": config.elite_health_percent, "arc_key": arc_key},
            "expected_effect": "elite health marker (real scaling is native C++)",
        },
        {
            "native_action_kind": "creature_yell",
            "payload": {"text": taunt, "arc_key": arc_key},
            "expected_effect": "player-perceivable announcement of the nemesis return",
        },
        {
            "native_action_kind": "creature_attack_player",
            "payload": {"arc_key": arc_key},
            "expected_effect": "nemesis engages the scoped player",
        },
    ]

    issues: list[str] = []
    for step in steps:
        issues.extend(
            validate_native_action_payload(action_kind=step["native_action_kind"], payload=step["payload"])
        )

    revenge_bounty = {
        "rule_key": f"nemesis_revenge:{trigger.player_guid}:{trigger.subject_entry}",
        "is_active": True,
        "player_guid_scope": trigger.player_guid,
        "subject_type": "creature",
        "subject_entry": trigger.subject_entry,
        "trigger_event_type": "kill",
        "kill_threshold": 1,
        "window_seconds": 86400,
        "quest_id": None,  # allocated from a fresh reserved slot at install time
        "requires_slot_allocation": True,
        "turn_in_npc_entry": trigger.turn_in_npc_entry,
        "grant_mode": "direct_quest_add",
        "post_reward_cooldown_seconds": config.revenge_post_reward_cooldown_seconds,
        "metadata": {
            "nemesis": True,
            "nemesis_name": nemesis_name,
            "source_kill_count": trigger.kill_count,
            "arc_key": arc_key,
        },
    }

    plan = NemesisPlan(
        arc_key=arc_key,
        nemesis_name=nemesis_name,
        scene_steps=steps,
        revenge_bounty=revenge_bounty,
        reward_arc_ref=arc_key,
        native_readiness=_native_readiness([s["native_action_kind"] for s in steps]),
    )
    return plan, issues


def evaluate_nemesis(trigger: NemesisTrigger, config: NemesisConfig | None = None) -> NemesisDecision:
    config = config or NemesisConfig()
    if trigger.kill_count < config.kill_threshold:
        return NemesisDecision(
            eligible=False,
            reason=(
                f"{trigger.kill_count}/{config.kill_threshold} kills of "
                f"{trigger.subject_name!r}; nemesis not yet awakened"
            ),
        )
    plan, issues = build_nemesis_plan(trigger, config)
    if issues:
        return NemesisDecision(
            eligible=False,
            reason="nemesis plan failed native payload-contract validation",
            plan=plan,
            contract_issues=issues,
        )
    return NemesisDecision(
        eligible=True,
        reason=(
            f"{trigger.kill_count} kills of {trigger.subject_name!r} crossed "
            f"threshold {config.kill_threshold}; nemesis awakened"
        ),
        plan=plan,
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="wm living.nemesis", description="Nemesis decision/plan scaffold (dry-run only).")
    p.add_argument("--player-guid", type=int, required=True)
    p.add_argument("--subject-entry", type=int, required=True)
    p.add_argument("--subject-name", default=None)
    p.add_argument("--kill-count", type=int, default=None)
    p.add_argument("--zone-id", type=int, default=None)
    p.add_argument("--player-name", default=None)
    p.add_argument("--turn-in-npc-entry", type=int, default=None)
    p.add_argument("--kill-threshold", type=int, default=None)
    p.add_argument("--from-journal", action="store_true", help="read kill_count/subject from the live journal")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    config = NemesisConfig()
    if args.kill_threshold is not None:
        config.kill_threshold = args.kill_threshold
    if args.from_journal:
        from wm.living.journal_trigger import build_journal_reader, build_nemesis_trigger_from_journal

        trigger = build_nemesis_trigger_from_journal(
            reader=build_journal_reader(),
            player_guid=args.player_guid,
            subject_entry=args.subject_entry,
            player_name=args.player_name,
            subject_name=args.subject_name,
            turn_in_npc_entry=args.turn_in_npc_entry,
        )
    else:
        if args.kill_count is None or args.subject_name is None:
            p.error("--kill-count and --subject-name are required unless --from-journal is set")
        trigger = NemesisTrigger(
            player_guid=args.player_guid,
            subject_entry=args.subject_entry,
            subject_name=args.subject_name,
            kill_count=args.kill_count,
            zone_id=args.zone_id,
            player_name=args.player_name,
            turn_in_npc_entry=args.turn_in_npc_entry,
        )
    decision = evaluate_nemesis(trigger, config)

    if args.json:
        print(json.dumps(decision.to_dict(), indent=2))
        return 0 if decision.eligible else 1

    print(f"eligible : {decision.eligible}")
    print(f"reason   : {decision.reason}")
    if decision.contract_issues:
        for issue in decision.contract_issues:
            print(f"  CONTRACT {issue}")
    if decision.plan:
        pl = decision.plan
        print(f"arc_key  : {pl.arc_key}")
        print(f"nemesis  : {pl.nemesis_name}")
        print(f"scene    : {len(pl.scene_steps)} steps")
        for s in pl.scene_steps:
            print(f"  - {s['native_action_kind']}: {s['expected_effect']}")
        nr = pl.native_readiness
        print(f"native   : live_ready={nr['live_ready']} implemented={nr['implemented']}")
        print(f"           not_implemented={nr['not_implemented']}")
        print(f"revenge  : bounty rule {pl.revenge_bounty['rule_key']} (quest slot allocated at install)")
        print(f"reward   : arc ref {pl.reward_arc_ref} (ArcRewardFactory on revenge completion)")
    print("\nDRY-RUN ONLY: nothing was submitted; native verbs above gate live execution.")
    return 0 if decision.eligible else 1


class NemesisManager:
    """Reads/writes nemesis state from wm_nemesis table."""

    def __init__(self, db_client: Any = None):
        self._db = db_client

    def is_awakened(self, player_guid: int, subject_entry: int) -> bool:
        if self._db is None:
            return False
        rows = self._db.query(
            "SELECT status FROM wm_nemesis "
            "WHERE player_guid = %s AND subject_entry = %s AND status = 'awakened'",
            (player_guid, subject_entry),
        )
        return bool(rows)

    def record_awakening(self, player_guid: int, subject_entry: int,
                         nemesis_name: str, arc_key: str) -> None:
        if self._db is None:
            return
        self._db.execute(
            """
            INSERT INTO wm_nemesis (player_guid, subject_entry, nemesis_name, arc_key, status)
            VALUES (%s, %s, %s, %s, 'awakened')
            ON DUPLICATE KEY UPDATE nemesis_name = VALUES(nemesis_name),
                arc_key = VALUES(arc_key), status = 'awakened', resolved_at = NULL
            """,
            (player_guid, subject_entry, nemesis_name, arc_key),
        )

    def record_slain(self, player_guid: int, subject_entry: int) -> None:
        if self._db is None:
            return
        self._db.execute(
            "UPDATE wm_nemesis SET status = 'slain', resolved_at = NOW() "
            "WHERE player_guid = %s AND subject_entry = %s",
            (player_guid, subject_entry),
        )

    def evaluate_and_record(
        self,
        trigger: NemesisTrigger,
        config: NemesisConfig | None = None,
    ) -> NemesisDecision:
        decision = evaluate_nemesis(trigger, config)
        if decision.eligible and decision.plan:
            self.record_awakening(
                trigger.player_guid, trigger.subject_entry,
                decision.plan.nemesis_name, decision.plan.arc_key,
            )
        return decision


if __name__ == "__main__":
    sys.exit(main())
