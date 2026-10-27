#!/usr/bin/env python3
import sys, struct, json, math
from collections import Counter

BIN = sys.argv[1]; REFS = sys.argv[2]
data = open(BIN, 'rb').read(); n = len(data); BASE = 0x8f000000
J = json.load(open(REFS))
refs = {int(k, 16): v for k, v in J['refs'].items()}          # target -> [(site,kind)]
bl   = {int(k, 16): v for k, v in J['bl'].items()}            # target -> [callsites]
entries = sorted(bl.keys())                                   # approx function entries (BL targets)

def enclosing(site):
    import bisect
    i = bisect.bisect_right(entries, site) - 1
    return entries[i] if i >= 0 else None

def cluster(lo, hi, label):
    print(f"\n==== {label}: BL-called functions in [{lo:#x},{hi:#x}) and their callers ====")
    tgs = sorted(t for t in bl if lo <= t < hi)
    for t in tgs:
        callers = bl[t]
        print(f"  fn {t:#010x}: {len(callers)} caller site(s)")
        for c in sorted(callers)[:10]:
            print(f"      called from {c:#010x}  (in fn {enclosing(c) and hex(enclosing(c))})")

# ---------- Q2: AES cluster ----------
cluster(0x8f0f5000, 0x8f0f8000, "Q2 AES/crypto cluster ~0x8f0f6100")

# ---------- Q4: libjpeg cluster + one level up ----------
cluster(0x8f116000, 0x8f119000, "Q4 libjpeg-turbo cluster ~0x8f118d60")

print("\n==== Q4: partition / image name strings and who references them ====")
names = [b"PARAM", b"param", b"up_param", b"UP_PARAM", b"logo", b"LOGO", b"splash",
         b"SPLASH", b"download", b"DOWNLOAD", b"BOOT", b"boot.img", b"sw_path",
         b"/dev/block", b"mmc", b"ufs", b"GPT", b"sboot", b"LOADER", b"jpeg", b"jpg",
         b"image", b"IMAGE", b"bootlogo", b"kernel", b"RECOVERY", b"recovery"]
for name in names:
    i = data.find(name)
    sites_total = 0
    first = None
    locs = []
    while i != -1 and len(locs) < 50:
        va = BASE + i
        r = refs.get(va, [])
        if r:
            sites_total += len(r)
            if first is None:
                first = (va, r[0])
        locs.append(va)
        i = data.find(name, i + 1)
    if first:
        fv, (s, k) = first
        print(f"  {name.decode():10s}: {len(locs)} occurrence(s); string@{fv:#x} referenced from {s:#x} [{k}] (total refd sites {sites_total})")

# ---------- Q3: entropy / structure stats ----------
def stats(off, size, label):
    b = data[off:off+size]
    N = len(b)
    cnt = Counter(b)
    H = -sum((c/N)*math.log2(c/N) for c in cnt.values())
    exp = N/256
    chi = sum((cnt.get(i,0)-exp)**2/exp for i in range(256))
    # serial correlation coefficient
    x = b; m = sum(x)/N
    num = sum((x[i]-m)*(x[(i+1)%N]-m) for i in range(N))
    den = sum((v-m)**2 for v in x)
    scc = num/den if den else 0
    # duplicate 16-byte blocks
    blocks = [bytes(b[i:i+16]) for i in range(0, N-15, 16)]
    bc = Counter(blocks); dups = sum(v-1 for v in bc.values() if v > 1)
    printable = sum(1 for v in b if 32 <= v < 127)/N
    zero_bytes = 256 - len(cnt)
    # sliding window entropy (8 windows)
    win = []
    w = N//8
    for i in range(8):
        wb = b[i*w:(i+1)*w]; wc = Counter(wb); WN = len(wb)
        win.append(-sum((c/WN)*math.log2(c/WN) for c in wc.values()))
    print(f"\n==== Q3 {label}: file@{off:#x} va@{BASE+off:#x} size {N} (0x{N:x}) ====")
    print(f"  size % 16         : {N % 16}")
    print(f"  Shannon entropy   : {H:.4f} bits/byte")
    print(f"  chi-square(255 df): {chi:.1f}   (uniform/random ~255; compressed/structured >> )")
    print(f"  serial corr coef  : {scc:+.4f}   (near 0 = random; |.|>~.05 = structure)")
    print(f"  printable ASCII   : {printable*100:.1f}%   unused byte values: {zero_bytes}/256")
    print(f"  16B blocks        : {len(blocks)} total, {dups} duplicate")
    print(f"  head 32B          : {b[:32].hex()}")
    print(f"  tail 16B          : {b[-16:].hex()}")
    print(f"  window entropy x8 : {' '.join(f'{v:.2f}' for v in win)}")

stats(0x3400, 0x18000, "entropy-A")
stats(0x12c800, 0x16800, "entropy-B")
