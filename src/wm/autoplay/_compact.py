from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from typing import Any


def _parse_json_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if value in (None, ""):
        return {}
    try:
        parsed = json.loads(str(value))
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _risk_from_payload(payload: dict[str, Any]) -> str:
    risk = payload.get("risk")
    if isinstance(risk, dict) and risk.get("level"):
        return str(risk["level"])
    if isinstance(risk, str):
        return risk
    steps = payload.get("steps")
    if isinstance(steps, list):
        risks = [str(step.get("risk_level") or "low") for step in steps if isinstance(step, dict)]
        if "high" in risks:
            return "high"
        if "medium" in risks:
            return "medium"
    return "low"


def _draft_source_event_at(record: dict[str, Any]) -> str | None:
    opportunity = record.get("opportunity") if isinstance(record.get("opportunity"), dict) else {}
    value = opportunity.get("source_event_at") or record.get("source_event_at")
    return str(value) if value else None


def _applied_lane_counts(status: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in status.get("proposal_queue") or []:
        if isinstance(item, dict) and str(item.get("state") or "") == "APPLIED":
            lane = str(item.get("lane") or "")
            if lane:
                counts[lane] = int(counts.get(lane, 0)) + 1
    return counts


def _as_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _compact_draft_record(record: dict[str, Any]) -> dict[str, Any]:
    return {
        key: record.get(key)
        for key in ("draft_id", "lane", "schema_version", "state", "player_guid")
        if key in record
    }


def _compact_request(request: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(request, dict):
        return None
    return {
        "model": request.get("model"),
        "temperature": request.get("temperature"),
        "max_tokens": request.get("max_tokens"),
        "response_format": request.get("response_format"),
    }


def _stable_key(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:12]


def _parse_time(value: str) -> datetime | None:
    if not value:
        return None
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    if "T" not in normalized and " " in normalized:
        normalized = normalized.replace(" ", "T", 1)
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _int_or_none(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
