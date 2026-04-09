from __future__ import annotations

import argparse
import time

from wm.config import Settings
from wm.db.mysql_cli import MysqlCliClient
from wm.events.adapters import ADAPTER_CHOICES
from wm.events.store import EventStore
from wm.events.run import _apply_settings_overrides
from wm.events.run import _emit_output
from wm.events.run import _validate_run_arguments
from wm.events.run import execute_event_spine
from wm.sources.addon_log import arm_addon_log_cursor
from wm.sources.combat_log import arm_combat_log_cursor


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Continuously run the WM event spine.")
    parser.add_argument("--adapter", choices=ADAPTER_CHOICES, default="addon_log")
    parser.add_argument("--mode", choices=["dry-run", "apply"], default="apply")
    parser.add_argument("--batch-size", type=int)
    parser.add_argument("--player-guid", type=int)
    parser.add_argument("--questgiver-entry", type=int)
    parser.add_argument("--confirm-live-apply", action="store_true")
    parser.add_argument("--interval-seconds", type=float, default=2.0)
    parser.add_argument("--max-iterations", type=int)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--print-idle", action="store_true")
    parser.add_argument("--arm-from-end", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    settings = Settings.from_env()
    _apply_settings_overrides(args=args, settings=settings)
    _validate_run_arguments(args=args, settings=settings)

    if args.arm_from_end:
        client = MysqlCliClient()
        store = EventStore(client=client, settings=settings)
        if args.adapter == "combat_log":
            arm_result = arm_combat_log_cursor(settings=settings, store=store)
        elif args.adapter == "addon_log":
            arm_result = arm_addon_log_cursor(settings=settings, store=store)
        else:
            raise SystemExit("--arm-from-end is only supported with --adapter addon_log or --adapter combat_log.")
        if args.summary:
            print(
                f"armed_from_end=true file_exists={arm_result.file_exists} "
                f"previous_offset={arm_result.previous_offset} armed_offset={arm_result.armed_offset}"
            )

    iteration = 0
    try:
        while True:
            iteration += 1
            payload = execute_event_spine(
                settings=settings,
                adapter_name=args.adapter,
                mode=args.mode,
                player_guid=args.player_guid,
                batch_size=args.batch_size,
            )
            payload["confirm_live_apply"] = args.confirm_live_apply
            payload["iteration"] = iteration

            if args.summary and (_has_activity(payload) or args.print_idle):
                _emit_output(payload=payload, summary=True, output_json=None)

            if args.max_iterations is not None and iteration >= int(args.max_iterations):
                break
            time.sleep(max(float(args.interval_seconds), 0.1))
    except KeyboardInterrupt:
        if args.summary:
            print("watch_stopped=true")
        return 130

    return 0


def _has_activity(payload: dict[str, object]) -> bool:
    counters = (
        "polled_count",
        "recorded_count",
        "runtime_state_event_count",
        "runtime_state_recorded_count",
        "projected_count",
        "derived_event_count",
        "opportunity_count",
        "plan_count",
        "execution_count",
    )
    return any(int(payload.get(key) or 0) > 0 for key in counters)


if __name__ == "__main__":
    raise SystemExit(main())
