from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
from typing import Any, Protocol

from wm.character.reader import CharacterStateBundle, load_character_state
from wm.config import Settings
from wm.control.registry import ControlRegistry
from wm.context.models import ContextPack
from wm.db.mysql_cli import MysqlCliClient, MysqlCliError
from wm.events.models import WMEvent
from wm.events.store import EventStore
from wm.journal.reader import SubjectJournalBundle, SubjectJournalReader
from wm.reactive.models import ReactiveQuestRule
from wm.reactive.store import ReactiveQuestStore
from wm.subjects.resolver import build_subject_card_from_profile
from wm.targets.resolver import LookupStore, TargetResolver
from wm.targets.runtime_resolver import RuntimeTargetResolver


class TargetProfileResolver(Protocol):
    def resolve_creature_entry(self, entry: int) -> Any | None:
        ...


class SubjectJournalLoader(Protocol):
    def load_for_creature(
        self,
        *,
        player_guid: int,
        creature_entry: int,
        resolved_subject_card: Any | None = None,
    ) -> SubjectJournalBundle:
        ...


class CharacterStateLoader(Protocol):
    def load(self, *, character_guid: int) -> CharacterStateBundle:
        ...


class ContextEventStore(Protocol):
    def list_recent_events(
        self,
        *,
        event_class: str | None = None,
        player_guid: int | None = None,
        limit: int = 20,
        newest_first: bool = True,
    ) -> list[WMEvent]:
        ...

    def list_subject_events(
        self,
        *,
        player_guid: int,
        subject_type: str,
        subject_entry: int,
        event_type: str | None = None,
        event_class: str = "observed",
        limit: int = 200,
        newest_first: bool = False,
    ) -> list[WMEvent]:
        ...


class ReactiveRuntimeStore(Protocol):
    def list_active_rules(
        self,
        *,
        subject_type: str | None = None,
        subject_entry: int | None = None,
        trigger_event_type: str | None = None,
        player_guid: int | None = None,
    ) -> list[ReactiveQuestRule]:
        ...

    def get_player_quest_runtime_state(self, *, player_guid: int, quest_id: int) -> Any | None:
        ...

    def fetch_character_quest_status(self, *, player_guid: int, quest_id: int) -> str:
        ...


class NativeContextSnapshotLoader(Protocol):
    def load_latest(self, *, player_guid: int) -> dict[str, Any] | None:
        ...


class ContextPackBuildError(RuntimeError):
    """Raised when the requested context pack cannot be built deterministically."""


class DbCharacterStateLoader:
    def __init__(self, *, client: MysqlCliClient, settings: Settings) -> None:
        self.client = client
        self.settings = settings

    def load(self, *, character_guid: int) -> CharacterStateBundle:
        return load_character_state(
            client=self.client,
            settings=self.settings,
            character_guid=int(character_guid),
        )


class LatestNativeContextSnapshotLoader:
    def __init__(self, *, client: MysqlCliClient, settings: Settings) -> None:
        self.client = client
        self.settings = settings

    def load_latest(self, *, player_guid: int) -> dict[str, Any] | None:
        rows = self.client.query(
            host=self.settings.world_db_host,
            port=self.settings.world_db_port,
            user=self.settings.world_db_user,
            password=self.settings.world_db_password,
            database=self.settings.world_db_name,
            sql=(
                "SELECT SnapshotID, RequestID, OccurredAt, PlayerGUID, ContextKind, Radius, MapID, ZoneID, AreaID, Source, PayloadJSON "
                "FROM wm_bridge_context_snapshot "
                f"WHERE PlayerGUID = {int(player_guid)} "
                "ORDER BY SnapshotID DESC LIMIT 1"
            ),
        )
        if not rows:
            return None
        row = rows[0]
        return {
            "snapshot_id": _int_or_none(row.get("SnapshotID")),
            "request_id": _int_or_none(row.get("RequestID")),
            "occurred_at": _str_or_none(row.get("OccurredAt")),
            "player_guid": _int_or_none(row.get("PlayerGUID")),
            "context_kind": _str_or_none(row.get("ContextKind")),
            "radius": _int_or_none(row.get("Radius")),
            "map_id": _int_or_none(row.get("MapID")),
            "zone_id": _int_or_none(row.get("ZoneID")),
            "area_id": _int_or_none(row.get("AreaID")),
            "source": _str_or_none(row.get("Source")),
            "payload": _parse_json_value(row.get("PayloadJSON")),
        }


class ContextPackBuilder:
    def __init__(
        self,
        *,
        target_resolver: TargetProfileResolver,
        journal_loader: SubjectJournalLoader,
        character_loader: CharacterStateLoader | None = None,
        event_store: ContextEventStore | None = None,
        reactive_store: ReactiveRuntimeStore | None = None,
        control_registry: ControlRegistry | None = None,
        native_snapshot_loader: NativeContextSnapshotLoader | None = None,
        include_native_snapshot: bool = True,
    ) -> None:
        self.target_resolver = target_resolver
        self.journal_loader = journal_loader
        self.character_loader = character_loader
        self.event_store = event_store
        self.reactive_store = reactive_store
        self.control_registry = control_registry
        self.native_snapshot_loader = native_snapshot_loader
        self.include_native_snapshot = include_native_snapshot

    def build_for_target(
        self,
        *,
        player_guid: int,
        target_entry: int,
        source_event: WMEvent | None = None,
        recent_event_limit: int = 10,
        related_event_limit: int = 20,
    ) -> ContextPack:
        profile = self.target_resolver.resolve_creature_entry(int(target_entry))
        if profile is None:
            raise ContextPackBuildError(f"Target creature entry {int(target_entry)} could not be resolved.")

        notes: list[str] = []
        subject_card = build_subject_card_from_profile(profile)
        journal = self.journal_loader.load_for_creature(
            player_guid=int(player_guid),
            creature_entry=int(target_entry),
            resolved_subject_card=subject_card,
        )
        notes.extend(_pack_notes(journal=journal))

        character_state = _optional(
            notes=notes,
            label="character_state",
            callback=lambda: self._load_character_state(player_guid=int(player_guid)),
        )
        recent_events = _optional_list(
            notes=notes,
            label="recent_events",
            callback=lambda: self._load_recent_events(player_guid=int(player_guid), limit=recent_event_limit),
        )
        related_events = _optional_list(
            notes=notes,
            label="related_subject_events",
            callback=lambda: self._load_related_subject_events(
                player_guid=int(player_guid),
                target_entry=int(target_entry),
                limit=related_event_limit,
            ),
        )
        quest_runtime = _optional(
            notes=notes,
            label="quest_runtime",
            callback=lambda: self._load_quest_runtime(player_guid=int(player_guid), target_entry=int(target_entry)),
        ) or {"active_rules": [], "active_rule_count": 0}
        eligible_recipes, policy = self._load_control_context(notes=notes, source_event=source_event)
        native_context_snapshot = None
        if self.include_native_snapshot:
            native_context_snapshot = _optional(
                notes=notes,
                label="native_context_snapshot",
                callback=lambda: self._load_native_context_snapshot(player_guid=int(player_guid)),
            )
            if native_context_snapshot is None and self.native_snapshot_loader is not None:
                notes.append("native_context_snapshot: no existing snapshot row was loaded.")

        generation_input = _build_generation_input(
            player_guid=int(player_guid),
            character_state=character_state,
            source_event=source_event,
            target_profile=profile.to_dict(),
            subject_card=subject_card.to_dict(),
            journal=journal,
            quest_runtime=quest_runtime,
            eligible_recipes=eligible_recipes,
        )

        return ContextPack(
            pack_id=_pack_id(player_guid=int(player_guid), target_entry=int(target_entry), source_event=source_event),
            player_guid=int(player_guid),
            target_entry=int(target_entry),
            source_event=source_event.to_dict() if source_event is not None else None,
            character_state=character_state,
            target_profile=profile.to_dict(),
            subject_card=subject_card.to_dict(),
            journal_summary=_journal_summary_dict(journal),
            journal_status=journal.status,
            journal_source_flags=list(journal.source_flags),
            recent_events=recent_events,
            related_subject_events=related_events,
            quest_runtime=quest_runtime,
            eligible_recipes=eligible_recipes,
            policy=policy,
            native_context_snapshot=native_context_snapshot,
            generation_input=generation_input,
            status=_pack_status(journal=journal, notes=notes),
            notes=notes,
        )

    def _load_character_state(self, *, player_guid: int) -> dict[str, Any] | None:
        if self.character_loader is None:
            raise RuntimeError("character loader is not configured")
        bundle = self.character_loader.load(character_guid=int(player_guid))
        payload = asdict(bundle)
        if payload.get("profile") is None:
            payload["status"] = "PARTIAL"
            payload["notes"] = payload.get("notes") or ["No wm_character_profile row was loaded."]
        else:
            payload["status"] = payload.get("status") or "WORKING"
            payload["notes"] = payload.get("notes") or []
        return payload

    def _load_recent_events(self, *, player_guid: int, limit: int) -> list[dict[str, Any]]:
        if self.event_store is None:
            raise RuntimeError("event store is not configured")
        return [
            event.to_dict()
            for event in self.event_store.list_recent_events(
                player_guid=int(player_guid),
                limit=max(0, int(limit)),
                newest_first=True,
            )
        ]

    def _load_related_subject_events(self, *, player_guid: int, target_entry: int, limit: int) -> list[dict[str, Any]]:
        if self.event_store is None:
            raise RuntimeError("event store is not configured")
        return [
            event.to_dict()
            for event in self.event_store.list_subject_events(
                player_guid=int(player_guid),
                subject_type="creature",
                subject_entry=int(target_entry),
                limit=max(0, int(limit)),
                newest_first=True,
            )
        ]

    def _load_quest_runtime(self, *, player_guid: int, target_entry: int) -> dict[str, Any]:
        if self.reactive_store is None:
            raise RuntimeError("reactive store is not configured")
        rules = self.reactive_store.list_active_rules(
            subject_type="creature",
            subject_entry=int(target_entry),
            player_guid=int(player_guid),
        )
        active_rules: list[dict[str, Any]] = []
        for rule in rules:
            runtime_state = self.reactive_store.get_player_quest_runtime_state(
                player_guid=int(player_guid),
                quest_id=int(rule.quest_id),
            )
            character_status = self.reactive_store.fetch_character_quest_status(
                player_guid=int(player_guid),
                quest_id=int(rule.quest_id),
            )
            active_rules.append(
                {
                    "rule": rule.to_dict(),
                    "runtime_state": runtime_state.to_dict() if runtime_state is not None else None,
                    "character_quest_status": character_status,
                }
            )
        return {
            "active_rule_count": len(active_rules),
            "active_rules": active_rules,
        }

    def _load_control_context(
        self,
        *,
        notes: list[str],
        source_event: WMEvent | None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
        if self.control_registry is None:
            notes.append("control: registry is not configured.")
            return [], None
        try:
            event_type = source_event.event_type if source_event is not None else None
            recipes = (
                self.control_registry.eligible_recipes_for_event_type(event_type)
                if event_type not in (None, "")
                else []
            )
            policy_id = str(self.control_registry.registry.get("default_policy", "direct_apply"))
            policy = {
                "id": policy_id,
                "registry_hash": self.control_registry.registry_hash,
                "schema_hash": self.control_registry.schema_hash,
                "policy": self.control_registry.default_policy,
            }
            return recipes, policy
        except Exception as exc:
            notes.append(f"control: failed to load registry context: {_safe_error(exc)}")
            return [], None

    def _load_native_context_snapshot(self, *, player_guid: int) -> dict[str, Any] | None:
        if self.native_snapshot_loader is None:
            raise RuntimeError("native context snapshot loader is not configured")
        return self.native_snapshot_loader.load_latest(player_guid=int(player_guid))


def _pack_status(*, journal: SubjectJournalBundle, notes: list[str]) -> str:
    if journal.status == "UNKNOWN":
        return "UNKNOWN"
    if notes or journal.status == "PARTIAL":
        return "PARTIAL"
    return "WORKING"


def _pack_notes(*, journal: SubjectJournalBundle) -> list[str]:
    notes: list[str] = []
    if "subject_definition" not in journal.source_flags:
        notes.append("journal: no active wm_subject_definition row was loaded; subject identity came from resolver/enrichment fallback.")
    if "player_subject_journal" not in journal.source_flags:
        notes.append("journal: no wm_player_subject_journal row was loaded; counters defaulted to zero.")
    return notes


def _journal_summary_dict(journal: SubjectJournalBundle) -> dict[str, Any] | None:
    if journal.summary is None:
        return None
    return {
        "title": journal.summary.title,
        "description": journal.summary.description,
        "history_lines": journal.summary.history_lines,
        "raw": journal.summary.raw,
    }


def _build_generation_input(
    *,
    player_guid: int,
    character_state: dict[str, Any] | None,
    source_event: WMEvent | None,
    target_profile: dict[str, Any],
    subject_card: dict[str, Any],
    journal: SubjectJournalBundle,
    quest_runtime: dict[str, Any],
    eligible_recipes: list[dict[str, Any]],
) -> dict[str, Any]:
    character_profile = (character_state or {}).get("profile") or {}
    arc_states = (character_state or {}).get("arc_states") or []
    unlocks = (character_state or {}).get("unlocks") or []
    rewards = (character_state or {}).get("rewards") or []
    conversation_steering = (character_state or {}).get("conversation_steering") or []
    counters = asdict(journal.counters) if journal.counters is not None else {}
    active_rules = quest_runtime.get("active_rules") or []
    quest_states = sorted(
        {
            str((item.get("runtime_state") or {}).get("current_state") or item.get("character_quest_status") or "")
            for item in active_rules
            if isinstance(item, dict)
        }
        - {""}
    )
    return {
        "player": {
            "guid": int(player_guid),
            "name": character_profile.get("character_name"),
            "persona": character_profile.get("wm_persona"),
            "tone": character_profile.get("tone"),
        },
        "trigger": {
            "event_type": source_event.event_type if source_event is not None else None,
            "event_class": source_event.event_class if source_event is not None else None,
            "source": source_event.source if source_event is not None else None,
            "source_event_key": source_event.source_event_key if source_event is not None else None,
        },
        "target": {
            "entry": target_profile.get("entry"),
            "name": target_profile.get("name") or subject_card.get("display_name"),
            "mechanical_type": target_profile.get("mechanical_type"),
            "family": target_profile.get("family"),
            "faction_id": target_profile.get("faction_id"),
            "faction_label": target_profile.get("faction_label"),
            "role_tags": subject_card.get("role_tags") or [],
            "group_keys": subject_card.get("group_keys") or [],
            "area_tags": subject_card.get("area_tags") or [],
        },
        "history": {
            "kill_count": counters.get("kill_count", 0),
            "talk_count": counters.get("talk_count", 0),
            "quest_complete_count": counters.get("quest_complete_count", 0),
            "last_quest_title": counters.get("last_quest_title"),
            "summary_lines": journal.summary.history_lines if journal.summary is not None else [],
        },
        "journey": {
            "active_arc_keys": [
                str(arc.get("arc_key"))
                for arc in arc_states
                if isinstance(arc, dict) and str(arc.get("status") or "active") == "active" and arc.get("arc_key")
            ],
            "unlock_refs": [
                f"{unlock.get('unlock_kind')}:{unlock.get('unlock_id')}"
                for unlock in unlocks
                if isinstance(unlock, dict) and unlock.get("unlock_kind") and unlock.get("unlock_id")
            ],
            "reward_refs": [
                f"{reward.get('reward_kind')}:{reward.get('template_id')}"
                for reward in rewards
                if isinstance(reward, dict) and reward.get("reward_kind") and reward.get("template_id")
            ],
            "steering": [
                {
                    "key": note.get("steering_key"),
                    "kind": note.get("steering_kind"),
                    "body": note.get("body"),
                    "priority": note.get("priority", 0),
                }
                for note in conversation_steering
                if isinstance(note, dict) and note.get("body")
            ],
        },
        "quest_runtime": {
            "active_rule_count": int(quest_runtime.get("active_rule_count") or 0),
            "states": quest_states,
        },
        "eligible_recipe_ids": [str(recipe.get("id")) for recipe in eligible_recipes if recipe.get("id") not in (None, "")],
    }


def _optional(*, notes: list[str], label: str, callback) -> Any | None:
    try:
        return callback()
    except Exception as exc:
        notes.append(f"{label}: {_safe_error(exc)}")
        return None


def _optional_list(*, notes: list[str], label: str, callback) -> list[dict[str, Any]]:
    value = _optional(notes=notes, label=label, callback=callback)
    return value if isinstance(value, list) else []


def _pack_id(*, player_guid: int, target_entry: int, source_event: WMEvent | None) -> str:
    event_part = "manual"
    if source_event is not None:
        event_part = f"{source_event.source}:{source_event.source_event_key}"
    return f"context:{int(player_guid)}:creature:{int(target_entry)}:{event_part}"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m wm.context.builder")
    subject_group = parser.add_mutually_exclusive_group(required=True)
    subject_group.add_argument("--target-entry", type=int)
    subject_group.add_argument("--event-id", type=int)
    parser.add_argument("--player-guid", type=int, help="Required with --target-entry; optional override with --event-id.")
    parser.add_argument(
        "--lookup-json",
        type=Path,
        default=Path("data/lookup/creature_template_full.json"),
        help="Static creature lookup JSON used unless --runtime is set.",
    )
    parser.add_argument("--runtime", action="store_true", help="Resolve target profile from the live world DB.")
    parser.add_argument("--recent-event-limit", type=int, default=10)
    parser.add_argument("--related-event-limit", type=int, default=20)
    parser.add_argument("--control-root", type=Path)
    parser.add_argument("--no-native-snapshot", action="store_true")
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--output-json", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        settings = Settings.from_env()
        client = MysqlCliClient()
        source_event = _load_source_event(args=args, client=client, settings=settings)
        player_guid = _resolve_player_guid(args=args, source_event=source_event)
        target_entry = _resolve_target_entry(args=args, source_event=source_event)
        control_root = args.control_root if args.control_root is not None else Path(settings.control_root)
        builder = ContextPackBuilder(
            target_resolver=_build_target_resolver(args=args, client=client, settings=settings),
            journal_loader=SubjectJournalReader(client=client, settings=settings),
            character_loader=DbCharacterStateLoader(client=client, settings=settings),
            event_store=EventStore(client=client, settings=settings),
            reactive_store=ReactiveQuestStore(client=client, settings=settings),
            control_registry=ControlRegistry.load(control_root),
            native_snapshot_loader=LatestNativeContextSnapshotLoader(client=client, settings=settings),
            include_native_snapshot=not bool(args.no_native_snapshot),
        )
        pack = builder.build_for_target(
            player_guid=player_guid,
            target_entry=target_entry,
            source_event=source_event,
            recent_event_limit=args.recent_event_limit,
            related_event_limit=args.related_event_limit,
        )
        payload = pack.to_dict()
        exit_code = 0
    except ContextPackBuildError as exc:
        payload = {
            "schema_version": "wm.context_pack.v1",
            "status": "UNKNOWN",
            "error": str(exc),
            "notes": [str(exc)],
        }
        exit_code = 2
    raw = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.output_json is not None:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(raw, encoding="utf-8")
    if args.summary:
        print(_render_summary(payload))
        if args.output_json is not None:
            print("")
            print(f"output_json: {args.output_json}")
    else:
        print(raw)
    return exit_code


def _load_source_event(*, args: argparse.Namespace, client: MysqlCliClient, settings: Settings) -> WMEvent | None:
    if args.event_id is None:
        return None
    try:
        event = EventStore(client=client, settings=settings).get_event(event_id=int(args.event_id))
    except MysqlCliError as exc:
        raise ContextPackBuildError(f"WM event {int(args.event_id)} could not be loaded: {_safe_error(exc)}") from exc
    if event is None:
        raise ContextPackBuildError(f"WM event {int(args.event_id)} was not found.")
    return event


def _resolve_player_guid(*, args: argparse.Namespace, source_event: WMEvent | None) -> int:
    if args.player_guid is not None:
        return int(args.player_guid)
    if source_event is not None and source_event.player_guid is not None:
        return int(source_event.player_guid)
    raise ContextPackBuildError("--player-guid is required when the source event has no player GUID.")


def _resolve_target_entry(*, args: argparse.Namespace, source_event: WMEvent | None) -> int:
    if args.target_entry is not None:
        return int(args.target_entry)
    if source_event is not None and source_event.subject_type == "creature" and source_event.subject_entry is not None:
        return int(source_event.subject_entry)
    raise ContextPackBuildError("--event-id must point at a creature event or --target-entry must be supplied.")


def _build_target_resolver(
    *,
    args: argparse.Namespace,
    client: MysqlCliClient,
    settings: Settings,
) -> TargetProfileResolver:
    if args.runtime:
        return RuntimeTargetResolver(client=client, settings=settings)
    return TargetResolver(store=LookupStore.from_json(args.lookup_json))


def _render_summary(payload: dict[str, Any]) -> str:
    if payload.get("status") == "UNKNOWN" and payload.get("error"):
        return "\n".join(
            [
                f"status: {payload.get('status')}",
                f"error: {payload.get('error')}",
                f"notes: {len(payload.get('notes') or [])}",
            ]
        )
    subject = payload.get("subject_card") or {}
    generation_input = payload.get("generation_input") or {}
    history = generation_input.get("history") or {}
    quest_runtime = generation_input.get("quest_runtime") or {}
    return "\n".join(
        [
            f"pack: {payload.get('pack_id')}",
            f"status: {payload.get('status')}",
            f"player_guid: {payload.get('player_guid')}",
            f"target: {payload.get('target_entry')} | {subject.get('display_name')}",
            f"trigger_event_type: {(generation_input.get('trigger') or {}).get('event_type')}",
            f"journal_status: {payload.get('journal_status')}",
            f"recent_events: {len(payload.get('recent_events') or [])}",
            f"related_subject_events: {len(payload.get('related_subject_events') or [])}",
            f"history: kills={history.get('kill_count', 0)}, talks={history.get('talk_count', 0)}, quests={history.get('quest_complete_count', 0)}",
            f"quest_runtime: active_rules={quest_runtime.get('active_rule_count', 0)}, states={', '.join(quest_runtime.get('states') or []) or '(none)'}",
            f"eligible_recipes: {', '.join(generation_input.get('eligible_recipe_ids') or []) or '(none)'}",
            f"native_snapshot: {str(bool(payload.get('native_context_snapshot'))).lower()}",
            f"notes: {len(payload.get('notes') or [])}",
        ]
    )


def _safe_error(exc: Exception) -> str:
    message = str(exc).strip()
    if not message:
        return type(exc).__name__
    return f"{type(exc).__name__}: {message}"


def _parse_json_value(value: Any) -> Any:
    if value in (None, ""):
        return None
    try:
        return json.loads(str(value))
    except json.JSONDecodeError:
        return {"raw": str(value)}


def _int_or_none(value: Any) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


def _str_or_none(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


if __name__ == "__main__":
    raise SystemExit(main())
