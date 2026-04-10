from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

from wm.control.models import ControlProposal


@dataclass(slots=True)
class ControlRegistry:
    root: Path
    registry: dict[str, Any]
    events: dict[str, dict[str, Any]]
    actions: dict[str, dict[str, Any]]
    recipes: dict[str, dict[str, Any]]
    policies: dict[str, dict[str, Any]]
    runtime: dict[str, dict[str, Any]]
    registry_hash: str
    schema_hash: str

    @classmethod
    def load(cls, root: str | Path) -> "ControlRegistry":
        root_path = Path(root)
        registry_path = root_path / "registry.json"
        registry = _read_json(registry_path)
        events = _load_named_documents(root_path / str(registry.get("events_dir", "events")))
        actions = _load_named_documents(root_path / str(registry.get("actions_dir", "actions")))
        recipes = _load_named_documents(root_path / str(registry.get("recipes_dir", "recipes")))
        policies = _load_named_documents(root_path / str(registry.get("policies_dir", "policies")))
        runtime = _load_named_documents(root_path / str(registry.get("runtime_dir", "runtime")))
        bundle = {
            "registry": registry,
            "events": events,
            "actions": actions,
            "recipes": recipes,
            "policies": policies,
            "runtime": runtime,
        }
        registry_hash = _hash_json(bundle)
        schema_hash = _hash_json(ControlProposal.model_json_schema())
        return cls(
            root=root_path,
            registry=registry,
            events=events,
            actions=actions,
            recipes=recipes,
            policies=policies,
            runtime=runtime,
            registry_hash=registry_hash,
            schema_hash=schema_hash,
        )

    @property
    def default_policy(self) -> dict[str, Any]:
        policy_id = str(self.registry.get("default_policy", "direct_apply"))
        return self.policies.get(policy_id, {})

    def validate(self) -> list[str]:
        issues: list[str] = []
        for kind, docs in (("event", self.events), ("action", self.actions), ("recipe", self.recipes)):
            for doc_id, doc in docs.items():
                if doc.get("id") != doc_id:
                    issues.append(f"{kind} {doc_id} has mismatched id {doc.get('id')!r}")
                if "schema_version" not in doc:
                    issues.append(f"{kind} {doc_id} is missing schema_version")

        for recipe_id, recipe in self.recipes.items():
            for event_type in recipe.get("trigger_event_types", []):
                if not self.event_for_type(str(event_type)):
                    issues.append(f"recipe {recipe_id} references unknown event_type {event_type}")
            for action_id in recipe.get("allowed_actions", []):
                if str(action_id) not in self.actions:
                    issues.append(f"recipe {recipe_id} references unknown action {action_id}")
            default_action = recipe.get("default_action")
            if isinstance(default_action, dict):
                default_kind = default_action.get("kind")
                if default_kind and default_kind not in recipe.get("allowed_actions", []):
                    issues.append(f"recipe {recipe_id} default action {default_kind} is not allowed by the recipe")
        return issues

    def event_for_type(self, event_type: str) -> dict[str, Any] | None:
        for event in self.events.values():
            if event.get("event_type") == event_type:
                return event
        return None

    def eligible_recipes_for_event_type(self, event_type: str) -> list[dict[str, Any]]:
        return [
            recipe
            for recipe in self.recipes.values()
            if recipe.get("enabled", True) and event_type in recipe.get("trigger_event_types", [])
        ]

    def action(self, action_id: str) -> dict[str, Any] | None:
        return self.actions.get(action_id)

    def recipe(self, recipe_id: str) -> dict[str, Any] | None:
        return self.recipes.get(recipe_id)


def _load_named_documents(path: Path) -> dict[str, dict[str, Any]]:
    docs: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return docs
    for file_path in sorted(path.glob("**/*.json")):
        data = _read_json(file_path)
        doc_id = str(data.get("id") or file_path.stem)
        if doc_id in docs:
            raise ValueError(f"Duplicate control id {doc_id!r} in {path}")
        docs[doc_id] = data
    return docs


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return data


def _hash_json(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
