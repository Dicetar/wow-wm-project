-- Move Bonebound Alpha behavior config from legacy shadow_dot names to visible bleed names.
-- Runtime still accepts shadow_dot_* for backward compatibility.

UPDATE wm_spell_behavior
SET ConfigJSON = REPLACE(
    REPLACE(
    REPLACE(
    REPLACE(
    REPLACE(
    REPLACE(
    REPLACE(
    REPLACE(
        ConfigJSON,
        '"shadow_dot_enabled"', '"bleed_enabled"'),
        '"shadow_dot_cooldown_ms"', '"bleed_cooldown_ms"'),
        '"shadow_dot_duration_ms"', '"bleed_duration_ms"'),
        '"shadow_dot_tick_ms"', '"bleed_tick_ms"'),
        '"shadow_dot_base_damage"', '"bleed_base_damage"'),
        '"shadow_dot_damage_per_level_pct"', '"bleed_damage_per_level_pct"'),
        '"shadow_dot_damage_per_intellect_pct"', '"bleed_damage_per_intellect_pct"'),
        '"shadow_dot_damage_per_shadow_power_pct"', '"bleed_damage_per_shadow_power_pct"')
WHERE ShellSpellID = 940001
  AND BehaviorKind = 'summon_bonebound_alpha_v3'
  AND ConfigJSON LIKE '%shadow_dot_%';

SELECT
    'bonebound_alpha_visible_bleed_aura_spell' AS metric,
    772 AS value;

SELECT
    'bonebound_alpha_bleed_config' AS metric,
    JSON_EXTRACT(ConfigJSON, '$.bleed_cooldown_ms') AS cooldown_ms,
    JSON_EXTRACT(ConfigJSON, '$.bleed_duration_ms') AS duration_ms,
    JSON_EXTRACT(ConfigJSON, '$.bleed_tick_ms') AS tick_ms
FROM wm_spell_behavior
WHERE ShellSpellID = 940001
  AND BehaviorKind = 'summon_bonebound_alpha_v3'
  AND Status = 'active';
