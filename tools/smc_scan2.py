#!/usr/bin/env python3
# Find real `smc #0` / `hvc` sites and the register state (x0=SMCCC fn id, x1..x6 args)
# resolved from the preceding movz/movk/mov/adrp/add. capstone via ctypes.
import sys, ctypes, ctypes.util, re
from collections import deque

BIN = sys.argv[1]
data = open(BIN, 'rb').read(); BASE = 0x8f000000; END = 0xf3000
cs = ctypes.CDLL(ctypes.util.find_library('capstone') or '/usr/lib64/libcapstone.so.5')
class I(ctypes.Structure):
    _fields_=[("id",ctypes.c_uint),("address",ctypes.c_uint64),("size",ctypes.c_uint16),
              ("bytes",ctypes.c_uint8*24),("mnemonic",ctypes.c_char*32),
              ("op_str",ctypes.c_char*160),("detail",ctypes.c_void_p)]
cs.cs_open.argtypes=[ctypes.c_int,ctypes.c_int,ctypes.POINTER(ctypes.c_size_t)]
cs.cs_malloc.argtypes=[ctypes.c_size_t]; cs.cs_malloc.restype=ctypes.POINTER(I)
cs.cs_disasm_iter.argtypes=[ctypes.c_size_t,ctypes.POINTER(ctypes.c_void_p),
    ctypes.POINTER(ctypes.c_size_t),ctypes.POINTER(ctypes.c_uint64),ctypes.POINTER(I)]
cs.cs_disasm_iter.restype=ctypes.c_bool
h=ctypes.c_size_t(); cs.cs_open(1,0,ctypes.byref(h)); ins=cs.cs_malloc(h.value)
buf=ctypes.create_string_buffer(data[:END],END); code=ctypes.cast(buf,ctypes.c_void_p)
size=ctypes.c_size_t(END); addr=ctypes.c_uint64(BASE)

hexn=re.compile(r'0x[0-9a-fA-F]+')
def reg(t):
    t=t.strip(); m=re.match(r'^[wx](\d+)$',t); return int(m.group(1)) if m else None
def lsl(tok):
    mm=re.search(r'lsl\s*#(\d+)',tok); return int(mm.group(1)) if mm else 0
def imm(tok):
    mm=re.search(r'#(-?)(0x[0-9a-fA-F]+|\d+)', tok)
    if not mm: return None
    v=int(mm.group(2),16) if mm.group(2).startswith('0x') else int(mm.group(2))
    return -v if mm.group(1)=='-' else v
regval={}; win=deque(maxlen=14); sites=[]
while size.value>0:
    if cs.cs_disasm_iter(h.value,ctypes.byref(code),ctypes.byref(size),ctypes.byref(addr),ins):
        pc=ins.contents.address; m=ins.contents.mnemonic.decode(); o=ins.contents.op_str.decode()
        win.append((pc,m,o))
        toks=o.split(','); dst=reg(toks[0]) if toks else None
        wid = 0xFFFFFFFF if (toks and toks[0].strip().startswith('w')) else 0xFFFFFFFFFFFFFFFF
        if m=='movz':
            v=imm(toks[1]) if len(toks)>1 else None
            if dst is not None and v is not None: regval[dst]=(v<<lsl(o))&wid
        elif m=='movn':
            v=imm(toks[1]) if len(toks)>1 else None
            if dst is not None and v is not None: regval[dst]=(~(v<<lsl(o)))&wid
        elif m=='movk':
            v=imm(toks[1]) if len(toks)>1 else None; sh=lsl(o)
            if dst is not None and v is not None: regval[dst]=((regval.get(dst,0)&~(0xffff<<sh))|(v<<sh))&wid
        elif m=='mov' and len(toks)==2:
            rn=reg(toks[1]); v=imm(toks[1])
            if rn in regval: regval[dst]=regval[rn]&wid
            elif v is not None: regval[dst]=v&wid
            elif dst is not None: regval.pop(dst,None)
        elif m=='adrp':
            n=hexn.findall(o)
            if dst is not None and n: regval[dst]=int(n[-1],16)
        elif m in('add','sub') and '#' in o and len(toks)>=3:
            rn=reg(toks[1]); v=imm(toks[2])
            if rn in regval and v is not None: regval[dst]=(regval[rn]+(v if m=='add' else -v))&wid
            elif dst is not None: regval.pop(dst,None)
        elif m=='orr' and len(toks)==3:
            rn=reg(toks[1]); v=imm(toks[2])
            if v is not None and (rn is None or rn in regval):
                regval[dst]=((regval.get(rn,0) if rn is not None else 0)|v)&wid
            elif dst is not None: regval.pop(dst,None)
        elif dst is not None:
            regval.pop(dst,None)
        if m in('smc','hvc'):
            snap={r:regval.get(r) for r in range(0,7)}
            sites.append((pc,m,o,snap,list(win)))
    else:
        code.value+=4; size.value-=4; addr.value+=4; regval.clear()

real=[s for s in sites if s[1]=='smc' and s[2].strip() in('#0','0','0x0')]
print(f"{len(sites)} smc/hvc total; {len(real)} are `smc #0`\n")
def fmt(v): return f"{v:#x}" if v is not None else "?"
for pc,m,o,snap,w in real:
    x0=snap.get(0)
    print(f"@ {pc:#x}  {m} {o}   x0(fnid)={fmt(x0)}  x1={fmt(snap.get(1))}  x2={fmt(snap.get(2))}  x3={fmt(snap.get(3))}")
    for a,mm,oo in w[:-1]: print(f"      {a:#x}: {mm} {oo}")
    print()
# also dump non-#0 smc/hvc for completeness
other=[s for s in sites if s not in real]
print(f"\n---- {len(other)} other smc/hvc (non-#0 imm, likely data-as-code false hits) ----")
for pc,m,o,snap,w in other[:8]:
    print(f"@ {pc:#x}  {m} {o}  x0={fmt(snap.get(0))}")
