from __future__ import annotations

import json
from typing import Any


SYSTEM_PROMPT = (
    "You generate World Master structured drafts. Output only one JSON object matching the provided schema. "
    "Do not include SQL, GM commands, shell commands, config edits, file writes, or direct mutation instructions. "
    "Use schema_version exactly as provided. Respect WM domain gates: repeatable bounty template_defaults.SpecialFlags "
    "must be 1, one-shot quest template_defaults.SpecialFlags must be 0, and min_level must not exceed quest_level. "
    "If required facts are missing, still return a conservative draft with notes."
)


def build_messages(
    *,
    schema_version: str,
    instruction: str,
    context_pack: Any | None = None,
    candidate_pack: Any | None = None,
) -> list[dict[str, str]]:
    user_payload = {
        "schema_version": schema_version,
        "instruction": instruction,
        "context_pack": context_pack,
        "candidate_pack": candidate_pack,
    }
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(user_payload, indent=2, ensure_ascii=False, sort_keys=True)},
    ]
