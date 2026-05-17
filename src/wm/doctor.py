"""WM system-health command.

Roadmap Phase 0 deliverable: "add a 'system health' command that prints one
summary view" with exit criterion "WM can report live readiness in one
command". Composes existing primitives (Settings, MysqlCliClient,
SoapRuntimeClient) and reports each check with the repo status vocabulary so a
fresh machine / dirty-lab problem is diagnosable without source diving.

Status vocabulary:
- WORKING: reachable and as expected
- UNKNOWN: not checkable here (disabled, lab not built, dependency missing)
- FAIL:    expected to work but did not

Designed for offline tests: db/soap clients are injectable, and a doctor must
behave correctly precisely when things are unreachable.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import sys
from pathlib import Path
from typing import Any

from wm.config import Settings
from wm.db.mysql_cli import MysqlCliClient, MysqlCliError
from wm.runtime_sync.soap import SoapRuntimeClient

WORKING = "WORKING"
UNKNOWN = "UNKNOWN"
FAIL = "FAIL"

# WM-owned tables that bootstrap SQL is responsible for. Missing tables here is
# the single most common "exists in DB but fails in-game" precondition the
# full-loop runbook depends on.
_EXPECTED_WORLD_TABLES = (
    "wm_event_log",
    "wm_control_proposal",
    "wm_reserved_slot",
    "wm_publish_log",
)
_EXPECTED_CHAR_TABLES = (
    "wm_character_arc_state",
    "wm_character_reward_instance",
)


@dataclass(slots=True)
class CheckResult:
    name: str
    status: str
    detail: str

    def __post_init__(self) -> None:
        # Detail must stay one line: mysql/SOAP errors are multi-line and would
        # break the one-row-per-check summary contract.
        self.detail = " ".join(self.detail.split())

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "status": self.status, "detail": self.detail}


def _db_check(
    client: MysqlCliClient | None,
    *,
    name: str,
    host: str,
    port: int,
    user: str,
    password: str,
    database: str,
    expected_tables: tuple[str, ...],
) -> list[CheckResult]:
    if client is None:
        return [CheckResult(name, UNKNOWN, "mysql client unavailable; see mysql-bin check")]
    try:
        client.query(host=host, port=port, user=user, password=password, database=database, sql="SELECT 1 AS ok")
    except MysqlCliError as exc:
        return [CheckResult(name, FAIL, f"{host}:{port}/{database} unreachable: {exc}")]
    results = [CheckResult(name, WORKING, f"{host}:{port}/{database} reachable")]

    try:
        rows = client.query(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            sql="SHOW TABLES LIKE 'wm\\_%'",
        )
    except MysqlCliError as exc:
        results.append(CheckResult(f"{name}.wm_tables", UNKNOWN, f"could not list wm_ tables: {exc}"))
        return results
    present = {str(next(iter(row.values()))) for row in rows if row}
    missing = [t for t in expected_tables if t not in present]
    if missing:
        results.append(
            CheckResult(
                f"{name}.wm_tables",
                FAIL,
                f"missing bootstrap tables: {', '.join(missing)} (apply sql/bootstrap)",
            )
        )
    else:
        results.append(CheckResult(f"{name}.wm_tables", WORKING, f"{len(expected_tables)} expected WM tables present"))
    return results


def _soap_check(settings: Settings, soap_client: SoapRuntimeClient | None) -> CheckResult:
    if not settings.soap_enabled:
        return CheckResult("soap", UNKNOWN, "WM_SOAP_ENABLED is off; runtime reloads need manual console")
    client = soap_client or SoapRuntimeClient(settings=settings)
    result = client.execute_command(".server info")
    if result.ok:
        return CheckResult("soap", WORKING, f"{client.endpoint} responded")
    return CheckResult(
        "soap",
        FAIL,
        f"{client.endpoint} not usable: {result.fault_code or ''} {result.fault_string or ''}".strip(),
    )


def _native_bridge_check(settings: Settings) -> CheckResult:
    path = Path(settings.wm_bridge_config_path)
    if not path.exists():
        return CheckResult("native_bridge", UNKNOWN, f"config not found at {path} (BridgeLab not built/staged?)")
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return CheckResult("native_bridge", FAIL, f"config unreadable: {exc}")
    allow = ""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("WmBridge.PlayerGuidAllowList"):
            allow = stripped.split("=", 1)[1].strip().strip('"') if "=" in stripped else ""
            break
    if allow == "*":
        return CheckResult("native_bridge", WORKING, "config present; WARNING wildcard scope '*' is active")
    if allow:
        return CheckResult("native_bridge", WORKING, f"config present; scoped to {allow}")
    return CheckResult("native_bridge", UNKNOWN, "config present; PlayerGuidAllowList empty (module inert)")


def _control_registry_check(settings: Settings) -> CheckResult:
    registry = Path(settings.control_root) / "registry.json"
    if not registry.exists():
        return CheckResult("control_registry", FAIL, f"missing {registry}")
    try:
        json.loads(registry.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return CheckResult("control_registry", FAIL, f"registry.json invalid: {exc}")
    return CheckResult("control_registry", WORKING, "control registry loads")


def run_doctor(
    settings: Settings,
    *,
    db_client: MysqlCliClient | None = None,
    soap_client: SoapRuntimeClient | None = None,
) -> list[CheckResult]:
    results: list[CheckResult] = []

    if db_client is None:
        try:
            db_client = MysqlCliClient()
            results.append(CheckResult("mysql_bin", WORKING, str(db_client.mysql_bin_path)))
        except MysqlCliError as exc:
            db_client = None
            results.append(CheckResult("mysql_bin", FAIL, str(exc)))
    else:
        results.append(CheckResult("mysql_bin", WORKING, "injected client"))

    results.extend(
        _db_check(
            db_client,
            name="world_db",
            host=settings.world_db_host,
            port=settings.world_db_port,
            user=settings.world_db_user,
            password=settings.world_db_password,
            database=settings.world_db_name,
            expected_tables=_EXPECTED_WORLD_TABLES,
        )
    )
    results.extend(
        _db_check(
            db_client,
            name="char_db",
            host=settings.char_db_host,
            port=settings.char_db_port,
            user=settings.char_db_user,
            password=settings.char_db_password,
            database=settings.char_db_name,
            expected_tables=_EXPECTED_CHAR_TABLES,
        )
    )
    results.append(_soap_check(settings, soap_client))
    results.append(_native_bridge_check(settings))
    results.append(_control_registry_check(settings))
    return results


def _exit_code(results: list[CheckResult]) -> int:
    return 1 if any(r.status == FAIL for r in results) else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="wm doctor", description="Report WM live readiness in one command.")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    parser.add_argument("--summary", action="store_true", help="print one summary line per check")
    args = parser.parse_args(argv)

    settings = Settings.from_env()
    results = run_doctor(settings)
    code = _exit_code(results)

    if args.json:
        print(json.dumps({"ok": code == 0, "checks": [r.to_dict() for r in results]}, indent=2))
        return code

    width = max(len(r.name) for r in results)
    for r in results:
        print(f"  {r.status:<8} {r.name:<{width}}  {r.detail}")
    fails = sum(1 for r in results if r.status == FAIL)
    unknowns = sum(1 for r in results if r.status == UNKNOWN)
    print(f"\n{'OK' if code == 0 else 'NOT READY'}: {fails} FAIL, {unknowns} UNKNOWN, {len(results)} checks")
    return code


if __name__ == "__main__":
    sys.exit(main())
