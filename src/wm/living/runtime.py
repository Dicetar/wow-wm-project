from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from wm.control._cli import build_live_coordinator
from wm.control.scene_play import ControlScene, SceneStep, build_scene_proposal
from wm.living.legend import LegendTrigger, evaluate_legend
from wm.living.nemesis import NemesisTrigger, evaluate_nemesis
from wm.living.oath import OathTrigger, evaluate_oath
from wm.living.patron import PatronTrigger, evaluate_patron
from wm.living.rumor import RumorTrigger, evaluate_rumor
from wm.panel.state import PanelState, utc_now_iso
from wm.sources.native_bridge.action_kinds import NATIVE_ACTION_KIND_BY_ID
from wm.sources.native_bridge.player_marker import DEFAULT_MARKER_SPELL_ID


LANES = {"rumor", "patron", "oath", "nemesis", "legend", "scene_director"}
OPERATIONS = {"trigger", "suppress", "revoke", "cleanup"}


@dataclass(slots=True)
class LivingStateStore:
    root: Path = Path(".wm-bootstrap/state/living")

    def load(self, player_guid: int) -> dict[str, Any]:
        path = self.root / f"{int(player_guid)}.json"
        if not path.exists():
            return {"schema_version": "wm.living.state.v1", "player_guid": int(player_guid), "lanes": {}, "audit": []}
        raw = json.loads(path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}

    def record(self, *, player_guid: int, lane: str, operation: str, details: dict[str, Any]) -> dict[str, Any]:
        state = self.load(player_guid)
        now = utc_now_iso()
        lanes = dict(state.get("lanes") or {})
        lane_state = dict(lanes.get(lane) or {})
        lane_state.update({"operation": operation, "updated_at": now, **details})
        lanes[lane] = lane_state
        audit = list(state.get("audit") or [])
        audit.append({
            "at": now,
            "lane": lane,
            "operation": operation,
            "status": details.get("status"),
            "outcome": details.get("outcome"),
        })
        state.update({"schema_version": "wm.living.state.v1", "player_guid": int(player_guid), "lanes": lanes, "audit": audit[-200:]})
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.root / f"{int(player_guid)}.json"
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(path)
        return state

    def audit(self, *, player_guid: int, lane: str, operation: str, status: str, outcome: str, run_key: str) -> dict[str, Any]:
        state = self.load(player_guid)
        audit = list(state.get("audit") or [])
        audit.append({
            "at": utc_now_iso(),
            "lane": lane,
            "operation": operation,
            "status": status,
            "outcome": outcome,
            "run_key": run_key,
        })
        state["audit"] = audit[-200:]
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.root / f"{int(player_guid)}.json"
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(path)
        return state


def resolve_marker_session(
    session: dict[str, Any] | None,
    *,
    expected_player_guid: int | None = None,
    max_age_seconds: int = 900,
    now: datetime | None = None,
) -> dict[str, Any]:
    session = session or {}
    if session.get("source") != "marker":
        raise ValueError("active WM Session is not marker-selected")
    if int(session.get("marker_spell_id") or 0) != DEFAULT_MARKER_SPELL_ID:
        raise ValueError(f"active WM Session does not use canonical marker {DEFAULT_MARKER_SPELL_ID}")
    guid = session.get("character_guid")
    if guid in (None, ""):
        raise ValueError("active WM Session has no character GUID")
    if expected_player_guid is not None and int(guid) != int(expected_player_guid):
        raise ValueError("requested player GUID conflicts with active marker-selected WM Session")
    marker = session.get("marker") if isinstance(session.get("marker"), dict) else {}
    if marker.get("character_online") is not True:
        raise ValueError("marker-selected character is not confirmed online")
    selected_at = _parse_time(session.get("selected_at"))
    now = now or datetime.now(timezone.utc)
    if selected_at is None or (now - selected_at).total_seconds() > int(max_age_seconds):
        raise ValueError("marker-selected WM Session is stale; reapply aura 946602 and scope-latest")
    return {**session, "character_guid": int(guid)}


def build_lane_steps(lane: str, payload: dict[str, Any], session: dict[str, Any]) -> list[dict[str, Any]]:
    if lane not in LANES:
        raise ValueError(f"unknown living lane: {lane}")
    operation = str(payload.get("operation") or "trigger")
    if operation not in OPERATIONS:
        raise ValueError(f"unknown living operation: {operation}")
    player_guid = int(session["character_guid"])
    player_name = str(session.get("character_name") or "traveler")
    if operation != "trigger":
        return _terminal_steps(lane, operation, payload)
    if lane == "rumor":
        decision = evaluate_rumor(RumorTrigger(player_guid, player_name, _required_text(payload, "subject_name"), _required_int(payload, "deed_count"), payload.get("zone_name")))
    elif lane == "patron":
        decision = evaluate_patron(PatronTrigger(player_guid, player_name, _required_int(payload, "completed_wm_count")))
    elif lane == "oath":
        decision = evaluate_oath(OathTrigger(player_guid, player_name, _required_text(payload, "oath_key"), _required_text(payload, "constraint_label"), _required_int(payload, "target_count"), int(payload.get("current_count") or 0), str(payload.get("phase") or "accept"), _optional_int(payload.get("oath_quest_id"))))
    elif lane == "nemesis":
        decision = evaluate_nemesis(NemesisTrigger(player_guid, _required_int(payload, "subject_entry"), _required_text(payload, "subject_name"), _required_int(payload, "kill_count"), _optional_int(payload.get("zone_id")), player_name, _optional_int(payload.get("turn_in_npc_entry"))))
    elif lane == "legend":
        decision = evaluate_legend(LegendTrigger(player_guid, player_name, _required_text(payload, "zone_name"), _required_int(payload, "deed_count")))
    else:
        return _validate_director_steps(payload.get("steps"))
    if not decision.eligible or decision.plan is None:
        raise ValueError(decision.reason)
    if decision.contract_issues:
        raise ValueError("; ".join(decision.contract_issues))
    return list(decision.plan.scene_steps)


def execute_lane(
    *,
    payload: dict[str, Any],
    session: dict[str, Any],
    mode: str,
    coordinator: Any,
    state_store: LivingStateStore | None = None,
) -> dict[str, Any]:
    lane = str(payload.get("lane") or "")
    operation = str(payload.get("operation") or "trigger")
    steps = build_lane_steps(lane, payload, session)
    scene = ControlScene(
        scene_id=f"living_{lane}_{operation}",
        description=f"Living lane {lane} operation {operation}",
        steps=[_scene_step(item, index) for index, item in enumerate(steps)],
    )
    run_key = str(payload.get("run_key") or datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"))
    results = []
    for index, step in enumerate(scene.steps):
        proposal = build_scene_proposal(
            scene=scene,
            step=step,
            index=index,
            player_guid=int(session["character_guid"]),
            player_name=session.get("character_name"),
            run_key=run_key,
            manual_reason="job-gated living lane execution",
        )
        result = coordinator.execute(proposal=proposal, mode=mode, confirm_live_apply=mode == "apply")
        results.append(result)
        if result.status not in {"dry-run", "applied"}:
            break
    complete = len(results) == len(steps) and all(item.status in {"dry-run", "applied"} for item in results)
    outcome = _lane_outcome(operation=operation, complete=complete)
    response = {
        "schema_version": "wm.living.execution.v1",
        "lane": lane,
        "operation": operation,
        "outcome": outcome,
        "mode": mode,
        "status": "complete" if complete else "failed",
        "player_guid": int(session["character_guid"]),
        "marker_spell_id": int(session["marker_spell_id"]),
        "bridge_event_id": session.get("bridge_event_id"),
        "run_key": run_key,
        "steps": [item.to_dict() for item in results],
    }
    store = state_store or LivingStateStore()
    if mode == "apply" and complete:
        store.record(
            player_guid=int(session["character_guid"]),
            lane=lane,
            operation=operation,
            details={
                "status": "active" if operation == "trigger" else operation,
                "outcome": outcome,
                "run_key": run_key,
                "marker_spell_id": DEFAULT_MARKER_SPELL_ID,
                "bridge_event_id": session.get("bridge_event_id"),
            },
        )
    elif mode == "apply":
        store.audit(
            player_guid=int(session["character_guid"]),
            lane=lane,
            operation=operation,
            status="failed",
            outcome=outcome,
            run_key=run_key,
        )
    return response


def _lane_outcome(*, operation: str, complete: bool) -> str:
    if not complete:
        return "failure"
    if operation == "cleanup":
        return "cleanup"
    if operation == "suppress":
        return "suppression"
    if operation == "revoke":
        return "revocation"
    return "success"


def _terminal_steps(lane: str, operation: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
    if lane == "nemesis" and operation == "cleanup":
        arc_key = payload.get("arc_key") or f"nemesis:{{player_guid}}:{_required_int(payload, 'subject_entry')}"
        return [{"native_action_kind": "creature_despawn", "payload": {"arc_key": arc_key}, "expected_effect": "WM-owned nemesis despawned"}]
    if lane == "oath" and operation in {"revoke", "suppress"}:
        key = _required_text(payload, "oath_key")
        return [
            {"native_action_kind": "wm_counter_clear", "payload": {"counter_key": f"oath:{key}"}, "expected_effect": "oath state revoked"},
            {"native_action_kind": "world_announce_to_player", "payload": {"message": "The oath is released."}, "expected_effect": "revocation visible"},
        ]
    if lane == "patron" and operation in {"revoke", "suppress"}:
        return [
            {"native_action_kind": "wm_counter_clear", "payload": {"counter_key": "wm_patron:favor"}, "expected_effect": "patron state revoked"},
            {"native_action_kind": "world_announce_to_player", "payload": {"message": "The patron withdraws."}, "expected_effect": "revocation visible"},
        ]
    if operation in {"suppress", "revoke", "cleanup"}:
        return [{"native_action_kind": "world_announce_to_player", "payload": {"message": f"WM {lane} state {operation} complete."}, "expected_effect": "state transition visible"}]
    raise ValueError(f"operation {operation} is not supported for {lane}")


def _validate_director_steps(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list) or not raw:
        raise ValueError("scene_director requires a non-empty steps list")
    steps = [dict(item) for item in raw if isinstance(item, dict)]
    if len(steps) != len(raw):
        raise ValueError("scene_director steps must be objects")
    spawned: set[str] = set()
    cleaned: set[str] = set()
    for item in steps:
        kind = str(item.get("native_action_kind") or "")
        action = NATIVE_ACTION_KIND_BY_ID.get(kind)
        if action is None or not action.implemented:
            raise ValueError(f"scene_director uses unavailable action {kind!r}")
        body = item.get("payload") if isinstance(item.get("payload"), dict) else {}
        if kind == "creature_spawn":
            arc_key = _required_text(body, "arc_key")
            duration = int(body.get("duration_ms") or 0)
            if duration <= 0 or duration > 120_000:
                raise ValueError("scene_director creature spawns require duration_ms in 1..120000")
            spawned.add(arc_key)
        elif kind == "creature_despawn":
            cleaned.add(_required_text(body, "arc_key"))
    if len(spawned) < 2:
        raise ValueError("scene_director requires at least two WM-owned actors")
    if not spawned.issubset(cleaned):
        raise ValueError("scene_director requires explicit cleanup for every WM-owned actor")
    return steps


def _scene_step(item: dict[str, Any], index: int) -> SceneStep:
    kind = str(item["native_action_kind"])
    return SceneStep(kind, dict(item.get("payload") or {}), NATIVE_ACTION_KIND_BY_ID[kind].default_risk, float(item.get("delay_seconds") or 0), str(item.get("idempotency_suffix") or index), str(item.get("expected_effect") or ""))


def _required_text(payload: dict[str, Any], key: str) -> str:
    value = str(payload.get(key) or "").strip()
    if not value:
        raise ValueError(f"{key} is required")
    return value


def _required_int(payload: dict[str, Any], key: str) -> int:
    if payload.get(key) in (None, ""):
        raise ValueError(f"{key} is required")
    return int(payload[key])


def _optional_int(value: Any) -> int | None:
    return None if value in (None, "") else int(value)


def _parse_time(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Execute one marker-scoped living-world lane.")
    parser.add_argument("--input-json", required=True)
    parser.add_argument("--mode", choices=["dry-run", "apply"], default="dry-run")
    parser.add_argument("--max-session-age-seconds", type=int, default=900)
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args(argv)
    payload = json.loads(Path(args.input_json).read_text(encoding="utf-8"))
    session = resolve_marker_session(
        PanelState().load_session(),
        expected_player_guid=_optional_int(payload.get("player_guid")),
        max_age_seconds=args.max_session_age_seconds,
    )
    from wm.config import Settings
    result = execute_lane(payload=payload, session=session, mode=args.mode, coordinator=build_live_coordinator(Settings.from_env()))
    if args.summary:
        print(f"lane={result['lane']} operation={result['operation']} outcome={result['outcome']} mode={result['mode']} status={result['status']} player_guid={result['player_guid']} steps={len(result['steps'])}")
    else:
        print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
