# a10e firmware teardown

poking at the stock firmware on a parked **Samsung Galaxy A10e (SM-A102U)** - a cheap, carrier-locked US phone i had sitting around.

it started dumb and simple: i wanted an old phone as a pet cam for the dogs while i'm at work, running LineageOS the way i'd already done on two Galaxy Tab A8s. this one wouldn't play along. turns out it's locked down in a way the tablets never were - so instead of a custom ROM i ended up reading how a modern Android phone decides what it's allowed to boot, and why a carrier-locked one is a dead end for custom ROMs.

the phone, the idea and the questions are mine. the actual reverse-engineering - the disassembly, carving the keys out, the cross-build diffs - was Claude Code driving [Ghidra](https://github.com/NationalSecurityAgency/ghidra) through the [REA](https://github.com/morluto/rea) toolkit, over two sessions. then the whole writeup got a blind second review before i called it done.

## what this actually is

almost all of it is **static analysis** of firmware downloaded from Samsung. the only time anything touched the phone it was read-only - an `adb` getprop/package/partition sweep while it was booted, and a download-mode session where `heimdall` connected but pulled nothing and flashed nothing. **no partition ever got written, and no lock got bypassed.** i wasn't trying to crack anything. the point was to read the locks and actually get how they work.

there's also a mistake left in on purpose. a wrong ARM64 addressing assumption (the `ADRP` page phase) quietly turned a boring partition-table check into an imaginary "carrier lock" in an early draft. honestly it's the most useful thing in here - it's why the whole writeup went thru a second, blind review, which caught about a dozen more spots where a guess had been written up as fact.

## what it found (short version)

- the A10e is Project-Treble compliant, but the bootloader is **locked** and this US-carrier model gives you no way to unlock it - so no GSI or custom kernel actually boots.
- the lock it really enforces at boot is **verified boot (AVB)**: the bootloader refuses any boot/system image that isn't signed by one specific 4096-bit RSA key (fingerprint `e553992a79ab561a4805371cce123d1ee73db21b`).
- two more locks sit next to it: **Knox Guard** (a carrier/financing flash gate, with a signed engineering-token escape hatch) and the **TEEGRIS** TrustZone secure world (it holds status bits normal code can read but not change).
- the finding holds across the previous build, the next (Android 11) build, the *unlocked* sibling model, and Samsung's own published kernel source - the AVB key and the lock strings don't change.

the full story - real addresses, the AVB key tie, the SELinux policy read, the four cross-checks and the bug - is in **[`A10e-teardown.md`](A10e-teardown.md)**. that's the one to read.

## what's in here

| path | what it is |
|---|---|
| [`A10e-teardown.md`](A10e-teardown.md) | the full writeup |
| `.archify/architecture-a10e-trust-20261026-193833/` | boot-chain trust diagram - who verifies whom at boot - as standalone HTML + PNG |
| `.archify/architecture-a10e-trust-expanded-20261028-122000/` | the same chain plus the SELinux-fenced secure world, HTML + PNG |
| `tools/` | small Python scripts that rebuild the maps and disassembly - the ADRP phase sweep (`phase_test.py`), the load-base finder (`findbase.py` / `pin_base.py`), the partition map (`pitmap.py`), the cross-build `sboot` diff (`sboot_diff.py`), the AVB key tie (`vbmeta_key_tie.py`), and others |

the firmware bundles themselves aren't in here - they're big and you can just redownload them. grab them with `samloader`, then point the `tools/` scripts at your own copies. derived stuff (the carved AVB key, boot screens, the TEEGRIS ELFs, the cross-build sboots) rebuilds into `out/`, which is left untracked.

## the method in one line

load `sboot.bin` raw, measure the `ADRP` page phase with `tools/phase_test.py` (it's `0x800`, not `0`), pin the load base at `0x8ef9e800` from the absolute pointer tables, and only then does Ghidra follow the in-image pointers and resolve the AVB and Knox Guard paths to their own strings. the static read ran to **897 Ghidra operations** across the two sessions.

## tools

all free and local: `samloader` for Samsung firmware, `lz4` / `simg2img` / `debugfs` / [`avbtool`](https://android.googlesource.com/platform/external/avb/) for unpacking, [Ghidra](https://github.com/NationalSecurityAgency/ghidra) (via [REA](https://github.com/morluto/rea)) plus [`capstone`](https://github.com/capstone-engine/capstone) for the byte-level disassembly and the phase sweep, [`binwalk`](https://github.com/ReFirmLabs/binwalk), and `checkpolicy` + [`setools`](https://github.com/SELinuxProject/setools) for the SELinux policy.

## license

the scripts and the write-up are GPL-3.0 - see `LICENSE`. the `.archify/` diagrams were made with [archify](https://github.com/tt-a1i/archify), and the generated pages carry its runtime and the JetBrains Mono font (OFL-1.1) under their own licenses.

---

*hobby project, nothing to do with Samsung. nothing here bypasses a lock or turns one on - it's just a read of how the locks work. the reverse-engineering was Claude Code with the REA / Ghidra toolchain, and the writeup got a blind review before i called it done.*
