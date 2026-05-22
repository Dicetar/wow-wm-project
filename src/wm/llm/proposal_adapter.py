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


class ProposalGenerationError(Exception):
    """Raised when LIVE generation cannot produce a safe, valid draft."""


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
    llm_client: Any | None = None
    quest_schema: dict[str, Any] | None = None
    model_default: str = "qwen3-coder-30b-a3b-instruct"

    def propose(self, req: ProposalRequest) -> Proposal:
        if self.mode is AdapterMode.FIXTURE:
            return self._validate(self.fixture or {}, req, {"mode": "fixture"})
        prov = {"mode": "live"}
        try:
            raw = self._call_live(req)
        except ProposalGenerationError as exc:
            cg = int(req.context.get("character", {}).get("guid", 0))
            return Proposal(kind=req.kind, payload={}, character_guid=cg,
                            provenance=prov, is_blocked=True, block_reason=str(exc))
        return self._validate(raw, req, prov)

    # --- internals -----------------------------------------------------

    def _call_live(self, req: ProposalRequest) -> dict[str, Any]:
        from wm.llm.proposal_parser import ProposalParser
        from wm.quests.publish import bounty_draft_from_dict
        from wm.quests.validator import validate_bounty_quest_draft

        if self.llm_client is None or self.quest_schema is None:
            raise ProposalGenerationError("LIVE adapter missing llm_client/quest_schema")
        try:
            result = self.llm_client.generate_json(
                schema_version="wm.slice.bounty_draft.v1",
                schema=self.quest_schema,
                instruction=req.intent,
                context_pack=req.context,
                candidate_pack=req.constraints,
            )
        except Exception as exc:
            raise ProposalGenerationError(str(exc)) from exc

        screen = ProposalParser().parse(result.get("content") or "")
        if not screen.ok:
            raise ProposalGenerationError("; ".join(screen.issues) or "screen failed")

        authored = result.get("parsed") or {}
        merged = self._merge_fixed_facts(authored, req.constraints)
        try:
            draft = bounty_draft_from_dict(merged)
        except (KeyError, ValueError, TypeError) as exc:
            raise ProposalGenerationError(f"draft build failed: {exc}") from exc
        vr = validate_bounty_quest_draft(draft)
        if not vr.ok:
            raise ProposalGenerationError(
                "; ".join(f"{i.path}: {i.message}" for i in vr.errors))

        flat = draft.to_dict()
        return {
            "kind": "quest",
            "payload": {"quest_release": {
                "title": draft.title,
                "objective": draft.objective_text,
                "description": draft.quest_description,
                "giver_creature_entry": draft.questgiver_entry,
                "objective_kind": "kill",
                "rewards": {"xp_difficulty": draft.reward.reward_xp_difficulty,
                            "money_copper": draft.reward.money_copper},
                "draft": flat,
            }},
            "narrative_summary": authored.get("narrative_summary") or draft.offer_reward_text,
        }

    @staticmethod
    def _merge_fixed_facts(authored: dict[str, Any], constraints: dict[str, Any]) -> dict[str, Any]:
        c = constraints or {}
        cobj = c.get("objective", {})
        aobj = authored.get("objective", {})
        return {
            "quest_id": int(c.get("quest_id_placeholder", 999000)),
            "quest_level": int(c.get("quest_level", 1)),
            "min_level": int(c.get("min_level", 1)),
            "questgiver_entry": int(c["questgiver_entry"]),
            "questgiver_name": str(c.get("questgiver_name", "")),
            "title": str(authored.get("title", "")),
            "quest_description": str(authored.get("quest_description", "")),
            "objective_text": str(authored.get("objective_text", "")),
            "offer_reward_text": str(authored.get("offer_reward_text", "")),
            "request_items_text": str(authored.get("request_items_text", "")),
            "objective": {
                "target_entry": int(cobj["target_entry"]),
                "target_name": str(cobj["target_name"]),
                "kill_count": int(aobj.get("kill_count", 1)),
            },
            "reward": authored.get("reward", {}),
            "start_npc_entry": c.get("start_npc_entry"),
            "end_npc_entry": c.get("end_npc_entry"),
            "grant_mode": str(c.get("grant_mode", "direct_quest_add")),
            "tags": list(c.get("tags", ["wm-slice"])),
            "template_defaults": dict(c.get("template_defaults", {})),
        }

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
