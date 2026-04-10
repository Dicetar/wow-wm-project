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
    submit.add_argument("--wait", action="store_true")
    submit.add_argument("--summary", action="store_true")

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
        )
        if args.wait:
            request = bridge.wait(request_id=request.request_id)
        result = request.to_dict()
    else:
        raise SystemExit(f"Unsupported command: {args.command}")

    if args.summary:
        print(" ".join(f"{key}={value}" for key, value in result.items() if key != "payload"))
    else:
        print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
