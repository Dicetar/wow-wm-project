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
    assert bank.family_by_id("unit_target_friendly") is not None
    assert bank.family_by_id("target_centered_aoe") is not None
    assert bank.family_by_id("caster_centered_aoe") is not None
    assert bank.family_by_id("random_targets") is not None
    assert bank.family_by_id("frontal_cone") is not None
    assert bank.patch["workspace"] == "client_patches/wm_spell_shell_bank"
    assert bank.patch["slots_per_family"] == "100"
    assert bank.patch["reserve_gap_slots"] == "0"
    assert bank.total_family_slots == 1004


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
    stasis_shell = bank.shell_by_key("bonebound_echo_stasis_v1")
    echo_mind_blast_shell = bank.shell_by_key("echo_restorer_mind_blast_x3_v1")
    lanathel_shell = bank.shell_by_key("lanathel_blood_queen_stance_v1")
    watcher_beacon_shell = bank.shell_by_key("wm_watcher_beacon_v1")
    broug_vulnerable_shell = bank.shell_by_key("broug_vulnerable_v1")
    broug_deflected_shell = bank.shell_by_key("broug_deflected_v1")
    broug_deflect_shell = bank.shell_by_key("broug_deflect_v1")
    broug_counter_stance_shell = bank.shell_by_key("broug_deflect_counter_stance_v1")
    energy_surge_shell = bank.shell_by_key("energy_surge_potion_v1")
    broug_cloud_step_shell = bank.shell_by_key("broug_cloud_step_v1")
    broug_marked_meridian_shell = bank.shell_by_key("broug_marked_meridian_v1")
    broug_killing_intent_shell = bank.shell_by_key("broug_killing_intent_v1")
    broug_suppressed_shell = bank.shell_by_key("broug_suppressed_v1")
    broug_qi_reversal_shell = bank.shell_by_key("broug_qi_reversal_v1")
    broug_purged_state_shell = bank.shell_by_key("broug_purged_state_v1")
    broug_parry_shell = bank.shell_by_key("broug_universal_parry_v1")
    broug_marksman_shell = bank.shell_by_key("broug_skirmisher_shot_v1")
    broug_retaliation_shell = bank.shell_by_key("broug_auto_retaliation_v1")
    broug_silent_meridian_shell = bank.shell_by_key("broug_silent_meridian_v1")
    broug_domain_shell = bank.shell_by_key("broug_killing_intent_domain_v1")
    broug_predator_shell = bank.shell_by_key("broug_predators_strike_v1")
    broug_vitality_shell = bank.shell_by_key("broug_vitality_drain_v1")
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
    assert stasis_shell is not None
    assert stasis_shell.spell_id == 946600
    assert stasis_shell.family_id == "self_aura"
    assert stasis_shell.behavior_kind == "bonebound_echo_stasis_v1"
    assert stasis_shell.client_presentation is not None
    assert stasis_shell.client_presentation["cast_time_index"] == 6
    assert stasis_shell.client_presentation["reagent_1_item_id"] == 6265
    assert stasis_shell.client_presentation["reagent_1_count"] == 1
    assert echo_mind_blast_shell is not None
    assert echo_mind_blast_shell.spell_id == 946099
    assert echo_mind_blast_shell.family_id == "unit_target_projectile"
    assert echo_mind_blast_shell.patch_seed_template == "wm_mind_blast"
    assert echo_mind_blast_shell.client_presentation is not None
    assert echo_mind_blast_shell.client_presentation["range_index"] == 157
    assert lanathel_shell is not None
    assert lanathel_shell.spell_id == 946601
    assert lanathel_shell.family_id == "self_aura"
    assert lanathel_shell.behavior_kind == "lanathel_blood_queen_stance_v1"
    assert lanathel_shell.client_presentation is not None
    assert lanathel_shell.client_presentation["spell_icon_id"] == 4165
    assert lanathel_shell.client_presentation["spellbook_ability_id"] == 1946601
    assert watcher_beacon_shell is not None
    assert watcher_beacon_shell.spell_id == 946602
    assert watcher_beacon_shell.family_id == "self_aura"
    assert watcher_beacon_shell.patch_seed_template == "wm_watcher_marker"
    assert watcher_beacon_shell.behavior_kind == "watcher_marker_beacon_v1"
    assert watcher_beacon_shell.client_presentation is not None
    assert watcher_beacon_shell.client_presentation["dispel_type"] == 0
    assert watcher_beacon_shell.client_presentation["duration_index"] == 21
    assert watcher_beacon_shell.client_presentation["effect_apply_aura_name_1"] == 4
    assert watcher_beacon_shell.client_presentation["spell_icon_id"] == 135
    assert broug_vulnerable_shell is not None
    assert broug_vulnerable_shell.spell_id == 946200
    assert broug_vulnerable_shell.family_id == "unit_target_effect"
    assert broug_vulnerable_shell.behavior_kind == "broug_vulnerable_v1"
    assert broug_vulnerable_shell.client_presentation is not None
    assert broug_vulnerable_shell.client_presentation["dispel_type"] == 0
    assert broug_vulnerable_shell.client_presentation["duration_index"] == 3
    assert broug_vulnerable_shell.client_presentation["effect_1"] == 6
    assert broug_vulnerable_shell.client_presentation["effect_apply_aura_name_1"] == 4
    assert broug_vulnerable_shell.client_presentation["spell_icon_id"] == 558
    assert broug_deflected_shell is not None
    assert broug_deflected_shell.spell_id == 946201
    assert broug_deflected_shell.family_id == "unit_target_effect"
    assert broug_deflected_shell.behavior_kind == "broug_deflected_v1"
    assert broug_deflected_shell.client_presentation is not None
    assert broug_deflected_shell.client_presentation["dispel_type"] == 0
    assert broug_deflected_shell.client_presentation["duration_index"] == 36
    assert broug_deflected_shell.client_presentation["stack_amount"] == 255
    assert broug_deflected_shell.client_presentation["effect_1"] == 6
    assert broug_deflected_shell.client_presentation["effect_apply_aura_name_1"] == 4
    assert broug_deflected_shell.client_presentation["spell_icon_id"] == 558
    assert broug_deflect_shell is not None
    assert broug_deflect_shell.spell_id == 946603
    assert broug_deflect_shell.family_id == "self_aura"
    assert broug_deflect_shell.behavior_kind == "broug_deflect_v1"
    assert broug_deflect_shell.client_presentation is not None
    assert broug_deflect_shell.client_presentation["power_type"] == 3
    assert broug_deflect_shell.client_presentation["mana_cost"] == 5
    assert broug_deflect_shell.client_presentation["recovery_time"] == 500
    assert broug_deflect_shell.client_presentation["start_recovery_time"] == 0
    assert broug_deflect_shell.client_presentation["dispel_type"] == 0
    assert broug_deflect_shell.client_presentation["duration_index"] == 0
    assert broug_deflect_shell.client_presentation["effect_1"] == 0
    assert broug_deflect_shell.client_presentation["effect_apply_aura_name_1"] == 0
    assert broug_deflect_shell.client_presentation["effect_misc_value_1"] == 0
    assert broug_deflect_shell.client_presentation["spell_icon_id"] == 278
    assert broug_deflect_shell.client_presentation["spellbook_ability_id"] == 1946603
    assert broug_counter_stance_shell is not None
    assert broug_counter_stance_shell.spell_id == 946605
    assert broug_counter_stance_shell.family_id == "self_aura"
    assert broug_counter_stance_shell.behavior_kind == "broug_deflect_counter_stance_v1"
    assert broug_counter_stance_shell.client_presentation is not None
    assert broug_counter_stance_shell.client_presentation["category"] == 47
    assert broug_counter_stance_shell.client_presentation["power_type"] == 3
    assert broug_counter_stance_shell.client_presentation["mana_cost"] == 0
    assert broug_counter_stance_shell.client_presentation["recovery_time"] == 0
    assert broug_counter_stance_shell.client_presentation["category_recovery_time"] == 1000
    assert broug_counter_stance_shell.client_presentation["duration_index"] == 21
    assert broug_counter_stance_shell.client_presentation["effect_1"] == 6
    assert broug_counter_stance_shell.client_presentation["effect_implicit_target_a_1"] == 1
    assert broug_counter_stance_shell.client_presentation["effect_apply_aura_name_1"] == 36
    assert broug_counter_stance_shell.client_presentation["effect_misc_value_1"] == 13
    assert broug_counter_stance_shell.client_presentation["stance_bar_order"] == 1
    assert broug_counter_stance_shell.client_presentation["spell_visual_id_2"] == 0
    assert broug_counter_stance_shell.client_presentation["spell_icon_id"] == 563
    assert broug_counter_stance_shell.client_presentation["active_icon_id"] == 563
    assert broug_counter_stance_shell.client_presentation["spell_family_name"] == 8
    assert broug_counter_stance_shell.client_presentation["damage_class"] == 0
    assert broug_counter_stance_shell.client_presentation["prevention_type"] == 0
    assert broug_counter_stance_shell.client_presentation["spellbook_ability_id"] == 1946605
    assert "Counterstrike Stance" in broug_counter_stance_shell.tooltip
    assert energy_surge_shell is not None
    assert energy_surge_shell.spell_id == 946606
    assert energy_surge_shell.family_id == "self_aura"
    assert energy_surge_shell.behavior_kind == "energy_surge_potion_v1"
    assert energy_surge_shell.client_presentation is not None
    assert energy_surge_shell.client_presentation["spell_icon_id"] == 1299
    assert energy_surge_shell.client_presentation["spell_family_name"] == 0
    assert energy_surge_shell.client_presentation["spell_family_flags_1"] == 0
    assert energy_surge_shell.client_presentation["spell_family_flags_2"] == 0
    assert energy_surge_shell.client_presentation["spell_family_flags_3"] == 0
    assert energy_surge_shell.client_presentation["damage_class"] == 0
    assert energy_surge_shell.client_presentation["prevention_type"] == 0
    assert "10 additional energy" in energy_surge_shell.tooltip
    assert broug_cloud_step_shell is not None
    assert broug_cloud_step_shell.spell_id == 946202
    assert broug_cloud_step_shell.family_id == "unit_target_effect"
    assert broug_cloud_step_shell.behavior_kind == "broug_cloud_step_v1"
    assert broug_cloud_step_shell.client_presentation is not None
    assert broug_cloud_step_shell.client_presentation["power_type"] == 3
    assert broug_cloud_step_shell.client_presentation["mana_cost"] == 20
    assert broug_cloud_step_shell.client_presentation["recovery_time"] == 12000
    assert broug_cloud_step_shell.client_presentation["category_recovery_time"] == 1000
    assert broug_cloud_step_shell.client_presentation["start_recovery_time"] == 1000
    assert broug_cloud_step_shell.client_presentation["effect_1"] == 0
    assert broug_cloud_step_shell.client_presentation["spell_icon_id"] == 2363
    assert broug_cloud_step_shell.client_presentation["spellbook_ability_id"] == 1946202
    assert "Moves behind" in broug_cloud_step_shell.tooltip
    assert broug_marked_meridian_shell is not None
    assert broug_marked_meridian_shell.spell_id == 946203
    assert broug_marked_meridian_shell.family_id == "unit_target_effect"
    assert broug_marked_meridian_shell.behavior_kind == "broug_marked_meridian_v1"
    assert broug_marked_meridian_shell.client_presentation is not None
    assert broug_marked_meridian_shell.client_presentation["duration_index"] == 36
    assert broug_marked_meridian_shell.client_presentation["stack_amount"] == 1
    assert broug_marked_meridian_shell.client_presentation["effect_1"] == 6
    assert broug_marked_meridian_shell.client_presentation["effect_apply_aura_name_1"] == 4
    assert broug_marked_meridian_shell.client_presentation["spell_icon_id"] == 2112
    assert "35% increased damage" in broug_marked_meridian_shell.tooltip
    assert broug_killing_intent_shell is not None
    assert broug_killing_intent_shell.spell_id == 946620
    assert broug_killing_intent_shell.family_id == "self_aura"
    assert broug_killing_intent_shell.behavior_kind == "broug_killing_intent_v1"
    assert broug_killing_intent_shell.client_presentation is not None
    assert broug_killing_intent_shell.client_presentation["duration_index"] == 36
    assert broug_killing_intent_shell.client_presentation["effect_1"] == 6
    assert broug_killing_intent_shell.client_presentation["effect_apply_aura_name_1"] == 4
    assert broug_killing_intent_shell.client_presentation["spell_icon_id"] == 2112
    assert broug_killing_intent_shell.client_presentation["spell_family_name"] == 0
    assert broug_killing_intent_shell.client_presentation["spell_family_flags_1"] == 0
    assert broug_killing_intent_shell.client_presentation["spell_family_flags_2"] == 0
    assert broug_killing_intent_shell.client_presentation["spell_family_flags_3"] == 0
    assert broug_killing_intent_shell.client_presentation["damage_class"] == 0
    assert broug_killing_intent_shell.client_presentation["prevention_type"] == 0
    assert broug_killing_intent_shell.label == "Killing Intent"
    assert "10 sec killing window" in broug_killing_intent_shell.tooltip
    assert broug_suppressed_shell is not None
    assert broug_suppressed_shell.spell_id == 946204
    assert broug_suppressed_shell.family_id == "unit_target_effect"
    assert broug_suppressed_shell.behavior_kind == "broug_suppressed_v1"
    assert broug_suppressed_shell.client_presentation is not None
    assert broug_suppressed_shell.client_presentation["effect_1"] == 6
    assert broug_suppressed_shell.client_presentation["spell_icon_id"] == 2112
    assert broug_qi_reversal_shell is not None
    assert broug_qi_reversal_shell.spell_id == 946621
    assert broug_qi_reversal_shell.family_id == "self_aura"
    assert broug_qi_reversal_shell.client_presentation is not None
    assert broug_qi_reversal_shell.client_presentation["recovery_time"] == 45000
    assert broug_qi_reversal_shell.client_presentation["effect_1"] == 0
    assert broug_qi_reversal_shell.client_presentation["range_index"] == 1
    assert broug_qi_reversal_shell.client_presentation["spell_icon_id"] == 1933
    assert broug_qi_reversal_shell.client_presentation["spellbook_ability_id"] == 1946621
    assert broug_purged_state_shell is not None
    assert broug_purged_state_shell.spell_id == 946622
    assert broug_purged_state_shell.family_id == "self_aura"
    assert broug_purged_state_shell.client_presentation is not None
    assert broug_purged_state_shell.client_presentation["stack_amount"] == 2
    assert broug_purged_state_shell.client_presentation["spell_icon_id"] == 1933
    assert broug_purged_state_shell.client_presentation["spell_family_name"] == 0
    assert broug_purged_state_shell.client_presentation["spell_family_flags_1"] == 0
    assert broug_purged_state_shell.client_presentation["spell_family_flags_2"] == 0
    assert broug_purged_state_shell.client_presentation["spell_family_flags_3"] == 0
    assert broug_purged_state_shell.client_presentation["damage_class"] == 0
    assert broug_purged_state_shell.client_presentation["prevention_type"] == 0
    assert broug_parry_shell is not None
    assert broug_parry_shell.spell_id == 946800
    assert broug_parry_shell.family_id == "passive_aura"
    assert broug_parry_shell.behavior_kind == "broug_universal_parry_v1"
    assert broug_parry_shell.client_presentation is not None
    assert broug_parry_shell.client_presentation["spellbook_seed_spell_id"] == 1752
    assert broug_parry_shell.client_presentation["spellbook_ability_id"] == 1946800
    assert broug_parry_shell.client_presentation["spell_icon_id"] == 26
    assert broug_parry_shell.client_presentation["equipped_item_class"] == -1
    assert broug_parry_shell.client_presentation["effect_1"] == 0
    assert "Strength" in broug_parry_shell.tooltip
    assert "Expertise" in broug_parry_shell.tooltip
    assert "weapon mastery" in broug_parry_shell.tooltip
    assert broug_marksman_shell is not None
    assert broug_marksman_shell.spell_id == 946098
    assert broug_marksman_shell.family_id == "unit_target_projectile"
    assert broug_marksman_shell.behavior_kind == "broug_skirmisher_shot_v1"
    assert broug_marksman_shell.client_presentation is not None
    assert broug_marksman_shell.patch_seed_template == "wm_weapon_ranged_attack"
    assert broug_marksman_shell.client_presentation["effect_1"] == 58
    assert broug_marksman_shell.client_presentation["attributes"] == 0x410010
    assert broug_marksman_shell.client_presentation["interrupt_flags"] == 0
    assert broug_marksman_shell.client_presentation["aura_interrupt_flags"] == 0
    assert broug_marksman_shell.client_presentation["equipped_item_subclass_mask"] == 0x0005000C
    assert broug_marksman_shell.client_presentation["spell_visual_id_1"] == 0
    assert broug_marksman_shell.client_presentation["spell_visual_id_2"] == 0
    assert broug_marksman_shell.client_presentation["spellbook_seed_spell_id"] == 1752
    assert broug_marksman_shell.client_presentation["spellbook_ability_id"] == 1946098
    assert broug_marksman_shell.client_presentation["recovery_time"] == 0
    assert "ranged or thrown attack" in broug_marksman_shell.tooltip
    assert "while moving" in broug_marksman_shell.tooltip
    assert broug_retaliation_shell is not None
    assert broug_retaliation_shell.spell_id == 946802
    assert broug_retaliation_shell.family_id == "passive_aura"
    assert broug_retaliation_shell.behavior_kind == "broug_auto_retaliation_v1"
    assert broug_retaliation_shell.client_presentation is not None
    assert broug_retaliation_shell.client_presentation["spellbook_seed_spell_id"] == 1752
    assert broug_retaliation_shell.client_presentation["spellbook_ability_id"] == 1946802
    assert broug_retaliation_shell.client_presentation["equipped_item_class"] == -1
    assert broug_retaliation_shell.client_presentation["effect_1"] == 0
    assert broug_silent_meridian_shell is not None
    assert broug_silent_meridian_shell.spell_id == 946803
    assert broug_silent_meridian_shell.family_id == "passive_aura"
    assert broug_silent_meridian_shell.behavior_kind == "broug_silent_meridian_v1"
    assert broug_silent_meridian_shell.client_presentation is not None
    assert broug_silent_meridian_shell.client_presentation["spellbook_ability_id"] == 1946803
    assert broug_silent_meridian_shell.client_presentation["equipped_item_class"] == -1
    assert broug_silent_meridian_shell.client_presentation["effect_1"] == 0
    assert "Cloud Step" in broug_silent_meridian_shell.tooltip
    assert "10 sec" in broug_silent_meridian_shell.tooltip
    assert "6 sec" in broug_silent_meridian_shell.tooltip
    assert broug_domain_shell is not None
    assert broug_domain_shell.spell_id == 946804
    assert broug_domain_shell.family_id == "passive_aura"
    assert broug_domain_shell.client_presentation is not None
    assert broug_domain_shell.client_presentation["spellbook_ability_id"] == 1946804
    assert broug_domain_shell.client_presentation["effect_1"] == 0
    assert "15 sec" in broug_domain_shell.tooltip
    assert broug_predator_shell is not None
    assert broug_predator_shell.spell_id == 946805
    assert broug_predator_shell.family_id == "passive_aura"
    assert broug_predator_shell.client_presentation is not None
    assert broug_predator_shell.client_presentation["spellbook_ability_id"] == 1946805
    assert broug_vitality_shell is not None
    assert broug_vitality_shell.spell_id == 946806
    assert broug_vitality_shell.family_id == "passive_aura"
    assert broug_vitality_shell.client_presentation is not None
    assert broug_vitality_shell.client_presentation["spellbook_ability_id"] == 1946806
    assert pet_active_shell is not None
    assert pet_active_shell.family_id == "pet_active_compat"
    assert pet_active_shell.spell_id == 945000


def test_patch_rows_expand_compatibility_and_generic_ranges_and_overlay_named_shells() -> None:
    rows = generate_patch_rows(default_shell_bank_path())

    assert len(rows) == 1004
    assert rows[0].spell_id == 940000
    assert rows[-1].spell_id == 946999

    summon_shell = next(row for row in rows if row.spell_id == 940000)
    generic_projectile_slot = next(row for row in rows if row.spell_id == 946000)
    friendly_target_slot = next(row for row in rows if row.spell_id == 946100)
    echo_mind_blast_shell = next(row for row in rows if row.spell_id == 946099)
    target_centered_aoe_slot = next(row for row in rows if row.spell_id == 946300)
    caster_centered_aoe_slot = next(row for row in rows if row.spell_id == 946500)
    pet_active_shell = next(row for row in rows if row.spell_id == 945000)
    stasis_shell = next(row for row in rows if row.spell_id == 946600)
    random_targets_slot = next(row for row in rows if row.spell_id == 946700)
    lanathel_shell = next(row for row in rows if row.spell_id == 946601)
    watcher_beacon_shell = next(row for row in rows if row.spell_id == 946602)
    broug_vulnerable_shell = next(row for row in rows if row.spell_id == 946200)
    broug_deflected_shell = next(row for row in rows if row.spell_id == 946201)
    broug_cloud_step_shell = next(row for row in rows if row.spell_id == 946202)
    broug_marked_meridian_shell = next(row for row in rows if row.spell_id == 946203)
    broug_deflect_shell = next(row for row in rows if row.spell_id == 946603)
    broug_counter_stance_shell = next(row for row in rows if row.spell_id == 946605)
    energy_surge_shell = next(row for row in rows if row.spell_id == 946606)
    broug_killing_intent_shell = next(row for row in rows if row.spell_id == 946620)
    passive_slot = next(row for row in rows if row.spell_id == 946800)
    broug_marksman_shell = next(row for row in rows if row.spell_id == 946098)
    broug_retaliation_shell = next(row for row in rows if row.spell_id == 946802)
    broug_silent_meridian_shell = next(row for row in rows if row.spell_id == 946803)
    frontal_cone_slot = next(row for row in rows if row.spell_id == 946900)

    assert summon_shell.is_named_override is True
    assert summon_shell.shell_key == "bonebound_servant_v1"
    assert summon_shell.behavior_kind == "summon_bonebound_servant_v1"
    assert generic_projectile_slot.is_named_override is False
    assert generic_projectile_slot.shell_key == "unit_target_projectile_0001"
    assert generic_projectile_slot.seed_template == "wm_unit_target_projectile"
    assert friendly_target_slot.shell_key == "unit_target_friendly_0001"
    assert friendly_target_slot.seed_template == "wm_friendly_target_effect"
    assert echo_mind_blast_shell.is_named_override is True
    assert echo_mind_blast_shell.shell_key == "echo_restorer_mind_blast_x3_v1"
    assert echo_mind_blast_shell.seed_template == "wm_mind_blast"
    assert echo_mind_blast_shell.client_presentation["range_index"] == 157
    assert target_centered_aoe_slot.shell_key == "target_centered_aoe_0001"
    assert target_centered_aoe_slot.seed_template == "wm_target_centered_aoe"
    assert caster_centered_aoe_slot.shell_key == "caster_centered_aoe_0001"
    assert caster_centered_aoe_slot.seed_template == "wm_caster_centered_aoe"
    twin_shell = next(row for row in rows if row.spell_id == 940001)
    assert twin_shell.is_named_override is True
    assert twin_shell.shell_key == "bonebound_twins_v1"
    assert twin_shell.behavior_kind == "summon_bonebound_alpha_v3"
    assert twin_shell.client_presentation["spellbook_ability_id"] == 1940001
    assert twin_shell.client_presentation["spell_visual_id_2"] == 4054
    assert stasis_shell.is_named_override is True
    assert stasis_shell.shell_key == "bonebound_echo_stasis_v1"
    assert stasis_shell.behavior_kind == "bonebound_echo_stasis_v1"
    assert stasis_shell.client_presentation["cast_time_index"] == 6
    assert stasis_shell.client_presentation["reagent_1_item_id"] == 6265
    assert lanathel_shell.is_named_override is True
    assert lanathel_shell.shell_key == "lanathel_blood_queen_stance_v1"
    assert lanathel_shell.behavior_kind == "lanathel_blood_queen_stance_v1"
    assert lanathel_shell.client_presentation["spellbook_ability_id"] == 1946601
    assert lanathel_shell.client_presentation["spell_icon_id"] == 4165
    assert watcher_beacon_shell.is_named_override is True
    assert watcher_beacon_shell.shell_key == "wm_watcher_beacon_v1"
    assert watcher_beacon_shell.seed_template == "wm_watcher_marker"
    assert watcher_beacon_shell.client_presentation["duration_index"] == 21
    assert watcher_beacon_shell.client_presentation["effect_apply_aura_name_1"] == 4
    assert broug_vulnerable_shell.is_named_override is True
    assert broug_vulnerable_shell.shell_key == "broug_vulnerable_v1"
    assert broug_vulnerable_shell.behavior_kind == "broug_vulnerable_v1"
    assert broug_vulnerable_shell.seed_template == "wm_unit_target_effect"
    assert broug_vulnerable_shell.client_presentation["duration_index"] == 3
    assert broug_vulnerable_shell.client_presentation["stack_amount"] == 255
    assert broug_vulnerable_shell.client_presentation["effect_1"] == 6
    assert broug_vulnerable_shell.client_presentation["effect_apply_aura_name_1"] == 4
    assert broug_vulnerable_shell.client_presentation["spell_icon_id"] == 558
    assert broug_deflected_shell.is_named_override is True
    assert broug_deflected_shell.shell_key == "broug_deflected_v1"
    assert broug_deflected_shell.behavior_kind == "broug_deflected_v1"
    assert broug_deflected_shell.seed_template == "wm_unit_target_effect"
    assert broug_deflected_shell.client_presentation["duration_index"] == 36
    assert broug_deflected_shell.client_presentation["effect_1"] == 6
    assert broug_deflected_shell.client_presentation["effect_apply_aura_name_1"] == 4
    assert broug_deflected_shell.client_presentation["spell_icon_id"] == 558
    assert broug_cloud_step_shell.is_named_override is True
    assert broug_cloud_step_shell.shell_key == "broug_cloud_step_v1"
    assert broug_cloud_step_shell.behavior_kind == "broug_cloud_step_v1"
    assert broug_cloud_step_shell.seed_template == "wm_unit_target_effect"
    assert broug_cloud_step_shell.client_presentation["mana_cost"] == 20
    assert broug_cloud_step_shell.client_presentation["recovery_time"] == 12000
    assert broug_cloud_step_shell.client_presentation["category_recovery_time"] == 1000
    assert broug_cloud_step_shell.client_presentation["start_recovery_time"] == 1000
    assert broug_cloud_step_shell.client_presentation["spellbook_ability_id"] == 1946202
    assert broug_marked_meridian_shell.is_named_override is True
    assert broug_marked_meridian_shell.shell_key == "broug_marked_meridian_v1"
    assert broug_marked_meridian_shell.behavior_kind == "broug_marked_meridian_v1"
    assert broug_marked_meridian_shell.seed_template == "wm_unit_target_effect"
    assert broug_marked_meridian_shell.client_presentation["duration_index"] == 36
    assert broug_marked_meridian_shell.client_presentation["stack_amount"] == 1
    assert broug_marked_meridian_shell.client_presentation["effect_1"] == 6
    assert broug_marked_meridian_shell.client_presentation["effect_apply_aura_name_1"] == 4
    assert broug_deflect_shell.is_named_override is True
    assert broug_deflect_shell.shell_key == "broug_deflect_v1"
    assert broug_deflect_shell.behavior_kind == "broug_deflect_v1"
    assert broug_deflect_shell.seed_template == "wm_self_aura"
    assert broug_deflect_shell.client_presentation["mana_cost"] == 5
    assert broug_deflect_shell.client_presentation["recovery_time"] == 500
    assert broug_deflect_shell.client_presentation["duration_index"] == 0
    assert broug_deflect_shell.client_presentation["effect_1"] == 0
    assert broug_deflect_shell.client_presentation["effect_apply_aura_name_1"] == 0
    assert broug_deflect_shell.client_presentation["spell_icon_id"] == 278
    assert broug_counter_stance_shell.is_named_override is True
    assert broug_counter_stance_shell.shell_key == "broug_deflect_counter_stance_v1"
    assert broug_counter_stance_shell.behavior_kind == "broug_deflect_counter_stance_v1"
    assert broug_counter_stance_shell.seed_template == "wm_self_aura"
    assert broug_counter_stance_shell.client_presentation["recovery_time"] == 0
    assert broug_counter_stance_shell.client_presentation["duration_index"] == 21
    assert broug_counter_stance_shell.client_presentation["effect_1"] == 6
    assert broug_counter_stance_shell.client_presentation["effect_apply_aura_name_1"] == 36
    assert broug_counter_stance_shell.client_presentation["effect_misc_value_1"] == 13
    assert broug_counter_stance_shell.client_presentation["stance_bar_order"] == 1
    assert broug_counter_stance_shell.client_presentation["spell_visual_id_2"] == 0
    assert broug_counter_stance_shell.client_presentation["spell_icon_id"] == 563
    assert broug_counter_stance_shell.client_presentation["duration_index"] == 21
    assert broug_counter_stance_shell.client_presentation["spell_family_name"] == 8
    assert energy_surge_shell.is_named_override is True
    assert energy_surge_shell.shell_key == "energy_surge_potion_v1"
    assert energy_surge_shell.behavior_kind == "energy_surge_potion_v1"
    assert energy_surge_shell.seed_template == "wm_self_aura"
    assert energy_surge_shell.client_presentation["spell_icon_id"] == 1299
    assert broug_killing_intent_shell.is_named_override is True
    assert broug_killing_intent_shell.shell_key == "broug_killing_intent_v1"
    assert broug_killing_intent_shell.behavior_kind == "broug_killing_intent_v1"
    assert broug_killing_intent_shell.seed_template == "wm_self_aura"
    assert broug_killing_intent_shell.client_presentation["duration_index"] == 36
    assert broug_killing_intent_shell.client_presentation["effect_1"] == 6
    assert broug_killing_intent_shell.client_presentation["effect_apply_aura_name_1"] == 4
    assert broug_killing_intent_shell.client_presentation["spell_icon_id"] == 2112
    assert random_targets_slot.shell_key == "random_targets_0001"
    assert random_targets_slot.seed_template == "wm_random_targets"
    assert passive_slot.is_named_override is True
    assert passive_slot.shell_key == "broug_universal_parry_v1"
    assert passive_slot.behavior_kind == "broug_universal_parry_v1"
    assert passive_slot.seed_template == "wm_passive_aura"
    assert passive_slot.client_presentation["spellbook_ability_id"] == 1946800
    assert passive_slot.client_presentation["spell_icon_id"] == 26
    assert passive_slot.client_presentation["equipped_item_class"] == -1
    assert passive_slot.client_presentation["effect_1"] == 0
    assert broug_marksman_shell.is_named_override is True
    assert broug_marksman_shell.shell_key == "broug_skirmisher_shot_v1"
    assert broug_marksman_shell.behavior_kind == "broug_skirmisher_shot_v1"
    assert broug_marksman_shell.seed_template == "wm_weapon_ranged_attack"
    assert broug_marksman_shell.client_presentation["spellbook_ability_id"] == 1946098
    assert broug_marksman_shell.client_presentation["effect_1"] == 58
    assert broug_marksman_shell.client_presentation["attributes"] == 0x410010
    assert broug_marksman_shell.client_presentation["interrupt_flags"] == 0
    assert broug_marksman_shell.client_presentation["equipped_item_subclass_mask"] == 0x0005000C
    assert broug_marksman_shell.client_presentation["spell_visual_id_2"] == 0
    assert broug_marksman_shell.client_presentation["recovery_time"] == 0
    assert broug_retaliation_shell.is_named_override is True
    assert broug_retaliation_shell.shell_key == "broug_auto_retaliation_v1"
    assert broug_retaliation_shell.behavior_kind == "broug_auto_retaliation_v1"
    assert broug_retaliation_shell.seed_template == "wm_passive_aura"
    assert broug_retaliation_shell.client_presentation["spellbook_ability_id"] == 1946802
    assert broug_retaliation_shell.client_presentation["equipped_item_class"] == -1
    assert broug_retaliation_shell.client_presentation["effect_1"] == 0
    assert broug_silent_meridian_shell.is_named_override is True
    assert broug_silent_meridian_shell.shell_key == "broug_silent_meridian_v1"
    assert broug_silent_meridian_shell.behavior_kind == "broug_silent_meridian_v1"
    assert broug_silent_meridian_shell.seed_template == "wm_passive_aura"
    assert broug_silent_meridian_shell.client_presentation["spellbook_ability_id"] == 1946803
    assert broug_silent_meridian_shell.client_presentation["equipped_item_class"] == -1
    assert broug_silent_meridian_shell.client_presentation["effect_1"] == 0
    assert frontal_cone_slot.shell_key == "frontal_cone_0001"
    assert frontal_cone_slot.seed_template == "wm_frontal_cone"
    assert pet_active_shell.is_named_override is True
    assert pet_active_shell.shell_key == "bonebound_servant_slash_v1"


def test_patch_plan_reports_range_driven_summary() -> None:
    plan = build_patch_plan(default_shell_bank_path())

    assert plan["schema_version"] == "wm.spell_shell_patch_plan.v1"
    assert plan["generation_mode"] == "range_driven"
    assert plan["family_count"] == 13
    assert plan["generic_family_count"] == 10
    assert plan["slots_per_family"] == 100
    assert plan["reserve_gap_slots"] == 0
    assert plan["total_rows"] == 1004
    assert plan["named_override_count"] == 26
