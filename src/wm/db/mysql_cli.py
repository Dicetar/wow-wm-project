from __future__ import annotations

import csv
import io
import os
from pathlib import Path
import shutil
import subprocess
from typing import Any


class MysqlCliError(RuntimeError):
    """Raised when the mysql CLI cannot be executed successfully."""


class MysqlCliClient:
    def __init__(self, mysql_bin_path: str | Path | None = None) -> None:
        self.mysql_bin_path = Path(mysql_bin_path) if mysql_bin_path else Path(self._discover_mysql_bin())

    def query(self, *, host: str, port: int, user: str, password: str, database: str, sql: str) -> list[dict[str, Any]]:
        command = [
            str(self.mysql_bin_path),
            f"--host={host}",
            f"--port={port}",
            f"--user={user}",
            f"--password={password}",
            f"--database={database}",
            "--batch",
            "--raw",
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
            raise MysqlCliError(completed.stderr.strip() or completed.stdout.strip() or "mysql query failed")
        return self._parse_tsv_output(completed.stdout)

    @staticmethod
    def _parse_tsv_output(stdout: str) -> list[dict[str, Any]]:
        stripped = stdout.strip()
        if not stripped:
            return []
        reader = csv.DictReader(io.StringIO(stripped), delimiter="\t")
        rows: list[dict[str, Any]] = []
        for row in reader:
            normalized: dict[str, Any] = {}
            for key, value in row.items():
                normalized[key] = None if value == "NULL" else value
            rows.append(normalized)
        return rows

    @staticmethod
    def _discover_mysql_bin() -> str:
        env_path = os.getenv("WM_MYSQL_BIN_PATH")
        if env_path:
            return env_path
        which_path = shutil.which("mysql")
        if which_path:
            return which_path
        default_windows_path = r"D:\WOW\Azerothcore_WoTLK_Repack\mysql\bin\mysql.exe"
        if Path(default_windows_path).exists():
            return default_windows_path
        raise MysqlCliError(
            "mysql executable not found. Set WM_MYSQL_BIN_PATH in .env or ensure mysql is on PATH."
        )
