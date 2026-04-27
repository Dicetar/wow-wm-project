from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import time
from typing import Any

from wm.config import Settings
from wm.db.mysql_cli import MysqlCliClient
from wm.spells.platform import SpellBehaviorDebugClient

ECHO_MODE_BEHAVIOR_KIND = "bonebound_echo_mode_v1"
VALID_ECHO_MODES = {
    "hunt",
    "seek",
    "attack",
    "aggressive",
    "follow",
    "close",
    "guard",
    "passive",
    "teleport",
    "tp",
    "recall",
}


@dataclass(slots=True)
class EchoModeResult:
    mode: str
    ok: bool
    executed: bool
    player_guid: int
    echo_mode: str
    hunt_radius: float | None = None
    behavior_kind: str = ECHO_MODE_BEHAVIOR_KIND
    request_id: int | None = None
    status: str = "not_submitted"
    result: dict[str, Any] | None = None
    error_text: str | None = None
    notes: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def normalize_echo_mode(mode: str) -> str:
    normalized = str(mode).strip().lower()
    if normalized not in VALID_ECHO_MODES:
        raise ValueError(f"Unsupported echo mode: {mode}")
    if normalized in {"seek", "attack", "aggressive"}:
        return "hunt"
    if normalized in {"close", "guard", "passive"}:
        return "follow"
    if normalized in {"tp", "recall"}:
        return "teleport"
    return normalized


def normalize_hunt_radius(hunt_radius: float | int | str | None) -> float | None:
    if hunt_radius is None:
        return None
    radius = float(hunt_radius)
    if radius <= 0:
        raise ValueError("Echo hunt radius must be positive")
    return max(5.0, min(100.0, radius))


def submit_echo_mode(
    *,
    client: MysqlCliClient,
    settings: Settings,
    player_guid: int,
    echo_mode: str,
    hunt_radius: float | None = None,
    mode: str = "apply",
    wait: bool = True,
    timeout_seconds: float | None = None,
) -> EchoModeResult:
    if mode not in {"dry-run", "apply"}:
        raise ValueError(f"Unsupported echo mode command mode: {mode}")

    normalized = normalize_echo_mode(echo_mode)
    normalized_radius = normalize_hunt_radius(hunt_radius)
    player_guid = int(player_guid)
    notes = ["bonebound_echo_mode=true", f"echo_mode={normalized}"]
    payload: dict[str, Any] = {"mode": normalized}
    if normalized_radius is not None:
        notes.append(f"hunt_radius={normalized_radius:g}")
        payload["hunt_radius"] = normalized_radius

    if mode == "dry-run":
        return EchoModeResult(
            mode=mode,
            ok=True,
            executed=False,
            player_guid=player_guid,
            echo_mode=normalized,
            hunt_radius=normalized_radius,
            status="dry_run",
            notes=notes,
        )

    debug_client = SpellBehaviorDebugClient(client=client, settings=settings)
    request_id = debug_client.submit_fast(
        player_guid=player_guid,
        behavior_kind=ECHO_MODE_BEHAVIOR_KIND,
        payload=payload,
    )
    if not wait:
        return EchoModeResult(
            mode=mode,
            ok=True,
            executed=True,
            player_guid=player_guid,
            echo_mode=normalized,
            hunt_radius=normalized_radius,
            request_id=request_id,
            status="pending",
            notes=notes + ["submit_only=true"],
        )

    deadline = time.time() + (float(timeout_seconds) if timeout_seconds is not None else settings.native_bridge_action_wait_seconds)
    current = debug_client.get(request_id=request_id)
    while current is not None and current.status not in {"done", "failed", "rejected", "expired"} and time.time() < deadline:
        time.sleep(max(settings.native_bridge_action_poll_seconds, 0.05))
        current = debug_client.get(request_id=request_id)

    if current is None:
        return EchoModeResult(
            mode=mode,
            ok=False,
            executed=True,
            player_guid=player_guid,
            echo_mode=normalized,
            hunt_radius=normalized_radius,
            request_id=request_id,
            status="unknown",
            error_text="request_not_found_after_submit",
            notes=notes,
        )

    ok = current.status == "done" and bool(current.result.get("ok", True))
    return EchoModeResult(
        mode=mode,
        ok=ok,
        executed=True,
        player_guid=player_guid,
        echo_mode=normalized,
        hunt_radius=normalized_radius,
        request_id=request_id,
        status=current.status,
        result=current.result,
        error_text=current.error_text,
        notes=notes,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Toggle Bonebound Echoes between close-follow and nearest-target hunt mode.")
    parser.add_argument("--player-guid", type=int, required=True)
    parser.add_argument("--echo-mode", "--mode-name", choices=sorted(VALID_ECHO_MODES), required=True)
    parser.add_argument("--hunt-radius", type=float, help="Optional seek radius in yards, clamped to 5-100.")
    parser.add_argument("--mode", choices=["dry-run", "apply"], default="apply")
    parser.add_argument("--no-wait", action="store_true", help="Submit the request without waiting for worldserver processing.")
    parser.add_argument("--timeout-seconds", type=float)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--output-json", type=Path)
    return parser


def _print_summary(result: EchoModeResult) -> None:
    print(
        f"mode={result.mode} ok={str(result.ok).lower()} executed={str(result.executed).lower()} "
        f"player_guid={result.player_guid} echo_mode={result.echo_mode} status={result.status} "
        f"hunt_radius={result.hunt_radius if result.hunt_radius is not None else ''} "
        f"request_id={result.request_id if result.request_id is not None else ''}"
    )
    if result.error_text:
        print(f"error={result.error_text}")
    if result.notes:
        for note in result.notes:
            print(f"note={note}")


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    settings = Settings.from_env()
    result = submit_echo_mode(
        client=MysqlCliClient(),
        settings=settings,
        player_guid=int(args.player_guid),
        echo_mode=str(args.echo_mode),
        hunt_radius=args.hunt_radius,
        mode=str(args.mode),
        wait=not bool(args.no_wait),
        timeout_seconds=args.timeout_seconds,
    )
    payload = result.to_dict()
    raw = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.output_json is not None:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(raw, encoding="utf-8")
    if args.summary:
        _print_summary(result)
    else:
        print(raw)
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
