Status: HANDOFF
Last verified: 2026-05-18
Verified by: Claude
Doc type: handoff

# WM Session Handoff — Integration Into D:\WOW

Paste the block below into a fresh chat. It is self-contained.

---

## ROLE / CONTEXT

You are continuing work on **WM (World Master)**, an external-first per-character
progression engine for AzerothCore 3.3.5a (Python brain + typed native C++ body +
locked `control/` contracts). A prior chat produced 16 commits on a worktree branch.
Your job is to **safely integrate that work into `D:\WOW\wm-project`** after
reconciling a discovered collision. Honor the project's non-negotiables: no freeform
SQL/GM/shell/LLM mutation lane; native verbs proven in BridgeLab before status moves
off `not_implemented`; never reuse dirty visible IDs; current-state docs outrank
design notes; do not fabricate live/gameplay proof.

## REPO / FOLDER REALITY (verified 2026-05-18)

- Origin: `https://github.com/Dicetar/wow-wm-project.git`. Shared root `79911e9`.
- **Worktree (prior chat's work):** `D:\Projects\wow-wm-project\.claude\worktrees\lucid-curran-3c5f91`,
  branch `claude/lucid-curran-3c5f91`, HEAD `ab9b450`, **16 commits, 695 tests green**,
  branched from `c396ada`. Its `.git` is `D:\Projects\wow-wm-project\.git`.
- **Canonical clone:** `D:\WOW\wm-project`, branch `main`, HEAD `64afd3f`
  ("Stabilize WM control panel and LLM workbench"), **clean working tree**,
  `[ahead 1]` of `origin/main` which is still `c396ada`. So `64afd3f` is a
  **local-only, unpushed, 4744-line operator commit**. The old "dirty as hell"
  handoff warning is STALE — it is clean now.
- `D:\WOW` is now in scope: `WM_BridgeLab\` (isolated native lab, MySQL
  127.0.0.1:33307, player 5406/Jecia, promotion-gated), `Azerothcore_WoTLK_Rebuild\`,
  `Azerothcore_WoTLK_Repack\` (its `mysql\bin\mysql.exe` is what `wm doctor` finds),
  db_export bundles, transcripts, roadmap drafts.

## THE COLLISION (must reconcile before landing)

Operator commit `64afd3f` independently built the SAME subsystems as the prior chat:

- Theirs: `src/wm/panel/` (PACKAGE: server.py, jobs.py, schemas.py, state.py,
  catalog.py, static app.js/index.html/style.css), `src/wm/llm/{lmstudio,prompts,
  results,__init__}.py`, `tests/panel/*`, `src/wm/content/release.py` (+107),
  `pytest.ini`, `tests/conftest.py`, `scripts/{cleanup_workspace,validate_agent_skills,
  Repair-GitAcl}`.
- Prior chat's: `src/wm/panel.py` (MODULE — hard conflict, same `wm.panel` import),
  `src/wm/webpanel.py`, `src/wm/llm/{client,smoke,__init__}.py` (`__init__.py`
  conflicts), `tests/test_{panel,webpanel,llm_client,living_catalog}.py`.
- `src/wm/panel.py` (file) vs `src/wm/panel/` (dir) CANNOT coexist.

**OPEN DECISION (operator must choose):** recommended = **theirs wins** (their
package server+static UI+jobs+schemas is richer and is the operator's chosen
direction); drop the prior chat's `panel.py`/`webpanel.py`/`llm/client.py`/
`llm/smoke.py`; re-wire the prior chat's unique value (Living World Catalog,
`doctor`, status-as-data) onto THEIR panel. Alternatives: mine-wins (not
recommended, discards 4744 lines), or keep-both-namespaced.

## ADDITIVE, NON-COLLIDING (≈90% — `64afd3f` never touches these; land cleanly)

- `src/wm/living/` — Living World Memory layer: `nemesis, rumor, legend, patron,
  oath` scaffolds + `journal_trigger` + `catalog` (Wild Feature Catalog, ADR-0005),
  all dry-run, contract-validated, `live_ready` honest.
- `src/wm/journal/projector.py` + `project.py` + `sql/bootstrap/wm_zone_rollup.sql`
  (Journal V2 write side).
- `src/wm/sources/native_bridge/payload_contract.py` + `contracts_cli.py` +
  expanded `control/actions/native/native_bridge_action.json` (57/99 contracts
  enforced pre-flight) + `docs/NATIVE_CAPABILITY_EXPANSION_V1.md` (batched C++ plan).
- `src/wm/doctor.py`, `src/wm/status/` + `data/specs/feature_status.json`.
- Track-1 cleanup (deleted candidates/prompt `_v2/_v3` copy-chain) + `src/wm/cli.py`
  unified `wm` entrypoint.
- `docs/adr/0004` (compiler-is-shipped-artifact), `docs/adr/0005` (wild catalog),
  `docs/FULL_LOOP_PROOF_RUNBOOK.md`, `tests/test_arc_compiler_contract.py`.
- `.github/workflows/ci.yml` (first CI; DB-free suite + lints).
- Note: prior chat also edited `src/wm/cli.py` and `data/specs/feature_status.json`
  and `README.md`/`docs/ROADMAP.md` — minor, may need trivial merge with `64afd3f`'s
  doc +3-line edits.

## 16 COMMITS ON THE BRANCH (oldest→newest)

e4ba999 Track1 collapse copy-versioned + unified wm CLI; (doc consolidation);
99c9d8c ADR-0004 + full-loop runbook; 26d9936 compiler reward-panel contract test;
aa08c48 wm doctor; f06f41d LLM smoke (COLLIDES); 2d4ac0b wm panel (COLLIDES);
2e74c90 native payload contracts enforced+expanded; 8993d51 Nemesis scaffold;
2317fc4 Rumor/Legend/Patron/Oath scaffolds; 9c36cfd journal_trigger wiring;
9315a40 status-as-data + CI; f97e6ce Journal V2 projector;
2d81022 webpanel GUI (COLLIDES); ab9b450 Wild Feature Catalog ADR-0005.

## SESSION INTENT TRAIL (the operator's prompts, in order)

1. Analyze + critically evaluate the project; plan improvement/refactor/dev.
2. Track 1 debt paydown: collapse copy-versioned files, unify CLI, consolidate docs. Commit.
3. Deep critical assessment — what's ready vs needs improvement; read all goal docs.
4. Make plans for everything, ordered most→least important; begin high-priority.
5. Skip what needs the live lab; self-pick next codeable tasks from goals.
6. /system-design+/architecture+brainstorm: scan logs/docs for unimplemented
   features, invent fitting ones, build a grand plan + prep for release. Make it bigger.
7. Loaded local LLM (qwen3.5-9b @ 127.0.0.1:1234) for testing.
8. LLM later; build control-panel UX/features now.
9. Commit; keep picking next tasks until all finished, don't stop.
10. Make a nice GUI control panel surfacing all features.
11. /architecture: check repo for "wild ideas" and implement all needed.
12. D:\WOW is now part of the project — integrate all prior work into it; recheck, architect.
13. Compile all my prompts into one big handoff prompt for a new chat with the
    folders set up. (← this document)

## ARCHITECTURE PRINCIPLES TO KEEP

Python decides/validates/audits; native senses+executes typed actions; `control/`
is the shared manual/LLM contract lane; LLM advisory only and apply-gated; every
wild feature = trigger→Python→typed native/shell→client tier and must be
player-perceivable; reuse existing bus/factory/allocator/coordinator (ADR-0002);
no broad god-module splits before behavior is locked + live-proven.

## YOUR TASK

1. Confirm the panel/LLM reconciliation decision with the operator (recommended:
   theirs wins, port prior chat's Living World Catalog + doctor + status-as-data
   onto their `src/wm/panel/`).
2. Push `claude/lucid-curran-3c5f91` to origin (it is unpushed; prior chat's clone
   can push). In `D:\WOW\wm-project`, create an integration branch off `64afd3f`,
   land the additive 90% (cherry-pick/merge non-colliding commits), reconcile
   panel/LLM per the decision, drop the prior chat's superseded panel/llm files.
3. Do NOT reset/clobber `64afd3f`; it is unpushed operator work. Do NOT mutate
   `WM_BridgeLab` (promotion-gated). Do NOT push to origin/main without operator OK.
4. Reconcile trivial doc/cli/feature_status overlaps. `python -m pytest -q` must
   stay green. Run `wm doctor`, `wm status --validate`, `wm living.catalog
   --validate --dry-run-all`, `wm native.contracts` after integration.
5. Write `docs/adr/0006-...` recording the collision + chosen reconciliation, and
   update `WM_PLATFORM_HANDOFF.md` / `feature_status.json` to current truth.

Live/gameplay proof (bounty full loop, Batch 1-6 C++, arc compiler in-client) stays
operator-gated per `docs/FULL_LOOP_PROOF_RUNBOOK.md` — do not claim it done.
