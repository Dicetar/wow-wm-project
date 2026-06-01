from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from wm.sources.native_bridge.action_kinds import NATIVE_ACTION_KIND_BY_ID
from wm.sources.native_bridge.payload_contract import validate_native_action_payload

VERB_MODES = ("off", "confirm", "auto")
_RISK_DEFAULT_MODE = {"low": "auto", "medium": "confirm", "high": "confirm"}


def default_verb_modes() -> dict[str, str]:
    return {
        kind.kind: _RISK_DEFAULT_MODE.get(kind.default_risk, "confirm")
        for kind in NATIVE_ACTION_KIND_BY_ID.values()
        if kind.implemented and not kind.admin_only
    }


def resolve_verb_modes(config: dict[str, Any] | None) -> dict[str, str]:
    modes = default_verb_modes()
    for verb, mode in (config or {}).items():
        if verb in modes and str(mode) in VERB_MODES:
            modes[verb] = str(mode)
    return modes


@dataclass(slots=True)
class IntentRejection:
    reason: str


@dataclass(slots=True)
class CompiledIntent:
    proposal: Any          # wm.control.models.ControlProposal
    verb: str
    mode: str
    risk: str


def _stable(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:16]


def compile_intent(
    *,
    player_guid: int,
    verb: str,
    args: dict[str, Any] | None,
    modes: dict[str, str] | None,
    reason: str = "",
) -> CompiledIntent | IntentRejection:
    from wm.control.models import ControlProposal

    resolved = resolve_verb_modes(modes)
    mode = resolved.get(verb, "off")
    if mode == "off":
        return IntentRejection(f"verb not enabled: {verb!r}")
    kind = NATIVE_ACTION_KIND_BY_ID.get(verb)
    if kind is None or not kind.implemented:
        return IntentRejection(f"verb not implemented: {verb!r}")
    payload_args = dict(args or {})
    issues = validate_native_action_payload(action_kind=verb, payload=payload_args)
    if issues:
        return IntentRejection("; ".join(issues)[:300])
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    idem = f"autoplay:intent:{_stable(f'{player_guid}:{verb}:{payload_args}:{now}')}"
    proposal = ControlProposal.model_validate(
        {
            "schema_version": "control.proposal.v1",
            "source_event": None,
            "player": {"guid": int(player_guid)},
            "selected_recipe": "manual_admin_action",
            "action": {
                "kind": "native_bridge_action",
                "payload": {
                    "native_action_kind": verb,
                    "payload": payload_args,
                    "created_by": "wm.autoplay.intent",
                    "risk_level": kind.default_risk,
                    "expires_seconds": 120,
                },
            },
            "rationale": (reason or f"Conversational WM action: {verb}")[:300],
            "risk": {"level": kind.default_risk, "irreversible": False, "notes": []},
            "idempotency_key": idem,
            "author": {
                "kind": "manual_admin",
                "name": "wm.autoplay.intent",
                "manual_reason": (reason or f"operator-authorized conversational verb {verb}")[:300],
            },
            "metadata": {"lane": "intent", "intent_reason": reason[:300]},
        }
    )
    return CompiledIntent(proposal=proposal, verb=verb, mode=mode, risk=kind.default_risk)


_AFFIRM = {"yes", "y", "yeah", "yep", "do it", "go ahead", "confirm", "ok", "okay", "sure", "go for it"}
_NEGATE = {"no", "n", "nope", "cancel", "stop", "nevermind", "never mind", "forget it", "no thanks"}


def _norm(message: str) -> str:
    return " ".join(str(message).strip().lower().split()).rstrip("!.")


def is_affirmation(message: str) -> bool:
    return _norm(message) in _AFFIRM


def is_negation(message: str) -> bool:
    return _norm(message) in _NEGATE
