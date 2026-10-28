# Inside a locked phone: a Galaxy A10e firmware teardown

A hobby reverse-engineering walkthrough of the stock firmware for a **Samsung Galaxy A10e (SM-A102U)** — a cheap, parked, US-carrier phone. It began as "could I turn this old handset into a pet camera?" and turned into a full read of how a modern Android phone decides what it is allowed to run, and why a carrier-locked one is a dead end for custom ROMs.

Almost all of this is **static analysis** of downloaded firmware. The only contact with the device was read-only: an `adb` property/package/partition sweep while it was booted, and a download-mode session where `heimdall` connected but pulled nothing and flashed nothing. No partition was ever written, and no lock was bypassed. The point was the opposite — to *read* the locks and understand them.

There is also a mistake in here, kept in on purpose, because it's the most useful thing I learned. And because a single reverse-engineer fooling themselves is the normal case, the whole thing went through a blind second review; where that review narrowed a claim, this version says so.

---

## TL;DR

- The A10e is Project-Treble compliant, but its bootloader is **locked** and this US-carrier model exposes no way to unlock it, so in practice no GSI or custom kernel boots on it.
- The lock the bootloader actually *enforces* is **verified boot (AVB)**: it refuses any boot/system image not signed by a specific 4096-bit RSA key. I carved the key out, matched its fingerprint with `avbtool`, and tied it to the check in the bootloader's own code. (Unlocking the bootloader is what would relax this — which is why the lock state is the real wall.)
- Two more locks sit alongside it: **Knox Guard** (a carrier/financing flash gate, with a signed engineering-token escape hatch) and the **TEEGRIS** secure world (a TrustZone OS that holds status bits normal code can read but not change — I can show it *reads* them, not that it's the sole authority).
- I cross-checked the finding against the previous build, the next (Android 11) build, the *unlocked* sibling model, and Samsung's own published kernel source. The AVB key and the lock strings don't change; the big OS-major code rewrite I didn't fully disassemble.
- The best part is the method, and a bug: a wrong assumption about ARM64 addressing silently fooled me into writing up a partition-table check as a carrier lock. That story is the main event.

---

## The device

| | |
|---|---|
| Model | SM-A102U (T-Mobile / US carrier) |
| Build analysed | `A102USQSDAVD1` — bootloader 13, Android 9, April 2022, security patch 2022-01-01 |
| SoC | Exynos 7885-class. The firmware strings say `exynos7885` and `exynos7904`; the device-tree overlays name **Exynos 7884B**. I didn't resolve the family-name spread — Samsung reuses a base across close siblings. |
| Treble | yes (`ro.treble.enabled=true`, VNDK 28, system-as-root) |
| GSI flavour | reads as `a64_bvN` (32-bit apps, 64-bit binder). The `b` normally means A/B, but this phone has no `ro.build.ab_update` and no slot partitions, so whether that flavour is right for an A-only device I didn't confirm. |
| Bootloader | **locked** (`device_state=locked`, `flash.locked=1`), and OEM-unlock not available on this model |

So in theory it's Treble. In practice the bootloader door in front of Treble is shut, and on this US-carrier model there's no exposed way to open it (more under "Could it run LineageOS?").

---

## The firmware package

Samsung firmware ships as six `.tar.md5` bundles. Most files inside are LZ4-compressed (the `.pit` partition map and the OTA `fota.zip` are not); a flasher writes each to a named partition. All six MD5 trailers were recomputed by hand and passed.

| Bundle | Carries | Wipes data? |
|---|---|---|
| **BL** | bootloader (`sboot.bin`), boot screens (`param.bin`), Crypto Manager (`cm.bin`), `vbmeta` | no |
| **AP** | the OS: kernel (`boot.img`), `recovery`, `system`, `vendor`, device trees | no |
| **CP** | the cellular modem (`modem.bin`) | no |
| **CSC** | carrier setup **+ the partition map (PIT)** | yes |
| **HOME_CSC** | the same carrier setup, no PIT | no |
| **USERDATA** | the carrier's starting data partition | yes |

The PIT lists **38 partitions; only 17 are written** by this firmware. The other 21 are left untouched — `EFS`/`SEC_EFS`/`CPEFS` (radio identity and IMEI), `PERSISTENT` (factory-reset protection), the modem calibration areas, and others. That is why reflashing stock keeps your IMEI and doesn't trip anti-theft: the identity partitions are never in the download.

---

## The boot chain, in one picture

A trust-boundary diagram — who checks whom at boot — is in the project at
`.archify/architecture-a10e-trust-20261026-193833/a10e-trust.html`, built from the `vbmeta` descriptors.

```
sboot  ──AVB verify(BOOT, RSA-4096 vs vbmeta)──▶  kernel
  │                                                 │
  │ vbmeta also carries:                            └─▶ dm-verity on system + vendor (hashtrees + FEC)
  │   • SHA-256 hashes for bootloader, cm, boot
  │   • chained keys for recovery, dtb, dtbo, product
```

Live, the phone reports `verifiedbootstate = green`, `device_state = locked`, `selinux = enforcing`, `veritymode = enforcing` — all **consistent with** the static chain below.

---

## Lock #1 — Verified boot (AVB)  *(the one it enforces)*

`vbmeta` is Android's signed "table of contents" for the boot chain. Reading it with `avbtool` and carving the embedded key out by hand:

- Algorithm: **SHA256_RSA4096** (a 4096-bit RSA key).
- Key fingerprint (sha1): `e553992a79ab561a4805371cce123d1ee73db21b` — confirmed against `avbtool`, and recomputed by hand over the 1032-byte key blob.
- The same key signs the `vbmeta` root **and** every chained partition (`recovery`, `dtb`, `dtbo`, `product`).
- It carries SHA-256 hashes for `bootloader`, `cm` and `boot`, plus **dm-verity** hashtrees (with FEC) for `system` and `vendor`. (Those three hash descriptors match the files first-hand.)
- The bootloader carries a **byte-identical copy of that public key inside itself, in two places** (file offsets `0x12b070` and `0x322410`; in the 2023 builds, `0x12d070`/`0x322410`). So the key is *embedded in the bootloader image*, not something I could show is blown into a hardware fuse.

I tied the embedded key to the gate. A `.data` pointer at file `0x140b28` holds the address of the `0x12b070` key; it's loaded at file `0xaf334`, right before the Samsung check that logs `[AVB 2.0 ERR] AVB pubkey is not matched with vbmeta`. The generic libavb routine at file `0xa7a34` is `validate_vbmeta_public_key` (it returns an `AvbIOResult`); on a key that isn't the device's trusted key the path ends at the log line *"Public key used to sign data rejected"* and verification fails. (I'm describing the behaviour, not a line-by-line branch read — my first attempt mis-annotated those branches, so I'm not repeating a disassembly listing I can't stand behind.) libavb's source-file strings are all present (`avb_slot_verify.c`, `avb_rsa.c`, `avb_vbmeta_image.c`, descriptors).

Change `system` or `boot`, and its hash no longer matches `vbmeta`; and `vbmeta` can't be re-signed without Samsung's private key. That is the mechanism that refuses an unsigned GSI or custom kernel.

As a sanity check that I read the right firmware: the vbmeta digest `avbtool` computes from the staged partitions, `5d354bfd…a7e6`, **matches the live device's `ro.boot.vbmeta.digest`**. That digest covers the signed vbmeta hash set for the boot chain, so it's strong evidence the boot images on the phone are this firmware.

---

## Lock #2 — Knox Guard, and the engineering-token escape hatch

Separate from verified boot, the bootloader's **Download mode** (the Odin flashing screen) has a carrier/financing gate. Its strings are blunt: `"KG locked. Not allowed to flash."`, `"KG locked but allow to flash with eng token"`, and even `"blocked due to remaining installment balance"`. KG is **Knox Guard**.

Reading the Download-mode path at the correct base:

- The Odin command handler is **`usbd3_rdx_process`** (file `0xc0ecc`). It accumulates 1024-byte command blocks and hands each to **`process_packet`** (file `0x6cfc8`), which maps the Odin commands:

  | class | name | what it does |
  |---|---|---|
  | `100`/0x64 | session / control | `get_v3_protocol_ver`, set packet size, `sales_code %s`, model string |
  | `0x65`/'e' | **PIT** | validate + parse the partition table |
  | `0x66`/'f' | **binary flash** | per-partition write, through the flash gate |
  | `0x67`/'g' | end / reboot | |
  | `0x69`/'i' | device info | |

- The flash **verdict** lives in the writer at file `0x6f7ec`, which carries `"KG locked. Not allowed to flash."`.
- The lock **state** it reads is produced by a KG state engine at file `0x74968`: it reads the Knox "vaults" from **RPMB** (replay-protected secure storage), hash-verifies them, and resolves a state (`[KG] Normal / Locked / Blink / …`).
- The escape hatch is a signed **engineering (EM) token** (`"This is KNOX TEST binary. Please download EM-token first!"`): a certificate chain checked in `sboot`, bound to the chip ID, read from the `STEADY` partition. I traced its structure and strings, not the RSA/ASN.1 verification itself, so "can't be forged" is the design, not something I proved end-to-end.

There's also a separate signed-image check in this flow, independent of KG — `sboot` reports `"SW REV. CHECK FAIL(%s) DEVICE: %d, BINARY: %d"` (anti-rollback) and `"Custom binary blocked by CC Mode."` / `"MDM MODE. CAN'T DOWNLOAD."`.

> **The mistake lives here.** An earlier version reported this gate as a check for a "token magic `0x12349876`". That was wrong — see the method section. `0x12349876` is the Samsung **PIT file identifier**, and the code I pointed at is the partition-table parser next door.

---

## Lock #3 — the TEEGRIS secure world

Buried inside the bootloader are three small ARM64 ELF programs. Because they're real ELF files (headers and sections), they decompile cleanly, unlike the headerless bootloader around them. I carved them out and read them as standalone binaries.

- **teegris1 (~60 KB) — the CSMC "BFHandler" trusted app** (built `jenkins-BFHandler-exynos7904`). It RSA-verifies a Knox TIMA kernel-module signature (`lkm_sec_info`, `Module verification succeeded`), reads secure-boot measurement fields (`svb_magic`, virtual PCRs, `warranty_string`), and **prints** the `bl_secure_info` fields (`cc_mode`, `em_token`, `curr_bin_status`, `frp_lock`, `kernel_rp`, `warranty_bit`, …) from a `.rodata` table. The field dump is a readout; I did not catch it *setting* those bits.
- **teegris3 (~78 KB) — the secure-OS loader** (`startup_loader`): it `mmap`s **`startup.tzar.lz4`**, lz4-unpacks it, and loads the trusted apps. Reports `SECUREOS VERSION`.
- **teegris2 (~9 KB)** — a small stripped helper.

**An honest wall.** `startup.tzar.lz4` — the TEEGRIS secure OS body — is opened as a **file from the secure filesystem**, not embedded in sboot (no lz4 magic in `sboot.bin` or `cm.bin`). It isn't in the stock image set I have, so the trusted apps themselves can't be pulled from this download. *Where* it's provisioned I couldn't pin: there's no `TZSW` partition in the 38-entry PIT or the live by-name map — only sboot's internal name table mentions the name. `cm.bin` is a signed container of several modules (`CryptoManagerV40`, `srpmb_fw`, …), `SignerVer02`; its encrypted payload is handled over secure-monitor calls (`smc #0`) — decrypted inside the secure world, which I'm inferring from the call pattern, not proving.

**Putting the three together:** the phone won't *run* unsigned images (AVB — the mechanism, read with confidence), won't *flash* freely once carrier/financing-locked (KG, unless you hold a signed EM-token), and a TEEGRIS secure-world module *reports* a wall of status/lock bits. AVB I read with full confidence; for KG and the secure world I can show the handlers and strings, but I did not tie a specific secure-world bit to the flash decision, so treat "it's all one structure" as reasoned, not proven.

---

## What SELinux actually enforces

The locked bootloader is the flash/boot wall; SELinux is the wall *inside* the running OS. The boot cmdline asks for `androidboot.selinux=permissive`, which looks alarming — but **Android `init` ignores it** on a user build (it's honoured only when the build sets `ALLOW_PERMISSIVE_SELINUX`), and the kernel carries an `ALWAYS_ENFORCE` backstop besides (see the source cross-check). The phone runs Enforcing: `ro.boot.selinux=enforcing`, `ro.build.selinux.enforce=1`. I pulled the compiled device policy from `vendor.img` and read it with `checkpolicy` + `setools`:

- sepolicy **v30 MLS**, 2374 types, 95 classes, **39,074 `allow`** rules, 450 `allowxperm`.
- **Zero domains in permissive mode** — a proper `user`-build lockdown. (That means nothing is running *unconfined*; it does **not** mean nothing has broad powers.)
- `execmem` (write-then-execute memory) is granted to **47 domains** — app sandboxes, the TEE/Knox app domains, *and* a fair spread of system daemons (`shell`, `rild`, `radio`, `bluetooth`, `nfc`, `hal_camera_default`, `hal_drm_default`, `healthd`, `dumpstate`, `install_recovery`, `python`). Scoped, but broader than just apps.

**The fence around the secure world holds.** `untrusted_app` has **no `hwservice_manager find`** on any of 13 secure hwservice types (`proca`, `tee`, `teeregistry`, `wsm`, `sem`, `skpm`, `drk`, `wvkprov`, `qchdcpkprov`, `secure_storage`, `keymaster`, …), and **no `chr_file` access to the TrustZone device nodes** (`/dev/tzdev`, `/dev/tziwsock`, …) — only `getattr` on `debugfs_trustzone`. The one secure node an app can touch is Knox DAR (`/dev/dek_req`). That fence earns its keep because most of those TrustZone nodes are mode **0666** (Unix permissions wide open), so SELinux is the main thing gating them.

**What's actually behind the fence.** Reading `vendor.img` directly with `debugfs`, the secure-world userspace that ships is **TEEGRIS**, not Trustonic (the kernel has `CONFIG_TZDEV=y`; `CONFIG_TRUSTONIC_TEE` is absent). The real, launched services map to their SELinux domains: `tzdaemon`, the Knox `proca` HAL, `secure_storage_daemon`, `keymaster@4.0`, `gatekeeper@1.0`, Widevine DRM, and Samsung's `sem`/`drk`/`wsm`/`skpm`/`wvkprov` HALs — all 32-bit (no `/vendor/lib64`). Behind them sit **21 trusted apps** in `/vendor/tee`. But a chunk of the policy is **shared-template residue**: the Trustonic (`trustonic.tee`, `mcDriverDaemon`), HDCP-provisioning and `secure_element` domains are fenced off, yet **no binary for them ships on this image** — there, the fence guards doors with nothing behind them.

---

## Could it run LineageOS?

Short answer: not on this phone. Two separate things stand in the way.

**Wall 1 — it can't get in.** The bootloader is locked (`device_state = locked`, `flash.locked = 1`), and OEM-unlocking isn't available: `ro.oem_unlock_supported = 1` but `sys.oem_unlock_allowed = 0`. One honest caveat the blind review forced: `oem_unlock_allowed=0` only proves the Developer-options toggle is *off* — the AOSP `PersistentDataBlockService` sets that property from the toggle state, default 0. That US-carrier A102U models don't expose a *working* toggle (so you can't flip it to 1) is well-documented behaviour of these models, not something I proved from these files. Either way, even if an image reached a partition, AVB (Lock #1) rejects anything not signed by Samsung's key.

**Wall 2 — Treble/VINTF would object.** Treble has a boot-time check (VINTF) that pairs a system image with the phone's vendor code only when their declared versions match **exactly**. This vendor declares **target-level 3** (Android 9); the LineageOS 21 (Android 14) GSI ships compatibility matrices only for **levels 4–8** (both reproduced first-hand). By the exact-match rule there's no level-3 matrix for it to pair with, so the pairing should be refused — I'm stating that as the rule's consequence, not something I booted to confirm. Two caveats the review corrected: the GSI *does* still ship the VNDK-28 runtime (`com.android.vndk.v28.apex` is present — my earlier "it dropped it" was wrong), and the kernel issue is the **patch level** (the GSI's `compatibility_matrix.4.xml` wants kernel `4.4.302`; this phone is `4.4.111`), not "4.4 is too old." Whether an Android-9-era GSI would clear the check I didn't test.

So the GSI stays a souvenir — the locked bootloader is the wall you actually hit, and VINTF is a second one behind it.

---

## How it was done — the method, and the bug

The bootloader (`sboot.bin`) is a 4 MB ARM64 image with no symbols and no obvious load address. It begins with a 16-byte header: the first word `0x00000010` is the header length (constant across builds), the second word is a **per-build image checksum** (`0xfdcdbc1d` here, `0x70dbeb06` in the 2021 build, `0xa20ccd12` in 2023 — so not a magic, as I first assumed). The real reset stub is at offset `0x10`.

**1. Ghidra stalled.** Loaded raw at a guessed base, auto-analysis couldn't tie the "blocked"/"rejected" strings to any code — cross-references came back empty. Part of that is real (Ghidra doesn't form `ADRP`+`ADD` references in a raw image, so an empty xref list proves nothing); part was seeding the entry at offset 0 (the header, not code).

**2. The bug that bit me: the `ADRP` page phase.** ARM64 finds its own data with an `ADRP`+`ADD` pair. `ADRP` is **page**-relative: it forms `(PC & ~0xFFF) + offset`, so to know which byte a reference lands on you need the load address **modulo 4 KB** — the "page phase" — not the whole base. I assumed the phase was `0`. For this image it's **`0x800`** — half a page. With the wrong phase, *every* string reference lands **exactly `0x800` bytes (2 KB) off**, on a different string. The disassembly still looks fine; the references just point at the wrong text. It fails **silently**.

The right way is to measure it — for each candidate phase, count how many `ADRP`+`ADD` pairs resolve exactly to the start of a C string. The repo's `tools/phase_test.py` reports ~**4249 at `0x800`** vs ~**1000 at phase 0**; a from-scratch recompute lands around 3600 vs 870. Either way, one phase wins sharply.

**3. What the bug cost.** Under the wrong phase, the partition-table parser's `0x12349876` check (that constant is the identifier at the top of every Samsung PIT file) resolved its references onto Knox Guard strings 2 KB away, so I wrote it up as a "KG token gate." Under the correct phase, that site cleanly references `guid_part.c` (partition-table integrity), and the real AVB gate and KG path resolve to their own strings.

**4. The base, and the real unlock.** `ADRP` gives you the phase, not the base. For the base you need *absolute* pointers: a 13-entry table of partition-name pointers (file `0x12b488`) where every entry equals `base + that string's file offset`. Solve → **`0x8ef9e800`**. And here's the honest correction to my own "the phase is enough" takeaway: the phase is enough to resolve string references in a hand-written scan, but **pinning the base was the real unlock** — only then did Ghidra's analyzer follow the in-image pointer tables, auto-form the download-engine and KG functions, and let the caller walks run. The `0x8f000000` I'd first chased is a `ldr;br` jump literal, the VA of file offset `0x61800`.

**5. Reshape the input.** The three TEEGRIS programs are real ELF files embedded mid-binary. Carving them to standalone files gave the tools headers, sections and cross-references. Often the right move is to reshape the input rather than fight the tool.

**Takeaways:**
- `ADRP` is **page**-relative. Measure the phase; don't assume zero. A wrong phase fails *silently* — that's how a partition-table check got written up as a carrier lock.
- But for a raw image, **pin the load base** too: the phase reads strings, the base is what makes the disassembler's own analysis work.
- An empty cross-reference list in a raw image usually means "not disassembled," not "not referenced."
- **Get a second, blind pass.** Mine invented a lock that wasn't there; and a later blind review caught a dozen more places I'd stated inference as fact.

---

## Does it hold? Cross-checks

A single read can fool you (see above), so I checked the conclusion against other firmware and Samsung's own source. These compare *string sets and keys*, and — for the big 2023 rewrite — I did **not** disassemble the changed code, so read "same locks" as "same keys and lock strings," not a full code audit.

**1. The previous build.** The prior build `A102USQUBAUJ1` (Oct 2021, ~6 months before ours) differs by **2276 bytes (0.05%) across ~20 regions** — version strings, per-image checksums, regenerated signatures, and a few SLSI header fields (one tracks bootloader `11 → 13`). No wholesale code change.

**2. The next build (OS-major).** The Android-11 build `A102USQUGCWH1` (Aug 2023, an **AT&T** package — a carrier sibling, *not* my T-Mobile phone's build) has **30.55% of the bootloader rewritten**. But the **AVB root key is unchanged** and the **KG/AVB/rollback string sets are byte-identical**. A major rebuild that keeps the same root of trust and the same lock vocabulary — the rewritten 30% I didn't read instruction-by-instruction.

**3. The encrypted pre-boot stage, across four builds.** `sboot` carries an encrypted blob (roughly file `0x32e0`–`0x1b420`) preceded by a plaintext `[SECLIB] Moonstone-…` tag — a secure library stage. Hashing the encrypted body across the four `sboot` images on hand:

| build | OS | variant | encrypted body |
|---|---|---|---|
| BAUJ1 (2021) | Android 9 | T-Mobile | **body A** |
| AVD1 (2022) | Android 9 | T-Mobile | **body A** (identical) |
| GCWH1 (2023) | Android 11 | AT&T | **body B** |
| U1 GCWH1 (2023) | Android 11 | unlocked | **body B** (identical) |

So it's **identical within an Android version and across carrier vs unlocked, and different across the OS-major bump**. The plaintext `[SECLIB] Moonstone` header is identical in all four (a 16-byte field next to it changes in 2023). The body is uniformly random (H ≈ 7.998/8). That reads as a per-OS-version secure-library stage, not a per-device secret — but whether the 2023 change is a true re-key or just a new IV on the same library, I can't tell, and "signed" is an assumption from the `SECLIB` framing, not shown.

**4. The unlocked sibling.** The unlocked `SM-A102U1` and the carrier `SM-A102U` AT&T build (both Aug 2023) differ by ~16% (421 regions, which I did *not* characterise). What I *can* line up — the AVB keys and the OEM-unlock-related code/strings (`get_oem_unlock_val`, FRP, carrierid) — matches, and the clearest difference is the sales string `USA:SINGLE` (carrier) vs `USA:OPEN` (unlocked). So the evidence points to the lock being **provisioning, not a crippled bootloader**, with the honest caveat that I matched the unlock machinery by its strings (at shifted offsets), not by diffing all 16%.

**5. Samsung's own kernel source.** Samsung publishes the GPL kernel source (4.4.177, the `A102U1` drop — close to, but not the same build as, the 4.4.111 binary I read in Ghidra). The SELinux enforce behaviour is there: a build-time `-DCONFIG_ALWAYS_ENFORCE=true` (from `security/selinux/Makefile`, gated on user + ship + enforce) makes `sel_write_enforce` force `enforcing`, and `RKP_KDP=y` moves the enforce flag under hypervisor protection. The source matches the mechanism I read in essence (I'm not quoting it verbatim — the shape, not the exact lines). RKP, DEFEX, FIVE and PROCA source are present; the TIMA LKMAUTH source is withheld.

**And the modem, briefly:** the `CP` bundle is a Samsung **Shannon** baseband (`ShannonOS 3.5 R7`). The A10e is a 4G LTE device; the firmware is the shared Shannon codebase (it carries some NR/ENDC support strings, which don't mean the model has 5G). The 2022→2023 modem is the same OS family — a refresh, not a new baseband. (I read this less deeply than the bootloader; the CPU core and an absolute "no 5G" I'm not asserting.)

---

## The walls (what I could *not* read)

- **The encrypted payloads.** `cm.bin`'s module payload and `sboot`'s `[SECLIB]` body are encrypted; no key ships in the firmware, so their plaintext is unrecoverable statically. The `AP/meta-data/fota.zip` (312 entries, the OTA kit) is encrypted too.
- **The TEEGRIS OS body.** `startup.tzar.lz4` isn't in the image set I have, so the trusted apps can't be extracted from this download, and I couldn't even pin which partition it lives on.
- **The startup indirection.** sboot's very first hop goes through a function pointer filled in at runtime in on-chip SRAM (`0x020200a8`), so a static trace can't follow the earliest boot. (The later kernel hand-off and the Odin dispatch *were* resolved statically — those aren't walls.) Emulating the early path would need QEMU/Unicorn plus modelling the Exynos peripherals and the encrypted stages — a big lift for little payoff, scoped and parked.

None of these change the conclusion; they're the parts a static read can honestly only point at.

---

## Tools

All free and local: Samsung's firmware via `samloader` for the 2022/2021 builds (the 2023 builds came from a third-party firmware mirror, since the headless fetch of newer builds is blocked at Samsung's servers); `lz4`, `simg2img`, `debugfs`, `avbtool` for unpacking; Ghidra (via REA) for analysis, plus `capstone` (through a `ctypes` wrapper) for the byte-level disassembly and the ADRP phase sweep; `binwalk` for a first pass; `checkpolicy` + `setools-console` for the SELinux policy; small Python scripts for the reference work. All told, the static read ran to **897 REA (Ghidra) operations** across two analysis sessions — 616 in the dedicated `sboot` pass and 281 in the follow-ups. `heimdall` connected to the phone in download mode and the Odin protocol initialised, but the session closed without returning a PIT and nothing was flashed — so no live PIT/flash demo on Linux. The only device contact was that read-only `adb` sweep (`getprop`, `pm list`, the by-name map) and the heimdall session; no partition was written.

## Reproducing

The `tools/` scripts regenerate the maps and disassembly from the firmware in `firmware/`. Run `tools/phase_test.py <sboot.bin>` first to confirm the page phase (`0x800`), then set the Ghidra image base to `0x8ef9e800`. Derived artifacts (boot screens, carved ELFs, the extracted key, the cross-build sboots) land in `out/` and aren't committed, since they rebuild from the bundles.
