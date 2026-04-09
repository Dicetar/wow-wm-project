from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class DatabaseTarget:
    key: str
    host: str
    port: int
    user: str
    database: str
    source_file: str
    password: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "host": self.host,
            "port": self.port,
            "user": self.user,
            "database": self.database,
            "source_file": self.source_file,
        }


@dataclass(slots=True)
class RuntimeLayout:
    repack_root: str
    config_root: str
    module_config_root: str
    source_hint_root: str
    data_dir: str
    logs_dir: str
    mysql_root: str
    optional_sql_dir: str
    worldserver_conf_source_directory: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "repack_root": self.repack_root,
            "config_root": self.config_root,
            "module_config_root": self.module_config_root,
            "source_hint_root": self.source_hint_root,
            "data_dir": self.data_dir,
            "logs_dir": self.logs_dir,
            "mysql_root": self.mysql_root,
            "optional_sql_dir": self.optional_sql_dir,
            "worldserver_conf_source_directory": self.worldserver_conf_source_directory,
        }


@dataclass(slots=True)
class ConfigOverlay:
    relative_path: str
    dist_relative_path: str | None
    changed_from_dist: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "relative_path": self.relative_path,
            "dist_relative_path": self.dist_relative_path,
            "changed_from_dist": self.changed_from_dist,
        }


@dataclass(slots=True)
class OptionalSqlOverlay:
    filename: str
    source_path: str
    target_relative_dir: str
    classification: str
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "filename": self.filename,
            "source_path": self.source_path,
            "target_relative_dir": self.target_relative_dir,
            "classification": self.classification,
            "notes": list(self.notes),
        }


@dataclass(slots=True)
class ModuleRepoMapping:
    key: str
    display_name: str
    config_files: list[str] = field(default_factory=list)
    repo_url: str | None = None
    branch: str | None = None
    commit: str | None = None
    status: str = "unresolved"
    source_hint_dirs: list[str] = field(default_factory=list)
    runtime_markers: list[str] = field(default_factory=list)
    matched_updates: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "display_name": self.display_name,
            "config_files": list(self.config_files),
            "repo_url": self.repo_url,
            "branch": self.branch,
            "commit": self.commit,
            "status": self.status,
            "source_hint_dirs": list(self.source_hint_dirs),
            "runtime_markers": list(self.runtime_markers),
            "matched_updates": list(self.matched_updates),
            "notes": list(self.notes),
        }


@dataclass(slots=True)
class RepackSourceGap:
    category: str
    name: str
    impact: str
    reason: str
    evidence: list[str] = field(default_factory=list)
    candidate_repo: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "name": self.name,
            "impact": self.impact,
            "reason": self.reason,
            "evidence": list(self.evidence),
            "candidate_repo": self.candidate_repo,
        }


@dataclass(slots=True)
class CoreTarget:
    repo_url: str
    branch: str
    commit: str
    version_string: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "repo_url": self.repo_url,
            "branch": self.branch,
            "commit": self.commit,
            "version_string": self.version_string,
        }


@dataclass(slots=True)
class UpdateRecord:
    database: str
    state: str
    names: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "database": self.database,
            "state": self.state,
            "names": list(self.names),
        }


@dataclass(slots=True)
class RuntimeMarkerSummary:
    latest_server_log: str | None
    runtime_module_configs: list[str] = field(default_factory=list)
    ready_markers: list[str] = field(default_factory=list)
    missing_property_warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "latest_server_log": self.latest_server_log,
            "runtime_module_configs": list(self.runtime_module_configs),
            "ready_markers": list(self.ready_markers),
            "missing_property_warnings": list(self.missing_property_warnings),
        }


@dataclass(slots=True)
class BuildTooling:
    git_path: str | None
    cmake_path: str | None
    msbuild_path: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "git_path": self.git_path,
            "cmake_path": self.cmake_path,
            "msbuild_path": self.msbuild_path,
        }


@dataclass(slots=True)
class LiveRepackManifest:
    generated_at_utc: str
    core: CoreTarget
    runtime_layout: RuntimeLayout
    build_tooling: BuildTooling
    databases: list[DatabaseTarget] = field(default_factory=list)
    config_overlays: list[ConfigOverlay] = field(default_factory=list)
    runtime_markers: RuntimeMarkerSummary = field(default_factory=lambda: RuntimeMarkerSummary(latest_server_log=None))
    updates: list[UpdateRecord] = field(default_factory=list)
    optional_sql: list[OptionalSqlOverlay] = field(default_factory=list)
    modules: list[ModuleRepoMapping] = field(default_factory=list)
    source_gaps: list[RepackSourceGap] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at_utc": self.generated_at_utc,
            "core": self.core.to_dict(),
            "runtime_layout": self.runtime_layout.to_dict(),
            "build_tooling": self.build_tooling.to_dict(),
            "databases": [item.to_dict() for item in self.databases],
            "config_overlays": [item.to_dict() for item in self.config_overlays],
            "runtime_markers": self.runtime_markers.to_dict(),
            "updates": [item.to_dict() for item in self.updates],
            "optional_sql": [item.to_dict() for item in self.optional_sql],
            "modules": [item.to_dict() for item in self.modules],
            "source_gaps": [item.to_dict() for item in self.source_gaps],
        }

    def render_gap_report(self) -> str:
        lines = [
            "# Live Repack Source Gaps",
            "",
            f"- Generated UTC: `{self.generated_at_utc}`",
            f"- Core target: `{self.core.repo_url}` @ `{self.core.commit}`",
            f"- Runtime source hint: `{self.runtime_layout.source_hint_root}`",
            "",
        ]

        unresolved_modules = [module for module in self.modules if module.status != "verified"]
        if unresolved_modules:
            lines.extend(["## Module Mappings Requiring Review", ""])
            for module in unresolved_modules:
                lines.append(
                    f"- `{module.display_name}`: status=`{module.status}` repo=`{module.repo_url or 'unknown'}`"
                )
                for note in module.notes:
                    lines.append(f"  note: {note}")
                if module.matched_updates:
                    lines.append(f"  updates: {', '.join(module.matched_updates[:8])}")
            lines.append("")

        if self.source_gaps:
            lines.extend(["## Explicit Gaps", ""])
            for gap in self.source_gaps:
                lines.append(
                    f"- `{gap.name}` ({gap.category}) impact=`{gap.impact}`: {gap.reason}"
                )
                for evidence in gap.evidence:
                    lines.append(f"  evidence: {evidence}")
                if gap.candidate_repo:
                    lines.append(f"  candidate: {gap.candidate_repo}")
            lines.append("")

        if self.runtime_markers.missing_property_warnings:
            lines.extend(["## Startup Warnings", ""])
            for warning in self.runtime_markers.missing_property_warnings:
                lines.append(f"- {warning}")
            lines.append("")

        return "\n".join(lines).rstrip() + "\n"


def ensure_parent_dir(path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
