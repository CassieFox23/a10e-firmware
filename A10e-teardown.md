# Inside a locked phone: a Galaxy A10e firmware teardown

A hobby reverse-engineering walkthrough of the stock firmware for the **Samsung Galaxy A10e (SM-A102U)**, a parked US-carrier phone. It started as "can I turn this old phone into a pet camera?" and turned into a full look at how a modern Android phone decides what it is allowed to run — and why a carrier-locked one is such a dead end for custom ROMs.

Everything here is static analysis of firmware downloaded from Samsung's own update servers. Nothing was flashed, nothing was run on the phone, and no lock was bypassed — the opposite, really: the point was to read the locks and understand them.

> **Correction, 2026-10-26.** An earlier version of this guide described a second flash lock built on a "Knox Guard token magic `0x12349876`." That was wrong. The cause was an ARM64 addressing bug (wrong `ADRP` page phase) that resolved string references to a string exactly 2 KB away. `0x12349876` is the Samsung **PIT** (partition table) magic, and the code in question is the partition-table parser. A blind second-pass review and an independent session both caught it on primary evidence. The method section below now walks through the bug, because it is the most useful thing in here.

---

## TL;DR

- The A10e is Project-Treble compliant, but its bootloader can't be unlocked, so no GSI or custom kernel can ever boot on it.
- Its stock firmware is six bundles that map onto 38 phone partitions; 21 of them (radio identity, keys, factory-reset protection) are never touched by a flash, which is why a reflash keeps the phone's IMEI.
- The one lock that actually blocks a custom ROM is **verified boot (AVB)**: the bootloader refuses to run any boot/system image not signed by a 4096-bit RSA key. I carved the key out, confirmed its fingerprint with `avbtool`, and read the check in the bootloader's own code.
- There are two other locks, read with less certainty: **Knox Guard** (a carrier/financing flash gate — real, but a `kg_state` handler, *not* the token check I first wrote) and the **TEEGRIS** secure world (a TrustZone OS that holds the secure status bits normal code can read but not change).
- The fun part is the method, and the mistake: the bootloader is a headless ARM64 blob, and a wrong assumption about `ADRP` addressing silently fooled me. That story is the main event.

---

## The device

| | |
|---|---|
| Model | SM-A102U (T-Mobile / US carrier) |
| Build | `A102USQSDAVD1` — bootloader v13, Android 9, April 2022, patch 2022-01-01 |
| SoC | Exynos 7885-class (strings in the firmware say `exynos7885` and `7904`; some third-party sources list Exynos 7884 — I didn't resolve the discrepancy) |
| Treble | yes (`ro.treble.enabled=true`, VNDK 28) |
| GSI flavour | `a64_bvN` (32-bit apps, 64-bit binder, system-as-root, vanilla) |
| Bootloader | **locked, no OEM-unlock toggle** — the wall for custom ROMs |

So in theory it's Treble and would take an `a64_bvN` GSI. In practice the bootloader door in front of Treble is bolted shut, and on this US-carrier model there's no way to open it.

---

## The firmware package

Samsung firmware comes as six `.tar.md5` bundles. Each file inside is LZ4-compressed; a flasher writes each one to a named partition.

| Bundle | Carries | Wipes data? |
|---|---|---|
| **BL** | bootloader (`sboot.bin`), boot screens, Crypto Manager, `vbmeta` | no |
| **AP** | the OS: kernel, recovery, `system`, `vendor` | no |
| **CP** | the cellular modem | no |
| **CSC** | carrier setup **+ the partition map (PIT)** | yes |
| **HOME_CSC** | the same carrier setup, no PIT | no |
| **USERDATA** | the carrier's starting data partition | yes |

The PIT (partition table) lists 38 partitions. Only 17 are written by this firmware. The other 21 — `EFS`/`SEC_EFS` (radio identity and IMEI), `PERSISTENT` (factory-reset protection), the modem calibration areas, and others — are left untouched, which is exactly why reflashing stock doesn't wipe your IMEI or trip anti-theft.

---

## Lock #1 — Verified boot (AVB)  *(the one that matters)*

`vbmeta` is Android's signed "table of contents" for the boot chain. Reading it with `avbtool` and carving the embedded key out by hand:

- Algorithm: **SHA256_RSA4096** (a 4096-bit RSA key).
- Key fingerprint (sha1): `e553992a79ab561a4805371cce123d1ee73db21b` (confirmed against `avbtool`, and recomputed by hand over the 1032-byte key blob).
- The same key signs the `vbmeta` root **and** every chained partition (`recovery`, `dtb`, `dtbo`, `product`).
- It carries SHA-256 hashes for `bootloader`, `cm` and `boot`, plus **dm-verity** hash trees (with FEC) for `system` and `vendor`.
- The bootloader carries a byte-identical copy of that public key inside itself, in two places (file offsets `0x12b070` and `0x322410`) — so the key is *embedded in the bootloader*, not something I could show is blown into a hardware fuse.

That key is *the* thing an image has to be signed with. Change `system` or `boot` — as a GSI or custom kernel does — and its hash no longer matches `vbmeta`, and `vbmeta` itself can't be re-signed without Samsung's private key.

I then found the code that enforces it, inside the bootloader. It's **libavb** (the standard Android Verified Boot library) compiled in. The gate is an indirect call to a key validator, followed by a flag test:

```
blr  x8                     ; call the public-key validator (x8 from an ops struct)
cmp  w0, #1
b.eq <ok, key matched>      ; result 1 -> accepted
cbnz w0, <other error>
ldrb w0, [x29, #0x4c0]      ; the per-partition "key accepted" flag it sets
cbz  w0, <reject>           ; not accepted -> reject
...  "%s: Public key used to sign data rejected. (%d)"
```

If the key an image was signed with isn't the device's trusted key, it logs "Public key used to sign data rejected" and boot fails. That is the whole idea, and it's the real reason an unsigned GSI or custom kernel is refused.

---

## Lock #2 — Knox Guard (the flash gate)  *(real, but read this correction)*

Separately from verified boot, the bootloader's **Download mode** (the Odin flashing screen) has a carrier/financing gate. Its strings are blunt: `"KG locked. Not allowed to flash."`, `"custom binary! kernel rp skip checking.."`, and `"blocked due to remaining installment balance"`. KG is **Knox Guard** — the "this phone isn't paid off / is carrier-locked" case is literally in there.

**What I got wrong the first time:** I reported this gate as a check for a "token magic `0x12349876`", with a tidy four-line disassembly. That was a mistake caused by the addressing bug in the method section. The function I pointed at is actually the **PIT (partition-table) parser**: it copies a 28-byte header, checks the magic `0x12349876` (which is the identifier at the top of every Samsung PIT file — see Heimdall's `libpit`), caps the entry count at 128, and loops over 132-byte entries. It has nothing to do with Knox Guard.

**What the real gate does**, once the addressing is correct: the KG handler (around file offset `0x6f8b8`) reads a `kg_state` and tests a flag bit through a helper (`0x88bfc`, a bit-test against a global word). If that bit is set, it takes an **engineering-mode token path** — the nearby strings are `"[EMC]Certificate verify success"`, `"[EMC]Token signature verify success"` and `"[EMC]DID isn't matched"`, i.e. a signed token with certificate and signature checks (I didn't trace where the flag bit itself is set). If the bit is clear, only a partition named `STEADY` may be flashed (`"KG locked. but allowed to flash steady."`); anything else is refused with `"KG locked. Not allowed to flash."` / `"All binaries are not allowed to be flashed due to KG locked.(%s)"`. There is **no** `0x12349876` compare here — that constant was the partition-table parser next door. (So my original hunch that a signed token existed was right; I'd just pinned it to the wrong constant.)

---

## Lock #3 — the TEEGRIS secure world

Buried inside the bootloader are three small ARM64 ELF programs. Because they're proper ELF files (with headers and sections), they decompile cleanly, unlike the headerless bootloader itself.

- Two of them are preceded by the tag `TEEGRIS_EXYNOS7904_CSMC`. Neither is the secure OS itself: the larger (~60 KB) is a **CSMC handler** (it prints `CSMC: BEGIN` and the `bl_secure_info` status lines below); the smaller (~9 KB) is a tiny stub — little more than a stack-check string and generic sections.
- The third is **not** tagged TEEGRIS; it's preceded by `bin/startup_loader` and is the **secure-OS loader** by content (`load_startup_tzar`, `startup.tzar.lz4`, `SECUREOS VERSION`). The TEEGRIS secure OS proper is the compressed `startup.tzar.lz4` this loader unpacks at boot — not one of these three ELFs.
- One module prints Samsung's **`bl_secure_info`** fields as debug lines (`CSMC: bl_secure_info.<field>`). The fields it names include `cc_mode`, `em_status`/`em_token`, `curr_bin_status`, `frp_lock`, `kernel_rp` — and more besides (`rp_ver`, `system_rp`, `sec_boot`, `warranty_bit`, `image_status[]`, and others). So this is a secure-world module that *reports* a long list of status/lock bits; it's a readout, not the authority that sets them.

**Putting it together:** the phone won't *run* unsigned images (AVB — the hard wall), and won't *flash* freely once carrier/financing-locked (KG). A TEEGRIS secure-world module reports a wall of status/lock bits that normal code can read but not change. I read AVB with full confidence; KG and the secure-world details carry the caveats above — in particular I didn't tie the KG flag bit back to a specific secure-world field, so treat "it's all one structure" as unproven.

---

## How it was done — the method (the fun part, and the mistake)

The bootloader (`sboot.bin`) is a 4 MB ARM64 image with no symbols and no obvious load address. It *does* begin with a small 16-byte header (word `0x00000010`, then the magic `0xfdcdbc1d`) followed by a reset-style stub at offset `0x10` — which matters below.

**1. Ghidra stalled, and the first diagnosis was half-right.** Loaded raw at a guessed base, auto-analysis found thousands of functions but couldn't tie the "blocked"/"rejected" strings to any code — cross-references came back empty, and the "entry point" at offset 0 decoded as a single garbage instruction. Part of that is real (code reached only through function pointers stays undisassembled). Part of it was self-inflicted: offset 0 is the *header*, not code, so seeding the entry there was always going to produce garbage. The real entry stub is at `0x10`.

**2. The bug that actually bit me: the `ADRP` page phase.** ARM64 finds its own data with an `ADRP`+`ADD` pair. `ADRP` is **page**-relative: it forms `(PC & ~0xFFF) + offset`. To compute which byte a reference lands on, you need the load address **modulo 4 KB** — the "page phase". Not the whole base. Just the low 12 bits.

I assumed the phase was 0 (a 4 KB-aligned base, file offset mapping straight onto a page boundary). For this image it's `0x800` — half a page. With the wrong phase, *every* string reference lands **exactly** `0x800` bytes (2 KB) off, on a different string. The disassembly still looks fine; the references just point at the wrong text. It fails silently.

The right way to find the phase is to measure it: for each candidate phase, count how many `ADRP`+`ADD` pairs resolve exactly to the start of a C string. One phase wins sharply.

| Page phase | `ADRP`+`ADD` pairs landing on a clean string start |
|---|---|
| `0x800` (correct) | 3209 |
| `0` (my wrong assumption) | 900 |

(An independent session reproduced this on a live Ghidra session: ~4249 of 6462 pairs clean at `0x800` vs ~1000 at phase 0, with phase-0 hits landing on mid-token junk.)

**3. What the bug cost, and what fixing it revealed.** Under the wrong phase, references land exactly `0x800` (2 KB) off. The partition-table parser's `0x12349876` magic check resolved onto Knox Guard strings 2 KB away, so I wrote it up as a KG token gate. Under the correct `0x800` phase, that site cleanly references `update_guid_partition_table` / `guid_part.c` (partition-table integrity), and the *real* AVB key gate (file `0xa7a34`) and KG handler (file `0x6f8b8`) resolve to their own, correct strings — the ones quoted in the locks above.

**4. On the "load base".** `ADRP` gives you the phase, not the base. For the base itself you need *absolute* pointers — and there's a clean source: a 13-entry table of partition-name pointers (file `0x12b488`) where every entry equals `base + that string's file offset`. Solve for the base and you get **`0x8ef9e800`**: all 13 entries then resolve to real partition names (`BOOTLOADER`, `BOOT`, `VBMETA`, `RADIO`, `RECOVERY`, …), and ~450 pointers image-wide land on string starts — a sharp result. Two things fall out. The phase is `0x800` because `0x8ef9e800` ends in `0x800`, not because the base is unaligned in some exotic way. And the base is `0x61800` *below* the `0x8f000000` I first chased — which turns out to be a `ldr x1,=0x8f000000; br x1` jump constant in the startup stub. That jump literal is exactly what my discarded "pointer span" argument had mistaken for the base. (You still don't *need* the base to read logic — the phase is enough — but it's there if you want it.) File offsets stay the stable reference; add `0x8ef9e800` for a VA.

**5. Carve the clean bits out.** The TEEGRIS programs are real ELF files embedded mid-binary. Parsing their ELF headers to get their exact size and carving them to standalone files gave the tools something with symbols and sections — and cross-references, function boundaries and decompilation all worked normally. The right move is often to *reshape the input* rather than fight the tool.

**Takeaways for anyone poking at firmware:**
- `ADRP` is **page**-relative. To resolve a reference you need the load address mod 4 KB. Don't assume it's zero — measure it (the phase with the most references landing on clean string starts wins).
- A wrong page phase fails *silently*: everything disassembles, references just point at data exactly 2 KB away. That's how a partition-table check got written up as a carrier lock.
- You don't need the full load base to read logic — the page phase is enough. If you *do* want the base, `ADRP` won't give it to you; find absolute pointers (a labeled pointer table pins it cleanly). A zero-padding "span" won't.
- An empty cross-reference list in a raw image usually means "not disassembled," not "not referenced."
- If part of a blob is a real container/ELF, extract it and let the tools work on headers they understand.
- Get a second, blind pass before you trust your own writeup. Mine invented a lock that wasn't there.

---

## Tools

All free and local: Samsung's own firmware via `samloader`; `lz4`, `simg2img`, `debugfs`, `avbtool` for unpacking; Ghidra (via REA) for analysis, plus `capstone` (driven through a tiny `ctypes` wrapper, since the Python bindings aren't installed here) for the byte-level disassembly and the phase sweep; `binwalk` for a first pass; small Python scripts for the `ADRP` reference work. No device was connected and nothing was flashed.

## Reproducing

The `tools/` scripts regenerate the maps and disassembly from the firmware in `firmware/`. The `ADRP` reference resolver takes the page phase (`0x800`) as a parameter — run the phase sweep first to confirm it. Derived artifacts (boot screens, carved ELFs, the extracted key) land in `out/` and aren't committed, since they rebuild from the bundles.
