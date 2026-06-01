"""Schema-constrained chat-intent extractor (second pass).

The conversational chat model is an in-character roleplay voice; it narrates but
almost never emits a usable typed verb. This module runs a separate, deterministic
classification pass over the same player message and verb catalog, asking a
schema-bound LLM call whether the player clearly wants exactly one implemented
verb and, if so, with what args.

It only proposes. Everything downstream is unchanged: `compile_intent` still
validates the verb is enabled + implemented and that the payload satisfies its
contract, the coordinator still dry-runs, and confirm-mode still gates risky
verbs. Any failure here returns ``None`` so the chat reply is never blocked.
"""

from __future__ import annotations

import json
from typing import Any


_SCHEMA_VERSION = "wm.autoplay.intent_extract.v1"

_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "act": {"type": "boolean"},
        "verb": {"type": "string"},
        "args": {"type": "object"},
        "reason": {"type": "string"},
    },
    "required": ["act", "verb", "args", "reason"],
    "additionalProperties": False,
}


def _verb_catalog(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    catalog: list[dict[str, Any]] = []
    for action in manifest.get("native_actions", []) or []:
        if not isinstance(action, dict):
            continue
        kind = action.get("kind")
        if not kind:
            continue
        entry: dict[str, Any] = {"verb": kind, "description": action.get("description", "")}
        for field in ("required", "required_any", "optional", "notes"):
            value = action.get(field)
            if value:
                entry[field] = value
        catalog.append(entry)
    return catalog


def extract_chat_intent(
    *,
    client: Any,
    player_guid: int,
    message: str,
    manifest: dict[str, Any],
    identity: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Return a typed ``{verb, args, reason}`` intent or ``None``.

    Never raises: any extraction failure (no model, transport error, malformed
    output, verb not in the catalog) yields ``None``.
    """
    catalog = _verb_catalog(manifest)
    if not catalog:
        return None
    allowed = {str(item["verb"]) for item in catalog}
    instruction = (
        "You are the intent extractor for World Master. Decide whether the player's "
        "message is a clear request to perform exactly one of the listed verbs in the "
        "live game world. Only act when the request is unambiguous. Fill args using the "
        "verb's required / required_any / optional fields; use exact field names. If the "
        "player is just chatting, greeting, asking a question, or unclear, set act=false. "
        "Never invent a verb that is not in the catalog. Output only the JSON object."
    )
    context_pack = {
        "schema_version": _SCHEMA_VERSION,
        "player_guid": int(player_guid),
        "player_message": str(message)[:1000],
        "player_identity": identity or {},
        "verb_catalog": catalog,
    }
    try:
        result = client.generate_json(
            schema_version=_SCHEMA_VERSION,
            schema=_OUTPUT_SCHEMA,
            instruction=instruction,
            context_pack=context_pack,
        )
    except Exception:
        return None
    parsed = result.get("parsed") if isinstance(result, dict) else None
    if not isinstance(parsed, dict):
        return None
    if not bool(parsed.get("act")):
        return None
    verb = str(parsed.get("verb") or "").strip()
    if verb not in allowed:
        return None
    args = parsed.get("args")
    return {
        "verb": verb,
        "args": args if isinstance(args, dict) else {},
        "reason": str(parsed.get("reason") or "")[:300],
    }


def build_intent_client(client_factory: Any, settings: Any, *, control_config: dict[str, Any]):
    """Build a json-schema LM Studio client for intent extraction.

    Uses a dedicated ``llm_intent_model`` if configured, else the chat model.
    """
    from dataclasses import replace

    model = control_config.get("llm_intent_model") or settings.model
    intent_settings = replace(settings, schema_mode="json_schema", model=model, max_tokens=256)
    return client_factory(intent_settings)
