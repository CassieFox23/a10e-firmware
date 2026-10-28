#!/usr/bin/env python3
# Re-resolve ADRP+ADD references under the CORRECT page phase 0x800. Work in FILE OFFSETS
# (base/VA is now uncertain). Answer: entropy-A refs, AVB-key refs, and what the KG/PIT code
# near file 0x6f000-0x72000 actually points at.
import sys, ctypes, ctypes.util, re
from collections import defaultdict
BIN=sys.argv[1]; data=open(BIN,'rb').read(); B=0x8ef9e000; END=len(data); PHI=0x800
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
size=ctypes.c_size_t(END); addr=ctypes.c_uint64(B)
hexn=re.compile(r'0x[0-9a-fA-F]+')
def reg(t):
    t=t.strip(); m=re.match(r'^[wx](\d+)$',t); return int(m.group(1)) if m else None
def foff(P0,off_a,k):
    delta=((PHI+off_a)&~0xFFF)-(off_a&~0xFFF)
    return (P0-B)+delta+k-PHI
regpage={}; refs=defaultdict(list)
while size.value>0:
    if cs.cs_disasm_iter(h.value,ctypes.byref(code),ctypes.byref(size),ctypes.byref(addr),ins):
        pc=ins.contents.address; m=ins.contents.mnemonic.decode(); o=ins.contents.op_str.decode()
        toks=o.split(','); dst=reg(toks[0]) if toks else None
        if m=='adrp':
            n=hexn.findall(o)
            if dst is not None and n: regpage[dst]=(int(n[-1],16),pc-B)
        elif m=='add' and '#' in o and len(toks)>=3:
            rn=reg(toks[1]); n=hexn.findall(toks[2])
            if rn in regpage and n:
                P0,off_a=regpage[rn]; S=foff(P0,off_a,int(n[0],16))
                refs[S].append(pc-B)
            if dst is not None: regpage.pop(dst,None)
        elif dst is not None: regpage.pop(dst,None)
    else:
        code.value+=4; size.value-=4; addr.value+=4; regpage.clear()
def cstr(S,maxlen=60):
    e=S
    while e<len(data) and 0x20<=data[e]<0x7e and e-S<maxlen: e+=1
    return data[S:e].decode('latin1')
print("=== entropy-A refs under phase 0x800 (file 0x3400..0x1b400) ===")
ea=sorted(s for s in refs if 0x3400<=s<0x1b400)
print(f"  {len(ea)} distinct target(s) referenced inside entropy-A; sample: {[hex(x) for x in ea[:8]]}")
print("\n=== AVB key refs (file 0x12b070, 0x322410) ===")
for t in (0x12b070,0x322410):
    print(f"  0x{t:x}: {len(refs.get(t,[]))} ref-site(s) {[hex(x) for x in refs.get(t,[])[:6]]}")
print("\n=== what the code at file 0x6f000..0x72000 references (string targets only) ===")
seen=set()
for S,sites in sorted(refs.items()):
    for site in sites:
        if 0x6f000<=site<0x72000 and 0x20<=data[S] if S<len(data) else False:
            txt=cstr(S)
            if len(txt)>=4 and (site,S) not in seen:
                seen.add((site,S)); print(f"  site 0x{site:x} -> 0x{S:x}: {txt!r}")
print("\n=== locate key strings (raw byte offsets) ===")
for kw in (b'kFileIdentifier',b'pit_check_integrity',b'guid_part',b'update_guid',b'partition_table',
           b'KG locked',b'Custom binary',b'not allowed to be flashed',b'rp skip checking',
           b'Public key used to sign',b'AVB pubkey is not matched'):
    i=data.find(kw)
    print(f"  {kw.decode(errors='replace'):28s}: {'file 0x%x'%i if i>=0 else 'not found'}")
# what references the 0x12349876 comparison site region specifically
print("\n=== refs made by code at 0x71900..0x719c0 and 0x6f880..0x70a80 ===")
for lo,hi,lbl in ((0x71900,0x719c0,'around 0x71958'),(0x6f880,0x70a80,'KG-handler window')):
    tgts=[(site,S) for S,sites in refs.items() for site in sites if lo<=site<hi]
    for site,S in sorted(tgts)[:12]:
        print(f"  [{lbl}] 0x{site:x} -> 0x{S:x}: {cstr(S)!r}")
