# Inside a locked phone: a Galaxy A10e firmware teardown

A hobby reverse-engineering walkthrough of the stock firmware for the **Samsung Galaxy A10e (SM-A102U)**, a parked US-carrier phone. It started as "can I turn this old phone into a pet camera?" and turned into a full look at how a modern Android phone decides what it is allowed to run — and why a carrier-locked one is such a dead end for custom ROMs.

Everything here is static analysis of firmware downloaded from Samsung's own update servers. Nothing was flashed, nothing was run on the phone, and no lock was bypassed — the opposite, really: the point was to read the locks and understand them.

---

## TL;DR

- The A10e is Project-Treble compliant, but its bootloader can't be unlocked, so no GSI or custom kernel can ever boot on it.
- Its stock firmware is six bundles that map onto 38 phone partitions; 21 of them (radio identity, keys, factory-reset protection) are never touched by a flash, which is why a reflash keeps the phone's IMEI.
- The phone has **three independent locks**, and I read each one in the actual code:
  1. **Verified boot (AVB):** the bootloader refuses to run any boot/system image not signed by a 4096-bit RSA key fused to the device.
  2. **Knox Guard / KG:** in Download mode, the flasher refuses any payload without a signed engineering token.
  3. **TEEGRIS secure world:** a TrustZone OS holds a `bl_secure_info` structure that tracks every lock bit; normal code can read it but can't forge it.
- The fun part was method: the bootloader is a headless ARM64 blob with no symbols, so standard tools stalled. I'll show why, and the trick that got around it.

---

## The device

| | |
|---|---|
| Model | SM-A102U (T-Mobile / US carrier) |
| Build | `A102USQSDAVD1` — bootloader v13, Android 9, April 2022, patch 2022-01-01 |
| SoC | Exynos 7885-class (the firmware strings also say 7904/7885 in different places) |
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

## Lock #1 — Verified boot (AVB)

`vbmeta` is Android's signed "table of contents" for the boot chain. Reading it with `avbtool` and carving the embedded key out by hand:

- Algorithm: **SHA256_RSA4096** (a 4096-bit RSA key).
- The same key signs the `vbmeta` root **and** every chained partition (`recovery`, `dtb`, `dtbo`, `product`).
- It carries SHA-256 hashes for `bootloader`, `cm` and `boot`, plus **dm-verity** hash trees (with FEC) for `system` and `vendor`.

That key is *the* thing an image has to be signed with. Change `system` or `boot` — as a GSI or custom kernel does — and its hash no longer matches `vbmeta`, and `vbmeta` itself can't be re-signed without Samsung's private key.

I then found the code that enforces it, inside the bootloader. It's **libavb** (the standard Android Verified Boot library) compiled in. The core gate, disassembled:

```
bl   <validate_public_key>      ; is the key this image was signed with one we trust?
cbnz w0, <continue>             ; trusted -> keep going
...  "Public key used to sign data rejected. (%d)"
mov  w21, #6                    ; result = rejected
bl   <log>                      ; and boot fails
```

Four lines, and that's the whole idea: validate the signing key, and if it isn't the device's own key, reject and stop.

---

## Lock #2 — Knox Guard (the flash gate)

Separately from verified boot, the bootloader's **Download mode** (the Odin flashing screen) has its own gate. Its strings tell the story: `"KG locked. Not allowed to flash."`, `"KG locked but allow to flash with eng token"`, and `"blocked due to remaining installment balance"`. KG is **Knox Guard** — Samsung's carrier/financing lock (the "this phone isn't paid off" case is literally in there).

The decision, read directly from the disassembly:

```
w0 = 0x12349876               ; a token "magic" value
w1 = <field from the flash payload you send>
if w1 != 0x12349876 -> "...not allowed to be flashed due to KG locked", return -1   (REFUSE)
else                -> take the "allow to flash with eng token" branch
```

On a KG-locked phone, whatever you try to flash has to carry an engineering token stamped with the magic `0x12349876`. No token, instant refusal. Important caveat: that magic is only the token's *format tag* — a real token is signed and validated further down (Samsung-internal; you can't forge one). The magic alone unlocks nothing.

---

## Lock #3 — the TEEGRIS secure world

Buried inside the bootloader are three small ARM64 ELF programs tagged `TEEGRIS` — Samsung's TrustZone secure OS. Because they're proper ELF files (with headers and sections), they decompile cleanly, unlike the headerless bootloader itself.

- One is the **secure-OS loader** (`load_startup_tzar`, `startup.tzar.lz4`, `SECUREOS VERSION`), which unpacks the TrustZone OS at boot.
- The most interesting one reports Samsung's **`bl_secure_info`** structure. Its strings name every lock bit the secure world tracks:
  - `cc_mode` — the "Custom binary blocked by CC Mode" state
  - `em_status` / `em_token` — engineering mode and the KG engineering token
  - `curr_bin_status` — Samsung Official vs. custom binary
  - `frp_lock` — factory-reset protection
  - `kernel_rp` — kernel rollback protection
  - plus `afw_value`, `ap_serial`, `image_status[]`, `kap_status`

That single structure is where all three locks meet. The normal-world bootloader *reads* these bits to decide what it'll run and flash, but the values live in the secure world where normal code can't change them.

**Putting it together:** the phone won't *run* unsigned images (AVB), won't *flash* without a signed token (KG), and the state behind both is held in a place you can't reach (TEEGRIS). Three layers, each independent. That's why a US-carrier A10e is a wall.

---

## How it was done — the method (the fun part)

The bootloader (`sboot.bin`) is a 4 MB headless ARM64 image: no file header, no symbols, no entry point. Opening it in Ghidra was where it got interesting.

**1. Ghidra stalled, and the error was the clue.** Loaded raw at a guessed base, auto-analysis found 3,301 functions but couldn't tie the "blocked" strings to any code — every cross-reference came back empty, and the "entry point" decompiled to a single garbage instruction. The reason: with no valid entry to seed from, the disassembler never covered the code that's only reached through function pointers.

**2. Hunting the "real load base" — and learning it doesn't exist.** The natural next step is "find the address this image is meant to load at." I tried four ways:
- Clustering the absolute 64-bit pointers in the file → they sat around `0x8f000000`, but didn't land on function starts, so they're **runtime RAM buffers**, not code addresses.
- Matching pointers to string starts, to function prologues, to literal-pool entries, to MOVZ/MOVK-built constants → every method smeared across many candidates with no sharp winner.

The lesson: **ARM64 code is mostly position-relative.** It finds its own strings and functions with `ADRP+ADD` ("jump this far from *here*"), which reads the same no matter where you load it — so the file simply carries no single "base" to recover. And crucially, you don't need one.

**3. The trick: find the reference in the raw bytes.** Since `ADRP+ADD` is position-independent, I wrote a tiny scanner that decodes those instruction pairs straight from the file and computes which string each one points at. That found the exact instruction that builds the address of the verified-boot error message — which pinned the function Ghidra had skipped. From there, `capstone` disassembled it directly. Same scanner found the Knox Guard gate a few hundred bytes away.

**4. Carve the clean bits out.** The TEEGRIS programs are real ELF files embedded mid-binary. Parsing their ELF headers to get their exact size and carving them to standalone files gave Ghidra something with symbols and sections — and suddenly cross-references, function boundaries and decompilation all worked normally. A good reminder that the right move is often to *reshape the input* rather than fight the tool.

**Takeaways for anyone poking at firmware:**
- An empty cross-reference list in a raw image usually means "not disassembled," not "not referenced."
- For ARM64, don't chase a load base to read logic — `ADRP+ADD` is base-independent; scan for it directly.
- Absolute pointers in a blob are often RAM buffers, not code; don't trust a pointer cluster as a base.
- If part of a blob is a real container/ELF, extract it and let the tools do their job on headers they understand.

---

## Tools

All free and local: Samsung's own firmware via `samloader`; `lz4`, `simg2img`, `debugfs`, `avbtool` for unpacking; Ghidra (via REA) and `capstone` for disassembly; `binwalk` for a first pass; small Python scripts for the ADRP/base work (in `tools/sboot/`). No device was connected and nothing was flashed.

## Reproducing

The `tools/` scripts regenerate the maps and disassembly from the firmware in `firmware/`. Derived artifacts (boot screens, carved ELFs, the extracted key) land in `out/` and aren't committed, since they rebuild from the bundles.
