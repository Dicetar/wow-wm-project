#!/usr/bin/env python3
"""Phase 0D domain extractor.

Move a named set of top-level anonymous-namespace definitions out of
wm_bridge_action_queue.cpp into a domain TU, verbatim, and drop the
matching r.Register lines (the domain file re-registers them).

Brace matching is string/char/comment aware (the code is full of "{"/"}"
JSON literals), so naive counting is not used.
"""
import sys, re

MONO = r"D:\WOW\WM_BridgeLab\src\modules\mod-wm-bridge\src\wm_bridge_action_queue.cpp"

def find_span(lines, name):
    """Return (start_idx, end_idx) inclusive 0-based for the definition of
    `name` at indent 4 in the anon namespace, via brace matching."""
    sig_re = re.compile(r'^    (?:[A-Za-z_][\w:<>\*&\s]*?\s[\*&]?)?' + re.escape(name) + r'\b')
    start = None
    for i, ln in enumerate(lines):
        if sig_re.match(ln) and not ln.rstrip().endswith(';'):
            # struct or function definition (has a body)
            start = i
            break
    if start is None:
        raise SystemExit(f"NOT FOUND: {name}")
    # scan forward to first '{', then brace-match
    depth = 0
    seen = False
    i = start
    in_block = False
    while i < len(lines):
        s = lines[i]
        j = 0
        in_str = in_chr = in_line = False
        while j < len(s):
            c = s[j]
            two = s[j:j+2]
            if in_line:
                break
            if in_block:
                if two == '*/':
                    in_block = False; j += 2; continue
                j += 1; continue
            if in_str:
                if c == '\\': j += 2; continue
                if c == '"': in_str = False
                j += 1; continue
            if in_chr:
                if c == '\\': j += 2; continue
                if c == "'": in_chr = False
                j += 1; continue
            if two == '//':
                in_line = True; break
            if two == '/*':
                in_block = True; j += 2; continue
            if c == '"':
                in_str = True; j += 1; continue
            if c == "'":
                in_chr = True; j += 1; continue
            if c == '{':
                depth += 1; seen = True
            elif c == '}':
                depth -= 1
                if seen and depth == 0:
                    return (start, i)
            j += 1
        i += 1
    raise SystemExit(f"UNBALANCED: {name}")

def main():
    names = sys.argv[1].split(',')
    out_append = sys.argv[2]      # file to append extracted bodies to
    reg_kinds = sys.argv[3]       # comma list of action kinds to drop r.Register for ('' = none)

    with open(MONO, 'r', encoding='utf-8', newline='\n') as f:
        lines = f.read().split('\n')

    spans = []
    for n in names:
        spans.append((n, *find_span(lines, n)))
    # sort by start to emit in source order; detect overlap
    spans.sort(key=lambda t: t[1])
    for a, b in zip(spans, spans[1:]):
        if a[2] >= b[1]:
            raise SystemExit(f"OVERLAP {a[0]} {b[0]}")

    extracted = []
    drop = set()
    for name, s, e in spans:
        extracted.append('\n'.join(lines[s:e+1]))
        for k in range(s, e+1):
            drop.add(k)
        # also drop a single trailing blank line if present (keeps spacing tidy)
        if e+1 < len(lines) and lines[e+1].strip() == '':
            drop.add(e+1)

    # drop r.Register lines for the kinds
    kinds = [k for k in reg_kinds.split(',') if k]
    for i, ln in enumerate(lines):
        st = ln.strip()
        if st.startswith('r.Register(') and any(f'"{k}"' in ln for k in kinds):
            drop.add(i)

    kept = [ln for i, ln in enumerate(lines) if i not in drop]
    with open(MONO, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(kept))

    with open(out_append, 'a', encoding='utf-8', newline='\n') as f:
        f.write('\n\n'.join(extracted))
        f.write('\n')

    print(f"moved {len(spans)} defs: {[n for n,_,_ in spans]}")
    print(f"mono {len(lines)} -> {len(kept)} lines; dropped {len(drop)}")

if __name__ == '__main__':
    main()
