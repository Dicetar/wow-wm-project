from __future__ import annotations

from dataclasses import asdict
from dataclasses import dataclass
from typing import Any

from wm.config import Settings
from wm.runtime_sync import RuntimeCommandResult
from wm.runtime_sync import SoapRuntimeClient


@dataclass(slots=True)
class QuestGrantPreview:
    ok: bool
    player_guid: int
    player_name: str | None
    quest_id: int
    command_preview: str | None
    issues: list[dict[str, str]]
    notes: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ReactiveQuestRuntimeManager:
    def __init__(
        self,
        *,
        settings: Settings,
        soap_client: SoapRuntimeClient,
    ) -> None:
        self.settings = settings
        self.soap_client = soap_client

    def preview_grant(self, *, player_guid: int, player_name: str | None, quest_id: int) -> QuestGrantPreview:
        issues: list[dict[str, str]] = []
        notes: list[str] = []
        if not self.settings.soap_enabled:
            issues.append(
                {
                    "path": "soap_enabled",
                    "message": "WM_SOAP_ENABLED is not set, so live quest grant cannot run.",
                    "severity": "error",
                }
            )
        if not self.settings.soap_user or not self.settings.soap_password:
            issues.append(
                {
                    "path": "soap_credentials",
                    "message": "WM_SOAP_USER / WM_SOAP_PASSWORD are required for direct quest grant.",
                    "severity": "error",
                }
            )
        if player_name in (None, ""):
            issues.append(
                {
                    "path": "player_name",
                    "message": f"Could not resolve player GUID {player_guid} into a character name.",
                    "severity": "error",
                }
            )

        command_preview = None
        if player_name not in (None, ""):
            command_preview = build_quest_add_command(player_name=str(player_name), quest_id=quest_id)
            notes.append("Quest grant uses the AzerothCore GM quest command path over SOAP.")

        ok = not any(issue["severity"] == "error" for issue in issues)
        return QuestGrantPreview(
            ok=ok,
            player_guid=int(player_guid),
            player_name=str(player_name) if player_name not in (None, "") else None,
            quest_id=int(quest_id),
            command_preview=command_preview,
            issues=issues,
            notes=notes,
        )

    def grant_quest(self, *, player_guid: int, player_name: str | None, quest_id: int) -> RuntimeCommandResult:
        preview = self.preview_grant(player_guid=player_guid, player_name=player_name, quest_id=quest_id)
        if not preview.ok or preview.command_preview is None:
            return RuntimeCommandResult(
                command=preview.command_preview or "",
                ok=False,
                fault_code="PreviewError",
                fault_string="; ".join(issue["message"] for issue in preview.issues) or "Quest grant preview failed.",
            )
        result = self.soap_client.execute_command(preview.command_preview)
        result.command = preview.command_preview
        return result

    def remove_quest(self, *, player_guid: int, player_name: str | None, quest_id: int) -> RuntimeCommandResult:
        preview = self.preview_grant(player_guid=player_guid, player_name=player_name, quest_id=quest_id)
        if not preview.ok or preview.player_name is None:
            return RuntimeCommandResult(
                command="",
                ok=False,
                fault_code="PreviewError",
                fault_string="Quest remove preview failed.",
            )
        command = build_quest_remove_command(player_name=preview.player_name, quest_id=quest_id)
        result = self.soap_client.execute_command(command)
        result.command = command
        return result

    def reward_quest(self, *, player_guid: int, player_name: str | None, quest_id: int) -> RuntimeCommandResult:
        preview = self.preview_grant(player_guid=player_guid, player_name=player_name, quest_id=quest_id)
        if not preview.ok or preview.player_name is None:
            return RuntimeCommandResult(
                command="",
                ok=False,
                fault_code="PreviewError",
                fault_string="Quest reward preview failed.",
            )
        command = build_quest_reward_command(player_name=preview.player_name, quest_id=quest_id)
        result = self.soap_client.execute_command(command)
        result.command = command
        return result


def build_quest_add_command(*, player_name: str, quest_id: int) -> str:
    return f".quest add {int(quest_id)} {player_name}"


def build_quest_remove_command(*, player_name: str, quest_id: int) -> str:
    return f".quest remove {int(quest_id)} {player_name}"


def build_quest_reward_command(*, player_name: str, quest_id: int) -> str:
    return f".quest reward {int(quest_id)} {player_name}"
