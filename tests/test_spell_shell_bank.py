from wm.spells.shell_bank import default_shell_bank_path
from wm.spells.shell_bank import build_patch_plan
from wm.spells.shell_bank import generate_patch_rows
from wm.spells.shell_bank import load_spell_shell_bank


def test_default_spell_shell_bank_loads() -> None:
    bank = load_spell_shell_bank()

    assert bank.schema_version == "wm.spell_shell_bank.v1"
    assert bank.client_patch_required is True
    assert bank.family_by_id("summon_pet") is not None
    assert bank.family_by_id("pet_active") is not None
    assert bank.patch["workspace"] == "client_patches/wm_spell_shell_bank"
    assert bank.patch["slots_per_family"] == "1000"
    assert bank.total_family_slots == 6000


def test_summon_pet_shell_range_resolves_spell_id() -> None:
    bank = load_spell_shell_bank(default_shell_bank_path())

    family = bank.family_for_spell(940000)

    assert family is not None
    assert family.family_id == "summon_pet"
    assert family.supports_true_pet is True
    assert family.supports_multi_pet is False
    assert family.slot_count == 1000
    assert family.slot_range_end == 940999
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
    assert pet_active_shell is not None
    assert pet_active_shell.family_id == "pet_active"
    assert pet_active_shell.spell_id == 945000


def test_patch_rows_expand_all_family_ranges_and_overlay_named_shells() -> None:
    rows = generate_patch_rows(default_shell_bank_path())

    assert len(rows) == 6000
    assert rows[0].spell_id == 940000
    assert rows[-1].spell_id == 945999

    summon_shell = next(row for row in rows if row.spell_id == 940000)
    default_summon_slot = next(row for row in rows if row.spell_id == 940002)
    pet_active_shell = next(row for row in rows if row.spell_id == 945000)

    assert summon_shell.is_named_override is True
    assert summon_shell.shell_key == "bonebound_servant_v1"
    assert summon_shell.behavior_kind == "summon_bonebound_servant_v1"
    assert default_summon_slot.is_named_override is False
    assert default_summon_slot.shell_key == "summon_pet_0003"
    assert default_summon_slot.seed_template == "wm_summon_pet"
    twin_shell = next(row for row in rows if row.spell_id == 940001)
    assert twin_shell.is_named_override is True
    assert twin_shell.shell_key == "bonebound_twins_v1"
    assert twin_shell.behavior_kind == "summon_bonebound_alpha_v3"
    assert pet_active_shell.is_named_override is True
    assert pet_active_shell.shell_key == "bonebound_servant_slash_v1"


def test_patch_plan_reports_range_driven_summary() -> None:
    plan = build_patch_plan(default_shell_bank_path())

    assert plan["schema_version"] == "wm.spell_shell_patch_plan.v1"
    assert plan["generation_mode"] == "range_driven"
    assert plan["family_count"] == 6
    assert plan["slots_per_family"] == 1000
    assert plan["total_rows"] == 6000
    assert plan["named_override_count"] == 3
