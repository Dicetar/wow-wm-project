from __future__ import annotations

import argparse
import json
from typing import Any

from wm.config import Settings
from wm.db.mysql_cli import MysqlCliClient
from wm.sources.native_bridge.action_kinds import NATIVE_ACTION_KIND_BY_ID
from wm.sources.native_bridge.actions import NativeBridgeActionClient


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage native WM bridge action queue and live player scope.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    scope = subparsers.add_parser("scope-player", help="Enable or disable native bridge scope for one player.")
    scope.add_argument("--player-guid", type=int, required=True)
    scope.add_argument("--profile", default="default")
    scope.add_argument("--disable", action="store_true")
    scope.add_argument("--reason", default="manual WM bridge scope update")
    scope.add_argument("--expires-seconds", type=int)
    scope.add_argument("--summary", action="store_true")

    policy = subparsers.add_parser("policy", help="Enable or disable one native action policy.")
    policy.add_argument("--action-kind", choices=sorted(NATIVE_ACTION_KIND_BY_ID), required=True)
    policy.add_argument("--profile", default="default")
    policy.add_argument("--enable", action="store_true")
    policy.add_argument("--disable", action="store_true")
    policy.add_argument("--max-risk-level")
    policy.add_argument("--cooldown-ms", type=int)
    policy.add_argument("--burst-limit", type=int)
    policy.add_argument("--admin-only", action="store_true")
    policy.add_argument("--summary", action="store_true")

    submit = subparsers.add_parser("submit", help="Submit a native bridge action request.")
    submit.add_argument("--player-guid", type=int, required=True)
    submit.add_argument("--action-kind", choices=sorted(NATIVE_ACTION_KIND_BY_ID), required=True)
    submit.add_argument("--payload-json", default="{}")
    submit.add_argument("--idempotency-key", required=True)
    submit.add_argument("--created-by", default="manual")
    submit.add_argument("--risk-level", default="low")
    submit.add_argument("--expires-seconds", type=int, default=60)
    submit.add_argument("--max-attempts", type=int, default=3)
    submit.add_argument("--sequence-id")
    submit.add_argument("--sequence-order", type=int, default=0)
    submit.add_argument("--wait-for-prior", action="store_true")
    submit.add_argument("--priority", type=int, default=5)
    submit.add_argument("--purge-after-seconds", type=int)
    submit.add_argument("--target-map-id", type=int)
    submit.add_argument("--target-x", type=float)
    submit.add_argument("--target-y", type=float)
    submit.add_argument("--target-z", type=float)
    submit.add_argument("--target-o", type=float)
    submit.add_argument("--target-player-guid", type=int)
    submit.add_argument("--wait", action="store_true")
    submit.add_argument("--summary", action="store_true")

    sequence = subparsers.add_parser("submit-sequence", help="Submit a small ordered native bridge action sequence.")
    sequence.add_argument("--player-guid", type=int, required=True)
    sequence.add_argument("--sequence-id", required=True)
    sequence.add_argument("--actions-json", required=True, help="JSON array of action objects with action_kind and optional payload/idempotency_key.")
    sequence.add_argument("--created-by", default="manual")
    sequence.add_argument("--risk-level", default="low")
    sequence.add_argument("--expires-seconds", type=int, default=60)
    sequence.add_argument("--max-attempts", type=int, default=3)
    sequence.add_argument("--priority", type=int, default=5)
    sequence.add_argument("--wait", action="store_true")
    sequence.add_argument("--summary", action="store_true")

    inspect = subparsers.add_parser("inspect", help="List native bridge action queue requests.")
    inspect.add_argument("--player-guid", type=int)
    inspect.add_argument("--status")
    inspect.add_argument("--limit", type=int, default=20)
    inspect.add_argument("--summary", action="store_true")

    recover = subparsers.add_parser("recover-stale", help="Requeue or fail expired claimed action rows.")
    recover.add_argument("--summary", action="store_true")

    cleanup = subparsers.add_parser("cleanup", help="Delete terminal action rows whose cleanup policy is due.")
    cleanup.add_argument("--older-than-seconds", type=int)
    cleanup.add_argument("--limit", type=int, default=500)
    cleanup.add_argument("--summary", action="store_true")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    settings = Settings.from_env()
    bridge = NativeBridgeActionClient(client=MysqlCliClient(), settings=settings)

    if args.command == "scope-player":
        bridge.enable_player_scope(
            player_guid=args.player_guid,
            profile=args.profile,
            enabled=not args.disable,
            reason=args.reason,
            expires_seconds=args.expires_seconds,
        )
        result: dict[str, Any] = {
            "player_guid": args.player_guid,
            "profile": args.profile,
            "enabled": not args.disable,
            "expires_seconds": args.expires_seconds,
        }
    elif args.command == "policy":
        if args.enable == args.disable:
            raise SystemExit("Pass exactly one of --enable or --disable.")
        bridge.set_action_policy(
            action_kind=args.action_kind,
            profile=args.profile,
            enabled=bool(args.enable),
            max_risk_level=args.max_risk_level,
            cooldown_ms=args.cooldown_ms,
            burst_limit=args.burst_limit,
            admin_only=args.admin_only if args.admin_only else None,
        )
        result = {
            "action_kind": args.action_kind,
            "profile": args.profile,
            "enabled": bool(args.enable),
        }
    elif args.command == "submit":
        try:
            payload = json.loads(args.payload_json)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"Invalid --payload-json: {exc}") from exc
        if not isinstance(payload, dict):
            raise SystemExit("--payload-json must be a JSON object.")
        request = bridge.submit(
            idempotency_key=args.idempotency_key,
            player_guid=args.player_guid,
            action_kind=args.action_kind,
            payload=payload,
            created_by=args.created_by,
            risk_level=args.risk_level,
            expires_seconds=args.expires_seconds,
            max_attempts=args.max_attempts,
            sequence_id=args.sequence_id,
            sequence_order=args.sequence_order,
            wait_for_prior=args.wait_for_prior,
            priority=args.priority,
            purge_after_seconds=args.purge_after_seconds,
            target_map_id=args.target_map_id,
            target_x=args.target_x,
            target_y=args.target_y,
            target_z=args.target_z,
            target_o=args.target_o,
            target_player_guid=args.target_player_guid,
        )
        if args.wait:
            request = bridge.wait(request_id=request.request_id)
        result = request.to_dict()
    elif args.command == "submit-sequence":
        try:
            actions = json.loads(args.actions_json)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"Invalid --actions-json: {exc}") from exc
        if not isinstance(actions, list) or not all(isinstance(item, dict) for item in actions):
            raise SystemExit("--actions-json must be a JSON array of objects.")
        requests = []
        for index, action in enumerate(actions):
            action_kind = str(action.get("action_kind") or "")
            if action_kind not in NATIVE_ACTION_KIND_BY_ID:
                raise SystemExit(f"Unknown native bridge action kind at index {index}: {action_kind}")
            payload = action.get("payload") if isinstance(action.get("payload"), dict) else {}
            request = bridge.submit(
                idempotency_key=str(action.get("idempotency_key") or f"{args.sequence_id}:{index}:{action_kind}"),
                player_guid=int(action.get("player_guid") or args.player_guid),
                action_kind=action_kind,
                payload=payload,
                created_by=str(action.get("created_by") or args.created_by),
                risk_level=str(action.get("risk_level") or args.risk_level),
                expires_seconds=int(action.get("expires_seconds") or args.expires_seconds),
                max_attempts=int(action.get("max_attempts") or args.max_attempts),
                sequence_id=args.sequence_id,
                sequence_order=int(action.get("sequence_order") if action.get("sequence_order") is not None else index),
                wait_for_prior=bool(action.get("wait_for_prior", index > 0)),
                priority=int(action.get("priority") or args.priority),
            )
            if args.wait:
                request = bridge.wait(request_id=request.request_id)
            requests.append(request.to_dict())
        result = {"sequence_id": args.sequence_id, "requests": requests}
    elif args.command == "inspect":
        requests = bridge.list_requests(player_guid=args.player_guid, status=args.status, limit=args.limit)
        result = {"count": len(requests), "requests": [request.to_dict() for request in requests]}
    elif args.command == "recover-stale":
        result = bridge.recover_stale_claims()
    elif args.command == "cleanup":
        result = bridge.cleanup_terminal_requests(older_than_seconds=args.older_than_seconds, limit=args.limit)
    else:
        raise SystemExit(f"Unsupported command: {args.command}")

    if args.summary:
        print(" ".join(f"{key}={_summary_value(value)}" for key, value in result.items() if key != "payload"))
    else:
        print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


def _summary_value(value: Any) -> str:
    if isinstance(value, list):
        return str(len(value))
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


if __name__ == "__main__":
    raise SystemExit(main())
