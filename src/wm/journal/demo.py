from __future__ import annotations

from wm.journal.models import JournalCounters, JournalEvent, SubjectCard
from wm.journal.summarizer import format_summary_markdown, summarize_subject_journal


def main() -> None:
    stieve = SubjectCard(
        subject_name="Stieve",
        short_description="Miner living in Goldshire",
        archetype="npc",
        species="human",
        occupation="miner",
        home_area="Goldshire",
        tags=["human", "miner", "civilian", "goldshire"],
    )
    stieve_summary = summarize_subject_journal(
        subject=stieve,
        counters=JournalCounters(
            talk_count=2,
            quest_complete_count=1,
            last_quest_title="A Miner's Burden",
        ),
        events=[JournalEvent(event_type="trainer_learn", event_value="Mining")],
    )

    wolf = SubjectCard(
        subject_name="Grey Wolf",
        short_description="Shabby looking wild beast",
        archetype="beast",
        species="wolf",
        occupation="wild predator",
        home_area="Elwynn Forest",
        tags=["wolf", "beast", "wild", "skinnable"],
    )
    wolf_summary = summarize_subject_journal(
        subject=wolf,
        counters=JournalCounters(kill_count=18, skin_count=10, feed_count=1),
        events=[
            JournalEvent(event_type="feed_trigger_quest", event_value="A Cautious Truce")
        ],
    )

    print("=== SUBJECT JOURNAL EXAMPLE: STIEVE ===")
    print(format_summary_markdown(stieve_summary))
    print()
    print("=== SUBJECT JOURNAL EXAMPLE: GREY WOLF ===")
    print(format_summary_markdown(wolf_summary))


if __name__ == "__main__":
    main()
