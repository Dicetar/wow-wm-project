from __future__ import annotations

from dataclasses import asdict
from typing import Any

from wm.candidates.models import CandidateSet
from wm.prompt.package import PromptPackage


def augment_prompt_package_with_candidates(
    *,
    package: PromptPackage,
    quest_candidates: CandidateSet,
    item_candidates: CandidateSet,
    spell_candidates: CandidateSet,
) -> dict[str, Any]:
    return {
        **package.to_dict(),
        "candidates": {
            "quests": _candidate_set_to_dict(quest_candidates),
            "items": _candidate_set_to_dict(item_candidates),
            "spells": _candidate_set_to_dict(spell_candidates),
        },
    }


def _candidate_set_to_dict(candidate_set: CandidateSet) -> dict[str, Any]:
    return {
        "kind": candidate_set.kind,
        "source_path": candidate_set.source_path,
        "options": [asdict(option) for option in candidate_set.options],
    }
