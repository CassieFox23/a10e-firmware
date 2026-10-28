# pre-fix: only votes for page-aligned bases (phase 0), so it can never find the real 0x8ef9e800 - kept for the record; use tools/pin_base.py
import sys, struct, collections
data = open(sys.argv[1], "rb").read()
n = len(data)
# all aligned absolute pointers in a wide range
ptrs = {}
for off in range(0, n-8, 4):
    v = struct.unpack_from("<Q", data, off)[0]
    if 0x88000000 <= v < 0x98000000:
        ptrs.setdefault(v, []).append(off)
known = {0x102928:"KG locked", 0x1009a8:"installment", 0x100a08:"CC Mode",
         0x1100c0:"vbmeta err fmt", 0x110098:"vbmeta err", 0x110178:"unsupported AVB",
         0x118d60:"libjpeg copyright", 0x102780:"TEEGRIS noarg"}
# for each known string fo, which pointer values would imply which base, and does that pointer exist?
votes = collections.Counter()
for sfo, name in known.items():
    hits = []
    for v in ptrs:
        b = v - sfo
        if (b & 0xFFF) == 0 and 0x88000000 <= b < 0x98000000:
            hits.append(b)
            votes[b] += 1
    print(f"{name:18} fo={sfo:#08x}: bases implied by a real pointer: {[hex(h) for h in sorted(set(hits))]}")
print("\nbases supported by >=2 distinct known strings:")
for b, c in votes.most_common(10):
    if c >= 2: print(f"  base={b:#011x}  strings_agreeing={c}")
