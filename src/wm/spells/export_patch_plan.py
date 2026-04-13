from __future__ import annotations

import argparse
import json
from pathlib import Path

from wm.spells.shell_bank import build_patch_plan


def default_output_path() -> Path:
    return (
        Path(__file__)
        .resolve()
        .parents[3]
        .joinpath(".wm-bootstrap", "state", "client-patches", "wm_spell_shell_bank", "patch-plan.json")
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Export the WM spell shell bank into a generated patch plan.")
    parser.add_argument(
        "--shell-bank",
        default=None,
        help="Optional path to spell_shell_bank.json. Defaults to the repo contract.",
    )
    parser.add_argument(
        "--out",
        default=str(default_output_path()),
        help="Output JSON path for the generated patch plan.",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Print a short summary after writing the patch plan.",
    )
    args = parser.parse_args()

    plan = build_patch_plan(args.shell_bank)
    output_path = Path(args.out)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")

    if args.summary:
        print(
            json.dumps(
                {
                    "out": str(output_path),
                    "generation_mode": plan["generation_mode"],
                    "family_count": plan["family_count"],
                    "slots_per_family": plan["slots_per_family"],
                    "total_rows": plan["total_rows"],
                    "named_override_count": plan["named_override_count"],
                },
                ensure_ascii=False,
            )
        )
    else:
        print(str(output_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
