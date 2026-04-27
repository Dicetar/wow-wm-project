-- Use a positive persistent buff marker for Bonebound Echo count.
-- WM strips the spell effects and owns the stack amount; the client only renders the icon + stack number.

UPDATE wm_spell_behavior
SET ConfigJSON = JSON_SET(
    ConfigJSON,
    '$.alpha_echo_count_aura_spell_id', 467,
    '$.alpha_echo_count_aura_refresh_ms', 0
)
WHERE ShellSpellID = 940001
  AND BehaviorKind = 'summon_bonebound_alpha_v3'
  AND Status = 'active';

SELECT
    'bonebound_alpha_echo_counter_aura_config' AS metric,
    JSON_EXTRACT(ConfigJSON, '$.alpha_echo_count_aura_spell_id') AS alpha_echo_count_aura_spell_id,
    JSON_EXTRACT(ConfigJSON, '$.alpha_echo_count_aura_refresh_ms') AS alpha_echo_count_aura_refresh_ms
FROM wm_spell_behavior
WHERE ShellSpellID = 940001
  AND BehaviorKind = 'summon_bonebound_alpha_v3'
  AND Status = 'active';
