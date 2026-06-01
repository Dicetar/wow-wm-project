"""Schema-constrained conversational-memory extractor (Phase 4 write path).

Each chat turn, this runs a separate deterministic pass over the player's
message and asks a schema-bound LLM call whether the player stated something
*durable and worth remembering across sessions* -- a stable preference, a
personal fact, a chosen form of address, a like/dislike. Most turns say no.

When it says yes, it returns a typed conversation-steering note candidate. The
service persists it through the existing validated seam
(``CharacterJourneyApplier.apply_plan({"conversation_steering": [...]})``) -- it
is never a freeform write. Any failure here returns ``None`` so the chat reply
is never blocked, and the LLM only proposes: deterministic code slugifies the
key, clamps lengths, and the journey applier validates before the upsert.
"""

from __future__ import annotations

import re
from typing import Any

_SCHEMA_VERSION = "wm.autoplay.memory_extract.v1"

# Durable note categories. Free-form steering_kind is allowed downstream, but we
# steer the model toward these so memory stays meaningful, not chit-chat.
_STEERING_KINDS = (
    "player_preference",
    "player_fact",
    "form_of_address",
    "preferred_theme",
    "disliked_theme",
)

_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "remember": {"type": "boolean"},
        "steering_key": {"type": "string"},
        "steering_kind": {"type": "string"},
        "body": {"type": "string"},
        "reason": {"type": "string"},
    },
    "required": ["remember", "steering_key", "steering_kind", "body", "reason"],
    "additionalProperties": False,
}

_KEY_MAX = 64
_BODY_MAX = 240


def _slugify_key(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_")
    return slug[:_KEY_MAX]


def extract_memory_note(
    *,
    client: Any,
    player_guid: int,
    message: str,
    identity: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Return a typed conversation-steering note candidate, or ``None``.

    Never raises: any failure (no model, transport error, malformed output,
    nothing durable said) yields ``None``.
    """
    instruction = (
        "You capture durable memory for World Master. Decide whether the player's message "
        "states something worth remembering about THEM across sessions: a stable preference, "
        "a personal fact, how they want to be addressed, or a like/dislike. Do NOT remember "
        "transient things (current task, one-off requests, greetings, questions, small talk) "
        "or anything about the world rather than the player. When nothing durable is stated, "
        "set remember=false. When it is, write a short stable steering_key (snake_case), pick a "
        f"steering_kind from {list(_STEERING_KINDS)}, and a one-sentence body phrased as a fact "
        "World Master should keep in mind. Output only the JSON object."
    )
    context_pack = {
        "schema_version": _SCHEMA_VERSION,
        "player_guid": int(player_guid),
        "player_message": str(message)[:1000],
        "player_identity": identity or {},
        "steering_kinds": list(_STEERING_KINDS),
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
    if not bool(parsed.get("remember")):
        return None
    key = _slugify_key(parsed.get("steering_key") or "")
    body = str(parsed.get("body") or "").strip()[:_BODY_MAX]
    if not key or not body:
        return None
    kind = str(parsed.get("steering_kind") or "").strip() or "player_preference"
    if kind not in _STEERING_KINDS:
        kind = "player_preference"
    return {
        "steering_key": key,
        "steering_kind": kind,
        "body": body,
        "source": "conversation",
        "reason": str(parsed.get("reason") or "")[:300],
    }


def build_memory_client(client_factory: Any, settings: Any, *, control_config: dict[str, Any]):
    """Build a json-schema LM Studio client for memory extraction.

    Uses a dedicated ``llm_memory_model`` if configured, else the intent model,
    else the chat model.
    """
    from dataclasses import replace

    model = control_config.get("llm_memory_model") or control_config.get("llm_intent_model") or settings.model
    memory_settings = replace(settings, schema_mode="json_schema", model=model, max_tokens=256)
    return client_factory(memory_settings)
