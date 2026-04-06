from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
import sys
from typing import Any

from wm.config import Settings
from wm.db.mysql_cli import MysqlCliClient
from wm.quests.publish import QuestPublisher, load_bounty_quest_draft
from wm.runtime_sync import RuntimeCommandResult, RuntimeSyncResult, SoapRuntimeClient, build_default_quest_reload_commands


@dataclass(slots=True)
class LivePublishResult:
    mode: str
    publish: dict[str, Any]
    runtime_sync: dict[str, Any]
    restart_recommended: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m wm.quests.live_publish")
    parser.add_argument("--draft-json", type=Path, required=True)
    parser.add_argument("--mode", choices=["dry-run", "apply"], default="dry-run")
    parser.add_argument("--runtime-sync", choices=["auto", "off", "soap"], default="auto")
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--output-json", type=Path)
    return parser


def _sync_runtime(*, draft: Any, settings: Settings, mode: str, runtime_sync_mode: str) -> RuntimeSyncResult:
    if mode != "apply":
        return RuntimeSyncResult(
            protocol="none",
            enabled=False,
            overall_ok=True,
            restart_recommended=False,
            note="Dry-run mode does not touch the live runtime.",
        )

    enabled = runtime_sync_mode == "soap" or (runtime_sync_mode == "auto" and settings.soap_enabled)
    if not enabled:
        return RuntimeSyncResult(
            protocol="none",
            enabled=False,
            overall_ok=True,
            restart_recommended=True,
            note="Runtime sync is disabled. Restart worldserver before testing the quest.",
        )

    if not settings.soap_user or not settings.soap_password:
        return RuntimeSyncResult(
            protocol="soap",
            enabled=True,
            overall_ok=False,
            restart_recommended=True,
            note="SOAP runtime sync was requested but WM_SOAP_USER / WM_SOAP_PASSWORD are not configured.",
        )

    client = SoapRuntimeClient(settings=settings)
    commands = build_default_quest_reload_commands(questgiver_entry=draft.questgiver_entry)
    results: list[RuntimeCommandResult] = []
    overall_ok = True
    for command in commands:
        result = client.execute_command(command)
        result.command = command
        results.append(result)
        if not result.ok:
            overall_ok = False

    return RuntimeSyncResult(
        protocol="soap",
        enabled=True,
        overall_ok=overall_ok,
        commands=results,
        restart_recommended=True,
        note=(
            "Quest rows were published and reload commands were sent. "
            "For new quests or objective-behavior changes, restart worldserver before serious testing."
        ),
    )


def _render_summary(result: LivePublishResult) -> str:
    publish = result.publish
    runtime_sync = result.runtime_sync
    lines = [
        f"mode: {result.mode}",
        f"applied: {str(bool(publish.get('applied', False))).lower()}",
        f"validation.ok: {str(bool(publish.get('validation', {}).get('ok', False))).lower()}",
        f"preflight.ok: {str(bool(publish.get('preflight', {}).get('ok', False))).lower()}",
        f"runtime_sync.enabled: {str(bool(runtime_sync.get('enabled', False))).lower()}",
        f"runtime_sync.protocol: {runtime_sync.get('protocol')}",
        f"runtime_sync.overall_ok: {str(bool(runtime_sync.get('overall_ok', False))).lower()}",
        f"restart_recommended: {str(bool(result.restart_recommended)).lower()}",
        "",
        "issues:",
    ]
    issues = publish.get("preflight", {}).get("issues", [])
    if not issues:
        lines.append("- none")
    else:
        for issue in issues:
            lines.append(f"- {issue.get('path')} | {issue.get('severity')} | {issue.get('message')}")
    lines.extend(["", "runtime_commands:"])
    commands = runtime_sync.get("commands", [])
    if not commands:
        lines.append("- none")
    else:
        for command in commands:
            if command.get("ok"):
                preview = str(command.get("result") or "").strip().splitlines()
                preview_text = preview[0] if preview else "ok"
                lines.append(f"- ok | {command.get('command')} | {preview_text}")
            else:
                lines.append(
                    f"- fail | {command.get('command')} | {command.get('fault_string') or command.get('fault_code')}"
                )
    if runtime_sync.get("note"):
        lines.extend(["", f"note: {runtime_sync.get('note')}"])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    settings = Settings.from_env()
    client = MysqlCliClient()
    publisher = QuestPublisher(client=client, settings=settings)
    draft = load_bounty_quest_draft(args.draft_json)
    publish_result = publisher.publish(draft=draft, mode=args.mode)
    runtime_sync_result = _sync_runtime(
        draft=draft,
        settings=settings,
        mode=args.mode,
        runtime_sync_mode=args.runtime_sync,
    )
    result = LivePublishResult(
        mode=args.mode,
        publish=publish_result.to_dict(),
        runtime_sync=runtime_sync_result.to_dict(),
        restart_recommended=bool(runtime_sync_result.restart_recommended),
    )
    raw = json.dumps(result.to_dict(), indent=2, ensure_ascii=False)
    if args.output_json is not None:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(raw, encoding="utf-8")
    if args.summary or args.output_json is not None:
        print(_render_summary(result))
        if args.output_json is not None:
            print("")
            print(f"output_json: {args.output_json}")
    else:
        print(raw)
    publish_ok = bool(publish_result.preflight.get("ok", False) and publish_result.validation.get("ok", False))
    runtime_ok = bool(runtime_sync_result.overall_ok)
    return 0 if publish_ok and runtime_ok else 2


if __name__ == "__main__":
    sys.exit(main())
