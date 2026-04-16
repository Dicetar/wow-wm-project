from __future__ import annotations

from typing import Any


def execution_to_dict(result: Any) -> dict[str, Any] | None:
    if result is None:
        return None
    if hasattr(result, "to_dict"):
        result = result.to_dict()
    if isinstance(result, dict):
        return result
    return None


def execution_status(result: Any) -> str | None:
    payload = execution_to_dict(result)
    if payload is None:
        return None
    status = payload.get("status")
    return None if status in (None, "") else str(status)


def native_request_refs_from_execution(result: Any) -> list[dict[str, Any]]:
    payload = execution_to_dict(result)
    if payload is None:
        return []
    steps = payload.get("steps")
    if not isinstance(steps, list):
        return []

    refs: list[dict[str, Any]] = []
    for step in steps:
        if not isinstance(step, dict):
            continue
        details = step.get("details")
        if not isinstance(details, dict):
            continue
        for request_key in ("native_request", "request"):
            request = details.get(request_key)
            if not isinstance(request, dict):
                continue
            refs.append(_request_ref_from_step(step=step, details=details, request_key=request_key, request=request))
    return refs


def native_request_refs_from_results(*results: Any) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for result in results:
        for ref in native_request_refs_from_execution(result):
            key = (str(ref.get("request_id") or ""), str(ref.get("idempotency_key") or ""))
            if key in seen:
                continue
            seen.add(key)
            refs.append(ref)
    return refs


def format_native_request_summary(ref: dict[str, Any]) -> str:
    return (
        "native_request "
        f"step={_summary_value(ref.get('step_kind'))} "
        f"source={_summary_value(ref.get('request_source'))} "
        f"request_id={_summary_value(ref.get('request_id'))} "
        f"action_kind={_summary_value(ref.get('action_kind'))} "
        f"status={_summary_value(ref.get('status'))} "
        f"player_guid={_summary_value(ref.get('player_guid'))} "
        f"error={_summary_value(ref.get('error_text'))}"
    )


def _request_ref_from_step(
    *,
    step: dict[str, Any],
    details: dict[str, Any],
    request_key: str,
    request: dict[str, Any],
) -> dict[str, Any]:
    return {
        "step_kind": _str_or_none(step.get("kind")),
        "step_status": _str_or_none(step.get("status")),
        "request_source": request_key,
        "request_id": _coalesce(request.get("request_id"), request.get("RequestID")),
        "idempotency_key": _coalesce(request.get("idempotency_key"), request.get("IdempotencyKey")),
        "player_guid": _coalesce(request.get("player_guid"), request.get("PlayerGUID")),
        "action_kind": _coalesce(request.get("action_kind"), request.get("ActionKind"), details.get("native_action_kind")),
        "status": _coalesce(request.get("status"), request.get("Status")),
        "error_text": _coalesce(request.get("error_text"), request.get("ErrorText")),
        "result": request.get("result") if isinstance(request.get("result"), dict) else request.get("ResultJSON"),
    }


def _coalesce(*values: Any) -> Any:
    for value in values:
        if value not in (None, ""):
            return value
    return None


def _str_or_none(value: Any) -> str | None:
    return None if value in (None, "") else str(value)


def _summary_value(value: Any) -> str:
    return "None" if value in (None, "") else str(value)
