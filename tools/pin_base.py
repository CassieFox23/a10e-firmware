#!/usr/bin/env python3
# Re-derive sboot's load base. Phase is known (base & 0xFFF == 0x800). High bits must come
# from ABSOLUTE anchors: stored 64-bit pointers that point at known landmarks (string starts
# and function entries). Vote base = pointer_value - landmark_file_offset; true base peaks.
import sys, ctypes, ctypes.util, re, struct
from collections import Counter, defaultdict
BIN=sys.argv[1]; data=open(BIN,'rb').read(); N=len(data); SCAN=0x8ef9e800
# ---- landmarks: string starts ----
strstarts=set()
i=0
while i < N-6:
    if (i==0 or data[i-1]==0) and all(0x20<=data[i+j]<0x7e for j in range(6)):
        strstarts.add(i)
    i+=1
# ---- landmarks: function entries (BL targets as file offsets; base cancels) ----
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
buf=ctypes.create_string_buffer(data[:N],N); code=ctypes.cast(buf,ctypes.c_void_p)
size=ctypes.c_size_t(N); addr=ctypes.c_uint64(SCAN)
hexn=re.compile(r'0x[0-9a-fA-F]+'); funcs=set()
while size.value>0:
    if cs.cs_disasm_iter(h.value,ctypes.byref(code),ctypes.byref(size),ctypes.byref(addr),ins):
        m=ins.contents.mnemonic.decode(); o=ins.contents.op_str.decode()
        if m=='bl':
            n=hexn.findall(o)
            if n: funcs.add(int(n[0],16)-SCAN)
    else:
        code.value+=4; size.value-=4; addr.value+=4
landmarks = strstarts | {f for f in funcs if 0<=f<N}
print(f"landmarks: {len(strstarts)} string starts + {len(funcs)} fn entries = {len(landmarks)} total")
# index landmarks by low-12 bits
by_res=defaultdict(list)
for L in landmarks: by_res[L & 0xFFF].append(L)
# ---- pointers ----
votes=Counter(); examples=defaultdict(list)
nptr=0
for off in range(0, N-8, 8):
    V=struct.unpack_from('<Q',data,off)[0]
    if not (0x40000000 <= V < 0x100000000): continue
    nptr+=1
    res=(V - 0x800) & 0xFFF
    for L in by_res.get(res, ()):
        B=V-L
        if B & 0xFFF != 0x800: continue
        if not (0x40000000 <= B < 0x100000000): continue
        votes[B]+=1
        if len(examples[B])<6: examples[B].append((off,V,L))
print(f"candidate pointers in window: {nptr}")
print("\ntop base candidates (base = ptr - landmark, phase 0x800):")
for B,c in votes.most_common(12):
    print(f"  base {B:#x}: {c} votes")
if votes:
    B,c=votes.most_common(1)[0]
    print(f"\n=== winner {B:#x} ({c} votes) sample pointer->landmark ===")
    def cstr(F):
        e=F
        while e<N and 0x20<=data[e]<0x7e and e-F<40: e+=1
        return data[F:e].decode('latin1') if e>F else '<fn>'
    for off,V,L in examples[B]:
        kind = 'str' if L in strstarts else 'fn'
        s = cstr(L) if L in strstarts else f'fn@file_0x{L:x}'
        print(f"  ptr@file_0x{off:x} = {V:#x} -> file_0x{L:x} [{kind}] {s!r}")
