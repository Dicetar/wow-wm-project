# Phase 2 — Contextual Quest Generation

This note defines the **next safe continuation step** after the live quest publish / edit / rollback slice.

The quest platform already works live.
The missing piece is that generation is still mostly **generic**.

The purpose of Phase 2 is to make quest drafts react to:

- the resolved questgiver profile
- the resolved target profile
- WM-owned enrichment rows
- WM-owned player/subject journal history

without putting an LLM back into the critical path.

---

## What is already in the repo

The repo already has the core tables needed for contextual generation:

- `wm_subject_definition`
- `wm_subject_enrichment`
- `wm_player_subject_journal`
- `wm_player_subject_event`

Those tables are created by:

```bash
mysql -u root -p acore_world < sql/bootstrap/wm_bootstrap.sql
```

The repo also already has:

- live creature resolution
- quest draft generation
- publish preflight
- live publish with runtime sync
- live edit
- rollback
- reserved-slot governance

So the correct continuation is **not** more infrastructure. It is wiring the existing WM memory model into generation.

---

## New helper added now

A new command has been added:

```bash
python -m wm.quests.context_builder
```

This command reads the same live DB used by the quest pipeline and builds a deterministic context package for a questgiver + target pair.

It resolves:

- questgiver creature profile
- target creature profile
- optional subject enrichment
- optional player-specific journal history
- recent player/subject events
- deterministic generation hints

This gives the project a clean bridge into **context-aware quest generation** without changing publish/rollback behavior yet.

---

## Example usage

### By creature names

```bash
python -m wm.quests.context_builder \
  --questgiver-name "Marshal McBride" \
  --target-name "Kobold Vermin" \
  --player-guid 1 \
  --summary
```

### By creature entries

```bash
python -m wm.quests.context_builder \
  --questgiver-entry 197 \
  --target-entry 6 \
  --player-guid 1 \
  --base-kill-count 8 \
  --output-json .\artifacts\context_kobold.json \
  --summary
```

---

## What the context builder returns

The output package contains:

- `questgiver_profile`
- `target_profile`
- `questgiver_context`
- `target_context`
- `generation_hints`

The important part for Phase 2 is `generation_hints`.

It currently derives:

- `recommended_kill_count`
- `extra_tags`
- `tone_flags`
- `description_seeds`

These are deterministic hints, not generated prose.

That matters because it keeps generation stable and testable.

---

## Current heuristics

The helper currently reacts to a few things on purpose:

### Subject enrichment

If `wm_subject_enrichment` exists for the target, it can influence:

- tags
- role labels
- home area hints
- description seeds

### Player → target history

If `wm_player_subject_journal` exists, it can influence:

- repeated-hunt detection
- skinning-history detection
- fed-by-player detection
- known-to-player flags
- kill count escalation hints

### Player → questgiver history

If the same player has prior talk / quest completion history with the questgiver, the helper marks the questgiver as familiar.

---

## Why this is the right next step

This matches the current project stance:

- **lookup-first**
- **validation-first**
- **journal-first**
- **external-first**

It also matches the current roadmap:

> Make quest generation context-aware instead of merely syntactically valid.

The important design rule is:

**context should become structured generation input before it becomes prose.**

That keeps the WM explainable.

---

## Recommended next code step after this helper

After validating the helper against real rows, the next repo change should be:

### Integrate `context_builder` into `wm.quests.generate_bounty`

Suggested flow:

1. resolve questgiver profile
2. resolve target profile
3. optionally load contextual package using `--player-guid`
4. feed the package into `build_bounty_quest_draft`
5. let deterministic hints affect:
   - kill count
   - tags
   - wording seeds
   - reward heuristics

That would upgrade quest generation from:

- generic bounty boilerplate

into:

- bounty generation that notices repeated hunting, enrichment tags, known questgivers, and local subject context

while still remaining deterministic.

---

## Practical testing order

1. confirm bootstrap tables exist
2. run the new context builder against a questgiver/target pair with no journal rows
3. manually add a `wm_subject_enrichment` row for the target
4. rerun and confirm enrichment appears in output
5. manually add a `wm_subject_definition` row + `wm_player_subject_journal` row for the player
6. rerun and confirm history changes the context flags and recommended kill count
7. only then wire the same logic into `generate_bounty`

---

## Minimal manual seed examples

### Enrichment example

```sql
INSERT INTO wm_subject_enrichment (
  SubjectType,
  EntryID,
  Species,
  Profession,
  RoleLabel,
  HomeArea,
  ShortDescription,
  TagsJSON
) VALUES (
  'creature',
  6,
  'kobold',
  NULL,
  'tunnel vermin',
  'Northshire Vineyards',
  'Small tunnel raiders stealing candles from local work crews.',
  '["kobold","candle_thief","vineyard"]'
);
```

### Subject definition + journal example

```sql
INSERT INTO wm_subject_definition (
  SubjectType,
  CreatureEntry,
  JournalName,
  Archetype,
  Species,
  Occupation,
  HomeArea,
  ShortDescription
) VALUES (
  'creature',
  6,
  'Kobold Vermin',
  'local pest',
  'kobold',
  'raider',
  'Northshire Vineyards',
  'Repeatedly seen stealing candles and disrupting workers.'
);
```

Then use the returned `SubjectID` to insert a player journal row:

```sql
INSERT INTO wm_player_subject_journal (
  PlayerGUID,
  SubjectID,
  KillCount,
  TalkCount,
  QuestCompleteCount,
  NotesJSON
) VALUES (
  1,
  <SUBJECT_ID>,
  14,
  0,
  1,
  '{"status":"known nuisance"}'
);
```

---

## What this helper intentionally does not do yet

Not yet:

- write enrichment rows automatically
- summarize freeform notes with an LLM
- publish quests
- edit live quests
- decide event triggers
- generate non-bounty archetypes

This helper is a **context package builder**, not a replacement for the publish pipeline.

That boundary is intentional.
