#!/usr/bin/env python3
# Thread 2: tie boot.img to vbmeta's "boot" hash descriptor + read load addrs.
# Args: <boot.img>
import sys, hashlib, struct
img = open(sys.argv[1], 'rb').read()
print(f"boot.img total size: {len(img)}")

# --- vbmeta "boot" hash descriptor (from avbtool info_image on vbmeta.img) ---
salt_hex = "3a95a06409b24d0eb00e5cd64b5c323e50186fb2b0b1bdff54b12df363e80a15"
vb_digest = "79fb7164d409a4e3dc8aeb171705df6494505fe65bf265dbc09e6248e0b88722"
vb_imgsize = 29315616
salt = bytes.fromhex(salt_hex)

# AVB hash descriptor digest = H(salt || image[:Image Size])
h = hashlib.sha256(); h.update(salt); h.update(img[:vb_imgsize])
calc = h.hexdigest()
print("\n=== Thread 2 tie: boot.img vs vbmeta 'boot' hash descriptor ===")
print(f"  hashed length   : {vb_imgsize} (of {len(img)} total; rest is padding)")
print(f"  salt            : {salt_hex}")
print(f"  vbmeta digest   : {vb_digest}")
print(f"  computed sha256 : {calc}")
print(f"  MATCH           : {calc == vb_digest}")

# --- Android boot image header (v1) ---
assert img[:8] == b'ANDROID!', f"bad magic {img[:8]!r}"
(ksize, kaddr, rsize, raddr, ssize, saddr, tags_addr, page_size,
 hdr_ver, os_ver) = struct.unpack_from('<10I', img, 8)
name = img[48:48+16].rstrip(b'\x00').decode('latin1')
cmdline = img[64:64+512].rstrip(b'\x00').decode('latin1')
print("\n=== Android boot header ===")
print(f"  header_version : {hdr_ver}")
print(f"  page_size      : {page_size}")
print(f"  kernel_size    : {ksize}   kernel_addr : 0x{kaddr:08x}")
print(f"  ramdisk_size   : {rsize}   ramdisk_addr: 0x{raddr:08x}")
print(f"  second_size    : {ssize}   second_addr : 0x{saddr:08x}")
print(f"  tags_addr      : 0x{tags_addr:08x}")
print(f"  name           : {name!r}")
print(f"  cmdline        : {cmdline!r}")
print("\n=== 0x80080000 hand-off tie (round 2) ===")
print(f"  round-2 boot handler jumps to fixed 0x80080000 (DRAM 0x80000000 + 0x80000 TEXT_OFFSET)")
print(f"  header kernel_addr = 0x{kaddr:08x}  -> {'MATCHES 0x80080000' if kaddr==0x80080000 else 'differs; sboot uses its own fixed addr'}")
