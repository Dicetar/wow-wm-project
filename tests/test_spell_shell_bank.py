from wm.spells.shell_bank import default_shell_bank_path
from wm.spells.shell_bank import build_patch_plan
from wm.spells.shell_bank import generate_patch_rows
from wm.spells.shell_bank import load_spell_shell_bank


def test_default_spell_shell_bank_loads() -> None:
    bank = load_spell_shell_bank()

    assert bank.schema_version == "wm.spell_shell_bank.v2"
    assert bank.client_patch_required is True
    assert bank.family_by_id("summon_pet_compat") is not None
    assert bank.family_by_id("passive_aura") is not None
    assert bank.patch["workspace"] == "client_patches/wm_spell_shell_bank"
    assert bank.patch["slots_per_family"] == "100"
    assert bank.total_family_slots == 504


def test_summon_pet_shell_range_resolves_spell_id() -> None:
    bank = load_spell_shell_bank(default_shell_bank_path())

    family = bank.family_for_spell(940000)

    assert family is not None
    assert family.family_id == "summon_pet_compat"
    assert family.supports_true_pet is True
    assert family.supports_multi_pet is False
    assert family.slot_count == 2
    assert family.slot_range_end == 940001
    assert family.patch_seed_template == "wm_summon_pet"


def test_bonebound_shell_definitions_are_present() -> None:
    bank = load_spell_shell_bank(default_shell_bank_path())

    summon_shell = bank.shell_by_key("bonebound_servant_v1")
    twin_shell = bank.shell_by_key("bonebound_twins_v1")
    pet_active_shell = bank.shell_by_spell_id(945000)

    assert summon_shell is not None
    assert summon_shell.spell_id == 940000
    assert summon_shell.behavior_kind == "summon_bonebound_servant_v1"
    assert twin_shell is not None
    assert twin_shell.spell_id == 940001
    assert twin_shell.behavior_kind == "summon_bonebound_alpha_v3"
    assert twin_shell.client_presentation is not None
    assert twin_shell.client_presentation["cast_time_index"] == 14
    assert twin_shell.client_presentation["mana_cost"] == 180
    assert twin_shell.client_presentation["spell_visual_id_2"] == 4054
    assert twin_shell.client_presentation["spellbook_seed_spell_id"] == 697
    assert pet_active_shell is not None
    assert pet_active_shell.family_id == "pet_active_compat"
    assert pet_active_shell.spell_id == 945000


def test_patch_rows_expand_compatibility_and_generic_ranges_and_overlay_named_shells() -> None:
    rows = generate_patch_rows(default_shell_bank_path())

    assert len(rows) == 504
    assert rows[0].spell_id == 940000
    assert rows[-1].spell_id == 946899

    summon_shell = next(row for row in rows if row.spell_id == 940000)
    generic_projectile_slot = next(row for row in rows if row.spell_id == 946000)
    pet_active_shell = next(row for row in rows if row.spell_id == 945000)

    assert summon_shell.is_named_override is True
    assert summon_shell.shell_key == "bonebound_servant_v1"
    assert summon_shell.behavior_kind == "summon_bonebound_servant_v1"
    assert generic_projectile_slot.is_named_override is False
    assert generic_projectile_slot.shell_key == "unit_target_projectile_0001"
    assert generic_projectile_slot.seed_template == "wm_unit_target_projectile"
    twin_shell = next(row for row in rows if row.spell_id == 940001)
    assert twin_shell.is_named_override is True
    assert twin_shell.shell_key == "bonebound_twins_v1"
    assert twin_shell.behavior_kind == "summon_bonebound_alpha_v3"
    assert twin_shell.client_presentation["spellbook_ability_id"] == 1940001
    assert twin_shell.client_presentation["spell_visual_id_2"] == 4054
    assert pet_active_shell.is_named_override is True
    assert pet_active_shell.shell_key == "bonebound_servant_slash_v1"
    assert all(row.spell_id != 946100 for row in rows)
    assert all(row.spell_id != 946300 for row in rows)
    assert all(row.spell_id != 946500 for row in rows)
    assert all(row.spell_id != 946700 for row in rows)
    assert all(row.spell_id != 946900 for row in rows)


def test_patch_plan_reports_range_driven_summary() -> None:
    plan = build_patch_plan(default_shell_bank_path())

    assert plan["schema_version"] == "wm.spell_shell_patch_plan.v1"
    assert plan["generation_mode"] == "range_driven"
    assert plan["family_count"] == 8
    assert plan["generic_family_count"] == 5
    assert plan["slots_per_family"] == 100
    assert plan["reserve_gap_slots"] == 100
    assert plan["total_rows"] == 504
    assert plan["named_override_count"] == 4
