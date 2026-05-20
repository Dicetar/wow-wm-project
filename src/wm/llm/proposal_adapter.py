"""LLM proposal adapter — builds structured proposals from context + intent.

Modes:
  FIXTURE: returns the provided recorded proposal (used by tests + CI).
  LIVE:    calls LM Studio via wm.llm.lmstudio + parses via proposal_parser.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class AdapterMode(str, Enum):
    FIXTURE = "fixture"
    LIVE = "live"


class ProposalKind(str, Enum):
    QUEST = "quest"
    SCENE = "scene"
    ABILITY = "ability"


@dataclass(slots=True)
class ProposalRequest:
    kind: ProposalKind
    context: dict[str, Any]
    intent: str
    constraints: dict[str, Any]


@dataclass(slots=True)
class Proposal:
    kind: ProposalKind
    payload: dict[str, Any]
    character_guid: int
    narrative_summary: str = ""
    provenance: dict[str, Any] = field(default_factory=dict)
    is_blocked: bool = False
    block_reason: str = ""


_QUEST_REQUIRED_FIELDS = (
    "title", "objective", "description", "giver_creature_entry",
    "objective_kind", "rewards",
)


@dataclass(slots=True)
class ProposalAdapter:
    mode: AdapterMode = AdapterMode.FIXTURE
    fixture: dict[str, Any] | None = None

    def propose(self, req: ProposalRequest) -> Proposal:
        if self.mode is AdapterMode.FIXTURE:
            raw = self.fixture or {}
            prov = {"mode": "fixture"}
        else:
            raw = self._call_live(req)
            prov = {"mode": "live"}

        return self._validate(raw, req, prov)

    # --- internals -----------------------------------------------------

    def _call_live(self, req: ProposalRequest) -> dict[str, Any]:
        # imports are lazy so tests can run without the LM Studio dep
        from wm.llm import lmstudio, proposal_parser, prompts  # noqa: F401
        prompt = self._build_prompt(req)
        text = lmstudio.chat_completion(prompt=prompt)
        return proposal_parser.parse_structured(text)

    def _build_prompt(self, req: ProposalRequest) -> str:
        # Real prompt composition is delegated to wm.llm.prompts in follow-up
        # work; for the slice the live mode is opt-in and the prompt is a
        # straight JSON contract dump.
        import json
        return (
            "Return ONLY a JSON object matching the WM proposal schema for "
            f"kind={req.kind.value}. Intent: {req.intent}\n"
            f"Constraints: {json.dumps(req.constraints)}\n"
            f"Context: {json.dumps(req.context)}\n"
        )

    def _validate(self, raw: dict[str, Any], req: ProposalRequest, prov: dict[str, Any]) -> Proposal:
        cg = int(req.context.get("character", {}).get("guid", 0))
        if not raw or "kind" not in raw or "payload" not in raw:
            return Proposal(kind=req.kind, payload=raw or {}, character_guid=cg,
                            provenance=prov, is_blocked=True, block_reason="missing kind/payload")
        if raw["kind"] != req.kind.value:
            return Proposal(kind=req.kind, payload=raw["payload"], character_guid=cg,
                            provenance=prov, is_blocked=True,
                            block_reason=f"kind mismatch: expected {req.kind.value}, got {raw['kind']!r}")
        if req.kind is ProposalKind.QUEST:
            q = raw["payload"].get("quest_release")
            if not q:
                return Proposal(kind=req.kind, payload=raw["payload"], character_guid=cg,
                                provenance=prov, is_blocked=True, block_reason="missing quest_release")
            missing = [k for k in _QUEST_REQUIRED_FIELDS if k not in q]
            if missing:
                return Proposal(kind=req.kind, payload=raw["payload"], character_guid=cg,
                                provenance=prov, is_blocked=True,
                                block_reason=f"missing fields: {','.join(missing)}")
        return Proposal(kind=req.kind, payload=raw["payload"], character_guid=cg,
                        narrative_summary=str(raw.get("narrative_summary", "")), provenance=prov)
