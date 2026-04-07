from __future__ import annotations

from wm.spells.models import ManagedSpellDraft, ValidationIssue, ValidationResult

ALLOWED_SLOT_KINDS = {"visible_spell_slot", "passive_slot", "helper_slot", "item_trigger_slot"}


def validate_managed_spell_draft(draft: ManagedSpellDraft) -> ValidationResult:
    issues: list[ValidationIssue] = []

    if draft.spell_entry <= 0:
        issues.append(ValidationIssue(path="spell_entry", message="spell_entry must be a positive integer."))
    if draft.slot_kind not in ALLOWED_SLOT_KINDS:
        issues.append(
            ValidationIssue(
                path="slot_kind",
                message=f"slot_kind must be one of: {', '.join(sorted(ALLOWED_SLOT_KINDS))}.",
            )
        )
    name = draft.name.strip()
    if not name:
        issues.append(ValidationIssue(path="name", message="name must not be empty."))
    elif len(name) > 120:
        issues.append(ValidationIssue(path="name", message="name is too long for routine operator use."))

    if draft.slot_kind == "visible_spell_slot" and draft.base_visible_spell_id in (None, 0):
        issues.append(
            ValidationIssue(
                path="base_visible_spell_id",
                message="visible spell slots require a base_visible_spell_id.",
            )
        )
    if draft.slot_kind == "item_trigger_slot" and draft.trigger_item_entry in (None, 0):
        issues.append(
            ValidationIssue(
                path="trigger_item_entry",
                message="item_trigger_slot requires trigger_item_entry.",
            )
        )
    if draft.helper_spell_id is not None and draft.helper_spell_id <= 0:
        issues.append(ValidationIssue(path="helper_spell_id", message="helper_spell_id must be > 0 when provided."))

    for index, rule in enumerate(draft.proc_rules, start=1):
        if rule.spell_id <= 0:
            issues.append(
                ValidationIssue(path=f"proc_rules[{index}].spell_id", message="spell_id must be a positive integer.")
            )
        if rule.procs_per_minute < 0:
            issues.append(
                ValidationIssue(
                    path=f"proc_rules[{index}].procs_per_minute",
                    message="procs_per_minute must be >= 0.",
                )
            )
        if rule.chance < 0:
            issues.append(
                ValidationIssue(path=f"proc_rules[{index}].chance", message="chance must be >= 0." )
            )

    for index, link in enumerate(draft.linked_spells, start=1):
        if link.trigger_spell_id <= 0:
            issues.append(
                ValidationIssue(
                    path=f"linked_spells[{index}].trigger_spell_id",
                    message="trigger_spell_id must be a positive integer.",
                )
            )
        if link.effect_spell_id <= 0:
            issues.append(
                ValidationIssue(
                    path=f"linked_spells[{index}].effect_spell_id",
                    message="effect_spell_id must be a positive integer.",
                )
            )

    return ValidationResult(issues=issues)
