from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class SubjectDefinition:
    entry: int
    display_name: str
    archetype_key: str | None
    settlement_role: str | None
    area_context_json: str | None


@dataclass
class ClusterRow:
    cluster_key: str
    cluster_type: str
    zone_id: int | None


class EnrichmentLoader:
    """Loads enrichment data from wm_subject_* tables. Gracefully returns empty when DB is None."""

    def __init__(self, db_client: Any):
        self._db = db_client

    def load_definition(self, entry: int) -> SubjectDefinition | None:
        if self._db is None:
            return None
        try:
            rows = self._db.query(
                "SELECT entry, display_name, archetype_key, settlement_role, area_context_json "
                "FROM wm_subject_definition WHERE entry = %s",
                (entry,)
            )
            if not rows:
                return None
            r = rows[0]
            return SubjectDefinition(
                entry=r["entry"], display_name=r["display_name"],
                archetype_key=r.get("archetype_key"),
                settlement_role=r.get("settlement_role"),
                area_context_json=r.get("area_context_json"),
            )
        except Exception:
            return None

    def load_notes(self, entry: int) -> list[str]:
        if self._db is None:
            return []
        try:
            rows = self._db.query(
                "SELECT note_value FROM wm_subject_enrichment WHERE entry = %s ORDER BY added_at",
                (entry,)
            )
            return [r["note_value"] for r in rows]
        except Exception:
            return []

    def load_clusters(self, entry: int) -> list[ClusterRow]:
        if self._db is None:
            return []
        try:
            rows = self._db.query(
                "SELECT cluster_key, cluster_type, zone_id FROM wm_subject_cluster WHERE entry = %s",
                (entry,)
            )
            return [ClusterRow(cluster_key=r["cluster_key"],
                               cluster_type=r["cluster_type"],
                               zone_id=r.get("zone_id")) for r in rows]
        except Exception:
            return []
