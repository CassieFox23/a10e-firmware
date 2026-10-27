import sys, struct
data = open(sys.argv[1], "rb").read(); n=len(data)
def w(fo): return struct.unpack_from("<I", data, fo)[0]
def sx(v,b): return v-(1<<b) if v&(1<<(b-1)) else v
targets={0x102928:"KG locked",0x1009a8:"installment",0x100a08:"CC Mode",
         0x1100c0:"vbmeta err fmt",0x110178:"unsupported AVB",0x110098:"vbmeta err"}
# pass1: record ADRP results (reg->page) and look ahead up to 16 instrs for ADD/LDR building a target
res={t:[] for t in targets}
for ifo in range(0,n-4,4):
    W=w(ifo)
    if (W&0x9F000000)!=0x90000000: continue
    rd=W&0x1f; imm=sx(((W>>5)&0x7ffff)<<2|((W>>29)&3),21)
    page=(ifo&~0xFFF)+(imm<<12)
    for k in range(1,17):
        j=ifo+4*k
        if j>n-4: break
        W2=w(j)
        # add xD, xRd, #imm12 (+ optional lsl#12)
        if (W2&0x7F800000)==0x11000000 and ((W2>>5)&0x1f)==rd:
            sh=12 if (W2&0x400000) else 0
            addr=page+(((W2>>10)&0xFFF)<<sh)
            if addr in targets: res[addr].append((hex(ifo),"add",hex(j)))
        # if rd reused as dest of another adrp or overwritten, stop
        if (W2&0x9F00001F)==(0x90000000|rd): break
        if (W2&0x1f)==rd and (W2&0x7F800000)==0x11000000: break
for t,name in targets.items():
    print(f"{name:16} fo={t:#08x}: {res[t][:6]}")
