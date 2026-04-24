from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
import sys
from typing import Any

from wm.config import Settings
from wm.db.mysql_cli import MysqlCliClient
from wm.runtime_sync import RuntimeSyncResult, sync_runtime_after_publish
from wm.spells.publish import SpellPublisher, _demo_draft, load_managed_spell_draft


@dataclass(slots=True)
class LiveSpellPublishResult:
    mode: str
    publish: dict[str, Any]
    runtime_sync: dict[str, Any]
    restart_recommended: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _sync_runtime(*, settings: Settings, mode: str, runtime_sync_mode: str, soap_commands: list[str]) -> RuntimeSyncResult:
    return sync_runtime_after_publish(
        settings=settings,
        mode=mode,
        runtime_sync_mode=runtime_sync_mode,
        soap_commands=soap_commands,
        no_sync_note=(
            "Spell-side rows were published to the live DB. "
            "No runtime reload command was sent; restart worldserver or use a known realm-specific reload path before judging live state."
        ),
        synced_note=(
            "Managed spell rows were published and the supplied runtime command(s) were sent. "
            "Because spell-helper reload behavior is core/module-specific, restart worldserver if live state stays stale."
        ),
    )


def _render_summary(result: LiveSpellPublishResult) -> str:
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
    issues = list(publish.get("validation", {}).get("issues", [])) + list(publish.get("preflight", {}).get("issues", []))
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


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m wm.spells.live_publish")
    parser.add_argument("--draft-json", type=Path, help="Path to a managed spell draft JSON file.")
    parser.add_argument("--demo", action="store_true", help="Use the built-in managed spell demo draft.")
    parser.add_argument("--mode", choices=["dry-run", "apply"], default="dry-run")
    parser.add_argument("--runtime-sync", choices=["auto", "off", "soap"], default="auto")
    parser.add_argument(
        "--soap-command",
        action="append",
        default=[],
        help="SOAP command to send after apply. Repeat for multiple commands.",
    )
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--output-json", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if not args.demo and args.draft_json is None:
        parser.error("Provide --draft-json PATH or use --demo.")

    draft = _demo_draft() if args.demo else load_managed_spell_draft(args.draft_json)
    settings = Settings.from_env()
    client = MysqlCliClient()
    publisher = SpellPublisher(client=client, settings=settings)
    publish_result = publisher.publish(draft=draft, mode=args.mode)
    runtime_sync_result = _sync_runtime(
        settings=settings,
        mode=args.mode,
        runtime_sync_mode=args.runtime_sync,
        soap_commands=[str(command) for command in args.soap_command],
    )
    result = LiveSpellPublishResult(
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

    publish_ok = bool(publish_result.validation.get("ok", False) and publish_result.preflight.get("ok", False))
    if args.mode == "apply":
        publish_ok = publish_ok and bool(publish_result.applied)
    runtime_ok = bool(runtime_sync_result.overall_ok)
    return 0 if publish_ok and runtime_ok else 2


if __name__ == "__main__":
    sys.exit(main())
