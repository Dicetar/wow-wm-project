from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from wm.config import Settings
from wm.db.mysql_cli import MysqlCliClient
from wm.quests.generate_bounty import LiveCreatureResolver


def _sql_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


class QuestContextBuilder:
    def __init__(self, *, client: MysqlCliClient, settings: Settings) -> None:
        self.client = client
        self.settings = settings
        self.creature_resolver = LiveCreatureResolver(client=client, settings=settings)
        self._table_cache: dict[str, bool] = {}

    def build(
        self,
        *,
        questgiver_entry: int | None,
        questgiver_name: str | None,
        target_entry: int | None,
        target_name: str | None,
        player_guid: int | None,
        base_kill_count: int,
    ) -> dict[str, Any]:
        questgiver = self.creature_resolver.resolve(entry=questgiver_entry, name=questgiver_name)
        target = self.creature_resolver.resolve(entry=target_entry, name=target_name)

        questgiver_context = self._subject_context(entry=questgiver.entry, player_guid=player_guid)
        target_context = self._subject_context(entry=target.entry, player_guid=player_guid)
        hints = self._build_generation_hints(
            questgiver_profile=questgiver.profile.to_dict(),
            target_profile=target.profile.to_dict(),
            questgiver_context=questgiver_context,
            target_context=target_context,
            base_kill_count=base_kill_count,
        )

        return {
            "player_guid": player_guid,
            "questgiver_profile": questgiver.profile.to_dict(),
            "target_profile": target.profile.to_dict(),
            "questgiver_context": questgiver_context,
            "target_context": target_context,
            "generation_hints": hints,
        }

    def _subject_context(self, *, entry: int, player_guid: int | None) -> dict[str, Any]:
        enrichment = self._subject_enrichment(entry=entry)
        definition = self._subject_definition(entry=entry)
        journal = self._player_subject_journal(player_guid=player_guid, subject_id=definition.get("SubjectID") if definition else None)
        recent_events = self._recent_events(player_guid=player_guid, subject_id=definition.get("SubjectID") if definition else None)

        context_flags: list[str] = []
        if enrichment:
            context_flags.append("enriched_subject")
        if definition:
            context_flags.append("registered_subject")
        if journal:
            context_flags.append("known_to_player")
            kill_count = int(journal.get("KillCount") or 0)
            skin_count = int(journal.get("SkinCount") or 0)
            talk_count = int(journal.get("TalkCount") or 0)
            quest_complete_count = int(journal.get("QuestCompleteCount") or 0)
            feed_count = int(journal.get("FeedCount") or 0)
            if kill_count > 0:
                context_flags.append("combat_history")
            if skin_count > 0:
                context_flags.append("skinning_history")
            if talk_count > 0 or quest_complete_count > 0:
                context_flags.append("social_history")
            if kill_count >= 10 or skin_count >= 5:
                context_flags.append("over_hunted")
            if feed_count > 0:
                context_flags.append("fed_by_player")
        if recent_events:
            context_flags.append("has_recent_events")

        return {
            "subject_entry": entry,
            "definition": definition,
            "enrichment": enrichment,
            "player_journal": journal,
            "recent_events": recent_events,
            "context_flags": context_flags,
        }

    def _build_generation_hints(
        self,
        *,
        questgiver_profile: dict[str, Any],
        target_profile: dict[str, Any],
        questgiver_context: dict[str, Any],
        target_context: dict[str, Any],
        base_kill_count: int,
    ) -> dict[str, Any]:
        tags: list[str] = ["contextual_generation"]
        tone: list[str] = []
        description_seeds: list[str] = []
        recommended_kill_count = max(1, int(base_kill_count))

        target_journal = target_context.get("player_journal") or {}
        questgiver_journal = questgiver_context.get("player_journal") or {}
        target_enrichment = target_context.get("enrichment") or {}
        questgiver_enrichment = questgiver_context.get("enrichment") or {}

        target_role = str(target_enrichment.get("RoleLabel") or target_enrichment.get("Profession") or "").strip()
        target_home_area = str(target_enrichment.get("HomeArea") or "").strip()
        questgiver_role = str(questgiver_enrichment.get("RoleLabel") or questgiver_enrichment.get("Profession") or "").strip()

        if target_role:
            tags.append(target_role.lower().replace(" ", "_"))
            description_seeds.append(f"target_role:{target_role}")
        if target_home_area:
            tags.append(target_home_area.lower().replace(" ", "_"))
            description_seeds.append(f"target_home_area:{target_home_area}")
        if questgiver_role:
            description_seeds.append(f"questgiver_role:{questgiver_role}")

        target_kills = int(target_journal.get("KillCount") or 0)
        target_skins = int(target_journal.get("SkinCount") or 0)
        target_feeds = int(target_journal.get("FeedCount") or 0)
        questgiver_talks = int(questgiver_journal.get("TalkCount") or 0)
        questgiver_quests = int(questgiver_journal.get("QuestCompleteCount") or 0)

        if target_kills >= 10:
            tags.append("repeat_target")
            tone.append("escalating")
            description_seeds.append("player_has_hunted_this_target_repeatedly")
            recommended_kill_count += min(4, target_kills // 10)
        if target_skins >= 5:
            tags.append("skinner_history")
            tone.append("grim")
            description_seeds.append("player_has_skinned_this_subject")
        if target_feeds > 0:
            tags.append("ambiguous_relationship")
            tone.append("tense")
            description_seeds.append("player_has_also_fed_this_subject")
        if questgiver_talks > 0 or questgiver_quests > 0:
            tags.append("known_questgiver")
            tone.append("familiar")
            description_seeds.append("questgiver_knows_the_player")

        service_roles = questgiver_profile.get("service_roles") or []
        if "TRAINER" in service_roles or "QUEST_GIVER" in service_roles:
            tags.append("service_npc")
        mechanical_type = str(target_profile.get("mechanical_type") or "").lower()
        family = str(target_profile.get("family") or "").lower()
        if mechanical_type:
            tags.append(mechanical_type)
        if family and family != "none":
            tags.append(family)

        if not tone:
            tone.append("neutral")
        recommended_kill_count = max(1, min(recommended_kill_count, 20))

        return {
            "recommended_kill_count": recommended_kill_count,
            "extra_tags": sorted(dict.fromkeys(tags)),
            "tone_flags": tone,
            "description_seeds": description_seeds,
        }

    def _subject_enrichment(self, *, entry: int) -> dict[str, Any] | None:
        if not self._table_exists("wm_subject_enrichment"):
            return None
        rows = self._query_world(
            "SELECT SubjectType, EntryID, Species, Profession, RoleLabel, HomeArea, ShortDescription, TagsJSON "
            "FROM wm_subject_enrichment "
            f"WHERE SubjectType = 'creature' AND EntryID = {int(entry)} LIMIT 1"
        )
        return rows[0] if rows else None

    def _subject_definition(self, *, entry: int) -> dict[str, Any] | None:
        if not self._table_exists("wm_subject_definition"):
            return None
        rows = self._query_world(
            "SELECT SubjectID, SubjectType, CreatureEntry, JournalName, Archetype, Species, Occupation, HomeArea, ShortDescription, TagsJSON "
            "FROM wm_subject_definition "
            f"WHERE SubjectType = 'creature' AND CreatureEntry = {int(entry)} LIMIT 1"
        )
        return rows[0] if rows else None

    def _player_subject_journal(self, *, player_guid: int | None, subject_id: Any) -> dict[str, Any] | None:
        if player_guid is None or subject_id in (None, "") or not self._table_exists("wm_player_subject_journal"):
            return None
        rows = self._query_world(
            "SELECT PlayerGUID, SubjectID, FirstSeenAt, LastSeenAt, KillCount, SkinCount, FeedCount, TalkCount, QuestCompleteCount, LastQuestTitle, NotesJSON "
            "FROM wm_player_subject_journal "
            f"WHERE PlayerGUID = {int(player_guid)} AND SubjectID = {int(subject_id)} LIMIT 1"
        )
        return rows[0] if rows else None

    def _recent_events(self, *, player_guid: int | None, subject_id: Any, limit: int = 5) -> list[dict[str, Any]]:
        if player_guid is None or subject_id in (None, "") or not self._table_exists("wm_player_subject_event"):
            return []
        rows = self._query_world(
            "SELECT EventType, EventValue, CreatedAt FROM wm_player_subject_event "
            f"WHERE PlayerGUID = {int(player_guid)} AND SubjectID = {int(subject_id)} "
            "ORDER BY EventID DESC "
            f"LIMIT {int(limit)}"
        )
        return rows

    def _table_exists(self, table_name: str) -> bool:
        cached = self._table_cache.get(table_name)
        if cached is not None:
            return cached
        rows = self.client.query(
            host=self.settings.world_db_host,
            port=self.settings.world_db_port,
            user=self.settings.world_db_user,
            password=self.settings.world_db_password,
            database="information_schema",
            sql=(
                "SELECT TABLE_NAME FROM information_schema.TABLES "
                f"WHERE TABLE_SCHEMA = {_sql_string(self.settings.world_db_name)} "
                f"AND TABLE_NAME = {_sql_string(table_name)} LIMIT 1"
            ),
        )
        exists = bool(rows)
        self._table_cache[table_name] = exists
        return exists

    def _query_world(self, sql: str) -> list[dict[str, Any]]:
        return self.client.query(
            host=self.settings.world_db_host,
            port=self.settings.world_db_port,
            user=self.settings.world_db_user,
            password=self.settings.world_db_password,
            database=self.settings.world_db_name,
            sql=sql,
        )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m wm.quests.context_builder")
    questgiver_group = parser.add_mutually_exclusive_group(required=True)
    questgiver_group.add_argument("--questgiver-entry", type=int)
    questgiver_group.add_argument("--questgiver-name")
    target_group = parser.add_mutually_exclusive_group(required=True)
    target_group.add_argument("--target-entry", type=int)
    target_group.add_argument("--target-name")
    parser.add_argument("--player-guid", type=int)
    parser.add_argument("--base-kill-count", type=int, default=8)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--summary", action="store_true")
    return parser


def _render_summary(payload: dict[str, Any]) -> str:
    hints = payload.get("generation_hints") or {}
    questgiver = payload.get("questgiver_profile") or {}
    target = payload.get("target_profile") or {}
    target_context = payload.get("target_context") or {}
    lines = [
        f"questgiver: {questgiver.get('entry')} | {questgiver.get('name')}",
        f"target: {target.get('entry')} | {target.get('name')}",
        f"player_guid: {payload.get('player_guid')}",
        f"recommended_kill_count: {hints.get('recommended_kill_count')}",
        f"extra_tags: {', '.join(hints.get('extra_tags') or []) or '(none)'}",
        f"tone_flags: {', '.join(hints.get('tone_flags') or []) or '(none)'}",
        f"target_context_flags: {', '.join(target_context.get('context_flags') or []) or '(none)'}",
    ]
    journal = target_context.get("player_journal") or {}
    if journal:
        lines.append(
            "target_journal: "
            f"kills={journal.get('KillCount') or 0}, "
            f"skins={journal.get('SkinCount') or 0}, "
            f"feeds={journal.get('FeedCount') or 0}, "
            f"talks={journal.get('TalkCount') or 0}, "
            f"quests={journal.get('QuestCompleteCount') or 0}"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    settings = Settings.from_env()
    client = MysqlCliClient()
    builder = QuestContextBuilder(client=client, settings=settings)
    payload = builder.build(
        questgiver_entry=args.questgiver_entry,
        questgiver_name=args.questgiver_name,
        target_entry=args.target_entry,
        target_name=args.target_name,
        player_guid=args.player_guid,
        base_kill_count=args.base_kill_count,
    )
    raw = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.output_json is not None:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(raw, encoding="utf-8")
    if args.summary or args.output_json is not None:
        print(_render_summary(payload))
        if args.output_json is not None:
            print("")
            print(f"output_json: {args.output_json}")
    else:
        print(raw)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
