-- Move Echo Restorers into a closer randomized support ring between the player and Echo Destroyers.

UPDATE wm_spell_behavior
SET ConfigJSON = JSON_SET(
    ConfigJSON,
    '$.priest_echo_safe_follow_distance', 1.8,
    '$.priest_echo_safe_min_enemy_distance', 6.0
)
WHERE ShellSpellID = 940001
  AND BehaviorKind = 'summon_bonebound_alpha_v3'
  AND Status = 'active';

SELECT
    'bonebound_echo_restorer_positioning' AS metric,
    JSON_EXTRACT(ConfigJSON, '$.priest_echo_safe_follow_distance') AS priest_echo_safe_follow_distance,
    JSON_EXTRACT(ConfigJSON, '$.priest_echo_safe_min_enemy_distance') AS priest_echo_safe_min_enemy_distance
FROM wm_spell_behavior
WHERE ShellSpellID = 940001
  AND BehaviorKind = 'summon_bonebound_alpha_v3'
  AND Status = 'active';
