-- Restorer ranged seek support and 100-yard Mind Blast filler range.

UPDATE wm_spell_behavior
SET ConfigJSON = JSON_SET(
    ConfigJSON,
    '$.priest_echo_dps_max_range', 100.0
)
WHERE ShellSpellID = 940001
  AND BehaviorKind = 'summon_bonebound_alpha_v3'
  AND Status = 'active';

SELECT
    'bonebound_restorer_seek_teleport_range' AS metric,
    JSON_EXTRACT(ConfigJSON, '$.priest_echo_dps_spell_id') AS priest_echo_dps_spell_id,
    JSON_EXTRACT(ConfigJSON, '$.priest_echo_dps_damage_spell_id') AS priest_echo_dps_damage_spell_id,
    JSON_EXTRACT(ConfigJSON, '$.priest_echo_dps_max_range') AS priest_echo_dps_max_range
FROM wm_spell_behavior
WHERE ShellSpellID = 940001
  AND BehaviorKind = 'summon_bonebound_alpha_v3'
  AND Status = 'active';
