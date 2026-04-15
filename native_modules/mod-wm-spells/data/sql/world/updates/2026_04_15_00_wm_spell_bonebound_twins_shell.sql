-- Keep Bonebound Twins on the WM-owned shell path.
-- Retire stock carrier script bindings that were useful only during the failed prototype pass.

UPDATE wm_spell_shell
SET State = 'retired',
    UpdatedAt = CURRENT_TIMESTAMP
WHERE ShellSpellID IN (49126);

UPDATE wm_spell_behavior
SET Status = 'disabled',
    UpdatedAt = CURRENT_TIMESTAMP
WHERE ShellSpellID IN (49126);

DELETE FROM spell_script_names
WHERE spell_id IN (688, 691, 697, 712, 8853, 30146, 49126, 57913)
  AND ScriptName IN ('spell_wm_twin_skeleton_shell', 'spell_wm_skeletal_pet_shell', 'spell_wm_shell_dispatch');

INSERT INTO wm_spell_shell (ShellSpellID, ShellKey, FamilyID, Label, State, ClientPatchVersion, OwnershipKey, ProvenanceJSON) VALUES
(940001, 'bonebound_twins_v1', 'summon_pet', 'Bonebound Twins', 'planned', 'wm_spell_shell_bank.v1', 'wm.spell_shell:bonebound_twins_v1', '{"notes":["WM-owned shell. Do not replace Summon Voidwalker, Raise Ghoul, or any other stock spell carrier."]}')
ON DUPLICATE KEY UPDATE
    ShellKey = VALUES(ShellKey),
    FamilyID = VALUES(FamilyID),
    Label = VALUES(Label),
    State = VALUES(State),
    ClientPatchVersion = VALUES(ClientPatchVersion),
    OwnershipKey = VALUES(OwnershipKey),
    ProvenanceJSON = VALUES(ProvenanceJSON),
    UpdatedAt = CURRENT_TIMESTAMP;

INSERT INTO wm_spell_behavior (ShellSpellID, BehaviorKind, ConfigJSON, Status) VALUES
(940001, 'summon_bonebound_twin_v2', '{"creature_entry":1860,"display_id":734,"name":"Bonebound Alpha","require_corpse":false,"persist_pet":true,"spawn_omega":true,"preserve_base_stats":true,"owner_intellect_to_all_stats":true,"owner_intellect_to_all_stats_scale":1.0,"owner_shadow_power_to_attack_power":true,"owner_shadow_power_to_attack_power_scale":1.0,"virtual_item_1":1897,"virtual_item_2":0,"virtual_item_3":0,"omega_creature_entry":1860,"omega_name":"Bonebound Omega","omega_display_id":734,"omega_virtual_item_1":1897,"omega_virtual_item_2":0,"omega_virtual_item_3":0,"omega_follow_distance":2.2,"omega_follow_angle":-1.5708,"omega_scale_multiplier":1.0,"omega_health_pct":100,"omega_damage_pct":100}', 'active')
ON DUPLICATE KEY UPDATE
    BehaviorKind = VALUES(BehaviorKind),
    ConfigJSON = VALUES(ConfigJSON),
    Status = VALUES(Status),
    UpdatedAt = CURRENT_TIMESTAMP;

DELETE FROM spell_script_names WHERE spell_id IN (940001) AND ScriptName = 'spell_wm_shell_dispatch';
INSERT INTO spell_script_names (spell_id, ScriptName) VALUES
(940001, 'spell_wm_shell_dispatch');
