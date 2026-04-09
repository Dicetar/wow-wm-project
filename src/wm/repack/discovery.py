from __future__ import annotations

from argparse import ArgumentParser
from datetime import UTC
from datetime import datetime
import json
from pathlib import Path
import re
import shutil
from typing import Any

from wm.db.mysql_cli import MysqlCliClient
from wm.repack.catalog import ModuleCatalog
from wm.repack.models import BuildTooling
from wm.repack.models import ConfigOverlay
from wm.repack.models import CoreTarget
from wm.repack.models import DatabaseTarget
from wm.repack.models import LiveRepackManifest
from wm.repack.models import OptionalSqlOverlay
from wm.repack.models import RepackSourceGap
from wm.repack.models import RuntimeLayout
from wm.repack.models import RuntimeMarkerSummary
from wm.repack.models import UpdateRecord
from wm.repack.models import ensure_parent_dir

DEFAULT_REPACK_ROOT = Path(r"D:\WOW\Azerothcore_WoTLK_Repack")
DEFAULT_OUTPUT_DIR = Path("data/repack")
CORE_REPO_URL = "https://github.com/mod-playerbots/azerothcore-wotlk.git"
CORE_BRANCH = "Playerbot"
CORE_COMMIT_FALLBACK = "946f88d981c5"


class ParsedConfig:
    def __init__(self, values: dict[str, str]) -> None:
        self.values = values

    def get(self, key: str, default: str | None = None) -> str | None:
        return self.values.get(key, default)


def _parse_acore_config(path: Path) -> ParsedConfig:
    values: dict[str, str] = {}
    pattern = re.compile(r"^\s*([A-Za-z0-9_.]+)\s*=\s*(.*?)\s*$")
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = pattern.match(raw_line)
        if match is None:
            continue
        key, value = match.groups()
        values[key] = value.strip().strip('"')
    return ParsedConfig(values)


def _parse_db_info(value: str, *, key: str, source_file: str) -> DatabaseTarget:
    host, port, user, password, database = [part.strip() for part in value.split(";")]
    return DatabaseTarget(
        key=key,
        host=host,
        port=int(port),
        user=user,
        database=database,
        source_file=source_file,
        password=password,
    )


def _discover_config_overlays(config_root: Path) -> list[ConfigOverlay]:
    overlays: list[ConfigOverlay] = []
    for path in sorted(config_root.rglob("*.conf")):
        if " - Copy.conf" in path.name:
            continue
        relative_path = path.relative_to(config_root).as_posix()
        dist_path = path.with_name(f"{path.name}.dist")
        changed = dist_path.exists() and path.read_bytes() != dist_path.read_bytes()
        overlays.append(
            ConfigOverlay(
                relative_path=relative_path,
                dist_relative_path=dist_path.relative_to(config_root).as_posix() if dist_path.exists() else None,
                changed_from_dist=changed,
            )
        )
    return overlays


def _discover_runtime_markers(logs_dir: Path) -> RuntimeMarkerSummary:
    server_logs = sorted(
        (path for path in logs_dir.glob("Server_*.log") if path.stat().st_size > 0),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    log_path = server_logs[0] if server_logs else None
    summary = RuntimeMarkerSummary(latest_server_log=str(log_path) if log_path else None)
    if log_path is None:
        return summary

    for raw_line in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if line.startswith("> ") and line.endswith(".conf"):
            summary.runtime_module_configs.append(line.removeprefix("> ").strip())
        if "Missing property" in line:
            summary.missing_property_warnings.append(line)
        if " Ready" in line or "initialized" in line:
            summary.ready_markers.append(line)
    return summary


def _discover_build_tooling() -> BuildTooling:
    git_path = shutil.which("git")
    cmake_path = shutil.which("cmake")
    msbuild_path = shutil.which("MSBuild.exe")

    if cmake_path is None:
        candidate = Path(
            r"C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe"
        )
        if candidate.exists():
            cmake_path = str(candidate)

    if msbuild_path is None:
        candidate = Path(
            r"C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools\MSBuild\Current\Bin\MSBuild.exe"
        )
        if candidate.exists():
            msbuild_path = str(candidate)

    return BuildTooling(git_path=git_path, cmake_path=cmake_path, msbuild_path=msbuild_path)


def _query_rows(
    client: MysqlCliClient,
    *,
    database: str,
    sql: str,
    connection: DatabaseTarget,
) -> list[dict[str, Any]]:
    return client.query(
        host=connection.host,
        port=connection.port,
        user=connection.user,
        password=connection.password,
        database=database,
        sql=sql,
    )


def _discover_updates(
    client: MysqlCliClient,
    databases: list[DatabaseTarget],
) -> list[UpdateRecord]:
    records: list[UpdateRecord] = []
    by_database = {item.database: item for item in databases}
    for database_name in ("acore_world", "acore_characters", "acore_auth", "acore_playerbots"):
        connection = by_database.get(database_name)
        if connection is None:
            continue
        for state in ("MODULE", "CUSTOM"):
            try:
                rows = _query_rows(
                    client,
                    database=database_name,
                    sql=f"SELECT name FROM updates WHERE state='{state}' ORDER BY name;",
                    connection=connection,
                )
            except Exception:
                continue
            names = [row["name"] for row in rows if row.get("name")]
            if names:
                records.append(UpdateRecord(database=database_name, state=state, names=names))
    return records


def _discover_core_target(client: MysqlCliClient, world_connection: DatabaseTarget) -> CoreTarget:
    commit = CORE_COMMIT_FALLBACK
    version_string = f"AzerothCore rev. {CORE_COMMIT_FALLBACK}+"
    try:
        rows = _query_rows(
            client,
            database=world_connection.database,
            sql="SELECT core_version, core_revision FROM version LIMIT 1;",
            connection=world_connection,
        )
    except Exception:
        rows = []
    if rows:
        row = rows[0]
        version_string = row.get("core_version") or version_string
        commit = (row.get("core_revision") or commit).rstrip("+")
    return CoreTarget(
        repo_url=CORE_REPO_URL,
        branch=CORE_BRANCH,
        commit=commit,
        version_string=version_string,
    )


def _discover_optional_sql(optional_root: Path) -> list[OptionalSqlOverlay]:
    overlays: list[OptionalSqlOverlay] = []
    for path in sorted(optional_root.glob("*.sql")):
        overlays.append(
            OptionalSqlOverlay(
                filename=path.name,
                source_path=str(path),
                target_relative_dir="modules/mod-individual-progression/data/sql/world/base",
                classification="manual_review",
                notes=[
                    "Repack README says these files belong under mod-individual-progression/data/sql/world/base.",
                    "Do not auto-apply without verifying which options are already represented in the live DB.",
                ],
            )
        )
    return overlays


def _merge_module_mappings(
    catalog: ModuleCatalog,
    config_overlays: list[ConfigOverlay],
    runtime_markers: RuntimeMarkerSummary,
    source_hint_root: Path,
    updates: list[UpdateRecord],
) -> tuple[list[Any], list[RepackSourceGap]]:
    mappings: dict[str, Any] = {}
    source_hint_dirs = {path.name for path in source_hint_root.glob("*") if path.is_dir()}

    for overlay in config_overlays:
        if not overlay.relative_path.startswith("modules/"):
            continue
        config_name = Path(overlay.relative_path).name
        mapping = catalog.match_config_file(config_name)
        existing = mappings.get(mapping.key)
        if existing is None:
            mappings[mapping.key] = mapping
            existing = mapping
        if config_name not in existing.config_files:
            existing.config_files.append(config_name)

    for runtime_config in runtime_markers.runtime_module_configs:
        mapping = catalog.match_config_file(runtime_config)
        existing = mappings.get(mapping.key)
        if existing is None:
            mappings[mapping.key] = mapping
            existing = mapping
        if runtime_config not in existing.runtime_markers:
            existing.runtime_markers.append(runtime_config)

    all_update_names = [
        name
        for record in updates
        for name in record.names
        if record.state in {"MODULE", "CUSTOM"}
    ]
    unmatched_updates = catalog.attach_update_markers(mappings, all_update_names)

    for mapping in mappings.values():
        if mapping.key in source_hint_dirs:
            mapping.source_hint_dirs.append(mapping.key)
        elif mapping.display_name in source_hint_dirs:
            mapping.source_hint_dirs.append(mapping.display_name)

    gaps: list[RepackSourceGap] = []
    for mapping in sorted(mappings.values(), key=lambda item: item.display_name):
        if mapping.status == "verified":
            continue
        gaps.append(
            RepackSourceGap(
                category="module",
                name=mapping.display_name,
                impact="build" if mapping.status == "unresolved" else "parity",
                reason="No fully verified source mapping is pinned yet." if mapping.status == "unresolved" else "Repo mapping is still a convention-level candidate.",
                evidence=[
                    f"configs={','.join(mapping.config_files) or 'none'}",
                    f"runtime={','.join(mapping.runtime_markers) or 'none'}",
                    f"updates={','.join(mapping.matched_updates[:10]) or 'none'}",
                ],
                candidate_repo=mapping.repo_url,
            )
        )

    for update_name in unmatched_updates:
        gaps.append(
            RepackSourceGap(
                category="sql-update",
                name=update_name,
                impact="parity",
                reason="Update name did not match any pinned module catalog entry.",
                evidence=["Live DB updates state includes this SQL stream."],
            )
        )

    return sorted(mappings.values(), key=lambda item: item.display_name), gaps


def export_live_repack_manifest(
    *,
    repack_root: Path = DEFAULT_REPACK_ROOT,
    mysql_client: MysqlCliClient | None = None,
) -> LiveRepackManifest:
    config_root = repack_root / "configs"
    world_conf = _parse_acore_config(config_root / "worldserver.conf")
    world_db_target = _parse_db_info(
        world_conf.get("WorldDatabaseInfo", "127.0.0.1;3306;acore;;acore_world"),
        key="world",
        source_file="configs/worldserver.conf",
    )

    databases = [
        _parse_db_info(
            world_conf.get("LoginDatabaseInfo", "127.0.0.1;3306;acore;;acore_auth"),
            key="auth",
            source_file="configs/worldserver.conf",
        ),
        world_db_target,
        _parse_db_info(
            world_conf.get("CharacterDatabaseInfo", "127.0.0.1;3306;acore;;acore_characters"),
            key="characters",
            source_file="configs/worldserver.conf",
        ),
        DatabaseTarget(
            key="playerbots",
            host=world_db_target.host,
            port=world_db_target.port,
            user=world_db_target.user,
            database="acore_playerbots",
            source_file="runtime-log",
            password=world_db_target.password,
        ),
    ]

    runtime_layout = RuntimeLayout(
        repack_root=str(repack_root),
        config_root=str(config_root),
        module_config_root=str(config_root / "modules"),
        source_hint_root=str(repack_root / "source" / "azerothcore" / "modules"),
        data_dir=str(repack_root / (world_conf.get("DataDir") or "data")),
        logs_dir=str(repack_root / (world_conf.get("LogsDir") or "logs")),
        mysql_root=str(repack_root / "mysql"),
        optional_sql_dir=str(repack_root / "optional"),
        worldserver_conf_source_directory=world_conf.get("SourceDirectory"),
    )

    client = mysql_client or MysqlCliClient()
    world_connection = next(item for item in databases if item.key == "world")
    manifest = LiveRepackManifest(
        generated_at_utc=datetime.now(UTC).replace(microsecond=0).isoformat(),
        core=_discover_core_target(client, world_connection),
        runtime_layout=runtime_layout,
        build_tooling=_discover_build_tooling(),
        databases=databases,
        config_overlays=_discover_config_overlays(config_root),
        runtime_markers=_discover_runtime_markers(Path(runtime_layout.logs_dir)),
        updates=_discover_updates(client, databases),
        optional_sql=_discover_optional_sql(Path(runtime_layout.optional_sql_dir)),
    )

    catalog = ModuleCatalog()
    manifest.modules, gaps = _merge_module_mappings(
        catalog=catalog,
        config_overlays=manifest.config_overlays,
        runtime_markers=manifest.runtime_markers,
        source_hint_root=Path(runtime_layout.source_hint_root),
        updates=manifest.updates,
    )
    manifest.source_gaps = [
        RepackSourceGap(
            category="source-hint",
            name="trimmed-repack-source",
            impact="build",
            reason="The packaged source tree only contains a subset of modules and is not itself a buildable checkout.",
            evidence=[runtime_layout.source_hint_root],
        ),
        *gaps,
    ]
    return manifest


def write_manifest_bundle(manifest: LiveRepackManifest, output_dir: Path = DEFAULT_OUTPUT_DIR) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "live-repack-manifest.json"
    report_path = output_dir / "live-repack-source-gaps.md"
    ensure_parent_dir(manifest_path)
    manifest_path.write_text(json.dumps(manifest.to_dict(), indent=2), encoding="utf-8")
    report_path.write_text(manifest.render_gap_report(), encoding="utf-8")
    return manifest_path, report_path


def _build_parser() -> ArgumentParser:
    parser = ArgumentParser(description="Export a live AzerothCore repack manifest from the current environment.")
    parser.add_argument("--repack-root", default=str(DEFAULT_REPACK_ROOT))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--summary", action="store_true")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    manifest = export_live_repack_manifest(repack_root=Path(args.repack_root))
    manifest_path, report_path = write_manifest_bundle(manifest, output_dir=Path(args.output_dir))
    if args.summary:
        print(
            " ".join(
                [
                    f"manifest={manifest_path}",
                    f"report={report_path}",
                    f"modules={len(manifest.modules)}",
                    f"verified={sum(1 for item in manifest.modules if item.status == 'verified')}",
                    f"gaps={len(manifest.source_gaps)}",
                ]
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
