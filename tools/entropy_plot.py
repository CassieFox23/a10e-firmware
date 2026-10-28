#!/usr/bin/env python3
# Clean entropy plots for the A10e firmware write-up.
# Static read-only: computes windowed Shannon entropy of firmware bytes and plots it.
import sys, os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
from matplotlib.patches import Patch
from matplotlib.lines import Line2D

BG="#020617"; FG="#e2e8f0"; MUTED="#94a3b8"; GRID="#1e293b"
LINE="#cba6f7"; FILL="#cba6f7"; ENC="#f38ba8"; EDGE="#f9e2af"; KEY="#89dceb"

plt.rcParams.update({
    "figure.facecolor":BG, "axes.facecolor":BG, "savefig.facecolor":BG,
    "text.color":FG, "axes.labelcolor":FG, "xtick.color":MUTED, "ytick.color":MUTED,
    "axes.edgecolor":GRID, "grid.color":GRID, "font.size":11, "font.family":"DejaVu Sans",
})

def wentropy(data, win, step):
    arr=np.frombuffer(data, dtype=np.uint8); n=len(arr)
    xs=np.arange(0, max(1, n-win+1), step); ys=np.empty(len(xs))
    for i,s in enumerate(xs):
        w=arr[s:s+win]; c=np.bincount(w, minlength=256).astype(np.float64)
        p=c[c>0]/w.size; ys[i]=-(p*np.log2(p)).sum()
    return xs, ys

def block_entropy(data, a, b):
    seg=np.frombuffer(data, dtype=np.uint8)[a:b]
    c=np.bincount(seg, minlength=256).astype(np.float64); p=c[c>0]/seg.size
    return -(p*np.log2(p)).sum()

def chi2(data, a, b):
    seg=np.frombuffer(data, dtype=np.uint8)[a:b]
    c=np.bincount(seg, minlength=256).astype(np.float64); e=seg.size/256
    return float(((c-e)**2/e).sum())

def load(p):
    with open(p,"rb") as f: return f.read()

def hexfmt(x,_):
    x=int(x); return f"0x{x:X}" if x else "0"

def style_ax(ax, size):
    ax.set_ylim(0,8.3); ax.set_xlim(0,size); ax.set_yticks([0,2,4,6,8])
    ax.grid(True, lw=0.5, alpha=0.5)
    ax.xaxis.set_major_formatter(FuncFormatter(hexfmt)); ax.tick_params(labelsize=9)
    step=0x80000 if size>=0x200000 else max(0x1000, 1<<(size//8).bit_length()-1)
    ax.set_xticks(np.arange(0, size+1, step))
    for s in ax.spines.values(): s.set_linewidth(0.8)

def plot_line(ax, xs, ys):
    ax.fill_between(xs, 0, ys, color=FILL, alpha=0.18, linewidth=0)
    ax.plot(xs, ys, color=LINE, lw=0.8)
    ax.axhline(8.0, color=MUTED, lw=0.6, ls=":", alpha=0.6)

ENTROPY_DIR=sys.argv[1]; OUT_DIR=sys.argv[2]
P=lambda n: os.path.join(ENTROPY_DIR, n)

# ---------- Figure 1: sboot.bin, annotated with a legend ----------
sb=load(P("sboot.bin")); size=len(sb)
xs,ys=wentropy(sb, 1024, 256)
a,b=0x32e0,0x1b420
Hblock=block_entropy(sb, a, b)
ta,tb=0x12c800,0x143000
Htab=block_entropy(sb, ta, tb); Xtab=chi2(sb, ta, tb); Xblob=chi2(sb, a, b)
fig,ax=plt.subplots(figsize=(12,5.4), dpi=170)
plot_line(ax, xs, ys)
ax.axvspan(a,b, color=ENC, alpha=0.16, lw=0)
ax.axvspan(ta,tb, color=EDGE, alpha=0.14, lw=0)
ax.axvline(0x1b400, color=EDGE, lw=1.1, ls="--")
for kx in (0x12b070, 0x322410): ax.axvline(kx, color=KEY, lw=1.0, ls=":")
style_ax(ax, size)
ax.set_title("sboot.bin — bootloader entropy  (build A102USQSDAVD1, image checksum 0xfdcdbc1d)",
             color=FG, fontsize=12.5, pad=22, loc="left")
ax.annotate("Shannon entropy over the 4 MB image · high = encrypted, compressed or dense tables · mid ≈ ARM64 code · low = headers/padding",
            xy=(0,1.02), xycoords="axes fraction", color=MUTED, fontsize=9.5)
ax.set_xlabel("file offset"); ax.set_ylabel("entropy (bits/byte)")
handles=[
    Patch(facecolor=ENC, alpha=0.55, edgecolor="none",
          label=f"encrypted [SECLIB] pre-boot blob · 0x32E0–0x1B420 · H ≈ {Hblock:.3f}/8, χ² {Xblob:,.0f} (random ≈ 255)"),
    Patch(facecolor=EDGE, alpha=0.45, edgecolor="none",
          label=f"90 KiB data table, not encrypted · 0x12C800–0x143000 · H ≈ {Htab:.2f}/8 but χ² {Xtab:,.0f}"),
    Line2D([0],[0], color=EDGE, lw=1.4, ls="--", label="hard entropy edge · 0x1B400"),
    Line2D([0],[0], color=KEY, lw=1.4, ls=":",  label="embedded AVB RSA-4096 key ×2 (1 KB each, thin lines) · 0x12B070, 0x322410"),
]
ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5,-0.17), ncol=2, fontsize=9, framealpha=0.9,
          facecolor="#0b1225", edgecolor=GRID, labelcolor=FG)
fig.tight_layout()
f1=os.path.join(OUT_DIR,"entropy-sboot.png"); fig.savefig(f1); plt.close(fig)
print("sboot whole-blob H =", round(float(Hblock),4), "chi2", round(Xblob), "| table H =", round(float(Htab),3), "chi2", round(Xtab), "->", f1)

# ---------- Figure 2: clean overview ----------
panels=[("sboot.bin","bootloader"),("cm.bin","Crypto Manager"),
        ("vbmeta.img","verified-boot table"),("param.bin","boot screens"),
        ("modem.bin","Shannon baseband"),("modem_debug.bin","modem debug")]
if not all(os.path.exists(P(fn)) for fn,_ in panels):
    print("overview skipped: needs all six images in", ENTROPY_DIR); sys.exit(0)
fig,axes=plt.subplots(3,2, figsize=(13,9.5), dpi=150)
fig.suptitle("Galaxy A10e firmware — entropy map of each partition",
             color=FG, fontsize=15, y=0.985)
for ax,(fn,desc) in zip(axes.flat, panels):
    data=load(P(fn)); n=len(data)
    step=max(256, n//2200); win=min(4096, max(512, step*2))
    xs,ys=wentropy(data, win, step)
    plot_line(ax, xs, ys); style_ax(ax, n)
    ax.set_title(f"{fn}  —  {desc}  ({n:,} bytes)", color=FG, fontsize=10.5, loc="left", pad=6)
    ax.tick_params(labelsize=7.5)
axes[2,0].set_xlabel("file offset"); axes[2,1].set_xlabel("file offset")
for r in range(3): axes[r,0].set_ylabel("entropy")
fig.text(0.5, 0.012, "Shannon entropy, 0–8 bits/byte (windowed) · high = encrypted/compressed, low = structured/padding",
         ha="center", color=MUTED, fontsize=9)
fig.tight_layout(rect=[0,0.02,1,0.97])
f2=os.path.join(OUT_DIR,"entropy-overview.png"); fig.savefig(f2); plt.close(fig)
print("overview ->", f2)
