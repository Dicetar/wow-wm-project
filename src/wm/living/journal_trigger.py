"""Bridge the existing journal reader into Living World triggers.

The Living World scaffolds take deterministic inputs so they unit-test without
a DB. This module is the read-side adapter that turns real
`SubjectJournalReader` counters into those triggers, so the features consume
actual world memory at runtime. The reader is injectable -> still offline
testable with a fake bundle.
"""

from __future__ import annotations

from typing import Any

from wm.living.nemesis import NemesisTrigger
from wm.living.rumor import RumorTrigger


def load_subject_journal_counts(
    *,
    reader: Any,
    player_guid: int,
    subject_entry: int,
) -> tuple[int, str | None]:
    """Return (kill_count, subject_name) from the journal bundle.

    Degrades to (0, None) when counters/subject rows are absent (the reader's
    documented PARTIAL/UNKNOWN fallback) so callers can decide eligibility.
    """
    bundle = reader.load_for_creature(player_guid=player_guid, creature_entry=subject_entry)
    counters = getattr(bundle, "counters", None)
    kill_count = int(getattr(counters, "kill_count", 0) or 0) if counters is not None else 0
    card = getattr(bundle, "subject_card", None)
    subject_name = getattr(card, "subject_name", None) if card is not None else None
    return kill_count, subject_name


def build_nemesis_trigger_from_journal(
    *,
    reader: Any,
    player_guid: int,
    subject_entry: int,
    player_name: str | None = None,
    subject_name: str | None = None,
    turn_in_npc_entry: int | None = None,
) -> NemesisTrigger:
    kills, journal_name = load_subject_journal_counts(
        reader=reader, player_guid=player_guid, subject_entry=subject_entry
    )
    return NemesisTrigger(
        player_guid=player_guid,
        subject_entry=subject_entry,
        subject_name=subject_name or journal_name or f"creature:{subject_entry}",
        kill_count=kills,
        player_name=player_name,
        turn_in_npc_entry=turn_in_npc_entry,
    )


def build_rumor_trigger_from_journal(
    *,
    reader: Any,
    player_guid: int,
    player_name: str,
    subject_entry: int,
    subject_name: str | None = None,
    zone_name: str | None = None,
) -> RumorTrigger:
    deeds, journal_name = load_subject_journal_counts(
        reader=reader, player_guid=player_guid, subject_entry=subject_entry
    )
    return RumorTrigger(
        player_guid=player_guid,
        player_name=player_name,
        subject_name=subject_name or journal_name or f"creature:{subject_entry}",
        deed_count=deeds,
        zone_name=zone_name,
    )


def build_journal_reader() -> Any:
    """Construct the live SubjectJournalReader from env settings (runtime path)."""
    from wm.config import Settings
    from wm.db.mysql_cli import MysqlCliClient
    from wm.journal.reader import SubjectJournalReader

    settings = Settings.from_env()
    return SubjectJournalReader(client=MysqlCliClient(), settings=settings)
