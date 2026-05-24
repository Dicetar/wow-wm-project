"""Unified client+server WM shell-spell DBC publish.

One coherent lane that replaces the two drifting paths (the server staging
script and the separate client build). It materializes both the server and
client Spell.dbc for the same shell ids from the *same* shell bank, verifies
the two rows agree on name/icon/duration (via the shell audit), and only then
stages the server Spell.dbc into the DataDir (backing up the prior file) and
queues the client MPQ rebuild for the close-watcher.

Staging is gated on verification: a shell the audit reports BROKEN never reaches
the live DataDir."""
from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from wm.spells.client_patch import materialize_client_spell_dbc
from wm.spells.client_patch_pending import mark_pending
from wm.spells.server_dbc import materialize_server_spell_dbc
from wm.spells.shell_audit import audit_spell_shells


@dataclass(slots=True)
class UnifiedPublishResult:
    selected_spell_ids: list[int]
    verified: bool
    staged: bool
    audit_status: str
    server_out: str
    client_out: str
    target_server_dbc: str
    backup_path: str | None = None
    audit_issues: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def publish_spell_dbc(
    *,
    spell_ids: list[int],
    source_dbc: str | Path,
    server_out: str | Path,
    client_out: str | Path,
    target_server_dbc: str | Path,
    backup_dir: str | Path,
    include: str = "named",
    seed_profile: str = "castable",
    shell_bank_path: str | Path | None = None,
    source_spell_icon_dbc: str | Path | None = None,
    apply: bool = False,
    pending_path: str | Path | None = None,
    mark_pending_fn: Callable[..., Any] = mark_pending,
) -> UnifiedPublishResult:
    selected = [int(spell_id) for spell_id in spell_ids]

    server_result = materialize_server_spell_dbc(
        source_dbc=source_dbc,
        out=server_out,
        include=include,
        seed_profile=seed_profile,
        shell_bank_path=shell_bank_path,
        spell_ids=selected,
    )
    materialize_client_spell_dbc(
        source_dbc=source_dbc,
        out=client_out,
        include=include,
        shell_bank_path=shell_bank_path,
        spell_ids=selected,
        source_spell_icon_dbc=source_spell_icon_dbc,
    )

    report = audit_spell_shells(
        spell_ids=server_result.selected_spell_ids,
        shell_bank_path=shell_bank_path,
        client_dbc=client_out,
        server_dbc=server_out,
    )
    verified = report.status != "BROKEN"
    issues = [issue for result in report.spell_results for issue in result.to_dict()["issues"]]

    staged = False
    backup_path: str | None = None
    if apply and verified:
        backup_path = _stage_server_dbc(server_out=server_out, target=target_server_dbc, backup_dir=backup_dir)
        mark_pending_fn(server_result.selected_spell_ids, reason="unified spell publish", path=pending_path)
        staged = True

    return UnifiedPublishResult(
        selected_spell_ids=server_result.selected_spell_ids,
        verified=verified,
        staged=staged,
        audit_status=report.status,
        server_out=str(Path(server_out)),
        client_out=str(Path(client_out)),
        target_server_dbc=str(Path(target_server_dbc)),
        backup_path=backup_path,
        audit_issues=issues,
    )


def _stage_server_dbc(*, server_out: str | Path, target: str | Path, backup_dir: str | Path) -> str | None:
    target_path = Path(target)
    backup_path: str | None = None
    if target_path.exists():
        Path(backup_dir).mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        backup = Path(backup_dir) / f"Spell-{timestamp}.dbc"
        shutil.copy2(target_path, backup)
        backup_path = str(backup)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(Path(server_out), target_path)
    return backup_path


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m wm.spells.unified_dbc_publish",
        description="Materialize + verify + stage client and server WM shell Spell.dbc in one lane.",
    )
    parser.add_argument("--source-dbc", required=True)
    parser.add_argument("--server-out", required=True)
    parser.add_argument("--client-out", required=True)
    parser.add_argument("--target-server-dbc", required=True)
    parser.add_argument("--backup-dir", required=True)
    parser.add_argument("--include", choices=["named", "all"], default="named")
    parser.add_argument("--seed-profile", choices=["learnable", "castable"], default="castable")
    parser.add_argument("--shell-bank", default=None)
    parser.add_argument("--source-spell-icon-dbc", default=None)
    parser.add_argument("--spell-id", dest="spell_ids", action="append", type=int, required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--pending-path", default=None)
    parser.add_argument("--summary", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    result = publish_spell_dbc(
        spell_ids=list(args.spell_ids),
        source_dbc=args.source_dbc,
        server_out=args.server_out,
        client_out=args.client_out,
        target_server_dbc=args.target_server_dbc,
        backup_dir=args.backup_dir,
        include=args.include,
        seed_profile=args.seed_profile,
        shell_bank_path=args.shell_bank,
        source_spell_icon_dbc=args.source_spell_icon_dbc,
        apply=args.apply,
        pending_path=args.pending_path,
    )
    if args.summary:
        print(
            f"verified={str(result.verified).lower()} staged={str(result.staged).lower()} "
            f"audit_status={result.audit_status} selected={','.join(str(s) for s in result.selected_spell_ids)}"
        )
        for issue in result.audit_issues:
            print(f"  {issue.get('severity')} {issue.get('code')}: {issue.get('message')}")
    else:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0 if result.verified else 2


if __name__ == "__main__":
    raise SystemExit(main())
