-- Update the proven Bonebound Twins shell to use Gorehowl on both skeletons.
-- Shell 940001 remains the WM-owned carrier; stock carrier rows stay retired.

UPDATE wm_spell_behavior
SET ConfigJSON = JSON_SET(
        ConfigJSON,
        '$.virtual_item_1', 28773,
        '$.omega_virtual_item_1', 28773
    ),
    UpdatedAt = CURRENT_TIMESTAMP
WHERE ShellSpellID = 940001
  AND BehaviorKind = 'summon_bonebound_twin_v2'
  AND Status = 'active';

SELECT
    'bonebound_twins_alpha_weapon' AS metric,
    JSON_EXTRACT(ConfigJSON, '$.virtual_item_1') AS value
FROM wm_spell_behavior
WHERE ShellSpellID = 940001;

SELECT
    'bonebound_twins_omega_weapon' AS metric,
    JSON_EXTRACT(ConfigJSON, '$.omega_virtual_item_1') AS value
FROM wm_spell_behavior
WHERE ShellSpellID = 940001;
