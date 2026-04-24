from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
from typing import Any

from wm.config import Settings
from wm.db.mysql_cli import MysqlCliClient
from wm.events.models import WMEvent
from wm.events.store import EventStore
from wm.sources.native_bridge.actions import NativeBridgeActionClient
from wm.sources.native_bridge.actions import NativeBridgeActionRequest


DEFAULT_RANDOM_ENCHANT_KILL_CHANCE_PCT = 2.5
DEFAULT_PRESERVE_EXISTING_CHANCE_PCT = 15.0
DEFAULT_RANDOM_ENCHANT_CONSUMABLE_ITEM_ENTRY = 910007
DEFAULT_RANDOM_ENCHANT_CONSUMABLE_COUNT = 1


@dataclass(frozen=True, slots=True)
class RandomEnchantKillRoll:
    event_id: int
    player_guid: int
    source_event_key: str
    subject_entry: int | None
    subject_name: str | None
    roll_pct: float
    chance_pct: float
    selected: bool
    mode: str
    idempotency_key: str | None = None
    request_id: int | None = None
    request_status: str | None = None
    item_entry: int | None = None
    count: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "player_guid": self.player_guid,
            "source_event_key": self.source_event_key,
            "subject_entry": self.subject_entry,
            "subject_name": self.subject_name,
            "roll_pct": round(self.roll_pct, 4),
            "chance_pct": self.chance_pct,
            "selected": self.selected,
            "mode": self.mode,
            "idempotency_key": self.idempotency_key,
            "request_id": self.request_id,
            "request_status": self.request_status,
            "item_entry": self.item_entry,
            "count": self.count,
        }


class RandomEnchantKillRoller:
    def __init__(
        self,
        *,
        settings: Settings,
        event_store: EventStore,
        native_actions: NativeBridgeActionClient,
        rng_salt: str = "wm.random_enchant.kill.v1",
    ) -> None:
        self.settings = settings
        self.event_store = event_store
        self.native_actions = native_actions
        self.rng_salt = rng_salt

    def process_recent_kills(
        self,
        *,
        player_guid: int,
        chance_pct: float = DEFAULT_RANDOM_ENCHANT_KILL_CHANCE_PCT,
        preserve_existing_chance_pct: float = DEFAULT_PRESERVE_EXISTING_CHANCE_PCT,
        selector: str = "random_equipped",
        max_enchants: int = 3,
        item_entry: int = DEFAULT_RANDOM_ENCHANT_CONSUMABLE_ITEM_ENTRY,
        count: int = DEFAULT_RANDOM_ENCHANT_CONSUMABLE_COUNT,
        limit: int = 50,
        mode: str = "dry-run",
    ) -> list[RandomEnchantKillRoll]:
        if mode not in {"dry-run", "apply"}:
            raise ValueError("mode must be dry-run or apply")
        chance_pct = max(0.0, min(100.0, float(chance_pct)))
        preserve_existing_chance_pct = max(0.0, min(100.0, float(preserve_existing_chance_pct)))
        max_enchants = max(1, min(3, int(max_enchants)))

        recent_events = self.event_store.list_recent_events(
            event_class="observed",
            player_guid=int(player_guid),
            limit=max(1, int(limit)),
            newest_first=True,
        )
        kill_events = [
            event
            for event in reversed(recent_events)
            if event.event_type == "kill" and event.event_id is not None and event.player_guid is not None
        ]
        return self.process_events(
            events=kill_events,
            player_guid=player_guid,
            chance_pct=chance_pct,
            preserve_existing_chance_pct=preserve_existing_chance_pct,
            selector=selector,
            max_enchants=max_enchants,
            item_entry=item_entry,
            count=count,
            mode=mode,
        )

    def process_events(
        self,
        *,
        events: list[WMEvent],
        player_guid: int,
        chance_pct: float = DEFAULT_RANDOM_ENCHANT_KILL_CHANCE_PCT,
        preserve_existing_chance_pct: float = DEFAULT_PRESERVE_EXISTING_CHANCE_PCT,
        selector: str = "random_equipped",
        max_enchants: int = 3,
        item_entry: int = DEFAULT_RANDOM_ENCHANT_CONSUMABLE_ITEM_ENTRY,
        count: int = DEFAULT_RANDOM_ENCHANT_CONSUMABLE_COUNT,
        mode: str = "dry-run",
    ) -> list[RandomEnchantKillRoll]:
        results: list[RandomEnchantKillRoll] = []
        if mode not in {"dry-run", "apply"}:
            raise ValueError("mode must be dry-run or apply")
        chance_pct = max(0.0, min(100.0, float(chance_pct)))
        preserve_existing_chance_pct = max(0.0, min(100.0, float(preserve_existing_chance_pct)))
        max_enchants = max(1, min(3, int(max_enchants)))
        item_entry = int(item_entry)
        count = max(1, int(count))

        kill_events = [
            event
            for event in events
            if event.event_class == "observed"
            and event.event_type == "kill"
            and event.event_id is not None
            and event.player_guid is not None
            and int(event.player_guid) == int(player_guid)
        ]
        for event in kill_events:
            selected, roll_pct = self._roll_event(event=event, chance_pct=chance_pct)
            idempotency_key = f"random_enchant_consumable:on_kill:{int(player_guid)}:{int(event.event_id or 0)}"
            request: NativeBridgeActionRequest | None = None
            if selected and mode == "apply":
                request = self.native_actions.submit(
                    idempotency_key=idempotency_key,
                    player_guid=int(player_guid),
                    action_kind="player_add_item",
                    payload={
                        "item_id": item_entry,
                        "count": count,
                        "soulbound": False,
                        "reason": "random_enchant_consumable_drop",
                        "source_event_id": int(event.event_id or 0),
                        "source_event_key": event.source_event_key,
                        "chance_pct": chance_pct,
                    },
                    created_by="wm.random_enchant",
                    risk_level="medium",
                    expires_seconds=60,
                    max_attempts=3,
                    priority=5,
                )

            results.append(
                RandomEnchantKillRoll(
                    event_id=int(event.event_id or 0),
                    player_guid=int(player_guid),
                    source_event_key=event.source_event_key,
                    subject_entry=event.subject_entry,
                    subject_name=_subject_name(event),
                    roll_pct=roll_pct,
                    chance_pct=chance_pct,
                    selected=selected,
                    mode=mode,
                    idempotency_key=idempotency_key if selected else None,
                    request_id=request.request_id if request is not None else None,
                    request_status=request.status if request is not None else None,
                    item_entry=item_entry if selected else None,
                    count=count if selected else None,
                )
            )
        return results

    def _roll_event(self, *, event: WMEvent, chance_pct: float) -> tuple[bool, float]:
        material = f"{self.rng_salt}:{event.event_id}:{event.source}:{event.source_event_key}"
        digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
        roll_pct = (int(digest[:12], 16) / float(0xFFFFFFFFFFFF)) * 100.0
        return roll_pct < chance_pct, roll_pct


def _subject_name(event: WMEvent) -> str | None:
    for key in ("subject_name", "creature_name", "loot_source_name"):
        value = event.metadata.get(key)
        if value not in (None, ""):
            return str(value)
    payload = event.metadata.get("payload")
    if isinstance(payload, dict):
        value = payload.get("subject_name") or payload.get("creature_name") or payload.get("loot_source_name")
        if value not in (None, ""):
            return str(value)
    return None


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Roll rare random-enchant consumable grants from scoped WM kill events.")
    parser.add_argument("--player-guid", type=int, required=True)
    parser.add_argument("--mode", choices=("dry-run", "apply"), default="dry-run")
    parser.add_argument("--chance-pct", type=float, default=DEFAULT_RANDOM_ENCHANT_KILL_CHANCE_PCT)
    parser.add_argument("--preserve-existing-chance-pct", type=float, default=DEFAULT_PRESERVE_EXISTING_CHANCE_PCT)
    parser.add_argument("--selector", default="random_equipped")
    parser.add_argument("--max-enchants", type=int, default=3)
    parser.add_argument("--item-entry", type=int, default=DEFAULT_RANDOM_ENCHANT_CONSUMABLE_ITEM_ENTRY)
    parser.add_argument("--count", type=int, default=DEFAULT_RANDOM_ENCHANT_CONSUMABLE_COUNT)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    settings = Settings.from_env()
    client = MysqlCliClient()
    roller = RandomEnchantKillRoller(
        settings=settings,
        event_store=EventStore(client=client, settings=settings),
        native_actions=NativeBridgeActionClient(client=client, settings=settings),
    )
    results = roller.process_recent_kills(
        player_guid=int(args.player_guid),
        chance_pct=float(args.chance_pct),
        preserve_existing_chance_pct=float(args.preserve_existing_chance_pct),
        selector=str(args.selector),
        max_enchants=int(args.max_enchants),
        item_entry=int(args.item_entry),
        count=int(args.count),
        limit=int(args.limit),
        mode=str(args.mode),
    )
    selected = [result for result in results if result.selected]
    payload = {
        "ok": True,
        "mode": args.mode,
        "player_guid": int(args.player_guid),
        "processed_kills": len(results),
        "selected": len(selected),
        "chance_pct": float(args.chance_pct),
        "preserve_existing_chance_pct": float(args.preserve_existing_chance_pct),
        "item_entry": int(args.item_entry),
        "count": int(args.count),
        "results": [result.to_dict() for result in results],
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif args.summary:
        print(
            f"ok=true mode={args.mode} player_guid={int(args.player_guid)} "
            f"processed_kills={len(results)} selected={len(selected)} chance_pct={float(args.chance_pct):.2f} "
            f"item_entry={int(args.item_entry)} count={int(args.count)}"
        )
        for result in selected:
            request_text = f" request={result.request_id}:{result.request_status}" if result.request_id is not None else ""
            print(
                f"selected event={result.event_id} roll={result.roll_pct:.4f} "
                f"subject={result.subject_entry or ''} item={result.item_entry} "
                f"idempotency={result.idempotency_key}{request_text}"
            )
    else:
        print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
