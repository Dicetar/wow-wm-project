from __future__ import annotations

from typing import Any

from wm.autoplay.state import utc_now_iso


def verify_control_result(
    *,
    verb: str,
    applied_result: Any,
    expected_effect: str | None = None,
    strategy: str = "native_request_done",
) -> dict[str, Any]:
    """Small generic post-action verification record.

    This is intentionally conservative. It does not claim client visibility by
    itself; it records whether the control coordinator reached an applied state
    and captures native request references when available. Verb-specific DB or
    in-client proof can extend this record later without changing callers.
    """

    status = str(getattr(applied_result, "status", "") or "")
    issues = getattr(applied_result, "issues", None)
    refs = []
    try:
        from wm.control.summary import native_request_refs_from_results

        refs = native_request_refs_from_results(
            getattr(applied_result, "applied", None),
            getattr(applied_result, "dry_run", None),
        )
    except Exception:
        refs = []
    ok = status == "applied" and not issues
    return {
        "schema_version": "wm.autoplay.verification.v1",
        "at": utc_now_iso(),
        "verb": str(verb),
        "strategy": str(strategy),
        "status": "verified" if ok else "failed",
        "ok": ok,
        "control_status": status,
        "expected_effect": expected_effect,
        "native_request_refs": refs,
        "issue_count": len(issues or []),
    }
