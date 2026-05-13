from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from wm.content.release import validate_content_release_spec
from wm.control.models import ControlProposal


@dataclass(frozen=True, slots=True)
class SchemaIssue:
    path: str
    message: str
    severity: str = "error"

    def to_dict(self) -> dict[str, str]:
        return {"path": self.path, "message": self.message, "severity": self.severity}


@dataclass(frozen=True, slots=True)
class SchemaEntry:
    id: str
    label: str
    description: str
    lane: str
    mutating: bool
    dry_run_required: bool
    validator: str
    schema: dict[str, Any]
    ui: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "description": self.description,
            "lane": self.lane,
            "mutating": self.mutating,
            "dry_run_required": self.dry_run_required,
            "validator": self.validator,
            "schema": self.schema,
            "ui": self.ui,
        }


class SchemaCatalog:
    def __init__(self, entries: list[SchemaEntry]) -> None:
        self.entries = entries
        self.by_id = {entry.id: entry for entry in entries}

    @classmethod
    def load(cls, path: str | Path | None = None) -> "SchemaCatalog":
        catalog_path = Path(path) if path is not None else Path(__file__).parent / "schemas" / "catalog.json"
        raw = json.loads(catalog_path.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            raise ValueError("Panel schema catalog must be a JSON array.")
        entries: list[SchemaEntry] = []
        for item in raw:
            if not isinstance(item, dict):
                raise ValueError("Panel schema catalog entries must be JSON objects.")
            schema = dict(item.get("schema") or {})
            if item.get("id") == "control.proposal.v1":
                schema = ControlProposal.model_json_schema()
            entries.append(
                SchemaEntry(
                    id=str(item["id"]),
                    label=str(item.get("label") or item["id"]),
                    description=str(item.get("description") or ""),
                    lane=str(item.get("lane") or "unknown"),
                    mutating=bool(item.get("mutating", True)),
                    dry_run_required=bool(item.get("dry_run_required", True)),
                    validator=str(item.get("validator") or "json_schema"),
                    schema=schema,
                    ui=dict(item.get("ui") or {}),
                )
            )
        return cls(entries)

    def get(self, schema_version: str) -> SchemaEntry:
        try:
            return self.by_id[schema_version]
        except KeyError as exc:
            raise KeyError(f"Unknown schema_version: {schema_version}") from exc

    def list_api(self) -> list[dict[str, Any]]:
        return [entry.to_dict() for entry in self.entries]

    def validate(self, schema_version: str, payload: Any) -> dict[str, Any]:
        try:
            entry = self.get(schema_version)
        except KeyError as exc:
            return {
                "ok": False,
                "schema_version": schema_version,
                "issues": [SchemaIssue(path="schema_version", message=str(exc)).to_dict()],
            }

        issues = _validate_json_schema(entry.schema, payload, path="")
        domain = _validate_domain(entry, payload)
        issues.extend(SchemaIssue(**issue) for issue in domain.get("issues", []))
        ok = not any(issue.severity == "error" for issue in issues)
        return {
            "ok": ok,
            "schema_version": schema_version,
            "validator": entry.validator,
            "issues": [issue.to_dict() for issue in issues],
            "domain": domain,
        }


def _validate_domain(entry: SchemaEntry, payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {"ok": False, "issues": [SchemaIssue(path="", message="Payload must be a JSON object.").to_dict()]}
    if entry.validator == "wm.content.release":
        result = validate_content_release_spec(payload)
        return {
            "ok": result.ok,
            "issues": [issue.to_dict() for issue in result.issues],
            "content_kind": result.content_kind,
            "quest_kind": result.quest_kind,
        }
    if entry.validator == "wm.control.proposal":
        try:
            proposal = ControlProposal.model_validate(payload)
        except ValidationError as exc:
            return {
                "ok": False,
                "issues": [
                    SchemaIssue(path=".".join(str(part) for part in error.get("loc", ())), message=str(error.get("msg"))).to_dict()
                    for error in exc.errors()
                ],
            }
        return {"ok": True, "issues": [], "normalized": proposal.model_dump(mode="json")}
    return {"ok": True, "issues": []}


def _validate_json_schema(schema: dict[str, Any], value: Any, *, path: str) -> list[SchemaIssue]:
    issues: list[SchemaIssue] = []
    if not schema:
        return issues

    if "$ref" in schema:
        return issues

    if "const" in schema and value != schema["const"]:
        issues.append(SchemaIssue(path=path, message=f"Value must be {schema['const']!r}."))
    if "enum" in schema and value not in list(schema["enum"]):
        choices = ", ".join(str(item) for item in schema["enum"])
        issues.append(SchemaIssue(path=path, message=f"Value must be one of: {choices}."))

    expected_type = schema.get("type")
    if expected_type is not None and not _matches_type(value, expected_type):
        issues.append(SchemaIssue(path=path, message=f"Expected JSON type {_type_label(expected_type)}."))
        return issues

    if value is None:
        return issues

    if _has_type(schema, "object"):
        if not isinstance(value, dict):
            return issues
        properties = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
        for required_key in schema.get("required") or []:
            if required_key not in value:
                issues.append(SchemaIssue(path=_join_path(path, str(required_key)), message="Required field is missing."))
        if schema.get("additionalProperties") is False:
            for key in sorted(set(value) - set(properties)):
                issues.append(SchemaIssue(path=_join_path(path, str(key)), message="Unsupported field."))
        for key, nested_schema in properties.items():
            if key in value and isinstance(nested_schema, dict):
                issues.extend(_validate_json_schema(nested_schema, value[key], path=_join_path(path, str(key))))

    if _has_type(schema, "array"):
        if not isinstance(value, list):
            return issues
        min_items = schema.get("minItems")
        if isinstance(min_items, int) and len(value) < min_items:
            issues.append(SchemaIssue(path=path, message=f"Expected at least {min_items} item(s)."))
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                issues.extend(_validate_json_schema(item_schema, item, path=f"{path}[{index}]" if path else f"[{index}]"))

    if _has_type(schema, "string") and isinstance(value, str):
        min_length = schema.get("minLength")
        if isinstance(min_length, int) and len(value) < min_length:
            issues.append(SchemaIssue(path=path, message=f"Expected at least {min_length} character(s)."))
    if (_has_type(schema, "integer") or _has_type(schema, "number")) and isinstance(value, int | float) and not isinstance(value, bool):
        minimum = schema.get("minimum")
        if isinstance(minimum, int | float) and value < minimum:
            issues.append(SchemaIssue(path=path, message=f"Expected value >= {minimum}."))
        maximum = schema.get("maximum")
        if isinstance(maximum, int | float) and value > maximum:
            issues.append(SchemaIssue(path=path, message=f"Expected value <= {maximum}."))
    return issues


def _matches_type(value: Any, expected_type: Any) -> bool:
    allowed = expected_type if isinstance(expected_type, list) else [expected_type]
    return any(_matches_single_type(value, item) for item in allowed)


def _matches_single_type(value: Any, expected_type: str) -> bool:
    if expected_type == "null":
        return value is None
    if expected_type == "object":
        return isinstance(value, dict)
    if expected_type == "array":
        return isinstance(value, list)
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "number":
        return (isinstance(value, int | float) and not isinstance(value, bool))
    if expected_type == "boolean":
        return isinstance(value, bool)
    return True


def _has_type(schema: dict[str, Any], expected_type: str) -> bool:
    schema_type = schema.get("type")
    if schema_type is None:
        return False
    if isinstance(schema_type, list):
        return expected_type in schema_type
    return schema_type == expected_type


def _type_label(expected_type: Any) -> str:
    if isinstance(expected_type, list):
        return " or ".join(str(item) for item in expected_type)
    return str(expected_type)


def _join_path(parent: str, child: str) -> str:
    return f"{parent}.{child}" if parent else child
