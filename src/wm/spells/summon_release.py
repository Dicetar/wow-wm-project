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

DEFAULT_BONEBOUND_TWINS_BEHAVIOR_KIND = "summon_bonebound_alpha_v3"
DEFAULT_BONEBOUND_TWINS_SHELL_SPELL_ID = 940001


@dataclass(slots=True)
class ReleaseSummonResult:
    mode: str
    ok: bool
    executed: bool
    player_guid: int
    behavior_kind: str
    shell_spell_id: int
    request_id: int | None = None
    status: str = "not_submitted"
    result: dict[str, Any] | None = None
    error_text: str | None = None
    notes: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def submit_release_summon(
    *,
    client: MysqlCliClient,
    settings: Settings,
    player_guid: int,
    behavior_kind: str = DEFAULT_BONEBOUND_TWINS_BEHAVIOR_KIND,
    shell_spell_id: int = DEFAULT_BONEBOUND_TWINS_SHELL_SPELL_ID,
    mode: str = "apply",
    wait: bool = False,
    timeout_seconds: float | None = None,
) -> ReleaseSummonResult:
    if mode not in {"dry-run", "apply"}:
        raise ValueError(f"Unsupported release summon mode: {mode}")

    player_guid = int(player_guid)
    shell_spell_id = int(shell_spell_id)
    behavior_kind = str(behavior_kind)
    payload = {"shell_spell_id": shell_spell_id}
    notes = [
        "release_lane=true",
        "no_preflight=true",
        "submit_only=true" if not wait else "post_submit_wait=true",
    ]

    if mode == "dry-run":
        return ReleaseSummonResult(
            mode=mode,
            ok=True,
            executed=False,
            player_guid=player_guid,
            behavior_kind=behavior_kind,
            shell_spell_id=shell_spell_id,
            status="dry_run",
            notes=notes,
        )

    debug_client = SpellBehaviorDebugClient(client=client, settings=settings)
    request_id = debug_client.submit_fast(player_guid=player_guid, behavior_kind=behavior_kind, payload=payload)
    if not wait:
        return ReleaseSummonResult(
            mode=mode,
            ok=True,
            executed=True,
            player_guid=player_guid,
            behavior_kind=behavior_kind,
            shell_spell_id=shell_spell_id,
            request_id=request_id,
            status="pending",
            notes=notes,
        )

    deadline = time.time() + (float(timeout_seconds) if timeout_seconds is not None else settings.native_bridge_action_wait_seconds)
    current = debug_client.get(request_id=request_id)
    while current is not None and current.status not in {"done", "failed", "rejected", "expired"} and time.time() < deadline:
        time.sleep(max(settings.native_bridge_action_poll_seconds, 0.05))
        current = debug_client.get(request_id=request_id)

    if current is None:
        return ReleaseSummonResult(
            mode=mode,
            ok=False,
            executed=True,
            player_guid=player_guid,
            behavior_kind=behavior_kind,
            shell_spell_id=shell_spell_id,
            request_id=request_id,
            status="unknown",
            error_text="request_not_found_after_submit",
            notes=notes,
        )

    ok = current.status == "done" and bool(current.result.get("ok", True))
    return ReleaseSummonResult(
        mode=mode,
        ok=ok,
        executed=True,
        player_guid=player_guid,
        behavior_kind=behavior_kind,
        shell_spell_id=shell_spell_id,
        request_id=request_id,
        status=current.status,
        result=current.result,
        error_text=current.error_text,
        notes=notes,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Fast release lane for proven WM summons. This submits the summon request directly "
            "and skips shell-bank lookup, player lookup, preflight, and default wait/poll checks."
        )
    )
    parser.add_argument("--player-guid", type=int, required=True)
    parser.add_argument("--shell-spell-id", type=int, default=DEFAULT_BONEBOUND_TWINS_SHELL_SPELL_ID)
    parser.add_argument("--behavior-kind", default=DEFAULT_BONEBOUND_TWINS_BEHAVIOR_KIND)
    parser.add_argument("--mode", choices=["dry-run", "apply"], default="apply")
    parser.add_argument("--wait", action="store_true", help="Optional post-submit wait for completion; not used by the fastest path.")
    parser.add_argument("--timeout-seconds", type=float)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--output-json", type=Path)
    return parser


def _print_summary(result: ReleaseSummonResult) -> None:
    print(
        f"mode={result.mode} ok={str(result.ok).lower()} executed={str(result.executed).lower()} "
        f"release_lane=true player_guid={result.player_guid} shell_spell_id={result.shell_spell_id} "
        f"behavior_kind={result.behavior_kind} status={result.status} "
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
    result = submit_release_summon(
        client=MysqlCliClient(),
        settings=settings,
        player_guid=int(args.player_guid),
        behavior_kind=str(args.behavior_kind),
        shell_spell_id=int(args.shell_spell_id),
        mode=str(args.mode),
        wait=bool(args.wait),
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
