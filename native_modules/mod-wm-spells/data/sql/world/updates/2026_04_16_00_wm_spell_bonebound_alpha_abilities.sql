-- Retire the live 940001 Omega companion experiment and move the fast lane to
-- one real Alpha pet with native bleed/echo behavior.
-- The shell ID stays stable so existing operator commands keep working.

SET @wm_alpha_echo_creature_entry := 920101;
SET @wm_voidwalker_source_entry := 1860;

DELETE FROM creature_template_model WHERE CreatureID = @wm_alpha_echo_creature_entry;
DELETE FROM creature_template_addon WHERE entry = @wm_alpha_echo_creature_entry;
DELETE FROM creature_template_movement WHERE CreatureId = @wm_alpha_echo_creature_entry;
DELETE FROM creature_template_resistance WHERE CreatureID = @wm_alpha_echo_creature_entry;
DELETE FROM creature_template_spell WHERE CreatureID = @wm_alpha_echo_creature_entry;
DELETE FROM creature_template WHERE entry = @wm_alpha_echo_creature_entry;

DROP TEMPORARY TABLE IF EXISTS wm_tmp_bonebound_alpha_echo_template;
CREATE TEMPORARY TABLE wm_tmp_bonebound_alpha_echo_template AS
SELECT * FROM creature_template WHERE entry = @wm_voidwalker_source_entry;

UPDATE wm_tmp_bonebound_alpha_echo_template
SET
    entry = @wm_alpha_echo_creature_entry,
    name = 'Echo Destroyer',
    subname = '',
    AIName = '',
    ScriptName = '',
    VerifiedBuild = NULL;

INSERT INTO creature_template
SELECT * FROM wm_tmp_bonebound_alpha_echo_template;

DROP TEMPORARY TABLE IF EXISTS wm_tmp_bonebound_alpha_echo_template;

INSERT INTO creature_template_model (CreatureID, Idx, CreatureDisplayID, DisplayScale, Probability, VerifiedBuild)
SELECT @wm_alpha_echo_creature_entry, Idx, CreatureDisplayID, DisplayScale, Probability, VerifiedBuild
FROM creature_template_model
WHERE CreatureID = @wm_voidwalker_source_entry;

INSERT INTO creature_template_addon (entry, path_id, mount, bytes1, bytes2, emote, visibilityDistanceType, auras)
SELECT @wm_alpha_echo_creature_entry, path_id, mount, bytes1, bytes2, emote, visibilityDistanceType, auras
FROM creature_template_addon
WHERE entry = @wm_voidwalker_source_entry;

INSERT INTO creature_template_movement (CreatureId, Ground, Swim, Flight, Rooted, Chase, Random, InteractionPauseTimer)
SELECT @wm_alpha_echo_creature_entry, Ground, Swim, Flight, Rooted, Chase, Random, InteractionPauseTimer
FROM creature_template_movement
WHERE CreatureId = @wm_voidwalker_source_entry;

INSERT INTO creature_template_resistance (CreatureID, School, Resistance, VerifiedBuild)
SELECT @wm_alpha_echo_creature_entry, School, Resistance, VerifiedBuild
FROM creature_template_resistance
WHERE CreatureID = @wm_voidwalker_source_entry;

INSERT INTO creature_template_spell (CreatureID, `Index`, Spell, VerifiedBuild)
SELECT @wm_alpha_echo_creature_entry, `Index`, Spell, VerifiedBuild
FROM creature_template_spell
WHERE CreatureID = @wm_voidwalker_source_entry;

INSERT INTO wm_spell_shell (ShellSpellID, ShellKey, FamilyID, Label, State, ClientPatchVersion, OwnershipKey, ProvenanceJSON) VALUES
(940001, 'bonebound_twins_v1', 'summon_pet', 'Bonebound Alpha', 'planned', 'wm_spell_shell_bank.v1', 'wm.spell_shell:bonebound_twins_v1', '{"notes":["Legacy key retained for compatibility. Shell 940001 now runs the single-Alpha behavior; Omega TempSummon parity is retired after live damage/mana mismatch."]}')
ON DUPLICATE KEY UPDATE
    ShellKey = VALUES(ShellKey),
    FamilyID = VALUES(FamilyID),
    Label = VALUES(Label),
    State = VALUES(State),
    ClientPatchVersion = VALUES(ClientPatchVersion),
    OwnershipKey = VALUES(OwnershipKey),
    ProvenanceJSON = VALUES(ProvenanceJSON),
    UpdatedAt = CURRENT_TIMESTAMP;

INSERT INTO wm_spell_behavior (ShellSpellID, BehaviorKind, ConfigJSON, Status) VALUES
(940001, 'summon_bonebound_alpha_v3', '{"creature_entry":1860,"display_id":734,"name":"Bonebound Alpha","require_corpse":false,"persist_pet":true,"spawn_omega":false,"preserve_base_stats":true,"owner_intellect_to_all_stats":true,"owner_intellect_to_all_stats_scale":1.0,"owner_shadow_power_to_attack_power":true,"owner_shadow_power_to_attack_power_scale":1.0,"virtual_item_1":28773,"virtual_item_2":0,"virtual_item_3":0,"bleed_enabled":true,"bleed_cooldown_ms":6000,"bleed_duration_ms":4000,"bleed_tick_ms":1000,"bleed_base_damage":3,"bleed_damage_per_attack_power_pct":20,"bleed_damage_per_level_pct":0,"bleed_damage_per_intellect_pct":0,"bleed_damage_per_shadow_power_pct":0,"alpha_echo_enabled":true,"alpha_echo_creature_entry":920101,"alpha_echo_name":"Echo Destroyer","alpha_echo_proc_chance_pct":7.5,"alpha_echo_max_active":40,"alpha_echo_damage_pct":100,"alpha_echo_follow_distance":2.6,"alpha_echo_follow_angle":-1.5708}', 'active')
ON DUPLICATE KEY UPDATE
    BehaviorKind = VALUES(BehaviorKind),
    ConfigJSON = VALUES(ConfigJSON),
    Status = VALUES(Status),
    UpdatedAt = CURRENT_TIMESTAMP;

DELETE FROM spell_script_names WHERE spell_id = 940001 AND ScriptName = 'spell_wm_shell_dispatch';
INSERT INTO spell_script_names (spell_id, ScriptName) VALUES
(940001, 'spell_wm_shell_dispatch');

SELECT
    'bonebound_alpha_behavior' AS metric,
    BehaviorKind AS value
FROM wm_spell_behavior
WHERE ShellSpellID = 940001;

SELECT
    'bonebound_alpha_spawn_omega' AS metric,
    JSON_EXTRACT(ConfigJSON, '$.spawn_omega') AS value
FROM wm_spell_behavior
WHERE ShellSpellID = 940001;

SELECT
    'bonebound_alpha_echo_creature_entry' AS metric,
    JSON_EXTRACT(ConfigJSON, '$.alpha_echo_creature_entry') AS value
FROM wm_spell_behavior
WHERE ShellSpellID = 940001;
