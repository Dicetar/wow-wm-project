# Quest Publish Plan V1

## What this slice does

This adds the first real **publish wrapper** around the quest draft pipeline.

It does four things:

1. loads a saved quest draft JSON
2. runs DB-aware preflight checks
3. captures a rollback preview from the live world DB
4. supports `dry-run` and `apply` modes

## Module

- `src/wm/quests/publish.py`

## What preflight checks now verify

- required world tables exist:
  - `quest_template`
  - `creature_queststarter`
  - `creature_questender`
  - `creature_template`
  - `wm_publish_log`
  - `wm_rollback_snapshot`
- required `quest_template` columns exist on your actual DB
- quest giver entry exists in `creature_template`
- target entry exists in `creature_template`
- whether the quest ID already exists
- optional `wm_reserved_slot` state for the quest ID

## What apply mode now does

If validation and preflight both pass:

- inserts a `started` row into `wm_publish_log`
- inserts a rollback snapshot into `wm_rollback_snapshot`
- executes the staged quest SQL plan
- inserts a `success` row into `wm_publish_log`
- marks the reserved quest slot `active` if that table and row exist

If execution fails:

- it attempts to write a `failed` row into `wm_publish_log`

## Important limitation

This is still **Publish Plan V1**, not the final publish system.

Current limitations:

- rollback execution is not implemented yet; only snapshot capture is implemented
- no transaction wrapper is used yet
- the quest compiler still assumes the current AzerothCore-style `quest_template` columns used by the draft layer
- reserved slot tracking is optional for now, not hard-enforced

## Recommended local workflow

### 1. Dry-run with built-in demo draft

```powershell
cd D:\WOW\wm-project
.\.venv\Scripts\Activate.ps1
python -m wm.quests.publish --demo --mode dry-run
```

### 2. Save a draft JSON from another tool or from the demo output

Then run:

```powershell
python -m wm.quests.publish --draft-json .\your_draft.json --mode dry-run
```

### 3. Only after dry-run looks good, apply it

```powershell
python -m wm.quests.publish --draft-json .\your_draft.json --mode apply
```

## What a good dry-run should show

- `validation.ok = true`
- `preflight.ok = true`
- `snapshot_preview` present
- `sql_plan.statements` present
- `applied = false`

## Next target after this

The next most useful implementation is:

**Quest Rollback V1**

That should:

- fetch the latest `wm_rollback_snapshot` for a quest
- rebuild restore SQL from that snapshot
- support dry-run and apply rollback modes
- mark publish / rollback actions clearly in `wm_publish_log`
