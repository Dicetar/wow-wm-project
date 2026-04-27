-- Retune Echo Restorer filler into a lower-damage Bone Spike cast.
-- 69057 itself has a Marrowgar encounter SpellScript; runtime uses script-free 73142 for the same client visual
-- and logs the damage against 69057 after the configured cast window.

UPDATE wm_spell_behavior
SET ConfigJSON = JSON_SET(
    ConfigJSON,
    '$.priest_echo_dps_spell_id', 73142,
    '$.priest_echo_dps_damage_spell_id', 69057,
    '$.priest_echo_dps_cast_time_ms', 1500,
    '$.priest_echo_dps_damage_pct', 9,
    '$.priest_echo_dps_cooldown_ms', 2500,
    '$.priest_echo_spell_power_to_damage_pct', 11
)
WHERE ShellSpellID = 940001
  AND BehaviorKind = 'summon_bonebound_alpha_v3'
  AND Status = 'active';

SELECT
    'bonebound_echo_restorer_bone_spike_retune' AS metric,
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
