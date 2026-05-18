"""Tests for journal summarizer V2 prose output."""
from __future__ import annotations

from datetime import datetime, timedelta


def test_summarizer_produces_prose_for_rich_data():
    from wm.journal.summarizer import summarize_journal_counters

    counters = [
        {"counter_key": "kills", "count": 18,
         "last_at": (datetime.utcnow() - timedelta(days=2)).isoformat()},
        {"counter_key": "skins", "count": 10, "last_at": None},
    ]
    text = summarize_journal_counters(subject_name="Grey Wolf", counters=counters)
    assert "Grey Wolf" in text
    assert "18" in text
    assert "kill" in text.lower()


def test_summarizer_produces_minimal_text_for_empty_data():
    from wm.journal.summarizer import summarize_journal_counters
    text = summarize_journal_counters(subject_name="Murloc", counters=[])
    assert "Murloc" in text
    assert len(text) > 0
