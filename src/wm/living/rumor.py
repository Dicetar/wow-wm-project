"""Rumor Bulletin — the world murmurs about what the player has done.

Trigger: accumulated deeds against a subject/zone (journal-derived; passed in
for determinism). Decision: pick a heat tier and compose one player-scoped
announcement. Native: `world_announce_to_player` only — which is already
implemented, so this feature is `live_ready` today (no lab gate).

Dry-run scaffold: builds and contract-validates the plan; never submits.
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
class RumorConfig:
    min_deeds: int = 3
    tiers: tuple[tuple[int, str], ...] = (
        (3, "Whispers spread of {who} thinning {what}."),
        (10, "Folk speak openly: {who} has become the bane of {what}."),
        (25, "Songs already name {who} the scourge of {what}."),
    )


@dataclass(slots=True)
class RumorTrigger:
    player_guid: int
    player_name: str
    subject_name: str
    deed_count: int
    zone_name: str | None = None


@dataclass(slots=True)
class RumorPlan:
    line: str
    scene_steps: list[dict[str, Any]]
    native_readiness: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "line": self.line,
            "scene": {"schema_version": "control.scene.v1", "steps": self.scene_steps},
            "native_readiness": self.native_readiness,
        }


@dataclass(slots=True)
class RumorDecision:
    eligible: bool
    reason: str
    plan: RumorPlan | None = None
    contract_issues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "eligible": self.eligible,
            "reason": self.reason,
            "plan": self.plan.to_dict() if self.plan else None,
            "contract_issues": self.contract_issues,
        }


def _tier_line(trigger: RumorTrigger, config: RumorConfig) -> str:
    what = trigger.subject_name + (f" in {trigger.zone_name}" if trigger.zone_name else "")
    template = config.tiers[0][1]
    for threshold, tmpl in config.tiers:
        if trigger.deed_count >= threshold:
            template = tmpl
    return template.format(who=trigger.player_name, what=what)


def build_rumor_plan(trigger: RumorTrigger, config: RumorConfig | None = None) -> tuple[RumorPlan, list[str]]:
    config = config or RumorConfig()
    line = _tier_line(trigger, config)
    steps = [
        {
            "native_action_kind": "world_announce_to_player",
            "payload": {"message": line},
            "expected_effect": "player-perceivable rumor line reflecting their deeds",
        }
    ]
    issues: list[str] = []
    for step in steps:
        issues.extend(
            validate_native_action_payload(action_kind=step["native_action_kind"], payload=step["payload"])
        )
    kinds = [s["native_action_kind"] for s in steps]
    impl = [k for k in kinds if NATIVE_ACTION_KIND_BY_ID[k].implemented]
    pending = [k for k in kinds if not NATIVE_ACTION_KIND_BY_ID[k].implemented]
    plan = RumorPlan(
        line=line,
        scene_steps=steps,
        native_readiness={
            "implemented": impl,
            "not_implemented": pending,
            "live_ready": not pending,
            "note": "world_announce_to_player is implemented; this feature is live-ready.",
        },
    )
    return plan, issues


def evaluate_rumor(trigger: RumorTrigger, config: RumorConfig | None = None) -> RumorDecision:
    config = config or RumorConfig()
    if trigger.deed_count < config.min_deeds:
        return RumorDecision(
            eligible=False,
            reason=f"{trigger.deed_count}/{config.min_deeds} deeds; no rumor yet",
        )
    plan, issues = build_rumor_plan(trigger, config)
    if issues:
        return RumorDecision(eligible=False, reason="rumor plan failed contract validation", plan=plan, contract_issues=issues)
    return RumorDecision(eligible=True, reason=f"{trigger.deed_count} deeds; rumor spreads", plan=plan)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="wm living.rumor", description="Rumor Bulletin scaffold (dry-run only).")
    p.add_argument("--player-guid", type=int, required=True)
    p.add_argument("--player-name", required=True)
    p.add_argument("--subject-name", default=None)
    p.add_argument("--subject-entry", type=int, default=None)
    p.add_argument("--deed-count", type=int, default=None)
    p.add_argument("--zone-name", default=None)
    p.add_argument("--from-journal", action="store_true", help="read deed_count/subject from the live journal")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    if args.from_journal:
        if args.subject_entry is None:
            p.error("--subject-entry is required with --from-journal")
        from wm.living.journal_trigger import build_journal_reader, build_rumor_trigger_from_journal

        trigger = build_rumor_trigger_from_journal(
            reader=build_journal_reader(),
            player_guid=args.player_guid,
            player_name=args.player_name,
            subject_entry=args.subject_entry,
            subject_name=args.subject_name,
            zone_name=args.zone_name,
        )
    else:
        if args.deed_count is None or args.subject_name is None:
            p.error("--deed-count and --subject-name are required unless --from-journal is set")
        trigger = RumorTrigger(
            player_guid=args.player_guid,
            player_name=args.player_name,
            subject_name=args.subject_name,
            deed_count=args.deed_count,
            zone_name=args.zone_name,
        )
    decision = evaluate_rumor(trigger)
    if args.json:
        print(json.dumps(decision.to_dict(), indent=2))
        return 0 if decision.eligible else 1
    print(f"eligible : {decision.eligible}")
    print(f"reason   : {decision.reason}")
    if decision.plan:
        print(f"line     : {decision.plan.line}")
        print(f"native   : live_ready={decision.plan.native_readiness['live_ready']}")
    print("\nDRY-RUN ONLY: nothing was submitted.")
    return 0 if decision.eligible else 1


if __name__ == "__main__":
    sys.exit(main())
