"""Tests for EnrichmentLoader graceful no-DB fallback."""
from __future__ import annotations


def test_subject_definition_graceful_no_db():
    from wm.subjects.enrichment import EnrichmentLoader
    loader = EnrichmentLoader(db_client=None)
    defn = loader.load_definition(entry=3100)
    assert defn is None


def test_subject_notes_graceful_no_db():
    from wm.subjects.enrichment import EnrichmentLoader
    loader = EnrichmentLoader(db_client=None)
    notes = loader.load_notes(entry=3100)
    assert notes == []


def test_subject_cluster_graceful_no_db():
    from wm.subjects.enrichment import EnrichmentLoader
    loader = EnrichmentLoader(db_client=None)
    clusters = loader.load_clusters(entry=3100)
    assert clusters == []
