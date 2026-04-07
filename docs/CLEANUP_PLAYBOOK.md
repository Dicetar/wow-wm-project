# Cleanup Playbook

Use this note when WM-generated quest IDs need to be restored or wiped clean.

## Three different operations

### Rollback

Use `wm.quests.rollback` when you want to restore the **latest stored snapshot** for a quest ID.

This is appropriate when:
- a publish or live edit went wrong
- you want the quest slot returned to its last known snapped state

Important:
- rollback does **not** mean "make the slot empty"
- if the latest snapshot already contained a WM quest, rollback can restore that quest

### Purge

Use a hard purge when you want a **truly empty clean slate** for a WM test range.

A purge should:
- delete rows from `creature_queststarter`
- delete rows from `creature_questender`
- delete rows from `quest_offer_reward`
- delete rows from `quest_request_items`
- delete rows from `quest_template`
- reset matching `wm_reserved_slot` rows back to `free`

Use purge when:
- dummy/test quests have piled up
- you want to fully clear a range like `910001-910006`
- rollback would restore old WM content you no longer want

### Runtime / client cleanup

After rollback or purge, runtime state can still look stale.

Use this ladder:
1. send quest-related reload commands over SOAP
2. inspect DB relations if something still looks wrong
3. relog
4. restart worldserver only if needed

---

## Recommended cleanup ladder

### If you want to undo the latest change

1. run `wm.quests.rollback`
2. runtime sync / reload
3. relog if the client still looks stale

### If you want a range to become empty again

1. run a hard purge for the quest range
2. reset the same IDs in `wm_reserved_slot` to `free`
3. runtime sync / reload
4. relog
5. restart worldserver only if the state is still stale

---

## PowerShell lessons learned

When running cleanup from PowerShell:

- `< file.sql` is cmd-style redirection, not the reliable PowerShell path here
- `.env` values are available to Python, but not automatically exported to PowerShell `$env:` vars
- `$Host` is a built-in read-only PowerShell variable, so do not use `$host` as your DB host variable name

Reliable pattern:
- read DB config through `Settings.from_env()` using Python
- assign safe PowerShell variable names like `$dbHost`, `$dbPort`, `$dbUser`
- load SQL with `Get-Content -Raw`
- pass the full SQL string via mysql `--execute`

---

## DB inspection queries that helped

To distinguish a real leftover quest relation from stale presentation, inspect:

- `creature_queststarter WHERE id = <questgiver>`
- `creature_questender WHERE id = <questgiver>`
- `quest_template WHERE ID BETWEEN <range>`

If the DB shows no remaining quest rows / relations and the quest marker still appears, the issue is probably stale runtime or client state rather than leftover WM content.

---

## Practical rule for WM dummy ranges

For WM test ranges such as `910001-910006`:

- use them for experiments
- purge them when done
- free the matching reserved slots
- start fresh from one clean quest instead of stacking leftovers

That keeps the publish / edit / rollback lifecycle understandable and prevents confusing half-clean states.
