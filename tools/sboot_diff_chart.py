#!/usr/bin/env python3
# Bar chart: how much sboot.bin changed between builds while the AVB root key stayed the same.
# No firmware needed: the numbers are hardcoded from A10e-teardown.md, section
# "Does it hold up? Cross-checks" (items 1, 2 and 4). Colours and style follow tools/entropy_plot.py.
# Usage: sboot_diff_chart.py [output.png]   (default: ../figures/sboot-diff-chart.png)
import os, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import PathPatch
from matplotlib.path import Path
from matplotlib.transforms import blended_transform_factory

BG="#020617"; FG="#e2e8f0"; MUTED="#94a3b8"; GRID="#1e293b"
BAR="#cba6f7"; KEY="#89dceb"

plt.rcParams.update({
    "figure.facecolor":BG, "axes.facecolor":BG, "savefig.facecolor":BG,
    "text.color":FG, "axes.labelcolor":MUTED, "xtick.color":MUTED, "ytick.color":MUTED,
    "axes.edgecolor":GRID, "grid.color":GRID, "font.size":11, "font.family":"DejaVu Sans",
})

# (pair, builds, percent differing, value label, detail under the value)
# Teardown, Cross-checks item 2: 30.55% of the bootloader rewritten.
# Item 4: about 16% differ (421 regions). Item 1: 2276 bytes, 0.05%.
ROWS = [
    ("Android 11 AT&T build vs the phone's build",
     "A102USQUGCWH1 (Aug 2023) vs A102USQSDAVD1 (Apr 2022)",
     30.55, "30.55%", "rewritten"),
    ("Unlocked SM-A102U1 vs carrier SM-A102U (AT&T)",
     "both Aug 2023 builds",
     16.0, "about 16%", "421 regions"),
    ("Previous build vs the phone's build",
     "A102USQUBAUJ1 (Oct 2021) vs A102USQSDAVD1 (Apr 2022)",
     0.05, "0.05%", "2,276 bytes"),
]

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "figures", "sboot-diff-chart.png")

DPI = 170
fig = plt.figure(figsize=(12, 4.9), dpi=DPI)
ax = fig.add_axes([0.40, 0.30, 0.575, 0.46])
XMAX = 36
ax.set_xlim(0, XMAX); ax.set_ylim(-0.6, 2.6)
ax.set_xticks([0, 10, 20, 30]); ax.set_xticklabels(["0%", "10%", "20%", "30%"])
ax.set_yticks([])
ax.grid(True, axis="x", lw=0.8, ls="-")
ax.set_axisbelow(True)
ax.tick_params(axis="x", labelsize=9.5, length=0, pad=6)
for s in ("top", "right"): ax.spines[s].set_visible(False)
for s in ("left", "bottom"): ax.spines[s].set_linewidth(0.8)
ax.set_xlabel("share of sboot.bin that differs between the two builds", fontsize=9.5, labelpad=8)

# data units per pixel, for a 4 px rounded data end (4 CSS px is about 7 px at this dpi)
(x0p, y0p), (x1p, y1p) = ax.transData.transform([(0, 0), (1, 1)])
ppx, ppy = x1p - x0p, y1p - y0p
R = 7.0
rx, ry = R / ppx, R / ppy
BAR_H = 0.34

def bar(y, w):
    lo, hi = y - BAR_H / 2, y + BAR_H / 2
    if w <= 2 * rx:  # a sliver: plain rectangle, never rounded or padded
        verts = [(0, lo), (w, lo), (w, hi), (0, hi), (0, lo)]
        codes = [Path.MOVETO, Path.LINETO, Path.LINETO, Path.LINETO, Path.CLOSEPOLY]
    else:
        verts = [(0, lo), (w - rx, lo), (w, lo), (w, lo + ry), (w, hi - ry), (w, hi),
                 (w - rx, hi), (0, hi), (0, lo)]
        codes = [Path.MOVETO, Path.LINETO, Path.CURVE3, Path.CURVE3, Path.LINETO,
                 Path.CURVE3, Path.CURVE3, Path.LINETO, Path.CLOSEPOLY]
    ax.add_patch(PathPatch(Path(verts, codes), facecolor=BAR, edgecolor="none", zorder=3))

lab = blended_transform_factory(fig.transFigure, ax.transData)
for i, (pair, builds, pct, val, detail) in enumerate(ROWS):
    y = 2 - i
    bar(y, pct)
    fig.text(0.025, y + 0.13, pair, transform=lab, ha="left", va="center",
             fontsize=11.5, color=FG)
    fig.text(0.025, y - 0.15, builds, transform=lab, ha="left", va="center",
             fontsize=9.5, color=MUTED)
    ax.text(pct + 0.7, y + 0.1, val, ha="left", va="center", fontsize=13,
            fontweight="bold", color=FG, zorder=4)
    ax.text(pct + 0.7, y - 0.17, detail, ha="left", va="center", fontsize=9.5,
            color=MUTED, zorder=4)

fig.text(0.025, 0.925, "How much the bootloader (sboot.bin) changed between builds",
         fontsize=15, color=FG, ha="left", va="center")
fig.text(0.025, 0.855, "Three different pairs of builds, not a series over time. Each bar is one pair.",
         fontsize=10.5, color=MUTED, ha="left", va="center")

# note: the AVB root key is the same across all three pairs
fig.add_artist(plt.Line2D([0.0285], [0.1245], marker="o", markersize=9, color=KEY,
                          markeredgecolor=BG, markeredgewidth=2, transform=fig.transFigure))
fig.text(0.045, 0.125, "The AVB root key is the same in all three pairs", fontsize=11.5,
         color=FG, ha="left", va="center")
fig.text(0.045, 0.07, "KG / AVB / rollback lock strings are unchanged too. "
         "Unlocked pair: the AVB keys and the OEM-unlock code match.",
         fontsize=9.5, color=MUTED, ha="left", va="center")
fig.text(0.975, 0.02, "Source: A10e-teardown.md, Does it hold up? Cross-checks",
         fontsize=8, color=MUTED, ha="right", va="center")

os.makedirs(os.path.dirname(os.path.abspath(OUT)), exist_ok=True)
fig.savefig(OUT)
print("->", os.path.abspath(OUT))
