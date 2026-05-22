"""Wild Feature Catalog — the Living World layer as one first-class surface.

Per ADR-0005. Declarative registry over the already-tested evaluators so the
wild features are enumerable, collectively dry-run-provable, drift-proof
(live_ready computed from the real native registry), and CI-validated.
Single source of truth for the GUI/panel.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from wm.sources.native_bridge.action_kinds import NATIVE_ACTION_KIND_BY_ID
from wm.living import legend, nemesis, oath, patron, rumor


# Synthetic sample identity for the dry-run self-test only. NOT a real
# scoped player; the live catalog operates on whatever GUID the operator
# selects.
SAMPLE_PLAYER_GUID = 9_999_001
SAMPLE_PLAYER_NAME = "SampleHero"


@dataclass(slots=True)
class WildFeature:
    key: str
    archetype: str
    summary: str
    batch: str
    verbs: list[str]
    evaluate: Callable[[], Any]  # zero-arg: builds a representative decision
    test_ref: str
    extras: list[str] = field(default_factory=list)


def _nemesis_demo():
    return nemesis.evaluate_nemesis(
        nemesis.NemesisTrigger(player_guid=SAMPLE_PLAYER_GUID, subject_entry=46, subject_name="Murloc Forager", kill_count=12, player_name=SAMPLE_PLAYER_NAME)
    )


def _rumor_demo():
    return rumor.evaluate_rumor(
        rumor.RumorTrigger(player_guid=SAMPLE_PLAYER_GUID, player_name=SAMPLE_PLAYER_NAME, subject_name="Defias", deed_count=12, zone_name="Westfall")
    )


def _legend_demo():
    return legend.evaluate_legend(
        legend.LegendTrigger(player_guid=SAMPLE_PLAYER_GUID, player_name=SAMPLE_PLAYER_NAME, zone_name="Westfall", deed_count=80)
    )


def _patron_demo():
    return patron.evaluate_patron(patron.PatronTrigger(player_guid=SAMPLE_PLAYER_GUID, player_name=SAMPLE_PLAYER_NAME, completed_wm_count=10))


def _oath_demo():
    return oath.evaluate_oath(
        oath.OathTrigger(player_guid=SAMPLE_PLAYER_GUID, player_name=SAMPLE_PLAYER_NAME, oath_key="no_death", constraint_label="no deaths for 20 kills", target_count=20, current_count=20, phase="resolve")
    )


WILD_FEATURES: tuple[WildFeature, ...] = (
    WildFeature(
        key="living.nemesis",
        archetype="Bonebound Alpha (hostile owned actor)",
        summary="A subject the world remembers killing comes back named, hostile, and hunting the player.",
        batch="Batch 1 (creature_*)",
        verbs=["creature_spawn", "creature_set_name", "creature_set_faction", "creature_set_health_pct", "creature_yell", "creature_attack_player"],
        evaluate=_nemesis_demo,
        test_ref="tests/test_living_nemesis.py",
        extras=["revenge bounty (ReactiveQuestRule)", "reward arc ref"],
    ),
    WildFeature(
        key="living.rumor",
        archetype="Area-pressure scene (announcement)",
        summary="The world murmurs tiered rumor lines reflecting accumulated deeds.",
        batch="none (live-ready)",
        verbs=["world_announce_to_player"],
        evaluate=_rumor_demo,
        test_ref="tests/test_living_rumor.py",
    ),
    WildFeature(
        key="living.legend",
        archetype="Night Watcher's Lens (visible reward chain)",
        summary="A zone marks the player with a title + mailed rumor letter at deed tiers.",
        batch="Batch 2 (title/mail)",
        verbs=["world_announce_to_player", "player_add_title", "player_send_mail"],
        evaluate=_legend_demo,
        test_ref="tests/test_living_legend.py",
        extras=["journey reward_instance"],
    ),
    WildFeature(
        key="living.patron",
        archetype="Personal Journey Spine (favor progression)",
        summary="A WM patron's favor rises with completed WM work and unlocks tiered rewards.",
        batch="Batch 3 (wm_counter_*)",
        verbs=["wm_counter_set", "world_announce_to_player"],
        evaluate=_patron_demo,
        test_ref="tests/test_living_patron.py",
        extras=["tiered reward refs"],
    ),
    WildFeature(
        key="living.oath",
        archetype="Vellum/rune (bounded constraint + grant/revoke)",
        summary="The player swears a tracked constraint; keeping it grants, breaking it fails+revokes.",
        batch="Batch 3 (wm_counter_*/quest_fail)",
        verbs=["wm_counter_set", "wm_counter_clear", "quest_fail", "world_announce_to_player"],
        evaluate=_oath_demo,
        test_ref="tests/test_living_oath.py",
    ),
)


def build_wild_feature_catalog() -> dict[str, Any]:
    entries = []
    for f in WILD_FEATURES:
        pending = [v for v in f.verbs if not NATIVE_ACTION_KIND_BY_ID[v].implemented]
        entries.append(
            {
                "key": f.key,
                "archetype": f.archetype,
                "summary": f.summary,
                "batch": f.batch,
                "verbs": f.verbs,
                "not_implemented": pending,
                "live_ready": not pending,
                "extras": f.extras,
                "test_ref": f.test_ref,
            }
        )
    return {
        "schema_version": "wm.wild_feature_catalog.v1",
        "count": len(entries),
        "live_ready_count": sum(1 for e in entries if e["live_ready"]),
        "entries": entries,
    }


def validate_wild_catalog() -> list[str]:
    issues: list[str] = []
    for f in WILD_FEATURES:
        for v in f.verbs:
            if v not in NATIVE_ACTION_KIND_BY_ID:
                issues.append(f"{f.key}: unknown native verb {v!r}")
        if not callable(f.evaluate):
            issues.append(f"{f.key}: evaluate is not callable")
    keys = [f.key for f in WILD_FEATURES]
    if len(keys) != len(set(keys)):
        issues.append("duplicate wild feature keys")
    return issues


def dry_run_all() -> dict[str, Any]:
    """Run every wild evaluator once; assert each plan is contract-clean."""
    results = []
    ok = True
    for f in WILD_FEATURES:
        decision = f.evaluate()
        issues = list(getattr(decision, "contract_issues", []) or [])
        eligible = bool(getattr(decision, "eligible", False))
        if issues:
            ok = False
        results.append(
            {
                "key": f.key,
                "eligible": eligible,
                "contract_issues": issues,
            }
        )
    return {"ok": ok, "results": results}


def main(argv: list[str] | None = None) -> int:
    import argparse
    import json
    import sys

    p = argparse.ArgumentParser(prog="wm living.catalog", description="Wild Feature Catalog (read-only).")
    p.add_argument("--validate", action="store_true")
    p.add_argument("--dry-run-all", action="store_true")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    if args.validate:
        issues = validate_wild_catalog()
        if args.json:
            print(json.dumps({"ok": not issues, "issues": issues}, indent=2))
        else:
            print("OK" if not issues else "INVALID")
            for i in issues:
                print(f"  - {i}")
        return 0 if not issues else 1

    if args.dry_run_all:
        res = dry_run_all()
        print(json.dumps(res, indent=2) if args.json else
              f"dry_run_all ok={res['ok']} " + " ".join(f"{r['key']}:{'ok' if not r['contract_issues'] else 'BAD'}" for r in res["results"]))
        return 0 if res["ok"] else 1

    cat = build_wild_feature_catalog()
    if args.json:
        print(json.dumps(cat, indent=2))
        return 0
    print(f"Wild Feature Catalog ({cat['schema_version']})  {cat['live_ready_count']}/{cat['count']} live-ready\n")
    for e in cat["entries"]:
        flag = "LIVE" if e["live_ready"] else "GATED"
        print(f"  [{flag:<5}] {e['key']:<16} {e['batch']}")
        print(f"          {e['summary']}")
        print(f"          archetype: {e['archetype']}")
        if e["not_implemented"]:
            print(f"          pending C++: {', '.join(e['not_implemented'])}")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
