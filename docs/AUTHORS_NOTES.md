Status: PARTIAL
Last verified: not run (source implementation 2026-10-02)
Verified by: unknown
Doc type: reference

# Author's Notes

Explicit standing direction now has a separate storage and editing surface. No concrete quests,
character-specific content, native mechanics, model installation, or live DB changes were added.
Tests, builds, browser checks, and gameplay proof have not been run.

## Operator Surface

The **Author's Notes** tab is available in both panel modes. It supports World and Character
scope, preference/firm constraint, optional topic and expiry, editing, and archiving. The selected
session GUID prefills new Character notes. Archived/expired notes can be displayed explicitly.
Scope cannot be changed by editing; archive and add a new note in the intended scope.

`GET /api/wm/author-notes?player_guid=<guid>&include_inactive=1` returns World notes plus that
character's notes. Without GUID, the operator can list all notes. `context` contains applicable
active direction only. The operator API is part of the existing local panel, not a public player API.

`POST /api/wm/author-notes` accepts:

```json
{
  "operation": "add",
  "scope": "character",
  "player_guid": 123,
  "text": "Prefer exploration over repeated kill bounties.",
  "firmness": "preference",
  "topic": "quest_style",
  "expires_at": null
}
```

This is an illustrative payload, not a character default. `operation=edit` requires `note_id`
and the displayed integer `revision`; fields can be changed partially. `operation=archive`
requires only identity and revision. Optional `origin_key` makes repeated identical commands
idempotent; reusing it for different content is rejected.

## In-Game Input

Use the existing `towm` chat prefix (or the WM channel), not a newly installed client slash command:

```text
towm /note Prefer exploration over repeated kill bounties.
towm /note! Do not give this character companion creatures.
towm /notes
towm /notes 2
towm /note edit <note_id> Prefer brief dialogue and exploration.
towm /note remove <note_id>
```

`/note` creates a preference; `/note!` creates a firm constraint. Both default to the speaking
character. In-game edit/archive cannot affect another character or World notes. World scope,
topics, and expiry are set in the operator panel. Listing is paginated, four shortened entries
per page, to keep acknowledgements small; the panel contains the full text.

These commands bypass model generation and intent extraction. They still need the existing
native chat ingestion, a running/unpaused autoplay process, chat scanning enabled, and message
transport/scope for the acknowledgement. They can be handled with LLM generation disabled or
the model unavailable. Persisting the note and sending its acknowledgement are distinct outcomes;
a failed acknowledgement does not roll back a saved note. Native event origin keys prevent the
same imported chat command from adding another note on retry.

## Ownership And Context

`wm.author_notes.AuthorNotes` stores notes in `author-notes.sqlite3` beneath the existing
`PanelState.root`. Panel and autoplay must use the same root. SQLite transactions serialize
panel/runtime writes; no new service or world DB migration is required. Archive preserves the
row. Expiry stops applicability without deleting history. Back up this file with panel state.

There are at most 16 active World notes and 16 active notes per character, each up to 500
characters. Full active text is supplied rather than silently dropping firm constraints. Expired
and archived notes do not consume active capacity. Historical rows and command receipts remain
until an explicit future retention feature is added.

Applicable notes are supplied separately from memory to director evidence, chat voice and its
fallback, legacy intent extraction, content generation, and ambient narration. Generated draft
records retain the supplied note snapshot/revision hash. Director evidence no longer mislabels
ordinary narrative memory as Author's Notes. Forgetting conversational context does not delete
notes. No model-produced inference is promoted into a note; explicit commands or panel editing
are required.

Firm constraints take precedence over preferences. On the same topic, Character preferences
take precedence over World preferences. Differing firm notes with the same explicit topic are
flagged as **potential** conflicts, not proven semantic contradictions. The model is instructed
to clarify real conflicts. Notes have no authority to bypass policy, grant new capabilities, or
erase already accepted obligations.

## Proof Boundary And Limits

This is a source feature, not a tested or deployed guarantee. Free-form constraint interpretation
is model-assisted, not a deterministic policy engine. Untagged semantic conflicts cannot be
reliably detected by topic grouping. Existing approved/pending effects are not retroactively
cancelled or reauthorized when a note changes; their frozen evidence remains historical.
An ordinary sentence such as "remember this" does not automatically create a note: use the
explicit command or panel editor so inferred memory stays distinguishable from author direction.

Requested future proof should cover cross-process persistence, Character isolation, expiry,
concurrent edits, event retry without duplicate notes, no-model commands, panel editing in both
modes, and an actual decision respecting a note without claiming unsupported game effects.
