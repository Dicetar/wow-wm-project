from __future__ import annotations

from pathlib import Path
import subprocess
from typing import Any

from wm.autoplay._compact import _int_or_none
from wm.config import Settings


def status_summary(status: dict[str, Any]) -> str:
    readiness = status.get("readiness") or {}
    llm = status.get("llm") or {}
    session = status.get("active_session") or {}
    safe_window = status.get("safe_window") or {}
    counters = status.get("counters") or {}
    config = status.get("config") or {}
    return " ".join(
        [
            f"status={status.get('status')}",
            f"running={str(bool(status.get('running'))).lower()}",
            f"paused={str(bool(status.get('paused'))).lower()}",
            f"player_guid={session.get('character_guid') or '(none)'}",
            f"client_running={str(bool(safe_window.get('client_running'))).lower()}",
            f"scoped_player_online={str(bool(safe_window.get('scoped_player_online'))).lower()}",
            f"readiness={str(bool(readiness.get('ok'))).lower()}",
            f"llm={str(bool(llm.get('ok'))).lower()}",
            f"model={llm.get('model') or config.get('llm_model') or '(none)'}",
            f"llm_enabled={str(bool(config.get('llm_enabled', True))).lower()}",
            f"wm_chat={str(bool(config.get('llm_chat_enabled', True))).lower()}",
            f"chat_epoch={int(config.get('llm_chat_context_epoch') or 0)}",
            f"lanes={','.join(str(item) for item in config.get('llm_lanes', [])) or '(none)'}",
            f"ticks={counters.get('ticks', 0)}",
            f"drafts={counters.get('drafts_generated', 0)}",
            f"chat={counters.get('chat_replies', 0)}",
            f"issues={len(status.get('issues') or [])}",
            f"maintenance={len(status.get('maintenance_pending') or [])}",
        ]
    )


def _read_pid(path: Path) -> int | None:
    if not path.exists():
        return None
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def _process_exists(pid: int) -> bool:
    try:
        completed = subprocess.run(
            ["tasklist", "/FI", f"PID eq {int(pid)}"],
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        return False
    return str(int(pid)) in (completed.stdout or "")


def _wow_client_running() -> bool:
    try:
        completed = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq wow.exe"],
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        return False
    return "wow.exe" in (completed.stdout or "").lower()


def _is_scoped_player_online(*, settings: Settings, session: dict[str, Any] | None) -> bool:
    guid = _int_or_none((session or {}).get("character_guid"))
    if guid is None:
        return False
    try:
        from wm.db.mysql_cli import MysqlCliClient

        rows = MysqlCliClient().query(
            host=settings.char_db_host,
            port=settings.char_db_port,
            user=settings.char_db_user,
            password=settings.char_db_password,
            database=settings.char_db_name,
            sql=f"SELECT online FROM characters WHERE guid = {int(guid)} LIMIT 1",
        )
    except Exception:
        return False
    if not rows:
        return False
    try:
        return int(rows[0].get("online") or 0) > 0
    except (TypeError, ValueError):
        return False
