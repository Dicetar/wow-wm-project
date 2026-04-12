from wm.spells.shell_bank import default_shell_bank_path
from wm.spells.shell_bank import load_spell_shell_bank


def test_default_spell_shell_bank_loads() -> None:
    bank = load_spell_shell_bank()

    assert bank.schema_version == "wm.spell_shell_bank.v1"
    assert bank.client_patch_required is True
    assert bank.family_by_id("summon_pet") is not None
    assert bank.family_by_id("pet_active") is not None
    assert bank.patch["workspace"] == "client_patches/wm_spell_shell_bank"


def test_summon_pet_shell_range_resolves_spell_id() -> None:
    bank = load_spell_shell_bank(default_shell_bank_path())

    family = bank.family_for_spell(940000)

    assert family is not None
    assert family.family_id == "summon_pet"
    assert family.supports_true_pet is True
    assert family.supports_multi_pet is False


def test_bonebound_shell_definitions_are_present() -> None:
    bank = load_spell_shell_bank(default_shell_bank_path())

    summon_shell = bank.shell_by_key("bonebound_servant_v1")
    pet_active_shell = bank.shell_by_spell_id(940500)

    assert summon_shell is not None
    assert summon_shell.spell_id == 940000
    assert summon_shell.behavior_kind == "summon_bonebound_servant_v1"
    assert pet_active_shell is not None
    assert pet_active_shell.family_id == "pet_active"
