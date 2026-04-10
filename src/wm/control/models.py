from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


SCHEMA_VERSION = "control.proposal.v1"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ControlSourceEvent(StrictModel):
    event_id: int | None = None
    source: str | None = None
    source_event_key: str | None = None
    event_type: str | None = None

    @model_validator(mode="after")
    def require_event_reference(self) -> "ControlSourceEvent":
        if self.event_id is None and not self.source_event_key:
            raise ValueError("source_event requires event_id or source_event_key")
        return self


class ControlPlayer(StrictModel):
    guid: int
    name: str | None = None


class ControlAction(StrictModel):
    kind: str
    payload: dict[str, Any] = Field(default_factory=dict)


class ControlRisk(StrictModel):
    level: Literal["low", "medium", "high"] = "low"
    irreversible: bool = False
    notes: list[str] = Field(default_factory=list)


class ControlAuthor(StrictModel):
    kind: Literal["manual", "manual_admin", "llm"] = "manual"
    name: str | None = None
    manual_reason: str | None = None

    @model_validator(mode="after")
    def require_manual_admin_reason(self) -> "ControlAuthor":
        if self.kind == "manual_admin" and not (self.manual_reason or "").strip():
            raise ValueError("manual_admin proposals require manual_reason")
        return self


class ControlProposal(StrictModel):
    schema_version: Literal["control.proposal.v1"] = SCHEMA_VERSION
    source_event: ControlSourceEvent | None = None
    player: ControlPlayer
    selected_recipe: str
    action: ControlAction
    rationale: str
    risk: ControlRisk = Field(default_factory=ControlRisk)
    idempotency_key: str | None = None
    expected_effect: str | None = None
    author: ControlAuthor = Field(default_factory=ControlAuthor)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def require_event_for_non_admin(self) -> "ControlProposal":
        if self.author.kind != "manual_admin" and self.source_event is None:
            raise ValueError("non-admin proposals require source_event")
        return self


class ControlIssue(StrictModel):
    severity: Literal["error", "warning"] = "error"
    path: str
    message: str


class ControlValidationResult(StrictModel):
    ok: bool
    issues: list[ControlIssue] = Field(default_factory=list)
    normalized_proposal: dict[str, Any] | None = None
    registry_hash: str | None = None
    schema_hash: str | None = None
    policy: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_issues(
        cls,
        *,
        issues: list[ControlIssue],
        normalized_proposal: dict[str, Any] | None = None,
        registry_hash: str | None = None,
        schema_hash: str | None = None,
        policy: dict[str, Any] | None = None,
    ) -> "ControlValidationResult":
        return cls(
            ok=not any(issue.severity == "error" for issue in issues),
            issues=issues,
            normalized_proposal=normalized_proposal,
            registry_hash=registry_hash,
            schema_hash=schema_hash,
            policy=policy or {},
        )


RISK_ORDER = {"low": 0, "medium": 1, "high": 2}
