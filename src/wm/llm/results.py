from __future__ import annotations

import json
from typing import Any


class LlmResultError(ValueError):
    pass


def parse_json_object(text: str) -> dict[str, Any]:
    candidate = _strip_fence(text.strip())
    try:
        value = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise LlmResultError(f"LLM response was not valid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise LlmResultError("LLM response must be one JSON object.")
    return value


def _strip_fence(text: str) -> str:
    if not text.startswith("```"):
        return text
    lines = text.splitlines()
    if len(lines) >= 3 and lines[-1].strip() == "```":
        return "\n".join(lines[1:-1]).strip()
    return text
