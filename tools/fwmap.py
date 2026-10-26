import sys, os, re, json, struct, subprocess, tarfile
fw = sys.argv[1]; out = sys.argv[2]
def ident(h):
    if h[:4] == b"\x3a\xff\x26\xed":
        blk, = struct.unpack_from("<I", h, 12); tot, = struct.unpack_from("<I", h, 16)
        return "Android sparse image", blk * tot
    if h[:8] == b"ANDROID!": return "Android boot image (kernel + ramdisk)", None
    if h[:4] == b"AVB0": return "AVB vbmeta (signed hash list)", None
    if h[:4] == b"\xd0\x0d\xfe\xed": return "device tree blob (DTB)", None
    if h[:4] == b"\x76\x56\x34\x12" or h[:4] == b"PIT\x00": return "PIT", None
    if len(h) > 0x43a and h[0x438:0x43a] == b"\x53\xef": return "ext4 filesystem", None
    if h[257:262] == b"ustar": return "tar archive", None
    if h[:2] == b"PK": return "zip", None
    return "raw / unknown", None
rows = []
for t in sorted(f for f in os.listdir(fw) if f.endswith(".tar.md5")):
    bundle = t.split("_A102U")[0]
    with tarfile.open(os.path.join(fw, t)) as tf:
        for m in tf.getmembers():
            if not m.isfile(): continue
            r = {"bundle": bundle, "file": m.name, "packed": m.size}
            if m.name.endswith(".lz4"):
                p1 = subprocess.Popen(["tar", "-xOf", os.path.join(fw, t), m.name], stdout=subprocess.PIPE)
                p2 = subprocess.Popen(["lz4", "-dc"], stdin=p1.stdout, stdout=subprocess.PIPE); p1.stdout.close()
                head = b""; n = 0
                while True:
                    c = p2.stdout.read(1 << 22)
                    if not c: break
                    if len(head) < 8192: head += c[:8192 - len(head)]
                    n += len(c)
                p2.wait(); p1.wait()
                kind, sparse_full = ident(head)
                r.update(unpacked=n, kind=kind, full=sparse_full)
            else:
                f = tf.extractfile(m); head = f.read(8192)
                kind, sparse_full = ident(head); r.update(unpacked=m.size, kind=kind, full=sparse_full)
            rows.append(r)
json.dump(rows, open(out, "w"), indent=1)
print(len(rows), "files mapped")
