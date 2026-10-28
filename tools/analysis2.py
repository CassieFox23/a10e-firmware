#!/usr/bin/env python3
# Adds bare-ADRP page-load tracking to find table/indexed-load referrers.
import sys, struct, bisect
from collections import defaultdict, Counter

BIN = sys.argv[1]
data = open(BIN, 'rb').read(); n = len(data); BASE = 0x8ef9e800
def sx(v, b): return v - (1 << b) if v & (1 << (b - 1)) else v

pagerefs = defaultdict(list)   # page_va -> [site_pc]  (bare adrp)
fullrefs = defaultdict(list)   # target_va -> [(site,kind)] (adrp+add/ldr/adr)
bl = defaultdict(list)         # callee -> [callsite]
pend = {}
for idx in range(0, n - 4 + 1, 4):
    insn = struct.unpack_from('<I', data, idx)[0]; pc = BASE + idx
    if (insn & 0x9F000000) == 0x90000000:                       # ADRP
        immlo = (insn >> 29) & 3; immhi = (insn >> 5) & 0x7FFFF
        page = (pc & ~0xFFF) + (sx((immhi << 2) | immlo, 21) << 12)
        rd = insn & 0x1F; pend[rd] = (idx, page)
        pagerefs[page].append(pc); continue
    if (insn & 0x9F000000) == 0x10000000:                       # ADR
        immlo = (insn >> 29) & 3; immhi = (insn >> 5) & 0x7FFFF
        fullrefs[pc + sx((immhi << 2) | immlo, 21)].append((pc, 'adr'))
        pend.pop(insn & 0x1F, None); continue
    if (insn >> 24) == 0x91:                                    # ADD imm64
        sh = (insn >> 22) & 3; imm = (insn >> 10) & 0xFFF
        if sh == 1: imm <<= 12
        rn = (insn >> 5) & 0x1F; rd = insn & 0x1F
        if rn in pend and (idx - pend[rn][0]) <= 32:
            fullrefs[pend[rn][1] + imm].append((pc, 'adrp+add'))
        pend.pop(rd, None); continue
    if (insn & 0xFFC00000) == 0xF9400000:                       # LDR imm64
        imm = (insn >> 10) & 0xFFF; rn = (insn >> 5) & 0x1F; rt = insn & 0x1F
        if rn in pend and (idx - pend[rn][0]) <= 32:
            fullrefs[pend[rn][1] + imm * 8].append((pc, 'adrp+ldr'))
        pend.pop(rt, None); continue
    if (insn & 0xFC000000) == 0x94000000:                       # BL
        bl[pc + (sx(insn & 0x3FFFFFF, 26) << 2)].append(pc); continue

entries = sorted(bl.keys())
def enc(a):
    i = bisect.bisect_right(entries, a) - 1
    return entries[i] if i >= 0 else None
rev = defaultdict(set)
for callee, sites in bl.items():
    for s in sites:
        f = enc(s)
        if f is not None: rev[callee].add(f)

# locate S-boxes
fwd = data.find(bytes.fromhex('637c777bf26b6fc5'))
inv = data.find(bytes.fromhex('52096ad53036a538'))
print(f"AES forward S-box @ file {fwd:#x} va {BASE+fwd:#x}" if fwd>=0 else "forward S-box not found")
print(f"AES inverse S-box @ file {inv:#x} va {BASE+inv:#x}" if inv>=0 else "inverse S-box not found")

def fns_touching_page(page, label):
    c = Counter(enc(s) for s in pagerefs.get(page, []) if s < BASE + 0x119000)
    print(f"\n== {label}: functions doing adrp->{page:#x} (code sites) ==")
    for fn, k in c.most_common(12):
        callers = sorted(rev.get(fn, []))
        print(f"  fn {fn and hex(fn)}: {k} adrp site(s); {len(callers)} caller fn(s): {[hex(x) for x in callers[:8]]}")

print("\n########## Q2: AES S-box users ##########")
for pg in sorted({ (BASE+inv)&~0xFFF, (BASE+fwd)&~0xFFF }):
    fns_touching_page(pg, f"S-box page {pg:#x}")

print("\n########## Q4: libjpeg copyright / code ##########")
COPY = BASE + 0x118d60
print(f"direct refs to copyright string {COPY:#x}: {fullrefs.get(COPY, [])}")
fns_touching_page(COPY & ~0xFFF, f"copyright page {COPY & ~0xFFF:#x}")
