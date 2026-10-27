import sys, struct, bisect
from collections import Counter

path = sys.argv[1]
data = open(path, 'rb').read()
n = len(data)
WINDOW = 0x400000  # sboot is exactly 4 MiB; a self-pointer set spans at most this

vals = []
for off in range(0, n - 8, 4):
    v = struct.unpack_from('<Q', data, off)[0]
    if 0x10000 <= v < 0x100000000:   # plausible 32-bit-space code/data pointer
        vals.append(v)

vals.sort()
best_lo = best_cnt = 0
for i, lo in enumerate(vals):
    k = bisect.bisect_left(vals, lo + WINDOW)
    if k - i > best_cnt:
        best_cnt = k - i
        best_lo = lo

print(f"file size           : {n:#x} ({n} bytes)")
print(f"u64 ptr candidates  : {len(vals)}")
print(f"densest 4MiB window : starts {best_lo:#x}, holds {best_cnt} values")
win = [v for v in vals if best_lo <= v < best_lo + WINDOW]
print(f"window min/max/span : {min(win):#x} / {max(win):#x} / {max(win)-min(win):#x}")
for align in (0x1000, 0x10000, 0x100000, 0x400000):
    print(f"  base aligned {align:#010x} -> {best_lo & ~(align-1):#x}")
print("top 1MiB buckets (addr : count):")
for b, ct in Counter(v >> 20 for v in vals).most_common(8):
    print(f"  {b<<20:#x} : {ct}")
