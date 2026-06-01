"""Phase 5: LLM-composed conversational scenes, deterministically validated.

When a player asks WM to stage a moment ("summon a guard to greet me, then send
it off"), the model proposes an ordered list of native-action steps. The LLM only
*proposes*; this module validates every step deterministically before anything
runs:

  * only scene-safe, implemented verbs (reuses release._SCENE_ALLOWED_ACTION_KINDS,
    which excludes gameobject/weather/unimplemented verbs);
  * each step's payload satisfies its native payload contract;
  * creature_spawn steps get their spoken creature name resolved to a real
    creature_entry (via the offline resolver), like the single-action path;
  * owned-cleanup: a scene that spawns creatures must also despawn them or make
    every spawn temporary (duration_ms), so scenes never leak permanent actors;
  * the step count is capped.

Validated steps come back in the ``scene_play.SceneStep`` shape so the existing
scene runner / coordinator executes them with full audit + idempotency. Any
failure returns a SceneComposeError (validation) or ``None`` (nothing to do), so
the chat reply is never blocked and nothing unsafe is enqueued.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from wm.content.release import _SCENE_ALLOWED_ACTION_KINDS, _SCENE_UNSUPPORTED_MESSAGES
from wm.sources.native_bridge.action_kinds import NATIVE_ACTION_KIND_BY_ID
from wm.sources.native_bridge.payload_contract import validate_native_action_payload

_SCHEMA_VERSION = "wm.autoplay.scene_compose.v1"
_MAX_STEPS = 8

_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "compose": {"type": "boolean"},
        "scene_name": {"type": "string"},
        "steps": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "native_action_kind": {"type": "string"},
                    "payload": {"type": "object"},
                    "expected_effect": {"type": "string"},
                },
                "required": ["native_action_kind", "payload"],
                "additionalProperties": False,
            },
        },
        "reason": {"type": "string"},
    },
    "required": ["compose", "scene_name", "steps", "reason"],
    "additionalProperties": False,
}


@dataclass(slots=True)
class SceneComposeError:
    reason: str


@dataclass(slots=True)
class ComposedScene:
    scene_name: str
    steps: list[dict[str, Any]] = field(default_factory=list)  # {native_action_kind, payload, expected_effect}


def validate_scene_steps(
    raw_steps: Any,
    *,
    resolver: Any = None,
) -> list[dict[str, Any]] | SceneComposeError:
    """Validate + normalize proposed scene steps. Reuses the scene safety rules."""
    if not isinstance(raw_steps, list) or not raw_steps:
        return SceneComposeError("scene has no steps")
    if len(raw_steps) > _MAX_STEPS:
        return SceneComposeError(f"scene has too many steps ({len(raw_steps)} > {_MAX_STEPS})")

    validated: list[dict[str, Any]] = []
    spawn_count = 0
    despawn_count = 0
    spawns_all_temporary = True

    for index, raw in enumerate(raw_steps):
        if not isinstance(raw, dict):
            return SceneComposeError(f"step {index} is not an object")
        verb = str(raw.get("native_action_kind") or "").strip()
        if not verb:
            return SceneComposeError(f"step {index} is missing native_action_kind")
        if verb in _SCENE_UNSUPPORTED_MESSAGES:
            return SceneComposeError(_SCENE_UNSUPPORTED_MESSAGES[verb])
        if verb not in _SCENE_ALLOWED_ACTION_KINDS:
            return SceneComposeError(f"step {index}: {verb!r} is not a scene-safe action")
        kind = NATIVE_ACTION_KIND_BY_ID.get(verb)
        if kind is None or not kind.implemented:
            return SceneComposeError(f"step {index}: {verb!r} is not implemented")

        payload = raw.get("payload") if isinstance(raw.get("payload"), dict) else {}

        if verb == "creature_spawn":
            from wm.autoplay.spawn_args import SpawnArgsError, prepare_creature_spawn_args

            prepared = prepare_creature_spawn_args(payload, resolver=resolver)
            if isinstance(prepared, SpawnArgsError):
                return SceneComposeError(f"step {index}: {prepared.reason}")
            payload = prepared
            spawn_count += 1
            if prepared.get("duration_ms") is None:
                spawns_all_temporary = False
        elif verb == "creature_despawn":
            despawn_count += 1

        issues = validate_native_action_payload(action_kind=verb, payload=payload)
        if issues:
            return SceneComposeError(f"step {index} ({verb}): {'; '.join(issues)[:200]}")

        validated.append({
            "native_action_kind": verb,
            "payload": payload,
            "expected_effect": str(raw.get("expected_effect") or "")[:200],
        })

    # Owned cleanup: spawned creatures must be despawned or made temporary.
    if spawn_count > 0 and despawn_count == 0 and not spawns_all_temporary:
        return SceneComposeError(
            "scene spawns creatures without cleanup; add a creature_despawn step or duration_ms on each spawn"
        )

    return validated


def extract_scene_request(
    *,
    client: Any,
    player_guid: int,
    message: str,
    identity: dict[str, Any] | None = None,
    resolver: Any = None,
) -> ComposedScene | None:
    """Return a validated ComposedScene the player asked WM to stage, or None.

    Never raises: no model, transport error, malformed output, nothing to stage,
    or a scene that fails validation all yield ``None`` (chat is never blocked).
    """
    instruction = (
        "You are the scene director for World Master. Decide whether the player is asking "
        "you to STAGE a small live moment (summon creatures, have them speak/emote/cast, "
        "apply a visible aura, then send them away). If so, set compose=true and lay out an "
        "ordered list of steps. Use only these scene actions: "
        f"{sorted(_SCENE_ALLOWED_ACTION_KINDS)}. For creature_spawn, give a creature_name "
        "(e.g. 'guard', 'wolf') -- the system resolves it. Link a spawned creature to its "
        "later steps by giving them all the SAME arc_key (e.g. arc_key='greet'): the spawn, "
        "its creature_say (needs text), creature_emote (emote_id), creature_cast_spell, and "
        "creature_despawn all share that arc_key. Any creatures you spawn MUST be cleaned up: "
        "add a creature_despawn step (same arc_key) or set duration_ms on the spawn. "
        "Keep it to a few steps. If the player is just chatting or wants a single simple "
        "action, set compose=false. Output only the JSON object."
    )
    context_pack = {
        "schema_version": _SCHEMA_VERSION,
        "player_guid": int(player_guid),
        "player_message": str(message)[:1000],
        "player_identity": identity or {},
        "scene_actions": sorted(_SCENE_ALLOWED_ACTION_KINDS),
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
    if not isinstance(parsed, dict) or not bool(parsed.get("compose")):
        return None
    validated = validate_scene_steps(parsed.get("steps"), resolver=resolver)
    if isinstance(validated, SceneComposeError):
        return None
    scene_name = str(parsed.get("scene_name") or "scene").strip()[:64] or "scene"
    return ComposedScene(scene_name=scene_name, steps=validated)
