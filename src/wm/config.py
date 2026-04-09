from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


def _load_dotenv(dotenv_path: str | Path = ".env") -> None:
    path = Path(dotenv_path)
    if not path.exists():
        return

    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key and key not in os.environ:
            os.environ[key] = value


@dataclass(slots=True)
class Settings:
    env: str = "dev"
    log_level: str = "INFO"

    world_db_host: str = "127.0.0.1"
    world_db_port: int = 3306
    world_db_name: str = "acore_world"
    world_db_user: str = "root"
    world_db_password: str = ""

    char_db_host: str = "127.0.0.1"
    char_db_port: int = 3306
    char_db_name: str = "acore_characters"
    char_db_user: str = "root"
    char_db_password: str = ""

    soap_enabled: bool = False
    soap_host: str = "127.0.0.1"
    soap_port: int = 7878
    soap_user: str = ""
    soap_password: str = ""
    soap_path: str = "/"

    event_default_questgiver_entry: int | None = None
    event_followup_kill_count: int = 6
    event_default_reward_money_copper: int = 1200
    addon_log_path: str = r"D:\WOW\Azerothcore_WoTLK_Repack\logs\WMOps.log"
    addon_log_batch_size: int = 200
    addon_channel_name: str = "WMBridgePrivate"
    addon_prefix: str = "WMBRIDGE"
    combat_log_path: str = r"D:\WOW\world of warcraft 3.3.5a hd\Logs\WoWCombatLog.txt"
    combat_log_batch_size: int = 200
    combat_log_player_name: str | None = None

    @classmethod
    def from_env(cls) -> "Settings":
        _load_dotenv()
        return cls(
            env=os.getenv("WM_ENV", "dev"),
            log_level=os.getenv("WM_LOG_LEVEL", "INFO"),
            world_db_host=os.getenv("WM_WORLD_DB_HOST", "127.0.0.1"),
            world_db_port=int(os.getenv("WM_WORLD_DB_PORT", "3306")),
            world_db_name=os.getenv("WM_WORLD_DB_NAME", "acore_world"),
            world_db_user=os.getenv("WM_WORLD_DB_USER", "root"),
            world_db_password=os.getenv("WM_WORLD_DB_PASSWORD", ""),
            char_db_host=os.getenv("WM_CHAR_DB_HOST", "127.0.0.1"),
            char_db_port=int(os.getenv("WM_CHAR_DB_PORT", "3306")),
            char_db_name=os.getenv("WM_CHAR_DB_NAME", "acore_characters"),
            char_db_user=os.getenv("WM_CHAR_DB_USER", "root"),
            char_db_password=os.getenv("WM_CHAR_DB_PASSWORD", ""),
            soap_enabled=os.getenv("WM_SOAP_ENABLED", "0").strip().lower() in {"1", "true", "yes", "on"},
            soap_host=os.getenv("WM_SOAP_HOST", "127.0.0.1"),
            soap_port=int(os.getenv("WM_SOAP_PORT", "7878")),
            soap_user=os.getenv("WM_SOAP_USER", ""),
            soap_password=os.getenv("WM_SOAP_PASSWORD", ""),
            soap_path=os.getenv("WM_SOAP_PATH", "/"),
            event_default_questgiver_entry=(
                int(os.getenv("WM_EVENT_DEFAULT_QUESTGIVER_ENTRY"))
                if os.getenv("WM_EVENT_DEFAULT_QUESTGIVER_ENTRY") not in (None, "")
                else None
            ),
            event_followup_kill_count=int(os.getenv("WM_EVENT_FOLLOWUP_KILL_COUNT", "6")),
            event_default_reward_money_copper=int(os.getenv("WM_EVENT_DEFAULT_REWARD_MONEY_COPPER", "1200")),
            addon_log_path=os.getenv(
                "WM_ADDON_LOG_PATH",
                r"D:\WOW\Azerothcore_WoTLK_Repack\logs\WMOps.log",
            ),
            addon_log_batch_size=int(os.getenv("WM_ADDON_LOG_BATCH_SIZE", "200")),
            addon_channel_name=os.getenv("WM_ADDON_CHANNEL_NAME", "WMBridgePrivate"),
            addon_prefix=os.getenv("WM_ADDON_PREFIX", "WMBRIDGE"),
            combat_log_path=os.getenv(
                "WM_COMBAT_LOG_PATH",
                r"D:\WOW\world of warcraft 3.3.5a hd\Logs\WoWCombatLog.txt",
            ),
            combat_log_batch_size=int(os.getenv("WM_COMBAT_LOG_BATCH_SIZE", "200")),
            combat_log_player_name=(
                os.getenv("WM_COMBAT_LOG_PLAYER_NAME")
                if os.getenv("WM_COMBAT_LOG_PLAYER_NAME") not in (None, "")
                else None
            ),
        )
