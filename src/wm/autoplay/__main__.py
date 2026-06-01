from __future__ import annotations

import argparse
import json
from pathlib import Path

from wm.autoplay.service import AutoplayRuntimeConfig
from wm.autoplay.service import AutoplayService
from wm.autoplay.service import status_summary
from wm.autoplay.state import AutoplayStateStore


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m wm.autoplay", description="Run the local WM autoplay service.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run = subparsers.add_parser("run", help="Run autoplay until stopped.")
    run.add_argument("--player-guid", type=int)
    run.add_argument("--interval-seconds", type=float, default=2.0)
    run.add_argument("--state-root", type=Path, default=None)
    run.add_argument("--project-root", type=Path, default=Path.cwd())
    run.add_argument("--lab-mysql-port", type=int, default=33307)
    run.add_argument("--soap-port", type=int, default=7879)
    run.add_argument("--once", action="store_true")
    run.add_argument("--no-start-watcher", action="store_true")
    run.add_argument("--no-llm", action="store_true")
    run.add_argument("--no-llm-chat", action="store_true")
    run.add_argument("--llm-lanes", default=None, help="Comma-separated lanes: chat,quest,item,spell,ability,scene,action.")
    run.add_argument("--llm-model", default=None)
    run.add_argument("--llm-base-url", default=None)
    run.add_argument("--llm-event-age-seconds", type=int, default=300)
    run.add_argument("--llm-cooldown-seconds", type=int, default=60)
    run.add_argument("--llm-events-per-tick", type=int, default=1)
    run.add_argument("--summary", action="store_true")

    status = subparsers.add_parser("status", help="Print autoplay status.")
    status.add_argument("--state-root", type=Path, default=None)
    status.add_argument("--summary", action="store_true")

    stop = subparsers.add_parser("stop", help="Request autoplay stop.")
    stop.add_argument("--state-root", type=Path, default=None)
    stop.add_argument("--summary", action="store_true")

    pause = subparsers.add_parser("pause", help="Pause autoplay.")
    pause.add_argument("--state-root", type=Path, default=None)
    pause.add_argument("--summary", action="store_true")

    resume = subparsers.add_parser("resume", help="Resume autoplay.")
    resume.add_argument("--state-root", type=Path, default=None)
    resume.add_argument("--summary", action="store_true")

    configure = subparsers.add_parser("configure", help="Update autoplay LLM controls for the running service.")
    configure.add_argument("--state-root", type=Path, default=None)
    llm_toggle = configure.add_mutually_exclusive_group()
    llm_toggle.add_argument("--llm-enabled", action="store_true")
    llm_toggle.add_argument("--llm-disabled", action="store_true")
    chat_toggle = configure.add_mutually_exclusive_group()
    chat_toggle.add_argument("--llm-chat-enabled", action="store_true")
    chat_toggle.add_argument("--llm-chat-disabled", action="store_true")
    configure.add_argument("--llm-lanes", default=None, help="Comma-separated lanes: chat,quest,item,spell,ability,scene,action.")
    configure.add_argument("--llm-model", default=None)
    configure.add_argument("--llm-base-url", default=None)
    configure.add_argument("--llm-event-age-seconds", type=int)
    configure.add_argument("--llm-cooldown-seconds", type=int)
    configure.add_argument("--llm-events-per-tick", type=int)
    configure.add_argument("--summary", action="store_true")

    generate = subparsers.add_parser("generate", help="Generate one LLM autoplay draft from the latest eligible event.")
    generate.add_argument("--player-guid", type=int, required=True)
    generate.add_argument("--lane", choices=["quest", "item", "spell", "ability", "scene", "action"])
    generate.add_argument("--event-id", type=int)
    generate.add_argument("--source-event-key")
    generate.add_argument("--state-root", type=Path, default=None)
    generate.add_argument("--project-root", type=Path, default=Path.cwd())
    generate.add_argument("--llm-model", default=None)
    generate.add_argument("--llm-base-url", default=None)
    generate.add_argument("--summary", action="store_true")

    chat = subparsers.add_parser("chat", help="Ask the local WM LLM a direct question and send the reply in-game.")
    chat.add_argument("--player-guid", type=int, required=True)
    chat.add_argument("--message", required=True)
    chat.add_argument("--state-root", type=Path, default=None)
    chat.add_argument("--project-root", type=Path, default=Path.cwd())
    chat.add_argument("--llm-model", default=None)
    chat.add_argument("--llm-base-url", default=None)
    chat.add_argument("--summary", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    store = AutoplayStateStore(args.state_root) if args.state_root is not None else AutoplayStateStore()

    if args.command == "status":
        status = store.load_status()
        print(status_summary(status) if args.summary else json.dumps(status, indent=2, ensure_ascii=False))
        return 0
    if args.command == "stop":
        status = store.request_stop()
        print(status_summary(status) if args.summary else json.dumps(status, indent=2, ensure_ascii=False))
        return 0
    if args.command == "pause":
        status = store.set_paused(True)
        print(status_summary(status) if args.summary else json.dumps(status, indent=2, ensure_ascii=False))
        return 0
    if args.command == "resume":
        status = store.set_paused(False)
        print(status_summary(status) if args.summary else json.dumps(status, indent=2, ensure_ascii=False))
        return 0
    if args.command == "configure":
        updates = {
            "llm_enabled": True if args.llm_enabled else False if args.llm_disabled else None,
            "llm_chat_enabled": True if args.llm_chat_enabled else False if args.llm_chat_disabled else None,
            "llm_lanes": _split_lanes(args.llm_lanes) if args.llm_lanes else None,
            "llm_model": args.llm_model,
            "llm_base_url": args.llm_base_url,
            "llm_event_age_seconds": args.llm_event_age_seconds,
            "llm_cooldown_seconds": args.llm_cooldown_seconds,
            "llm_events_per_tick": args.llm_events_per_tick,
        }
        status = store.configure(updates)
        print(status_summary(status) if args.summary else json.dumps(status, indent=2, ensure_ascii=False))
        return 0
    if args.command == "generate":
        config = AutoplayRuntimeConfig(
            player_guid=args.player_guid,
            project_root=args.project_root.resolve(),
            start_watcher=False,
            llm_model=args.llm_model,
            llm_base_url=args.llm_base_url,
            llm_lanes=tuple([args.lane] if args.lane else ("chat", "scene", "action")),
        )
        result = AutoplayService(store=store).generate_once(
            config=config,
            lane=args.lane,
            event_id=args.event_id,
            source_event_key=args.source_event_key,
        )
        if args.summary:
            if "results" in result:
                print(f"ok={str(bool(result.get('ok'))).lower()} count={len(result.get('results') or [])}")
            else:
                inner = result.get("result") if isinstance(result.get("result"), dict) else {}
                print(f"ok={str(bool(result.get('ok'))).lower()} lane={inner.get('lane')} draft_id={inner.get('draft_id')}")
        else:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result.get("ok") else 2
    if args.command == "chat":
        config = AutoplayRuntimeConfig(
            player_guid=args.player_guid,
            project_root=args.project_root.resolve(),
            start_watcher=False,
            llm_model=args.llm_model,
            llm_base_url=args.llm_base_url,
        )
        result = AutoplayService(store=store).chat_once(config=config, message=args.message)
        if args.summary:
            reply = result.get("reply") if isinstance(result.get("reply"), dict) else {}
            print(f"ok={str(bool(result.get('ok'))).lower()} message={reply.get('message') or result.get('error')}")
        else:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result.get("ok") else 2
    if args.command == "run":
        config = AutoplayRuntimeConfig(
            player_guid=args.player_guid,
            interval_seconds=args.interval_seconds,
            start_watcher=not bool(args.no_start_watcher),
            bridge_lab_mysql_port=args.lab_mysql_port,
            soap_port=args.soap_port,
            project_root=args.project_root.resolve(),
            llm_enabled=not bool(args.no_llm),
            llm_chat_enabled=not bool(args.no_llm_chat),
            llm_lanes=tuple(_split_lanes(args.llm_lanes) if args.llm_lanes else ("chat", "scene", "action")),
            llm_event_age_seconds=int(args.llm_event_age_seconds),
            llm_cooldown_seconds=int(args.llm_cooldown_seconds),
            llm_events_per_tick=int(args.llm_events_per_tick),
            llm_model=args.llm_model,
            llm_base_url=args.llm_base_url,
        )
        code = AutoplayService(store=store).run_forever(config=config, once=bool(args.once))
        if args.summary:
            print(status_summary(store.load_status()))
        return code
    raise SystemExit(f"Unsupported command: {args.command}")


def _split_lanes(raw: str) -> list[str]:
    return [item.strip() for item in str(raw).split(",") if item.strip()]


if __name__ == "__main__":
    raise SystemExit(main())
