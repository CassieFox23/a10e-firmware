#!/usr/bin/env python3
# Thread 3: parse cm.bin (CryptoManagerV40 LDFW container) first-hand.
# Args: <cm.bin>
import sys, struct, hashlib, re
data = open(sys.argv[1], 'rb').read()
N = len(data)
print(f"cm.bin size: {N} (0x{N:x})")

MAGIC = 0x10adab1e
# --- scan for all LDFW-entry magics ---
magics = [m.start() for m in re.finditer(struct.pack('<I', MAGIC), data)]
print(f"\n0x10adab1e magic at offsets: {[hex(x) for x in magics]}")

def u32(o): return struct.unpack_from('<I', data, o)[0]
def name_at(o):
    raw = data[o:o+32]
    nul = raw.find(b'\x00')
    return raw[:nul if nul>=0 else 32].decode('latin1', 'replace')

for base in magics[:12]:
    words = [u32(base + 4*i) for i in range(12)]
    nm = name_at(base + 0x30)
    print(f"\n entry @0x{base:x}:")
    print(f"   words[0..11]: {' '.join('0x%08x'%w for w in words)}")
    print(f"   name@+0x30  : {nm!r}")

# --- ASCII name/string inventory (>=5 printable) ---
print("\n=== notable strings (CryptoManager/RPMB/Signer/LDFW/version) ===")
for m in re.finditer(rb'[\x20-\x7e]{5,}', data):
    s = m.group().decode('latin1')
    if any(k in s for k in ('CryptoManager','srpmb','Signer','LDFW','RPMB','VERSION','version','ldfw','v40','V40','teegris','Teegris','TEEGRIS','exynos','SB2','cm_')):
        print(f"   0x{m.start():06x}: {s!r}")

# --- SMC fnid hunt: raw LE + movk-encoded (0xc200 in high half) ---
print("\n=== SMC fnid search ===")
for fnid in (0xc2001014, 0xc2001018, 0xc2003818, 0xc200101c, 0xc200101d, 0xc2001013):
    hits = [m.start() for m in re.finditer(struct.pack('<I', fnid), data)]
    if hits:
        print(f"   raw {hex(fnid)} (LE word) at: {[hex(x) for x in hits[:8]]}{' ...' if len(hits)>8 else ''}")
# AArch64 movk w?, #0xc200, lsl#16 -> encoding bits: 0x72A84000 | (imm16<<5) | rd ; imm16=0xc200
# movk Wd,#0xc200,lsl#16 = 0x72980000 | (0xc200<<5)&.. ; simpler: search for the imm16 0xc200 appearing
# in a movk by scanning for bytes that encode movk with hw=1 imm16=0xc200. Do a coarse scan for 0xc200
# as a halfword anywhere (candidate movk immediates), report counts only.
hw = struct.pack('<H', 0xc200)
c200_hits = [m.start() for m in re.finditer(hw, data)]
print(f"   halfword 0xc200 appears {len(c200_hits)} times (movk-immediate candidates; need disasm to confirm)")

# --- tie cm.bin to vbmeta 'cm' hash descriptor ---
cm_salt = "1c915614158a9cfc08ad3b30e06a4ed71659c9fe78864b5be5cd28bc3d8c04c2"
cm_digest = "989f62a54c824a34c15c207f00529f062de8af36525b0eff9ca3f24eb697c876"
cm_imgsize = 4112912
h = hashlib.sha256(); h.update(bytes.fromhex(cm_salt)); h.update(data[:cm_imgsize])
calc = h.hexdigest()
print("\n=== cm.bin vs vbmeta 'cm' hash descriptor ===")
print(f"   hashed length {cm_imgsize} of {N}")
print(f"   vbmeta cm digest : {cm_digest}")
print(f"   computed sha256  : {calc}")
print(f"   MATCH            : {calc == cm_digest}")
