Status: PARTIAL
Last verified: 2026-05-24
Verified by: Claude
Doc type: handoff

# Handoff — project track + what to develop next (2026-05-24)

Read the current-state chain first (`wm-workflow` mandates it): `AGENTS.md` →
`docs/README_OPERATIONS_INDEX.md` → `docs/WM_PLATFORM_HANDOFF.md` →
`docs/CODEX_WORKING_RULES.md` → the contract skills. Then this.

Branch `main`, pushed to `origin` (`Dicetar/wow-wm-project`).

---

## TL;DR — where the project is

The **Python/orchestration + repo health** layer is in good shape and proven.
The **LLM content loop** (quest generation → publish → grant) is **live-proven**.
The **spell/ability layer** is the real weak link: shells are authored client-side
but the **server-side spell publish pipeline is incomplete and was silently
drifting** — that is the next big development area.

### Proven WORKING this session (all pushed)
- **Repo CI health**: `python -m pytest -q` collects and passes (**940**),
  repeatable from a clean workspace, **no `--ignore`**. Fixed: `wm.cli`
  package/module collision; native-bridge safety tests re-homed onto the
  registry/domain files; pytest temp floor (Windows `0o700`/lock issues).
- **Slice LIVE-LLM quest loop — gameplay WORKING**: an arc OPEN beat → LM Studio
  (`qwen3-coder-30b`, an *instruct* model) generates a kill-bounty quest →
  `ProposalParser` screen + `validate_bounty_quest_draft` → publish (fresh
  reserved id) → reload → grant. Proven in-client: quest **"The Watcher's Mark"
  (910213)** is in Astel's (5408) quest log with the LLM-authored text.
- **Universal Panel V2.1 — read-side WORKING**: `/api/wm/session/overview`
  returns real per-character journey/state for any scoped GUID; marker-driven
  bootstrap selects the discovered GUID (not hardcoded). Universality guard test
  (`tests/test_no_hardcoded_test_guids.py`) blocks new hardcoded `5405/5406/5408`
  in generic code paths.
- **MPQ client-patch auto-apply — WORKING**: publishing a spell sets a pending
  flag; the BridgeLab watcher (`--client-patch-on-close`) rebuilds+installs
  `patch-z.mpq` when `wow.exe` closes. Proven: built+installed a real patch
  (1004 spell rows incl. the marker) into the live client.
- **Marker aura 946602 — WORKING (buff panel)**: was an invisible 0-duration
  dummy named "Tricked or Treated"; fixed to `duration_index 21` (permanent) so
  it shows on the buff panel (icon 135 "WM Watcher Beacon"), no character VFX,
  no gameplay effect. Verified in-client.

### Honest PARTIAL / NOT-DONE
- **Generic cross-lane proposal approval (Panel V2.2)**: specced direction, NOT
  built. The panel approves slice/arc proposals; generic quest/item/spell/action
  approval into one inbox is the next panel lane.
- **Watcher LIVE generation**: the reactive watcher's constraints are
  recipe/slots-shaped, not arc fixed-facts, so LIVE watcher quest proposals park
  with an actionable reason. Not wired.
- **Spell/ability server-side publish**: see the next section — this is the big one.

---

## The big finding: the spell server-publish pipeline is the weak link

All 26 entries in `control/runtime/spell_shell_bank.json` are `patch_state:
"planned"`, and the **server-side half of the spell pipeline is incomplete and
was drifting from the client half**. Concretely (all verified live this session):

1. **Server materializer does NOT author the spell name.**
   `wm.spells.server_dbc.materialize_server_spell_dbc` clones a seed spell and
   reuses the seed's string block — so the server spell keeps the *seed's* name
   (946602 was literally named **"Tricked or Treated"**), while the **client**
   patch authors the real name ("WM Watcher Beacon"). Client truth and server
   truth drift by design. The player only sees the client name on the buff
   panel, so this is "merely" confusing today — but it means server-side lookups,
   logs, and any name-based logic are wrong.
2. **Presentation bugs ship silently.** 946602 had `duration_index 0` → an
   invisible aura that never sat on the buff panel. There is no shell-audit that
   catches "buff intended but duration 0", "dummy aura with no visual when a
   visible buff is intended", or "missing name". Other shells likely have similar
   latent bugs.
3. **The `spell_dbc` DB *table* is stale and misleading.** It disagrees with the
   `Spell.dbc` *file* the worldserver actually loads (table had 946500-not-946602;
   file has 946602-not-946500). It is NOT the server's spell source and should be
   treated as non-authoritative / retired. (I wasted real time diagnosing off it —
   don't.)
4. **DataDir coupling is confusing but correct.** The Lab worldserver
   (`D:\WOW\WM_BridgeLab\run\bin\worldserver.exe`) has
   `DataDir = "D:\WOW\Azerothcore_WoTLK_Rebuild\run\data"`, so it loads DBCs from
   the "Rebuild" tree. "Rebuild" is the clean-original baseline AND the Lab's live
   DataDir. The server-DBC staging tool targets it (correct), but this dual role
   is a footgun — treat the Rebuild `dbc/Spell.dbc` as the live server DBC.
5. **New quests need a worldserver restart.** The slice grant (910213) only
   landed after a worldserver restart (the reload-after-publish isn't enough for a
   brand-new quest). The publish-on-approval flow should detect/flag this.

**Net:** client truth (MPQ patch) and server truth (`Spell.dbc` in DataDir) are
published by separate, inconsistent paths and drift. The MPQ auto-apply lane
built this session fixed the *client* half; the *server* half has no equivalent
"author name + presentation + verify" publish.

---

## Recommended next development order

1. **Unify + harden the spell publish pipeline (highest value, real debt).**
   - Make `server_dbc` author the spell **name + tooltip + duration** from the
     shell bank (single source of truth), matching what the client patch already
     does, so client and server never drift.
   - Add a **shell-audit** gate that fails on presentation bugs: visible-buff
     shell with `duration_index 0`; dummy aura with no `spell_visual` *and* no
     buff-panel intent; missing/placeholder name; seed-leaked name.
   - Provide a **combined client+server publish** (one command) that keeps both
     DBCs in sync and verifies the result (read back the server row + the client
     row) before declaring done.
   - Retire/ignore the stale `spell_dbc` table as a spell source.
2. **Publish the 26 "planned" shells properly** (or explicitly classify which are
   intended-live vs staged), now that the pipeline authors names/presentation.
   Re-verify Broug + Energy Surge live (they were only static-preflight WORKING,
   never combat-proven).
3. **Panel V2.2 — generic cross-lane proposal approval** (the universal operator
   workflow: character-scoped inbox → approve → publish/apply/rollback for any
   managed quest/item/spell/action through existing strict contracts).
4. **Slice grant robustness**: handle the new-quest-needs-restart caveat in
   publish-on-approval (auto-restart via SOAP-safe path, or surface a clear
   "restart required" status), and finish the watcher LIVE generation
   (map recipe/slots → fixed publish facts via `wm.targets.resolver`).
5. **Marker migration cleanup**: the system defaults to `946602`; ensure server +
   client + tooling all align on it and retire `946500` cleanly.

---

## Hard lessons from this session (do NOT repeat)
- **Verify against the source the runtime actually uses.** The `spell_dbc` table
  looked authoritative and wasn't; the live `Spell.dbc` file is. Confirm the
  loader before claiming "missing/present".
- **Don't overclaim.** "Repo WORKING" / static-preflight WORKING ≠ gameplay
  WORKING. Spells especially: client-patched ≠ castable; a spell must exist
  server-side AND show client-side AND be applicable.
- **No "green except ignored tests."** Full `pytest -q` must collect+pass.
- **Client/server truth are separate and must be published together.** A client
  MPQ patch for a server-missing/mis-defined spell is dead weight.

## Live env state at handoff
- Worldserver: pid `2672`, up + SOAP-responsive (DB `33307` / SOAP `7879` /
  world `8095`). A rapid double-restart earlier produced a worldserver that
  booted to `AC>` then died — restart wrapper has a stability edge case; verify
  the pid stays alive after a restart.
- LM Studio: up; **use an instruct/coder model** (`qwen3-coder-30b-a3b-instruct`)
  — the uncensored RP model returns empty content under strict JSON-schema.
- Astel (5408): online, marker `946602` applied (on the buff panel).
- Untracked/deferred (leave alone): the abilities track
  (`src/wm/abilities/{__init__,models,tracker}.py` + its test), the `2026-05-18`
  superpowers planning docs, `scripts/phase0/`, `sql/bootstrap/wm_ability_tables.sql`.

## Specs/plans written this session
- `docs/superpowers/specs/2026-05-22-slice-live-llm-quest-pipeline-design.md` (+ plan)
- `docs/superpowers/plans/2026-05-22-universal-panel-v2_1-character-view.md`
- `docs/superpowers/specs/2026-05-22-mpq-client-patch-auto-apply-design.md` (+ plan)

End of handoff.
