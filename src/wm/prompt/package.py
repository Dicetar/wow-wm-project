from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from wm.character.reader import CharacterStateBundle
from wm.journal.reader import SubjectJournalBundle
from wm.targets.resolver import TargetProfile


@dataclass(slots=True)
class PromptPackage:
    character_guid: int
    target_entry: int
    target_profile: dict[str, Any]
    character_profile: dict[str, Any] | None
    arc_states: list[dict[str, Any]]
    unlocks: list[dict[str, Any]]
    rewards: list[dict[str, Any]]
    prompt_queue: list[dict[str, Any]]
    journal_summary: dict[str, Any] | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_prompt_package(
    *,
    character_guid: int,
    target_entry: int,
    target_profile: TargetProfile,
    character_state: CharacterStateBundle,
    subject_journal: SubjectJournalBundle,
) -> PromptPackage:
    return PromptPackage(
        character_guid=character_guid,
        target_entry=target_entry,
        target_profile=target_profile.to_dict(),
        character_profile=asdict(character_state.profile) if character_state.profile else None,
        arc_states=[asdict(x) for x in character_state.arc_states],
        unlocks=[asdict(x) for x in character_state.unlocks],
        rewards=[asdict(x) for x in character_state.rewards],
        prompt_queue=[asdict(x) for x in character_state.prompt_queue],
        journal_summary=(
            {
                "title": subject_journal.summary.title,
                "description": subject_journal.summary.description,
                "history_lines": subject_journal.summary.history_lines,
            }
            if subject_journal.summary
            else None
        ),
    )
