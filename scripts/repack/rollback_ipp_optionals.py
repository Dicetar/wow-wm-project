from __future__ import annotations

import json
import math
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from time import sleep, time
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[2]
MYSQL_EXE = Path(r"D:\WOW\Azerothcore_WoTLK_Repack\mysql\bin\mysql.exe")
MYSQLDUMP_EXE = Path(r"D:\WOW\Azerothcore_WoTLK_Repack\mysql\bin\mysqldump.exe")
MYSQLD_EXE = Path(r"D:\WOW\Azerothcore_WoTLK_Repack\mysql\bin\mysqld.exe")
MYSQLADMIN_EXE = Path(r"D:\WOW\Azerothcore_WoTLK_Repack\mysql\bin\mysqladmin.exe")
CORE_BASE_SQL_ROOT = Path(r"D:\WOW\Azerothcore_WoTLK_Rebuild\source\azerothcore\data\sql\base\db_world")
CORE_UPDATE_SQL_ROOT = Path(r"D:\WOW\Azerothcore_WoTLK_Rebuild\source\azerothcore\data\sql\updates\db_world")
IPP_BASE_SQL_ROOT = Path(r"D:\WOW\Azerothcore_WoTLK_Rebuild\source\azerothcore\modules\mod-individual-progression\data\sql\world\base")
REPACK_OPTIONAL_SQL_ROOT = Path(r"D:\WOW\Azerothcore_WoTLK_Repack\optional")

DB_HOST = "127.0.0.1"
DB_PORT = "3306"
DB_USER = "acore"
DB_PASS = "acore"
LIVE_WORLD_DB = "acore_world"
LIVE_CHAR_DB = "acore_characters"

OUTPUT_ROOT = REPO_ROOT / "data" / "repack" / "ipp_optional_rollback"
TRACKED_SQL_PATH = REPO_ROOT / "sql" / "repack" / "db_world" / "2026_04_09_01_rollback_ipp_optionals.sql"


BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
USE_RE = re.compile(r"^USE\s+`?([A-Za-z0-9_]+)`?$", re.IGNORECASE | re.DOTALL)
SET_VAR_RE = re.compile(r"^SET\s+@([A-Za-z_][A-Za-z0-9_]*)\s*(?::=|=)\s*(.+)$", re.IGNORECASE | re.DOTALL)
UPDATE_RE = re.compile(r"^UPDATE\s+`?([A-Za-z0-9_]+)`?\s+SET\s+(.+?)\s+WHERE\s+(.+)$", re.IGNORECASE | re.DOTALL)
DELETE_RE = re.compile(r"^DELETE\s+FROM\s+`?([A-Za-z0-9_]+)`?\s+WHERE\s+(.+)$", re.IGNORECASE | re.DOTALL)
INSERT_RE = re.compile(
    r"^(INSERT|REPLACE)\s+INTO\s+`?([A-Za-z0-9_]+)`?\s*\((.+?)\)\s*VALUES\s*(.+)$",
    re.IGNORECASE | re.DOTALL,
)


@dataclass
class ParsedStatement:
    db_name: str
    raw_sql: str
    kind: str
    table: str | None = None
    where_sql: str | None = None
    insert_columns: list[str] | None = None
    insert_rows: list[list[object]] | None = None


class MysqlCli:
    def __init__(self, mysql_exe: Path, user: str, password: str, host: str, port: str) -> None:
        self.mysql_exe = mysql_exe
        self.user = user
        self.password = password
        self.host = host
        self.port = port

    def run(self, sql: str, database: str | None = None, force: bool = False) -> str:
        command = [
            str(self.mysql_exe),
            "-h",
            self.host,
            "-P",
            self.port,
            "-u",
            self.user,
            "--batch",
            "--raw",
            "--skip-column-names",
        ]
        if force:
            command.append("--force")
        if self.password:
            command.insert(8, f"-p{self.password}")
        if database:
            command.extend(["-D", database])
        completed = subprocess.run(
            command,
            input=sql,
            text=True,
            capture_output=True,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or "mysql failed")
        return completed.stdout


class TempMysqlServer:
    def __init__(self, root: Path, port: int) -> None:
        self.root = root
        self.data_dir = root / "data"
        self.log_path = root / "mysqld.log"
        self.port = port
        self.process: subprocess.Popen[str] | None = None

    def initialize(self) -> None:
        if self.root.exists():
            subprocess.run(
                ["powershell", "-Command", f"Remove-Item -LiteralPath '{self.root}' -Recurse -Force"],
                check=False,
                capture_output=True,
                text=True,
            )
        self.root.mkdir(parents=True, exist_ok=True)
        command = [
            str(MYSQLD_EXE),
            "--initialize-insecure",
            f"--basedir={MYSQLD_EXE.parent.parent}",
            f"--datadir={self.data_dir}",
            "--console",
        ]
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or "mysqld --initialize-insecure failed")

    def start(self) -> None:
        log_handle = self.log_path.open("w", encoding="utf-8", newline="\n")
        command = [
            str(MYSQLD_EXE),
            f"--basedir={MYSQLD_EXE.parent.parent}",
            f"--datadir={self.data_dir}",
            "--bind-address=127.0.0.1",
            f"--port={self.port}",
            "--console",
            "--skip-log-bin",
            "--skip-slave-start",
        ]
        self.process = subprocess.Popen(command, stdout=log_handle, stderr=subprocess.STDOUT, text=True)
        deadline = time() + 120
        while time() < deadline:
            ping = subprocess.run(
                [
                    str(MYSQLADMIN_EXE),
                    "-h",
                    "127.0.0.1",
                    "-P",
                    str(self.port),
                    "-u",
                    "root",
                    "ping",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            if ping.returncode == 0 and "mysqld is alive" in ping.stdout:
                return
            if self.process.poll() is not None:
                raise RuntimeError(self.log_path.read_text(encoding="utf-8", errors="ignore"))
            sleep(1)
        raise RuntimeError("temporary mysqld did not become ready in time")

    def stop(self) -> None:
        subprocess.run(
            [
                str(MYSQLADMIN_EXE),
                "-h",
                "127.0.0.1",
                "-P",
                str(self.port),
                "-u",
                "root",
                "shutdown",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if self.process is not None:
            try:
                self.process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=30)
            self.process = None

    def cleanup(self) -> None:
        if self.root.exists():
            subprocess.run(
                ["powershell", "-Command", f"Remove-Item -LiteralPath '{self.root}' -Recurse -Force"],
                check=False,
                capture_output=True,
                text=True,
            )


def sql_literal(value: object) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            raise ValueError(f"unsupported float value {value!r}")
        return format(value, ".15g")
    text = str(value)
    text = text.replace("\\", "\\\\").replace("'", "\\'")
    return f"'{text}'"


def strip_sql_comments(text: str) -> str:
    without_blocks = BLOCK_COMMENT_RE.sub("", text)
    result: list[str] = []
    quote: str | None = None
    escape = False
    index = 0
    while index < len(without_blocks):
        char = without_blocks[index]
        next_two = without_blocks[index : index + 2]
        if quote:
            result.append(char)
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == quote:
                quote = None
            index += 1
            continue
        if char in ("'", '"'):
            quote = char
            result.append(char)
            index += 1
            continue
        if next_two == "--":
            while index < len(without_blocks) and without_blocks[index] != "\n":
                index += 1
            continue
        result.append(char)
        index += 1
    return "".join(result)


def split_sql_statements(text: str) -> list[str]:
    without_lines = strip_sql_comments(text)
    statements: list[str] = []
    current: list[str] = []
    quote: str | None = None
    escape = False
    for char in without_lines:
        current.append(char)
        if quote:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == quote:
                quote = None
            continue
        if char in ("'", '"'):
            quote = char
        elif char == ";":
            statement = "".join(current[:-1]).strip()
            if statement:
                statements.append(statement)
            current = []
    tail = "".join(current).strip()
    if tail:
        statements.append(tail)
    return statements


def parse_sql_value(token: str) -> object:
    text = token.strip()
    if not text:
        return ""
    upper = text.upper()
    if upper == "NULL":
        return None
    if text[0] == "'" and text[-1] == "'":
        inner = text[1:-1]
        inner = inner.replace("\\'", "'").replace("\\\\", "\\")
        return inner
    if text.startswith("0x") or text.startswith("0X"):
        return text
    compact = re.sub(r"\s+", "", text)
    if re.fullmatch(r"[+-]?\d+(?:[+-]\d+)+", compact):
        parts = re.findall(r"[+-]?\d+", compact)
        return sum(int(part) for part in parts)
    if any(ch in text for ch in ".eE"):
        try:
            return float(text)
        except ValueError:
            return text
    try:
        return int(text)
    except ValueError:
        return text


def split_top_level(text: str, delimiter: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    quote: str | None = None
    escape = False
    depth = 0
    for char in text:
        if quote:
            current.append(char)
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == quote:
                quote = None
            continue
        if char in ("'", '"'):
            quote = char
            current.append(char)
            continue
        if char == "(":
            depth += 1
            current.append(char)
            continue
        if char == ")":
            depth -= 1
            current.append(char)
            continue
        if char == delimiter and depth == 0:
            parts.append("".join(current).strip())
            current = []
            continue
        current.append(char)
    tail = "".join(current).strip()
    if tail:
        parts.append(tail)
    return parts


def parse_insert_values(values_sql: str) -> list[list[object]]:
    tuples: list[list[object]] = []
    quote: str | None = None
    escape = False
    depth = 0
    current: list[str] = []
    tuple_chunks: list[str] = []
    for char in values_sql.strip():
        if quote:
            current.append(char)
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == quote:
                quote = None
            continue
        if char in ("'", '"'):
            quote = char
            current.append(char)
            continue
        if char == "(":
            depth += 1
            if depth == 1:
                current = []
                continue
        elif char == ")":
            depth -= 1
            if depth == 0:
                tuple_chunks.append("".join(current).strip())
                current = []
                continue
        if depth >= 1:
            current.append(char)
    for chunk in tuple_chunks:
        tuples.append([parse_sql_value(part) for part in split_top_level(chunk, ",")])
    return tuples


def parse_statement(statement: str, current_db: str) -> tuple[ParsedStatement | None, str]:
    use_match = USE_RE.match(statement)
    if use_match:
        return None, use_match.group(1)

    update_match = UPDATE_RE.match(statement)
    if update_match:
        set_clause = update_match.group(2)
        set_columns = [part.split("=", 1)[0].strip().strip("` ") for part in split_top_level(set_clause, ",")]
        return (
            ParsedStatement(
                db_name=current_db,
                raw_sql=statement,
                kind="update",
                table=update_match.group(1),
                where_sql=update_match.group(3).strip(),
                insert_columns=set_columns,
            ),
            current_db,
        )

    delete_match = DELETE_RE.match(statement)
    if delete_match:
        return (
            ParsedStatement(
                db_name=current_db,
                raw_sql=statement,
                kind="delete",
                table=delete_match.group(1),
                where_sql=delete_match.group(2).strip(),
            ),
            current_db,
        )

    insert_match = INSERT_RE.match(statement)
    if insert_match:
        columns = [part.strip().strip("`") for part in split_top_level(insert_match.group(3), ",")]
        rows = parse_insert_values(insert_match.group(4))
        return (
            ParsedStatement(
                db_name=current_db,
                raw_sql=statement,
                kind=insert_match.group(1).lower(),
                table=insert_match.group(2),
                insert_columns=columns,
                insert_rows=rows,
            ),
            current_db,
        )

    return (
        ParsedStatement(
            db_name=current_db,
            raw_sql=statement,
            kind="other",
        ),
        current_db,
    )


def substitute_variables(statement: str, variables: dict[str, object]) -> str:
    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in variables:
            return match.group(0)
        return str(variables[name])

    return re.sub(r"@([A-Za-z_][A-Za-z0-9_]*)", replace, statement)


def parse_statement_with_variables(
    statement: str,
    current_db: str,
    variables: dict[str, object],
) -> tuple[ParsedStatement | None, str, dict[str, object]]:
    use_match = USE_RE.match(statement)
    if use_match:
        return None, use_match.group(1), variables

    set_match = SET_VAR_RE.match(statement)
    if set_match:
        updated = dict(variables)
        updated[set_match.group(1)] = parse_sql_value(substitute_variables(set_match.group(2), variables))
        return None, current_db, updated

    parsed, next_db = parse_statement(substitute_variables(statement, variables), current_db)
    return parsed, next_db, variables


def build_baseline_db(mysql: MysqlCli, db_name: str) -> None:
    core_files = sorted(CORE_BASE_SQL_ROOT.glob("*.sql"))
    core_update_files = sorted(CORE_UPDATE_SQL_ROOT.glob("*.sql"))
    ipp_files = sorted(path for path in IPP_BASE_SQL_ROOT.glob("*.sql") if not path.name.startswith("zz_optional_"))
    lines = [
        f"DROP DATABASE IF EXISTS `{db_name}`;",
        "DROP DATABASE IF EXISTS `acore_characters`;",
        f"CREATE DATABASE `{db_name}` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;",
        "CREATE DATABASE `acore_characters` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;",
        "USE `acore_characters`;",
        "CREATE TABLE `character_settings` ("
        " `guid` int unsigned NOT NULL,"
        " `source` varchar(40) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,"
        " `data` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,"
        " PRIMARY KEY (`guid`,`source`)"
        ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Player Settings';",
        "SET FOREIGN_KEY_CHECKS = 0;",
        f"USE `{db_name}`;",
    ]
    for path in core_files:
        lines.append(f"USE `{db_name}`;")
        lines.append(f"SOURCE {path.as_posix()};")
    for path in core_update_files:
        lines.append(f"USE `{db_name}`;")
        lines.append(f"SOURCE {path.as_posix()};")
    for path in ipp_files:
        lines.append(f"USE `{db_name}`;")
        lines.append(f"SOURCE {path.as_posix()};")
    lines.append("SET FOREIGN_KEY_CHECKS = 1;")
    mysql.run("\n".join(lines), force=True)


def fetch_primary_keys(mysql: MysqlCli, database: str, table: str) -> list[str]:
    sql = (
        "SELECT COLUMN_NAME FROM information_schema.statistics "
        f"WHERE TABLE_SCHEMA = {sql_literal(database)} AND TABLE_NAME = {sql_literal(table)} AND INDEX_NAME = 'PRIMARY' "
        "ORDER BY SEQ_IN_INDEX;"
    )
    output = mysql.run(sql)
    return [line.strip() for line in output.splitlines() if line.strip()]


def fetch_columns(mysql: MysqlCli, database: str, table: str) -> list[str]:
    sql = (
        "SELECT COLUMN_NAME FROM information_schema.columns "
        f"WHERE TABLE_SCHEMA = {sql_literal(database)} AND TABLE_NAME = {sql_literal(table)} "
        "ORDER BY ORDINAL_POSITION;"
    )
    output = mysql.run(sql)
    return [line.strip() for line in output.splitlines() if line.strip()]


def select_rows_as_dicts(mysql: MysqlCli, database: str, table: str, where_sql: str) -> list[dict[str, object]]:
    columns = fetch_columns(mysql, database, table)
    if not columns:
        return []
    json_pairs = ", ".join(f"{sql_literal(column)}, `{column}`" for column in columns)
    sql = f"SELECT JSON_OBJECT({json_pairs}) FROM `{table}`"
    if where_sql:
        sql += f" WHERE {where_sql}"
    sql += ";"
    output = mysql.run(sql, database=database)
    rows: list[dict[str, object]] = []
    for line in output.splitlines():
        line = line.strip()
        if not line or line == "NULL":
            continue
        rows.append(json.loads(line))
    return rows


def chunked(items: list[str], size: int) -> Iterable[list[str]]:
    for index in range(0, len(items), size):
        yield items[index : index + size]


def build_pk_where(pk_columns: list[str], key_map: dict[str, object]) -> str:
    return " AND ".join(f"`{column}` = {sql_literal(key_map[column])}" for column in pk_columns)


def replace_rows_sql(table: str, rows: list[dict[str, object]]) -> list[str]:
    if not rows:
        return []
    columns = list(rows[0].keys())
    statements: list[str] = []
    for row_group in chunked([", ".join(sql_literal(row[column]) for column in columns) for row in rows], 200):
        column_sql = ", ".join(f"`{column}`" for column in columns)
        values_sql = ",\n".join(f"({value_group})" for value_group in row_group)
        statements.append(f"REPLACE INTO `{table}` ({column_sql}) VALUES\n{values_sql};")
    return statements


def parse_optional_files() -> list[ParsedStatement]:
    statements: list[ParsedStatement] = []
    for path in sorted(REPACK_OPTIONAL_SQL_ROOT.glob("zz_optional_*.sql")):
        current_db = LIVE_WORLD_DB
        variables: dict[str, object] = {}
        text = path.read_text(encoding="utf-8", errors="ignore")
        for statement in split_sql_statements(text):
            parsed, current_db, variables = parse_statement_with_variables(statement, current_db, variables)
            if parsed is not None:
                statements.append(parsed)
    return statements


def build_insert_rollback(
    mysql: MysqlCli,
    baseline_db: str,
    statement: ParsedStatement,
) -> tuple[list[str], list[str]]:
    assert statement.table and statement.insert_columns and statement.insert_rows
    table = statement.table
    pk_columns = fetch_primary_keys(mysql, baseline_db, table)
    if not pk_columns:
        return [], [f"-- skipped insert rollback for `{table}` because no primary key exists"]
    insert_index = {column: index for index, column in enumerate(statement.insert_columns)}
    if not all(pk in insert_index for pk in pk_columns):
        return [], [f"-- skipped insert rollback for `{table}` because primary key columns are not present in INSERT list"]

    keys: list[dict[str, object]] = []
    for row in statement.insert_rows:
        if len(row) < len(statement.insert_columns):
            raise RuntimeError(
                f"failed to parse INSERT for `{table}`: row has {len(row)} values but INSERT lists {len(statement.insert_columns)} columns"
            )
        keys.append({pk: row[insert_index[pk]] for pk in pk_columns})

    rollback_sql: list[str] = []
    warnings: list[str] = []
    baseline_rows: list[dict[str, object]] = []
    for key_group in chunked(keys, 100):
        where_sql = " OR ".join(f"({build_pk_where(pk_columns, key_map)})" for key_map in key_group)
        baseline_rows.extend(select_rows_as_dicts(mysql, baseline_db, table, where_sql))
    for key_map in keys:
        rollback_sql.append(f"DELETE FROM `{table}` WHERE {build_pk_where(pk_columns, key_map)};")
    rollback_sql.extend(replace_rows_sql(table, baseline_rows))
    return rollback_sql, warnings


def generate_rollbacks(mysql: MysqlCli, baseline_db: str) -> tuple[list[str], list[str], set[str], set[str]]:
    rollback_lines: list[str] = [
        "/*",
        "    Roll back Individual Progression optional SQL changes using an IPP baseline that excludes zz_optional_* files.",
        "    Generated by scripts/repack/rollback_ipp_optionals.py.",
        "*/",
        "",
    ]
    warnings: list[str] = []
    touched_world_tables: set[str] = set()
    touched_char_tables: set[str] = set()

    for statement in parse_optional_files():
        if statement.kind == "other":
            continue
        if statement.db_name == LIVE_CHAR_DB:
            if statement.table:
                touched_char_tables.add(statement.table)
            warnings.append(
                f"-- skipped character-db rollback for `{statement.raw_sql[:120]}...` because deleted character state cannot be reconstructed safely"
            )
            continue
        if statement.db_name != LIVE_WORLD_DB or not statement.table:
            continue

        touched_world_tables.add(statement.table)
        rollback_lines.append(f"-- rollback for {statement.kind.upper()} on `{statement.table}`")
        rollback_lines.append(f"-- original: {statement.raw_sql[:220].replace(chr(10), ' ')}")

        if statement.kind in {"update", "delete"}:
            baseline_rows = select_rows_as_dicts(mysql, baseline_db, statement.table, statement.where_sql or "")
            if not baseline_rows:
                warnings.append(f"-- no baseline rows found for `{statement.table}` WHERE {statement.where_sql}")
            rollback_lines.extend(replace_rows_sql(statement.table, baseline_rows))
        elif statement.kind in {"insert", "replace"}:
            sql_lines, sql_warnings = build_insert_rollback(mysql, baseline_db, statement)
            rollback_lines.extend(sql_lines)
            warnings.extend(sql_warnings)
        rollback_lines.append("")

    optional_names = [path.name for path in sorted(REPACK_OPTIONAL_SQL_ROOT.glob("zz_optional_*.sql"))]
    if optional_names:
        touched_world_tables.add("updates")
        rollback_lines.append("-- clear applied optional update markers")
        for name_group in chunked(optional_names, 50):
            names_sql = ", ".join(sql_literal(name) for name in name_group)
            rollback_lines.append(f"DELETE FROM `updates` WHERE `name` IN ({names_sql});")
        rollback_lines.append("")

    rollback_lines.extend(
        [
            "-- note:",
            "-- `zz_optional_limit_spells_to_expansion.sql` also deleted rows from acore_characters.character_spell.",
            "-- those learned-spell deletions were not automatically reconstructed, because the original per-character state is no longer knowable.",
            "",
        ]
    )
    return rollback_lines, warnings, touched_world_tables, touched_char_tables


def dump_backup_tables(world_tables: set[str], char_tables: set[str], stamp: str) -> list[Path]:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    backups: list[Path] = []
    if world_tables:
        world_backup = OUTPUT_ROOT / f"{stamp}_acore_world_tables.sql"
        command = [
            str(MYSQLDUMP_EXE),
            "-h",
            DB_HOST,
            "-P",
            DB_PORT,
            "-u",
            DB_USER,
            f"-p{DB_PASS}",
            LIVE_WORLD_DB,
            *sorted(world_tables),
        ]
        with world_backup.open("w", encoding="utf-8", newline="") as handle:
            subprocess.run(command, stdout=handle, stderr=subprocess.PIPE, text=True, check=True)
        backups.append(world_backup)
    if char_tables:
        char_backup = OUTPUT_ROOT / f"{stamp}_acore_characters_tables.sql"
        command = [
            str(MYSQLDUMP_EXE),
            "-h",
            DB_HOST,
            "-P",
            DB_PORT,
            "-u",
            DB_USER,
            f"-p{DB_PASS}",
            LIVE_CHAR_DB,
            *sorted(char_tables),
        ]
        with char_backup.open("w", encoding="utf-8", newline="") as handle:
            subprocess.run(command, stdout=handle, stderr=subprocess.PIPE, text=True, check=True)
        backups.append(char_backup)
    return backups


def apply_sql(mysql: MysqlCli, database: str, sql_path: Path) -> None:
    mysql.run(sql_path.read_text(encoding="utf-8"), database=database)


def main() -> int:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    baseline_db = "wm_ipp_nooptional"
    live_mysql = MysqlCli(MYSQL_EXE, DB_USER, DB_PASS, DB_HOST, DB_PORT)
    temp_root = OUTPUT_ROOT / f"temp_mysql_{stamp}"
    temp_mysql_server = TempMysqlServer(temp_root, port=33307)

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    print("Initializing temporary MySQL baseline server...")
    temp_mysql_server.initialize()
    temp_mysql_server.start()
    baseline_mysql = MysqlCli(MYSQL_EXE, "root", "", "127.0.0.1", str(temp_mysql_server.port))

    print(f"Building baseline DB `{baseline_db}`...")
    build_baseline_db(baseline_mysql, baseline_db)

    try:
        rollback_lines, warnings, touched_world_tables, touched_char_tables = generate_rollbacks(baseline_mysql, baseline_db)
        sql_text = "\n".join(rollback_lines).strip() + "\n"
        output_sql = OUTPUT_ROOT / f"{stamp}_rollback_ipp_optionals.sql"
        output_sql.write_text(sql_text, encoding="utf-8", newline="\n")
        TRACKED_SQL_PATH.parent.mkdir(parents=True, exist_ok=True)
        TRACKED_SQL_PATH.write_text(sql_text, encoding="utf-8", newline="\n")

        metadata = {
            "generated_at": stamp,
            "baseline_db": baseline_db,
            "output_sql": str(output_sql),
            "tracked_sql": str(TRACKED_SQL_PATH),
            "world_tables": sorted(touched_world_tables),
            "character_tables": sorted(touched_char_tables),
            "warnings": warnings,
        }
        metadata_path = OUTPUT_ROOT / f"{stamp}_rollback_ipp_optionals.json"
        metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8", newline="\n")

        print("Backing up affected tables...")
        backups = dump_backup_tables(touched_world_tables, touched_char_tables, stamp)
        print("Applying rollback SQL to acore_world...")
        apply_sql(live_mysql, LIVE_WORLD_DB, output_sql)

        print("Rollback complete.")
        print(f"Generated SQL: {output_sql}")
        print(f"Tracked SQL:   {TRACKED_SQL_PATH}")
        for backup in backups:
            print(f"Backup:        {backup}")
        if warnings:
            print("Warnings:")
            for warning in warnings[:20]:
                print(warning)
            if len(warnings) > 20:
                print(f"... {len(warnings) - 20} more warnings")
    finally:
        print("Stopping temporary MySQL baseline server...")
        temp_mysql_server.stop()
        temp_mysql_server.cleanup()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
