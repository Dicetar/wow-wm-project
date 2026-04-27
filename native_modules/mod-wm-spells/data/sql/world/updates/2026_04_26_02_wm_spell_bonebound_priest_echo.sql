-- Add rare support-role Echoes to the Bonebound Alpha echo lane.
-- The creature template is separate so live proof can distinguish support Echoes by name.

SET @wm_priest_echo_creature_entry := 920103;
SET @wm_alpha_echo_source_entry := 920101;
SET @wm_priest_echo_model_source_entry := 15121;

DELETE FROM creature_template_model WHERE CreatureID = @wm_priest_echo_creature_entry;
DELETE FROM creature_template_addon WHERE entry = @wm_priest_echo_creature_entry;
DELETE FROM creature_template_movement WHERE CreatureId = @wm_priest_echo_creature_entry;
DELETE FROM creature_template_resistance WHERE CreatureID = @wm_priest_echo_creature_entry;
DELETE FROM creature_template_spell WHERE CreatureID = @wm_priest_echo_creature_entry;
DELETE FROM creature_template WHERE entry = @wm_priest_echo_creature_entry;

DROP TEMPORARY TABLE IF EXISTS wm_tmp_bonebound_priest_echo_template;
CREATE TEMPORARY TABLE wm_tmp_bonebound_priest_echo_template AS
SELECT * FROM creature_template WHERE entry = @wm_alpha_echo_source_entry;

UPDATE wm_tmp_bonebound_priest_echo_template
SET
    entry = @wm_priest_echo_creature_entry,
    name = 'Echo Restorer',
    subname = 'Support Echo',
    AIName = '',
    ScriptName = '',
    VerifiedBuild = NULL;

INSERT INTO creature_template
SELECT * FROM wm_tmp_bonebound_priest_echo_template;

DROP TEMPORARY TABLE IF EXISTS wm_tmp_bonebound_priest_echo_template;

INSERT INTO creature_template_model (CreatureID, Idx, CreatureDisplayID, DisplayScale, Probability, VerifiedBuild)
SELECT @wm_priest_echo_creature_entry, Idx, CreatureDisplayID, DisplayScale, Probability, VerifiedBuild
FROM creature_template_model
WHERE CreatureID = @wm_priest_echo_model_source_entry;

INSERT INTO creature_template_addon (entry, path_id, mount, bytes1, bytes2, emote, visibilityDistanceType, auras)
SELECT @wm_priest_echo_creature_entry, path_id, mount, bytes1, bytes2, emote, visibilityDistanceType, auras
FROM creature_template_addon
WHERE entry = @wm_alpha_echo_source_entry;

INSERT INTO creature_template_movement (CreatureId, Ground, Swim, Flight, Rooted, Chase, Random, InteractionPauseTimer)
SELECT @wm_priest_echo_creature_entry, Ground, Swim, Flight, Rooted, Chase, Random, InteractionPauseTimer
FROM creature_template_movement
WHERE CreatureId = @wm_alpha_echo_source_entry;

INSERT INTO creature_template_resistance (CreatureID, School, Resistance, VerifiedBuild)
SELECT @wm_priest_echo_creature_entry, School, Resistance, VerifiedBuild
FROM creature_template_resistance
WHERE CreatureID = @wm_alpha_echo_source_entry;

INSERT INTO creature_template_spell (CreatureID, `Index`, Spell, VerifiedBuild)
SELECT @wm_priest_echo_creature_entry, `Index`, Spell, VerifiedBuild
FROM creature_template_spell
WHERE CreatureID = @wm_alpha_echo_source_entry;

UPDATE wm_spell_behavior
SET ConfigJSON = JSON_SET(
    ConfigJSON,
    '$.priest_echo_enabled', true,
    '$.priest_echo_creature_entry', 920103,
    '$.alpha_echo_name', 'Echo Destroyer',
    '$.priest_echo_name', 'Echo Restorer',
    '$.priest_echo_display_id', 11397,
    '$.priest_echo_virtual_item_1', 0,
    '$.priest_echo_virtual_item_2', 0,
    '$.priest_echo_virtual_item_3', 0,
    '$.priest_echo_staff_item_entries', JSON_ARRAY(18842, 22800, 19909, 21275, 21452, 22335, 19570, 19566),
    '$.priest_echo_scale_multiplier', 0.9,
    '$.priest_echo_proc_chance_pct', 5.0,
    '$.priest_echo_max_active', 10,
    '$.priest_echo_pity_after_warrior_spawns', 6,
    '$.priest_echo_damage_pct', 35,
    '$.priest_echo_support_radius', 45.0,
    '$.priest_echo_heal_below_health_pct', 95,
    '$.priest_echo_heal_spell_id', 2061,
    '$.priest_echo_heal_base_pct', 12,
    '$.priest_echo_heal_cooldown_ms', 2500,
    '$.priest_echo_renew_spell_id', 139,
    '$.priest_echo_renew_base_pct', 5,
    '$.priest_echo_renew_cooldown_ms', 10000,
    '$.priest_echo_shield_spell_id', 17,
    '$.priest_echo_shield_base_pct', 10,
    '$.priest_echo_shield_cooldown_ms', 12000,
    '$.priest_echo_disease_dispel_spell_id', 528,
    '$.priest_echo_curse_dispel_spell_id', 475,
    '$.priest_echo_dispel_cooldown_ms', 8000,
    '$.priest_echo_mass_dispel_spell_id', 32375,
    '$.priest_echo_mass_dispel_cooldown_ms', 180000,
    '$.priest_echo_mass_dispel_min_affected', 3,
    '$.priest_echo_mass_dispel_min_severity', 8,
    '$.priest_echo_mass_dispel_max_removals', 8,
    '$.priest_echo_dps_spell_id', 73142,
    '$.priest_echo_dps_damage_spell_id', 69057,
    '$.priest_echo_dps_cast_time_ms', 1500,
    '$.priest_echo_dps_damage_pct', 9,
    '$.priest_echo_dps_cooldown_ms', 2500,
    '$.priest_echo_spell_power_to_healing_pct', 35,
    '$.priest_echo_spell_power_to_shield_pct', 30,
    '$.priest_echo_spell_power_to_damage_pct', 11,
    '$.priest_echo_safe_follow_distance', 7.0,
    '$.priest_echo_safe_min_enemy_distance', 6.0
)
WHERE ShellSpellID = 940001
  AND BehaviorKind = 'summon_bonebound_alpha_v3'
  AND Status = 'active';

SELECT
    'bonebound_priest_echo_config' AS metric,
    JSON_EXTRACT(ConfigJSON, '$.priest_echo_enabled') AS priest_echo_enabled,
    JSON_EXTRACT(ConfigJSON, '$.priest_echo_creature_entry') AS priest_echo_creature_entry,
    JSON_EXTRACT(ConfigJSON, '$.alpha_echo_name') AS alpha_echo_name,
    JSON_EXTRACT(ConfigJSON, '$.priest_echo_name') AS priest_echo_name,
    JSON_EXTRACT(ConfigJSON, '$.priest_echo_proc_chance_pct') AS priest_echo_proc_chance_pct,
    JSON_EXTRACT(ConfigJSON, '$.priest_echo_max_active') AS priest_echo_max_active,
    JSON_EXTRACT(ConfigJSON, '$.priest_echo_pity_after_warrior_spawns') AS priest_echo_pity_after_warrior_spawns,
    JSON_EXTRACT(ConfigJSON, '$.priest_echo_display_id') AS priest_echo_display_id,
    JSON_EXTRACT(ConfigJSON, '$.priest_echo_staff_item_entries') AS priest_echo_staff_item_entries,
    JSON_EXTRACT(ConfigJSON, '$.priest_echo_heal_spell_id') AS priest_echo_heal_spell_id,
    JSON_EXTRACT(ConfigJSON, '$.priest_echo_shield_spell_id') AS priest_echo_shield_spell_id,
    JSON_EXTRACT(ConfigJSON, '$.priest_echo_mass_dispel_spell_id') AS priest_echo_mass_dispel_spell_id,
    JSON_EXTRACT(ConfigJSON, '$.priest_echo_safe_follow_distance') AS priest_echo_safe_follow_distance,
    JSON_EXTRACT(ConfigJSON, '$.priest_echo_safe_min_enemy_distance') AS priest_echo_safe_min_enemy_distance,
    JSON_EXTRACT(ConfigJSON, '$.priest_echo_dps_spell_id') AS priest_echo_dps_spell_id,
    JSON_EXTRACT(ConfigJSON, '$.priest_echo_dps_damage_spell_id') AS priest_echo_dps_damage_spell_id,
    JSON_EXTRACT(ConfigJSON, '$.priest_echo_dps_cast_time_ms') AS priest_echo_dps_cast_time_ms,
    JSON_EXTRACT(ConfigJSON, '$.priest_echo_dps_damage_pct') AS priest_echo_dps_damage_pct,
    JSON_EXTRACT(ConfigJSON, '$.priest_echo_spell_power_to_damage_pct') AS priest_echo_spell_power_to_damage_pct
FROM wm_spell_behavior
WHERE ShellSpellID = 940001
  AND BehaviorKind = 'summon_bonebound_alpha_v3'
  AND Status = 'active';
