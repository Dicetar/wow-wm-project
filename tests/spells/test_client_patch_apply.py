import pytest
from wm.spells.client_patch_apply import apply_pending_client_patch
from wm.spells.client_patch_pending import mark_pending, load_pending


def _build_ok(**kwargs):
    return {"ok": True, "kwargs": kwargs}


def test_apply_noop_when_nothing_pending(tmp_path):
    p = tmp_path / "pending.json"
    calls = []
    out = apply_pending_client_patch(pending_path=p, build_fn=lambda **k: calls.append(k))
    assert out["applied"] is False
    assert out["reason"] == "nothing pending"
    assert calls == []


def test_apply_builds_installs_and_clears_when_pending(tmp_path):
    p = tmp_path / "pending.json"
    mark_pending([947000], reason="spell publish", path=p)
    build_calls, cache_calls = [], []

    out = apply_pending_client_patch(
        pending_path=p,
        install_path="C:/WoW/Data",
        build_fn=lambda **k: build_calls.append(k) or _build_ok(**k),
        cache_clear_fn=lambda: cache_calls.append(True),
    )
    assert out["applied"] is True
    assert build_calls and build_calls[0]["include"] == "all"
    assert build_calls[0]["install_path"] == "C:/WoW/Data"
    assert cache_calls == [True]
    assert load_pending(path=p)["entries"] == []


def test_apply_keeps_pending_on_build_failure(tmp_path):
    p = tmp_path / "pending.json"
    mark_pending([947000], reason="spell publish", path=p)

    def boom(**k):
        raise RuntimeError("MPQEditor missing")

    out = apply_pending_client_patch(pending_path=p, install_path="C:/WoW/Data", build_fn=boom)
    assert out["applied"] is False
    assert "MPQEditor missing" in out["error"]
    assert load_pending(path=p)["entries"]


def test_close_watcher_fires_only_on_running_to_closed_edge():
    from wm.spells.client_patch_apply import ClientPatchCloseWatcher
    fired = []
    w = ClientPatchCloseWatcher(apply_fn=lambda: fired.append(True) or {"applied": True})
    assert w.tick(running=False) is None
    assert w.tick(running=True) is None
    assert w.tick(running=True) is None
    assert w.tick(running=False) == {"applied": True}
    assert w.tick(running=False) is None
    assert fired == [True]


def test_close_watcher_handles_open_close_open_close():
    from wm.spells.client_patch_apply import ClientPatchCloseWatcher
    fired = []
    w = ClientPatchCloseWatcher(apply_fn=lambda: fired.append(1) or {})
    for running in (True, False, True, False):
        w.tick(running=running)
    assert fired == [1, 1]


def test_cli_apply_now_invokes_apply(monkeypatch, capsys):
    import wm.spells.client_patch_apply as mod
    called = {}
    monkeypatch.setattr(mod, "apply_pending_client_patch",
                        lambda **k: called.update(k) or {"applied": False, "reason": "nothing pending"})
    rc = mod.main(["--install-path", "C:/WoW/Data"])
    assert rc == 0
    assert called["install_path"] == "C:/WoW/Data"
    assert "applied" in capsys.readouterr().out
