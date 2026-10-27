#!/usr/bin/env python3
# Hunt where target pointers are materialised (movz/movk/adrp+add) and stored/used.
import sys, ctypes, ctypes.util, re
from collections import deque

BIN = sys.argv[1]
data = open(BIN, 'rb').read(); BASE = 0x8ef9e800; CODE_END = 0xf3000
TARGETS = {0x8f073e3c, 0x8f073a70, 0x8f073ae8, 0x8f073c24}

cs = ctypes.CDLL(ctypes.util.find_library('capstone') or '/usr/lib64/libcapstone.so.5')
class I(ctypes.Structure):
    _fields_ = [("id", ctypes.c_uint), ("address", ctypes.c_uint64), ("size", ctypes.c_uint16),
                ("bytes", ctypes.c_uint8*24), ("mnemonic", ctypes.c_char*32),
                ("op_str", ctypes.c_char*160), ("detail", ctypes.c_void_p)]
cs.cs_open.argtypes=[ctypes.c_int,ctypes.c_int,ctypes.POINTER(ctypes.c_size_t)]
cs.cs_malloc.argtypes=[ctypes.c_size_t]; cs.cs_malloc.restype=ctypes.POINTER(I)
cs.cs_disasm_iter.argtypes=[ctypes.c_size_t,ctypes.POINTER(ctypes.c_void_p),
    ctypes.POINTER(ctypes.c_size_t),ctypes.POINTER(ctypes.c_uint64),ctypes.POINTER(I)]
cs.cs_disasm_iter.restype=ctypes.c_bool
h=ctypes.c_size_t(); cs.cs_open(1,0,ctypes.byref(h)); ins=cs.cs_malloc(h.value)
buf=ctypes.create_string_buffer(data[:CODE_END],CODE_END)
code=ctypes.cast(buf,ctypes.c_void_p); size=ctypes.c_size_t(CODE_END); addr=ctypes.c_uint64(BASE)

def reg(t):
    t=t.strip(); m=re.match(r'^[wx](\d+)$',t); return int(m.group(1)) if m else None
hexn=re.compile(r'0x[0-9a-fA-F]+')
regval={}; window=deque(maxlen=7); hits=[]
while size.value>0:
    if cs.cs_disasm_iter(h.value,ctypes.byref(code),ctypes.byref(size),ctypes.byref(addr),ins):
        pc=ins.contents.address; m=ins.contents.mnemonic.decode(); ops=ins.contents.op_str.decode()
        window.append((pc,m,ops))
        toks=ops.split(','); dst=reg(toks[0]) if toks else None
        def lsl(tok):
            mm=re.search(r'lsl\s*#(\d+)',tok); return int(mm.group(1)) if mm else 0
        if m=='adrp':
            n=hexn.findall(ops);  regval[dst]=int(n[-1],16) if (dst is not None and n) else regval.get(dst)
        elif m in('add','sub') and '#'in ops and len(toks)>=3:
            rn=reg(toks[1]); n=hexn.findall(toks[2])
            if rn in regval and n: regval[dst]=regval[rn]+(int(n[0],16) if m=='add' else -int(n[0],16))
            elif dst is not None: regval.pop(dst,None)
        elif m=='movz':
            n=hexn.findall(ops);
            if dst is not None and n: regval[dst]=int(n[0],16)<<lsl(ops)
        elif m=='movk':
            n=hexn.findall(ops); sh=lsl(ops)
            if dst is not None and n: regval[dst]=(regval.get(dst,0)&~(0xffff<<sh))|(int(n[0],16)<<sh)
        elif m=='mov' and len(toks)==2:
            rn=reg(toks[1]);
            if rn in regval: regval[dst]=regval[rn]
            elif dst is not None: regval.pop(dst,None)
        elif dst is not None:
            regval.pop(dst,None)
        # detect target materialised in dst, or present in op text
        got=None
        if dst is not None and regval.get(dst) in TARGETS: got=('built',regval[dst],dst)
        else:
            for t in TARGETS:
                if f'{t:#x}' in ops: got=('textref',t,None); break
        # detect store of a reg holding a target
        if m.startswith('st'):
            src=reg(toks[0])
            if src in regval and regval[src] in TARGETS:
                mb=re.search(r'\[\s*([wx]\d+|sp)([^\]]*)\]',ops); got=('STORE',regval[src],None)
        if got:
            hits.append((pc,got,list(window)))
    else:
        code.value+=4; size.value-=4; addr.value+=4; regval.clear()

print(f"materialisation/use sites for {sorted(hex(t) for t in TARGETS)}:\n")
for pc,(kind,val,rd),win in hits:
    print(f"@ {pc:#x}  {kind} {val:#x}")
    for a,m,o in win: print(f"      {a:#x}: {m} {o}")
    print()
print(f"total sites: {len(hits)}")
