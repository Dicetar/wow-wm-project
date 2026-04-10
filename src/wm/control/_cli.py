from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from wm.config import Settings
from wm.control.coordinator import ControlCoordinator
from wm.control.models import ControlProposal
from wm.control.registry import ControlRegistry
from wm.control.store import ControlAuditStore
from wm.db.mysql_cli import MysqlCliClient
from wm.events.executor import ReactionExecutor
from wm.events.store import EventStore


def load_registry(settings: Settings) -> ControlRegistry:
    return ControlRegistry.load(settings.control_root)


def load_proposal(path: Path) -> ControlProposal:
    return ControlProposal.model_validate_json(path.read_text(encoding="utf-8"))


def write_json(value: Any, path: Path | None = None) -> None:
    if hasattr(value, "model_dump"):
        payload = value.model_dump(mode="json")
    elif hasattr(value, "to_dict"):
        payload = value.to_dict()
    else:
        payload = value
    raw = json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True)
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(raw + "\n", encoding="utf-8")
    print(raw)


def build_live_coordinator(settings: Settings) -> ControlCoordinator:
    client = MysqlCliClient()
    event_store = EventStore(client=client, settings=settings)
    return ControlCoordinator(
        registry=load_registry(settings),
        event_store=event_store,
        executor=ReactionExecutor(client=client, settings=settings, store=event_store),
        audit_store=ControlAuditStore(client=client, settings=settings),
    )


def default_proposal_output_path(settings: Settings, *, event_id: int | None, recipe_id: str, action_kind: str) -> Path:
    base = Path(settings.control_proposal_state_path)
    event_part = f"event-{event_id}" if event_id is not None else "admin"
    return base / f"{event_part}-{recipe_id}-{action_kind}.json"
