-- Retune Echo Restorer filler to visible Mind Blast with stronger owner shadow spellpower scaling.
-- The runtime treats matching visual/damage spell IDs as one native spell hit with WM-calculated base damage.

UPDATE wm_spell_behavior
SET ConfigJSON = JSON_SET(
    ConfigJSON,
    '$.priest_echo_dps_spell_id', 8092,
    '$.priest_echo_dps_damage_spell_id', 8092,
    '$.priest_echo_dps_cast_time_ms', 1500,
    '$.priest_echo_dps_damage_pct', 19,
    '$.priest_echo_dps_cooldown_ms', 2500,
    '$.priest_echo_spell_power_to_damage_pct', 45
)
WHERE ShellSpellID = 940001
  AND BehaviorKind = 'summon_bonebound_alpha_v3'
  AND Status = 'active';

SELECT
    'bonebound_echo_restorer_mind_blast_retune' AS metric,
    JSON_EXTRACT(ConfigJSON, '$.priest_echo_dps_spell_id') AS priest_echo_dps_spell_id,
    JSON_EXTRACT(ConfigJSON, '$.priest_echo_dps_damage_spell_id') AS priest_echo_dps_damage_spell_id,
    JSON_EXTRACT(ConfigJSON, '$.priest_echo_dps_cast_time_ms') AS priest_echo_dps_cast_time_ms,
    JSON_EXTRACT(ConfigJSON, '$.priest_echo_dps_damage_pct') AS priest_echo_dps_damage_pct,
    JSON_EXTRACT(ConfigJSON, '$.priest_echo_dps_cooldown_ms') AS priest_echo_dps_cooldown_ms,
    JSON_EXTRACT(ConfigJSON, '$.priest_echo_spell_power_to_damage_pct') AS priest_echo_spell_power_to_damage_pct
FROM wm_spell_behavior
WHERE ShellSpellID = 940001
  AND BehaviorKind = 'summon_bonebound_alpha_v3'
  AND Status = 'active';
