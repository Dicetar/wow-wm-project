#!/usr/bin/env python3
"""0E.2 dependency mapper for wm_spell_runtime.cpp.

For each anon-namespace state container, list the enclosing functions
that reference it and classify each into a spell family. Flags any
container touched by >=2 families (the 0E.2 STOP-gate trigger).
"""
import re, collections

F = r"D:\WOW\wm-project\native_modules\mod-wm-spells\src\wm_spell_runtime.cpp"
L = open(F, encoding="utf-8", newline="\n").read().split("\n")

# function definition lines: indent-4, an identifier followed by '(' ,
# excluding control keywords; covers anon helpers and WmSpells:: defs.
fndef = re.compile(r'^    (?:[\w:<>\*&,\s]+?[ \*&])?([A-Za-z_]\w*)\s*\(')
ctrl = {'if','for','while','switch','return','sizeof','catch','else'}

func_at = [None]*len(L)   # line idx -> enclosing function name
cur = "<file-scope>"
depth = 0
pending = None
for i, ln in enumerate(L):
    m = fndef.match(ln)
    if m and m.group(1) not in ctrl and not ln.rstrip().endswith(';') and depth <= 1:
        pending = m.group(1)
    func_at[i] = cur
    o = ln.count('{'); c = ln.count('}')
    # NOTE: brace-count is approximate (string literals), but enclosing
    # attribution only needs nearest-def which we recompute below anyway.
    if pending and '{' in ln:
        cur = pending; pending = None
    depth += o - c
    if depth <= 0:
        cur = "<file-scope>"

# More robust: nearest preceding fndef line for each usage.
defs = []  # (line_idx, name)
for i, ln in enumerate(L):
    m = fndef.match(ln)
    if m and m.group(1) not in ctrl and not ln.rstrip().endswith(';'):
        defs.append((i, m.group(1)))
def enclosing(idx):
    name = "<file-scope>"
    for li, nm in defs:
        if li <= idx: name = nm
        else: break
    return name

FAMILY = [
 ('Lanathel',       re.compile(r'Lanathel', re.I)),
 ('NightWatchers',  re.compile(r'NightWatchersLens', re.I)),
 ('Proficiency',    re.compile(r'IntellectBlock|CombatProficienc|Proficienc', re.I)),
 ('BrougGuard',     re.compile(r'BrougGuard', re.I)),
 ('BrougLightness', re.compile(r'BrougLightness', re.I)),
 ('BrougEmptyCourt',re.compile(r'BrougEmptyCourt', re.I)),
 ('BrougAbilities', re.compile(r'Broug(Skirmisher|Deflect|CloudStep|QiReversal|SilentMeridian|KillingIntent|Predator|Vitality|UniversalParry|AutoRetal)|CounterStance|Deflect|ForcedParry', re.I)),
 ('Bonebound',      re.compile(r'Bonebound|AlphaEcho|PriestEcho|Echo|Companion|Cleave|Bleed', re.I)),
 ('Core',           re.compile(r'Config|IsPlayerAllowed|ExecuteShellBehavior|CheckShellCast|PollDebug|LoadBehaviorRecord|IsSupportedBehaviorKind|ShouldAllowShellDefaultEffect|IsBoneboundShellSpell|CheckBoneboundCorpseTarget|Counter|Quest|Json|ToJson|Build.*Status|Describe', re.I)),
]
def fam(fnname):
    for tag, rx in FAMILY:
        if rx.search(fnname): return tag
    return f'?({fnname})'

containers = []
for i, ln in enumerate(L):
    m = re.match(r'^    (?:std::unordered_map|std::unordered_set|std::map|std::set|std::vector)[^;]*?\b(g[A-Z]\w*)\s*;', ln)
    if m: containers.append(m.group(1))

print(f"{len(containers)} containers\n")
flagged = []
for c in containers:
    rx = re.compile(r'\b'+re.escape(c)+r'\b')
    fns = collections.OrderedDict()
    for i, ln in enumerate(L):
        if rx.search(ln) and not re.match(r'^    (?:std::unordered_map|std::unordered_set|std::map|std::set|std::vector)', ln):
            fn = enclosing(i)
            fns.setdefault(fn, 0)
            fns[fn]+=1
    fams = collections.OrderedDict()
    for fn in fns:
        fams.setdefault(fam(fn), [])
        fams[fam(fn)].append(fn)
    fam_set = set(fams.keys())
    cross = len([x for x in fam_set if not x.startswith('Core')]) > 1 or (len(fam_set) > 1)
    mark = "  <<< MULTI-FAMILY" if len(fam_set) > 1 else ""
    print(f"{c}: families={sorted(fam_set)}{mark}")
    for fm, fl in fams.items():
        print(f"    {fm}: {sorted(set(fl))}")
    if len(fam_set) > 1:
        flagged.append((c, sorted(fam_set)))

print("\n=== CROSS-FAMILY (>=2 families) ===")
for c, fs in flagged:
    print(f"  {c}: {fs}")
print(f"\nTOTAL cross-family containers: {len(flagged)} / {len(containers)}")
