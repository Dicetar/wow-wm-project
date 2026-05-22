from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import sys
from typing import Any

from wm.sources.native_bridge.player_marker import DEFAULT_MARKER_SPELL_ID


@dataclass(frozen=True, slots=True)
class ParameterSpec:
    name: str
    type: str = "string"
    required: bool = False
    default: Any = None
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "type": self.type,
            "required": self.required,
            "default": self.default,
            "description": self.description,
        }


@dataclass(frozen=True, slots=True)
class CommandEntry:
    id: str
    label: str
    category: str
    kind: str
    dry_run_argv: tuple[str, ...]
    apply_argv: tuple[str, ...] = ()
    mutating: bool = False
    dry_run_required: bool = False
    confirmation: str | None = None
    parameters: tuple[ParameterSpec, ...] = field(default_factory=tuple)
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "category": self.category,
            "kind": self.kind,
            "argv": ["python" if item == "{python}" else item for item in self.dry_run_argv],
            "mutating": self.mutating,
            "dry_run_required": self.dry_run_required,
            "confirmation": self.confirmation,
            "parameters": [parameter.to_dict() for parameter in self.parameters],
            "description": self.description,
            "has_apply": bool(self.apply_argv),
        }

    def argv_for(self, *, mode: str, params: dict[str, Any], paths: dict[str, Path]) -> list[str]:
        template = self.apply_argv if mode == "apply" else self.dry_run_argv
        if mode == "apply" and not template:
            raise ValueError(f"Command {self.id} has no apply argv.")
        context = _build_context(parameters=self.parameters, params=params, paths=paths)
        return [_format_part(part, context) for part in template]


class CommandCatalog:
    def __init__(self, entries: list[CommandEntry] | None = None) -> None:
        self.entries = entries if entries is not None else _default_entries()
        self.by_id = {entry.id: entry for entry in self.entries}

    def get(self, command_id: str) -> CommandEntry:
        try:
            return self.by_id[command_id]
        except KeyError as exc:
            raise KeyError(f"Unknown command id: {command_id}") from exc

    def list_api(self) -> list[dict[str, Any]]:
        return [entry.to_dict() for entry in self.entries]


def _build_context(*, parameters: tuple[ParameterSpec, ...], params: dict[str, Any], paths: dict[str, Path]) -> dict[str, Any]:
    context: dict[str, Any] = {"python": sys.executable}
    context.update({key: str(value) for key, value in paths.items()})
    for parameter in parameters:
        raw = params.get(parameter.name, parameter.default)
        if parameter.required and raw in (None, ""):
            raise ValueError(f"Missing required parameter: {parameter.name}")
        context[parameter.name] = _coerce_parameter(parameter, raw)
    return context


def _coerce_parameter(parameter: ParameterSpec, raw: Any) -> str:
    if raw is None:
        return ""
    if parameter.type == "integer":
        return str(int(raw))
    if parameter.type == "number":
        return str(float(raw))
    if parameter.type == "boolean":
        return "true" if bool(raw) else "false"
    return str(raw)


def _format_part(part: str, context: dict[str, Any]) -> str:
    return part.format(**context)


def _py(*parts: str) -> tuple[str, ...]:
    return ("{python}", "-m", *parts)


def _default_entries() -> list[CommandEntry]:
    player = ParameterSpec("player_guid", type="integer", required=True, description="Scoped player GUID.")
    limit = ParameterSpec("limit", type="integer", default=20, description="Maximum rows to list.")
    marker_spell = ParameterSpec(
        "marker_spell_id",
        type="integer",
        default=DEFAULT_MARKER_SPELL_ID,
        description="WM player marker aura spell.",
    )
    since_seconds = ParameterSpec("since_seconds", type="integer", default=300, description="Recent marker scan window in seconds.")
    expires_seconds = ParameterSpec("expires_seconds", type="integer", default=900, description="Scoped player TTL in seconds.")
    return [
        CommandEntry(
            id="watcher.status",
            label="Watcher Status",
            category="watcher",
            kind="read_only",
            dry_run_argv=(".\\status-bridge-lab-watch.bat",),
            description="Inspect the repo-owned BridgeLab watcher process.",
        ),
        CommandEntry(
            id="watcher.start",
            label="Start Watcher",
            category="watcher",
            kind="mutation",
            dry_run_argv=(".\\status-bridge-lab-watch.bat",),
            apply_argv=(".\\start-bridge-lab-watch.bat",),
            mutating=True,
            dry_run_required=True,
            confirmation="type_job_id",
            description="Start the repo-owned native BridgeLab watcher after a status dry-run.",
        ),
        CommandEntry(
            id="watcher.stop",
            label="Stop Watcher",
            category="watcher",
            kind="mutation",
            dry_run_argv=(".\\status-bridge-lab-watch.bat",),
            apply_argv=(".\\stop-bridge-lab-watch.bat",),
            mutating=True,
            dry_run_required=True,
            confirmation="type_job_id",
            description="Stop the repo-owned native BridgeLab watcher after a status dry-run.",
        ),
        CommandEntry(
            id="bridge_lab.start",
            label="Start BridgeLab",
            category="watcher",
            kind="mutation",
            dry_run_argv=(".\\status-bridge-lab-watch.bat",),
            apply_argv=(".\\start-bridge-lab-all.bat",),
            mutating=True,
            dry_run_required=True,
            confirmation="type_job_id",
            description="Start BridgeLab through the repo-owned all-in-one launcher.",
        ),
        CommandEntry(
            id="native.queue.inspect",
            label="Native Queue Inspect",
            category="watcher",
            kind="read_only",
            dry_run_argv=_py("wm.sources.native_bridge.actions_cli", "inspect", "--player-guid", "{player_guid}", "--limit", "{limit}", "--summary"),
            parameters=(player, limit),
        ),
        CommandEntry(
            id="marker.scan",
            label="Scan Player Markers",
            category="session",
            kind="read_only",
            dry_run_argv=_py(
                "wm.sources.native_bridge.player_marker",
                "scan",
                "--spell-id",
                "{marker_spell_id}",
                "--since-seconds",
                "{since_seconds}",
                "--limit",
                "{limit}",
                "--summary",
            ),
            parameters=(marker_spell, since_seconds, limit),
            description="Read recent marker-aura events and list candidate player sessions.",
        ),
        CommandEntry(
            id="marker.scope_latest",
            label="Scope Latest Marker",
            category="session",
            kind="mutation",
            dry_run_argv=_py(
                "wm.sources.native_bridge.player_marker",
                "scan",
                "--spell-id",
                "{marker_spell_id}",
                "--since-seconds",
                "{since_seconds}",
                "--limit",
                "10",
                "--summary",
            ),
            apply_argv=_py(
                "wm.sources.native_bridge.player_marker",
                "scope-latest",
                "--spell-id",
                "{marker_spell_id}",
                "--since-seconds",
                "{since_seconds}",
                "--expires-seconds",
                "{expires_seconds}",
                "--summary",
            ),
            mutating=True,
            dry_run_required=True,
            confirmation="type_job_id",
            parameters=(marker_spell, since_seconds, expires_seconds),
            description="Scope the latest marker-selected player in wm_bridge_player_scope after a scan dry-run.",
        ),
        CommandEntry(
            id="marker.observe_all.start",
            label="Temporary Observe All",
            category="session",
            kind="mutation",
            dry_run_argv=_py("wm.doctor", "--summary"),
            apply_argv=_py("wm.sources.native_bridge.configure", "--allow-all", "--reload-via-soap", "--summary"),
            mutating=True,
            dry_run_required=True,
            confirmation="type_job_id",
            description="Temporarily set WmBridge.PlayerGuidAllowList='*' through the existing bridge configure CLI.",
        ),
        CommandEntry(
            id="marker.observe_all.stop",
            label="Stop Observe All",
            category="session",
            kind="mutation",
            dry_run_argv=_py("wm.doctor", "--summary"),
            apply_argv=_py("wm.sources.native_bridge.configure", "--clear", "--reload-via-soap", "--summary"),
            mutating=True,
            dry_run_required=True,
            confirmation="type_job_id",
            description="Clear temporary wildcard bridge observation; DB-backed player scope remains separate.",
        ),
        CommandEntry(
            id="native.queue.recover",
            label="Recover Stale Queue",
            category="watcher",
            kind="mutation",
            dry_run_argv=_py("wm.sources.native_bridge.actions_cli", "inspect", "--limit", "{limit}", "--summary"),
            apply_argv=_py("wm.sources.native_bridge.actions_cli", "recover-stale", "--summary"),
            mutating=True,
            dry_run_required=True,
            confirmation="type_job_id",
            parameters=(limit,),
        ),
        CommandEntry(
            id="native.queue.cleanup",
            label="Cleanup Native Queue",
            category="watcher",
            kind="mutation",
            dry_run_argv=_py("wm.sources.native_bridge.actions_cli", "inspect", "--limit", "{limit}", "--summary"),
            apply_argv=_py("wm.sources.native_bridge.actions_cli", "cleanup", "--limit", "{limit}", "--summary"),
            mutating=True,
            dry_run_required=True,
            confirmation="type_job_id",
            parameters=(limit,),
        ),
        CommandEntry(
            id="context.build",
            label="Build Context Pack",
            category="context",
            kind="artifact",
            dry_run_argv=_py("wm.context.builder", "--target-entry", "{target_entry}", "--player-guid", "{player_guid}", "--summary", "--output-json", "{context_pack_json}"),
            parameters=(
                player,
                ParameterSpec("target_entry", type="integer", required=True, description="Creature template entry."),
            ),
            description="Build deterministic wm.context_pack.v1 from existing context/journal systems.",
        ),
        CommandEntry(
            id="candidates.release_pack",
            label="Build Release Candidates",
            category="content",
            kind="artifact",
            dry_run_argv=_py("wm.candidates.release_pack", "--context-pack-json", "{context_pack_path}", "--summary", "--write-candidates-dir", "{candidate_dir}"),
            parameters=(ParameterSpec("context_pack_path", required=True, description="Existing context pack JSON path."),),
        ),
        CommandEntry(
            id="content.release.validate",
            label="Validate Release Spec",
            category="release",
            kind="read_only",
            dry_run_argv=_py("wm.content.release", "{input_json}", "--summary"),
            description="Validate a content release spec through wm.content.release.",
        ),
        CommandEntry(
            id="content.release.plan",
            label="Build Release Plan",
            category="release",
            kind="read_only",
            dry_run_argv=_py("wm.content.release", "{input_json}", "--plan", "--summary"),
            description="Render release gates without applying content.",
        ),
        CommandEntry(
            id="content.release.packet",
            label="Build Release Packet",
            category="release",
            kind="read_only",
            dry_run_argv=_py("wm.content.release", "{input_json}", "--packet", "--summary"),
            description="Render a release packet without writing packet files.",
        ),
        CommandEntry(
            id="content.release.write_packet",
            label="Write Release Packet",
            category="release",
            kind="artifact",
            dry_run_argv=_py("wm.content.release", "{input_json}", "--packet", "--summary"),
            apply_argv=_py("wm.content.release", "{input_json}", "--write-packet-dir", "{packet_dir}", "--summary", "--force"),
            mutating=True,
            dry_run_required=True,
            confirmation="type_job_id",
            description="Write packet artifacts locally. This does not publish to the game.",
        ),
        CommandEntry(
            id="control.validate",
            label="Validate Control Proposal",
            category="proposal",
            kind="read_only",
            dry_run_argv=_py("wm.control.validate", "--proposal", "{proposal_json}", "--summary"),
            description="Validate a ControlProposal through the existing coordinator.",
        ),
        CommandEntry(
            id="control.apply",
            label="Apply Control Proposal",
            category="proposal",
            kind="mutation",
            dry_run_argv=_py("wm.control.apply", "--proposal", "{proposal_json}", "--mode", "dry-run", "--summary"),
            apply_argv=_py("wm.control.apply", "--proposal", "{proposal_json}", "--mode", "apply", "--confirm-live-apply", "--summary"),
            mutating=True,
            dry_run_required=True,
            confirmation="type_job_id",
            description="Apply an operator-reviewed ControlProposal through the existing control gate.",
        ),
        CommandEntry(
            id="workbench.publish_item",
            label="Publish Managed Item",
            category="content",
            kind="mutation",
            dry_run_argv=_py("wm.content.workbench", "publish-item", "--draft-json", "{input_json}", "--mode", "dry-run", "--output-json", "{result_json}"),
            apply_argv=_py("wm.content.workbench", "publish-item", "--draft-json", "{input_json}", "--mode", "apply", "--output-json", "{result_json}"),
            mutating=True,
            dry_run_required=True,
            confirmation="type_job_id",
        ),
        CommandEntry(
            id="workbench.publish_spell",
            label="Publish Managed Spell",
            category="content",
            kind="mutation",
            dry_run_argv=_py("wm.content.workbench", "publish-spell", "--draft-json", "{input_json}", "--mode", "dry-run", "--output-json", "{result_json}"),
            apply_argv=_py("wm.content.workbench", "publish-spell", "--draft-json", "{input_json}", "--mode", "apply", "--output-json", "{result_json}"),
            mutating=True,
            dry_run_required=True,
            confirmation="type_job_id",
        ),
        CommandEntry(
            id="workbench.publish_shell",
            label="Publish Shell",
            category="content",
            kind="mutation",
            dry_run_argv=_py("wm.content.workbench", "publish-shell", "--draft-json", "{input_json}", "--mode", "dry-run", "--output-json", "{result_json}"),
            apply_argv=_py("wm.content.workbench", "publish-shell", "--draft-json", "{input_json}", "--mode", "apply", "--output-json", "{result_json}"),
            mutating=True,
            dry_run_required=True,
            confirmation="type_job_id",
        ),
        CommandEntry(
            id="items.rollback",
            label="Rollback Item",
            category="maintenance",
            kind="mutation",
            dry_run_argv=_py("wm.items.rollback", "--item-entry", "{item_entry}", "--mode", "dry-run", "--summary"),
            apply_argv=_py("wm.items.rollback", "--item-entry", "{item_entry}", "--mode", "apply", "--summary"),
            mutating=True,
            dry_run_required=True,
            confirmation="type_job_id",
            parameters=(ParameterSpec("item_entry", type="integer", required=True),),
        ),
        CommandEntry(
            id="quests.purge_range",
            label="Purge Draft Quest",
            category="maintenance",
            kind="mutation",
            dry_run_argv=_py("wm.quests.purge_range", "--start-id", "{quest_id}", "--end-id", "{quest_id}", "--mode", "dry-run", "--summary"),
            apply_argv=_py("wm.quests.purge_range", "--start-id", "{quest_id}", "--end-id", "{quest_id}", "--mode", "apply", "--summary"),
            mutating=True,
            dry_run_required=True,
            confirmation="type_job_id",
            parameters=(ParameterSpec("quest_id", type="integer", required=True),),
        ),
    ]
