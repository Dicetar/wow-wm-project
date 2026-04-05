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
        )
