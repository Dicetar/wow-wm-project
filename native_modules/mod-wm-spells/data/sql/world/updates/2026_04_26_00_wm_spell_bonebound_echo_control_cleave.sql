-- Add Bonebound Alpha/Echo cleave, Echo hunt/follow control, and Echo-count aura marker defaults.

UPDATE wm_spell_behavior
SET ConfigJSON = JSON_SET(
    ConfigJSON,
    '$.cleave_enabled', true,
    '$.cleave_cooldown_ms', 3000,
    '$.cleave_radius', 8.0,
    '$.cleave_max_targets', 4,
    '$.alpha_cleave_damage_pct', 45,
    '$.echo_cleave_damage_pct', 25,
    '$.alpha_echo_hunt_radius', 35.0
)
WHERE ShellSpellID = 940001
  AND BehaviorKind = 'summon_bonebound_alpha_v3'
  AND Status = 'active';

SELECT
    'bonebound_alpha_echo_control_cleave_config' AS metric,
    JSON_EXTRACT(ConfigJSON, '$.cleave_enabled') AS cleave_enabled,
    JSON_EXTRACT(ConfigJSON, '$.cleave_cooldown_ms') AS cleave_cooldown_ms,
    JSON_EXTRACT(ConfigJSON, '$.cleave_radius') AS cleave_radius,
    JSON_EXTRACT(ConfigJSON, '$.alpha_cleave_damage_pct') AS alpha_cleave_damage_pct,
    JSON_EXTRACT(ConfigJSON, '$.echo_cleave_damage_pct') AS echo_cleave_damage_pct,
    JSON_EXTRACT(ConfigJSON, '$.alpha_echo_hunt_radius') AS alpha_echo_hunt_radius
FROM wm_spell_behavior
WHERE ShellSpellID = 940001
  AND BehaviorKind = 'summon_bonebound_alpha_v3'
  AND Status = 'active';
