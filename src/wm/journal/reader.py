from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from wm.config import Settings
from wm.db.mysql_cli import MysqlCliClient
from wm.journal.models import JournalCounters, JournalEvent, SubjectCard
from wm.journal.summarizer import JournalSummary, summarize_subject_journal


@dataclass(slots=True)
class SubjectJournalBundle:
    subject_id: int | None
    subject_card: SubjectCard | None
    counters: JournalCounters | None
    events: list[JournalEvent]
    summary: JournalSummary | None


def load_subject_journal_for_creature(
    *,
    client: MysqlCliClient,
    settings: Settings,
    player_guid: int,
    creature_entry: int,
) -> SubjectJournalBundle:
    guid = int(player_guid)
    entry = int(creature_entry)

    subject_rows = client.query(
        host=settings.world_db_host,
        port=settings.world_db_port,
        user=settings.world_db_user,
        password=settings.world_db_password,
        database=settings.world_db_name,
        sql=(
            "SELECT SubjectID, JournalName, Archetype, Species, Occupation, HomeArea, ShortDescription, TagsJSON "
            "FROM wm_subject_definition "
            f"WHERE SubjectType = 'creature' AND CreatureEntry = {entry} AND IsActive = 1"
        ),
    )

    if not subject_rows:
        return SubjectJournalBundle(
            subject_id=None,
            subject_card=None,
            counters=None,
            events=[],
            summary=None,
        )

    subject_row = subject_rows[0]
    subject_id = int(subject_row["SubjectID"])
    subject_card = _build_subject_card(subject_row)

    journal_rows = client.query(
        host=settings.world_db_host,
        port=settings.world_db_port,
        user=settings.world_db_user,
        password=settings.world_db_password,
        database=settings.world_db_name,
        sql=(
            "SELECT KillCount, SkinCount, FeedCount, TalkCount, QuestCompleteCount, LastQuestTitle "
            "FROM wm_player_subject_journal "
            f"WHERE PlayerGUID = {guid} AND SubjectID = {subject_id}"
        ),
    )

    event_rows = client.query(
        host=settings.world_db_host,
        port=settings.world_db_port,
        user=settings.world_db_user,
        password=settings.world_db_password,
        database=settings.world_db_name,
        sql=(
            "SELECT EventType, EventValue "
            "FROM wm_player_subject_event "
            f"WHERE PlayerGUID = {guid} AND SubjectID = {subject_id} ORDER BY EventID"
        ),
    )

    counters = _build_counters(journal_rows[0]) if journal_rows else JournalCounters()
    events = [_build_event(row) for row in event_rows]
    summary = summarize_subject_journal(subject_card, counters, events)

    return SubjectJournalBundle(
        subject_id=subject_id,
        subject_card=subject_card,
        counters=counters,
        events=events,
        summary=summary,
    )


def _build_subject_card(row: dict[str, Any]) -> SubjectCard:
    return SubjectCard(
        subject_name=str(row["JournalName"]),
        short_description=row.get("ShortDescription"),
        archetype=row.get("Archetype"),
        species=row.get("Species"),
        occupation=row.get("Occupation"),
        home_area=row.get("HomeArea"),
        tags=_parse_json_list(row.get("TagsJSON")),
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
