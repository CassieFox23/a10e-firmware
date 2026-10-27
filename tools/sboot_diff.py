#!/usr/bin/env python3
import sys, hashlib, math, re

AVB_KEY_OFFSETS = [0x12b070, 0x322410]
AVB_KEY_LEN = 1032
ENTROPY_A = (0x3400, 0x1b400)
MARKERS = [
    ("KG lock", [b"KG locked", b"Knox Guard", b"kg_state", b"KNOX TEST", b"eng token"]),
    ("AVB", [b"AVB 2.0", b"avb_version", b"libavb", b"vbmeta", b"Public key used to sign data rejected"]),
    ("rollback", [b"rollback", b"SW REV", b"Unsupported Version", b"anti", b"rpmb"]),
    ("build", [b"A102U", b"SRPSB", b"SignerVer02"]),
]

def sha(b): return hashlib.sha256(b).hexdigest()

def entropy(b):
    if not b: return 0.0
    h = [0]*256
    for x in b: h[x]+=1
    n=len(b); e=0.0
    for c in h:
        if c:
            p=c/n; e-=p*math.log2(p)
    return e

def clusters(diffs, gap=16):
    runs=[]
    if not diffs: return runs
    s=p=diffs[0]
    for o in diffs[1:]:
        if o-p>gap:
            runs.append((s,p)); s=o
        p=o
    runs.append((s,p))
    return runs

def ascii_at(buf, lo, hi):
    seg=buf[lo:hi+1]
    return "".join(chr(c) if 32<=c<127 else "." for c in seg)

def strings(buf, pat, minlen=6):
    out=set()
    for m in re.finditer(rb"[\x20-\x7e]{%d,}"%minlen, buf):
        s=m.group()
        if pat.search(s): out.add(s.decode("latin1"))
    return out

def main():
    if len(sys.argv)!=3:
        print("usage: sboot_diff.py OLD_sboot.bin NEW_sboot.bin"); sys.exit(2)
    pa,pb=sys.argv[1],sys.argv[2]
    a=open(pa,"rb").read(); b=open(pb,"rb").read()
    print(f"=== sboot diff ===\nA  {pa}\n   size {len(a):,}  sha256 {sha(a)}\nB  {pb}\n   size {len(b):,}  sha256 {sha(b)}")

    n=min(len(a),len(b))
    diffs=[i for i in range(n) if a[i]!=b[i]]
    tail=abs(len(a)-len(b))
    print(f"\n-- byte diff --\ncommon {n:,} B, differing {len(diffs):,} ({100*len(diffs)/n:.4f}%); size delta {tail} B")
    runs=clusters(diffs)
    print(f"{len(runs)} differing region(s):")
    for s,e in runs:
        ln=e-s+1
        note=""
        if ln<=64:
            aa,bb=ascii_at(a,s,e),ascii_at(b,s,e)
            if re.search(r"[A-Za-z0-9]{3}", aa+bb): note=f"  A='{aa}' B='{bb}'"
        print(f"  0x{s:06x}-0x{e:06x}  {ln:>6} B{note}")

    print("\n-- AVB key blobs --")
    for off in AVB_KEY_OFFSETS:
        ka,kb=a[off:off+AVB_KEY_LEN],b[off:off+AVB_KEY_LEN]
        print(f"  @0x{off:06x}: A {sha(ka)[:16]}  B {sha(kb)[:16]}  {'IDENTICAL' if ka==kb else 'CHANGED'}")

    lo,hi=ENTROPY_A
    ea,eb=a[lo:hi],b[lo:hi]
    print(f"\n-- entropy-A @0x{lo:04x}-0x{hi:04x} --")
    print(f"  A sha {sha(ea)[:16]} H={entropy(ea):.3f}  B sha {sha(eb)[:16]} H={entropy(eb):.3f}  {'IDENTICAL' if ea==eb else 'CHANGED'}")

    print("\n-- marker strings (A | B) --")
    for name,pats in MARKERS:
        pat=re.compile(b"|".join(re.escape(p) for p in pats))
        sa,sb=strings(a,pat),strings(b,pat)
        only_a=sorted(sa-sb); only_b=sorted(sb-sa)
        print(f"  {name}: {len(sa)} | {len(sb)} strings; {len(sa&sb)} shared")
        for s in only_a[:12]: print(f"      A-only: {s}")
        for s in only_b[:12]: print(f"      B-only: {s}")

if __name__=="__main__":
    main()
