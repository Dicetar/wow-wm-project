-- Retune Bonebound Alpha/Echo bleed to scale primarily from melee attack power.
-- Shadow spell power still matters through owner_shadow_power_to_attack_power.

UPDATE wm_spell_behavior
SET ConfigJSON = JSON_SET(
    ConfigJSON,
    '$.bleed_base_damage', 3,
    '$.bleed_damage_per_attack_power_pct', 20,
    '$.bleed_damage_per_level_pct', 0,
    '$.bleed_damage_per_intellect_pct', 0,
    '$.bleed_damage_per_shadow_power_pct', 0
)
WHERE ShellSpellID = 940001
  AND BehaviorKind = 'summon_bonebound_alpha_v3'
  AND Status = 'active';

SELECT
    'bonebound_alpha_bleed_attack_power_config' AS metric,
    JSON_EXTRACT(ConfigJSON, '$.bleed_damage_per_attack_power_pct') AS attack_power_pct,
    JSON_EXTRACT(ConfigJSON, '$.bleed_damage_per_level_pct') AS level_pct,
    JSON_EXTRACT(ConfigJSON, '$.bleed_damage_per_intellect_pct') AS intellect_pct,
    JSON_EXTRACT(ConfigJSON, '$.bleed_damage_per_shadow_power_pct') AS shadow_power_pct
FROM wm_spell_behavior
WHERE ShellSpellID = 940001
  AND BehaviorKind = 'summon_bonebound_alpha_v3'
  AND Status = 'active';
