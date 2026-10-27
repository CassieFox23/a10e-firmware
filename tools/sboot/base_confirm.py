import sys, struct, collections
data=open(sys.argv[1],"rb").read(); n=len(data)
def w(fo): return struct.unpack_from("<I",data,fo)[0]
def is_prologue(W):
    if W==0xD503233F: return True
    if (W&0xFFC07FFF)==0xA9807BFD: return True
    if (W&0xFFC003FF)==0xD10003FF: return True
    return False
# prologues only in the real code region 0x30000..0xd0000
prologues=[fo for fo in range(0x30000,0xd0000,4) if is_prologue(w(fo))]
ptrs=[struct.unpack_from("<Q",data,off)[0] for off in range(0,n-8,4)]
cluster=[p for p in ptrs if 0x8ef00000<=p<0x8f100000]
hist=collections.Counter()
for p in cluster:
    for fo in prologues:
        b=p-fo
        if (b&0xFFF)==0x800 and 0x8ef00000<=b<0x8f100000:
            hist[b]+=1
print(f"prologues in code region: {len(prologues)}, cluster ptrs 0x8ef0-0x8f10: {len(cluster)}")
print("sharp base candidates (ptr->prologue, phase 0x800):")
for b,c in hist.most_common(6): print(f"  base={b:#011x}  hits={c}")
