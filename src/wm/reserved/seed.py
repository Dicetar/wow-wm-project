from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
import subprocess
import sys
from typing import Any

from wm.config import Settings
from wm.db.mysql_cli import MysqlCliClient, MysqlCliError


@dataclass(slots=True)
class ReservedSeedResult:
    entity_type: str
    start_id: int
    end_id: int
    mode: str
    proposed_count: int
    existing_count: int
    inserted_count: int
    ok: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ReservedSlotSeeder:
    def __init__(self, *, client: MysqlCliClient, settings: Settings) -> None:
        self.client = client
        self.settings = settings

    def seed(self, *, entity_type: str, start_id: int, end_id: int, mode: str) -> ReservedSeedResult:
        if end_id < start_id:
            raise ValueError("end_id must be >= start_id")
        existing_rows = self.client.query(
            host=self.settings.world_db_host,
            port=self.settings.world_db_port,
            user=self.settings.world_db_user,
            password=self.settings.world_db_password,
            database=self.settings.world_db_name,
            sql=(
                "SELECT ReservedID FROM wm_reserved_slot "
                f"WHERE EntityType = {_sql_string(entity_type)} "
                f"AND ReservedID BETWEEN {int(start_id)} AND {int(end_id)}"
            ),
        )
        existing_ids = {int(row["ReservedID"]) for row in existing_rows}
        missing_ids = [value for value in range(start_id, end_id + 1) if value not in existing_ids]

        inserted_count = 0
        if mode == "apply" and missing_ids:
            values_sql = ", ".join(
                f"({_sql_string(entity_type)}, {int(reserved_id)}, 'free')" for reserved_id in missing_ids
            )
            self._execute_world(
                "INSERT INTO wm_reserved_slot (EntityType, ReservedID, SlotStatus) VALUES " + values_sql
            )
            inserted_count = len(missing_ids)

        return ReservedSeedResult(
            entity_type=entity_type,
            start_id=start_id,
            end_id=end_id,
            mode=mode,
            proposed_count=len(missing_ids),
            existing_count=len(existing_ids),
            inserted_count=inserted_count,
            ok=True,
        )

    def _execute_world(self, sql: str) -> None:
        command = [
            str(self.client.mysql_bin_path),
            f"--host={self.settings.world_db_host}",
            f"--port={self.settings.world_db_port}",
            f"--user={self.settings.world_db_user}",
            f"--password={self.settings.world_db_password}",
            f"--database={self.settings.world_db_name}",
            f"--execute={sql}",
        ]
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if completed.returncode != 0:
            raise MysqlCliError(completed.stderr.strip() or completed.stdout.strip() or "mysql execute failed")


def _sql_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m wm.reserved.seed")
    parser.add_argument("--entity-type", required=True)
    parser.add_argument("--start-id", type=int, required=True)
    parser.add_argument("--end-id", type=int, required=True)
    parser.add_argument("--mode", choices=["dry-run", "apply"], default="dry-run")
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--output-json", type=Path)
    return parser


def _render_summary(result: ReservedSeedResult) -> str:
    return "\n".join(
        [
            f"entity_type: {result.entity_type}",
            f"range: {result.start_id}-{result.end_id}",
            f"mode: {result.mode}",
            f"existing_count: {result.existing_count}",
            f"proposed_count: {result.proposed_count}",
            f"inserted_count: {result.inserted_count}",
            f"ok: {str(result.ok).lower()}",
        ]
    )


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    settings = Settings.from_env()
    client = MysqlCliClient()
    seeder = ReservedSlotSeeder(client=client, settings=settings)
    result = seeder.seed(
        entity_type=args.entity_type,
        start_id=args.start_id,
        end_id=args.end_id,
        mode=args.mode,
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
    return 0 if result.ok else 2


if __name__ == "__main__":
    sys.exit(main())
