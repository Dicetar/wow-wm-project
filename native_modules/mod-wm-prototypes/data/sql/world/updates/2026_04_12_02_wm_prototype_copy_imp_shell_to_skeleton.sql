DELETE FROM `spell_script_names`
WHERE `spell_id` IN (8853, 57913, 49126)
  AND `ScriptName` = 'spell_wm_skeletal_pet_shell';

INSERT INTO `spell_script_names` (`spell_id`, `ScriptName`) VALUES
(8853, 'spell_wm_skeletal_pet_shell'),
(57913, 'spell_wm_skeletal_pet_shell'),
(49126, 'spell_wm_skeletal_pet_shell');
