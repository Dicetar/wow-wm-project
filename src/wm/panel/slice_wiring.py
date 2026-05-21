"""Live MySQL-backed wiring for the panel's slice approval gate.

Mirrors the thin-shell + testable-parse split used in
`wm.cli.bridge_event_pump`: the SQL-issuing shells are not unit-tested
(they need a live DB), but the row-parsing logic is pure and covered.

Discovery is the *sanctioned* path: the active WM character is whoever
most recently received the marker aura (spell 946500), observed via the
`applied` event on `wm_bridge_event`. No peeking at acore_characters or
character_queststatus (see the slice handoff "Mistakes to not repeat").
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


MARKER_SPELL_ID = 946500


@dataclass(slots=True)
class SliceDbConfig:
    host: str = "127.0.0.1"
    port: int = 33307
    user: str = "acore"
    password: str = "acore"
    world_db: str = "acore_world"


def discover_guid_from_rows(rows: list[dict[str, str]]) -> int | None:
    """Return the PlayerGUID of the most recent marker-applied row.

    Rows are expected ordered most-recent-first (BridgeEventID DESC). The
    first row with a parseable PlayerGUID wins; unparseable rows are skipped.
    """
    for rec in rows:
        raw = rec.get("PlayerGUID")
        if raw in (None, "", "NULL"):
            continue
        try:
            return int(raw)
        except (TypeError, ValueError):
            continue
    return None


def make_live_slice_discoverer(*, client: Any, cfg: SliceDbConfig) -> Callable[[], int | None]:
    """Production discoverer: most recent marker-aura bearer from the spine."""
    def discover() -> int | None:
        sql = (
            "SELECT PlayerGUID,BridgeEventID FROM wm_bridge_event "
            "WHERE EventType = 'applied' "
            f"AND PayloadJSON LIKE '%\"spell_id\":{MARKER_SPELL_ID}%' "
            "ORDER BY BridgeEventID DESC LIMIT 25"
        )
        rows = client.query(host=cfg.host, port=cfg.port, user=cfg.user,
                            password=cfg.password, database=cfg.world_db, sql=sql)
        return discover_guid_from_rows(rows)
    return discover


def make_live_slice_factory(*, client: Any, cfg: SliceDbConfig,
                            starter_item_entry: int = 0) -> Callable[..., Any]:
    """Production factory: SliceRuntime wired to the native bus via NativeApplier."""
    def factory(*, character_guid: int) -> Any:
        from wm.cli.slice_demo import SliceRuntime
        from wm.cli.slice_demo_live import wrap_with_live_compilers
        from wm.cli.native_applier import NativeApplier

        rt = SliceRuntime.bootstrap(character_guid=character_guid,
                                    starter_item_entry=starter_item_entry)
        applier = NativeApplier(client=client, host=cfg.host, port=cfg.port,
                                user=cfg.user, password=cfg.password, database=cfg.world_db)
        wrap_with_live_compilers(rt, applier=applier)
        return rt
    return factory


def make_live_slice_pump_factory(*, client: Any, cfg: SliceDbConfig) -> Callable[[Any], Any]:
    """Production pump factory: a BridgeEventPump fed by the live spine fetch."""
    def pump_factory(rt: Any) -> Any:
        from wm.cli.bridge_event_pump import BridgeEventPump, make_mysql_fetch

        character_guid = rt.runner.module.character_guid
        fetch = make_mysql_fetch(client=client, host=cfg.host, port=cfg.port,
                                 user=cfg.user, password=cfg.password,
                                 database=cfg.world_db, character_guid=character_guid)
        return BridgeEventPump(runtime=rt, fetch=fetch)
    return pump_factory
