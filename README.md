# A10e firmware teardown

A hobby reverse-engineering teardown of the stock firmware on a parked **Samsung Galaxy A10e (SM-A102U)** — a cheap, carrier-locked US phone.

It started as a simple idea: turn an old handset into a pet camera for the dogs while I'm at work, running LineageOS the way I'd already done on two Galaxy Tab A8s. This phone turned out to be locked down in a way the tablets weren't — so instead of a custom ROM it became a full read of *how* a modern Android phone decides what it's allowed to boot, and why a carrier-locked one is a dead end for custom ROMs.

The phone, the firmware, and the questions are mine. The reverse-engineering itself — the disassembly, the key-carving, the cross-build diffs — was done with **Claude Code driving [Ghidra](https://github.com/NationalSecurityAgency/ghidra)** through the [REA](https://github.com/morluto/rea) toolkit, over two analysis sessions. The writeup then went through a blind review pass before it was called done.

## The honest framing

Almost all of this is **static analysis** of firmware downloaded from Samsung. The only contact with the phone itself was read-only — an `adb` property/package/partition sweep while it was booted, and a download-mode session where `heimdall` connected but pulled nothing and flashed nothing. **No partition was ever written, and no lock was bypassed.** The whole point was the opposite: to *read* the locks and understand them.

There's also a mistake kept in on purpose. A wrong ARM64 addressing assumption (the `ADRP` page phase) silently turned an ordinary partition-table check into an imaginary "carrier lock." It's the most useful thing in here, and it's why the whole writeup went through a second, blind review to catch others like it — which found about a dozen more places where inference had been written up as fact.

## What it found (short version)

- The A10e is Project-Treble compliant, but its bootloader is **locked**, and this US-carrier model exposes no way to unlock it — so in practice no GSI or custom kernel boots.
- The lock actually enforced at boot is **verified boot (AVB)**: the bootloader refuses any boot/system image not signed by a specific 4096-bit RSA key (fingerprint `e553992a79ab561a4805371cce123d1ee73db21b`).
- Two more locks sit alongside it: **Knox Guard** (a carrier/financing flash gate, with a signed engineering-token escape hatch) and the **TEEGRIS** TrustZone secure world (which holds status bits normal code can read but not change).
- The finding holds across the previous build, the next (Android 11) build, the *unlocked* sibling model, and Samsung's own published kernel source: the AVB root key and the lock strings don't change.

The full story — real addresses, the AVB key tie, the SELinux policy read, the four cross-checks, and the bug — is in **[`A10e-teardown.md`](A10e-teardown.md)**. That's the one thing to read.

## What's in this repo

| Path | What it is |
|---|---|
| [`A10e-teardown.md`](A10e-teardown.md) | The full writeup. |
| `.archify/architecture-a10e-trust-20261026-193833/` | Boot-chain trust diagram — who verifies whom at boot — as standalone HTML + PNG. |
| `.archify/architecture-a10e-trust-expanded-20261028-122000/` | Expanded diagram: the boot chain *plus* the SELinux-fenced secure world. HTML + PNG. |
| `tools/` | Small Python scripts that regenerate the maps and disassembly — the ADRP phase sweep (`phase_test.py`), the load-base finder (`findbase.py` / `pin_base.py`), the partition map (`pitmap.py`), the cross-build `sboot` diff (`sboot_diff.py`), the AVB key tie (`vbmeta_key_tie.py`), and others. |

The firmware bundles themselves are **not** included — they're large and freely redownloadable. Fetch them with `samloader`, then point the `tools/` scripts at your own copies. Derived artifacts (the carved AVB key, boot screens, the extracted TEEGRIS ELFs, the cross-build `sboot` images) rebuild into `out/`, which is left untracked.

## Method, in one line

Load `sboot.bin` raw, measure the `ADRP` page phase with `tools/phase_test.py` (it's `0x800`, not `0`), pin the load base at `0x8ef9e800` from the absolute pointer tables, and only then does Ghidra's analysis follow the in-image pointers and resolve the AVB and Knox Guard paths to their own strings. The static read ran to **897 Ghidra operations** across the two sessions.

## Tools

All free and local: `samloader` for Samsung firmware; `lz4`, `simg2img`, `debugfs` and [`avbtool`](https://android.googlesource.com/platform/external/avb/) for unpacking; [Ghidra](https://github.com/NationalSecurityAgency/ghidra) (via [REA](https://github.com/morluto/rea)) for analysis, plus [`capstone`](https://github.com/capstone-engine/capstone) for the byte-level disassembly and the phase sweep; [`binwalk`](https://github.com/ReFirmLabs/binwalk) for a first pass; `checkpolicy` and [`setools`](https://github.com/SELinuxProject/setools) for the SELinux policy.

---

*Hobby project, not affiliated with Samsung. Nothing here bypasses a lock or enables one — it's a read of how the locks work. The reverse-engineering was done by Claude Code with the REA / Ghidra toolchain; the writeup was blind-reviewed before being called done.*
