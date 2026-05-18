"""Managed content artifacts — WM-owned WoW IDs with lifecycle tracking."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

ArtifactKind = Literal["quest", "item", "creature", "spell", "gossip", "scene"]
ArtifactStatus = Literal["reserved", "active", "retired", "error"]


@dataclass(slots=True)
class ManagedArtifact:
    artifact_id: int
    kind: ArtifactKind
    status: ArtifactStatus
    label: str
    owner_key: str
    schema_version: str = "wm.artifact.v1"
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "kind": self.kind,
            "status": self.status,
            "label": self.label,
            "owner_key": self.owner_key,
            "schema_version": self.schema_version,
            "metadata": self.metadata,
        }


class ArtifactRegistry:
    def __init__(self, db_client: Any = None):
        self._db = db_client

    def register(self, artifact: ManagedArtifact) -> None:
        if self._db is None:
            return
        import json
        self._db.execute(
            """
            INSERT INTO wm_artifact
                (id, kind, status, label, owner_key, schema_version, metadata_json)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                status = VALUES(status),
                label = VALUES(label),
                owner_key = VALUES(owner_key),
                metadata_json = VALUES(metadata_json),
                updated_at = NOW()
            """,
            (
                artifact.artifact_id, artifact.kind, artifact.status,
                artifact.label, artifact.owner_key, artifact.schema_version,
                json.dumps(artifact.metadata) if artifact.metadata else None,
            ),
        )

    def retire(self, artifact_id: int, kind: ArtifactKind) -> None:
        if self._db is None:
            return
        self._db.execute(
            "UPDATE wm_artifact SET status = 'retired', updated_at = NOW() "
            "WHERE id = %s AND kind = %s",
            (artifact_id, kind),
        )

    def load(self, artifact_id: int, kind: ArtifactKind) -> ManagedArtifact | None:
        if self._db is None:
            return None
        rows = self._db.query(
            "SELECT id, kind, status, label, owner_key, schema_version, metadata_json "
            "FROM wm_artifact WHERE id = %s AND kind = %s",
            (artifact_id, kind),
        )
        if not rows:
            return None
        import json
        r = rows[0]
        raw_meta = r.get("metadata_json")
        return ManagedArtifact(
            artifact_id=int(r["id"]),
            kind=r["kind"],
            status=r["status"],
            label=r.get("label", ""),
            owner_key=r.get("owner_key", ""),
            schema_version=r.get("schema_version", "wm.artifact.v1"),
            metadata=json.loads(raw_meta) if raw_meta else {},
        )

    def list_active(self, kind: ArtifactKind | None = None) -> list[ManagedArtifact]:
        if self._db is None:
            return []
        import json
        if kind is not None:
            rows = self._db.query(
                "SELECT id, kind, status, label, owner_key, schema_version, metadata_json "
                "FROM wm_artifact WHERE status = 'active' AND kind = %s ORDER BY id",
                (kind,),
            )
        else:
            rows = self._db.query(
                "SELECT id, kind, status, label, owner_key, schema_version, metadata_json "
                "FROM wm_artifact WHERE status = 'active' ORDER BY kind, id",
            )
        result = []
        for r in rows:
            raw_meta = r.get("metadata_json")
            result.append(ManagedArtifact(
                artifact_id=int(r["id"]),
                kind=r["kind"],
                status=r["status"],
                label=r.get("label", ""),
                owner_key=r.get("owner_key", ""),
                schema_version=r.get("schema_version", "wm.artifact.v1"),
                metadata=json.loads(raw_meta) if raw_meta else {},
            ))
        return result
