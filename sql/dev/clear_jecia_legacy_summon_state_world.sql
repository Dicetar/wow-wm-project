-- Lab-only cleanup for legacy stock-carrier mappings used by the broken WM summon prototype.
-- Scope is intentionally narrow to the old stock carrier spell IDs.

DELETE FROM spell_script_names
WHERE spell_id IN (697, 8853, 57913, 49126)
  AND ScriptName LIKE 'spell_wm_%';

SELECT 'legacy_spell_script_rows_remaining' AS metric, COUNT(*) AS value
FROM spell_script_names
WHERE spell_id IN (697, 8853, 57913, 49126)
  AND ScriptName LIKE 'spell_wm_%';
