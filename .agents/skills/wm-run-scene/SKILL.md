---
name: wm-run-scene
description: Sequence a scripted scene — an ordered set of timed creature/world steps the WM plays out (say/emote/spawn/cast beats). Use this WHENEVER you want a directed moment rather than a single action: an NPC vignette, a staged encounter intro, a scripted reaction. Triggers: "run a scene", "sequence these NPC steps", "play a scripted moment", "stage an encounter intro". Python building-block API, not a CLI; built on the implemented creature actions.
---

# Run a scene sequence

A scene is an ordered list of steps the `SceneSequencer` plays, each emitting a
native-bus action with timing. It's the "director" layer over the per-action
creature/world verbs.

> **Python API, no `-m` CLI.** Entry points in `src/wm/scenes/`:
> `SceneStep`, `SceneContext`, `SceneSequencer` (`sequencer.py`; shapes in
> `models.py`). I have not executed the sequencer this session — read
> `sequencer.py` for the run method + how steps map to bus actions.

## Build on implemented actions only
A scene is only as capable as its underlying bus verbs. Per **wm-spawn-creature**,
the implemented creature actions are `creature_spawn` / `despawn` /
`set_display_id` / `set_scale` / `say` / `emote` / `cast_spell`, plus player-side
`player_apply_aura` etc. Steps that use movement/faction/yell/whisper/attack
(**not implemented**) or any `gameobject_*` action (**none implemented**) won't
execute — design scenes around the implemented set or flag the gap.

## Where it fits
Scenes are a deterministic compiler target for the approval gate (the spec's
"scene" proposal kind). In the current slice the scene compiler is recorded but
not wired to the native bus (`slice_demo_live.live_scene` is record-only) — so
scene execution beyond the building blocks is partial.

## Gotchas
- A scene that "does nothing" → it used unimplemented verbs; check against the
  wm-spawn-creature implemented list.
- Don't put narrative-only steps through the bus — journal those (wm-write-journal).
