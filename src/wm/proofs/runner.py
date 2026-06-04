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
) -> dict[str, Any]:
    packet = _packet_by_kind(proof_kind)
    root = Path(project_root).resolve()
    runtime = runtime_status or collect_runtime_status(project_root=root)
    checks = _runtime_checks(packet=packet, runtime=runtime)
    blockers = [check["detail"] for check in checks if check["status"] == "FAIL"]
    if packet.requires_player and not player_guid:
        checks.append({"name": "player_guid", "status": "FAIL", "detail": "player_guid is required for this live proof"})
        blockers.append("player_guid is required for this live proof")

    status = _record_status(packet=packet, checks=checks, mode=mode)
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
        "runtime_summary": runtime.get("summary", {}),
        "runtime_incidents": runtime.get("incidents", []),
        "evidence": [],
    }
    return (store or WmObservabilityStore.for_project(root)).save_proof(record)


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


def _record_status(*, packet: ProofPacket, checks: list[dict[str, str]], mode: str) -> str:
    if any(check["status"] == "FAIL" for check in checks):
        return "failed"
    if packet.manual_live:
        return "manual_required"
    return "passed" if str(mode or "dry-run") == "dry-run" else "manual_required"
