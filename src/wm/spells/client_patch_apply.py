"""Apply pending client patches when it is safe (client closed).

Decision + orchestration only; the actual MPQ build/install is the existing
wm.spells.client_patch.build_client_patch_package, injected as build_fn so the
logic is unit-testable without MPQEditor or a real client."""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Callable

from wm.spells.client_patch_pending import load_pending, clear_pending


def _default_build_fn(**kwargs: Any) -> Any:
    from wm.spells.client_patch import (
        build_client_patch_package, default_source_dbc_path,
        default_package_path, default_mpq_editor_path, default_install_path,
    )
    kwargs.setdefault("source_dbc", str(default_source_dbc_path()))
    kwargs.setdefault("package_out", str(default_package_path()))
    kwargs.setdefault("mpq_editor", str(default_mpq_editor_path()))
    if kwargs.get("install_path") is None:
        kwargs["install_path"] = str(default_install_path())
    return build_client_patch_package(**kwargs)


def _default_cache_clear() -> None:
    script = Path(__file__).resolve().parents[3].joinpath("scripts", "client", "Clear-WoWItemCache.ps1")
    if not script.exists():
        return
    subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)],
        capture_output=True, text=True, check=False,
    )


def apply_pending_client_patch(
    *,
    install_path: str | Path | None = None,
    mpq_editor: str | Path | None = None,
    pending_path: str | Path | None = None,
    build_fn: Callable[..., Any] = _default_build_fn,
    cache_clear_fn: Callable[[], None] = _default_cache_clear,
) -> dict[str, Any]:
    state = load_pending(path=pending_path)
    if not state["entries"]:
        return {"applied": False, "reason": "nothing pending"}

    spell_ids = [int(e["spell_id"]) for e in state["entries"]]
    build_kwargs: dict[str, Any] = {"include": "all"}
    if install_path is not None:
        build_kwargs["install_path"] = install_path
    if mpq_editor is not None:
        build_kwargs["mpq_editor"] = mpq_editor

    try:
        result = build_fn(**build_kwargs)
    except Exception as exc:
        return {"applied": False, "error": str(exc), "spell_ids": spell_ids}

    try:
        cache_clear_fn()
    except Exception:
        pass

    clear_pending(path=pending_path)
    return {"applied": True, "spell_ids": spell_ids, "result": result}


class ClientPatchCloseWatcher:
    """Fires apply_fn on each wow.exe running -> not-running transition.

    Pure edge logic: the caller feeds `running` (from any process probe) each
    tick; we only fire when the previous tick was running and this one is not.
    """
    def __init__(self, *, apply_fn: Callable[[], Any]) -> None:
        self._apply_fn = apply_fn
        self._was_running = False

    def tick(self, *, running: bool) -> Any | None:
        fired = None
        if self._was_running and not running:
            fired = self._apply_fn()
        self._was_running = running
        return fired


def main(argv: list[str] | None = None) -> int:
    import argparse
    import json
    p = argparse.ArgumentParser(prog="python -m wm.spells.client_patch_apply",
                                description="Apply the pending client patch now (build-all + install).")
    p.add_argument("--install-path", default=None)
    p.add_argument("--mpq-editor", default=None)
    args = p.parse_args(argv)
    out = apply_pending_client_patch(install_path=args.install_path, mpq_editor=args.mpq_editor)
    print(json.dumps(out, default=str))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
