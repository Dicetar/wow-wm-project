# Content Candidates V4

## What changed from V3

V3 restored candidate extraction from your real sample bundles by falling back to sampled row keys when schema metadata was inconsistent.

That solved the **empty list** problem.

However, the V3 demo showed the next real issue clearly:
- spell candidates were mechanically real, but many were narratively useless or highly internal
- items and quests were valid, but not prioritized for the current character and target context

V4 addresses that by introducing **context-aware ranking**.

## Current implementation in repo

- `src/wm/candidates/ranking.py`
- `src/wm/candidates/providers_v4.py`
- `src/wm/candidates/demo_ranked_v4.py`
- `src/wm/prompt/demo_candidates_v4.py`
- `tests/test_candidate_ranking.py`
- `tests/test_candidates_v4.py`

## What V4 improves

### Candidate context
V4 builds a compact ranking context from:
- target facts
- current target level hint
- character preferred themes
- character avoided themes

For the current demo, this means terms like:
- `murloc`
- `forager`
- `arcane`
- `ironforge`

can influence ranking.

### Heuristic scoring
Candidates are now ranked instead of just accepted in source order.

#### Quest heuristics
Examples:
- rewards/requirements near the target level rank better
- quests matching target/theme terms rank better
- strange outliers like talent-restoration style quests are penalized

#### Item heuristics
Examples:
- moderate-quality usable gear is preferred over obviously weird edge cases
- item-granted spell hooks get a bonus
- context terms influence score

#### Spell heuristics
Examples:
- context-aligned terms like `arcane` rise in rank
- noisy labels such as `passive`, `on gossip`, `proc`, `stance`, `trigger`, `script` are penalized

## Local commands

### Pull latest changes

```powershell
cd D:\WOW\wm-project
git pull origin main
```

### Reinstall editable package

```powershell
cd D:\WOW\wm-project
.\.venv\Scripts\Activate.ps1
pip install -e .
```

### Run tests

```powershell
cd D:\WOW\wm-project
.\.venv\Scripts\Activate.ps1
python -m unittest discover -s tests -v
```

### Run ranked candidate demo V4

```powershell
cd D:\WOW\wm-project
.\.venv\Scripts\Activate.ps1
python -m wm.candidates.demo_ranked_v4
```

### Run prompt package + ranked candidates demo V4

```powershell
cd D:\WOW\wm-project
.\.venv\Scripts\Activate.ps1
python -m wm.prompt.demo_candidates_v4
```

## Expected result

Compared to V3:
- top spell candidates should be less dominated by internal/gossip/passive noise
- candidate summaries will include `score=...`
- the model receives a more curated option list instead of raw source-order samples

## Next implementation target

Content Candidates V5 should add:
- class-aware filtering
- stronger item suitability rules
- explicit reward safety policies
- target-zone and faction relevance weighting
- slot allocation handoff for approved custom content staging
