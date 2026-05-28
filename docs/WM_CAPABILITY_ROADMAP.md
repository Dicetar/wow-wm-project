# WM Capability Roadmap

Status: `ACTIVE_DIRECTION`
Created: 2026-05-29
Repository: `wm-project`
Companion to: `docs/WM_MAIN_DESIGN_DOCUMENT.md` (architecture reference)
Supersedes the *priorities* (not the facts) in: `docs/NEXT_SESSION_HANDOFF_2026_05_27.md`

This document sets capability direction. It is feature-first. It assumes the existing
safeguards (control contracts, dry-run, policy gates, native C++ validation, audit,
rollback) are infrastructure to **ride on**, not work to expand. New features must use
those gates; they must not weaken or duplicate them.

## 1. Corrected Current State

The 2026-05-27 handoff lists "build one visible launcher" as the top objective. That is
**already done** in local WIP:

- `src/wm/launcher.py` (~819 lines), `start-wm-launcher.bat`, `tests/test_launcher.py` exist.

So the frontier is no longer "make it launch." The frontier is **making the WM feel like a
World Master** rather than a chat model bolted onto WoW.

What the LLM-facing code can do today:

- `src/wm/autoplay/world_context.py` builds a solid bounded read-only world snapshot
  (character row, online players, active quests, recent events, recent WM chat, native
  action history, latest native context snapshot). Perception is in good shape.
- `src/wm/autoplay/service.py::_chat_reply` feeds that context to the model, then constrains
  it to "one plain in-game sentence under 160 characters," and `_send_chat_reply` always
  wraps the result as a single `player_chat_message`.
- `src/wm/autoplay/tools.py` shows the model a tool manifest but its own docstring is honest:
  the model "still only authors typed drafts" — and in chat it cannot even do that, only talk.
- `src/wm/sources/native_bridge/action_kinds.py` defines ~99 native verbs; ~30 are
  `implemented=True`. A full validate -> dry-run -> policy -> apply -> audit -> rollback
  pipeline already exists and is exercised by the event-driven generation lanes.

## 2. Central Diagnosis

**The LLM and the action bus are disconnected at the conversational layer.**

Two halves never meet:

1. A **chat half**: the WM can *talk* about the world but its only possible action is to say
   a sentence.
2. A **generation half** (quest / item / spell / scene / action lanes): can produce real,
   validated, applyable proposals — but is triggered by **events**, never by **conversation**.

A player who types "I'm bored, send something to hunt me" gets flavor text, not a spawned
stalker, even though `creature_spawn` is implemented and the full apply pipeline is right
there. Closing that gap is the difference between a chatbot and a World Master — and it
removes no safeguard: the LLM still only proposes; Python still compiles/validates/applies;
C++ still executes only contracted verbs.

## 3. Phased Roadmap

### Phase 0 — Baseline to playable (mostly done; do not dwell)
- Launcher exists. Drive BridgeLab doctor to 8/8, make panel/autoplay model config a single
  source of truth, confirm chat round-trips live in-game.
- This is the floor, not the work.

### Phase 1 — KEYSTONE: Conversational Action Loop (highest leverage)
Chat can *optionally* emit a typed proposal that flows through the existing pipeline, then
confirms the result back in chat. "Talk -> act -> tell you." Detailed in Section 4.

### Phase 2 — Live Reaction Layer (ambient game master)
The autoplay tick already watches events. Add a bounded, cooldowned **narration/reaction
lane**: on notable live events (rare kill, death, level-up, zone entry, quest complete) the
WM proactively speaks or takes a low-risk action, so the world feels alive when the player is
silent. Distinct from the existing content-generation lanes, which emit drafts, not in-character
live reactions.

### Phase 3 — Verb Surface Expansion (native C++)
Implement the highest flavor-to-risk verbs from the ~69 unimplemented kinds. Priority order
by (flavor impact x safety x cost):
1. `creature_say` / `creature_yell` / `creature_whisper_player` (cheap, huge presence)
2. `gossip_override_set` / `npc_text_override_set` (WM speaks through existing NPCs)
3. `player_play_sound`, `zone_set_weather` (atmosphere)
4. `companion_*` family (a talking follower is a step-change in GM feel)
Native work respects the Python-owns-intent / C++-owns-runtime boundary.

### Phase 4 — Persistent Narrative Memory
Wire journal/subject memory **into** chat context as narrative ("you slew the Bonebound
Alpha last week") and write conversational facts **back** as durable memory. This is what
makes the WM per-character and persistent rather than goldfish-brained.

### Phase 5 — Scene Director (high ceiling)
Multi-step orchestrated moments via the action bus's sequence support (sequence IDs,
wait-for-prior): spawn -> approach -> speak -> cast -> despawn, authored from a single
conversation. The "Live Scene Director" north-star lane.

### Enabler — Split `autoplay/service.py` (only after Phase 1 is live-proven)
2.3k lines doing 6+ jobs (tick loop, chat, generation, proposal compile, watchers, status).
Split into `chat_runtime`, `reaction_runtime`, `generation_runtime`, `proposal_compile`,
`watchers`, `status`. Justified solely as feature-velocity unblock; gated behind live proof so
it never destabilizes a working loop.

## 4. Keystone Architecture (Phase 1 detail)

Chat output evolves from "a string" to a small discriminated union:

```
LLM chat output  ->  { reply: str, intent: null }                 (pure talk; today's behavior)
                 ->  { reply: str, intent: { verb, args, why } }   (talk + a proposed deed)
```

Flow, reusing existing components:

1. **Perceive** — `build_chat_world_context` + a manifest of verbs *allowed for this player and
   risk budget* (filtered `autoplay_tool_manifest`).
2. **Propose** — model returns reply text and, optionally, a high-level intent chosen from the
   manifest. The model never writes SQL or a raw proposal.
3. **Compile** — a deterministic `intent -> typed proposal` mapper (Python owns this). The
   model's args are validated/clamped; GUID, scope, and IDs are locked in by code, mirroring
   how `_chat_action_proposal` already builds the chat proposal.
4. **Gate** — straight into the existing control coordinator: schema -> policy -> dry-run.
   Low-risk verbs auto-apply; medium/high park as an approval (panel inbox already exists, or
   in-chat confirm).
5. **Confirm** — the WM speaks the outcome in chat (success or the reason it's blocked).
6. **Remember** — write the deed to the journal so Phase 4 can later reference it.

Net new surface is small: a chat-response schema, an `intent -> proposal` compiler, and a chat
approval affordance. Everything risky is already handled by existing code.

## 5. Operating Principles For This Roadmap

- Features ride existing safeguards; we do not expand safeguards as headline work.
- Never mark a capability `WORKING` without in-client player-facing proof.
- The LLM proposes; deterministic Python validates, compiles, applies, audits, rolls back;
  native C++ executes only contracted verbs. This boundary is non-negotiable and is what makes
  ambitious features safe to ship.
