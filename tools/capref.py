#!/usr/bin/env python3
# Operand-level AArch64 reference finder using the installed libcapstone (via ctypes).
# Tracks register address values so adrp;add;ldrb[base,idx] S-box accesses are caught.
import sys, ctypes, ctypes.util, re, json, bisect
from collections import defaultdict, Counter

BIN = sys.argv[1]
data = open(BIN, 'rb').read(); BASE = 0x8ef9e800
CODE_END = 0xf3000   # disassemble the code region (strings/tables start ~0xf3730)

libpath = ctypes.util.find_library('capstone') or '/usr/lib64/libcapstone.so.5'
cs = ctypes.CDLL(libpath)

class cs_insn(ctypes.Structure):
    _fields_ = [("id", ctypes.c_uint), ("address", ctypes.c_uint64),
                ("size", ctypes.c_uint16), ("bytes", ctypes.c_uint8 * 24),
                ("mnemonic", ctypes.c_char * 32), ("op_str", ctypes.c_char * 160),
                ("detail", ctypes.c_void_p)]

cs.cs_open.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_size_t)]
cs.cs_malloc.argtypes = [ctypes.c_size_t]; cs.cs_malloc.restype = ctypes.POINTER(cs_insn)
cs.cs_disasm_iter.argtypes = [ctypes.c_size_t, ctypes.POINTER(ctypes.c_void_p),
    ctypes.POINTER(ctypes.c_size_t), ctypes.POINTER(ctypes.c_uint64), ctypes.POINTER(cs_insn)]
cs.cs_disasm_iter.restype = ctypes.c_bool

CS_ARCH_ARM64 = 1; CS_MODE_LITTLE = 0
h = ctypes.c_size_t()
assert cs.cs_open(CS_ARCH_ARM64, CS_MODE_LITTLE, ctypes.byref(h)) == 0, "cs_open failed"
insn = cs.cs_malloc(h.value)

buf = ctypes.create_string_buffer(data[:CODE_END], CODE_END)
code = ctypes.cast(buf, ctypes.c_void_p)
size = ctypes.c_size_t(CODE_END)
addr = ctypes.c_uint64(BASE)

def reg(t):
    t = t.strip()
    m = re.match(r'^[wx](\d+)$', t)
    if m: return int(m.group(1))
    if t in ('sp', 'xzr', 'wzr'): return None
    return None

refs = defaultdict(list)       # target_va -> [(site, mnem)]
bl   = defaultdict(list)       # callee -> [callsite]
regval = {}
hexn = re.compile(r'0x[0-9a-fA-F]+')

while size.value > 0:
    if cs.cs_disasm_iter(h.value, ctypes.byref(code), ctypes.byref(size), ctypes.byref(addr), insn):
        pc = insn.contents.address
        m = insn.contents.mnemonic.decode(); ops = insn.contents.op_str.decode()
        toks = ops.split(',')
        dst = reg(toks[0]) if toks else None
        if m == 'adrp':
            n = hexn.findall(ops)
            if dst is not None and n: regval[dst] = int(n[-1], 16)
        elif m == 'adr':
            n = hexn.findall(ops)
            if n: refs[int(n[-1], 16)].append((pc, 'adr'))
            if dst is not None: regval.pop(dst, None)
        elif m in ('add', 'sub') and '#' in ops and len(toks) >= 3:
            rn = reg(toks[1]); n = hexn.findall(toks[2])
            if rn in regval and n:
                v = regval[rn] + (int(n[0], 16) if m == 'add' else -int(n[0], 16))
                regval[dst] = v
                if m == 'add': refs[v].append((pc, 'add'))
            else:
                if dst is not None: regval.pop(dst, None)
        elif m == 'mov' and len(toks) == 2:
            rn = reg(toks[1])
            if rn in regval: regval[dst] = regval[rn]
            elif dst is not None: regval.pop(dst, None)
        elif m.startswith('ld') or m.startswith('st'):
            mb = re.search(r'\[\s*([wx]\d+|sp)([^\]]*)\]', ops)
            if mb:
                base = reg(mb.group(1)); rest = mb.group(2)
                if base in regval:
                    off = hexn.findall(rest)
                    t = regval[base] + (int(off[0], 16) if off else 0)
                    refs[t].append((pc, m))
            # loads overwrite their dest register value
            if m.startswith('ld') and dst is not None: regval.pop(dst, None)
        elif m == 'bl':
            n = hexn.findall(ops)
            if n: bl[int(n[0], 16)].append(pc)
        else:
            if dst is not None: regval.pop(dst, None)
    else:
        code.value += 4; size.value -= 4; addr.value += 4
        regval.clear()

entries = sorted(bl.keys())
def enc(a):
    i = bisect.bisect_right(entries, a) - 1
    return entries[i] if i >= 0 else None
rev = defaultdict(set)
for callee, sites in bl.items():
    for s in sites:
        f = enc(s)
        if f is not None: rev[callee].add(f)

print(f"disassembled code region; ref targets {len(refs)}, BL targets {len(bl)}")
print("\n==== Q2: functions referencing the INVERSE S-box [0x8f094900,0x8f094a00) ====")
users = Counter()
for t, sites in refs.items():
    if 0x8f094900 <= t < 0x8f094a00:
        for s, mn in sites: users[enc(s)] += 1
for fn, c in users.most_common(12):
    callers = sorted(rev.get(fn, []))
    print(f"  fn {fn and hex(fn)}: {c} S-box ref(s); {len(callers)} caller(s): {[hex(x) for x in callers[:10]]}")

print("\n==== Q2: same for FORWARD S-box [0x8f09d5d8,0x8f09d6d8) (encrypt) ====")
fu = Counter()
for t, sites in refs.items():
    if 0x8f09d5d8 <= t < 0x8f09d6d8:
        for s, mn in sites: fu[enc(s)] += 1
for fn, c in fu.most_common(8):
    callers = sorted(rev.get(fn, []))
    print(f"  fn {fn and hex(fn)}: {c} ref(s); {len(callers)} caller(s): {[hex(x) for x in callers[:10]]}")

json.dump({"refs": {f"{k:#x}": v for k, v in refs.items()},
           "bl": {f"{k:#x}": v for k, v in bl.items()}}, open(sys.argv[2], 'w'))
print(f"\nsaved -> {sys.argv[2]}")
