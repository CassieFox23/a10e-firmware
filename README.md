# a10e firmware teardown

poking at the stock firmware on a parked **Samsung Galaxy A10e (SM-A102U)** - a cheap, carrier-locked US phone i had sitting around.

it started dumb and simple: i wanted an old phone as a pet cam for the dogs while i'm at work, running [LineageOS](https://lineageos.org) the way i'd already done on two Galaxy Tab A8s. this one wouldn't play along. turns out it's locked down in a way the tablets never were - so instead of a custom ROM i ended up reading how a modern Android phone decides what it's allowed to boot, and why a carrier-locked one is a dead end for custom ROMs.

the phone, the idea and the questions are mine. the actual reverse-engineering - the disassembly, carving the keys out, the cross-build diffs - was [Claude Code](https://github.com/anthropics/claude-code) (mostly Opus, with Sonnet helpers on some side passes) driving [Ghidra](https://github.com/NationalSecurityAgency/ghidra) through the [REA](https://github.com/morluto/rea) toolkit, over two sessions. then blind reviews went over the writeup before i called it done.

the whole shape in one picture - the locks at boot, then a [SELinux](https://github.com/SELinuxProject) fence once it's running:

![the A10e boot chain (verified boot from the bootloader down) and the SELinux-fenced TEEGRIS secure world](.archify/architecture-a10e-trust-expanded-20261028-122000/a10e-trust-expanded.png)

## what this actually is

almost all of it is **static analysis** of firmware downloaded from Samsung. the only time anything touched the phone it was read-only - an [`adb`](https://android.googlesource.com/platform/packages/modules/adb/) getprop/package/partition sweep while it was booted, and a download-mode session where [`heimdall`](https://git.sr.ht/~grimler/Heimdall) could see the phone but never got the partition table, and flashed nothing. **no partition ever got written, and no lock got bypassed.** i wasn't trying to crack anything. the point was to read the locks and actually get how they work.

there's also a mistake left in on purpose, and it's kinda the most useful thing in here. ARM64 code finds its own strings thru `ADRP` instructions, which only work if you know the load address's page phase. an early draft assumed the wrong phase, and that quietly turned a boring partition-table check into a made-up Knox Guard "token gate". a blind second pass in another session flagged it, and Claude re-checked it and confirmed it. later blind reviews caught more spots where a guess had been written up as fact.

## what it found (short version)

- the A10e is Project-Treble compliant (Android's split that lets one generic system image, a GSI, run on lots of phones), but the bootloader is **locked** and OEM unlocking isn't allowed on this unit (`sys.oem_unlock_allowed=0`) - so no GSI or custom kernel boots. these US-carrier phones are known for not exposing a working toggle, tho these files don't prove that part.
- the lock it really enforces at boot is **verified boot ([AVB](https://android.googlesource.com/platform/external/avb/))**: while it's locked, the bootloader refuses any boot/system image that isn't signed by one specific 4096-bit RSA key (fingerprint `e553992a79ab561a4805371cce123d1ee73db21b`).
- two more locks sit next to it: **Knox Guard** (a carrier/financing flash gate, with a hatch for a Samsung-signed engineering token) and the **TEEGRIS** TrustZone secure world, which runs Samsung's trusted apps apart from Android and guards their secrets more than it guards what boots (SELinux keeps normal apps away from it, Knox DAR aside).
- the AVB key and the lock strings stay the same across the previous build, a much later (Android 11) build and the *unlocked* sibling model - that's by keys and strings, not a full code read. Samsung's own published kernel source backs the SELinux side.

why Lineage can't go on, drawn out - the locked bootloader is the wall you actually hit, and the VINTF check (Treble's version match between the system image and the phone's vendor code) is a second one behind it:

![two walls: wall 1 is the locked bootloader with OEM unlocking not allowed and AVB only taking Samsung's key, wall 2 is the VINTF level mismatch (vendor level 3 vs GSI levels 4 to 8), and the Tab A8s got past wall 1 because they allow OEM unlock](.archify/workflow-a10e-two-walls-20261028-161640/a10e-two-walls.png)

and how much the bootloader changed between builds, compared byte position by byte position - the AVB key never did:

![how much sboot.bin changed: 30.55% of byte positions differ between the 2022 phone build and the 2023 AT&T build, about 16% between the unlocked and carrier 2023 builds, 0.05% from the 2021 build; the AVB root key is the same in all three](figures/sboot-diff-chart.png)

the bootloader image (`sboot.bin`) entropy, plotted - the encrypted pre-boot stage is the flat band right at the start, then the code drops lower. the other flat band up top is a 90 KB data table (dense, but structured, not encrypted), and the two AVB key copies are the thin lines:

![sboot.bin entropy - the encrypted pre-boot blob near the maximum, the ARM64 code lower, a 90 KB structured data table that also reads near the top, and the two 1 KB AVB key copies as thin lines](figures/entropy-sboot.png)

the full story - real addresses, the AVB key tie, the SELinux policy read, the four cross-checks and the bug - is in **[`A10e-teardown.md`](A10e-teardown.md)**. that's the one to read.

## the hardware

what's actually on the board, pulled from the device tree and its board overlays - the [appendix](A10e-hardware-appendix.md) has the full list:

![the A10e hardware from the device tree: the Exynos SoC blocks in the base tree, and the board layer (PMICs, charger, codec, touch, sensors, cameras, NFC) named by the three dtbo.img overlays](.archify/architecture-a10e-hardware-20261028-151200/a10e-hardware.png)

## what's in here

| path | what it is |
|---|---|
| [`A10e-teardown.md`](A10e-teardown.md) | the full writeup |
| [`A10e-hardware-appendix.md`](A10e-hardware-appendix.md) | the hardware map - every `dt.img` node with a `compatible` (170 of 430), the board parts the `dtbo.img` overlays name, the CPU/RAM layout, SoC vs board |
| `.archify/architecture-a10e-trust-20261026-193833/` | boot-chain trust diagram - who verifies whom at boot - as standalone HTML + PNG |
| `.archify/architecture-a10e-trust-expanded-20261028-122000/` | the same chain plus the SELinux-fenced secure world, HTML + PNG |
| `.archify/architecture-a10e-hardware-20261028-151200/` | the hardware map - SoC blocks and the board layer - HTML + PNG |
| `.archify/workflow-a10e-two-walls-20261028-161640/` | why Lineage can't go on - the two walls - HTML + PNG |
| `.archify/workflow-a10e-adrp-bug-20261028-161541/` | the `ADRP` page-phase bug, step by step - HTML + PNG |
| `figures/` | the entropy plots and the cross-build change chart (made by `tools/entropy_plot.py` and `tools/sboot_diff_chart.py`) |
| `tools/` | small Python scripts that rebuild the maps and disassembly - the ADRP phase check (`phase_test.py`), the load-base finder (`pin_base.py`; `findbase.py` is the first try, which landed on the wrong base), the partition map (`pitmap.py`), the cross-build `sboot` diff (`sboot_diff.py`), the AVB key tie (`vbmeta_key_tie.py`), and others. [`tools/README.md`](tools/README.md) says what each one takes, and `tools/sboot/pre-fix/` keeps the four old wrong-phase scripts for the record |

## get the files

the firmware bundles aren't in here - they're big and you can just redownload them. the main build is the newest one Samsung's servers still hand out for the T-Mobile A10e, so [`samloader`](https://github.com/topjohnwu/samloader-rs) grabs it without a version:

```
samloader download -m SM-A102U -r TMB -d fw/
```

that's `A102USQSDAVD1` (2022), and you end up with the six `.tar.md5` bundles (unzip first if your downloader hands you a zip). the older `A102USQUBAUJ1` (2021) needs `-v` with its full version string. the two 2023 builds (`A102USQUGCWH1` for AT&T, and the unlocked SM-A102U1 one) came off a firmware mirror, since Samsung's servers wouldn't hand them to a script.

the bootloader lives in the BL bundle, LZ4-compressed:

```
tar -xf fw/BL_A102USQSDAVD1_*.tar.md5 sboot.bin.lz4
lz4 -d sboot.bin.lz4 sboot.bin
```

then point the `tools/` scripts at it. derived stuff (the carved AVB key, boot screens, the TEEGRIS ELFs, the cross-build sboots) went into an untracked `out/` folder here, but the scripts take file paths as arguments, so put yours wherever.

## the method in one line

load `sboot.bin` raw, measure the `ADRP` page phase with `tools/phase_test.py` (it's `0x800`, not `0`), pin the load base at `0x8ef9e800` from the absolute pointer tables (`tools/pin_base.py`), and only then does Ghidra follow the in-image pointers and resolve the AVB and Knox Guard paths to their own strings. the static read ran to **897 Ghidra operations** across the two sessions.

the bug that made it interesting, drawn out - one wrong guess about the page phase, and how measuring it fixed everything after:

![the ADRP page-phase bug: guessing phase 0 sends every reference 2 KB off (about 1,000 clean hits) and turns the partition-table check into a fake Knox Guard gate; measuring phase 0x800 gives about 4,249 clean hits, then 13 name pointers pin the base at 0x8ef9e800](.archify/workflow-a10e-adrp-bug-20261028-161541/a10e-adrp-bug.png)

## tools

all free and local: [`samloader`](https://github.com/topjohnwu/samloader-rs) for Samsung firmware, [`lz4`](https://github.com/lz4/lz4) / [`simg2img`](https://github.com/anestisb/android-simg2img) / [`debugfs`](https://github.com/tytso/e2fsprogs) / [`avbtool`](https://android.googlesource.com/platform/external/avb/) for unpacking, [Ghidra](https://github.com/NationalSecurityAgency/ghidra) (via [REA](https://github.com/morluto/rea)) plus [`capstone`](https://github.com/capstone-engine/capstone) for the byte-level disassembly and the phase sweep, [`binwalk`](https://github.com/ReFirmLabs/binwalk), and [`checkpolicy`](https://github.com/SELinuxProject/selinux) + [`setools`](https://github.com/SELinuxProject/setools) for the SELinux policy.

## samsung

quick note - i'm not affiliated with Samsung at all. nobody there asked for this, helped with it or looked it over. it's just me and a phone i own.

Samsung, Galaxy, Knox and Exynos are Samsung's trademarks. the names are only here because that's what this is about.

there's no Samsung firmware or code in this repo. the stock bundles came straight off Samsung's servers (the two 2023 builds off a firmware mirror), and you can pull your own with [`samloader`](https://github.com/topjohnwu/samloader-rs). the writeup quotes a few short strings, addresses and a key fingerprint - just enough to show where things are.

the kernel cross-check used Samsung's own kernel source from [opensource.samsung.com](https://opensource.samsung.com) - the 4.4.177 release for the unlocked A102U1.

and none of this unlocks or gets around anything on a Samsung phone. it just reads how the locks work.

## license

the scripts and the write-up are [GPL-3.0](https://www.gnu.org/licenses/gpl-3.0.html) - see [`LICENSE`](LICENSE). the `.archify/` diagrams were made with [archify](https://github.com/tt-a1i/archify), and the generated pages carry its runtime and the [JetBrains Mono](https://github.com/JetBrains/JetBrainsMono) font ([OFL-1.1](https://openfontlicense.org)) under their own licenses.

---

*hobby project. the reverse-engineering was Claude Code (mostly Opus, with Sonnet helpers) with the REA / Ghidra toolchain, and blind reviews went over the writeup before i called it done.*
