from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import subprocess
from pathlib import Path
from typing import Any

from wm.spells.broug_empty_court import BROUG_EMPTY_COURT_ARC_KEY
from wm.spells.broug_lightness import BROUG_LIGHTNESS_ARC_KEY


REPO_ROOT = Path(__file__).resolve().parents[3]


@dataclass(slots=True)
class ReleaseGateStep:
    key: str
    command: list[str]
    mutates_lab: bool
    required: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ReleaseGatePlan:
    arc_key: str
    player_guid: int
    status: str
    steps: list[ReleaseGateStep]
    notes: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "arc_key": self.arc_key,
            "player_guid": self.player_guid,
            "status": self.status,
            "notes": self.notes,
            "steps": [step.to_dict() for step in self.steps],
        }


def build_release_gate_plan(*, arc_key: str, player_guid: int = 5405, include_native_build: bool = True) -> ReleaseGatePlan:
    if arc_key not in {BROUG_LIGHTNESS_ARC_KEY, BROUG_EMPTY_COURT_ARC_KEY, "broug_all_current"}:
        return ReleaseGatePlan(
            arc_key=arc_key,
            player_guid=player_guid,
            status="UNKNOWN",
            steps=[],
            notes=[f"No BridgeLab release-gate profile exists for arc `{arc_key}`."],
        )

    sql_files = []
    if arc_key in {BROUG_LIGHTNESS_ARC_KEY, "broug_all_current"}:
        sql_files.append("native_modules/mod-wm-spells/data/sql/world/updates/2026_05_02_00_wm_spell_broug_lightness_assassin.sql")
    if arc_key in {BROUG_EMPTY_COURT_ARC_KEY, "broug_all_current"}:
        sql_files.append("native_modules/mod-wm-spells/data/sql/world/updates/2026_05_02_01_wm_spell_broug_empty_court_v2.sql")

    tests = ["tests/test_spell_shell_bank.py", "tests/test_client_spell_patch.py", "tests/test_server_spell_dbc.py"]
    if arc_key in {BROUG_LIGHTNESS_ARC_KEY, "broug_all_current"}:
        tests.append("tests/test_broug_lightness.py")
    if arc_key in {BROUG_EMPTY_COURT_ARC_KEY, "broug_all_current"}:
        tests.append("tests/test_broug_empty_court.py")

    steps = [
        ReleaseGateStep(
            key="focused_tests",
            command=["python", "-m", "pytest", *tests],
            mutates_lab=False,
        ),
    ]
    for preflight_arc in _preflight_arcs_for(arc_key):
        steps.append(
            ReleaseGateStep(
                key=f"content_preflight:{preflight_arc}",
                command=["python", "-m", "wm.content.preflight", "--arc", preflight_arc, "--player-guid", str(player_guid), "--summary"],
                mutates_lab=False,
            )
        )
    steps.extend(
        [
            ReleaseGateStep(
                key="world_sql_apply",
                command=[
                    r"D:\WOW\WM_BridgeLab\deps\mysql\bin\mysql.exe",
                    "--host=127.0.0.1",
                    "--port=33307",
                    "--user=acore",
                    "--password=acore",
                    "--database=acore_world",
                    "--execute=" + " ".join(f"source D:/WOW/wm-project/{path};" for path in sql_files),
                ],
                mutates_lab=True,
            ),
            ReleaseGateStep(
                key="stage_server_spell_dbc",
                command=["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "scripts/bridge_lab/Stage-BridgeLabServerSpellDbc.ps1", "-Include", "named", "-SeedProfile", "castable"],
                mutates_lab=True,
            ),
            ReleaseGateStep(
                key="install_client_patch",
                command=[
                    "python",
                    "-m",
                    "wm.spells.client_patch",
                    "build",
                    "--source-dbc",
                    r"D:\WOW\Azerothcore_WoTLK_Rebuild\run\data\dbc\Spell.dbc",
                    "--include",
                    "all",
                    "--install",
                    "--summary",
                ],
                mutates_lab=True,
            ),
        ]
    )
    if include_native_build:
        steps.extend(
            [
                ReleaseGateStep(
                    key="native_worldserver_build",
                    command=[
                        "powershell",
                        "-NoProfile",
                        "-ExecutionPolicy",
                        "Bypass",
                        "-File",
                        "scripts/bridge_lab/Build-BridgeLabIncremental.ps1",
                        "-WorkspaceRoot",
                        r"D:\WOW\WM_BridgeLab",
                        "-Target",
                        "worldserver",
                        "-NoStageRuntime",
                    ],
                    mutates_lab=True,
                ),
                ReleaseGateStep(
                    key="deploy_worldserver",
                    command=["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "scripts/bridge_lab/Deploy-BridgeLabWorldServer.ps1"],
                    mutates_lab=True,
                ),
            ]
        )
    steps.append(
        ReleaseGateStep(
            key="native_ping",
            command=[
                "python",
                "-m",
                "wm.sources.native_bridge.actions_cli",
                "submit",
                "--player-guid",
                str(player_guid),
                "--action-kind",
                "debug_ping",
                "--payload-json",
                "{}",
                "--idempotency-key",
                "manual:release_gate:<timestamp>",
                "--wait",
                "--summary",
            ],
            mutates_lab=True,
        )
    )

    return ReleaseGatePlan(
        arc_key=arc_key,
        player_guid=player_guid,
        status="WORKING",
        steps=steps,
        notes=[
            "Default command output is a plan; use --apply to execute.",
            "Set PYTHONPATH=src and BridgeLab DB env vars before apply when running outside repo scripts.",
            "Client patch install requires wow.exe to be closed.",
        ],
    )


def _preflight_arcs_for(arc_key: str) -> list[str]:
    if arc_key == "broug_all_current":
        return [BROUG_LIGHTNESS_ARC_KEY, BROUG_EMPTY_COURT_ARC_KEY]
    return [arc_key]


def apply_release_gate_plan(plan: ReleaseGatePlan) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for step in plan.steps:
        command = [part.replace("<timestamp>", _timestamp()) for part in step.command]
        completed = subprocess.run(command, cwd=REPO_ROOT, text=True, capture_output=True, check=False)
        result = {
            "key": step.key,
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
        results.append(result)
        if completed.returncode != 0 and step.required:
            break
    return results


def _timestamp() -> str:
    from datetime import datetime

    return datetime.now().strftime("%Y%m%d%H%M%S")


def render_summary(plan: ReleaseGatePlan) -> str:
    lines = [f"arc={plan.arc_key}", f"player_guid={plan.player_guid}", f"status={plan.status}"]
    for step in plan.steps:
        lines.append(f"{step.key}: {' '.join(step.command)}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build or apply a BridgeLab release gate for player-facing arc content.")
    parser.add_argument("--arc", required=True)
    parser.add_argument("--player-guid", type=int, default=5405)
    parser.add_argument("--skip-native-build", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args(argv)

    plan = build_release_gate_plan(
        arc_key=args.arc,
        player_guid=args.player_guid,
        include_native_build=not args.skip_native_build,
    )
    payload: dict[str, Any] = plan.to_dict()
    if args.apply:
        payload["apply_results"] = apply_release_gate_plan(plan)
    if args.summary:
        print(render_summary(plan))
        if args.apply:
            for result in payload.get("apply_results", []):
                print(f"{result['key']} returncode={result['returncode']}")
    else:
        print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if plan.status != "UNKNOWN" else 1


if __name__ == "__main__":
    raise SystemExit(main())
