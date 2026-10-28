#!/usr/bin/env python3
# Parse a Samsung Shannon modem image (modem.bin / modem_debug.bin): the TOC
# at offset 0 (32-byte entries: name[12], offset, loadaddr, size, crc, id, all
# u32 LE), validate the section extents against the file, then read version and
# radio-capability strings out of the MAIN section.
#
# Static, read-only. Firmware is untrusted data: run isolated, pass the image
# path as an argument. Reads bytes only; never imports from the image's dir.
#   python3 -I tools/modem_toc.py <modem.bin> [<modem2.bin> ...]
import sys, struct, re

ENTRY = 32

def toc(buf):
    out = []
    for i in range(0, 0x200, ENTRY):
        name = buf[i:i+12].split(b"\x00", 1)[0]
        if not name and i != 0:
            break
        off, load, size, crc, eid = struct.unpack_from("<5I", buf, i+12)
        if not name and off == 0 and size == 0 and i != 0:
            break
        out.append((name.decode("ascii", "replace"), off, load, size, crc, eid))
    return out

def strings(blob, minlen=6):
    return re.findall(rb"[\x20-\x7e]{%d,}" % minlen, blob)

def report(path):
    with open(path, "rb") as f:
        buf = f.read()
    n = len(buf)
    print(f"\n===== {path}  ({n:,} bytes) =====")
    entries = toc(buf)
    print(f"{'name':10} {'file_off':>12} {'load_addr':>12} {'size':>12} {'crc':>10} id  fits?")
    main = None
    for name, off, load, size, crc, eid in entries:
        fits = "n/a" if off == 0 else ("OK" if off + size <= n else "OVERFLOW")
        print(f"{name:10} 0x{off:010x} 0x{load:010x} 0x{size:010x} 0x{crc:08x} {eid:>2}  {fits}")
        if name == "MAIN" and off and off + size <= n:
            main = (off, size)
    if not main:
        print("  (no MAIN section located; skipping string scan)")
        return
    off, size = main
    blob = buf[off:off+size]
    ss = strings(blob)
    print("\n  -- version / build markers in MAIN --")
    seen = set()
    for s in ss:
        if (b"Shannon" in s or b"CP Version" in s or b"RELDATE" in s or b"a10e" in s.lower()):
            t = s.decode("ascii", "replace")
            if t not in seen:
                seen.add(t); print("   ", t)
    # radio capability keyword census (strings, not proof of capability)
    print("\n  -- radio keyword census in MAIN (string counts; a count is not a capability) --")
    for k in [b"ShannonOS", b"NR5G", b"ENDC", b"EN-DC", b"NSA", b"5G", b"NR", b"mmWave",
              b"mmwave", b"sub6", b"LTE", b"CA_", b"B66", b"n71", b"n41"]:
        print(f"    {k.decode():8} {blob.count(k):>7}")
    # a few NR/5G context samples
    print("\n  -- sample NR/5G context strings (up to 12) --")
    shown = 0
    for s in ss:
        if (b"NR" in s or b"5G" in s or b"ENDC" in s or b"EN-DC" in s) and len(s) < 120:
            print("   ", s.decode("ascii", "replace"))
            shown += 1
            if shown >= 12:
                break

if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("usage: python3 -I tools/modem_toc.py <modem.bin> [...]")
    for p in sys.argv[1:]:
        report(p)
