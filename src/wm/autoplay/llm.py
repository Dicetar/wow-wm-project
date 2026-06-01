from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from wm.llm.lmstudio import LmStudioClient
from wm.panel.schemas import SchemaCatalog


SCHEMA_BY_LANE: dict[str, str] = {
    "quest": "wm.quest.release.repeatable_bounty.v1",
    "item": "wm.item.release.managed_power.v1",
    "spell": "wm.spell.release.managed_spell.v1",
    "ability": "wm.ability.release.shell_power.v1",
    "scene": "wm.scene.release.native_sequence.v1",
    "action": "control.proposal.v1",
}

FORBIDDEN_TEXT = (
    "freeform_sql",
    "gm_command",
    "shell_command",
    "powershell",
    "cmd.exe",
    "mysql ",
    "insert into",
    "update ",
    "delete from",
    "drop table",
    ".additem",
    ".learn",
    ".modify",
)


@dataclass(slots=True)
class LlmDraftResult:
    ok: bool
    schema_version: str
    draft: dict[str, Any] | None = None
    request: dict[str, Any] | None = None
    issues: list[dict[str, str]] = field(default_factory=list)
    raw_content: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class AutoplayLlmAdapter:
    client: LmStudioClient
    schemas: SchemaCatalog = field(default_factory=SchemaCatalog.load)

    def health(self) -> dict[str, Any]:
        try:
            models = self.client.list_models()
            configured = self.client.settings.model
            return {
                "ok": bool(configured and configured in models),
                "base_url": self.client.settings.base_url,
                "model": configured,
                "models": models,
                "error": None if configured else "LM Studio model is not configured.",
            }
        except Exception as exc:
            return {
                "ok": False,
                "base_url": self.client.settings.base_url,
                "model": self.client.settings.model,
                "models": [],
                "error": str(exc),
            }

    def generate(
        self,
        *,
        schema_version: str,
        instruction: str,
        context_pack: dict[str, Any] | None = None,
        candidate_pack: dict[str, Any] | None = None,
        deterministic_facts: dict[str, Any] | None = None,
    ) -> LlmDraftResult:
        try:
            entry = self.schemas.get(schema_version)
        except KeyError as exc:
            return LlmDraftResult(
                ok=False,
                schema_version=schema_version,
                issues=[{"path": "schema_version", "message": str(exc), "severity": "error"}],
            )
        try:
            result = self.client.generate_json(
                schema_version=schema_version,
                schema=llm_generation_schema(schema_version, entry.schema),
                instruction=instruction,
                context_pack=context_pack,
                candidate_pack=candidate_pack,
            )
        except Exception as exc:
            return LlmDraftResult(
                ok=False,
                schema_version=schema_version,
                issues=[{"path": "llm", "message": str(exc), "severity": "error"}],
            )
        draft = result.get("parsed") if isinstance(result.get("parsed"), dict) else None
        if draft is None:
            return LlmDraftResult(
                ok=False,
                schema_version=schema_version,
                request=result.get("request") if isinstance(result.get("request"), dict) else None,
                raw_content=str(result.get("content") or ""),
                issues=[{"path": "llm.content", "message": "LM Studio did not return a JSON object.", "severity": "error"}],
            )
        locked = lock_deterministic_facts(draft, deterministic_facts or {}, schema_version=schema_version)
        issues = screen_forbidden_content(locked)
        validation = self.schemas.validate(schema_version, locked)
        issues.extend(validation.get("issues") or [])
        ok = not any(str(issue.get("severity", "error")) == "error" for issue in issues)
        return LlmDraftResult(
            ok=ok,
            schema_version=schema_version,
            draft=locked,
            request=result.get("request") if isinstance(result.get("request"), dict) else None,
            raw_content=str(result.get("content") or ""),
            issues=issues,
        )


def schema_for_lane(lane: str) -> str:
    try:
        return SCHEMA_BY_LANE[str(lane)]
    except KeyError as exc:
        raise KeyError(f"Unsupported autoplay LLM lane: {lane}") from exc


def llm_generation_schema(schema_version: str, schema: dict[str, Any]) -> dict[str, Any]:
    if schema_version == "wm.quest.release.repeatable_bounty.v1":
        return {
            "type": "object",
            "additionalProperties": False,
            "required": ["schema_version", "quest_kind", "player_guid", "slot_policy", "repeatable", "quest", "objective", "reward"],
            "properties": {
                "schema_version": {"const": "wm.quest.release.repeatable_bounty.v1"},
                "quest_kind": {"const": "repeatable_bounty"},
                "player_guid": {"type": "integer"},
                "slot_policy": {"enum": ["fresh_reserved_or_existing_active_repeatable", "fresh_reserved_required"]},
                "repeatable": {"const": True},
                "quest": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["quest_level", "min_level", "grant_mode", "template_defaults"],
                    "properties": {
                        "quest_id": {"type": ["integer", "null"]},
                        "quest_level": {"type": "integer"},
                        "min_level": {"type": "integer"},
                        "questgiver_entry": {"type": ["integer", "null"]},
                        "questgiver_name": {"type": ["string", "null"]},
                        "title": {"type": ["string", "null"]},
                        "quest_description": {"type": ["string", "null"]},
                        "objective_text": {"type": ["string", "null"]},
                        "offer_reward_text": {"type": ["string", "null"]},
                        "request_items_text": {"type": ["string", "null"]},
                        "grant_mode": {"enum": ["direct_grant", "npc_start", "manual_operator"]},
                        "start_npc_entry": {"type": ["integer", "null"]},
                        "end_npc_entry": {"type": ["integer", "null"]},
                        "template_defaults": {
                            "type": "object",
                            "additionalProperties": True,
                            "required": ["SpecialFlags"],
                            "properties": {"SpecialFlags": {"const": 1}},
                        },
                    },
                },
                "objective": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["kind", "target_entry", "kill_count"],
                    "properties": {
                        "kind": {"const": "kill"},
                        "target_entry": {"type": "integer"},
                        "target_name": {"type": ["string", "null"]},
                        "kill_count": {"type": "integer"},
                    },
                },
                "reward": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["kind"],
                    "properties": {
                        "kind": {"enum": ["none", "money"]},
                        "money_copper": {"type": ["integer", "null"]},
                    },
                },
                "runtime_sync": {"type": "object", "additionalProperties": True},
                "notes": {"type": ["array", "string", "null"], "items": {"type": "string"}},
            },
        }
    if schema_version == "wm.item.release.managed_power.v1":
        return {
            "type": "object",
            "additionalProperties": False,
            "required": ["schema_version", "content_kind", "player_guid", "item_key", "item_entry", "slot_policy", "base_item_entry", "visibility", "effects", "reward_integration", "runtime"],
            "properties": {
                "schema_version": {"const": "wm.item.release.managed_power.v1"},
                "content_kind": {"const": "item"},
                "player_guid": {"type": "integer"},
                "item_key": {"type": "string"},
                "item_entry": {"type": "integer"},
                "slot_policy": {"enum": ["fresh_item_slot_required", "existing_proven_item_slot_extension"]},
                "base_item_entry": {"type": "integer"},
                "item_shape": {"type": "object", "additionalProperties": True},
                "visibility": {"type": "object", "additionalProperties": True},
                "effects": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
                "reward_integration": {"type": "object", "additionalProperties": True},
                "runtime": {"type": "object", "additionalProperties": True},
                "notes": {"type": ["array", "string", "null"], "items": {"type": "string"}},
            },
        }
    if schema_version == "wm.spell.release.managed_spell.v1":
        return {
            "type": "object",
            "additionalProperties": False,
            "required": ["schema_version", "content_kind", "player_guid", "spell_key", "spell_entry", "slot_kind", "name", "base_visible_spell_id", "proc_rules", "linked_spells", "runtime"],
            "properties": {
                "schema_version": {"const": "wm.spell.release.managed_spell.v1"},
                "content_kind": {"const": "spell"},
                "player_guid": {"type": "integer"},
                "spell_key": {"type": "string"},
                "spell_entry": {"type": "integer"},
                "slot_kind": {"type": "string"},
                "name": {"type": "string"},
                "base_visible_spell_id": {"type": ["integer", "null"]},
                "aura_description": {"type": ["string", "null"]},
                "proc_rules": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
                "linked_spells": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
                "runtime": {"type": "object", "additionalProperties": True},
                "tags": {"type": "array", "items": {"type": "string"}},
                "notes": {"type": ["array", "string", "null"], "items": {"type": "string"}},
            },
        }
    if schema_version == "wm.scene.release.native_sequence.v1":
        return {
            "type": "object",
            "additionalProperties": False,
            "required": ["schema_version", "content_kind", "player_guid", "scene_key", "scene_type", "slot_policy", "trigger", "runtime", "steps"],
            "properties": {
                "schema_version": {"const": "wm.scene.release.native_sequence.v1"},
                "content_kind": {"const": "scene"},
                "player_guid": {"type": "integer"},
                "scene_key": {"type": "string"},
                "scene_type": {"enum": ["creature_marker", "environment_effect", "area_pressure", "companion_intervention", "arc_beat"]},
                "slot_policy": {"const": "no_visible_id_required"},
                "trigger": {"type": "object", "additionalProperties": True},
                "runtime": {"type": "object", "additionalProperties": True},
                "steps": {
                    "type": "array",
                    "minItems": 1,
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["step_key", "native_action_kind", "payload", "risk_level", "idempotency_suffix", "requires_live_proof"],
                        "properties": {
                            "step_key": {"type": "string"},
                            "native_action_kind": {"enum": ["player_chat_message"]},
                            "payload": {"type": "object", "additionalProperties": True},
                            "risk_level": {"const": "low"},
                            "idempotency_suffix": {"type": "string"},
                            "expected_effect": {"type": ["string", "null"]},
                            "requires_live_proof": {"const": True},
                        },
                    },
                },
                "notes": {"type": ["array", "string", "null"], "items": {"type": "string"}},
            },
        }
    if schema_version == "control.proposal.v1":
        return {
            "type": "object",
            "additionalProperties": False,
            "required": ["schema_version", "source_event", "player", "selected_recipe", "action", "rationale", "risk", "author", "metadata"],
            "properties": {
                "schema_version": {"const": "control.proposal.v1"},
                "source_event": {
                    "type": "object",
                    "additionalProperties": True,
                    "properties": {
                        "event_id": {"type": ["integer", "null"]},
                        "source": {"type": ["string", "null"]},
                        "source_event_key": {"type": ["string", "null"]},
                        "event_type": {"type": ["string", "null"]},
                    },
                },
                "player": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["guid"],
                    "properties": {
                        "guid": {"type": "integer"},
                        "name": {"type": ["string", "null"]},
                    },
                },
                "selected_recipe": {"const": "manual_admin_action"},
                "action": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["kind", "payload"],
                    "properties": {
                        "kind": {"const": "native_bridge_action"},
                        "payload": {
                            "type": "object",
                            "additionalProperties": True,
                            "required": ["native_action_kind", "payload"],
                            "properties": {
                                "native_action_kind": {"enum": ["player_chat_message"]},
                                "payload": {"type": "object", "additionalProperties": True},
                            },
                        },
                    },
                },
                "rationale": {"type": "string"},
                "risk": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["level", "irreversible", "notes"],
                    "properties": {
                        "level": {"const": "low"},
                        "irreversible": {"const": False},
                        "notes": {"type": "array", "items": {"type": "string"}},
                    },
                },
                "author": {
                    "type": "object",
                    "additionalProperties": True,
                    "required": ["kind"],
                    "properties": {"kind": {"const": "llm"}, "name": {"type": ["string", "null"]}},
                },
                "metadata": {"type": "object", "additionalProperties": True},
                "idempotency_key": {"type": ["string", "null"]},
                "expected_effect": {"type": ["string", "null"]},
            },
        }
    return schema


def lock_deterministic_facts(draft: dict[str, Any], facts: dict[str, Any], *, schema_version: str) -> dict[str, Any]:
    locked = dict(draft)
    locked["schema_version"] = schema_version
    if facts.get("player_guid") not in (None, "") and "player_guid" in locked:
        locked["player_guid"] = int(facts["player_guid"])
    if schema_version == "wm.quest.release.repeatable_bounty.v1":
        locked["quest_kind"] = "repeatable_bounty"
        locked["repeatable"] = True
        locked["slot_policy"] = str(locked.get("slot_policy") or "fresh_reserved_required")
        source_event = facts.get("source_event") if isinstance(facts.get("source_event"), dict) else {}
        quest = locked.get("quest") if isinstance(locked.get("quest"), dict) else {}
        quest["grant_mode"] = "direct_grant"
        quest.setdefault("quest_level", 70)
        quest.setdefault("min_level", min(int(quest.get("quest_level") or 70), 70))
        quest.setdefault("questgiver_entry", 240)
        quest.setdefault("questgiver_name", "Marshal McBride")
        quest["template_defaults"] = {"SpecialFlags": 1, **dict(quest.get("template_defaults") or {})}
        quest["template_defaults"]["SpecialFlags"] = 1
        objective = locked.get("objective") if isinstance(locked.get("objective"), dict) else {}
        objective["kind"] = "kill"
        if source_event.get("subject_entry") not in (None, ""):
            objective["target_entry"] = int(source_event["subject_entry"])
        metadata = source_event.get("metadata") if isinstance(source_event.get("metadata"), dict) else {}
        source_payload = metadata.get("payload") if isinstance(metadata.get("payload"), dict) else {}
        if source_payload.get("subject_name") and not objective.get("target_name"):
            objective["target_name"] = str(source_payload["subject_name"])
        objective.setdefault("kill_count", 3)
        reward = locked.get("reward") if isinstance(locked.get("reward"), dict) else {}
        if reward.get("kind") not in {"none", "money"}:
            reward = {"kind": "none"}
        locked["quest"] = quest
        locked["objective"] = objective
        locked["reward"] = reward
    if schema_version == "wm.item.release.managed_power.v1":
        if facts.get("item_entry") not in (None, ""):
            locked["item_entry"] = int(facts["item_entry"])
        if facts.get("stable_key") and not locked.get("item_key"):
            locked["item_key"] = f"autoplay_{facts['stable_key']}"
    if schema_version == "wm.spell.release.managed_spell.v1":
        if facts.get("player_guid") not in (None, ""):
            locked["player_guid"] = int(facts["player_guid"])
        if facts.get("spell_entry") not in (None, ""):
            locked["spell_entry"] = int(facts["spell_entry"])
        if facts.get("stable_key") and not locked.get("spell_key"):
            locked["spell_key"] = f"autoplay_{facts['stable_key']}"
        tags = locked.get("tags") if isinstance(locked.get("tags"), list) else []
        locked["tags"] = sorted({*[str(item) for item in tags], "wm_autoplay", "llm_draft"})
    if schema_version == "wm.ability.release.shell_power.v1":
        if facts.get("stable_key") and not locked.get("ability_key"):
            locked["ability_key"] = f"autoplay_{facts['stable_key']}"
        allowed_families = {str(item) for item in facts.get("allowed_shell_families") or []}
        if allowed_families and locked.get("shell_family") not in allowed_families:
            locked["ability_type"] = "self_aura"
            locked["shell_family"] = "self_aura"
            locked["slot_policy"] = "existing_named_shell"
            locked["behavior_kind"] = "self_aura"
    if schema_version == "control.proposal.v1":
        player = locked.get("player") if isinstance(locked.get("player"), dict) else {}
        if facts.get("player_guid") not in (None, ""):
            player["guid"] = int(facts["player_guid"])
        locked["player"] = player
        locked["selected_recipe"] = "manual_admin_action"
        stable_key = str(facts.get("stable_key") or "autoplay")
        locked["idempotency_key"] = str(locked.get("idempotency_key") or f"autoplay:action:{stable_key}")
        source_event = facts.get("source_event")
        if isinstance(source_event, dict):
            locked["source_event"] = _compact_control_source_event(source_event)
        action = locked.get("action") if isinstance(locked.get("action"), dict) else {}
        action["kind"] = "native_bridge_action"
        payload = action.get("payload") if isinstance(action.get("payload"), dict) else {}
        allowed = [str(item) for item in facts.get("allowed_native_action_kinds") or []]
        native_kind = str(payload.get("native_action_kind") or "")
        if allowed and native_kind not in set(allowed):
            native_kind = allowed[0]
        if not native_kind:
            native_kind = "debug_ping"
        payload["native_action_kind"] = native_kind
        nested_payload = payload.get("payload") if isinstance(payload.get("payload"), dict) else {}
        if native_kind == "player_chat_message":
            if not (nested_payload.get("message") or nested_payload.get("text")):
                nested_payload["message"] = "WM senses the moment and answers quietly."
            nested_payload.setdefault("style", "channel")
            nested_payload.setdefault("channel_name", "WM")
            nested_payload.setdefault("sender_name", "WorldMaster")
        elif native_kind == "world_announce_to_player" and not (nested_payload.get("message") or nested_payload.get("text")):
            nested_payload["message"] = "WM senses the moment and answers quietly."
        payload["payload"] = nested_payload
        payload["created_by"] = "wm.autoplay.llm"
        payload["risk_level"] = "low"
        payload["expires_seconds"] = int(payload.get("expires_seconds") or 60)
        action["payload"] = payload
        locked["action"] = action
        risk = locked.get("risk") if isinstance(locked.get("risk"), dict) else {}
        risk["level"] = "low"
        risk["irreversible"] = False
        locked["risk"] = risk
        author = locked.get("author") if isinstance(locked.get("author"), dict) else {}
        author["kind"] = "llm"
        locked["author"] = author
    if schema_version == "wm.scene.release.native_sequence.v1":
        if facts.get("player_guid") not in (None, ""):
            locked["player_guid"] = int(facts["player_guid"])
        if facts.get("stable_key") and not locked.get("scene_key"):
            locked["scene_key"] = f"autoplay_{facts['stable_key']}"
        source_event = facts.get("source_event")
        if isinstance(source_event, dict):
            trigger = locked.get("trigger") if isinstance(locked.get("trigger"), dict) else {}
            trigger["source_event_required"] = True
            trigger["max_event_age_seconds"] = int(facts.get("max_event_age_seconds") or 300)
            if source_event.get("event_type") == "kill":
                trigger["kind"] = "kill_reaction"
            elif source_event.get("event_type") in {"quest_complete", "quest_completed", "quest_rewarded"}:
                trigger["kind"] = "quest_reaction"
            elif source_event.get("event_type") == "talk":
                trigger["kind"] = "talk_reaction"
            elif source_event.get("event_type") == "enter_area":
                trigger["kind"] = "area_pressure"
            trigger.setdefault("kind", "manual_operator")
            locked["trigger"] = trigger
        allowed = set(str(item) for item in facts.get("allowed_native_action_kinds") or [])
        if allowed:
            steps = locked.get("steps")
            if isinstance(steps, list):
                for index, step in enumerate(steps):
                    if isinstance(step, dict) and step.get("native_action_kind") not in allowed:
                        fallback_kind = sorted(allowed)[0]
                        step["native_action_kind"] = fallback_kind
                        step["payload"] = {"message": "WM sensed something nearby."}
                    if isinstance(step, dict):
                        step.setdefault("step_key", f"step_{index + 1}")
                        step.setdefault("risk_level", "low")
                        step.setdefault("idempotency_suffix", f"step_{index + 1}")
                        step.setdefault("requires_live_proof", True)
                        if step.get("native_action_kind") == "player_chat_message":
                            payload = step.get("payload") if isinstance(step.get("payload"), dict) else {}
                            if not (payload.get("message") or payload.get("text")):
                                payload["message"] = "WM sensed something nearby."
                            payload.setdefault("style", "channel")
                            payload.setdefault("channel_name", "WM")
                            payload.setdefault("sender_name", "WorldMaster")
                            step["payload"] = payload
                        elif step.get("native_action_kind") == "world_announce_to_player":
                            payload = step.get("payload") if isinstance(step.get("payload"), dict) else {}
                            if not (payload.get("message") or payload.get("text")):
                                payload["message"] = "WM sensed something nearby."
                            step["payload"] = payload
    return locked


def _compact_control_source_event(source_event: dict[str, Any]) -> dict[str, Any]:
    return {
        key: source_event.get(key)
        for key in ("event_id", "source", "source_event_key", "event_type")
        if source_event.get(key) not in (None, "")
    }


def screen_forbidden_content(value: Any, *, path: str = "") -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            lowered_key = str(key).lower()
            if lowered_key in {"sql", "freeform_sql", "gm_command", "shell_command", "config_edit"}:
                issues.append({"path": _join(path, str(key)), "message": "Forbidden mutation field.", "severity": "error"})
            issues.extend(screen_forbidden_content(nested, path=_join(path, str(key))))
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            issues.extend(screen_forbidden_content(nested, path=f"{path}[{index}]" if path else f"[{index}]"))
    elif isinstance(value, str):
        lowered = value.lower()
        for token in FORBIDDEN_TEXT:
            if token in lowered:
                issues.append({"path": path, "message": f"Forbidden mutation text: {token}", "severity": "error"})
                break
    return issues


def _join(parent: str, child: str) -> str:
    return f"{parent}.{child}" if parent else child
