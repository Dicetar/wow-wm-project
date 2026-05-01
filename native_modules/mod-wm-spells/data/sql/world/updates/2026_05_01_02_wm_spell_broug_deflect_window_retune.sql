-- Broug Deflect guard window retune.
-- Keep Deflect aura-free; only shorten the native root/invulnerability timing.

SET @wm_broug_deflect_shell_spell_id := 946603;

UPDATE wm_spell_behavior
SET ConfigJSON = JSON_SET(
        COALESCE(ConfigJSON, JSON_OBJECT()),
        '$.parry_pre_ms', 100,
        '$.parry_animation_ms', 450,
        '$.parry_post_ms', 100,
        '$.window_ms', 650
    ),
    UpdatedAt = CURRENT_TIMESTAMP
WHERE ShellSpellID = @wm_broug_deflect_shell_spell_id
  AND BehaviorKind = 'broug_deflect_v1';

SELECT
    'broug_deflect_window_ms' AS metric,
    ShellSpellID AS shell_spell_id,
    JSON_EXTRACT(ConfigJSON, '$.window_ms') AS value
FROM wm_spell_behavior
WHERE ShellSpellID = @wm_broug_deflect_shell_spell_id
  AND BehaviorKind = 'broug_deflect_v1';
