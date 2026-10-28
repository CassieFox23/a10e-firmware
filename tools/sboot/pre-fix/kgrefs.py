# pre-fix: forms ADRP pages from file offsets (phase 0), so its "KG gate" refs land 2 KB off - kept for the record, see A10e-teardown.md "How it was done"
import sys, struct
data=open(sys.argv[1],"rb").read(); n=len(data)
def w(fo): return struct.unpack_from("<I",data,fo)[0]
def sx(v,b): return v-(1<<b) if v&(1<<(b-1)) else v
def strat(fo):
    s=data[fo:fo+50].split(b"\0")[0]
    try: return s.decode()
    except: return repr(s)
LO,HI=0xff000,0x104000
pend={}
for ifo in range(0,n-4,4):
    W=w(ifo)
    if (W&0x9F000000)==0x90000000:
        rd=W&0x1f; imm=sx(((W>>5)&0x7ffff)<<2|((W>>29)&3),21)
        pend[rd]=((ifo&~0xFFF)+(imm<<12), ifo)
        continue
    if (W&0x7F800000)==0x11000000:   # add imm
        rd=W&0x1f; rn=(W>>5)&0x1f
        if rn in pend:
            sh=12 if (W&0x400000) else 0
            addr=pend[rn][0]+(((W>>10)&0xFFF)<<sh)
            if LO<=addr<HI:
                print(f"code {pend[rn][1]:#08x} (adrp)/{ifo:#08x} (add) -> str@{addr:#08x}: \"{strat(addr)}\"")
