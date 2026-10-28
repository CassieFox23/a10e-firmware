# pre-fix: assumes base 0x80000000 and annotates strings from file offsets, so its labels are wrong - kept for the record; load at 0x8ef9e800 instead
import sys
from capstone import Cs, CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN
data=open(sys.argv[1],"rb").read()
start=int(sys.argv[2],16); end=int(sys.argv[3],16)
base=0x80000000
md=Cs(CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN)
md.detail=False
# string table for annotating adrp+add targets
def strat(fo):
    if 0<=fo<len(data):
        s=data[fo:fo+60].split(b"\0")[0]
        try: return s.decode()
        except: return None
    return None
code=data[start:end]
pend={}  # reg-> adrp page (file offset)
for ins in md.disasm(code, base+start):
    fo=ins.address-base
    note=""
    m=ins.mnemonic; op=ins.op_str
    if m=="adrp":
        parts=op.split(", ")
        reg=parts[0]; page=int(parts[1].lstrip("#"),16)-base  # capstone already computed target page VA
        pend[reg]=page
    elif m=="add" and "," in op:
        p=op.split(", ")
        if len(p)==3 and p[1] in pend and p[2].startswith("#"):
            tgt=pend[p[1]]+int(p[2][1:],16)
            s=strat(tgt)
            if s is not None: note=f"   ; -> \"{s}\""
    print(f"{ins.address:#010x} ({fo:#07x}): {m:<8} {op}{note}")
