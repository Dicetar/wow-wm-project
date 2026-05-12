from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from typing import Any

from wm.spells.broug_empty_court import BROUG_EMPTY_COURT_ARC_KEY
from wm.spells.broug_lightness import BROUG_LIGHTNESS_ARC_KEY


@dataclass(slots=True)
class ProofStep:
    key: str
    instruction: str
    expected: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ProofPacket:
    arc_key: str
    player_guid: int
    status: str
    steps: list[ProofStep]
    counters: list[str]
    operator_checks: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "arc_key": self.arc_key,
            "player_guid": self.player_guid,
            "status": self.status,
            "steps": [step.to_dict() for step in self.steps],
            "counters": self.counters,
            "operator_checks": self.operator_checks,
        }


def build_proof_packet(*, arc_key: str, player_guid: int = 5405) -> ProofPacket:
    if arc_key == BROUG_LIGHTNESS_ARC_KEY:
        return ProofPacket(
            arc_key=arc_key,
            player_guid=player_guid,
            status="WORKING",
            steps=[
                ProofStep("quest_910182", "From Master Mathias Shaw, complete `Broug: Steps Without Dust` by killing 8 Syndicate Watchmen.", "Cloud Step `946202` is learned and visible in the spellbook."),
                ProofStep("cloud_step", "Cast Cloud Step on a hostile target from 0-25 yd.", "Broug moves behind/near the target, smoke appears at departure and arrival, Killing Intent appears for 10 sec, and Marked Meridian appears for 12 sec."),
                ProofStep("marked_hit", "Hit that marked target with direct melee or Skirmisher's Mark.", "Marked Meridian is consumed, damage is increased, and `cloud_step_strike` increments."),
                ProofStep("silent_manual", "After learning Silent Meridian Manual, Cloud Step a target and kill it within 10 sec.", "Broug gains 10 energy and Cloud Step's visible cooldown is reduced by 6 sec."),
            ],
            counters=["wm_broug_lightness_counter:cloud_step_strike", "wm_broug_lightness_counter:silent_meridian_kill"],
            operator_checks=[
                "Verify `character_spell` contains 946202 and 946803 for player 5405.",
                "Verify `wm_spell_grant` has active rows for quests 910182 and 910183.",
                "Verify Vulnerable stacks are not consumed or modified by Cloud Step.",
            ],
        )
    if arc_key == BROUG_EMPTY_COURT_ARC_KEY:
        return ProofPacket(
            arc_key=arc_key,
            player_guid=player_guid,
            status="WORKING",
            steps=[
                ProofStep("quest_910184", "At Sentinel Hill, accept `Broug: The Weight Before the Blade`, inspect Ash-Worn Track Circle near coords -10752, 990, then speak to Wei Jin.", "Quest completes without GM spawning; Wei Jin is visible and interactable."),
                ProofStep("qi_reversal", "Complete `Broug: Stilling the Water` and use Qi Reversal while Broug has Magic, Poison, or Disease effects.", "Qi Reversal uses the Cloak-style icon, self-casts with no target range, cleanses allowed types, and applies Purged State for 30 sec with 2 charges."),
                ProofStep("predator", "Complete `Broug: Ninety-Eight`, then consume Marked Meridian with an eligible hit.", "Predator's Strike heals Broug from actual damage dealt and `predator_heal` increments."),
                ProofStep("domain", "Complete `Broug: The Room That Silenced`, activate Cloud Step/Killing Intent near hostile enemies.", "Domain pulses Suppressed every 2 sec in 8 yd; Suppressed lasts 12 sec."),
                ProofStep("vitality", "Complete `Broug: Domain Unsealed`, then land killing blows, including one inside the Silent Meridian window.", "Vitality Drain heals on kills; Silent-window kills heal more and add energy."),
            ],
            counters=[
                "wm_broug_empty_court_counter:domain_pulse",
                "wm_broug_empty_court_counter:suppressed_death_extend",
                "wm_broug_empty_court_counter:qi_reversal_cleanse",
                "wm_broug_empty_court_counter:predator_heal",
                "wm_broug_empty_court_counter:vitality_kill",
            ],
            operator_checks=[
                "Verify custom gameobjects 195500 and 195501 are visible and clickable.",
                "Verify custom creatures 915500, 915510-915512, 915520, 915530-915539, and 915540 have model rows and spawn.",
                "Verify Energy Surge `946606` remains active through Cloud Step/Killing Intent changes.",
                "Verify no guard/parry or Vulnerable stack regression.",
            ],
        )
    return ProofPacket(arc_key=arc_key, player_guid=player_guid, status="UNKNOWN", steps=[], counters=[], operator_checks=[])


def render_summary(packet: ProofPacket) -> str:
    lines = [f"arc={packet.arc_key}", f"player_guid={packet.player_guid}", f"status={packet.status}"]
    for step in packet.steps:
        lines.append(f"{step.key}: {step.instruction} Expected: {step.expected}")
    if packet.counters:
        lines.append("counters=" + ",".join(packet.counters))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a concrete live proof packet for a WM arc.")
    parser.add_argument("--arc", required=True)
    parser.add_argument("--player-guid", type=int, default=5405)
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args(argv)

    packet = build_proof_packet(arc_key=args.arc, player_guid=args.player_guid)
    if args.summary:
        print(render_summary(packet))
    else:
        print(json.dumps(packet.to_dict(), indent=2, sort_keys=True))
    return 0 if packet.status != "UNKNOWN" else 1


if __name__ == "__main__":
    raise SystemExit(main())
