from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from wm.config import Settings
from wm.db.mysql_cli import MysqlCliClient, MysqlCliError
from wm.journal.models import JournalCounters, JournalEvent, SubjectCard
from wm.journal.summarizer import JournalSummary, summarize_subject_journal
from wm.subjects.models import SubjectCard as ResolvedSubjectCard


@dataclass(slots=True)
class SubjectJournalBundle:
    subject_id: int | None
    subject_card: SubjectCard | None
    counters: JournalCounters | None
    events: list[JournalEvent]
    summary: JournalSummary | None
    definition: dict[str, Any] | None = None
    enrichment: dict[str, Any] | None = None
    source_flags: list[str] = field(default_factory=list)
    status: str = "UNKNOWN"


class SubjectJournalReader:
    def __init__(self, *, client: MysqlCliClient, settings: Settings) -> None:
        self.client = client
        self.settings = settings
        self._table_cache: dict[str, bool] = {}

    def load_for_creature(
        self,
        *,
        player_guid: int,
        creature_entry: int,
        resolved_subject_card: ResolvedSubjectCard | None = None,
    ) -> SubjectJournalBundle:
        guid = int(player_guid)
        entry = int(creature_entry)

        definition = self._subject_definition(entry=entry)
        enrichment = self._subject_enrichment(entry=entry)
        subject_id = int(definition["SubjectID"]) if definition is not None else None
        subject_card = _build_subject_card(
            definition=definition,
            enrichment=enrichment,
            resolved_subject_card=resolved_subject_card,
            creature_entry=entry,
        )

        if subject_card is None:
            return SubjectJournalBundle(
                subject_id=subject_id,
                subject_card=None,
                counters=None,
                events=[],
                summary=None,
                definition=definition,
                enrichment=enrichment,
                source_flags=_source_flags(
                    definition=definition,
                    enrichment=enrichment,
                    resolved_subject_card=resolved_subject_card,
                    journal_row=None,
                    event_count=0,
                ),
                status="UNKNOWN",
            )

        journal_row = self._player_subject_journal(player_guid=guid, subject_id=subject_id)
        event_rows = self._recent_events(player_guid=guid, subject_id=subject_id)
        counters = _build_counters(journal_row) if journal_row is not None else JournalCounters()
        events = [_build_event(row) for row in event_rows]
        summary = summarize_subject_journal(subject_card, counters, events)

        return SubjectJournalBundle(
            subject_id=subject_id,
            subject_card=subject_card,
            counters=counters,
            events=events,
            summary=summary,
            definition=definition,
            enrichment=enrichment,
            source_flags=_source_flags(
                definition=definition,
                enrichment=enrichment,
                resolved_subject_card=resolved_subject_card,
                journal_row=journal_row,
                event_count=len(events),
            ),
            status="WORKING" if subject_id is not None else "PARTIAL",
        )

    def _subject_definition(self, *, entry: int) -> dict[str, Any] | None:
        if not self._table_exists("wm_subject_definition"):
            return None
        rows = self._query_world(
            "SELECT SubjectID, SubjectType, CreatureEntry, JournalName, Archetype, Species, Occupation, HomeArea, ShortDescription, TagsJSON "
            "FROM wm_subject_definition "
            f"WHERE SubjectType = 'creature' AND CreatureEntry = {int(entry)} AND IsActive = 1 "
            "LIMIT 1"
        )
        return rows[0] if rows else None

    def _subject_enrichment(self, *, entry: int) -> dict[str, Any] | None:
        if not self._table_exists("wm_subject_enrichment"):
            return None
        rows = self._query_world(
            "SELECT SubjectType, EntryID, Species, Profession, RoleLabel, HomeArea, ShortDescription, TagsJSON "
            "FROM wm_subject_enrichment "
            f"WHERE SubjectType = 'creature' AND EntryID = {int(entry)} LIMIT 1"
        )
        return rows[0] if rows else None

    def _player_subject_journal(self, *, player_guid: int, subject_id: int | None) -> dict[str, Any] | None:
        if subject_id is None or not self._table_exists("wm_player_subject_journal"):
            return None
        rows = self._query_world(
            "SELECT PlayerGUID, SubjectID, FirstSeenAt, LastSeenAt, KillCount, SkinCount, FeedCount, TalkCount, QuestCompleteCount, LastQuestTitle, NotesJSON "
            "FROM wm_player_subject_journal "
            f"WHERE PlayerGUID = {int(player_guid)} AND SubjectID = {int(subject_id)} LIMIT 1"
        )
        return rows[0] if rows else None

    def _recent_events(self, *, player_guid: int, subject_id: int | None, limit: int = 20) -> list[dict[str, Any]]:
        if subject_id is None or not self._table_exists("wm_player_subject_event"):
            return []
        return self._query_world(
            "SELECT EventType, EventValue, CreatedAt "
            "FROM wm_player_subject_event "
            f"WHERE PlayerGUID = {int(player_guid)} AND SubjectID = {int(subject_id)} "
            "ORDER BY EventID "
            f"LIMIT {int(limit)}"
        )

    def _table_exists(self, table_name: str) -> bool:
        cached = self._table_cache.get(table_name)
        if cached is not None:
            return cached
        try:
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
        except MysqlCliError:
            self._table_cache[table_name] = False
            return False
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


def load_subject_journal_for_creature(
    *,
    client: MysqlCliClient,
    settings: Settings,
    player_guid: int,
    creature_entry: int,
    resolved_subject_card: ResolvedSubjectCard | None = None,
) -> SubjectJournalBundle:
    return SubjectJournalReader(client=client, settings=settings).load_for_creature(
        player_guid=player_guid,
        creature_entry=creature_entry,
        resolved_subject_card=resolved_subject_card,
    )


def _build_subject_card(
    *,
    definition: dict[str, Any] | None,
    enrichment: dict[str, Any] | None,
    resolved_subject_card: ResolvedSubjectCard | None,
    creature_entry: int,
) -> SubjectCard | None:
    if definition is None and enrichment is None and resolved_subject_card is None:
        return None

    subject_name = _first_text(
        definition.get("JournalName") if definition is not None else None,
        resolved_subject_card.display_name if resolved_subject_card is not None else None,
        f"Creature {int(creature_entry)}",
    ) or f"Creature {int(creature_entry)}"
    tags = _dedupe(
        [
            *_parse_json_list(definition.get("TagsJSON") if definition is not None else None),
            *_parse_json_list(enrichment.get("TagsJSON") if enrichment is not None else None),
            *(resolved_subject_card.role_tags if resolved_subject_card is not None else []),
            *(resolved_subject_card.group_keys if resolved_subject_card is not None else []),
            *(resolved_subject_card.area_tags if resolved_subject_card is not None else []),
        ]
    )
    return SubjectCard(
        subject_name=subject_name,
        short_description=_first_text(
            definition.get("ShortDescription") if definition is not None else None,
            enrichment.get("ShortDescription") if enrichment is not None else None,
        ),
        archetype=_first_text(
            definition.get("Archetype") if definition is not None else None,
            resolved_subject_card.archetype if resolved_subject_card is not None else None,
        ),
        species=_first_text(
            definition.get("Species") if definition is not None else None,
            enrichment.get("Species") if enrichment is not None else None,
            resolved_subject_card.family if resolved_subject_card is not None else None,
            resolved_subject_card.creature_type if resolved_subject_card is not None else None,
        ),
        occupation=_first_text(
            definition.get("Occupation") if definition is not None else None,
            enrichment.get("Profession") if enrichment is not None else None,
            enrichment.get("RoleLabel") if enrichment is not None else None,
            resolved_subject_card.title if resolved_subject_card is not None else None,
        ),
        home_area=_first_text(
            definition.get("HomeArea") if definition is not None else None,
            enrichment.get("HomeArea") if enrichment is not None else None,
            resolved_subject_card.area_tags[0] if resolved_subject_card is not None and resolved_subject_card.area_tags else None,
        ),
        tags=tags,
    )


def _build_counters(row: dict[str, Any]) -> JournalCounters:
    return JournalCounters(
        kill_count=int(row.get("KillCount") or 0),
        skin_count=int(row.get("SkinCount") or 0),
        feed_count=int(row.get("FeedCount") or 0),
        talk_count=int(row.get("TalkCount") or 0),
        quest_complete_count=int(row.get("QuestCompleteCount") or 0),
        last_quest_title=row.get("LastQuestTitle"),
    )


def _build_event(row: dict[str, Any]) -> JournalEvent:
    return JournalEvent(
        event_type=str(row["EventType"]),
        event_value=row.get("EventValue"),
    )


def _source_flags(
    *,
    definition: dict[str, Any] | None,
    enrichment: dict[str, Any] | None,
    resolved_subject_card: ResolvedSubjectCard | None,
    journal_row: dict[str, Any] | None,
    event_count: int,
) -> list[str]:
    flags: list[str] = []
    if definition is not None:
        flags.append("subject_definition")
    if enrichment is not None:
        flags.append("subject_enrichment")
    if resolved_subject_card is not None:
        flags.append("subject_resolver")
    if journal_row is not None:
        flags.append("player_subject_journal")
    if event_count > 0:
        flags.append("player_subject_event")
    return flags


def _parse_json_list(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    import json
    try:
        parsed = json.loads(str(value))
        if isinstance(parsed, list):
            return [str(x) for x in parsed]
    except json.JSONDecodeError:
        return []
    return []


def _first_text(*values: Any) -> str | None:
    for value in values:
        if value not in (None, ""):
            return str(value)
    return None


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _sql_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("'", "''")
    return f"'{escaped}'"
