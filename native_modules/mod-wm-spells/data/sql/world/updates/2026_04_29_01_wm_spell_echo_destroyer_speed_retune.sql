-- Let melee Echo Destroyers catch and engage before ranged Restorers dominate the opener.
-- Runtime clamps the multiplier defensively; this value scales from Bonebound Alpha's current movement rates.

UPDATE wm_spell_behavior
SET ConfigJSON = JSON_SET(
    ConfigJSON,
    '$.alpha_echo_movement_speed_multiplier', 1.75
)
WHERE ShellSpellID = 940001
  AND BehaviorKind = 'summon_bonebound_alpha_v3'
  AND Status = 'active';

SELECT
    'bonebound_echo_destroyer_speed_retune' AS metric,
    JSON_EXTRACT(ConfigJSON, '$.alpha_echo_movement_speed_multiplier') AS alpha_echo_movement_speed_multiplier,
    JSON_EXTRACT(ConfigJSON, '$.priest_echo_movement_speed_multiplier') AS priest_echo_movement_speed_multiplier
FROM wm_spell_behavior
WHERE ShellSpellID = 940001
  AND BehaviorKind = 'summon_bonebound_alpha_v3'
  AND Status = 'active';
