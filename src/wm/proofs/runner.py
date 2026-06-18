from __future__ import annotations

from dataclasses import asdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from wm.observability import WmObservabilityStore
from wm.runtime.status import collect_runtime_status


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True, slots=True)
class ProofPacket:
    proof_kind: str
    title: str
    summary: str
    required_services: tuple[str, ...]
    steps: tuple[str, ...]
    acceptance: tuple[str, ...]
    manual_live: bool = True
    requires_player: bool = False


PACKETS: tuple[ProofPacket, ...] = (
    ProofPacket(
        proof_kind="runtime_startup",
        title="Clean Runtime Startup",
        summary="Verify the launcher-visible WM service stack has one logical instance per service.",
        required_services=("db", "auth", "world", "watcher", "panel", "autoplay"),
        manual_live=False,
        steps=(
            "Start core from launcher.",
            "Start watcher, panel, and autoplay from launcher.",
            "Run this packet and confirm every required service is running exactly once.",
        ),
        acceptance=(
            "DB/Auth/World/Watcher/Panel/Autoplay each report state=running.",
            "No duplicate_service or stale_service_state incident exists for required services.",
        ),
    ),
    ProofPacket(
        proof_kind="chat_action",
        title="In-Game Chat Action",
        summary="Player asks WM for a bounded action; WM replies, gates, applies or blocks, and verifies.",
        required_services=("db", "auth", "world", "watcher", "autoplay"),
        requires_player=True,
        steps=(
            "Join the in-game WM channel.",
            "Ask for a proven low/medium action.",
            "If confirm-gated, answer yes.",
            "Record WM reply, native request result, and visible outcome.",
        ),
        acceptance=(
            "Autoplay journal has deed or pending intent record.",
            "latest_verification is ok=true or the in-game reply explains the blocker.",
            "Panel timeline shows the chat turn and result.",
        ),
    ),
    ProofPacket(
        proof_kind="scene",
        title="Live Scene Director",
        summary="Player asks WM to stage a small scene and every step completes or reports the failed step.",
        required_services=("db", "auth", "world", "watcher", "autoplay"),
        requires_player=True,
        steps=(
            "Ask WM to stage a small temporary creature scene.",
            "Confirm if prompted.",
            "Observe spawn/say/emote/despawn or the first failed step.",
        ),
        acceptance=(
            "Scene run journal records steps_total and steps_executed.",
            "Spawned actors are cleaned up or temporary.",
            "WM sends a completion/failure line in chat.",
        ),
    ),
    ProofPacket(
        proof_kind="ambient",
        title="Ambient Live Reaction",
        summary="WM reacts to a notable event without player prompting and without spam.",
        required_services=("db", "auth", "world", "watcher", "autoplay"),
        requires_player=True,
        steps=(
            "Trigger a notable sensed event such as area entry or quest completion.",
            "Wait for autoplay tick.",
            "Record the single ambient line and cooldown state.",
        ),
        acceptance=(
            "Autoplay journal has ambient_narration.",
            "No repeated narration fires inside cooldown.",
        ),
    ),
    ProofPacket(
        proof_kind="memory",
        title="Persistent Conversation Memory",
        summary="A durable player preference is extracted, persisted, and visible in later context.",
        required_services=("db", "auth", "world", "autoplay"),
        requires_player=True,
        steps=(
            "Tell WM a stable preference or form of address.",
            "Confirm conversation_memory journal entry.",
            "Start a later chat turn and verify context uses the memory.",
        ),
        acceptance=(
            "Character journey/conversation steering row is written.",
            "Later WM response reflects the saved preference without restating stale facts.",
        ),
    ),
    ProofPacket(
        proof_kind="content",
        title="Generated Content Gate",
        summary="LLM-generated content remains behind release packet, dry-run, safe-window, and rollback gates.",
        required_services=("db", "auth", "world", "panel"),
        requires_player=True,
        steps=(
            "Generate a quest/item/scene packet.",
            "Dry-run release.",
            "Apply only if safe-window rules permit.",
            "Record rollback instructions.",
        ),
        acceptance=(
            "Packet manifest and proof checklist exist.",
            "DBC/client-patch content is maintenance-staged while client/player is active.",
        ),
    ),
    ProofPacket(
        proof_kind="rollback",
        title="Rollback Proof",
        summary="A reversible applied artifact can be cleaned up through owned rollback tooling.",
        required_services=("db", "auth", "world"),
        steps=(
            "Select a known reversible WM artifact.",
            "Run rollback dry-run.",
            "Apply rollback and verify DB/client-visible cleanup.",
        ),
        acceptance=(
            "Rollback command reports ok.",
            "Feature status remains PARTIAL until in-client cleanup is observed.",
        ),
    ),
    ProofPacket(
        proof_kind="failure",
        title="Actionable Failure Incident",
        summary="A failed dependency or native action produces a clear incident and next step.",
        required_services=(),
        steps=(
            "Create or observe a dependency failure.",
            "Refresh runtime status.",
            "Confirm an incident appears with kind, service, severity, and message.",
        ),
        acceptance=(
            "Panel incidents route shows the blocker.",
            "Launcher status text does not collapse the problem into ambiguous running/stopping wording.",
        ),
    ),
)


def list_proof_packets() -> list[dict[str, Any]]:
    return [asdict(packet) for packet in PACKETS]


def run_proof_packet(
    *,
    proof_kind: str,
    project_root: str | Path,
    player_guid: int | None = None,
    mode: str = "dry-run",
    store: WmObservabilityStore | None = None,
    runtime_status: dict[str, Any] | None = None,
    manual_evidence: list[str] | None = None,
) -> dict[str, Any]:
    packet = _packet_by_kind(proof_kind)
    root = Path(project_root).resolve()
    obs = store or WmObservabilityStore.for_project(root)
    runtime = runtime_status or collect_runtime_status(project_root=root)
    checks = _runtime_checks(packet=packet, runtime=runtime)
    blockers = [check["detail"] for check in checks if check["status"] == "FAIL"]
    if packet.requires_player and not player_guid:
        checks.append({"name": "player_guid", "status": "FAIL", "detail": "player_guid is required for this live proof"})
        blockers.append("player_guid is required for this live proof")

    evidence_since = _evidence_since(packet=packet, runtime=runtime)
    evidence_checks = _evidence_checks(
        packet=packet,
        project_root=root,
        store=obs,
        player_guid=player_guid,
        evidence_since=evidence_since,
    )
    evidence_refs = [
        ref
        for check in evidence_checks
        for ref in check.get("evidence_refs", [])
        if isinstance(ref, dict)
    ]
    status = _record_status(packet=packet, checks=checks, evidence_checks=evidence_checks, mode=mode)
    record = {
        "schema_version": "wm.proof.record.v1",
        "proof_id": f"proof-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}",
        "proof_kind": packet.proof_kind,
        "title": packet.title,
        "summary": packet.summary,
        "mode": str(mode or "dry-run"),
        "status": status,
        "player_guid": player_guid,
        "created_at": utc_now_iso(),
        "project_root": str(root),
        "steps": list(packet.steps),
        "acceptance": list(packet.acceptance),
        "required_services": list(packet.required_services),
        "checks": checks,
        "blockers": blockers,
        "next_actions": _next_actions(checks),
        "runtime_summary": runtime.get("summary", {}),
        "runtime_incidents": runtime.get("incidents", []),
        "evidence_window": {
            "since": evidence_since,
            "basis": "latest_required_service_started_at" if evidence_since else "unavailable",
        },
        "evidence_checks": evidence_checks,
        "evidence_refs": evidence_refs,
        "timeline_refs": {
            "timeline_url": "/api/wm/timeline",
            "proofs_url": "/api/wm/proofs",
            "incidents_url": "/api/wm/incidents",
        },
        "manual_evidence": list(manual_evidence or []),
        "evidence": list(manual_evidence or []),
    }
    return obs.save_proof(record)


def _packet_by_kind(proof_kind: str) -> ProofPacket:
    for packet in PACKETS:
        if packet.proof_kind == proof_kind:
            return packet
    known = ", ".join(packet.proof_kind for packet in PACKETS)
    raise KeyError(f"unknown proof_kind {proof_kind!r}; expected one of {known}")


def _runtime_checks(*, packet: ProofPacket, runtime: dict[str, Any]) -> list[dict[str, str]]:
    services = runtime.get("services") if isinstance(runtime.get("services"), dict) else {}
    checks: list[dict[str, str]] = []
    for service_key in packet.required_services:
        service = services.get(service_key) if isinstance(services.get(service_key), dict) else {}
        state = str(service.get("state") or "unknown")
        stale = bool(service.get("stale"))
        if state == "running" and not stale:
            checks.append({"name": f"service:{service_key}", "status": "PASS", "detail": "running"})
        elif state == "duplicate":
            checks.append({"name": f"service:{service_key}", "status": "FAIL", "detail": f"{service_key} has duplicate logical instances"})
        elif stale:
            checks.append({"name": f"service:{service_key}", "status": "FAIL", "detail": f"{service_key} state is stale"})
        else:
            checks.append({"name": f"service:{service_key}", "status": "FAIL", "detail": f"{service_key} is {state}"})
    for incident in runtime.get("incidents") or []:
        if not isinstance(incident, dict):
            continue
        service = str(incident.get("service") or "")
        severity = str(incident.get("severity") or "")
        if service in packet.required_services and severity == "error":
            checks.append({"name": f"incident:{service}", "status": "FAIL", "detail": str(incident.get("message") or incident.get("kind"))})
    return checks


def _evidence_since(*, packet: ProofPacket, runtime: dict[str, Any]) -> str | None:
    if packet.proof_kind not in {"chat_action", "ambient", "memory", "scene"}:
        return None
    services = runtime.get("services") if isinstance(runtime.get("services"), dict) else {}
    starts: list[datetime] = []
    for service_key in packet.required_services:
        service = services.get(service_key) if isinstance(services.get(service_key), dict) else {}
        if str(service.get("state") or "") != "running" or bool(service.get("stale")):
            return None
        started = _parse_iso_datetime(service.get("started_at"))
        if started is None:
            return None
        starts.append(started)
    if not starts:
        return None
    return _format_utc(max(starts))


def _evidence_checks(
    *,
    packet: ProofPacket,
    project_root: Path,
    store: WmObservabilityStore,
    player_guid: int | None,
    evidence_since: str | None = None,
) -> list[dict[str, Any]]:
    if packet.proof_kind not in {"chat_action", "ambient", "memory", "scene"}:
        return []
    journal = store.list_autoplay_journal(limit=200)
    autoplay_status = _load_autoplay_status(project_root)
    if packet.proof_kind == "chat_action":
        return _chat_action_evidence(
            journal=journal,
            autoplay_status=autoplay_status,
            player_guid=player_guid,
            evidence_since=evidence_since,
        )
    if packet.proof_kind == "ambient":
        return _ambient_evidence(journal=journal, player_guid=player_guid, evidence_since=evidence_since)
    if packet.proof_kind == "memory":
        return _memory_evidence(journal=journal, player_guid=player_guid, evidence_since=evidence_since)
    if packet.proof_kind == "scene":
        return _scene_evidence(journal=journal, player_guid=player_guid, evidence_since=evidence_since)
    return []


def _chat_action_evidence(
    *,
    journal: list[dict[str, Any]],
    autoplay_status: dict[str, Any],
    player_guid: int | None,
    evidence_since: str | None,
) -> list[dict[str, Any]]:
    chat = _latest_journal_entry(journal, {"chat"}, player_guid=player_guid, evidence_since=evidence_since)
    action = _latest_journal_entry(
        journal,
        {"deed", "pending_intent_set", "pending_intent_cleared"},
        player_guid=player_guid,
        evidence_since=evidence_since,
    )
    intent_issue = _latest_issue(
        autoplay_status,
        kinds={"intent"},
        player_guid=player_guid,
        evidence_since=evidence_since,
    )
    verification = _latest_verification(autoplay_status, action, evidence_since=evidence_since)
    checks = [
        _evidence_check(
            "journal:chat",
            "PASS" if chat else "PENDING",
            "chat turn recorded" if chat else _missing_detail("No autoplay chat journal entry found for this player.", evidence_since),
            chat,
        ),
        _evidence_check(
            "journal:intent_or_deed",
            "PASS" if action or intent_issue else "PENDING",
            (
                "intent/deed record found"
                if action
                else "intent blocker recorded"
                if intent_issue
                else _missing_detail("No deed, pending intent, cleared intent, or intent blocker found.", evidence_since)
            ),
            action,
            extra_refs=[_issue_ref(intent_issue)] if intent_issue else None,
        ),
    ]
    if verification:
        checks.append(_evidence_check(
            "verification:latest",
            "PASS" if bool(verification.get("ok")) else "FAIL",
            str(verification.get("status") or "verification recorded"),
            None,
            extra_refs=[_status_ref("latest_verification", verification)],
        ))
    elif intent_issue and chat:
        checks.append(_evidence_check(
            "verification:blocker_explained",
            "PASS",
            "Intent blocker and chat reply are both recorded.",
            chat,
            extra_refs=[_issue_ref(intent_issue)],
        ))
    else:
        checks.append(_evidence_check(
            "verification:latest",
            "PENDING",
            _missing_detail("No latest verification or recorded blocker explanation found yet.", evidence_since),
            None,
        ))
    return checks


def _ambient_evidence(
    *,
    journal: list[dict[str, Any]],
    player_guid: int | None,
    evidence_since: str | None,
) -> list[dict[str, Any]]:
    ambient = _latest_journal_entry(
        journal,
        {"ambient_narration"},
        player_guid=player_guid,
        evidence_since=evidence_since,
    )
    if ambient is None:
        return [_evidence_check(
            "journal:ambient_narration",
            "PENDING",
            _missing_detail("No ambient narration journal entry found.", evidence_since),
            None,
        )]
    return [_evidence_check(
        "journal:ambient_narration",
        "PASS" if bool(ambient.get("ok")) else "FAIL",
        "ambient narration spoken" if bool(ambient.get("ok")) else "ambient narration attempted but did not apply",
        ambient,
    )]


def _memory_evidence(
    *,
    journal: list[dict[str, Any]],
    player_guid: int | None,
    evidence_since: str | None,
) -> list[dict[str, Any]]:
    memory = _latest_journal_entry(
        journal,
        {"conversation_memory"},
        player_guid=player_guid,
        evidence_since=evidence_since,
    )
    later_chat = None
    if memory is not None:
        later_chat = next(
            (
                entry for entry in journal
                if str(entry.get("kind") or "") == "chat"
                and _matches_player(entry, player_guid)
                and _matches_window(entry, evidence_since)
                and _entry_after(entry, memory)
            ),
            None,
        )
    return [
        _evidence_check(
            "journal:conversation_memory",
            "PASS" if memory and bool(memory.get("ok")) else "FAIL" if memory else "PENDING",
            (
                "durable conversation memory stored"
                if memory and bool(memory.get("ok"))
                else "conversation memory write failed"
                if memory
                else _missing_detail("No conversation memory journal entry found.", evidence_since)
            ),
            memory,
        ),
        _evidence_check(
            "journal:later_chat",
            "PASS" if later_chat else "PENDING",
            "later chat turn recorded after memory write"
            if later_chat
            else _missing_detail("No later chat turn found after the memory write.", evidence_since),
            later_chat,
        ),
    ]


def _scene_evidence(
    *,
    journal: list[dict[str, Any]],
    player_guid: int | None,
    evidence_since: str | None,
) -> list[dict[str, Any]]:
    scene = _latest_journal_entry(journal, {"scene_run"}, player_guid=player_guid, evidence_since=evidence_since)
    if scene is None:
        return [
            _evidence_check("journal:scene_run", "PENDING", _missing_detail("No scene_run journal entry found.", evidence_since), None),
            _evidence_check("scene:cleanup", "PENDING", _missing_detail("No scene cleanup evidence found.", evidence_since), None),
        ]
    cleanup = scene.get("cleanup_status") if isinstance(scene.get("cleanup_status"), dict) else {}
    cleanup_state = str(cleanup.get("status") or "unknown")
    return [
        _evidence_check(
            "journal:scene_run",
            "PASS" if int(scene.get("steps_executed") or 0) > 0 else "FAIL",
            f"scene steps executed={scene.get('steps_executed')} total={scene.get('steps_total')}",
            scene,
        ),
        _evidence_check(
            "scene:cleanup",
            "PASS" if cleanup_state in {"not_required", "temporary_spawn", "despawn_step_planned"} else "FAIL",
            f"cleanup_status={cleanup_state}",
            scene,
        ),
    ]


def _load_autoplay_status(project_root: Path) -> dict[str, Any]:
    try:
        from wm.autoplay.state import AutoplayStateStore

        return AutoplayStateStore(project_root / ".wm-bootstrap" / "state" / "autoplay").load_status()
    except Exception:
        return {}


def _latest_journal_entry(
    journal: list[dict[str, Any]],
    kinds: set[str],
    *,
    player_guid: int | None,
    evidence_since: str | None = None,
) -> dict[str, Any] | None:
    return next(
        (
            entry for entry in journal
            if str(entry.get("kind") or "") in kinds and _matches_player(entry, player_guid)
            and _matches_window(entry, evidence_since)
        ),
        None,
    )


def _latest_issue(
    autoplay_status: dict[str, Any],
    *,
    kinds: set[str],
    player_guid: int | None,
    evidence_since: str | None = None,
) -> dict[str, Any] | None:
    for issue in autoplay_status.get("issues") or []:
        if not isinstance(issue, dict):
            continue
        if str(issue.get("kind") or "") not in kinds:
            continue
        if not _matches_window(issue, evidence_since):
            continue
        payload = issue.get("payload") if isinstance(issue.get("payload"), dict) else {}
        if player_guid is not None and payload.get("player_guid") not in (None, int(player_guid)):
            continue
        return issue
    return None


def _latest_verification(
    autoplay_status: dict[str, Any],
    action_entry: dict[str, Any] | None,
    *,
    evidence_since: str | None = None,
) -> dict[str, Any] | None:
    status_verification = autoplay_status.get("latest_verification")
    if isinstance(status_verification, dict) and _matches_window(status_verification, evidence_since):
        return status_verification
    if isinstance(action_entry, dict) and isinstance(action_entry.get("verification"), dict):
        return action_entry["verification"]
    return None


def _matches_player(entry: dict[str, Any], player_guid: int | None) -> bool:
    if player_guid is None:
        return True
    raw = entry.get("player_guid")
    if raw in (None, ""):
        return True
    try:
        return int(raw) == int(player_guid)
    except (TypeError, ValueError):
        return False


def _matches_window(entry: dict[str, Any], evidence_since: str | None) -> bool:
    if not evidence_since:
        return False
    entry_at = _entry_datetime(entry)
    since = _parse_iso_datetime(evidence_since)
    if entry_at is None or since is None:
        return False
    return entry_at >= since


def _entry_after(entry: dict[str, Any], previous: dict[str, Any]) -> bool:
    entry_at = _entry_datetime(entry)
    previous_at = _entry_datetime(previous)
    if entry_at is None or previous_at is None:
        return False
    return entry_at > previous_at


def _entry_datetime(entry: dict[str, Any]) -> datetime | None:
    return _parse_iso_datetime(entry.get("at") or entry.get("created_at") or entry.get("updated_at"))


def _missing_detail(detail: str, evidence_since: str | None) -> str:
    if not evidence_since:
        return f"{detail} Fresh evidence window is unavailable."
    return f"{detail} Evidence must be at or after {evidence_since}."


def _parse_iso_datetime(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    if not text or text.startswith("/Date("):
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    if "." in text:
        prefix, suffix = text.split(".", 1)
        plus_index = suffix.find("+")
        minus_index = suffix.find("-")
        tz_index = min([idx for idx in (plus_index, minus_index) if idx >= 0], default=-1)
        if tz_index >= 0:
            fraction = suffix[:tz_index]
            tz = suffix[tz_index:]
        else:
            fraction = suffix
            tz = ""
        if len(fraction) > 6:
            text = f"{prefix}.{fraction[:6]}{tz}"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _format_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _evidence_check(
    name: str,
    status: str,
    detail: str,
    entry: dict[str, Any] | None,
    *,
    extra_refs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    refs: list[dict[str, Any]] = []
    if entry is not None:
        refs.append(_journal_ref(entry))
    refs.extend(ref for ref in (extra_refs or []) if ref)
    return {
        "name": name,
        "status": status,
        "detail": detail,
        "evidence_refs": refs,
    }


def _journal_ref(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": "autoplay_journal",
        "kind": entry.get("kind"),
        "at": entry.get("at"),
        "player_guid": entry.get("player_guid"),
        "summary": _short_ref(entry),
    }


def _issue_ref(issue: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": "autoplay_status.issues",
        "kind": issue.get("kind"),
        "at": issue.get("at"),
        "reason": issue.get("reason"),
        "summary": str(issue.get("detail") or issue.get("reason") or "")[:180],
    }


def _status_ref(name: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": f"autoplay_status.{name}",
        "kind": payload.get("verb") or name,
        "at": payload.get("at"),
        "summary": str(payload.get("status") or payload.get("strategy") or name)[:180],
    }


def _short_ref(entry: dict[str, Any]) -> str:
    for key in ("summary", "line", "message", "scene_name", "verb", "reason"):
        value = entry.get(key)
        if value not in (None, ""):
            return str(value)[:180]
    reply = entry.get("reply") if isinstance(entry.get("reply"), dict) else {}
    if reply.get("message"):
        return str(reply["message"])[:180]
    return "recorded"


def _record_status(
    *,
    packet: ProofPacket,
    checks: list[dict[str, str]],
    evidence_checks: list[dict[str, Any]],
    mode: str,
) -> str:
    if any(check["status"] == "FAIL" for check in checks):
        return "failed"
    if any(check.get("status") == "FAIL" for check in evidence_checks):
        return "failed"
    if packet.manual_live and evidence_checks and all(check.get("status") == "PASS" for check in evidence_checks):
        return "passed"
    if packet.manual_live:
        return "manual_required"
    return "passed" if str(mode or "dry-run") == "dry-run" else "manual_required"


def _next_actions(checks: list[dict[str, str]]) -> list[str]:
    actions: list[str] = []
    for check in checks:
        if check.get("status") != "FAIL":
            continue
        name = str(check.get("name") or "")
        detail = str(check.get("detail") or "")
        if name.startswith("service:"):
            service = name.removeprefix("service:")
            if "duplicate" in detail:
                actions.append(f"Stop duplicate {service} instances with Stop All WM or Close Aux Windows, then start it once.")
            elif "stale" in detail:
                actions.append(f"Clear stale {service} heartbeat with Close Aux Windows or Stop All WM, then rerun the proof.")
            else:
                actions.append(f"Start {service} from the launcher, wait for status=running, then rerun the proof.")
        elif name == "player_guid":
            actions.append("Select or pass the configured proof player_guid before running this live proof.")
        elif name.startswith("incident:"):
            service = name.removeprefix("incident:")
            actions.append(f"Open panel incidents for {service}, resolve the blocker, then rerun the proof.")
        elif detail:
            actions.append(detail)
    deduped: list[str] = []
    for action in actions:
        if action not in deduped:
            deduped.append(action)
    return deduped
