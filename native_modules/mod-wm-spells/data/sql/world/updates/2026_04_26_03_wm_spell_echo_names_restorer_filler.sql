-- Retune Bonebound Echo role names and Priest Echo support spacing/filler spell.
-- This is idempotent so BridgeLab can be patched without replaying the full Priest template rebuild.

UPDATE creature_template
SET name = 'Echo Destroyer',
    subname = ''
WHERE entry = 920101;

UPDATE creature_template
SET name = 'Echo Restorer',
    subname = 'Support Echo'
WHERE entry = 920103;

UPDATE wm_spell_behavior
SET ConfigJSON = JSON_SET(
    ConfigJSON,
    '$.alpha_echo_name', 'Echo Destroyer',
    '$.priest_echo_name', 'Echo Restorer',
    '$.priest_echo_dps_spell_id', 73142,
    '$.priest_echo_dps_damage_spell_id', 69057,
    '$.priest_echo_dps_cast_time_ms', 1500,
    '$.priest_echo_dps_damage_pct', 9,
    '$.priest_echo_dps_cooldown_ms', 2500,
    '$.priest_echo_spell_power_to_damage_pct', 11,
    '$.priest_echo_safe_follow_distance', 7.0,
    '$.priest_echo_safe_min_enemy_distance', 6.0
)
WHERE ShellSpellID = 940001
  AND BehaviorKind = 'summon_bonebound_alpha_v3'
  AND Status = 'active';

SELECT
    'bonebound_echo_names_restorer_filler' AS metric,
    JSON_EXTRACT(ConfigJSON, '$.alpha_echo_name') AS alpha_echo_name,
    JSON_EXTRACT(ConfigJSON, '$.priest_echo_name') AS priest_echo_name,
    JSON_EXTRACT(ConfigJSON, '$.priest_echo_dps_spell_id') AS priest_echo_dps_spell_id,
    JSON_EXTRACT(ConfigJSON, '$.priest_echo_dps_damage_spell_id') AS priest_echo_dps_damage_spell_id,
    JSON_EXTRACT(ConfigJSON, '$.priest_echo_dps_cast_time_ms') AS priest_echo_dps_cast_time_ms,
    JSON_EXTRACT(ConfigJSON, '$.priest_echo_dps_damage_pct') AS priest_echo_dps_damage_pct,
    JSON_EXTRACT(ConfigJSON, '$.priest_echo_dps_cooldown_ms') AS priest_echo_dps_cooldown_ms,
    JSON_EXTRACT(ConfigJSON, '$.priest_echo_spell_power_to_damage_pct') AS priest_echo_spell_power_to_damage_pct,
    JSON_EXTRACT(ConfigJSON, '$.priest_echo_safe_follow_distance') AS priest_echo_safe_follow_distance,
    JSON_EXTRACT(ConfigJSON, '$.priest_echo_safe_min_enemy_distance') AS priest_echo_safe_min_enemy_distance
FROM wm_spell_behavior
WHERE ShellSpellID = 940001
  AND BehaviorKind = 'summon_bonebound_alpha_v3'
  AND Status = 'active';
