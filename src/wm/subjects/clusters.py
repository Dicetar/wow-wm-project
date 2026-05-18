from __future__ import annotations

from wm.subjects.enrichment import ClusterRow
from wm.subjects.models import SubjectCluster


def build_subject_cluster(entry: int, cluster_rows: list[ClusterRow]) -> SubjectCluster:
    """Build a SubjectCluster from DB rows. Missing rows yield None fields."""
    archetype_key: str | None = None
    family_cluster: str | None = None
    local_pop_key: str | None = None

    for row in cluster_rows:
        if row.cluster_type == "archetype":
            archetype_key = row.cluster_key
        elif row.cluster_type == "family":
            family_cluster = row.cluster_key
        elif row.cluster_type == "local_population":
            local_pop_key = row.cluster_key

    return SubjectCluster(
        exact_entry=entry,
        archetype_key=archetype_key,
        family_cluster=family_cluster,
        local_pop_key=local_pop_key,
    )
