from wm.spells.client_patch_pending import mark_pending, load_pending, clear_pending


def test_mark_load_clear_roundtrip(tmp_path):
    p = tmp_path / "client_patch_pending.json"
    assert load_pending(path=p)["entries"] == []

    st = mark_pending([947000], reason="spell publish", names={947000: "Cloud Step"}, path=p)
    assert st["schema_version"] == "wm.client_patch_pending.v1"
    assert [e["spell_id"] for e in st["entries"]] == [947000]
    assert st["entries"][0]["name"] == "Cloud Step"
    assert st["entries"][0]["reason"] == "spell publish"
    assert "queued_at" in st["entries"][0]

    st = mark_pending([947000, 947001], reason="spell publish", path=p)
    assert sorted(e["spell_id"] for e in st["entries"]) == [947000, 947001]

    assert load_pending(path=p)["entries"]
    cleared = clear_pending(path=p)
    assert cleared["entries"] == []
    assert cleared["last_applied_at"] is not None
    assert load_pending(path=p)["entries"] == []
