from __future__ import annotations

import argparse
import json
import sys

from wm.config import Settings
from wm.db.mysql_cli import MysqlCliClient
from wm.journal.projector import JournalProjector


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="wm journal.project", description="Project wm_event_log into journal counters.")
    p.add_argument("--player-guid", type=int, default=None)
    p.add_argument("--limit", type=int, default=200)
    p.add_argument("--mode", choices=["dry-run", "apply"], default="dry-run")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    settings = Settings.from_env()
    projector = JournalProjector(client=MysqlCliClient(), settings=settings)
    result = projector.project_unprojected(player_guid=args.player_guid, limit=args.limit, mode=args.mode)

    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
        return 0
    print(
        f"mode={args.mode} considered={result.considered} projected={result.projected} "
        f"skipped={result.skipped} materialized_subjects={result.materialized_subjects} "
        f"statements={len(result.statements)}"
    )
    if args.mode == "dry-run":
        print("DRY-RUN: no rows mutated; statements above would run in --mode apply.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
