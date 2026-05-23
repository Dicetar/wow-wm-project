from wm.spells import publish as publish_mod
from wm.spells.client_patch_pending import load_pending


def test_publish_marks_pending_on_apply(monkeypatch):
    calls = []
    monkeypatch.setattr(publish_mod, "mark_pending",
                        lambda spell_ids, **k: calls.append((list(spell_ids), k)))
    publish_mod._note_client_patch_pending(spell_entry=947000, mode="apply", applied=True)
    assert calls and calls[0][0] == [947000]
    assert calls[0][1]["reason"]


def test_publish_does_not_mark_on_dry_run_or_not_applied(monkeypatch):
    calls = []
    monkeypatch.setattr(publish_mod, "mark_pending", lambda spell_ids, **k: calls.append(1))
    publish_mod._note_client_patch_pending(spell_entry=947000, mode="dry-run", applied=False)
    publish_mod._note_client_patch_pending(spell_entry=947000, mode="apply", applied=False)
    assert calls == []


def test_publish_hook_never_raises(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("disk full")
    monkeypatch.setattr(publish_mod, "mark_pending", boom)
    publish_mod._note_client_patch_pending(spell_entry=947000, mode="apply", applied=True)  # must not raise
