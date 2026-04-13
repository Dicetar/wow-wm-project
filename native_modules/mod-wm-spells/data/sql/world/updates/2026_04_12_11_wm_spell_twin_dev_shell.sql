INSERT INTO wm_spell_shell (ShellSpellID, ShellKey, FamilyID, Label, State, ClientPatchVersion, OwnershipKey, ProvenanceJSON) VALUES
(49126, 'bonebound_twins_dev_raise_ghoul', 'summon_pet', 'Bonebound Twins (Dev Shell)', 'lab_only', 'wm_spell_shell_bank.v1', 'wm.dev_shell:bonebound_twins_dev_raise_ghoul', '{"notes":["temporary visible dev shell backed by stock client spell id 49126"]}')
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
(49126, 'summon_bonebound_twin_v2', '{"creature_entry":1860,"display_id":734,"name":"Bonebound Alpha","require_corpse":false,"persist_pet":true,"spawn_omega":true,"preserve_base_stats":true,"owner_intellect_to_all_stats":true,"owner_shadow_power_to_attack_power":true,"virtual_item_1":1897,"virtual_item_2":0,"virtual_item_3":0,"omega_creature_entry":1860,"omega_name":"Bonebound Omega","omega_display_id":734,"omega_virtual_item_1":1897,"omega_virtual_item_2":0,"omega_virtual_item_3":0,"omega_follow_distance":2.2,"omega_follow_angle":-1.5708,"omega_scale_multiplier":1.0,"omega_health_pct":100,"omega_damage_pct":100}', 'active'),
(940001, 'summon_bonebound_twin_v2', '{"creature_entry":1860,"display_id":734,"name":"Bonebound Alpha","require_corpse":false,"persist_pet":true,"spawn_omega":true,"preserve_base_stats":true,"owner_intellect_to_all_stats":true,"owner_shadow_power_to_attack_power":true,"virtual_item_1":1897,"virtual_item_2":0,"virtual_item_3":0,"omega_creature_entry":1860,"omega_name":"Bonebound Omega","omega_display_id":734,"omega_virtual_item_1":1897,"omega_virtual_item_2":0,"omega_virtual_item_3":0,"omega_follow_distance":2.2,"omega_follow_angle":-1.5708,"omega_scale_multiplier":1.0,"omega_health_pct":100,"omega_damage_pct":100}', 'planned')
ON DUPLICATE KEY UPDATE
    BehaviorKind = VALUES(BehaviorKind),
    ConfigJSON = VALUES(ConfigJSON),
    Status = VALUES(Status),
    UpdatedAt = CURRENT_TIMESTAMP;

DELETE FROM spell_script_names WHERE spell_id IN (49126);
INSERT INTO spell_script_names (spell_id, ScriptName) VALUES
(49126, 'spell_wm_shell_dispatch');
