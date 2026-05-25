from __future__ import annotations

from wm.events.models import ReactionCooldownKey


AUTO_BOUNTY_GRANT_COOLDOWN_RULE_TYPE = "reactive_bounty:auto:grant_cooldown"
AUTO_BOUNTY_GRANT_COOLDOWN_SUBJECT_TYPE = "player"
AUTO_BOUNTY_GRANT_COOLDOWN_SUBJECT_ENTRY = 0


def auto_bounty_grant_cooldown_key(*, player_guid: int) -> ReactionCooldownKey:
    return ReactionCooldownKey(
        rule_type=AUTO_BOUNTY_GRANT_COOLDOWN_RULE_TYPE,
        player_guid=int(player_guid),
        subject_type=AUTO_BOUNTY_GRANT_COOLDOWN_SUBJECT_TYPE,
        subject_entry=AUTO_BOUNTY_GRANT_COOLDOWN_SUBJECT_ENTRY,
    )

