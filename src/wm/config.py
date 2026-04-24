from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _default_bootstrap_path(*parts: str) -> str:
    return str(_repo_root().joinpath(".wm-bootstrap", *parts))


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
    event_default_reward_money_copper: int = 0
    reactive_auto_bounty_enabled: bool = False
    reactive_auto_bounty_max_event_age_seconds: int = 3600
    reactive_auto_bounty_single_open_per_player: bool = True
    random_enchant_on_kill_enabled: bool = False
    random_enchant_on_kill_chance_pct: float = 2.5
    random_enchant_preserve_existing_chance_pct: float = 15.0
    random_enchant_selector: str = "random_equipped"
    random_enchant_max_enchants: int = 3
    random_enchant_consumable_item_entry: int = 910007
    random_enchant_consumable_count: int = 1
    addon_log_path: str = _default_bootstrap_path("run", "logs", "WMOps.log")
    addon_log_batch_size: int = 200
    addon_channel_name: str = "WMBridgePrivate"
    addon_prefix: str = "WMBRIDGE"
    native_bridge_batch_size: int = 200
    native_bridge_action_wait_seconds: float = 5.0
    native_bridge_action_poll_seconds: float = 0.25
    native_bridge_gossip_session_timeout_seconds: int = 45
    quest_grant_transport: str = "auto"
    wm_bridge_config_path: str = _default_bootstrap_path("run", "configs", "modules", "mod_wm_bridge.conf")
    wm_prototypes_config_path: str = _default_bootstrap_path("run", "configs", "modules", "mod_wm_prototypes.conf")
    wm_spells_config_path: str = _default_bootstrap_path("run", "configs", "modules", "mod_wm_spells.conf")
    control_root: str = str(_repo_root().joinpath("control"))
    control_proposal_state_path: str = _default_bootstrap_path("state", "control-proposals")
    combat_log_path: str = _default_bootstrap_path("run", "logs", "WoWCombatLog.txt")
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
            event_default_reward_money_copper=int(os.getenv("WM_EVENT_DEFAULT_REWARD_MONEY_COPPER", "0")),
            reactive_auto_bounty_enabled=os.getenv("WM_REACTIVE_AUTO_BOUNTY_ENABLED", "0").strip().lower()
            in {"1", "true", "yes", "on"},
            reactive_auto_bounty_max_event_age_seconds=int(
                os.getenv("WM_REACTIVE_AUTO_BOUNTY_MAX_EVENT_AGE_SECONDS", "3600")
            ),
            reactive_auto_bounty_single_open_per_player=os.getenv(
                "WM_REACTIVE_AUTO_BOUNTY_SINGLE_OPEN_PER_PLAYER",
                "1",
            ).strip().lower()
            in {"1", "true", "yes", "on"},
            random_enchant_on_kill_enabled=os.getenv("WM_RANDOM_ENCHANT_ON_KILL_ENABLED", "0").strip().lower()
            in {"1", "true", "yes", "on"},
            random_enchant_on_kill_chance_pct=float(os.getenv("WM_RANDOM_ENCHANT_ON_KILL_CHANCE_PCT", "2.5")),
            random_enchant_preserve_existing_chance_pct=float(
                os.getenv("WM_RANDOM_ENCHANT_PRESERVE_EXISTING_CHANCE_PCT", "15.0")
            ),
            random_enchant_selector=os.getenv("WM_RANDOM_ENCHANT_SELECTOR", "random_equipped"),
            random_enchant_max_enchants=int(os.getenv("WM_RANDOM_ENCHANT_MAX_ENCHANTS", "3")),
            random_enchant_consumable_item_entry=int(
                os.getenv("WM_RANDOM_ENCHANT_CONSUMABLE_ITEM_ENTRY", "910007")
            ),
            random_enchant_consumable_count=int(os.getenv("WM_RANDOM_ENCHANT_CONSUMABLE_COUNT", "1")),
            addon_log_path=os.getenv(
                "WM_ADDON_LOG_PATH",
                _default_bootstrap_path("run", "logs", "WMOps.log"),
            ),
            addon_log_batch_size=int(os.getenv("WM_ADDON_LOG_BATCH_SIZE", "200")),
            addon_channel_name=os.getenv("WM_ADDON_CHANNEL_NAME", "WMBridgePrivate"),
            addon_prefix=os.getenv("WM_ADDON_PREFIX", "WMBRIDGE"),
            native_bridge_batch_size=int(os.getenv("WM_NATIVE_BRIDGE_BATCH_SIZE", "200")),
            native_bridge_action_wait_seconds=float(os.getenv("WM_NATIVE_BRIDGE_ACTION_WAIT_SECONDS", "5.0")),
            native_bridge_action_poll_seconds=float(os.getenv("WM_NATIVE_BRIDGE_ACTION_POLL_SECONDS", "0.25")),
            native_bridge_gossip_session_timeout_seconds=int(os.getenv("WM_NATIVE_BRIDGE_GOSSIP_SESSION_TIMEOUT_SECONDS", "45")),
            quest_grant_transport=os.getenv("WM_QUEST_GRANT_TRANSPORT", "auto"),
            wm_bridge_config_path=os.getenv(
                "WM_BRIDGE_CONFIG_PATH",
                _default_bootstrap_path("run", "configs", "modules", "mod_wm_bridge.conf"),
            ),
            wm_prototypes_config_path=os.getenv(
                "WM_PROTOTYPES_CONFIG_PATH",
                _default_bootstrap_path("run", "configs", "modules", "mod_wm_prototypes.conf"),
            ),
            wm_spells_config_path=os.getenv(
                "WM_SPELLS_CONFIG_PATH",
                _default_bootstrap_path("run", "configs", "modules", "mod_wm_spells.conf"),
            ),
            control_root=os.getenv("WM_CONTROL_ROOT", str(_repo_root().joinpath("control"))),
            control_proposal_state_path=os.getenv(
                "WM_CONTROL_PROPOSAL_STATE_PATH",
                _default_bootstrap_path("state", "control-proposals"),
            ),
            combat_log_path=os.getenv(
                "WM_COMBAT_LOG_PATH",
                _default_bootstrap_path("run", "logs", "WoWCombatLog.txt"),
            ),
            combat_log_batch_size=int(os.getenv("WM_COMBAT_LOG_BATCH_SIZE", "200")),
            combat_log_player_name=(
                os.getenv("WM_COMBAT_LOG_PLAYER_NAME")
                if os.getenv("WM_COMBAT_LOG_PLAYER_NAME") not in (None, "")
                else None
            ),
        )
