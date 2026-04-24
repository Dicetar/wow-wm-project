-- Separate Bonebound Alpha from stock Summon Voidwalker creature truth.
-- The shell spell was already moved off stock carriers, but using creature entry
-- 1860 still let stock 697 resolve to Bonebound Alpha through shared pet state.

SET @wm_bonebound_alpha_creature_entry := 920100;
SET @wm_voidwalker_source_entry := 1860;

DELETE FROM creature_template_model WHERE CreatureID = @wm_bonebound_alpha_creature_entry;
DELETE FROM creature_template_addon WHERE entry = @wm_bonebound_alpha_creature_entry;
DELETE FROM creature_template_movement WHERE CreatureId = @wm_bonebound_alpha_creature_entry;
DELETE FROM creature_template_resistance WHERE CreatureID = @wm_bonebound_alpha_creature_entry;
DELETE FROM creature_template_spell WHERE CreatureID = @wm_bonebound_alpha_creature_entry;
DELETE FROM creature_template WHERE entry = @wm_bonebound_alpha_creature_entry;

DROP TEMPORARY TABLE IF EXISTS wm_tmp_bonebound_alpha_template;
CREATE TEMPORARY TABLE wm_tmp_bonebound_alpha_template AS
SELECT * FROM creature_template WHERE entry = @wm_voidwalker_source_entry;

UPDATE wm_tmp_bonebound_alpha_template
SET
    entry = @wm_bonebound_alpha_creature_entry,
    name = 'Bonebound Alpha',
    subname = '',
    AIName = '',
    ScriptName = '',
    VerifiedBuild = NULL;

INSERT INTO creature_template
SELECT * FROM wm_tmp_bonebound_alpha_template;

DROP TEMPORARY TABLE IF EXISTS wm_tmp_bonebound_alpha_template;

INSERT INTO creature_template_model (CreatureID, Idx, CreatureDisplayID, DisplayScale, Probability, VerifiedBuild)
SELECT @wm_bonebound_alpha_creature_entry, Idx, CreatureDisplayID, DisplayScale, Probability, VerifiedBuild
FROM creature_template_model
WHERE CreatureID = @wm_voidwalker_source_entry;

INSERT INTO creature_template_addon (entry, path_id, mount, bytes1, bytes2, emote, visibilityDistanceType, auras)
SELECT @wm_bonebound_alpha_creature_entry, path_id, mount, bytes1, bytes2, emote, visibilityDistanceType, auras
FROM creature_template_addon
WHERE entry = @wm_voidwalker_source_entry;

INSERT INTO creature_template_movement (CreatureId, Ground, Swim, Flight, Rooted, Chase, Random, InteractionPauseTimer)
SELECT @wm_bonebound_alpha_creature_entry, Ground, Swim, Flight, Rooted, Chase, Random, InteractionPauseTimer
FROM creature_template_movement
WHERE CreatureId = @wm_voidwalker_source_entry;

INSERT INTO creature_template_resistance (CreatureID, School, Resistance, VerifiedBuild)
SELECT @wm_bonebound_alpha_creature_entry, School, Resistance, VerifiedBuild
FROM creature_template_resistance
WHERE CreatureID = @wm_voidwalker_source_entry;

INSERT INTO creature_template_spell (CreatureID, `Index`, Spell, VerifiedBuild)
SELECT @wm_bonebound_alpha_creature_entry, `Index`, Spell, VerifiedBuild
FROM creature_template_spell
WHERE CreatureID = @wm_voidwalker_source_entry;

INSERT INTO wm_spell_behavior (ShellSpellID, BehaviorKind, ConfigJSON, Status) VALUES
(940000, 'summon_bonebound_servant_v1', '{"creature_entry":920100,"display_id":734,"name":"Bonebound Servant","require_corpse":true,"persist_pet":true,"owner_intellect_to_all_stats":true,"owner_shadow_power_to_attack_power":true,"virtual_item_1":1897,"virtual_item_2":0,"virtual_item_3":0}', 'planned'),
(940001, 'summon_bonebound_alpha_v3', '{"creature_entry":920100,"display_id":734,"name":"Bonebound Alpha","require_corpse":false,"persist_pet":true,"spawn_omega":false,"preserve_base_stats":true,"owner_intellect_to_all_stats":true,"owner_intellect_to_all_stats_scale":1.0,"owner_shadow_power_to_attack_power":true,"owner_shadow_power_to_attack_power_scale":1.0,"virtual_item_1":28773,"virtual_item_2":0,"virtual_item_3":0,"shadow_dot_enabled":true,"shadow_dot_cooldown_ms":6000,"shadow_dot_duration_ms":4000,"shadow_dot_tick_ms":1000,"shadow_dot_base_damage":3,"shadow_dot_damage_per_level_pct":25,"shadow_dot_damage_per_intellect_pct":1,"shadow_dot_damage_per_shadow_power_pct":0,"alpha_echo_enabled":true,"alpha_echo_creature_entry":920101,"alpha_echo_proc_chance_pct":7.5,"alpha_echo_max_active":40,"alpha_echo_damage_pct":100,"alpha_echo_follow_distance":2.6,"alpha_echo_follow_angle":-1.5708}', 'active')
ON DUPLICATE KEY UPDATE
    BehaviorKind = VALUES(BehaviorKind),
    ConfigJSON = VALUES(ConfigJSON),
    Status = VALUES(Status),
    UpdatedAt = CURRENT_TIMESTAMP;

SELECT
    'bonebound_alpha_creature_template' AS metric,
    entry AS value
FROM creature_template
WHERE entry = @wm_bonebound_alpha_creature_entry;

SELECT
    'bonebound_alpha_behavior_creature_entry' AS metric,
    JSON_EXTRACT(ConfigJSON, '$.creature_entry') AS value
FROM wm_spell_behavior
WHERE ShellSpellID = 940001;
