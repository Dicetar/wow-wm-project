---
name: wm-random-enchant-item
description: Apply a random enchant to an item via the native bus — the reward primitive behind the reactive enchant-on-kill lane. Use this WHENEVER the WM should grant a randomized item upgrade as a reward or reactive drop. Triggers: "random-enchant the player's item", "give a random enchant reward", "roll an enchant on item X", "enchant-on-kill reward". Backed by reactive/random_enchant.
---

# Random-enchant an item

Enqueues a `player_random_enchant_item` action (implemented ✓) — applies a
randomized enchant to a player's item. This is the reward primitive the reactive
enchant-on-kill lane uses (`src/wm/reactive/random_enchant.py`,
`RandomEnchantDropSpec`: `item_entry`, `chance_pct`, `drop_key`).

> **Verify the exact bus payload before relying on it.** The reactive module
> models drops as `{drop_key, item_entry, chance_pct}`; the precise
> `player_random_enchant_item` payload (item ref + enchant slot/params) is
> interpreted by the C++ bridge and exercised in
> `tests/test_native_bridge_actions.py` / the reactive enchant tests. I have not
> run this one end-to-end — confirm the keys there. Same allowlist/online rules as
> the other grant skills.

## Two ways in
- **Reactive lane (canonical for enchant-on-kill):** the auto-bounty / native
  watcher can enable random-enchant-on-kill (`Start-BridgeLabAll.ps1` /
  `Start-BridgeLabAutoBounty.ps1` have an `EnableRandomEnchantOnKill` path). See
  **wm-auto-bounty**. Prefer this for the reactive reward flow.
- **Direct bus action:** enqueue `player_random_enchant_item` for a one-off
  reward, mirroring the other grant skills' insert.

## Verify
`SELECT Status, ResultJSON FROM wm_bridge_action_request WHERE ActionKind='player_random_enchant_item' AND PlayerGUID=5408 ORDER BY RequestID DESC LIMIT 1;`

## Gotchas
- Target item not in the player's bags → nothing to enchant; not a bus error.
- Don't conflate with a fixed enchant — this rolls a random one; for a specific
  managed effect, use a managed item (wm-create-item) or ability (wm-grant-ability).
- Player offline / not allow-listed → row won't process (smoke-test the bus first).
