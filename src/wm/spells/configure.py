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

ENABLE_KEY = "WmSpells.Enable"
ALLOWLIST_KEY = "WmSpells.PlayerGuidAllowList"
DEBUG_ENABLE_KEY = "WmSpells.LabOnlyDebugInvokeEnable"
BONEBOUND_ENABLE_KEY = "WmSpells.BoneboundServant.Enable"
BONEBOUND_SHELL_IDS_KEY = "WmSpells.BoneboundServant.ShellSpellIds"


@dataclass(slots=True)
class WmSpellsRuntimeConfigSnapshot:
    enabled: bool
    player_guid_allowlist: list[int]
    debug_invoke_enabled: bool
    bonebound_enabled: bool
    bonebound_shell_spell_ids: list[int]


@dataclass(slots=True)
class WmSpellsConfigUpdateResult:
    config_path: str
    previous_allowlist: list[int]
    new_allowlist: list[int]
    previous_shell_spell_ids: list[int]
    new_shell_spell_ids: list[int]
    enabled: bool
    debug_invoke_enabled: bool
    bonebound_enabled: bool
    changed: bool
    reload_requested: bool
    reload_result: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_wm_spells_runtime_config(config_path: Path) -> WmSpellsRuntimeConfigSnapshot:
    if not config_path.exists():
        raise FileNotFoundError(f"WM spells config file not found: {config_path}")
    return parse_wm_spells_runtime_config(config_path.read_text(encoding="utf-8"))


def parse_wm_spells_runtime_config(config_text: str) -> WmSpellsRuntimeConfigSnapshot:
    return WmSpellsRuntimeConfigSnapshot(
        enabled=_parse_bool_option(config_text, ENABLE_KEY, default=True),
        player_guid_allowlist=_parse_int_list_option(config_text, ALLOWLIST_KEY),
        debug_invoke_enabled=_parse_bool_option(config_text, DEBUG_ENABLE_KEY, default=False),
        bonebound_enabled=_parse_bool_option(config_text, BONEBOUND_ENABLE_KEY, default=True),
        bonebound_shell_spell_ids=_parse_int_list_option(config_text, BONEBOUND_SHELL_IDS_KEY),
    )


def update_wm_spells_runtime_config(
    *,
    config_path: Path,
    player_guids: list[int] | None = None,
    shell_spell_ids: list[int] | None = None,
    append_players: bool = False,
    clear_players: bool = False,
    replace_shell_spell_ids: bool = False,
    ensure_enabled: bool = True,
    enable_debug_invoke: bool | None = None,
    ensure_bonebound_enabled: bool = True,
    write: bool = True,
) -> WmSpellsConfigUpdateResult:
    if clear_players and player_guids:
        raise ValueError("clear_players cannot be combined with player_guids")

    existing_text = config_path.read_text(encoding="utf-8") if config_path.exists() else "[worldserver]\n"
    snapshot = parse_wm_spells_runtime_config(existing_text)

    if clear_players:
        new_allowlist: list[int] = []
    elif player_guids:
        incoming = sorted({int(guid) for guid in player_guids})
        if append_players:
            new_allowlist = sorted({*snapshot.player_guid_allowlist, *incoming})
        else:
            new_allowlist = incoming
    else:
        new_allowlist = list(snapshot.player_guid_allowlist)

    if shell_spell_ids:
        incoming_shell_ids = sorted({int(spell_id) for spell_id in shell_spell_ids})
        if replace_shell_spell_ids:
            new_shell_spell_ids = incoming_shell_ids
        else:
            new_shell_spell_ids = sorted({*snapshot.bonebound_shell_spell_ids, *incoming_shell_ids})
    else:
        new_shell_spell_ids = list(snapshot.bonebound_shell_spell_ids)

    enabled = True if ensure_enabled else snapshot.enabled
    debug_invoke_enabled = snapshot.debug_invoke_enabled if enable_debug_invoke is None else bool(enable_debug_invoke)
    bonebound_enabled = True if ensure_bonebound_enabled else snapshot.bonebound_enabled

    updated_text = existing_text
    updated_text = _set_bool_option(updated_text, ENABLE_KEY, enabled)
    updated_text = _set_int_list_option(updated_text, ALLOWLIST_KEY, new_allowlist)
    updated_text = _set_bool_option(updated_text, DEBUG_ENABLE_KEY, debug_invoke_enabled)
    updated_text = _set_bool_option(updated_text, BONEBOUND_ENABLE_KEY, bonebound_enabled)
    updated_text = _set_int_list_option(updated_text, BONEBOUND_SHELL_IDS_KEY, new_shell_spell_ids)
    changed = updated_text != existing_text

    if changed and write:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(updated_text, encoding="utf-8")

    return WmSpellsConfigUpdateResult(
        config_path=str(config_path),
        previous_allowlist=list(snapshot.player_guid_allowlist),
        new_allowlist=new_allowlist,
        previous_shell_spell_ids=list(snapshot.bonebound_shell_spell_ids),
        new_shell_spell_ids=new_shell_spell_ids,
        enabled=enabled,
        debug_invoke_enabled=debug_invoke_enabled,
        bonebound_enabled=bonebound_enabled,
        changed=changed,
        reload_requested=False,
    )


def _get_config_value(config_text: str, key: str) -> str | None:
    pattern = re.compile(rf"^\s*{re.escape(key)}\s*=\s*(?P<value>.*?)\s*$")
    for line in config_text.splitlines():
        match = pattern.match(line)
        if match:
            return match.group("value")
    return None


def _parse_bool_option(config_text: str, key: str, *, default: bool) -> bool:
    raw = _get_config_value(config_text, key)
    if raw is None:
        return default
    normalized = _strip_config_quotes(raw.strip()).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def _parse_int_list_option(config_text: str, key: str) -> list[int]:
    raw = _get_config_value(config_text, key)
    if raw is None:
        return []
    values: list[int] = []
    for token in _strip_config_quotes(raw.strip()).split(","):
        token = token.strip()
        if not token:
            continue
        try:
            values.append(int(token))
        except ValueError:
            continue
    return sorted(set(values))


def _set_bool_option(config_text: str, key: str, value: bool) -> str:
    rendered = f"{key} = {1 if value else 0}"
    return _set_config_line(config_text, key=key, rendered=rendered)


def _set_int_list_option(config_text: str, key: str, values: list[int]) -> str:
    rendered = f'{key} = "{",".join(str(int(value)) for value in sorted(set(values)))}"'
    return _set_config_line(config_text, key=key, rendered=rendered)


def _set_config_line(config_text: str, *, key: str, rendered: str) -> str:
    pattern = re.compile(rf"^\s*{re.escape(key)}\s*=\s*.*?$")
    lines = config_text.splitlines()
    output: list[str] = []
    replaced = False
    for line in lines:
        if pattern.match(line):
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


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Update mod-wm-spells runtime config and optionally reload worldserver config.")
    parser.add_argument("--config-path", type=Path)
    parser.add_argument("--player-guid", type=int, action="append", default=[])
    parser.add_argument("--append", action="store_true")
    parser.add_argument("--clear", action="store_true")
    parser.add_argument("--shell-spell-id", type=int, action="append", default=[])
    parser.add_argument("--replace-shell-spell-ids", action="store_true")
    parser.add_argument("--enable-debug-invoke", action="store_true")
    parser.add_argument("--disable-debug-invoke", action="store_true")
    parser.add_argument("--no-enable", action="store_true")
    parser.add_argument("--no-bonebound-enable", action="store_true")
    parser.add_argument("--reload-via-soap", action="store_true")
    parser.add_argument("--reload-command", default=".reload config")
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--output-json", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    settings = Settings.from_env()
    enable_debug = None
    if args.enable_debug_invoke:
        enable_debug = True
    elif args.disable_debug_invoke:
        enable_debug = False
    result = update_wm_spells_runtime_config(
        config_path=args.config_path or Path(settings.wm_spells_config_path),
        player_guids=[int(guid) for guid in args.player_guid],
        shell_spell_ids=[int(spell_id) for spell_id in args.shell_spell_id],
        append_players=bool(args.append),
        clear_players=bool(args.clear),
        replace_shell_spell_ids=bool(args.replace_shell_spell_ids),
        ensure_enabled=not bool(args.no_enable),
        enable_debug_invoke=enable_debug,
        ensure_bonebound_enabled=not bool(args.no_bonebound_enable),
        write=True,
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
            f"allowlist={','.join(str(v) for v in result.new_allowlist) or '<empty>'} "
            f"shell_spell_ids={','.join(str(v) for v in result.new_shell_spell_ids) or '<empty>'} "
            f"debug_invoke_enabled={str(bool(result.debug_invoke_enabled)).lower()} "
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


if __name__ == "__main__":
    raise SystemExit(main())
