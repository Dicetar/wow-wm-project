from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]


@dataclass(slots=True)
class ArcScaffoldFile:
    path: str
    purpose: str
    required: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ArcScaffoldPlan:
    arc_key: str
    status: str
    files: list[ArcScaffoldFile]
    required_gates: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "arc_key": self.arc_key,
            "status": self.status,
            "files": [file.to_dict() for file in self.files],
            "required_gates": self.required_gates,
        }


def build_scaffold_plan(*, arc_key: str, module_key: str | None = None) -> ArcScaffoldPlan:
    safe_module = module_key or arc_key
    if not safe_module.replace("_", "").replace("-", "").isalnum():
        return ArcScaffoldPlan(arc_key=arc_key, status="BROKEN", files=[], required_gates=["module_key_must_be_slug"])
    module_name = safe_module.replace("-", "_")
    return ArcScaffoldPlan(
        arc_key=arc_key,
        status="WORKING",
        files=[
            ArcScaffoldFile(f"control/examples/journey/{module_name}.json", "character journey seed"),
            ArcScaffoldFile(f"src/wm/spells/{module_name}.py", "constants, dry-run/apply/verify helpers"),
            ArcScaffoldFile(f"native_modules/mod-wm-spells/data/sql/world/updates/<date>_wm_spell_{module_name}.sql", "world SQL for shell, quest, creature, GO, and counter rows"),
            ArcScaffoldFile(f"docs/{module_name.upper()}.md", "status and live proof notes"),
            ArcScaffoldFile(f"tests/test_{module_name}.py", "focused static and helper tests"),
        ],
        required_gates=[
            "python -m wm.content.preflight --arc <arc_key> --summary",
            "python -m wm.spells.shell_audit --spell-id <shell_id> --summary",
            "python -m wm.live.proof_packet --arc <arc_key> --summary",
            "python -m wm.bridge_lab.release_gate --arc <arc_key> --summary",
        ],
    )


def render_summary(plan: ArcScaffoldPlan) -> str:
    lines = [f"arc={plan.arc_key}", f"status={plan.status}"]
    for file in plan.files:
        lines.append(f"{file.path}: {file.purpose}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Plan the standard file scaffold and gates for a new WM arc.")
    parser.add_argument("--arc", required=True)
    parser.add_argument("--module-key", default=None)
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args(argv)

    plan = build_scaffold_plan(arc_key=args.arc, module_key=args.module_key)
    if args.summary:
        print(render_summary(plan))
    else:
        print(json.dumps(plan.to_dict(), indent=2, sort_keys=True))
    return 0 if plan.status != "BROKEN" else 1


if __name__ == "__main__":
    raise SystemExit(main())
