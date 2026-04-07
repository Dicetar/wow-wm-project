# Mainline workflow and output rules

This note is the **current working rule** for how this repo should be used day to day.

It exists because the practical workflow for this project is intentionally simpler than a formal branching / PR / rebase process.

## Mainline rule

Default workflow:

```powershell
git checkout main
git pull origin main
```

After the local work is tested and documented:

```powershell
git add .
git commit -m "your commit message"
git push origin main
```

That is the normal path.

No branch / merge / rebase workflow is required for the default WM loop.

---

## If `git pull origin main` complains

Do not start hand-rolling merge/rebase cleanup.

Use the simple recovery path instead:

### Uncommitted local changes

```powershell
git status
git add .
git commit -m "wip"
git pull origin main
```

### Or stash instead of committing

```powershell
git status
git stash
git pull origin main
git stash pop
```

### Local commits not pushed yet

```powershell
git push origin main
git pull origin main
```

The repo should be kept in a straight-line, low-friction workflow.

---

## Low-output rule

The WM project should prefer **concise terminal output**.

Reason:
- large raw blobs of JSON
- verbose test runners
- oversized SQL previews
- unnecessary debug dumps

all make chat logs and working notes harder to use.

So the default rule is:

> print only the information needed to decide the next action

---

## Testing rule

Use the quiet test runner by default:

```powershell
python -m wm.dev.run_quiet_tests
```

Focused test run:

```powershell
python -m wm.dev.run_quiet_tests tests.test_item_pipeline
python -m wm.dev.run_quiet_tests tests.test_quest_drafts
```

Do **not** default to verbose unittest output unless a failure is being investigated.

The quiet runner prints only:

- overall pass/fail
- tests run
- failures
- errors
- skipped
- total duration

---

## WM command output rule

For WM CLI commands, prefer summary-style output and file artifacts over raw stdout blobs.

### Preferred pattern

```powershell
python -m wm.items.publish --demo --mode dry-run --summary
python -m wm.items.publish --demo --mode apply --summary --output-json .\artifacts\item_910000_publish.json
```

### Avoid by default

- raw JSON to terminal when summary is enough
- dumping large SQL plans directly into chat or notes
- verbose debug prints during routine operations

Use `--output-json` when full detail is needed, and keep terminal output short.

---

## Practical day-to-day order

The standard order is:

1. `git checkout main`
2. `git pull origin main`
3. `python -m wm.dev.run_quiet_tests`
4. dry-run the WM command being worked on
5. apply only after dry-run looks sane
6. confirm the smallest live proof
7. update docs if behavior changed
8. `git add .`
9. `git commit -m "..."`
10. `git push origin main`

That is the current intended workflow.

---

## When verbose output is allowed

Verbose output is fine only when:

- diagnosing a failed test
- inspecting a malformed draft
- checking a preflight/schema mismatch
- debugging runtime sync behavior

Even then, prefer:
- targeted verbose output
- one failing command at a time
- file artifact output over giant terminal dumps when possible

---

## Current intent

For this repo, simplicity beats ceremony.

The working defaults are:
- direct work on `main`
- concise output
- dry-run before apply
- docs updated alongside behavior changes
