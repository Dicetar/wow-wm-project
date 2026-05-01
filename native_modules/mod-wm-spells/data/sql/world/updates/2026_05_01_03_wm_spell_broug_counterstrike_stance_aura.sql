-- Broug Counterstrike Stance real stance-aura correction.
-- Existing visible shell 946605 stays active, but the DB toggle is no longer the gameplay gate.

SET @wm_broug_deflect_shell_spell_id := 946603;
SET @wm_broug_deflect_counter_stance_shell_spell_id := 946605;
SET @wm_broug_counter_stance_form_id := 13;
SET @wm_broug_counter_stance_bar_order := 1;

UPDATE wm_spell_shell
SET FamilyID = 'self_aura',
    Label = 'Counterstrike Stance',
    State = 'planned',
    ProvenanceJSON = JSON_OBJECT(
        'notes',
        JSON_ARRAY(
            'Fresh stance shell. Client/server DBC apply a real shapeshift-style stance aura on 946605 using form 13 and stance bar order 1.',
            'Native runtime gates the automatic Deflect counterattack on the live 946605 aura; legacy wm_broug_deflect_counter_stance rows are not a gameplay gate.'
        )
    ),
    UpdatedAt = CURRENT_TIMESTAMP
WHERE ShellSpellID = @wm_broug_deflect_counter_stance_shell_spell_id;

UPDATE wm_spell_behavior
SET ConfigJSON = JSON_OBJECT(
        'controls_spell_id', @wm_broug_deflect_shell_spell_id,
        'counterattack_requires_aura', TRUE,
        'stance_aura_spell_id', @wm_broug_deflect_counter_stance_shell_spell_id,
        'stance_form_id', @wm_broug_counter_stance_form_id,
        'stance_bar_order', @wm_broug_counter_stance_bar_order,
        'legacy_state_table', 'wm_broug_deflect_counter_stance'
    ),
    Status = 'active',
    UpdatedAt = CURRENT_TIMESTAMP
WHERE ShellSpellID = @wm_broug_deflect_counter_stance_shell_spell_id
  AND BehaviorKind = 'broug_deflect_counter_stance_v1';

UPDATE wm_spell_behavior
SET ConfigJSON = JSON_SET(
        COALESCE(ConfigJSON, JSON_OBJECT()),
        '$.counterattack_enabled_default', FALSE,
        '$.counterattack_requires_aura_spell_id', @wm_broug_deflect_counter_stance_shell_spell_id
    ),
    UpdatedAt = CURRENT_TIMESTAMP
WHERE ShellSpellID = @wm_broug_deflect_shell_spell_id
  AND BehaviorKind = 'broug_deflect_v1';

INSERT INTO spell_cooldown_overrides
    (Id, RecoveryTime, CategoryRecoveryTime, StartRecoveryTime, StartRecoveryCategory, Comment)
VALUES
    (@wm_broug_deflect_counter_stance_shell_spell_id, 0, 0, 0, 0, 'WM Broug Counterstrike Stance real aura/no-GCD shell')
ON DUPLICATE KEY UPDATE
    RecoveryTime = VALUES(RecoveryTime),
    CategoryRecoveryTime = VALUES(CategoryRecoveryTime),
    StartRecoveryTime = VALUES(StartRecoveryTime),
    StartRecoveryCategory = VALUES(StartRecoveryCategory),
    Comment = VALUES(Comment);

SELECT
    'broug_counterstrike_stance_aura_gate' AS metric,
    b.ShellSpellID AS shell_spell_id,
    JSON_EXTRACT(b.ConfigJSON, '$.counterattack_requires_aura') AS requires_aura,
    JSON_EXTRACT(b.ConfigJSON, '$.stance_form_id') AS stance_form_id
FROM wm_spell_behavior b
WHERE b.ShellSpellID = @wm_broug_deflect_counter_stance_shell_spell_id
  AND b.BehaviorKind = 'broug_deflect_counter_stance_v1';
