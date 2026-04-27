from __future__ import annotations

import argparse
import sys
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
from wm.sources.native_bridge.arm import arm_native_bridge_cursor


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
    parser.add_argument("--mark-existing-evaluated-on-arm", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    settings = Settings.from_env()
    _apply_settings_overrides(args=args, settings=settings)
    _validate_run_arguments(args=args, settings=settings)
    if args.mark_existing_evaluated_on_arm and not args.arm_from_end:
        raise SystemExit("--mark-existing-evaluated-on-arm requires --arm-from-end.")

    if args.arm_from_end:
        client = MysqlCliClient()
        store = EventStore(client=client, settings=settings)
        existing_max_event_id = store.max_observed_event_id(player_guid=args.player_guid)
        if args.adapter == "combat_log":
            arm_result = arm_combat_log_cursor(settings=settings, store=store)
        elif args.adapter == "addon_log":
            arm_result = arm_addon_log_cursor(settings=settings, store=store)
        elif args.adapter == "native_bridge":
            arm_result = arm_native_bridge_cursor(
                settings=settings,
                store=store,
                player_guid=args.player_guid,
                client=client,
            )
        else:
            raise SystemExit(
                "--arm-from-end is only supported with --adapter addon_log, --adapter combat_log, or --adapter native_bridge."
            )
        marked_existing_evaluated = 0
        if args.mark_existing_evaluated_on_arm:
            marked_existing_evaluated = store.mark_unevaluated_observed_events_evaluated(
                player_guid=args.player_guid,
                max_event_id=existing_max_event_id,
            )
        if args.summary:
            if args.adapter == "native_bridge":
                print(
                    f"armed_from_end=true table_exists={arm_result.table_exists} "
                    f"player_guid={arm_result.player_guid} previous_last_seen={arm_result.previous_last_seen} "
                    f"armed_last_seen={arm_result.armed_last_seen} "
                    f"marked_existing_evaluated={marked_existing_evaluated}",
                    flush=True,
                )
            else:
                print(
                    f"armed_from_end=true file_exists={arm_result.file_exists} "
                    f"previous_offset={arm_result.previous_offset} armed_offset={arm_result.armed_offset} "
                    f"marked_existing_evaluated={marked_existing_evaluated}",
                    flush=True,
                )

    iteration = 0
    try:
        while True:
            iteration += 1
            try:
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
            except KeyboardInterrupt:
                raise
            except (Exception, SystemExit) as exc:
                _emit_watch_iteration_error(
                    iteration=iteration,
                    adapter_name=args.adapter,
                    mode=args.mode,
                    player_guid=args.player_guid,
                    exc=exc,
                )
                if args.max_iterations is not None and iteration >= int(args.max_iterations):
                    break
                time.sleep(max(float(args.interval_seconds), 0.1))
                continue

            if args.max_iterations is not None and iteration >= int(args.max_iterations):
                break
            time.sleep(max(float(args.interval_seconds), 0.1))
    except KeyboardInterrupt:
        if args.summary:
            print("watch_stopped=true", flush=True)
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


def _emit_watch_iteration_error(
    *,
    iteration: int,
    adapter_name: str,
    mode: str,
    player_guid: int | None,
    exc: BaseException,
) -> None:
    message = str(exc).strip() or repr(exc)
    message = message.replace("\r", " ").replace("\n", " ")
    print(
        f"watch_iteration_failed=true iteration={iteration} adapter={adapter_name} "
        f"mode={mode} player_guid={player_guid} error_type={type(exc).__name__} error={message}",
        file=sys.stderr,
        flush=True,
    )


if __name__ == "__main__":
    raise SystemExit(main())
