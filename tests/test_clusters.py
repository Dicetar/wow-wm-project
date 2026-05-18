"""Tests for build_subject_cluster."""
from __future__ import annotations


def test_build_cluster_from_enrichment_rows():
    from wm.subjects.clusters import build_subject_cluster
    from wm.subjects.enrichment import ClusterRow
    rows = [
        ClusterRow(cluster_key="wolves_elwynn", cluster_type="family", zone_id=12),
        ClusterRow(cluster_key="wolf", cluster_type="archetype", zone_id=None),
    ]
    cluster = build_subject_cluster(entry=3100, cluster_rows=rows)
    assert cluster.exact_entry == 3100
    assert cluster.archetype_key == "wolf"
    assert cluster.family_cluster == "wolves_elwynn"


def test_build_cluster_empty_rows():
    from wm.subjects.clusters import build_subject_cluster
    cluster = build_subject_cluster(entry=3100, cluster_rows=[])
    assert cluster.exact_entry == 3100
    assert cluster.archetype_key is None
    assert cluster.family_cluster is None
    assert cluster.local_pop_key is None
