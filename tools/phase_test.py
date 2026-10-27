#!/usr/bin/env python3
# Decisive test: do ADRP+ADD targets land on string starts better under page phase 0 or 0x800?
# ADRP target_VA = (PC & ~0xFFF) + imm<<12; with base B+phi (B page-aligned), file_off of an
# adrp(off_a)+add(k) target = (P0-B) + delta - phi, where P0 is the phi=0 page-abs and
# delta = ((phi+off_a)&~0xFFF) - (off_a&~0xFFF).
import sys, ctypes, ctypes.util, re
BIN=sys.argv[1]; data=open(BIN,'rb').read(); B=0x8ef9e000; END=len(data)
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
def is_strstart(S):
    if S<0 or S+6>len(data): return False
    if S>0 and data[S-1] not in (0,): return False
    return all(0x20<=data[S+i]<0x7e for i in range(6))
regpage={}; pairs=[]
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
                P0,off_a=regpage[rn]; k=int(n[0],16); pairs.append((P0,off_a,k))
            if dst is not None: regpage.pop(dst,None)
        elif dst is not None:
            regpage.pop(dst,None)
    else:
        code.value+=4; size.value-=4; addr.value+=4; regpage.clear()
def fileoff(P0,off_a,k,phi):
    delta=((phi+off_a)&~0xFFF)-(off_a&~0xFFF)
    return (P0-B)+delta+k-phi
res={}
for phi in (0,0x800):
    hits=0; samples=[]
    for P0,off_a,k in pairs:
        S=fileoff(P0,off_a,k,phi)
        if is_strstart(S):
            hits+=1
            if len(samples)<14:
                end=S
                while end<len(data) and 0x20<=data[end]<0x7e and end-S<48: end+=1
                samples.append((S,data[S:end].decode('latin1')))
    res[phi]=(hits,samples)
    print(f"\n=== phase 0x{phi:x}: {len(pairs)} ADRP+ADD pairs, {hits} land on a string start ===")
    for S,s in samples[:14]: print(f"    file 0x{S:x}: {s!r}")
print(f"\nSUMMARY: phase0 hits={res[0][0]}  phase0x800 hits={res[0x800][0]}  total pairs={len(pairs)}")
