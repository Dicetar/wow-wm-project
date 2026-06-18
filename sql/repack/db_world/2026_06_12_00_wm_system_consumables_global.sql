-- WM reusable system consumables are global/unbound across characters.
UPDATE item_template
SET bonding = 0
WHERE entry IN (910007, 910008, 910009, 910014, 910015);

UPDATE wm_reserved_slot
SET
    CharacterGUID = NULL,
    NotesJSON = '["wm_random_enchant_consumable","base_item_entry:955","native_script:wm_random_enchant_consumable","global_all_characters","bind:none"]'
WHERE EntityType = 'item'
  AND ReservedID = 910007;

UPDATE wm_reserved_slot
SET
    CharacterGUID = NULL,
    NotesJSON = '["wm_random_enchant_consumable","base_item_entry:955","single_slot","tier_roll:3=40,4=30,5=30","deterministic_costs:t3=5,t4=12,t5=20","deterministic_categories:stats,damage,ratings,defense,resistances,utility,other","global_all_characters","bind:none"]'
WHERE EntityType = 'item'
  AND ReservedID = 910008;

UPDATE wm_reserved_slot
SET
    CharacterGUID = NULL,
    NotesJSON = '["wm_bone_lure_charm","base_item_entry:41119","native_script:wm_bone_lure_charm","deploys_creature:920102","global_all_characters","bind:none"]'
WHERE EntityType = 'item'
  AND ReservedID = 910009;

UPDATE wm_reserved_slot
SET
    CharacterGUID = NULL,
    NotesJSON = '["wm_bone_lure_obelisk","base_creature_entry:3579","display_id:16135","native_script:wm_bone_lure_obelisk","global_all_characters"]'
WHERE EntityType = 'creature_template'
  AND ReservedID = 920102;

UPDATE wm_reserved_slot
SET
    CharacterGUID = NULL,
    NotesJSON = '["wm_energy_surge_potion","base_item_entry:33448","native_script:wm_energy_surge_potion","visible_aura:946606","energy_per_second:10","duration_ms:7200000","global_all_characters","bind:none"]'
WHERE EntityType = 'item'
  AND ReservedID = 910014;

UPDATE wm_reserved_slot
SET
    CharacterGUID = NULL,
    NotesJSON = '["shell_spell","energy_surge_potion_v1","visible_aura","energy_per_second:10","duration_ms:7200000","global_all_characters"]'
WHERE EntityType = 'spell'
  AND ReservedID = 946606;

UPDATE wm_reserved_slot
SET
    CharacterGUID = NULL,
    NotesJSON = '["wm_enchanting_stone","base_item_entry:34057","native_script:wm_enchanting_stone","addon_gui:slot_upgrade_cancel","max_upgrade:+8","stat_multiplier:2^level","boss_drop:35","final_boss_drop:100","global_all_characters","bind:none"]'
WHERE EntityType = 'item'
  AND ReservedID = 910015;
