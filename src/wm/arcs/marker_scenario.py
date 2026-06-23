from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any

from wm.arcs.factory import SCENARIO_VERSION
from wm.config import Settings
from wm.db.mysql_cli import MysqlCliClient
from wm.db.mysql_cli import MysqlCliError
from wm.living.runtime import resolve_marker_session
from wm.panel.state import PanelState
from wm.reactive.turn_in_selector import ZoneQuestTurnInCandidate, ZoneQuestTurnInSelector
from wm.sources.native_bridge.player_marker import DEFAULT_MARKER_SPELL_ID
from wm.targets.resolver import decode_creature_type, decode_faction_label, decode_rank, decode_unit_class


DEFAULT_ARC_KEY = "marker_target_compiler_reward_panel_v1"
DEFAULT_REWARD_ITEM_DRAFT = "control/examples/items/night_watchers_lens.json"
DEFAULT_REWARD_ITEM_ENTRY = 910006
DEFAULT_REWARD_ITEM_NAME = "Night Watcher's Lens"


@dataclass(frozen=True, slots=True)
class CharacterFacts:
    guid: int
    name: str
    race: int
    character_class: int
    level: int
    online: bool
    map_id: int | None
    zone_id: int | None
    area_id: int | None = None
    zone_name: str | None = None
    area_name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class TargetCandidate:
    entry: int
    name: str
    level_min: int
    level_max: int
    faction_id: int
    faction_label: str | None
    mechanical_type: str
    rank: str
    unit_class: str
    spawn_count: int
    map_id: int | None
    zone_id: int | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class MarkerScenarioSelection:
    character: CharacterFacts
    target: TargetCandidate
    turn_in: ZoneQuestTurnInCandidate
    marker_session: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "character": self.character.to_dict(),
            "target": self.target.to_dict(),
            "turn_in": asdict(self.turn_in),
            "marker_session": self.marker_session,
        }


class MarkerScenarioError(RuntimeError):
    pass


class MarkerArcScenarioGenerator:
    def __init__(self, *, client: MysqlCliClient, settings: Settings, panel_state: PanelState | None = None) -> None:
        self.client = client
        self.settings = settings
        self.panel_state = panel_state or PanelState()

    def generate(
        self,
        *,
        player_guid: int | None = None,
        arc_key: str = DEFAULT_ARC_KEY,
        max_marker_age_seconds: int = 900,
    ) -> dict[str, Any]:
        session = self._resolve_session(player_guid=player_guid, max_age_seconds=max_marker_age_seconds)
        resolved_guid = int(player_guid if player_guid is not None else session["character_guid"])
        character = self._load_character_facts(player_guid=resolved_guid)
        if not character.online:
            raise MarkerScenarioError(f"player {resolved_guid} is not online")
        if character.zone_id is None or character.zone_id <= 0:
            raise MarkerScenarioError(f"player {resolved_guid} has no usable zone_id for scenario selection")

        target = self._select_target(character=character)
        turn_in = ZoneQuestTurnInSelector(client=self.client, settings=self.settings).select(
            player_guid=character.guid,
            zone_id=character.zone_id,
        )
        if turn_in is None:
            raise MarkerScenarioError(f"no faction-compatible questgiver found for player {character.guid} in zone {character.zone_id}")

        selection = MarkerScenarioSelection(character=character, target=target, turn_in=turn_in, marker_session=session)
        return build_marker_arc_scenario(selection=selection, arc_key=arc_key)

    def _resolve_session(self, *, player_guid: int | None, max_age_seconds: int) -> dict[str, Any] | None:
        if player_guid is not None:
            return None
        session = self.panel_state.load_session()
        try:
            return resolve_marker_session(session, max_age_seconds=max_age_seconds)
        except ValueError as exc:
            raise MarkerScenarioError(str(exc)) from exc

    def _load_character_facts(self, *, player_guid: int) -> CharacterFacts:
        char_rows = self.client.query(
            host=self.settings.char_db_host,
            port=self.settings.char_db_port,
            user=self.settings.char_db_user,
            password=self.settings.char_db_password,
            database=self.settings.char_db_name,
            sql=(
                "SELECT guid, name, race, class, level, map, zone, online "
                "FROM characters "
                f"WHERE guid = {int(player_guid)} LIMIT 1"
            ),
        )
        if not char_rows:
            raise MarkerScenarioError(f"character {player_guid} was not found")
        char = char_rows[0]
        presence = self._load_presence(player_guid=player_guid)
        return CharacterFacts(
            guid=int(char.get("guid") or player_guid),
            name=str(char.get("name") or f"player-{player_guid}"),
            race=_int_or_zero(char.get("race")),
            character_class=_int_or_zero(char.get("class")),
            level=max(1, _int_or_zero((presence or {}).get("Level")) or _int_or_zero(char.get("level"))),
            online=_truthy((presence or {}).get("Online")) or _truthy(char.get("online")),
            map_id=_int_or_none((presence or {}).get("MapID")) or _int_or_none(char.get("map")),
            zone_id=_int_or_none((presence or {}).get("ZoneID")) or _int_or_none(char.get("zone")),
            area_id=_int_or_none((presence or {}).get("AreaID")),
            zone_name=_text_or_none((presence or {}).get("ZoneName")),
            area_name=_text_or_none((presence or {}).get("AreaName")),
        )

    def _load_presence(self, *, player_guid: int) -> dict[str, Any] | None:
        try:
            rows = self.client.query(
                host=self.settings.world_db_host,
                port=self.settings.world_db_port,
                user=self.settings.world_db_user,
                password=self.settings.world_db_password,
                database=self.settings.world_db_name,
                sql=(
                    "SELECT PlayerGUID, Online, MapID, ZoneID, AreaID, ZoneName, AreaName, Level "
                    "FROM wm_bridge_player_presence "
                    f"WHERE PlayerGUID = {int(player_guid)} LIMIT 1"
                ),
            )
        except Exception:
            return None
        return rows[0] if rows else None

    def _select_target(self, *, character: CharacterFacts) -> TargetCandidate:
        level_floor = max(1, character.level - 5)
        level_ceiling = max(level_floor, character.level + 3)
        map_filter = f"AND c.map = {int(character.map_id)}" if character.map_id is not None else ""
        rows = self.client.query(
            host=self.settings.world_db_host,
            port=self.settings.world_db_port,
            user=self.settings.world_db_user,
            password=self.settings.world_db_password,
            database=self.settings.world_db_name,
            sql=f"""
SELECT
    ct.entry,
    ct.name,
    ct.minlevel,
    ct.maxlevel,
    ct.faction,
    ct.type,
    ct.rank,
    ct.unit_class,
    COUNT(DISTINCT c.guid) AS spawn_count,
    MIN(c.map) AS map_id,
    MIN(c.zoneId) AS zone_id
FROM creature c
JOIN creature_template ct ON ct.entry = c.id1
WHERE c.zoneId = {int(character.zone_id)}
{map_filter}
  AND ct.maxlevel BETWEEN {level_floor} AND {level_ceiling}
  AND ct.rank IN (0, 4)
  AND ct.type NOT IN (8, 11, 12, 13)
  AND COALESCE(ct.npcflag, 0) = 0
  AND COALESCE(ct.faction, 0) NOT IN (0, 35)
GROUP BY ct.entry, ct.name, ct.minlevel, ct.maxlevel, ct.faction, ct.type, ct.rank, ct.unit_class
HAVING COUNT(DISTINCT c.guid) >= 2
ORDER BY
    ABS(((ct.minlevel + ct.maxlevel) / 2) - {int(character.level)}) ASC,
    COUNT(DISTINCT c.guid) DESC,
    ct.maxlevel DESC,
    ct.entry ASC
LIMIT 20
""".strip(),
        )
        if not rows:
            raise MarkerScenarioError(
                f"no zone-compatible target found for player {character.guid} "
                f"(zone={character.zone_id}, map={character.map_id}, level={character.level})"
            )
        return _target_from_row(rows[0])


def build_marker_arc_scenario(*, selection: MarkerScenarioSelection, arc_key: str = DEFAULT_ARC_KEY) -> dict[str, Any]:
    character = selection.character
    target = selection.target
    turn_in = selection.turn_in
    kill_count = _kill_count_for_target(target=target, character=character)
    place = character.area_name or character.zone_name or f"zone {character.zone_id}"
    title = "The Watcher's Proof"
    objective = f"Slay {kill_count} {target.name}."
    return {
        "schema_version": SCENARIO_VERSION,
        "arc_key": arc_key,
        "player_guid": character.guid,
        "title": title,
        "summary": (
            f"{character.name} completes a compiler-generated proof in {place} "
            f"against {target.name} and receives a visible managed reward."
        ),
        "beats": [
            {
                "beat_key": "watcher_calls",
                "label": "The Watcher Calls",
                "kind": "setup",
                "description": f"The marker-selected target is locked to {character.name} ({character.guid}).",
            },
            {
                "beat_key": "local_threat_falls",
                "label": "Local Threat Falls",
                "kind": "quest_objective",
                "description": f"Defeat a level-compatible local target in {place}: {target.name}.",
            },
            {
                "beat_key": "reward_verified",
                "label": "Reward Verified",
                "kind": "reward",
                "description": "The client reward panel and journey provenance confirm compiler output.",
            },
        ],
        "target": {
            "creature_entry": target.entry,
            "target_name": target.name,
            "kill_count": kill_count,
        },
        "turn_in_npc": {
            "entry": turn_in.entry,
            "name": turn_in.name,
        },
        "quest": {
            "title": title,
            "quest_level": max(1, target.level_max),
            "min_level": max(1, min(character.level, target.level_min)),
            "grant_mode": "npc_start",
            "quest_description": (
                f"The watcher has marked a bounded disturbance near {place}. "
                f"Break the pressure from {target.name}, then return to {turn_in.name}."
            ),
            "objective_text": objective,
            "request_items_text": f"Complete the proof against {target.name}, then report back.",
            "offer_reward_text": "The proof is recorded. Take this token and carry the mark forward.",
        },
        "reward": {
            "kind": "managed_item",
            "item_draft_path": DEFAULT_REWARD_ITEM_DRAFT,
            "item_entry": DEFAULT_REWARD_ITEM_ENTRY,
            "item_name": DEFAULT_REWARD_ITEM_NAME,
            "item_count": 1,
            "reward_item_mode": "fixed",
            "is_equipped_gate": True,
        },
        "journey_updates": {
            "stage_key": "compiler_reward_panel_proven",
            "branch_key": "marker_target_proof",
            "conversation_steering": [],
            "prompt_queue": [],
        },
        "runtime_sync": {"mode": "auto", "item_commands": [], "quest_commands": []},
        "notes": [
            "Generated from the runtime-selected marker target; do not substitute a fixture GUID.",
            f"marker_spell_id:{DEFAULT_MARKER_SPELL_ID}",
            f"selected_target:{target.entry}:{target.name}:spawns={target.spawn_count}:zone={target.zone_id}",
            f"selected_turn_in:{turn_in.entry}:{turn_in.name}:zone={character.zone_id}",
            "Quest rows must be generated by wm.quests.compiler through wm.arcs.factory; do not hand-clone quest rows.",
        ],
    }


def _target_from_row(row: dict[str, Any]) -> TargetCandidate:
    faction_id = _int_or_zero(row.get("faction"))
    type_id = _int_or_zero(row.get("type"))
    rank_id = _int_or_zero(row.get("rank"))
    unit_class = _int_or_zero(row.get("unit_class"))
    return TargetCandidate(
        entry=int(row["entry"]),
        name=str(row.get("name") or row["entry"]),
        level_min=max(1, _int_or_zero(row.get("minlevel"))),
        level_max=max(1, _int_or_zero(row.get("maxlevel"))),
        faction_id=faction_id,
        faction_label=decode_faction_label(faction_id),
        mechanical_type=decode_creature_type(type_id),
        rank=decode_rank(rank_id),
        unit_class=decode_unit_class(unit_class),
        spawn_count=max(0, _int_or_zero(row.get("spawn_count"))),
        map_id=_int_or_none(row.get("map_id")),
        zone_id=_int_or_none(row.get("zone_id")),
    )


def _kill_count_for_target(*, target: TargetCandidate, character: CharacterFacts) -> int:
    del character
    if target.spawn_count >= 8:
        return 4
    return max(2, min(3, target.spawn_count))


def _settings_for_db_profile(settings: Settings, profile: str) -> Settings:
    if profile == "env":
        return settings
    if profile == "bridgelab":
        from wm.doctor import settings_for_profile

        return settings_for_profile(settings, "bridgelab")
    raise ValueError(f"unknown marker scenario DB profile: {profile}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m wm.arcs.marker_scenario")
    parser.add_argument("--player-guid", type=int, help="Optional explicit runtime target. If omitted, the active marker session is required.")
    parser.add_argument("--arc-key", default=DEFAULT_ARC_KEY)
    parser.add_argument("--max-marker-age-seconds", type=int, default=900)
    parser.add_argument("--db-profile", choices=("env", "bridgelab"), default="env")
    parser.add_argument("--output-json", type=Path, default=Path(".wm-bootstrap/state/arcs/marker_target_compiler_reward_panel_v1.json"))
    parser.add_argument("--summary", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    settings = _settings_for_db_profile(Settings.from_env(), args.db_profile)
    try:
        payload = MarkerArcScenarioGenerator(client=MysqlCliClient(), settings=settings).generate(
            player_guid=args.player_guid,
            arc_key=args.arc_key,
            max_marker_age_seconds=args.max_marker_age_seconds,
        )
    except (MarkerScenarioError, MysqlCliError, ValueError) as exc:
        print(f"marker_arc_scenario error={exc}")
        return 1
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    if args.summary:
        print(
            "marker_arc_scenario "
            f"player_guid={payload.get('player_guid')} "
            f"target={payload.get('target', {}).get('creature_entry')} "
            f"turn_in={payload.get('turn_in_npc', {}).get('entry')} "
            f"output_json={args.output_json}"
        )
    else:
        print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


def _int_or_none(value: object) -> int | None:
    if value in (None, "", "NULL"):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _int_or_zero(value: object) -> int:
    return _int_or_none(value) or 0


def _truthy(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if value in (None, "", "0", 0, "false", "False"):
        return False
    return True


def _text_or_none(value: object) -> str | None:
    if value in (None, "", "NULL"):
        return None
    text = str(value).strip()
    return text or None


if __name__ == "__main__":
    raise SystemExit(main())
