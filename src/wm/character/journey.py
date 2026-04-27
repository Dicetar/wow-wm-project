from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any

from wm.character.reader import CharacterStateBundle, CharacterStateReader
from wm.config import Settings
from wm.db.mysql_cli import MysqlCliClient, MysqlCliError


JOURNEY_PLAN_SCHEMA_VERSION = "wm.character_journey.seed.v1"
DISALLOWED_PLAN_KEYS = {"sql", "sql_text", "sql_file", "gm_command", "gm_commands", "shell_command", "command"}
DISALLOWED_GRANT_METHODS = {"gm_command", "freeform_gm", "freeform_sql", "sql", "shell"}
ALLOWED_GRANT_METHODS = {"control", "native_bridge", "managed_publish", "shell_grant", "item_grant", "manual_record"}
ALLOWED_ARC_STATUSES = {"active", "paused", "completed", "failed", "retired"}


class JourneyPlanError(ValueError):
    """Raised when a character-journey plan is structurally unsafe or invalid."""


@dataclass(slots=True)
class JourneyOperation:
    label: str
    sql: str
    mutates: bool = True

    def to_dict(self, *, include_sql: bool = False) -> dict[str, Any]:
        payload = {"label": self.label, "mutates": self.mutates}
        if include_sql:
            payload["sql"] = self.sql
        return payload


@dataclass(slots=True)
class JourneyApplyResult:
    player_guid: int | None
    mode: str
    ok: bool
    status: str
    mutated: bool
    operations: list[JourneyOperation]
    error: str | None = None
    schema_version: str = JOURNEY_PLAN_SCHEMA_VERSION

    def to_dict(self, *, include_sql: bool = False) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "player_guid": self.player_guid,
            "mode": self.mode,
            "ok": self.ok,
            "status": self.status,
            "mutated": self.mutated,
            "operation_count": len(self.operations),
            "operations": [operation.to_dict(include_sql=include_sql) for operation in self.operations],
            "error": self.error,
        }


class CharacterJourneyStore:
    def __init__(self, *, client: MysqlCliClient, settings: Settings) -> None:
        self.client = client
        self.settings = settings

    def inspect(self, *, player_guid: int) -> CharacterStateBundle:
        return CharacterStateReader(client=self.client, settings=self.settings).load(character_guid=int(player_guid))

    def apply_plan(self, *, plan: dict[str, Any], mode: str = "dry-run") -> JourneyApplyResult:
        normalized = validate_journey_plan(plan)
        player_guid = int(normalized["player_guid"])
        operations = build_journey_operations(normalized)
        if mode == "dry-run":
            return JourneyApplyResult(
                player_guid=player_guid,
                mode=mode,
                ok=True,
                status="WORKING",
                mutated=False,
                operations=operations,
            )
        if mode != "apply":
            raise JourneyPlanError(f"Unsupported mode: {mode}")
        for operation in operations:
            try:
                self._execute(operation.sql)
            except MysqlCliError as exc:
                return JourneyApplyResult(
                    player_guid=player_guid,
                    mode=mode,
                    ok=False,
                    status="BROKEN",
                    mutated=True,
                    operations=operations,
                    error=f"{operation.label}: {_safe_error(exc)}",
                )
        return JourneyApplyResult(
            player_guid=player_guid,
            mode=mode,
            ok=True,
            status="WORKING",
            mutated=True,
            operations=operations,
        )

    def _execute(self, sql: str) -> list[dict[str, Any]]:
        return self.client.query(
            host=self.settings.char_db_host,
            port=self.settings.char_db_port,
            user=self.settings.char_db_user,
            password=self.settings.char_db_password,
            database=self.settings.char_db_name,
            sql=sql,
        )


def load_journey_plan(path: Path) -> dict[str, Any]:
    try:
        parsed = json.loads(path.read_text(encoding="utf-8-sig"))
    except OSError as exc:
        raise JourneyPlanError(f"Could not read plan JSON: {_safe_error(exc)}") from exc
    except json.JSONDecodeError as exc:
        raise JourneyPlanError(f"Invalid plan JSON: {_safe_error(exc)}") from exc
    if not isinstance(parsed, dict):
        raise JourneyPlanError("Journey plan must be a JSON object.")
    return parsed


def validate_journey_plan(plan: dict[str, Any]) -> dict[str, Any]:
    _reject_disallowed_keys(plan)
    allowed_top = {
        "schema_version",
        "player_guid",
        "profile",
        "arc_states",
        "unlocks",
        "reward_instances",
        "conversation_steering",
        "prompt_queue",
        "metadata",
    }
    unknown = sorted(set(plan) - allowed_top)
    if unknown:
        raise JourneyPlanError(f"Unsupported journey plan field(s): {', '.join(unknown)}")
    if plan.get("schema_version") != JOURNEY_PLAN_SCHEMA_VERSION:
        raise JourneyPlanError(f"schema_version must be {JOURNEY_PLAN_SCHEMA_VERSION}")
    player_guid = _positive_int(plan.get("player_guid"), "player_guid")
    normalized: dict[str, Any] = {"schema_version": JOURNEY_PLAN_SCHEMA_VERSION, "player_guid": player_guid}
    normalized["profile"] = _normalize_profile(plan.get("profile"), player_guid=player_guid)
    normalized["arc_states"] = [_normalize_arc(item, player_guid=player_guid) for item in _list_field(plan, "arc_states")]
    normalized["unlocks"] = [_normalize_unlock(item, player_guid=player_guid) for item in _list_field(plan, "unlocks")]
    normalized["reward_instances"] = [
        _normalize_reward(item, player_guid=player_guid) for item in _list_field(plan, "reward_instances")
    ]
    normalized["conversation_steering"] = [
        _normalize_steering(item, player_guid=player_guid) for item in _list_field(plan, "conversation_steering")
    ]
    normalized["prompt_queue"] = [
        _normalize_prompt(item, player_guid=player_guid) for item in _list_field(plan, "prompt_queue")
    ]
    normalized["metadata"] = plan.get("metadata") if isinstance(plan.get("metadata"), dict) else {}
    return normalized


def build_journey_operations(plan: dict[str, Any]) -> list[JourneyOperation]:
    normalized = plan if _is_normalized_plan(plan) else validate_journey_plan(plan)
    operations: list[JourneyOperation] = []
    profile = normalized.get("profile")
    if profile is not None:
        operations.append(JourneyOperation(label="profile:upsert", sql=_profile_upsert_sql(profile)))
    for arc in normalized.get("arc_states") or []:
        operations.append(JourneyOperation(label=f"arc_state:upsert:{arc['arc_key']}", sql=_arc_upsert_sql(arc)))
    for unlock in normalized.get("unlocks") or []:
        operations.append(
            JourneyOperation(
                label=f"unlock:record:{unlock['unlock_kind']}:{unlock['unlock_id']}",
                sql=_unlock_upsert_sql(unlock),
            )
        )
    for reward in normalized.get("reward_instances") or []:
        operations.append(
            JourneyOperation(
                label=f"reward:dedupe:{reward['reward_kind']}:{reward['template_id']}",
                sql=_reward_delete_sql(reward),
            )
        )
        operations.append(
            JourneyOperation(
                label=f"reward:record:{reward['reward_kind']}:{reward['template_id']}",
                sql=_reward_insert_sql(reward),
            )
        )
    for note in normalized.get("conversation_steering") or []:
        operations.append(
            JourneyOperation(label=f"steering:upsert:{note['steering_key']}", sql=_steering_upsert_sql(note))
        )
    for prompt in normalized.get("prompt_queue") or []:
        operations.append(JourneyOperation(label=f"prompt:queue:{prompt['prompt_kind']}", sql=_prompt_insert_sql(prompt)))
    return operations


def _is_normalized_plan(plan: dict[str, Any]) -> bool:
    profile = plan.get("profile")
    if isinstance(profile, dict) and "character_guid" in profile:
        return True
    for key in ("arc_states", "unlocks", "reward_instances", "conversation_steering", "prompt_queue"):
        values = plan.get(key) or []
        if values and isinstance(values[0], dict) and "character_guid" in values[0]:
            return True
    return False


def inspect_journey_payload(*, player_guid: int, bundle: CharacterStateBundle) -> dict[str, Any]:
    return {
        "schema_version": "wm.character_journey.inspect.v1",
        "player_guid": int(player_guid),
        "status": bundle.status,
        "profile": asdict(bundle.profile) if bundle.profile is not None else None,
        "arc_states": [asdict(item) for item in bundle.arc_states],
        "unlocks": [asdict(item) for item in bundle.unlocks],
        "reward_instances": [asdict(item) for item in bundle.rewards],
        "conversation_steering": [asdict(item) for item in bundle.conversation_steering],
        "prompt_queue": [asdict(item) for item in bundle.prompt_queue],
        "notes": list(bundle.notes),
    }


def render_inspect_summary(payload: dict[str, Any]) -> str:
    profile = payload.get("profile") or {}
    return "\n".join(
        [
            f"journey: player={payload.get('player_guid')} name={profile.get('character_name')}",
            f"status: {payload.get('status')}",
            f"arcs: {len(payload.get('arc_states') or [])}",
            f"unlocks: {len(payload.get('unlocks') or [])}",
            f"reward_instances: {len(payload.get('reward_instances') or [])}",
            f"conversation_steering: {len(payload.get('conversation_steering') or [])}",
            f"prompt_queue: {len(payload.get('prompt_queue') or [])}",
            f"notes: {len(payload.get('notes') or [])}",
        ]
    )


def render_apply_summary(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"journey_apply: player={payload.get('player_guid')}",
            f"mode: {payload.get('mode')}",
            f"status: {payload.get('status')}",
            f"ok: {str(bool(payload.get('ok'))).lower()}",
            f"mutated: {str(bool(payload.get('mutated'))).lower()}",
            f"operations: {payload.get('operation_count')}",
            f"error: {payload.get('error')}" if payload.get("error") else "error: (none)",
        ]
    )


def _normalize_profile(raw: Any, *, player_guid: int) -> dict[str, Any] | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise JourneyPlanError("profile must be an object.")
    allowed = {"character_name", "wm_persona", "tone", "preferred_themes", "avoided_themes"}
    _reject_unknown(raw, allowed, "profile")
    character_name = _required_text(raw.get("character_name"), "profile.character_name")
    return {
        "character_guid": int(player_guid),
        "character_name": character_name,
        "wm_persona": _text_or_default(raw.get("wm_persona"), "default"),
        "tone": _text_or_default(raw.get("tone"), "adaptive"),
        "preferred_themes": _string_list(raw.get("preferred_themes"), "profile.preferred_themes"),
        "avoided_themes": _string_list(raw.get("avoided_themes"), "profile.avoided_themes"),
    }


def _normalize_arc(raw: Any, *, player_guid: int) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise JourneyPlanError("arc_states entries must be objects.")
    allowed = {"arc_key", "stage_key", "status", "branch_key", "summary"}
    _reject_unknown(raw, allowed, "arc_states[]")
    status = _text_or_default(raw.get("status"), "active")
    if status not in ALLOWED_ARC_STATUSES:
        raise JourneyPlanError(f"Unsupported arc status: {status}")
    return {
        "character_guid": int(player_guid),
        "arc_key": _required_text(raw.get("arc_key"), "arc_states[].arc_key"),
        "stage_key": _required_text(raw.get("stage_key"), "arc_states[].stage_key"),
        "status": status,
        "branch_key": _optional_text(raw.get("branch_key")),
        "summary": _optional_text(raw.get("summary")),
    }


def _normalize_unlock(raw: Any, *, player_guid: int) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise JourneyPlanError("unlocks entries must be objects.")
    allowed = {"unlock_kind", "unlock_id", "source_arc_key", "source_quest_id", "grant_method", "bot_eligible"}
    _reject_unknown(raw, allowed, "unlocks[]")
    grant_method = _text_or_default(raw.get("grant_method"), "control")
    if grant_method in DISALLOWED_GRANT_METHODS:
        raise JourneyPlanError(f"Unsupported grant_method for WM roadmap architecture: {grant_method}")
    if grant_method not in ALLOWED_GRANT_METHODS:
        raise JourneyPlanError(f"Unknown grant_method: {grant_method}")
    return {
        "character_guid": int(player_guid),
        "unlock_kind": _required_text(raw.get("unlock_kind"), "unlocks[].unlock_kind"),
        "unlock_id": _positive_int(raw.get("unlock_id"), "unlocks[].unlock_id"),
        "source_arc_key": _optional_text(raw.get("source_arc_key")),
        "source_quest_id": _optional_int(raw.get("source_quest_id"), "unlocks[].source_quest_id"),
        "grant_method": grant_method,
        "bot_eligible": _bool(raw.get("bot_eligible"), default=False),
    }


def _normalize_reward(raw: Any, *, player_guid: int) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise JourneyPlanError("reward_instances entries must be objects.")
    allowed = {"reward_kind", "template_id", "source_arc_key", "source_quest_id", "is_equipped_gate"}
    _reject_unknown(raw, allowed, "reward_instances[]")
    return {
        "character_guid": int(player_guid),
        "reward_kind": _required_text(raw.get("reward_kind"), "reward_instances[].reward_kind"),
        "template_id": _positive_int(raw.get("template_id"), "reward_instances[].template_id"),
        "source_arc_key": _optional_text(raw.get("source_arc_key")),
        "source_quest_id": _optional_int(raw.get("source_quest_id"), "reward_instances[].source_quest_id"),
        "is_equipped_gate": _bool(raw.get("is_equipped_gate"), default=False),
    }


def _normalize_steering(raw: Any, *, player_guid: int) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise JourneyPlanError("conversation_steering entries must be objects.")
    allowed = {"steering_key", "steering_kind", "body", "priority", "source", "is_active", "metadata"}
    _reject_unknown(raw, allowed, "conversation_steering[]")
    metadata = raw.get("metadata")
    if metadata is None:
        metadata = {}
    if not isinstance(metadata, dict):
        raise JourneyPlanError("conversation_steering[].metadata must be an object.")
    return {
        "character_guid": int(player_guid),
        "steering_key": _required_text(raw.get("steering_key"), "conversation_steering[].steering_key"),
        "steering_kind": _text_or_default(raw.get("steering_kind"), "player_preference"),
        "body": _required_text(raw.get("body"), "conversation_steering[].body"),
        "priority": _optional_int(raw.get("priority"), "conversation_steering[].priority") or 0,
        "source": _text_or_default(raw.get("source"), "operator"),
        "is_active": _bool(raw.get("is_active"), default=True),
        "metadata": metadata,
    }


def _normalize_prompt(raw: Any, *, player_guid: int) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise JourneyPlanError("prompt_queue entries must be objects.")
    allowed = {"prompt_kind", "body"}
    _reject_unknown(raw, allowed, "prompt_queue[]")
    return {
        "character_guid": int(player_guid),
        "prompt_kind": _required_text(raw.get("prompt_kind"), "prompt_queue[].prompt_kind"),
        "body": _required_text(raw.get("body"), "prompt_queue[].body"),
    }


def _profile_upsert_sql(profile: dict[str, Any]) -> str:
    return (
        "INSERT INTO wm_character_profile "
        "(CharacterGUID, CharacterName, WMPersona, Tone, PreferredThemesJSON, AvoidedThemesJSON) VALUES "
        f"({profile['character_guid']}, {_sql_string(profile['character_name'])}, "
        f"{_sql_string(profile['wm_persona'])}, {_sql_string(profile['tone'])}, "
        f"{_json_or_null(profile['preferred_themes'])}, {_json_or_null(profile['avoided_themes'])}) "
        "ON DUPLICATE KEY UPDATE "
        "CharacterName = VALUES(CharacterName), WMPersona = VALUES(WMPersona), Tone = VALUES(Tone), "
        "PreferredThemesJSON = VALUES(PreferredThemesJSON), AvoidedThemesJSON = VALUES(AvoidedThemesJSON)"
    )


def _arc_upsert_sql(arc: dict[str, Any]) -> str:
    return (
        "INSERT INTO wm_character_arc_state "
        "(CharacterGUID, ArcKey, StageKey, Status, BranchKey, Summary) VALUES "
        f"({arc['character_guid']}, {_sql_string(arc['arc_key'])}, {_sql_string(arc['stage_key'])}, "
        f"{_sql_string(arc['status'])}, {_sql_string_or_null(arc['branch_key'])}, {_sql_string_or_null(arc['summary'])}) "
        "ON DUPLICATE KEY UPDATE "
        "StageKey = VALUES(StageKey), Status = VALUES(Status), BranchKey = VALUES(BranchKey), Summary = VALUES(Summary)"
    )


def _unlock_upsert_sql(unlock: dict[str, Any]) -> str:
    return (
        "INSERT INTO wm_character_unlock "
        "(CharacterGUID, UnlockKind, UnlockID, SourceArcKey, SourceQuestID, GrantMethod, BotEligible) VALUES "
        f"({unlock['character_guid']}, {_sql_string(unlock['unlock_kind'])}, {unlock['unlock_id']}, "
        f"{_sql_string_or_null(unlock['source_arc_key'])}, {_sql_int_or_null(unlock['source_quest_id'])}, "
        f"{_sql_string(unlock['grant_method'])}, {_sql_bool(unlock['bot_eligible'])}) "
        "ON DUPLICATE KEY UPDATE "
        "SourceArcKey = VALUES(SourceArcKey), SourceQuestID = VALUES(SourceQuestID), "
        "GrantMethod = VALUES(GrantMethod), BotEligible = VALUES(BotEligible)"
    )


def _reward_delete_sql(reward: dict[str, Any]) -> str:
    return (
        "DELETE FROM wm_character_reward_instance "
        f"WHERE CharacterGUID = {reward['character_guid']} "
        f"AND RewardKind = {_sql_string(reward['reward_kind'])} "
        f"AND TemplateID = {reward['template_id']} "
        f"AND COALESCE(SourceArcKey, '') = {_sql_string(reward['source_arc_key'] or '')} "
        f"AND COALESCE(SourceQuestID, 0) = {int(reward['source_quest_id'] or 0)}"
    )


def _reward_insert_sql(reward: dict[str, Any]) -> str:
    return (
        "INSERT INTO wm_character_reward_instance "
        "(CharacterGUID, RewardKind, TemplateID, SourceArcKey, SourceQuestID, IsEquippedGate) VALUES "
        f"({reward['character_guid']}, {_sql_string(reward['reward_kind'])}, {reward['template_id']}, "
        f"{_sql_string_or_null(reward['source_arc_key'])}, {_sql_int_or_null(reward['source_quest_id'])}, "
        f"{_sql_bool(reward['is_equipped_gate'])})"
    )


def _steering_upsert_sql(note: dict[str, Any]) -> str:
    return (
        "INSERT INTO wm_character_conversation_steering "
        "(CharacterGUID, SteeringKey, SteeringKind, Body, Priority, Source, IsActive, MetadataJSON) VALUES "
        f"({note['character_guid']}, {_sql_string(note['steering_key'])}, {_sql_string(note['steering_kind'])}, "
        f"{_sql_string(note['body'])}, {int(note['priority'])}, {_sql_string(note['source'])}, "
        f"{_sql_bool(note['is_active'])}, {_json_or_null(note['metadata'])}) "
        "ON DUPLICATE KEY UPDATE "
        "SteeringKind = VALUES(SteeringKind), Body = VALUES(Body), Priority = VALUES(Priority), "
        "Source = VALUES(Source), IsActive = VALUES(IsActive), MetadataJSON = VALUES(MetadataJSON)"
    )


def _prompt_insert_sql(prompt: dict[str, Any]) -> str:
    return (
        "INSERT INTO wm_character_prompt_queue (CharacterGUID, PromptKind, Body, IsConsumed) "
        f"SELECT {prompt['character_guid']}, {_sql_string(prompt['prompt_kind'])}, {_sql_string(prompt['body'])}, 0 "
        "FROM DUAL WHERE NOT EXISTS ("
        "SELECT 1 FROM wm_character_prompt_queue "
        f"WHERE CharacterGUID = {prompt['character_guid']} "
        f"AND PromptKind = {_sql_string(prompt['prompt_kind'])} "
        f"AND Body = {_sql_string(prompt['body'])} AND IsConsumed = 0)"
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m wm.character.journey")
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect", help="Inspect one character's WM journey spine.")
    inspect_parser.add_argument("--player-guid", type=int, required=True)
    inspect_parser.add_argument("--summary", action="store_true")
    inspect_parser.add_argument("--output-json", type=Path)

    apply_parser = subparsers.add_parser("apply", help="Validate or apply a strict journey seed/update plan.")
    apply_parser.add_argument("--plan-json", type=Path, required=True)
    apply_parser.add_argument("--mode", choices=["dry-run", "apply"], default="dry-run")
    apply_parser.add_argument("--summary", action="store_true")
    apply_parser.add_argument("--output-json", type=Path)
    apply_parser.add_argument("--include-sql", action="store_true", help="Include generated SQL in JSON output.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "inspect":
        settings = Settings.from_env()
        client = MysqlCliClient()
        store = CharacterJourneyStore(client=client, settings=settings)
        bundle = store.inspect(player_guid=int(args.player_guid))
        payload = inspect_journey_payload(player_guid=int(args.player_guid), bundle=bundle)
        _emit_payload(payload=payload, output_json=args.output_json, summary=args.summary, renderer=render_inspect_summary)
        return 0
    if args.command == "apply":
        try:
            plan = load_journey_plan(args.plan_json)
            if args.mode == "dry-run":
                normalized = validate_journey_plan(plan)
                result = JourneyApplyResult(
                    player_guid=int(normalized["player_guid"]),
                    mode="dry-run",
                    ok=True,
                    status="WORKING",
                    mutated=False,
                    operations=build_journey_operations(normalized),
                )
            else:
                settings = Settings.from_env()
                client = MysqlCliClient()
                store = CharacterJourneyStore(client=client, settings=settings)
                result = store.apply_plan(plan=plan, mode=str(args.mode))
            payload = result.to_dict(include_sql=bool(args.include_sql))
            exit_code = 0 if result.ok else 1
        except JourneyPlanError as exc:
            payload = {
                "schema_version": JOURNEY_PLAN_SCHEMA_VERSION,
                "player_guid": None,
                "mode": str(args.mode),
                "ok": False,
                "status": "BROKEN",
                "mutated": False,
                "operation_count": 0,
                "operations": [],
                "error": str(exc),
            }
            exit_code = 2
        _emit_payload(payload=payload, output_json=args.output_json, summary=args.summary, renderer=render_apply_summary)
        return exit_code
    return 1


def _emit_payload(*, payload: dict[str, Any], output_json: Path | None, summary: bool, renderer) -> None:
    raw = json.dumps(payload, indent=2, ensure_ascii=False)
    if output_json is not None:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(raw, encoding="utf-8")
    if summary:
        print(renderer(payload))
        if output_json is not None:
            print("")
            print(f"output_json: {output_json}")
    else:
        print(raw)


def _reject_disallowed_keys(value: Any, *, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            key_text = str(key)
            if key_text.lower() in DISALLOWED_PLAN_KEYS:
                raise JourneyPlanError(f"Unsupported mutation field {path}.{key_text}")
            _reject_disallowed_keys(nested, path=f"{path}.{key_text}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _reject_disallowed_keys(nested, path=f"{path}[{index}]")


def _reject_unknown(raw: dict[str, Any], allowed: set[str], label: str) -> None:
    unknown = sorted(set(raw) - allowed)
    if unknown:
        raise JourneyPlanError(f"Unsupported {label} field(s): {', '.join(unknown)}")


def _list_field(plan: dict[str, Any], key: str) -> list[Any]:
    value = plan.get(key, [])
    if value is None:
        return []
    if not isinstance(value, list):
        raise JourneyPlanError(f"{key} must be an array.")
    return value


def _required_text(value: Any, label: str) -> str:
    text = _optional_text(value)
    if text is None:
        raise JourneyPlanError(f"{label} is required.")
    return text


def _text_or_default(value: Any, default: str) -> str:
    return _optional_text(value) or default


def _optional_text(value: Any) -> str | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    return text or None


def _positive_int(value: Any, label: str) -> int:
    parsed = _optional_int(value, label)
    if parsed is None or parsed <= 0:
        raise JourneyPlanError(f"{label} must be a positive integer.")
    return parsed


def _optional_int(value: Any, label: str) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise JourneyPlanError(f"{label} must be an integer.") from exc


def _bool(value: Any, *, default: bool) -> bool:
    if value in (None, ""):
        return bool(default)
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    raise JourneyPlanError(f"Invalid boolean value: {value}")


def _string_list(value: Any, label: str) -> list[str]:
    if value in (None, ""):
        return []
    if not isinstance(value, list):
        raise JourneyPlanError(f"{label} must be an array.")
    return [str(item) for item in value if str(item).strip()]


def _sql_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("'", "''")
    return f"'{escaped}'"


def _sql_string_or_null(value: str | None) -> str:
    if value in (None, ""):
        return "NULL"
    return _sql_string(str(value))


def _sql_int_or_null(value: int | None) -> str:
    if value is None:
        return "NULL"
    return str(int(value))


def _sql_bool(value: bool) -> str:
    return "1" if value else "0"


def _json_or_null(value: Any) -> str:
    if value in (None, ""):
        return "NULL"
    return _sql_string(json.dumps(value, ensure_ascii=False, sort_keys=True))


def _safe_error(exc: Exception) -> str:
    message = str(exc).strip()
    if not message:
        return type(exc).__name__
    return f"{type(exc).__name__}: {message}"


if __name__ == "__main__":
    raise SystemExit(main())
