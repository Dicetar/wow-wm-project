#!/usr/bin/env python3
"""0E.3/0E.4 function ownership analyzer for wm_spell_runtime.cpp.

For every function definition (anon helpers + public WmSpells:: defs):
span, name-based family, containers touched, and callers. A helper is
SHARED (-> wm_spell_internal) when it has no family signal and is called
from >=2 families or is a generic util; otherwise it is family-private
(moves with its family in 0E.4).
"""
import re, collections, sys

F = r"D:\WOW\wm-project\native_modules\mod-wm-spells\src\wm_spell_runtime.cpp"
L = open(F, encoding="utf-8", newline="\n").read().split("\n")

ctrl = {'if','for','while','switch','return','sizeof','catch','else','do'}
fndef = re.compile(r'^    (?:[\w:<>\*&,\s]+?[ \*&])?([A-Za-z_]\w*)\s*\(')

def scan_spans():
    """string/comment-aware brace match -> list of (name,s,e) 0-based incl."""
    spans=[]; i=0; n=len(L)
    while i<n:
        m=fndef.match(L[i])
        if m and m.group(1) not in ctrl and not L[i].rstrip().endswith(';'):
            name=m.group(1); depth=0; seen=False; j=i; inb=False
            while j<n:
                s=L[j]; k=0; ins=inc=inl=False
                while k<len(s):
                    c=s[k]; two=s[k:k+2]
                    if inl: break
                    if inb:
                        if two=='*/': inb=False;k+=2;continue
                        k+=1;continue
                    if ins:
                        if c=='\\':k+=2;continue
                        if c=='"':ins=False
                        k+=1;continue
                    if inc:
                        if c=='\\':k+=2;continue
                        if c=="'":inc=False
                        k+=1;continue
                    if two=='//': inl=True;break
                    if two=='/*': inb=True;k+=2;continue
                    if c=='"':ins=True;k+=1;continue
                    if c=="'":inc=True;k+=1;continue
                    if c=='{':depth+=1;seen=True
                    elif c=='}':
                        depth-=1
                        if seen and depth==0:
                            spans.append((name,i,j)); break
                    k+=1
                if seen and depth==0: break
                j+=1
            i=j+1; continue
        i+=1
    return spans

spans=scan_spans()
# de-dup (overloads): keep all, but ownership keyed by name
by_name=collections.defaultdict(list)
for nm,s,e in spans: by_name[nm].append((s,e))

FAM=[('Lanathel',r'Lanathel'),
     ('NightWatchers',r'NightWatchersLens'),
     ('Proficiency',r'IntellectBlock|CombatProficienc'),
     ('Broug',r'Broug|CounterStance|ForcedParry|Deflect|Skirmisher|CloudStep|QiReversal|SilentMeridian|KillingIntent|Predator|Vitality|UniversalParry|MarkedMeridian|Domain'),
     ('Bonebound',r'Bonebound|AlphaEcho|PriestEcho|BoneboundEcho|Bleed|Cleave|Omega|Companion'),
     ('Core',r'^(GetConfig|LoadConfig|IsPlayerAllowed|ExecuteShellBehavior|CheckShellCast|CheckBoneboundCorpseTarget|PollDebug|LoadBehaviorRecord|IsSupportedBehaviorKind|ShouldAllowShellDefaultEffect|IsBoneboundShellSpell)')]
def nfam(nm):
    for t,rx in FAM:
        if re.search(rx,nm): return t
    return None

# containers + their owning family (from spellmap verdict)
CONT_FAM={}
for ln in L:
    m=re.match(r'^    (?:std::unordered_map|std::unordered_set|std::map|std::set|std::vector)[^;]*?\b(g[A-Z]\w*)\s*;',ln)
    if m:
        c=m.group(1)
        if re.search(r'Broug',c):CONT_FAM[c]='Broug'
        elif re.search(r'Bonebound',c):CONT_FAM[c]='Bonebound'
        elif re.search(r'NightWatchersLens',c):CONT_FAM[c]='NightWatchers'
        elif re.search(r'IntellectBlock',c):CONT_FAM[c]='Proficiency'
        elif re.search(r'Lanathel',c):CONT_FAM[c]='Lanathel'
        else:CONT_FAM[c]='?'

def enclosing(idx):
    nm='<file>'
    for n2,s,e in spans:
        if s<=idx<=e: nm=n2
    return nm

# for each function: containers touched + callees (other known fn names)
names=set(by_name)
fninfo={}
for nm,occ in by_name.items():
    conts=set(); callees=set()
    for (s,e) in occ:
        body="\n".join(L[s:e+1])
        for c in CONT_FAM:
            if re.search(r'\b'+c+r'\b',body): conts.add(c)
        for cand in names:
            if cand!=nm and re.search(r'\b'+re.escape(cand)+r'\s*\(',body): callees.add(cand)
    fninfo[nm]=(conts,callees)

# callers map
callers=collections.defaultdict(set)
for nm,(conts,callees) in fninfo.items():
    for ce in callees: callers[ce].add(nm)

def fam_of(nm,depth=0):
    f=nfam(nm)
    if f: return f
    conts,_=fninfo[nm]
    cf={CONT_FAM[c] for c in conts if CONT_FAM[c]!='?'}
    if len(cf)==1: return next(iter(cf))
    if len(cf)>1: return 'MULTI:'+'+'.join(sorted(cf))
    return None

print(f"{len(spans)} fn defs, {len(by_name)} unique names\n")
shared=[]; fam_owned=collections.defaultdict(list); unknown=[]
for nm in sorted(by_name):
    f=fam_of(nm)
    cl_fams={fam_of(c) for c in callers[nm]}
    cl_fams={x for x in cl_fams if x}
    base_cl={x.split(':')[0] if x and x.startswith('MULTI') else x for x in cl_fams}
    real_cl=set()
    for x in cl_fams:
        if x and x.startswith('MULTI:'): real_cl|=set(x[6:].split('+'))
        elif x: real_cl.add(x)
    if f and not f.startswith('MULTI'):
        fam_owned[f].append(nm)
    elif f and f.startswith('MULTI'):
        shared.append((nm,'touches '+f))
    else:
        noncore={x for x in real_cl if x!='Core'}
        if len(noncore)>=2:
            shared.append((nm,'called by '+','.join(sorted(real_cl))))
        elif len(noncore)==1:
            fam_owned[next(iter(noncore))].append(nm)
        else:
            unknown.append((nm,sorted(real_cl)))

for fam in sorted(fam_owned):
    print(f"== {fam} ({len(fam_owned[fam])}) ==")
    print("  "+", ".join(sorted(fam_owned[fam])))
print(f"\n== SHARED candidates (-> wm_spell_internal) ({len(shared)}) ==")
for nm,why in sorted(shared): print(f"  {nm}  [{why}]")
print(f"\n== UNKNOWN / generic util (review) ({len(unknown)}) ==")
for nm,cl in sorted(unknown): print(f"  {nm}  callers_fam={cl}")
