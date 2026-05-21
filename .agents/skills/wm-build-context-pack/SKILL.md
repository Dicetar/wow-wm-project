---
name: wm-build-context-pack
description: Build the deterministic context pack that feeds the LLM for an OPEN beat or reactive proposal — the snapshot of character/journal/event/zone state. Use this WHENEVER you need to assemble or understand the input the WM's LLM proposals are grounded in. Triggers: "build a context pack", "what does the LLM see", "assemble the snapshot for the proposal", "context pack for character/target X". This is a Python building-block API, not a CLI.
---

# Build a context pack

The context pack is the deterministic state snapshot handed to the LLM adapter so
proposals are grounded (not hallucinated). It is assembled by
`wm.context.ContextPackBuilder.build_for_target(...)`.

> **Python API, no `-m` CLI.** It composes injected loaders (Protocols in
> `src/wm/context/builder.py`): character state, subject journal, event store,
> reactive runtime, and the latest native context snapshot. I have not executed
> this directly this session — treat the entrypoint below as the map, and read
> `src/wm/context/builder.py` for the constructor wiring.

## Entry point
```python
from wm.context.builder import ContextPackBuilder
# builder is constructed with the loaders it needs (see the Protocols / the
# DbCharacterStateLoader + LatestNativeContextSnapshotLoader helpers in builder.py)
pack = builder.build_for_target(...)   # -> a context pack (see context/pack.py, models.py)
```
Supporting modules: `context/pack.py`, `context/snapshot.py`, `context/store.py`,
`context/zone_mood.py`, `context/legend.py`.

## Native snapshot input
The live native snapshot is requested through
`scripts/bridge_lab/Request-BridgeLabContextSnapshot.ps1` (the bridge writes a
snapshot row the builder's `LatestNativeContextSnapshotLoader` reads).

## Where it's used
The slice's OPEN-beat and Watcher proposal flows build a pack, then pass it to the
proposal adapter (`wm.llm.proposal_adapter`). In FIXTURE mode the pack isn't sent
to a model; in LIVE mode it grounds the LM Studio prompt.

## Gotchas
- Don't fabricate pack contents for the LLM — the whole point is determinism.
- Stale native snapshot → request a fresh one before building.
