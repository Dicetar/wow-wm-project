"""Read-side character overview for the operator panel.

Pure aggregation over a CharacterStateBundle (wm.character.reader) plus optional
readiness + proposal-count inputs. No DB or HTTP here so it is unit-testable and
reusable; the panel endpoint supplies the bundle/readiness from live readers.
"""
from __future__ import annotations
from typing import Any

from wm.character.reader import CharacterStateBundle


def build_character_overview(
    *,
    player_guid: int,
    bundle: CharacterStateBundle,
    readiness: dict[str, Any] | None = None,
    proposal_counts: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "player_guid": int(player_guid),
        "status": bundle.status,
        "has_profile": bundle.profile is not None,
        "counts": {
            "arc_states": len(bundle.arc_states),
            "unlocks": len(bundle.unlocks),
            "rewards": len(bundle.rewards),
            "conversation_steering": len(bundle.conversation_steering),
            "prompt_queue": len(bundle.prompt_queue),
        },
        "notes": list(bundle.notes),
        "readiness": readiness,
        "proposals": proposal_counts,
    }
