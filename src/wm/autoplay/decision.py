"""Typed model decision for the scoped director pilot."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


Outcome = Literal["propose_content", "propose_action", "ask_clarification", "no_action", "needs_capability"]

DECISION_SCHEMA: dict[str, Any] = {
    "type": "object", "additionalProperties": False,
    "required": ["outcome", "capability", "args", "reason", "question"],
    "properties": {
        "outcome": {"enum": ["propose_content", "propose_action", "ask_clarification",
                              "no_action", "needs_capability"]},
        "capability": {"type": "string"},
        "args": {"type": "object"},
        "reason": {"type": "string"},
        "question": {"type": "string"},
    },
}


@dataclass(frozen=True, slots=True)
class DirectorDecision:
    outcome: Outcome
    capability: str
    args: dict[str, Any]
    reason: str
    question: str


def decide_request(*, client: Any, evidence: dict[str, Any]) -> DirectorDecision:
    result = client.generate_json(
        schema_version="wm.director.decision.v1", schema=DECISION_SCHEMA,
        instruction=(
            "Classify the player's natural-language request. Propose only the listed capabilities. "
            "Use propose_content with capability quest for a playable kill quest request; "
            "use propose_action with capability world_announce_to_player and args.message for a clear "
            "announcement request. Ask a short clarification when essential details are missing. "
            "Use needs_capability when the desired mechanic is unavailable. Otherwise no_action. "
            "Never invent target IDs or player GUIDs; the host resolves them."
        ),
        context_pack=evidence,
    )
    request = result.get("request") if isinstance(result, dict) else None
    response_format = request.get("response_format") if isinstance(request, dict) else None
    if not isinstance(response_format, dict) or response_format.get("type") != "json_schema":
        raise ValueError("director decision was not schema-constrained")
    parsed = result.get("parsed")
    if not isinstance(parsed, dict) or set(parsed) != set(DECISION_SCHEMA["required"]):
        raise ValueError("director decision is missing required final fields")
    outcome = parsed["outcome"]
    if outcome not in DECISION_SCHEMA["properties"]["outcome"]["enum"]:
        raise ValueError("unknown director decision outcome")
    capability = str(parsed["capability"] or "").strip()
    args = parsed["args"]
    if not isinstance(args, dict):
        raise ValueError("director decision args must be an object")
    if outcome == "propose_content" and capability != "quest":
        return DirectorDecision("needs_capability", capability, {}, str(parsed["reason"])[:500], "")
    if outcome == "propose_action":
        message = args.get("message")
        if capability != "world_announce_to_player" or not isinstance(message, str) or not message.strip():
            return DirectorDecision("needs_capability", capability, {}, str(parsed["reason"])[:500], "")
    if outcome == "ask_clarification" and not str(parsed["question"] or "").strip():
        raise ValueError("clarification decision needs a question")
    return DirectorDecision(outcome, capability, args, str(parsed["reason"])[:500],
                            str(parsed["question"])[:300])
