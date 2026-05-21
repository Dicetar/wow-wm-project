---
name: wm-write-journal
description: Write, read, or summarize the WM journal — the narrative memory that records what happened to a character/subject and feeds back into future context packs. Use this WHENEVER you need to record a beat/event into the journal, read a subject's history, or summarize it. Triggers: "write a journal entry", "record this to the journal", "read the character's journal", "summarize what happened to subject X". Python building-block API, not a CLI.
---

# WM journal: write / read / summarize

The journal is the WM's narrative memory. Every PINNED auto-apply and approved
proposal should journal an entry; the journal is read back into future context
packs (wm-build-context-pack), closing the narrative loop.

> **Python API, no `-m` CLI.** Entry points in `src/wm/journal/`:
> - `JournalWriter` (`writer.py`) — append entries
> - `SubjectJournalReader` / `load_subject_journal_for_creature(...)` (`reader.py`)
>   — read a subject's `SubjectJournalBundle`
> - `summarizer.py` — condense a journal for context
> - `projector.py` / `project.py` — projection; `inspect.py`, `demo.py` — inspection/demo
>
> I have not executed these this session — read the module for constructor/DB
> wiring before relying on exact signatures.

## Typical usage
```python
from wm.journal.writer import JournalWriter
from wm.journal.reader import SubjectJournalReader
# writer.write(...) to append; reader to load a subject bundle the context builder consumes
```

## Architecture boundary (wm-workflow)
The journal is **Python-owned** (decisions/state/audit). Native modules sense and
act; they do not own narrative memory. Keep journal writes on the Python side.

## Gotchas
- Skipping journaling on an applied beat → future context packs lose that history,
  weakening LLM grounding.
- Don't treat the journal as live game state — it's the record, not the world.
