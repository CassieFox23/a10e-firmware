# Galaxy A10e (SM-A102U) `dt.img`: hardware enumeration

A companion to [`A10e-teardown.md`](A10e-teardown.md) — the hardware side, read out of the device tree.

Static, read-only. Parsed 2026-10-27 with a hand-written FDT reader (`python3 -I`), no `dtc`. Every claim below that says "in the file" was read from `out/extracted/dt.img`. Items marked "likely" or "general knowledge" are interpretation, not something the file states.

## The big finding

**This device tree describes the Exynos SoC only. None of the board-level parts are in it.** There are 170 nodes with a `compatible`, and every one is either a SoC block, a CPU core, a reserved-memory region, or Samsung software plumbing. The I2C, SPI, UART and MMC controllers have no child nodes at all (checked: zero children under any `hsi2c`, `i2c`, `spi`, `uart`, `usi`, `speedy` or `dwmmc` node), and almost all of them are `status = "disabled"`. So there is no PMIC, fuel gauge, charger, touchscreen, accelerometer, magnetometer, image-sensor chip, audio codec, NFC chip, or display panel named anywhere in this file. A keyword sweep over the whole 8 MB image (max77, s2mpu, s2mu, fuel, gauge, charger, battery, tsp, synaptics, himax, melfas, zinitix, focal, goodix, imx, s5k, accel, gyro, magnet, proximity, nfc, codec chips, tcpc, typec, muic, panel, …) found nothing but pin-group names and input-booster key names (see the sweep note below).

Where those parts are described instead wasn't checked. Unverified guess: the board-specific nodes live in `dtbo.img` (same folder, 8,388,608 bytes, not opened) or are added by the bootloader at boot. Parsing `dtbo.img` with the same reader is the obvious next step.

## Container and file facts

| Item | Value |
|---|---|
| dt_table magic | 0xd7b7ab1e, total_size 0x15ce0, 1 entry, page_size 0x800 |
| dt entry | dt_size 0x15ca0, dt_offset 0x40, id 0, rev 0 |
| FDT | magic 0xd00dfeed at 0x40, totalsize 89,248 (0x15ca0), version 17, last_comp_version 16, 430 nodes |
| Number of FDTs in the 8 MB file | 1 (only one 0xd00dfeed magic anywhere) |
| Root compatible | `samsung,armv8`, `samsung,exynos7885` |
| Root `model` | **None.** The root has no `model` property, and no node anywhere has one. Root props are only `compatible`, `dtb-hw_rev` (0), `dtb-hw_rev_end` (0xff), `interrupt-parent`, `#address-cells`, `#size-cells`. The read: the dtb is tagged for hardware revs 0 through 255, i.e. any rev. |
| `chosen/bootargs` | see "Bootargs" below |

The file after the FDT (0x15ce0 onward) is Samsung signing data plus an Android Verified Boot footer, not more device tree. Printable strings in it: `SignerVer02`, `50702675R`, `A102USQSDAVD1`, `20220405200203`, `SM-A102U_NA_ATT_GBL0`, `SRPSB15A013`, `dt.img`, then `AVB0` / `avbtool 1.1.0` / sha256 and an `AVBf` footer at 0x7fffc0. Interpretation (not stated in the file): `SM-A102U_NA_ATT_GBL0` reads as model plus a North America / AT&T region tag, and `20220405200203` looks like a build timestamp of 2022-04-05 20:02:03, which matches the file date on disk.

## Highlights

**CPU (8 cores, from `/cpus`, all `enable-method = psci`)**

| Cluster (MPIDR affinity) | Cores | Core type |
|---|---|---|
| 0 | `cpu@0`, `cpu@1` | 2x ARM Cortex-A73 |
| 1 | `cpu@100`, `cpu@101`, `cpu@102`, `cpu@103` | 4x ARM Cortex-A53 |
| 2 | `cpu@200`, `cpu@201` | 2x ARM Cortex-A53 |

That is 2x A73 + 6x A53. Logical IDs: A53s are 0 to 5, A73s are 6 and 7 (property `logical-id`). The two cluster-2 A53s carry a `sched_skip` property (meaning not checked). Clock speeds are not in these nodes.

**RAM (from the `memory@` nodes, `#address-cells = 2`, `#size-cells = 1`)**

| Node | Base | Size |
|---|---|---|
| `memory@80000000` | 0x80000000 | 0x3da00000 = 986 MiB |
| `memory@C0000000` | 0xC0000000 | 0x40000000 = 1024 MiB |
| `memory@880000000` | 0x8_80000000 | 0 (empty) |
| `memory@900000000` | 0x9_00000000 | 0 (empty) |

Sum = 2,107,637,760 bytes = 2010 MiB = 1.96 GiB (script-computed). It is exactly 2 GiB minus a 38 MiB hole between 0xBDA00000 and 0xC0000000, and the second bank ends exactly at 0x1_00000000. The inference: a 2 GiB part with 38 MiB carved out. Caveat (unverified guess): Samsung bootloaders often rewrite the memory nodes at boot, so this is what the file says, not proof of the installed RAM.

**Model string:** none in the file (see above). The only identity strings are the root `compatible` (`samsung,exynos7885`), the bootarg `androidboot.hardware=samsungexynos7885`, and the signer footer (`SM-A102U_NA_ATT_GBL0`).

## Priority classes

| Class | In dt.img? | What the file actually has |
|---|---|---|
| PMIC / power management | No chip named | `samsung,exynos7885-pmu` + `syscon` at `/system-controller@11c80000` and `samsung,exynos-pmu` are the SoC's own power-management register block, **not** a PMIC chip. `samsung,exynos-acpm` (+ `-ipc`, `-dvfs`) is the SoC's power co-processor, likely what drives the PMIC (general knowledge). `samsung,exynos-speedy` at `/speedy@11CE0000` is Samsung's proprietary PMIC-style bus, disabled. Bootarg `pmic_info=0x3` is a flag handed to the kernel (meaning not verified). |
| Fuel gauge / charger | **None** | No node, no string. |
| Touchscreen controller | **None** | The only "touch" hits are `TOUCHKEY` / `TOUCH` / `MULTITOUCH` names under `/input_booster`, a software CPU-boost helper. |
| Accelerometer / magnetometer / other sensors | **None** | No sensor nodes. `/adc@120A0000` (`samsung,exynos-adc-v3`) is the SoC's general ADC; what is wired to it is not in the file. Thermal zones `BIG`, `LITTLE`, `G3D` are the SoC's own temperature sensors. |
| Camera image sensors | **Not named** | SoC side only: `/fimc_is@14450000` ISP, 4x `/fimc_is_sensor@144x0000` interface slots, 4x MIPI CSI D-PHY (`phy_isp_csis0..3`), 3 sensor master clocks (`CIS_CLK0..2`), `/gdc` distortion correction. How many physical cameras the phone has, and their chips, is not in this file. |
| Audio codec | **Not named** | SoC ABOX audio DSP (`/abox@0x14A50000`, 8 read + 5 write DMA channels). Pin groups `aud-codec-mclk`, `aud-codec-bus`, `aud-spk-bus`, `aud-fm-bus`, `aud-loopback-bus`, `aud_dmic_on/off` hint that an external codec / speaker amp / DMIC exist on the board (a read, not stated), but no codec node. |
| NFC | **None** | No node, no string. |
| Wi-Fi / Bluetooth | Yes, SoC-linked | `/scsc_wifibt@120c0000` (`samsung,scsc_wifibt`): Samsung SCSC combo, reached over an SoC mailbox (MBOX / ALIVE / WDOG interrupts), with 4 MiB reserved at 0xe9000000 (`exynos,wifibt_if`) and `exynos,btabox_rmem` for BT audio. Likely Samsung SLSI's in-house combo chip (general knowledge); exact chip not named. |
| eMMC / UFS / SD | eMMC-style, controllers only | No UFS anywhere (0 hits for "ufs"). Three DesignWare MMC hosts, all `disabled` in this file: `dwmmc0@13500000` (has a `cmdq_mem` region; pin groups `sd0-bus-width8` + `sd0-rdqs`, so 8-bit with data strobe, likely eMMC), `dwmmc1@13510000` (4-bit, role unclear), `dwmmc2@13550000` (4-bit, likely the SD card slot). Also `samsung,mmc-srpmb` (secure RPMB over MMC) and `samsung,exynos-fmp` (`host-type = mmc`, `block-type = mmcblk0p`). The flash chip itself is not named. |
| USB / Type-C | SoC USB only | `/usb@13600000` (`samsung,exynos-dwusb`) + `/usb@13600000/dwc3` (`synopsys,dwc3`) + `/phy@135D0000` (`samsung,exynos-usbdrd-phy`, `has_combo_phy = 1`, USB 2.0/3.0 PHY), controller `status = disabled`. No Type-C controller, muic or tcpc node. Bootarg `ccic_info=0x1` is a flag handed to the kernel; Samsung uses "CCIC" for its Type-C controller chip (general knowledge), but what the flag means here, and which port type the phone has, isn't verified. |
| Display panel | **Not named** | SoC side only: `/dsim@0x14870000` (MIPI DSI host), `/decon_f@0x14860000` (display controller), 4x `/dpp@...` planes, `phy_m4s4_dsi`. The `dsim` node has no child, so no panel node. |

Other hardware seen: GPU `arm,mali` at `/mali@11500000` (model not stated; Mali-G71 MP2 for the Exynos 7885 is general knowledge, not in the file); video codec `samsung,mfc-v6`; JPEG codec, 2D blitter and scaler; FM radio block `samsung,exynos7885-fm` (with an external LNA gpio, `fm-lna-en`); cellular modem and GNSS reserved RAM (`exynos,modem_if` 0xf5400000, 136 MiB; `exynos,gnss_if` 0xffc00000, 4 MiB); two SIM-detect lines (`samsung,exynos-usim-detect`, `sim0_det_gpio`, `sim1_det_gpio`); secure world (`samsung,teegris`, `samsung,exynos-tee`, `/reserved-memory/tima_region`).

## Bootargs (`/chosen/bootargs`, verbatim, treat as data)

```
console=ram skip_initramfs rootwait ro init=/init clk_ignore_unused bcm_setup=0xffffff80f8e00000 androidboot.hardware=samsungexynos7885 androidboot.selinux=permissive ess_setup=0x86000000 ecd_setup=disable androidboot.debug_level=0x4948 firmware_class.path=/vendor/firmware reserve-fimc=0xffffff80fa000000 pmic_info=0x3 androidboot.cp_reserved_mem=ON ccic_info=0x1 epx_activate=true
```

These are the strings as shipped in the file. Samsung's bootloader normally edits bootargs before the kernel sees them (unverified guess), so do not read `androidboot.selinux=permissive` as the running device's state. (The main teardown confirms the live device runs Enforcing.)

## Sweep note

The keyword sweep (raw bytes of the whole 8 MB file, case-insensitive) hit only: `sm-` (the signer footer), `touch` x3 (input-booster key names), `codec` x12 (the `aud-codec-*` pin groups), `ccic` x1 and `pmic` x1 (both in bootargs), `wifi` x6 (the `wifibt` nodes). Everything else on the sweep list had zero hits. The sweep proves absence from this file only, not from the phone.

## Suggested follow-ups (not done here)

- Parse `out/extracted/dtbo.img` with the same reader to look for the board overlay nodes (PMIC, charger, touch, sensors, panel, camera sensors).
- Cross-check against `kernel_config.txt` in the same folder (enabled drivers) once the DT overlay is read.

## Full table: every node with a `compatible` (170)

`status` is the node's own `status` property as shipped (`-` means none). "SoC" means a block inside the Exynos chip. "likely" and "general knowledge" mark interpretation.

| # | node path | compatible | status | what it is |
|---|---|---|---|---|
| 1 | `/` | `samsung,armv8, samsung,exynos7885` | - | Root board + SoC: Samsung Exynos 7885 family SoC (retail part number not in file) |
| 2 | `/reserved-memory/framebuffer@0xEC000000` | `exynos,dpu_fb_handover` | - | Reserved RAM for bootloader-to-kernel framebuffer handover (boot splash), likely |
| 3 | `/reserved-memory/modem_if` | `exynos,modem_if` | - | Reserved RAM for the cellular modem (CP) interface |
| 4 | `/reserved-memory/cp_ram_logging` | `exynos,cp_ram_logging` | - | Reserved RAM for modem (CP) crash/RAM logging, likely |
| 5 | `/reserved-memory/gnss_if` | `exynos,gnss_if` | - | Reserved RAM for the GNSS (GPS) interface, likely |
| 6 | `/reserved-memory/tima_region@0xB8000000` | `removed-dma-pool` | - | Generic reserved DMA pool; name is "tima", so likely Samsung TIMA/Knox kernel-integrity region |
| 7 | `/reserved-memory/sec_debug_magic` | `exynos,sec_debug_magic` | - | Samsung debug-magic reserved region (software) |
| 8 | `/reserved-memory/seclog_mem` | `exynos,seclog` | - | Reserved RAM for secure-world log (software) |
| 9 | `/reserved-memory/wifibt_if` | `exynos,wifibt_if` | - | Reserved RAM shared with the Wi-Fi/Bluetooth firmware |
| 10 | `/reserved-memory/abox_rmem@0xE9400000` | `exynos,abox_rmem` | - | Reserved RAM for the ABOX audio DSP |
| 11 | `/reserved-memory/btabox_rmem` | `exynos,btabox_rmem` | - | Reserved RAM for Bluetooth audio through ABOX, likely |
| 12 | `/reserved-memory/crypto` | `exynos8890-ion,crypto` | - | ION reserved heap for crypto (software), likely |
| 13 | `/reserved-memory/video_stream` | `exynos8890-ion,vstream` | - | ION reserved heap for protected video stream, likely |
| 14 | `/pinctrl@11CB0000` | `samsung,exynos7885-pinctrl` | - | SoC GPIO / pin-mux controller bank |
| 15 | `/pinctrl@11CB0000/wakeup-interrupt-controller` | `samsung,exynos7-wakeup-eint` | - | SoC external wake-up interrupt controller |
| 16 | `/pinctrl@148F0000` | `samsung,exynos7885-pinctrl` | - | SoC GPIO / pin-mux controller bank |
| 17 | `/pinctrl@13430000` | `samsung,exynos7885-pinctrl` | - | SoC GPIO / pin-mux controller bank |
| 18 | `/pinctrl@139B0000` | `samsung,exynos7885-pinctrl` | - | SoC GPIO / pin-mux controller bank |
| 19 | `/pd-dispaud@11c84020` | `samsung,exynos-pd` | okay | SoC power domain |
| 20 | `/pd-mfcmscl@11c84040` | `samsung,exynos-pd` | okay | SoC power domain |
| 21 | `/pd-isp@11c84060` | `samsung,exynos-pd` | okay | SoC power domain |
| 22 | `/pd-cam@11c84080` | `samsung,exynos-pd` | okay | SoC power domain |
| 23 | `/pd-g3d@11c840a0` | `samsung,exynos-pd` | okay | SoC power domain |
| 24 | `/dbgdev-pd-dispaud` | `samsung,exynos-pd-dbg` | - | Debug stub for a SoC power domain (software) |
| 25 | `/dbgdev-pd-mfcmscl` | `samsung,exynos-pd-dbg` | - | Debug stub for a SoC power domain (software) |
| 26 | `/dbgdev-pd-isp` | `samsung,exynos-pd-dbg` | - | Debug stub for a SoC power domain (software) |
| 27 | `/dbgdev-pd-cam` | `samsung,exynos-pd-dbg` | - | Debug stub for a SoC power domain (software) |
| 28 | `/dbgdev-pd-g3d` | `samsung,exynos-pd-dbg` | - | Debug stub for a SoC power domain (software) |
| 29 | `/exynos-snapshot` | `samsung,exynos-snapshot` | - | Samsung debug snapshot (software) |
| 30 | `/fimc_is@14450000` | `samsung,exynos5-fimc-is` | ok | SoC camera ISP pipeline (FIMC-IS: ISP, MCSC scaler, VRA, GDC). This is the SoC side, not an image sensor |
| 31 | `/phy_isp_csis0@14510840` | `samsung,mipi-phy-s4` | - | SoC MIPI D-PHY for a camera (CSI-2) input |
| 32 | `/phy_isp_csis1@14510840` | `samsung,mipi-phy-s4` | - | SoC MIPI D-PHY for a camera (CSI-2) input |
| 33 | `/phy_isp_csis2@14510840` | `samsung,mipi-phy-s4` | - | SoC MIPI D-PHY for a camera (CSI-2) input |
| 34 | `/phy_isp_csis3@14510840` | `samsung,mipi-phy-csis` | - | SoC MIPI PHY for camera (CSI-2) input |
| 35 | `/fimc_is_sensor@14410000` | `samsung,exynos5-fimc-is-sensor` | - | SoC camera-sensor interface slot (one of 4). The sensor chip behind it is NOT named in this file |
| 36 | `/fimc_is_sensor@14400000` | `samsung,exynos5-fimc-is-sensor` | - | SoC camera-sensor interface slot (one of 4). The sensor chip behind it is NOT named in this file |
| 37 | `/fimc_is_sensor@14420000` | `samsung,exynos5-fimc-is-sensor` | - | SoC camera-sensor interface slot (one of 4). The sensor chip behind it is NOT named in this file |
| 38 | `/fimc_is_sensor@14430000` | `samsung,exynos5-fimc-is-sensor` | - | SoC camera-sensor interface slot (one of 4). The sensor chip behind it is NOT named in this file |
| 39 | `/gdc@0x14630000` | `samsung,exynos5-camerapp-gdc` | - | SoC camera post-processing: geometric distortion correction |
| 40 | `/input_booster` | `input_booster` | okay | Samsung input-event CPU/memory boost helper (software, not a chip) |
| 41 | `/mali@11500000` | `arm,mali` | - | ARM Mali GPU (model not in file) |
| 42 | `/arm-pmu` | `arm,armv8-pmuv3` | - | ARMv8 CPU performance-monitor unit |
| 43 | `/chipid@10000000` | `samsung,exynos7885-chipid` | - | SoC chip-ID register block |
| 44 | `/reboot` | `exynos,reboot` | - | SoC reboot / reset helper |
| 45 | `/cpus/cpu@100` | `arm,cortex-a53, arm,armv8` | - | CPU core: ARM Cortex-A53 (efficiency) |
| 46 | `/cpus/cpu@101` | `arm,cortex-a53, arm,armv8` | - | CPU core: ARM Cortex-A53 (efficiency) |
| 47 | `/cpus/cpu@102` | `arm,cortex-a53, arm,armv8` | - | CPU core: ARM Cortex-A53 (efficiency) |
| 48 | `/cpus/cpu@103` | `arm,cortex-a53, arm,armv8` | - | CPU core: ARM Cortex-A53 (efficiency) |
| 49 | `/cpus/cpu@200` | `arm,cortex-a53, arm,armv8` | - | CPU core: ARM Cortex-A53 (efficiency) |
| 50 | `/cpus/cpu@201` | `arm,cortex-a53, arm,armv8` | - | CPU core: ARM Cortex-A53 (efficiency) |
| 51 | `/cpus/cpu@0` | `arm,cortex-a73, arm,armv8` | - | CPU core: ARM Cortex-A73 (performance) |
| 52 | `/cpus/cpu@1` | `arm,cortex-a73, arm,armv8` | - | CPU core: ARM Cortex-A73 (performance) |
| 53 | `/cpus/idle-states/bootcl-cpu-sleep` | `exynos,idle-state` | okay | CPU idle (sleep) state definition |
| 54 | `/cpus/idle-states/nobootcl-cpu-sleep` | `exynos,idle-state` | okay | CPU idle (sleep) state definition |
| 55 | `/psci` | `arm,psci` | - | ARM PSCI power-state firmware interface |
| 56 | `/interrupt-controller@123001000` | `arm,cortex-a15-gic, arm,cortex-a9-gic` | - | ARM GIC interrupt controller |
| 57 | `/timer` | `arm,armv8-timer` | - | ARMv8 generic timer |
| 58 | `/clock-controller@0x12060000` | `samsung,exynos7885-clock` | - | SoC clock controller (CMU) |
| 59 | `/devfreq_mif@17000010` | `samsung,exynos-devfreq` | - | SoC bus/block frequency scaling (devfreq) domain |
| 60 | `/devfreq_int@17000020` | `samsung,exynos-devfreq` | - | SoC bus/block frequency scaling (devfreq) domain |
| 61 | `/devfreq_disp@17000040` | `samsung,exynos-devfreq` | - | SoC bus/block frequency scaling (devfreq) domain |
| 62 | `/devfreq_cam@17000050` | `samsung,exynos-devfreq` | - | SoC bus/block frequency scaling (devfreq) domain |
| 63 | `/devfreq_aud@17000060` | `samsung,exynos-devfreq` | - | SoC bus/block frequency scaling (devfreq) domain |
| 64 | `/devfreq_fsys@17000070` | `samsung,exynos-devfreq` | - | SoC bus/block frequency scaling (devfreq) domain |
| 65 | `/mct@10040000` | `samsung,exynos4210-mct` | - | SoC multi-core timer |
| 66 | `/ITMON@0` | `samsung,exynos-itmon` | - | SoC interconnect error monitor |
| 67 | `/usi@10032000` | `samsung,exynos-usi` | disabled | SoC USI (selects whether a port acts as UART / I2C / SPI) |
| 68 | `/usi@10032004` | `samsung,exynos-usi` | disabled | SoC USI (selects whether a port acts as UART / I2C / SPI) |
| 69 | `/usi@10032008` | `samsung,exynos-usi` | disabled | SoC USI (selects whether a port acts as UART / I2C / SPI) |
| 70 | `/speedy@11CE0000` | `samsung,exynos-speedy` | disabled | SoC SPEEDY serial-bus controller. Likely the Samsung proprietary bus used to reach a Samsung PMIC (general knowledge, not stated in file); disabled here |
| 71 | `/uart@13800000` | `samsung,exynos-uart` | disabled | SoC UART |
| 72 | `/uart@13810000` | `samsung,exynos-uart` | disabled | SoC UART |
| 73 | `/uart@13820000` | `samsung,exynos-uart` | disabled | SoC UART |
| 74 | `/uart@13920000` | `samsung,exynos-uart` | disabled | SoC UART |
| 75 | `/uart@13940000` | `samsung,exynos-uart` | disabled | SoC UART |
| 76 | `/uart@13980000` | `samsung,exynos-uart` | disabled | SoC UART |
| 77 | `/fmp` | `samsung,exynos-fmp` | - | SoC Flash Memory Protector (storage encryption engine); host-type is mmc |
| 78 | `/smu` | `samsung,exynos-smu` | - | SoC storage security unit, likely |
| 79 | `/dwmmc0@13500000` | `samsung,exynos-dw-mshc` | disabled | SoC DesignWare MMC/SD/SDIO host controller |
| 80 | `/dwmmc1@13510000` | `samsung,exynos-dw-mshc` | disabled | SoC DesignWare MMC/SD/SDIO host controller |
| 81 | `/dwmmc2@13550000` | `samsung,exynos-dw-mshc` | disabled | SoC DesignWare MMC/SD/SDIO host controller |
| 82 | `/hsi2c@138A0000` | `samsung,exynos5-hsi2c` | disabled | SoC high-speed I2C controller (no child devices described) |
| 83 | `/hsi2c@138B0000` | `samsung,exynos5-hsi2c` | disabled | SoC high-speed I2C controller (no child devices described) |
| 84 | `/hsi2c@138C0000` | `samsung,exynos5-hsi2c` | disabled | SoC high-speed I2C controller (no child devices described) |
| 85 | `/hsi2c@138D0000` | `samsung,exynos5-hsi2c` | disabled | SoC high-speed I2C controller (no child devices described) |
| 86 | `/hsi2c@13920000` | `samsung,exynos5-hsi2c` | disabled | SoC high-speed I2C controller (no child devices described) |
| 87 | `/hsi2c@13930000` | `samsung,exynos5-hsi2c` | disabled | SoC high-speed I2C controller (no child devices described) |
| 88 | `/hsi2c@13940000` | `samsung,exynos5-hsi2c` | disabled | SoC high-speed I2C controller (no child devices described) |
| 89 | `/hsi2c@13950000` | `samsung,exynos5-hsi2c` | disabled | SoC high-speed I2C controller (no child devices described) |
| 90 | `/hsi2c@13980000` | `samsung,exynos5-hsi2c` | disabled | SoC high-speed I2C controller (no child devices described) |
| 91 | `/hsi2c@13990000` | `samsung,exynos5-hsi2c` | disabled | SoC high-speed I2C controller (no child devices described) |
| 92 | `/i2c@13830000` | `samsung,s3c2440-i2c` | disabled | SoC standard I2C controller (no child devices described) |
| 93 | `/i2c@13840000` | `samsung,s3c2440-i2c` | disabled | SoC standard I2C controller (no child devices described) |
| 94 | `/i2c@13850000` | `samsung,s3c2440-i2c` | disabled | SoC standard I2C controller (no child devices described) |
| 95 | `/i2c@13860000` | `samsung,s3c2440-i2c` | disabled | SoC standard I2C controller (no child devices described) |
| 96 | `/i2c@13870000` | `samsung,s3c2440-i2c` | disabled | SoC standard I2C controller (no child devices described) |
| 97 | `/i2c@13880000` | `samsung,s3c2440-i2c` | disabled | SoC standard I2C controller (no child devices described) |
| 98 | `/i2c@13890000` | `samsung,s3c2440-i2c` | disabled | SoC standard I2C controller (no child devices described) |
| 99 | `/i2c@11CD0000` | `samsung,s3c2440-i2c` | disabled | SoC standard I2C controller (no child devices described) |
| 100 | `/spi@13900000` | `samsung,exynos-spi` | disabled | SoC SPI controller (no child devices described) |
| 101 | `/spi@13910000` | `samsung,exynos-spi` | disabled | SoC SPI controller (no child devices described) |
| 102 | `/spi@13920000` | `samsung,exynos-spi` | disabled | SoC SPI controller (no child devices described) |
| 103 | `/spi@13940000` | `samsung,exynos-spi` | disabled | SoC SPI controller (no child devices described) |
| 104 | `/spi@13980000` | `samsung,exynos-spi` | disabled | SoC SPI controller (no child devices described) |
| 105 | `/iommu-domain_disp` | `samsung,exynos-iommu-bus` | - | SoC IOMMU domain grouping |
| 106 | `/dpp@0x148B1000` | `samsung,exynos7885-dpp` | - | SoC display post-processor plane (DPU DPP) |
| 107 | `/dpp@0x148B2000` | `samsung,exynos7885-dpp` | - | SoC display post-processor plane (DPU DPP) |
| 108 | `/dpp@0x148B3000` | `samsung,exynos7885-dpp` | - | SoC display post-processor plane (DPU DPP) |
| 109 | `/dpp@0x148B4000` | `samsung,exynos7885-dpp` | - | SoC display post-processor plane (DPU DPP) |
| 110 | `/disp_ss@0x14820000` | `samsung,exynos7885-disp_ss` | - | SoC display subsystem sysreg block |
| 111 | `/system-controller@11c80000` | `samsung,exynos7885-pmu, syscon` | - | SoC power-management-unit REGISTER BLOCK (not a PMIC chip) |
| 112 | `/exynos-pmu` | `samsung,exynos-pmu` | - | SoC PMU driver node (not a PMIC chip) |
| 113 | `/phy_m4s4_dsi@0x11c80000` | `samsung,mipi-phy-dsim` | - | SoC MIPI D-PHY for the display (DSI) output |
| 114 | `/dsim@0x14870000` | `samsung,exynos7885-dsim` | - | SoC MIPI DSI host (display link). No panel child node in this file |
| 115 | `/decon_f@0x14860000` | `samsung,exynos7885-decon` | - | SoC display controller (DECON). Panel not described |
| 116 | `/sysmmu@148C0000` | `samsung,exynos-sysmmu` | - | SoC system MMU (IOMMU) for a block |
| 117 | `/iommu-domain_aud` | `samsung,exynos-iommu-bus` | - | SoC IOMMU domain grouping |
| 118 | `/sysmmu_abox@14A30000` | `samsung,exynos-sysmmu` | - | SoC system MMU (IOMMU) for a block |
| 119 | `/abox_gic@0x14AF0000` | `samsung,abox_gic` | - | ABOX audio-DSP interrupt controller |
| 120 | `/abox@0x14A50000` | `samsung,abox` | - | SoC ABOX audio subsystem (audio DSP + I2S/DMA). No external codec node |
| 121 | `/abox@0x14A50000/abox_rdma@0x14A51000` | `samsung,abox-rdma` | - | ABOX audio read DMA (playback) channel |
| 122 | `/abox@0x14A50000/abox_rdma@0x14A51100` | `samsung,abox-rdma` | - | ABOX audio read DMA (playback) channel |
| 123 | `/abox@0x14A50000/abox_rdma@0x14A51200` | `samsung,abox-rdma` | - | ABOX audio read DMA (playback) channel |
| 124 | `/abox@0x14A50000/abox_rdma@0x14A51300` | `samsung,abox-rdma` | - | ABOX audio read DMA (playback) channel |
| 125 | `/abox@0x14A50000/abox_rdma@0x14A51400` | `samsung,abox-rdma` | - | ABOX audio read DMA (playback) channel |
| 126 | `/abox@0x14A50000/abox_rdma@0x14A51500` | `samsung,abox-rdma` | - | ABOX audio read DMA (playback) channel |
| 127 | `/abox@0x14A50000/abox_rdma@0x14A51600` | `samsung,abox-rdma` | - | ABOX audio read DMA (playback) channel |
| 128 | `/abox@0x14A50000/abox_rdma@0x14A51700` | `samsung,abox-rdma` | - | ABOX audio read DMA (playback) channel |
| 129 | `/abox@0x14A50000/abox_wdma@0x14A52000` | `samsung,abox-wdma` | - | ABOX audio write DMA (capture) channel |
| 130 | `/abox@0x14A50000/abox_wdma@0x14A52100` | `samsung,abox-wdma` | - | ABOX audio write DMA (capture) channel |
| 131 | `/abox@0x14A50000/abox_wdma@0x14A52200` | `samsung,abox-wdma` | - | ABOX audio write DMA (capture) channel |
| 132 | `/abox@0x14A50000/abox_wdma@0x14A52300` | `samsung,abox-wdma` | - | ABOX audio write DMA (capture) channel |
| 133 | `/abox@0x14A50000/abox_wdma@0x14A52400` | `samsung,abox-wdma` | - | ABOX audio write DMA (capture) channel |
| 134 | `/abox@0x14A50000/abox_debug@0` | `samsung,abox-debug` | - | ABOX debug (software) |
| 135 | `/abox@0x14A50000/abox_vss@0` | `samsung,abox-vss` | - | ABOX virtual sub-system (software) |
| 136 | `/iommu-domain_is` | `samsung,exynos-iommu-bus` | - | SoC IOMMU domain grouping |
| 137 | `/sysmmu@14540000` | `samsung,exynos-sysmmu` | - | SoC system MMU (IOMMU) for a block |
| 138 | `/sysmmu@14730000` | `samsung,exynos-sysmmu` | - | SoC system MMU (IOMMU) for a block |
| 139 | `/sysmmu@14760000` | `samsung,exynos-sysmmu` | - | SoC system MMU (IOMMU) for a block |
| 140 | `/iommu-domain_mfcmscl` | `samsung,exynos-iommu-bus` | - | SoC IOMMU domain grouping |
| 141 | `/sysmmu@12C50000` | `samsung,exynos-sysmmu` | - | SoC system MMU (IOMMU) for a block |
| 142 | `/smfc@12C00000` | `samsung,exynos8890-jpeg` | - | SoC hardware JPEG codec |
| 143 | `/scaler@12C10000` | `samsung,exynos5-scaler` | - | SoC image scaler |
| 144 | `/fimg2d@12C20000` | `samsung,s5p-fimg2d` | - | SoC 2D blitter |
| 145 | `/scsc_wifibt@120c0000` | `samsung,scsc_wifibt` | - | Samsung SCSC combo Wi-Fi/Bluetooth, reached over an SoC mailbox. Likely Samsung SLSI in-house combo chip (general knowledge). Exact chip not named |
| 146 | `/acpm` | `samsung,exynos-acpm` | - | SoC ACPM (Alive Clock and Power Manager) firmware co-processor, likely the part that drives the PMIC for the CPU (general knowledge) |
| 147 | `/mfc0@12C30000` | `samsung,mfc-v6` | ok | SoC multi-format video codec (MFC) |
| 148 | `/acpm_ipc` | `samsung,exynos-acpm-ipc` | - | ACPM mailbox / IPC channel |
| 149 | `/acpm_dvfs` | `samsung,exynos-acpm-dvfs` | - | ACPM frequency/voltage scaling |
| 150 | `/pwm@13970000` | `samsung,s3c6400-pwm` | ok | SoC PWM timer |
| 151 | `/pwm-clock-controller@13970000` | `samsung,exynos-pwm-clock` | - | SoC PWM clock helper |
| 152 | `/watchdog@10060000` | `samsung,exynos8-wdt` | - | SoC watchdog timer |
| 153 | `/usb@13600000` | `samsung,exynos-dwusb` | disabled | SoC USB controller wrapper (Samsung glue around Synopsys DWC3) |
| 154 | `/usb@13600000/dwc3` | `synopsys,dwc3` | - | Synopsys DWC3 USB dual-role controller (on the SoC) |
| 155 | `/phy@135D0000` | `samsung,exynos-usbdrd-phy` | disabled | SoC USB 2.0 / 3.0 combo PHY (property has_combo_phy=1) |
| 156 | `/adc@120A0000` | `samsung,exynos-adc-v3` | - | SoC general-purpose ADC (what is wired to it is not in the file) |
| 157 | `/rtc@11C90000` | `samsung,exynos8-rtc` | - | SoC real-time clock |
| 158 | `/usim_det` | `samsung,exynos-usim-detect` | - | SIM-card detect logic (SIM0 and SIM1 detect lines) |
| 159 | `/exynos-pm` | `samsung,exynos-pm` | - | SoC power-management driver node (software) |
| 160 | `/amba` | `arm,amba-bus` | - | ARM AMBA bus container |
| 161 | `/amba/pdma0@12020000` | `arm,pl330, arm,primecell` | - | ARM PL330 DMA controller |
| 162 | `/seclog` | `samsung,exynos-seclog` | - | Secure-world log driver (software) |
| 163 | `/tee` | `samsung,exynos-tee` | - | TEE interface driver node (software) |
| 164 | `/teegris` | `samsung,teegris` | - | Samsung TEEGRIS secure-OS interface (software) |
| 165 | `/mmc-srpmb` | `samsung,mmc-srpmb` | - | Secure RPMB access through the MMC controller, so eMMC-style storage, likely |
| 166 | `/fm@14840000` | `samsung,exynos7885-fm` | okay | SoC FM radio receiver block (external LNA gpio) |
| 167 | `/exynos-dm@17000000` | `samsung,exynos-dvfs-manager` | - | SoC DVFS manager (software) |
| 168 | `/BIG@10070000` | `samsung,exynos7885-tmu` | - | SoC thermal management unit (temperature sensor for a cluster) |
| 169 | `/LITTLE@10070000` | `samsung,exynos7885-tmu` | - | SoC thermal management unit (temperature sensor for a cluster) |
| 170 | `/G3D@10074000` | `samsung,exynos7885-tmu` | - | SoC thermal management unit (temperature sensor for a cluster) |
