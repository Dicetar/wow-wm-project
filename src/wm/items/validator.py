from __future__ import annotations

from wm.items.models import ManagedItemDraft, ValidationIssue, ValidationResult


def validate_managed_item_draft(draft: ManagedItemDraft) -> ValidationResult:
    issues: list[ValidationIssue] = []

    if draft.item_entry <= 0:
        issues.append(ValidationIssue(path="item_entry", message="Item entry must be a positive integer."))
    if draft.base_item_entry <= 0:
        issues.append(ValidationIssue(path="base_item_entry", message="Base item entry must be a positive integer."))
    if draft.item_entry == draft.base_item_entry:
        issues.append(
            ValidationIssue(
                path="item_entry",
                message="Managed item slot must differ from the base item entry being cloned.",
            )
        )

    name = draft.name.strip()
    if not name:
        issues.append(ValidationIssue(path="name", message="Item name must not be empty."))
    elif len(name) > 120:
        issues.append(ValidationIssue(path="name", message="Item name is too long for item_template.name."))

    if draft.display_id is not None and draft.display_id <= 0:
        issues.append(ValidationIssue(path="display_id", message="display_id must be > 0 when provided."))
    if draft.item_level is not None and draft.item_level < 1:
        issues.append(ValidationIssue(path="item_level", message="item_level must be >= 1 when provided."))
    if draft.required_level is not None and draft.required_level < 0:
        issues.append(ValidationIssue(path="required_level", message="required_level must be >= 0 when provided."))
    if draft.quality is not None and draft.quality not in {0, 1, 2, 3, 4, 5, 6, 7}:
        issues.append(ValidationIssue(path="quality", message="quality must be between 0 and 7."))
    if draft.stackable is not None and draft.stackable == 0:
        issues.append(ValidationIssue(path="stackable", message="stackable should be >= 1 or omitted."))
    if draft.max_count is not None and draft.max_count < -1:
        issues.append(ValidationIssue(path="max_count", message="max_count must be >= -1 when provided."))
    if draft.buy_price is not None and draft.buy_price < 0:
        issues.append(ValidationIssue(path="buy_price", message="buy_price must be >= 0 when provided."))
    if draft.sell_price is not None and draft.sell_price < 0:
        issues.append(ValidationIssue(path="sell_price", message="sell_price must be >= 0 when provided."))

    if len(draft.stats) > 10:
        issues.append(ValidationIssue(path="stats", message="A WoW 3.3.5 item supports at most 10 stat lines."))
    for index, stat in enumerate(draft.stats, start=1):
        if stat.stat_type <= 0:
            issues.append(
                ValidationIssue(path=f"stats[{index}].stat_type", message="stat_type must be a positive integer.")
            )
        if stat.stat_value == 0:
            issues.append(
                ValidationIssue(path=f"stats[{index}].stat_value", message="stat_value should not be zero.")
            )

    if len(draft.spells) > 5:
        issues.append(ValidationIssue(path="spells", message="A WoW 3.3.5 item supports at most 5 spell slots."))
    for index, spell in enumerate(draft.spells, start=1):
        if spell.spell_id <= 0:
            issues.append(
                ValidationIssue(path=f"spells[{index}].spell_id", message="spell_id must be a positive integer.")
            )
        if spell.trigger < 0:
            issues.append(
                ValidationIssue(path=f"spells[{index}].trigger", message="trigger must be >= 0.")
            )

    if draft.clear_stats and draft.stats:
        issues.append(
            ValidationIssue(
                path="stats",
                message="clear_stats is unnecessary when explicit stats are already provided.",
                severity="warning",
            )
        )
    if draft.clear_spells and draft.spells:
        issues.append(
            ValidationIssue(
                path="spells",
                message="clear_spells is unnecessary when explicit spells are already provided.",
                severity="warning",
            )
        )

    return ValidationResult(issues=issues)
