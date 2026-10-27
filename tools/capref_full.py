#!/usr/bin/env python3
# Whole-image operand-level adrp+add/adr/ldr ref scan + bl graph (capstone/ctypes).
# Linear decode desyncs on data, but targeted lookups for a specific VA are robust:
# real code refs to an exact address stand out from sparse random false hits.
import sys, ctypes, ctypes.util, re, bisect
from collections import defaultdict
BIN=sys.argv[1]; data=open(BIN,'rb').read(); BASE=0x8f000000; END=len(data)
cs=ctypes.CDLL(ctypes.util.find_library('capstone') or '/usr/lib64/libcapstone.so.5')
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
refs=defaultdict(list); bl=defaultdict(list); regval={}
while size.value>0:
    if cs.cs_disasm_iter(h.value,ctypes.byref(code),ctypes.byref(size),ctypes.byref(addr),ins):
        pc=ins.contents.address; m=ins.contents.mnemonic.decode(); ops=ins.contents.op_str.decode()
        toks=ops.split(','); dst=reg(toks[0]) if toks else None
        if m=='adrp':
            n=hexn.findall(ops)
            if dst is not None and n: regval[dst]=int(n[-1],16)
        elif m=='adr':
            n=hexn.findall(ops)
            if n: refs[int(n[-1],16)].append((pc,'adr'))
            if dst is not None: regval.pop(dst,None)
        elif m in('add','sub') and '#' in ops and len(toks)>=3:
            rn=reg(toks[1]); n=hexn.findall(toks[2])
            if rn in regval and n:
                v=regval[rn]+(int(n[0],16) if m=='add' else -int(n[0],16)); regval[dst]=v
                if m=='add': refs[v].append((pc,'add'))
            elif dst is not None: regval.pop(dst,None)
        elif m.startswith('ld') or m.startswith('st'):
            mb=re.search(r'\[\s*([wx]\d+|sp)([^\]]*)\]',ops)
            if mb:
                base=reg(mb.group(1)); rest=mb.group(2)
                if base in regval:
                    off=hexn.findall(rest); t=regval[base]+(int(off[0],16) if off else 0)
                    refs[t].append((pc,m))
            if m.startswith('ld') and dst is not None: regval.pop(dst,None)
        elif m=='bl':
            n=hexn.findall(ops)
            if n: bl[int(n[0],16)].append(pc)
        elif dst is not None: regval.pop(dst,None)
    else:
        code.value+=4; size.value-=4; addr.value+=4; regval.clear()
entries=sorted(bl.keys())
def enc(a):
    i=bisect.bisect_right(entries,a)-1; return entries[i] if i>=0 else None
def q(va,label):
    s=refs.get(va,[])
    fns=sorted({enc(x) for x,_ in s if enc(x) is not None})
    print(f"  {label} {va:#x}: {len(s)} code ref-site(s); enclosing fn(s): {[hex(x) for x in fns[:10]]}")
    for site,k in sorted(s)[:6]: print(f"       {k} from {site:#x} (fn {enc(site) and hex(enc(site))})")
print(f"scanned whole image; ref targets={len(refs)} bl targets={len(bl)}\n")
print("== THREAD 3: Odin protocol string referrers ==")
for va,l in ((0x8f1037a8,'ODIN'),(0x8f1152c8,'LOKE'),(0x8f1152a0,'DVIF'),(0x8f102558,'PIT'),(0x8f1043ef,'Download')):
    q(va,l)
print("\n== THREAD 2: AVB key + pubkey validator ==")
q(0x8f12b070,'AVB-key')
q(0x8f322410,'AVB-key-2')
pv=0x8f0aa298
print(f"  pubkey-validator {pv:#x}: {len(bl.get(pv,[]))} direct BL caller-site(s); caller fn(s): {[hex(enc(x)) for x in bl.get(pv,[])[:10] if enc(x)]}")
print("\n== THREAD 2: rollback string referrers ==")
for va,l in ((0x8f0f6b22,'rollback'),(0x8f108d37,'Rollback')):
    q(va,l)
