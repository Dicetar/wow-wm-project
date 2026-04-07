# Development Workflow

This note defines the **default engineering workflow** for working on the WM repo.

The WM is not a pure library project.
Every meaningful change has two sides:

1. repository correctness
2. live AzerothCore operational safety

So a change is not finished when the Python code looks clean.
A change is finished when:

- unit/smoke checks pass
- dry-run output is sane
- apply flow is deliberate
- rollback path is known in advance
- the repo docs match the new behavior

---

## 1. Pull latest before starting

Start every work session by updating the local checkout.

### Windows PowerShell

```powershell
git checkout main
git pull --ff-only origin main
```

### Optional feature branch

```powershell
git checkout -b feat/item-slot-pipeline-v1
```

Use a feature branch when the change touches multiple files or introduces a new live pipeline slice.

---

## 2. Activate the Python environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
```

The project currently has no external runtime dependencies in `pyproject.toml`, so editable install should stay simple. Keep using the project venv anyway so command behavior stays stable. See `pyproject.toml` for the current package baseline.

---

## 3. Verify `.env` before any live work

Before running live DB commands, confirm the environment matches the real local server.

At minimum check:

- `WM_WORLD_DB_HOST`
- `WM_WORLD_DB_PORT`
- `WM_WORLD_DB_NAME`
- `WM_WORLD_DB_USER`
- `WM_WORLD_DB_PASSWORD`
- `WM_MYSQL_BIN_PATH` if `mysql` is not already on `PATH`
- SOAP settings if runtime sync will be used

Do **not** assume defaults are correct for your current machine.

---

## 4. Run repo-side tests first

Run the Python test suite before touching the live DB.

### All tests

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
```

### Focused tests while iterating

```powershell
python -m unittest tests.test_quest_drafts -v
python -m unittest tests.test_item_pipeline -v
```

If a new slice has no tests yet, add at least a smoke-level test for:

- validation
- plan compilation
- JSON draft load

No new live pipeline should land with zero repo-side test coverage.

---

## 5. Use dry-run before apply

The default WM rule is:

> dry-run first, inspect output, then apply.

Never jump straight to `--mode apply` on a new code path.

### Quest workflow example

```powershell
python -m wm.quests.generate_bounty --questgiver-name "Marshal McBride" --target-name "Kobold Vermin" --quest-id 910005 --summary
python -m wm.quests.live_publish --draft-json .\artifacts\generated_bounty.json --mode dry-run --runtime-sync off --summary
```

Inspect:

- validation result
- preflight issues
- generated SQL plan
- reserved slot warnings
- runtime expectations

Only then do:

```powershell
python -m wm.quests.live_publish --draft-json .\artifacts\generated_bounty.json --mode apply --runtime-sync auto --summary
```

### Item workflow example

```powershell
python -m wm.reserved.seed --entity-type item --start-id 910000 --end-id 910099 --mode apply --summary
python -m wm.items.publish --demo --mode dry-run --summary
```

Inspect:

- base item row exists
- item slot preflight is clean enough
- stat/spell slot compatibility checks are sane
- final row preview looks reasonable

Only then do:

```powershell
python -m wm.items.publish --demo --mode apply --summary --output-json .\artifacts\item_910000_publish.json
```

---

## 6. Define rollback before apply

Before every new live test, know the reversal path.

### For quests

Use the built-in rollback command:

```powershell
python -m wm.quests.rollback --quest-id 910005 --mode apply --runtime-sync auto --summary
```

If the runtime/client state still looks stale after rollback, use the cleanup ladder documented in:

- `docs/CLEANUP_PLAYBOOK.md`

### For items

Item Slot Pipeline V1 stores rollback snapshots and publish logs, but a dedicated `wm.items.rollback` command does **not** exist yet.

So before item apply tests, explicitly note:

- which `item_entry` you are changing
- which `base_item_entry` you cloned from
- whether the item slot already existed
- whether a worldserver restart may be needed after reverting manually

Until item rollback command support exists, treat item apply tests as controlled/manual operations.

---

## 7. Live test in the smallest safe loop

After an apply, do the smallest proof that the slice actually works.

### Quest slice

Minimum proof:

- quest is present in DB
- questgiver offers or updates correctly
- objective text is correct
- reward fields are correct
- rollback restores the previous state

### Item slice

Minimum proof:

- item row exists in DB
- item name/description/stats look correct
- quest reward points to the correct item entry
- item can be obtained by the quest path being tested
- stale runtime/client behavior is documented if observed

The point of live testing is not “play for an hour.”
The point is to prove the slice’s contract.

---

## 8. Update docs in the same change set

Any new live pipeline or operational rule should update docs immediately.

At minimum, check whether the change should update:

- `README.md`
- `docs/ROADMAP.md`
- feature doc for the new slice
- cleanup / operational playbook
- transcript/archive notes if this is a major milestone

A working code path with stale docs is not a finished WM change.

---

## 9. Commit workflow

A good WM commit should be small enough to explain in one sentence.

Examples:

- `feat: add managed item publish pipeline`
- `docs: add development workflow note`
- `test: add item pipeline smoke tests`
- `fix: harden item preflight compatibility checks`

Before committing, run:

```powershell
git status
python -m unittest discover -s tests -p "test_*.py" -v
```

Then commit:

```powershell
git add .
git commit -m "feat: add managed item publish pipeline"
```

---

## 10. Push / PR workflow

If you are using a feature branch:

```powershell
git push -u origin feat/item-slot-pipeline-v1
```

Then open a PR.

A good PR description should include:

- what new capability was added
- what live safety boundary exists
- what commands were used for dry-run / apply
- what was tested only at repo level vs. what was tested live
- what is still intentionally missing

Suggested structure:

```text
Summary
- adds managed item slot publish pipeline

Repo-side checks
- unittest suite run
- item validator/compiler smoke tests added

Live workflow tested
- reserved item slot seeded
- dry-run publish inspected
- apply path executed against local server
- quest reward pointed to managed item entry

Known limits
- no dedicated wm.items.rollback command yet
- runtime reload remains server/module-specific
```

---

## 11. Definition of done for a WM pipeline change

A new pipeline slice is only done when all of these are true:

- repo tests pass
- dry-run output is inspectable and useful
- apply mode is explicit and bounded
- preflight catches the most obvious unsafe states
- publish logging exists
- rollback path exists or is clearly documented as missing
- live test steps are written down
- docs are updated in the same change set

If any of those are missing, the slice is still in progress.

---

## 12. Current recommended order for real work

For the current repo state, the safest order is:

1. unit tests
2. dry-run
3. apply
4. minimal live proof
5. rollback / cleanup check
6. docs update
7. commit
8. push / PR

That order is the default unless a very specific task justifies deviating from it.
