from __future__ import annotations

from wm.events.content import DeterministicContentFactory
from wm.events.models import PlannedAction
from wm.events.models import ReactionOpportunity
from wm.events.models import ReactionPlan


class DeterministicReactionPlanner:
    def __init__(self, *, content_factory: DeterministicContentFactory | None = None) -> None:
        self.content_factory = content_factory

    def plan(self, opportunity: ReactionOpportunity) -> ReactionPlan:
        actions: list[PlannedAction] = []
        generated_metadata: dict[str, object] = {}

        if self.content_factory is not None:
            generated_actions, generated_metadata = self.content_factory.build_actions(opportunity)
            actions.extend(generated_actions)

        quest_draft = opportunity.metadata.get("quest_draft")
        if isinstance(quest_draft, dict):
            actions.append(
                PlannedAction(
                    kind="quest_publish",
                    payload=quest_draft,
                    description="Publish a quest draft through the canonical quest publisher.",
                )
            )

        item_draft = opportunity.metadata.get("item_draft")
        if isinstance(item_draft, dict):
            actions.append(
                PlannedAction(
                    kind="item_publish",
                    payload=item_draft,
                    description="Publish a managed item reward through the item slot pipeline.",
                )
            )

        spell_draft = opportunity.metadata.get("spell_draft")
        if isinstance(spell_draft, dict):
            actions.append(
                PlannedAction(
                    kind="spell_publish",
                    payload=spell_draft,
                    description="Publish a managed spell or passive through the spell slot pipeline.",
                )
            )

        announcement_text = opportunity.metadata.get("announcement_text")
        if isinstance(announcement_text, str) and announcement_text.strip():
            actions.append(
                PlannedAction(
                    kind="announcement",
                    payload={"text": announcement_text.strip()},
                    description="Emit or queue a WM announcement.",
                )
            )

        if not actions:
            actions.append(
                PlannedAction(
                    kind="noop",
                    payload={"reason": "No deterministic artifact payloads were attached to the opportunity."},
                    description="No-op placeholder plan until content payloads are attached.",
                )
            )

        return ReactionPlan(
            plan_key=opportunity.reaction_key,
            opportunity_type=opportunity.opportunity_type,
            rule_type=opportunity.rule_type,
            player_guid=opportunity.player_guid,
            subject=opportunity.subject,
            actions=actions,
            metadata={
                "source_event_key": opportunity.source_event_key,
                "opportunity_metadata": opportunity.metadata,
                "generated_metadata": generated_metadata,
            },
            cooldown_key=opportunity.cooldown_key,
            cooldown_seconds=opportunity.cooldown_seconds,
        )
