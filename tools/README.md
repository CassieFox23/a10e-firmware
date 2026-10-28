# tools

small python scripts behind the teardown. rough hobby code, no packaging, no tests. they only read the files you point them at; the only things they write are the json and png files named below.

**which firmware.** the main build is `A102USQSDAVD1` (2022, T-Mobile). most scripts hardcode offsets or addresses from its `sboot.bin`, plus the load base `0x8ef9e800` and the ADRP page phase `0x800`. in the two 2023 builds (`A102USQUGCWH1`, and the unlocked `SM-A102U1` GCWH1) the first AVB key sits at `0x12d070` instead of `0x12b070`, so offset-pinned scripts won't line up there. the 2021 build (`A102USQUBAUJ1`) has the key at `0x12b070` too, but nothing else was checked on it. scripts marked "any build" or "no build constants" have no hardcoded offsets.

**where the inputs come from.** download the bundles yourself (see the main README), `tar -xf` them, then `lz4 -d x.lz4 x`. `sboot.bin`, `cm.bin`, `param.bin` and `vbmeta.img` come from the `BL_*.tar.md5` bundle (as `sboot.bin.lz4` etc), `boot.img` from `AP_*`, `modem.bin` / `modem_debug.bin` from `CP_*`, the PIT from `CSC_*`.

## needs

- Python 3. the stdlib covers everything except the items below
- the system capstone library (not `pip install capstone`), loaded through `ctypes` with `find_library('capstone')` and a `/usr/lib64/libcapstone.so.5` fallback. used by `pin_base.py`, `phase_test.py`, `phase08_refs.py`, `capref.py`, `capref2.py`, `capref_full.py`, `cmbin_movk.py`, `smc_scan2.py`
- the Python `capstone` binding: only `sboot/pre-fix/disasm.py`
- numpy and matplotlib for `entropy_plot.py`; matplotlib alone for `sboot_diff_chart.py`
- `tar` and `lz4` on PATH for `fwmap.py`
- the rest need no capstone; `aa64refs.py` is pure python and decodes the instructions itself

## firmware map / partitions

- `fwmap.py <fw_dir> <out.json>` - walks every `*.tar.md5` in `<fw_dir>`, sniffs each member's first 8 KiB (sparse image, boot image, vbmeta, DTB, PIT, ext4, tar, zip) and writes one json row per file (`bundle`, `file`, `packed`, `unpacked`, `kind`, `full`). `.lz4` members are streamed through `lz4 -dc` just to measure them. prints `N files mapped`. the bundle name is the filename before `_A102U`. no build constants.
- `pitmap.py <pit.txt> <files.json>` - joins a PIT text dump with the json from `fwmap.py` and prints a markdown table (bundle, file, partition and ID, slot size, unpacked size, type), then a "Not in this firmware" list. `<pit.txt>` is `--- Entry #N ---` blocks with `Partition Name:`, `Partition ID:`, `Start Block:`, `Partition Block Count:` and `Flash Filename:` lines. skips `meta-data/` rows; slot size is blocks x 512 B. no build constants.

## sboot load base and ADRP phase

- `findbase.py <sboot.bin>` - the first try, kept as the false start. takes every 4-byte-aligned u64 in `0x10000`-`0xffffffff`, finds the densest 4 MiB window and prints it with aligned-base guesses and the top 1 MiB buckets. lands on `0x8f000000`, which is wrong. any build (assumes a 4 MiB image).
- `phase_test.py <sboot.bin>` - the ADRP phase check. disassembles the image at a page-aligned base `0x8ef9e000` and counts the `adrp`+`add` pairs that land on a C string start under phase `0` vs `0x800` (those two only, not a full sweep). prints both counts with sample strings and a `SUMMARY` line. base hardcoded, no offsets.
- `pin_base.py <sboot.bin>` - lands on the load base `0x8ef9e800`. collects landmarks (string starts, `bl` targets as file offsets), then every 8-byte-aligned pointer in `0x40000000`-`0xffffffff` votes `base = pointer - landmark`, phase `0x800` only. prints the landmark counts, the top 12 bases with votes, and sample pointer to landmark lines for the winner. `0x8ef9e800` is only a disassembly address here; the base comes from the votes. any build.
- `sboot/base_confirm.py <sboot.bin>` - a cross-check, not a finder. lists function prologues in file `0x30000`-`0xd0000` and matches pointers in `0x8ef00000`-`0x8f100000` against them at phase `0x800`. prints the counts and the top 6 bases. build-specific ranges, build not stated.
- `phase08_refs.py <sboot.bin>` - re-resolves `adrp`+`add` references at the right phase `0x800` and reports file offsets: distinct targets inside the encrypted blob (`0x3400`-`0x1b400`), references to the two AVB key copies (`0x12b070`, `0x322410`), string targets of code in `0x6f000`-`0x72000`, a raw-byte lookup of key strings (`pit_check_integrity`, `guid_part`, `AVB pubkey is not matched` and others), and refs from code in `0x71900`-`0x719c0` and `0x6f880`-`0x70a80`. tied to A102USQSDAVD1.

## AVB key tie

- `vbmeta_key_tie.py <vbmeta_pubkey.bin> <sboot.bin>` - checks that sboot embeds the same AVB public key as vbmeta. reads the libavb key blob (1032 bytes for RSA-4096: 8-byte header, modulus, rr) carved out of `vbmeta.img`, then searches sboot for the whole blob and for the modulus alone. prints the sha256s, the offsets of both, and whether the blob carved 8 bytes before each modulus hit equals the vbmeta key. any build.
- `bootimg_tie.py <boot.img>` - ties `boot.img` to the `boot` hash descriptor in vbmeta: sha256(salt + first 29315616 bytes) against the digest hardcoded in the script, then prints the Android boot header (v1 layout: sizes, load addresses, page size, name, cmdline) and compares `kernel_addr` with `0x80080000`. tied to A102USQSDAVD1 (salt, digest and size are its `boot` descriptor).

## cross-build diffs and charts

- `sboot_diff.py <OLD_sboot.bin> <NEW_sboot.bin>` - byte-diffs two sboot builds (usage and exit 2 without exactly two args): differing regions merged within 16 bytes, the AVB RSA-4096 key blobs in each (found by structure, so offset-independent) and which are shared, whether the high-entropy region `0x3400`-`0x1b400` changed, and marker strings (KG lock, AVB, rollback, build) found on one side only. that region is hardcoded, build not stated; otherwise any pair of builds.
- `sboot_diff_chart.py [out.png]` - draws the three-bar chart of how much `sboot.bin` changed between builds. reads no firmware: 30.55%, about 16% and 0.05% are hardcoded from the teardown's cross-checks section, with the build names in the labels. default output is `figures/sboot-diff-chart.png`. prints the path.
- `entropy_plot.py <in_dir> <out_dir>` - windowed Shannon entropy plots; `<out_dir>` must already exist. writes `entropy-sboot.png` from `<in_dir>/sboot.bin` (marks the encrypted blob `0x32e0`-`0x1b420`, the edge `0x1b400`, the 90 KiB data table `0x12c800`-`0x143000` with its chi-square, and the key copies `0x12b070` / `0x322410`), then `entropy-overview.png` only if `<in_dir>` also has `cm.bin`, `vbmeta.img`, `param.bin`, `modem.bin` and `modem_debug.bin` (otherwise it says it skipped it). prints the blob's and the table's entropy and chi-square. the sboot figure is tied to A102USQSDAVD1 (its title names the build and checksum `0xfdcdbc1d`).

## sboot references and call graph (base `0x8ef9e800`)

- `aa64refs.py <sboot.bin> <refs.json>` - pure-python scanner: decodes `adrp` (+`add` / `ldr`), `adr` and `bl` over the whole image. prints counts, a control check on three known strings, refs landing in the three embedded ELFs and in the two high-entropy regions, then writes the full index to `<refs.json>` for `analysis.py`. tied to A102USQSDAVD1 (hardcoded base, ELF offsets, regions).
- `analysis.py <sboot.bin> <refs.json>` - reads the json from `aa64refs.py` (`capref.py` writes the same layout). prints callers of BL-called functions in two file ranges (`0xf5000`-`0xf8000`, around the AES S-box, and `0x116000`-`0x119000`, around the libjpeg string), who references partition and image-name strings, and entropy / chi-square / serial-correlation stats for the two high-entropy regions. both ranges are written as `BASE` + file offset, at the pinned base.
- `analysis2.py <sboot.bin>` - like `aa64refs.py` plus bare `adrp` page tracking. finds the AES forward and inverse S-boxes by byte pattern and lists the functions that `adrp` into their pages with their callers (any build), then does the same for the libjpeg copyright string at file `0x118d60` (`BASE` + offset).
- `capref.py <sboot.bin> <refs.json>` - operand-level scan through system capstone, tracking register values through `adrp` / `add` / `sub` / `mov` so `adrp; add; ldrb [base, idx]` S-box accesses count. only file `0`-`0xf3000`. prints the functions that touch the inverse S-box (`0x8f094900`-`0x8f094a00`) and the forward one (`0x8f09d5d8`-`0x8f09d6d8`) with callers, and writes the index to `<refs.json>`. tied to A102USQSDAVD1 (the S-box VAs sit at file `0xf6100` and `0xfedd8` there).
- `capref2.py <sboot.bin>` - hunts where four hardcoded VAs (`0x8f073a70`, `0x8f073ae8`, `0x8f073c24`, `0x8f073e3c`) are built (`movz` / `movk` / `adrp`+`add`), named in an operand, or stored. prints each site with the 7 instructions up to and including it, then a total. file `0`-`0xf3000` only. what the four addresses are isn't stated in the script; build not stated.
- `capref_full.py <sboot.bin>` - whole-image version of the operand-level scan (the script notes that linear decode desyncs on data, so use it for lookups of specific VAs). prints code ref sites and enclosing functions for the Odin-protocol strings (`ODIN`, `LOKE`, `DVIF`, `PIT`, `Download`), both AVB key copies, the callers of a pubkey-validator at `0x8f048a98`, and two rollback strings. tied to A102USQSDAVD1 (spot-checked: `ODIN`, `LOKE`, `DVIF`, `Download` and the key copy resolve at the pinned base).

## secure world / cm.bin / SMC scans

- `cmbin_parse.py <cm.bin>` - parses the Crypto Manager (LDFW) container: the first 12 `0x10adab1e` magics with their first 12 words and the name at +0x30, strings mentioning CryptoManager / RPMB / TEEGRIS and similar, a search for six SMC function ids as raw words, and a count of the halfword `0xc200`. then sha256(salt + first 4112912 bytes) against the vbmeta `cm` digest hardcoded in the script. tied to A102USQSDAVD1 (salt, digest, size are its `cm` descriptor).
- `cmbin_movk.py <cm.bin>` - finds `movk` / `movz` with `#0xc200, lsl #16` (the high half of the SMC function ids), lists each hit with its VA and module, and disassembles 6 instructions before and 9 after for the first 12. file offsets map to load VAs through a hardcoded six-module table (`CryptoManagerV40`, `fmp_fw_V20`, `drm_fw`, `srpmb_fw`, `hdcp_fw`, `tail_fw`). build-specific constants, build not stated.
- `smc_scan2.py <sboot.bin>` - finds `smc #0` and `hvc` in the code region (file `0`-`0xf3000`, base `0x8ef9e800`), tracks `movz` / `movk` / `mov` / `adrp` / `add` / `orr` and prints x0 (the function id) and x1-x3 at each `smc #0` with the 13 instructions before it. also lists up to 8 other `smc` / `hvc` hits, which are likely data decoded as code. tied to A102USQSDAVD1 (hardcoded base and code end).

## modem

- `modem_toc.py <modem.bin> [<modem2.bin> ...]` - parses the Shannon modem table of contents at offset 0 (32-byte entries: `name[12]`, offset, load address, size, crc, id, u32 LE), checks that each section fits the file, then from `MAIN` prints version / build strings (`Shannon`, `CP Version`, `RELDATE`, `a10e`), counts of radio keywords (a count is not proof of a capability) and up to 12 NR / 5G strings. reads `modem.bin` from the `CP` bundle (`modem_debug.bin` is a zip, so it stops at once there); no build constants. the header suggests `python3 -I`.

## pre-fix (wrong phase, kept for the record)

`tools/sboot/pre-fix/` holds scripts from before the ADRP phase was measured. they use phase `0` (or base `0x80000000`), so their references land 2 KB off. they are left as they were, so they still give wrong answers on purpose. use `phase_test.py` and `pin_base.py` for real results. offsets in them are from the 2022 build (A102USQSDAVD1). two labels in their tables (`0x102928` "KG locked", `0x102780` "TEEGRIS noarg") don't match the text at those offsets.

- `sboot/pre-fix/kgrefs.py <sboot.bin>` - prints `adrp`+`add` references that land in file `0xff000`-`0x104000` (the Knox Guard string area), with the string text. pages are built from file offsets, so phase 0.
- `sboot/pre-fix/findrefs2.py <sboot.bin>` - looks for `adrp` + `add` pairs (up to 16 instructions apart) that build six hardcoded string offsets, phase 0. prints the first 6 hits per string.
- `sboot/pre-fix/findbase5.py <sboot.bin>` - votes for a base from pointers in `0x88000000`-`0x98000000` against eight hardcoded string offsets, only accepting page-aligned bases (phase 0), so it can never find `0x8ef9e800`. prints the bases implied per string and any agreed by 2 or more.
- `sboot/pre-fix/disasm.py <sboot.bin> <start_hex> <end_hex>` - disassembles a file range with the Python `capstone` binding at base `0x80000000` and annotates `adrp`+`add` targets with the string they point at (wrong base, so wrong labels). start and end are hex file offsets.
