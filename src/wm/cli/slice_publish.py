"""Publish-on-approval for the LIVE slice: allocate -> publish -> reload -> grant.

Composes the existing reserved-slot allocator, quest publisher, SOAP runtime
client, and native applier. Any failure raises SlicePublishError so the
ApprovalGate parks the proposal (no partial state -- the reserved slot only
flips to active inside a successful QuestPublisher.publish)."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any

from wm.quests.publish import bounty_draft_from_dict


class SlicePublishError(Exception):
    pass


@dataclass(slots=True)
class SlicePublishService:
    allocator: Any
    publisher: Any
    soap: Any
    applier: Any

    def publish_and_grant(self, *, draft_dict: dict[str, Any],
                          character_guid: int, beat_id: str) -> dict[str, Any]:
        slot = self.allocator.allocate_next_free_slot(
            entity_type="quest", character_guid=character_guid,
            notes=[f"slice:{beat_id}"])
        if slot is None:
            raise SlicePublishError("no free reserved quest slot available")
        quest_id = int(slot.reserved_id)

        merged = dict(draft_dict)
        merged["quest_id"] = quest_id
        draft = bounty_draft_from_dict(merged)

        result = self.publisher.publish(draft=draft, mode="apply")
        if not getattr(result, "applied", False):
            raise SlicePublishError(
                f"publish not applied for quest {quest_id}: "
                f"{getattr(result, 'preflight', {})}")

        reload_result = self.soap.execute_command(".reload all quest")
        reload_ok = bool(getattr(reload_result, "ok", True))

        idem = f"slice.quest_grant:{beat_id}:{quest_id}:{character_guid}"
        grant = self.applier.insert_quest_add(
            character_guid=character_guid, quest_id=quest_id, idempotency_key=idem)
        if not grant.get("ok", False):
            raise SlicePublishError(
                f"quest {quest_id} published but grant failed; "
                "worldserver restart may be required")

        return {"ok": True, "quest_id": quest_id,
                "reload_ok": reload_ok, "grant": grant}
