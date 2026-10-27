#!/usr/bin/env python3
# Pure-Python AArch64 reference/callgraph scanner for a raw image.
# Decodes ADRP(+ADD/+LDR), ADR, and BL. No external deps.
import sys, struct, json

BASE = 0x8f000000
path = sys.argv[1]
data = open(path, 'rb').read()
n = len(data)

def sx(v, bits):
    return v - (1 << bits) if v & (1 << (bits - 1)) else v

refs = {}      # target_va -> list of (site_va, kind)
bl   = {}      # target_va -> list of callsite_va
pend = {}      # reg -> (idx, page_va)

def add_ref(t, site, kind):
    refs.setdefault(t, []).append((site, kind))

for idx in range(0, n - 4 + 1, 4):
    insn = struct.unpack_from('<I', data, idx)[0]
    pc = BASE + idx
    top8 = insn >> 24
    # ADRP: (insn & 0x9F000000) == 0x90000000
    if (insn & 0x9F000000) == 0x90000000:
        immlo = (insn >> 29) & 3
        immhi = (insn >> 5) & 0x7FFFF
        imm = sx((immhi << 2) | immlo, 21) << 12
        page = (pc & ~0xFFF) + imm
        rd = insn & 0x1F
        pend[rd] = (idx, page)
        continue
    # ADR: (insn & 0x9F000000) == 0x10000000
    if (insn & 0x9F000000) == 0x10000000:
        immlo = (insn >> 29) & 3
        immhi = (insn >> 5) & 0x7FFFF
        imm = sx((immhi << 2) | immlo, 21)
        add_ref(pc + imm, pc, 'adr')
        pend.pop(insn & 0x1F, None)
        continue
    # ADD (immediate) 64-bit: top byte 0x91
    if top8 == 0x91:
        shift = (insn >> 22) & 3
        imm12 = (insn >> 10) & 0xFFF
        if shift == 1:
            imm12 <<= 12
        rn = (insn >> 5) & 0x1F
        rd = insn & 0x1F
        if rn in pend and (idx - pend[rn][0]) <= 8 * 4:
            target = pend[rn][1] + imm12
            add_ref(target, pc, 'adrp+add')
        pend.pop(rd, None)
        continue
    # LDR (immediate, unsigned offset) 64-bit: (insn & 0xFFC00000)==0xF9400000
    if (insn & 0xFFC00000) == 0xF9400000:
        imm12 = (insn >> 10) & 0xFFF
        rn = (insn >> 5) & 0x1F
        rt = insn & 0x1F
        if rn in pend and (idx - pend[rn][0]) <= 8 * 4:
            litaddr = pend[rn][1] + imm12 * 8
            add_ref(litaddr, pc, 'adrp+ldr(litaddr)')
            off = litaddr - BASE
            if 0 <= off <= n - 8:
                val = struct.unpack_from('<Q', data, off)[0]
                add_ref(val, pc, 'adrp+ldr(ptr)')
        pend.pop(rt, None)
        continue
    # BL: (insn & 0xFC000000)==0x94000000
    if (insn & 0xFC000000) == 0x94000000:
        off = sx(insn & 0x3FFFFFF, 26) << 2
        bl.setdefault(pc + off, []).append(pc)
        continue

def hits_in(lo, hi):
    out = []
    for t, sites in refs.items():
        if lo <= t < hi:
            out.append((t, sites))
    return sorted(out)

print(f"image {path}  base {BASE:#x}  size {n:#x}")
print(f"data-ref targets: {len(refs)}   BL targets: {len(bl)}\n")

print("== CONTROL: refs to known 'blocked' strings (must be non-empty) ==")
for t in (0x8f1009a8, 0x8f100a08, 0x8f1128e8):
    s = refs.get(t, [])
    print(f"  {t:#010x}: {len(s)} site(s)" + (f"  e.g. {s[0][0]:#010x} [{s[0][1]}]" if s else "  -- NONE --"))

print("\n== Q1: refs landing in each embedded ELF's first 0x2000 (header/entry) ==")
for name, off in (("ELF1 TEEGRIS", 0x11982b), ("ELF2 TEEGRIS", 0x12862b), ("ELF3 startup_loader", 0x2d4827)):
    va = BASE + off
    h = hits_in(va - 0x40, va + 0x2000)
    print(f"  {name} @ {va:#010x}: {sum(len(s) for _,s in h)} ref(s) in [-0x40,+0x2000)")
    for t, sites in h[:8]:
        for site, kind in sites[:3]:
            print(f"      target {t:#010x}  <- site {site:#010x} [{kind}]")

print("\n== Q3 context: refs into the two high-entropy regions ==")
for name, off, size in (("entropy-A 96KiB", 0x3400, 0x18000), ("entropy-B 90KiB", 0x12c800, 0x16800)):
    va = BASE + off
    h = hits_in(va, va + size)
    print(f"  {name} @ {va:#010x} (+{size:#x}): {sum(len(s) for _,s in h)} ref(s)")
    for t, sites in h[:6]:
        print(f"      target {t:#010x}  <- {sites[0][0]:#010x} [{sites[0][1]}]  ({len(sites)} site(s))")

# persist for Q2/Q4 reuse
with open(sys.argv[2], 'w') as f:
    json.dump({"base": BASE,
               "refs": {f"{k:#x}": v for k, v in refs.items()},
               "bl": {f"{k:#x}": v for k, v in bl.items()}}, f)
print(f"\nfull index -> {sys.argv[2]}")
