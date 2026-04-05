from __future__ import annotations

from wm.journal.models import JournalCounters, JournalEvent, JournalSummary, SubjectCard


def summarize_subject_journal(
    subject: SubjectCard,
    counters: JournalCounters,
    events: list[JournalEvent] | None = None,
) -> JournalSummary:
    events = events or []
    history_lines: list[str] = []

    if counters.quest_complete_count > 0 and counters.last_quest_title:
        history_lines.append(
            f'Player completed quest: "{counters.last_quest_title}"'
        )
    elif counters.quest_complete_count > 0:
        history_lines.append(
            f"Player completed quests: {counters.quest_complete_count}"
        )

    if counters.kill_count > 0:
        history_lines.append(f"Player killed {counters.kill_count}")

    if counters.skin_count > 0:
        history_lines.append(f"Player skinned {counters.skin_count}")

    if counters.feed_count > 0:
        history_lines.append(f"Player fed {subject.subject_name} {counters.feed_count} time(s)")

    if counters.talk_count > 0:
        history_lines.append(f"Player talked to {subject.subject_name} {counters.talk_count} time(s)")

    for event in events:
        label = event.event_type.strip().lower()
        value = event.event_value.strip() if event.event_value else None

        if label == "trainer_learn" and value:
            history_lines.append(f"Player learned {value} from {subject.subject_name}")
        elif label == "feed_trigger_quest" and value:
            history_lines.append(
                f"Player fed {subject.subject_name} and unlocked quest: \"{value}\""
            )
        elif label == "note" and value:
            history_lines.append(value)

    return JournalSummary(
        title=subject.subject_name,
        description=subject.short_description,
        history_lines=history_lines,
        raw={
            "subject": {
                "subject_name": subject.subject_name,
                "short_description": subject.short_description,
                "archetype": subject.archetype,
                "species": subject.species,
                "occupation": subject.occupation,
                "home_area": subject.home_area,
                "tags": subject.tags,
            },
            "counters": {
                "kill_count": counters.kill_count,
                "skin_count": counters.skin_count,
                "feed_count": counters.feed_count,
                "talk_count": counters.talk_count,
                "quest_complete_count": counters.quest_complete_count,
                "last_quest_title": counters.last_quest_title,
            },
            "events": [
                {"event_type": event.event_type, "event_value": event.event_value}
                for event in events
            ],
        },
    )


def format_summary_markdown(summary: JournalSummary) -> str:
    lines = [summary.title]
    if summary.description:
        lines.append(summary.description)
    lines.extend(summary.history_lines)
    return "\n".join(lines)
