import sys, re, json
t = open(sys.argv[1]).read(); rows = json.load(open(sys.argv[2]))
pit = {}
for e in re.split(r"--- Entry #\d+ ---", t)[1:]:
    g = lambda k: (re.search(rf"{k}: ?(.*)", e).group(1).strip() if re.search(rf"{k}: ?(.*)", e) else "")
    pit[g("Partition Name")] = dict(id=int(g("Partition ID")), start=int(g("Start Block")), cnt=int(g("Partition Block Count")), file=g("Flash Filename"))
byfile = {v["file"]: k for k, v in pit.items() if v["file"]}
def h(n):
    for u in ("B", "KiB", "MiB", "GiB"):
        if n < 1024 or u == "GiB":
            return f"{n:.0f} {u}" if u == "B" else f"{n:.1f} {u}"
        n /= 1024
print("| Bundle | File | Partition (ID) | Slot | Unpacked | Type |")
print("|---|---|---|---|---|---|")
shipped = set()
for r in rows:
    f = r["file"]
    if f.startswith("meta-data/"):
        continue
    base = f[:-4] if f.endswith(".lz4") else f
    shipped.add(base)
    part = byfile.get(base)
    slot = "rest of storage" if part and pit[part]["cnt"] == 0 else (h(pit[part]["cnt"] * 512) if part else "-")
    size = h(r["full"]) + " full" if r.get("full") else h(r["unpacked"])
    where = f"{part} ({pit[part]['id']})" if part else "-"
    print(f"| {r['bundle']} | `{base}` | {where} | {slot} | {size} | {r['kind']} |")
print()
print("Not in this firmware:", ", ".join(f"{k} ({v['id']})" for k, v in sorted(pit.items(), key=lambda x: x[1]["start"]) if v["file"] not in shipped))
