"""Slice demo runtime — wires onboarding + Arc Runner + Watcher + gate.

Exposes a Python API used by tests + a minimal CLI for the BridgeLab run.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
from typing import Any
from wm.abilities.grant_compiler import compile_grant_plan
from wm.abilities.schema import parse_ability
from wm.arcs.runner import ArcRunner, RunnerEvent
from wm.arcs.story_module import parse_story_module
from wm.llm.proposal_adapter import (
    ProposalAdapter, AdapterMode, Proposal, ProposalKind,
)
from wm.onboarding.starter_item import OnboardingHandler, OnboardingEvent
from wm.panel.approval_gate import ApprovalGate
from wm.panel.issues_queue import IssuesQueue
from wm.reactive.reactive_template import parse_reactive_template
from wm.reactive.watcher import Watcher, WatcherEvent

DEMO_MODULE_PATH = "control/examples/story_modules/demo_one.story_module.json"
TEMPLATE_DIR     = "control/examples/reactive_templates"
ABILITY_DIR      = "control/examples/abilities"
DEFAULT_FIXTURE  = "tests/fixtures/llm/quest_proposal_basic.json"


def _load(p: str | Path) -> dict: return json.loads(Path(p).read_text(encoding="utf-8"))


@dataclass(slots=True)
class SliceRuntime:
    gate: ApprovalGate
    issues: IssuesQueue
    runner: ArcRunner
    watcher: Watcher
    onboarding: OnboardingHandler
    applied_log: list[dict] = field(default_factory=list)
    abilities_by_id: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def bootstrap(cls, *, character_guid: int, starter_item_entry: int,
                  adapter_mode: AdapterMode = AdapterMode.FIXTURE,
                  fixture_path: str = DEFAULT_FIXTURE,
                  llm_client: Any | None = None,
                  quest_schema: dict | None = None) -> "SliceRuntime":
        issues = IssuesQueue()
        applied_log: list[dict] = []

        # ability catalog
        abilities = {
            (a := parse_ability(_load(p))).id: a
            for p in Path(ABILITY_DIR).iterdir() if p.suffix == ".json"
        }

        def quest_compiler(p: Proposal) -> dict:
            applied_log.append({"kind": "quest", "payload": p.payload,
                                "narrative": p.narrative_summary,
                                "provenance": p.provenance})
            return {"ok": True}

        def ability_compiler(p: Proposal) -> dict:
            ability_id = p.payload.get("ability_id")
            spec = abilities.get(ability_id)
            if spec is None:
                raise ValueError(f"unknown ability_id={ability_id}")
            plan = compile_grant_plan(spec, character_guid=p.character_guid)
            applied_log.append({"kind": "ability", "ability_id": ability_id,
                                "steps": [asdict(s) for s in plan.steps]})
            return {"ok": True, "plan": plan}

        def scene_compiler(p: Proposal) -> dict:
            applied_log.append({"kind": "scene", "payload": p.payload})
            return {"ok": True}

        gate = ApprovalGate(issues=issues,
                            quest_compiler=quest_compiler,
                            ability_compiler=ability_compiler,
                            scene_compiler=scene_compiler)

        # Arc Runner
        module = parse_story_module(_load(DEMO_MODULE_PATH))
        if module.character_guid != character_guid:
            module.character_guid = character_guid  # the demo lets you target any char
        adapter = ProposalAdapter(mode=adapter_mode, fixture=_load(fixture_path),
                                  llm_client=llm_client, quest_schema=quest_schema)
        runner = ArcRunner(module=module, adapter=adapter, gate=gate)

        # Watcher
        templates = [parse_reactive_template(_load(p))
                     for p in sorted(Path(TEMPLATE_DIR).iterdir())
                     if p.suffix == ".json"]
        watcher = Watcher(templates=templates, adapter=adapter, gate=gate,
                          active_character_guid=character_guid)

        # Onboarding
        def _on_attention(evt: OnboardingEvent) -> None:
            runner.on_event(RunnerEvent(kind=evt.kind, character_guid=evt.character_guid, params={}))
        onboarding = OnboardingHandler(starter_item_entry=starter_item_entry,
                                       active_character_guid=character_guid,
                                       emit=_on_attention)

        return cls(gate=gate, issues=issues, runner=runner, watcher=watcher,
                   onboarding=onboarding, applied_log=applied_log,
                   abilities_by_id=abilities)

    # --- event feeders (test API + bridge bridge for the runbook) -------

    def feed_attention(self, *, character_guid: int | None = None) -> None:
        """Activate the character for the WM — the aura sentinel's entry point.

        Mirrors what the (now obsolete) starter-item onboarding path did, but
        is driven by the marker-aura `applied` event observed on the spine.
        """
        guid = character_guid if character_guid is not None else self.runner.module.character_guid
        self.runner.on_event(RunnerEvent(
            kind="wm.attention.granted", character_guid=guid, params={}))

    def feed_use_item(self, *, item_entry: int) -> None:
        self.onboarding.on_event(OnboardingEvent(
            kind="use_item", character_guid=self.runner.module.character_guid,
            params={"item_entry": item_entry}))

    def feed_quest_completed(self, *, beat_ref: str, character_level: int = 1) -> None:
        self.runner.on_event(RunnerEvent(
            kind="quest.completed", character_guid=self.runner.module.character_guid,
            params={"beat_ref": beat_ref, "character_level": character_level}))

    def feed_kill(self, *, creature_family: str, zone: str, ts: int) -> None:
        self.watcher.on_event(WatcherEvent(
            kind="kill", character_guid=self.runner.module.character_guid,
            params={"creature_family": creature_family, "zone": zone}, ts=ts))


@dataclass(slots=True)
class ScriptedOperator:
    gate: ApprovalGate

    def approve_next(self) -> None:
        pending = self.gate.pending()
        if not pending: return
        self.gate.approve(pending[0].id)


# ---------------------------------------------------------------------
# `python -m wm.cli.slice_demo` entrypoint — live BridgeLab loop + REPL.
# ---------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(prog="wm.cli.slice_demo",
                                     description="WM vertical slice runtime (live BridgeLab loop).")
    parser.add_argument("--character", type=int, required=True, help="Active character GUID.")
    parser.add_argument("--starter-item", type=int, required=True, help="Onboarding starter-item entry.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=33307)
    parser.add_argument("--user", default="acore")
    parser.add_argument("--password", default="acore")
    parser.add_argument("--database", default="acore_world")
    parser.add_argument("--in-process", action="store_true",
                        help="Skip live DB wiring; run the in-process demo only (smoke test).")
    args = parser.parse_args(argv)

    rt = SliceRuntime.bootstrap(character_guid=args.character,
                                 starter_item_entry=args.starter_item)

    if not args.in_process:
        from wm.cli.slice_demo_live import wrap_with_live_compilers
        from wm.cli.native_applier import NativeApplier
        from wm.cli.bridge_event_pump import BridgeEventPump, make_mysql_fetch
        from wm.db.mysql_cli import MysqlCliClient

        client = MysqlCliClient()
        applier = NativeApplier(client=client, host=args.host, port=args.port,
                                user=args.user, password=args.password, database=args.database)
        wrap_with_live_compilers(rt, applier=applier)
        fetch = make_mysql_fetch(client=client, host=args.host, port=args.port,
                                  user=args.user, password=args.password,
                                  database=args.database, character_guid=args.character)
        pump = BridgeEventPump(runtime=rt, fetch=fetch)
        print(f"[wm] live mode: char={args.character} starter_item={args.starter_item}; "
              "poll wm_bridge_event each Enter.")
    else:
        pump = None
        print(f"[wm] in-process smoke mode: char={args.character} starter_item={args.starter_item}; "
              "use 'use <id>' / 'qc <beat>' / 'kill <family> <zone>' to feed synthetic events.")

    print("commands: <Enter> poll · a <id> approve · r <id> [reason] reject · "
          "i issues · p pending · l log · q quit")

    while True:
        # show state
        pend = rt.gate.pending()
        if pend:
            print("\n--- pending ---")
            for pp in pend:
                p = pp.proposal
                summary = (p.narrative_summary[:80] + "…") if len(p.narrative_summary) > 80 else p.narrative_summary
                print(f"  #{pp.id} {p.kind.value:7s} char={p.character_guid} {summary or '(no summary)'}")
        try:
            cmd = input("[wm]> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nbye.")
            return 0

        if not cmd:
            if pump is not None:
                n = pump.poll_once()
                if n: print(f"[wm] polled {n} event(s); watermark={pump.last_seen_event_id}")
            continue
        parts = cmd.split(maxsplit=2)
        verb = parts[0]
        if verb == "q":
            return 0
        if verb == "a" and len(parts) >= 2:
            res = rt.gate.approve(int(parts[1]))
            print(f"  approve → ok={res.ok} {res.error or ''}")
            continue
        if verb == "r" and len(parts) >= 2:
            reason = parts[2] if len(parts) > 2 else "operator-rejected"
            rt.gate.reject(int(parts[1]), reason=reason)
            print(f"  reject  → {reason}")
            continue
        if verb == "i":
            issues = rt.issues.list_open()
            print(f"  issues: {len(issues)}")
            for it in issues:
                print(f"    #{it.id} {it.kind} {it.reason}")
            continue
        if verb == "p":
            print(f"  pending: {len(pend)}")
            continue
        if verb == "l":
            print(f"  applied_log: {len(rt.applied_log)}")
            for entry in rt.applied_log[-10:]:
                print(f"    {entry.get('kind')} {entry.get('applier') or entry.get('steps') or entry.get('narrative','')[:60]}")
            continue
        # in-process synthetic feeders (smoke mode aids)
        if verb == "use" and len(parts) >= 2:
            rt.feed_use_item(item_entry=int(parts[1])); continue
        if verb == "qc" and len(parts) >= 2:
            rt.feed_quest_completed(beat_ref=parts[1], character_level=int(parts[2]) if len(parts) > 2 else 1); continue
        if verb == "kill" and len(parts) >= 3:
            fam, zone = parts[1], parts[2]
            import time
            rt.feed_kill(creature_family=fam, zone=zone, ts=int(time.time())); continue
        print(f"  unknown command: {cmd!r}")
