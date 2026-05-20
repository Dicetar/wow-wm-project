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
                  fixture_path: str = DEFAULT_FIXTURE) -> "SliceRuntime":
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
        adapter = ProposalAdapter(mode=adapter_mode, fixture=_load(fixture_path))
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
