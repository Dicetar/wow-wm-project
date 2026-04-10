from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
from typing import Any

from wm.config import Settings
from wm.runtime_sync.soap import RuntimeCommandResult
from wm.runtime_sync.soap import SoapRuntimeClient

ALLOWLIST_KEY = "WmBridge.PlayerGuidAllowList"
ALLOWLIST_RE = re.compile(r"^(?P<prefix>\s*WmBridge\.PlayerGuidAllowList\s*=\s*)(?P<value>.*?)(?P<suffix>\s*)$")


@dataclass(slots=True)
class BridgeConfigUpdateResult:
    config_path: str
    previous_allowlist: list[int]
    new_allowlist: list[int]
    changed: bool
    reload_requested: bool
    reload_result: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def update_bridge_player_allowlist(
    *,
    config_path: Path,
    player_guids: list[int],
    append: bool = False,
    clear: bool = False,
) -> BridgeConfigUpdateResult:
    if clear and player_guids:
        raise ValueError("clear cannot be combined with player_guids")
    if not clear and not player_guids:
        raise ValueError("player_guids are required unless clear is true")

    existing_text = config_path.read_text(encoding="utf-8") if config_path.exists() else "[worldserver]\n"
    previous_allowlist = parse_allowlist(existing_text)
    if clear:
        new_allowlist: list[int] = []
    elif append:
        new_allowlist = sorted({*previous_allowlist, *[int(guid) for guid in player_guids]})
    else:
        new_allowlist = sorted({int(guid) for guid in player_guids})

    updated_text = set_allowlist(existing_text, new_allowlist)
    changed = updated_text != existing_text
    if changed:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(updated_text, encoding="utf-8")

    return BridgeConfigUpdateResult(
        config_path=str(config_path),
        previous_allowlist=previous_allowlist,
        new_allowlist=new_allowlist,
        changed=changed,
        reload_requested=False,
    )


def parse_allowlist(config_text: str) -> list[int]:
    for line in config_text.splitlines():
        match = ALLOWLIST_RE.match(line)
        if not match:
            continue
        raw_value = _strip_config_quotes(match.group("value").strip())
        values: list[int] = []
        for token in raw_value.split(","):
            token = token.strip()
            if not token or token == "*":
                continue
            try:
                values.append(int(token))
            except ValueError:
                continue
        return sorted(set(values))
    return []


def set_allowlist(config_text: str, player_guids: list[int]) -> str:
    rendered = f'{ALLOWLIST_KEY} = "{",".join(str(int(guid)) for guid in sorted(set(player_guids)))}"'
    lines = config_text.splitlines()
    output: list[str] = []
    replaced = False
    for line in lines:
        if ALLOWLIST_RE.match(line):
            output.append(rendered)
            replaced = True
        else:
            output.append(line)

    if not replaced:
        if output and output[-1].strip():
            output.append("")
        output.append(rendered)

    return "\n".join(output) + "\n"


def _strip_config_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        return value[1:-1]
    return value


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Update mod-wm-bridge player allowlist and optionally reload config.")
    parser.add_argument("--config-path", type=Path)
    parser.add_argument("--player-guid", type=int, action="append", default=[])
    parser.add_argument("--append", action="store_true")
    parser.add_argument("--clear", action="store_true")
    parser.add_argument("--reload-via-soap", action="store_true")
    parser.add_argument("--reload-command", default=".reload config")
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--output-json", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    settings = Settings.from_env()
    config_path = args.config_path or Path(settings.wm_bridge_config_path)
    result = update_bridge_player_allowlist(
        config_path=config_path,
        player_guids=[int(guid) for guid in args.player_guid],
        append=bool(args.append),
        clear=bool(args.clear),
    )
    if args.reload_via_soap:
        command_result = _reload_config_via_soap(settings=settings, command=str(args.reload_command))
        result.reload_requested = True
        result.reload_result = command_result.to_dict()

    payload = result.to_dict()
    raw = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.output_json is not None:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(raw, encoding="utf-8")
    if args.summary:
        print(
            f"config_path={payload['config_path']} changed={payload['changed']} "
            f"previous={','.join(str(v) for v in result.previous_allowlist) or '<empty>'} "
            f"new={','.join(str(v) for v in result.new_allowlist) or '<empty>'} "
            f"reload_requested={result.reload_requested}"
        )
        if result.reload_result is not None:
            print(
                f"reload_ok={result.reload_result.get('ok')} "
                f"fault={result.reload_result.get('fault_string') or result.reload_result.get('fault_code') or ''}"
            )
    else:
        print(raw)
    return 0


def _reload_config_via_soap(*, settings: Settings, command: str) -> RuntimeCommandResult:
    if not settings.soap_enabled:
        return RuntimeCommandResult(
            command=command,
            ok=False,
            fault_code="SOAPDisabled",
            fault_string="Set WM_SOAP_ENABLED=1 to reload config through SOAP.",
        )
    result = SoapRuntimeClient(settings=settings).execute_command(command)
    result.command = command
    return result


if __name__ == "__main__":
    raise SystemExit(main())
