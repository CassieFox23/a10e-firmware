#!/usr/bin/env python3
# Thread 1: prove sboot embeds the SAME AVB public key that vbmeta.img carries.
# Parse the libavb pubkey blob (vbmeta_pubkey.bin), pull its 512-byte modulus,
# then search the whole sboot.bin for the blob and the modulus. Report every
# offset + sha256. Args: <vbmeta_pubkey.bin> <sboot.bin>
import sys, hashlib, struct
keyf, sbootf = sys.argv[1], sys.argv[2]
key = open(keyf, 'rb').read()
sboot = open(sbootf, 'rb').read()

# AvbRSAPublicKeyHeader: uint32 key_num_bits (BE), uint32 n0inv (BE), then
# modulus (key_num_bits/8), then rr (key_num_bits/8).
key_num_bits, n0inv = struct.unpack('>II', key[:8])
modlen = key_num_bits // 8
modulus = key[8:8+modlen]
print(f"pubkey blob: {len(key)} bytes, key_num_bits={key_num_bits}, modlen={modlen}")
print(f"  blob   sha256 = {hashlib.sha256(key).hexdigest()}")
print(f"  modulus sha256 = {hashlib.sha256(modulus).hexdigest()}")
print(f"  modulus[:8]={modulus[:8].hex()} ...[-8:]={modulus[-8:].hex()}")

def find_all(hay, needle):
    offs, i = [], hay.find(needle)
    while i != -1:
        offs.append(i); i = hay.find(needle, i+1)
    return offs

blob_hits = find_all(sboot, key)
mod_hits = find_all(sboot, modulus)
print(f"\nfull 1032-byte blob found in sboot at: {[hex(x) for x in blob_hits]}")
print(f"512-byte modulus found in sboot at:   {[hex(x) for x in mod_hits]}")
for off in mod_hits:
    # carve the 1032 bytes starting 8 before the modulus (header is 8 bytes)
    start = off - 8
    if start >= 0:
        carved = sboot[start:start+len(key)]
        same = carved == key
        print(f"  @file 0x{start:x}: carved-1032 sha256={hashlib.sha256(carved).hexdigest()} "
              f"{'== vbmeta key' if same else '!= (framing differs)'}")
