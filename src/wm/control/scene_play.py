from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import time
from typing import Any

from wm.config import Settings
from wm.control._cli import build_live_coordinator
from wm.control.coordinator import ControlExecutionResult
from wm.control.models import ControlAction
from wm.control.models import ControlAuthor
from wm.control.models import ControlPlayer
from wm.control.models import ControlProposal
from wm.control.models import ControlRisk
from wm.control.summary import format_native_request_summary
from wm.control.summary import native_request_refs_from_results
from wm.sources.native_bridge.action_kinds import NATIVE_ACTION_KIND_BY_ID


@dataclass(frozen=True, slots=True)
class SceneStep:
    native_action_kind: str
    payload: dict[str, Any]
    risk_level: str
    delay_seconds: float = 0.0
    idempotency_suffix: str | None = None
    expected_effect: str | None = None


@dataclass(frozen=True, slots=True)
class ControlScene:
    scene_id: str
    description: str
    steps: list[SceneStep]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Play an ordered experimental WM control scene.")
    parser.add_argument("--scene", required=True, help="Scene id under control/scenes or a JSON file path.")
    parser.add_argument("--player-guid", type=int, required=True)
    parser.add_argument("--player-name")
    parser.add_argument("--mode", choices=["dry-run", "apply"], default="dry-run")
    parser.add_argument("--confirm-live-apply", action="store_true")
    parser.add_argument("--run-key", help="Idempotency run key. Defaults to a timestamp so scenes can be repeated.")
    parser.add_argument("--manual-reason", default="manual WM scene play")
    parser.add_argument("--summary", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    settings = Settings.from_env()
    scene = load_scene(scene_ref=args.scene, control_root=Path(settings.control_root))
    run_key = args.run_key or datetime.utcnow().strftime("%Y%m%d%H%M%S")
    coordinator = build_live_coordinator(settings)
    results: list[ControlExecutionResult] = []

    for index, step in enumerate(scene.steps):
        if args.mode == "apply" and step.delay_seconds > 0:
            time.sleep(step.delay_seconds)
        proposal = build_scene_proposal(
            scene=scene,
            step=step,
            index=index,
            player_guid=args.player_guid,
            player_name=args.player_name,
            run_key=run_key,
            manual_reason=args.manual_reason,
        )
        result = coordinator.execute(
            proposal=proposal,
            mode=args.mode,
            confirm_live_apply=args.confirm_live_apply,
        )
        results.append(result)
        if result.status not in {"dry-run", "applied"}:
            break

    payload = {
        "scene_id": scene.scene_id,
        "mode": args.mode,
        "run_key": run_key,
        "status": "complete" if len(results) == len(scene.steps) and all(item.status in {"dry-run", "applied"} for item in results) else "failed",
        "steps": [result.to_dict() for result in results],
    }
    if args.summary:
        print(
            f"scene_id={payload['scene_id']} mode={payload['mode']} run_key={payload['run_key']} "
            f"status={payload['status']} steps={len(results)}/{len(scene.steps)}"
        )
        for index, result in enumerate(results):
            native_kind = result.proposal.action.payload.get("native_action_kind")
            print(
                f"step={index} native_action_kind={native_kind} status={result.status} "
                f"idempotency_key={result.proposal.idempotency_key} issues={len(result.issues or [])}"
            )
            for ref in native_request_refs_from_results(result.applied, result.dry_run):
                print(format_native_request_summary(ref))
    else:
        print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if payload["status"] == "complete" else 1


def load_scene(*, scene_ref: str, control_root: Path) -> ControlScene:
    path = Path(scene_ref)
    if not path.exists():
        path = control_root / "scenes" / f"{scene_ref}.json"
    raw = json.loads(path.read_text(encoding="utf-8-sig"))
    if raw.get("schema_version") != "control.scene.v1":
        raise ValueError(f"Unsupported control scene schema: {raw.get('schema_version')}")
    scene_id = str(raw.get("id") or "").strip()
    if not scene_id:
        raise ValueError(f"Scene {scene_ref} is missing id.")
    description = str(raw.get("description") or "").strip()
    steps = []
    for index, item in enumerate(raw.get("steps", [])):
        if not isinstance(item, dict):
            raise ValueError(f"Scene step {index} must be an object.")
        native_action_kind = str(item.get("native_action_kind") or "").strip()
        if not native_action_kind:
            raise ValueError(f"Scene step {index} is missing native_action_kind.")
        action_kind = NATIVE_ACTION_KIND_BY_ID.get(native_action_kind)
        if action_kind is None:
            raise ValueError(f"Scene step {index} references unknown native action kind: {native_action_kind}")
        if not action_kind.implemented:
            raise ValueError(f"Scene step {index} references unimplemented native action kind: {native_action_kind}")
        payload = item.get("payload")
        if payload is None:
            payload = {}
        if not isinstance(payload, dict):
            raise ValueError(f"Scene step {index} payload must be an object.")
        risk_level = _scene_risk_level(item.get("risk_level"), index)
        delay_seconds = _scene_delay_seconds(item.get("delay_seconds"), index)
        steps.append(
            SceneStep(
                native_action_kind=native_action_kind,
                payload=payload,
                risk_level=risk_level,
                delay_seconds=delay_seconds,
                idempotency_suffix=str(item.get("idempotency_suffix") or index),
                expected_effect=str(item.get("expected_effect") or ""),
            )
        )
    if not steps:
        raise ValueError(f"Scene {scene_ref} has no steps.")
    return ControlScene(scene_id=scene_id, description=description, steps=steps)


def build_scene_proposal(
    *,
    scene: ControlScene,
    step: SceneStep,
    index: int,
    player_guid: int,
    player_name: str | None,
    run_key: str,
    manual_reason: str,
) -> ControlProposal:
    substitutions = {
        "scene_id": scene.scene_id,
        "run_key": run_key,
        "player_guid": str(player_guid),
    }
    payload = _materialize_payload(step.payload, substitutions)
    idempotency_suffix = step.idempotency_suffix or str(index)
    return ControlProposal(
        source_event=None,
        player=ControlPlayer(guid=player_guid, name=player_name),
        selected_recipe="manual_admin_action",
        action=ControlAction(
            kind="native_bridge_action",
            payload={
                "native_action_kind": step.native_action_kind,
                "payload": payload,
                "created_by": f"wm.control.scene:{scene.scene_id}",
                "risk_level": step.risk_level,
                "expires_seconds": 60,
                "max_attempts": 3,
                "priority": 5,
            },
        ),
        rationale=f"Play scene {scene.scene_id}: {scene.description}",
        risk=ControlRisk(level=_risk_level(step.risk_level), irreversible=False),
        idempotency_key=f"control:scene:{scene.scene_id}:{player_guid}:{run_key}:{index}:{idempotency_suffix}",
        expected_effect=step.expected_effect or f"Scene step {index} executes {step.native_action_kind}.",
        author=ControlAuthor(kind="manual_admin", name="wm.control.scene_play", manual_reason=manual_reason),
        metadata={"scene_id": scene.scene_id, "scene_step": index, "run_key": run_key},
    )


def _materialize_payload(value: Any, substitutions: dict[str, str]) -> Any:
    if isinstance(value, dict):
        return {key: _materialize_payload(item, substitutions) for key, item in value.items()}
    if isinstance(value, list):
        return [_materialize_payload(item, substitutions) for item in value]
    if isinstance(value, str):
        result = value
        for key, replacement in substitutions.items():
            result = result.replace("{" + key + "}", replacement)
        return result
    return value


def _risk_level(value: str) -> str:
    return value if value in {"low", "medium", "high"} else "low"


def _scene_risk_level(value: object, index: int) -> str:
    risk_level = str(value or "low").strip().lower()
    if risk_level not in {"low", "medium", "high"}:
        raise ValueError(f"Scene step {index} uses invalid risk_level: {risk_level}")
    return risk_level


def _scene_delay_seconds(value: object, index: int) -> float:
    try:
        delay_seconds = float(value or 0)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Scene step {index} uses invalid delay_seconds: {value}") from exc
    if delay_seconds < 0:
        raise ValueError(f"Scene step {index} uses negative delay_seconds: {delay_seconds}")
    return delay_seconds


if __name__ == "__main__":
    raise SystemExit(main())
