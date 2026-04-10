from __future__ import annotations

import argparse
import json
from pathlib import Path

from wm.config import Settings
from wm.control.models import ControlProposal


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export JSON Schema files for WM control models.")
    parser.add_argument("--output-dir", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    settings = Settings.from_env()
    output_dir = args.output_dir or Path(settings.control_root) / "generated"
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "control_proposal.schema.json"
    path.write_text(
        json.dumps(ControlProposal.model_json_schema(), indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"schema_written={path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
