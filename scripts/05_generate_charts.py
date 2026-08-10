"""
Results Visualisation — Chapter 5 Figures
Generates publication-quality charts from the CAD comparison results
for both Apophis and Bennu.

Dissertation: Integrity Assurance in Planetary Defense
Author: Nithin Yadav Gopinath (C5003001)
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import os

OUTPUT_DIR = "results/figures"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── Colour palette ─────────────────────────────────────────────────
C_CLEAN   = "#2E75B6"
C_BIAS    = "#E24B4A"
C_NOISE   = "#F5A623"
C_OUTLIER = "#1D9E75"
C_APOPHIS = "#2E75B6"
C_BENNU   = "#7C5CFC"
BG        = "#0F1520"
SURF      = "#13161E"
TEXT      = "#E8EAF0"
MUTED     = "#9CA3AF"
GRID      = "#1F2D45"

def style_dark(ax, fig):
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(SURF)
    ax.tick_params(colors=MUTED, labelsize=9)
    ax.xaxis.label.set_color(MUTED)
    ax.yaxis.label.set_color(MUTED)
    ax.title.set_color(TEXT)
    for spine in ax.spines.values():
        spine.set_color(GRID)
    ax.grid(axis='y', color=GRID, linewidth=0.5, linestyle='--', alpha=0.7)
    ax.set_axisbelow(True)


# ── Data ──────────────────────────────────────────────────────────
scenarios  = ["Systematic\nBias\n(2.0 arcsec)", "Stochastic\nNoise\n(1.5 arcsec)", "Targeted\nOutlier\n(30 arcsec,\n20 obs)"]
apophis_delta = [5088.0,  2570.1,  249.8]   # km, absolute values
bennu_delta   = [3334.6,  1679.7,  493.5]

apophis_pct = [(d/13866930)*100 for d in apophis_delta]
bennu_pct   = [(d/262350077)*100 for d in bennu_delta]


# ── Figure 1: Bar chart — CAD delta by scenario, both objects ──────
fig, ax = plt.subplots(figsize=(11, 6))
style_dark(ax, fig)

x     = np.arange(len(scenarios))
width = 0.35

bars_a = ax.bar(x - width/2, apophis_delta, width,
                color=C_APOPHIS, alpha=0.9, label='Apophis (99942)',
                edgecolor='none', zorder=3)
bars_b = ax.bar(x + width/2, bennu_delta, width,
                color=C_BENNU, alpha=0.9, label='Bennu (101955)',
                edgecolor='none', zorder=3)

# Value labels on bars
for bar in bars_a:
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 80,
            f'{bar.get_height():,.0f} km', ha='center', va='bottom',
            color=C_APOPHIS, fontsize=8.5, fontweight='bold')
for bar in bars_b:
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 80,
            f'{bar.get_height():,.0f} km', ha='center', va='bottom',
            color=C_BENNU, fontsize=8.5, fontweight='bold')

ax.set_xticks(x)
ax.set_xticklabels(scenarios, color=TEXT, fontsize=9)
ax.set_ylabel('Close Approach Distance Delta (km)', color=MUTED, fontsize=10)
ax.set_title('Figure 1: CAD Delta by Injection Archetype\n'
             'Apophis vs Bennu — Simulated Adversarial Manipulation',
             color=TEXT, fontsize=12, fontweight='bold', pad=15)
ax.legend(facecolor=SURF, edgecolor=GRID, labelcolor=TEXT, fontsize=9)
ax.set_ylim(0, max(apophis_delta) * 1.25)

fig.text(0.5, 0.01,
         'Source: GMAT R2026a simulation | MPC ADES data | Epoch: 2020-Jan-01 geocentric | '
         'Nithin Yadav Gopinath (C5003001)',
         ha='center', color=MUTED, fontsize=7.5)

plt.tight_layout(rect=[0, 0.04, 1, 1])
path1 = os.path.join(OUTPUT_DIR, "fig1_cad_delta_comparison.png")
plt.savefig(path1, dpi=180, bbox_inches='tight', facecolor=BG)
plt.close()
print(f"Saved: {path1}")


# ── Figure 2: Targeted outlier stealthiness — observation % vs delta ─
fig, ax = plt.subplots(figsize=(9, 5))
style_dark(ax, fig)

objects     = ['Apophis\n(9,337 obs)', 'Bennu\n(603 obs)']
pct_corrupt = [20/9337*100, 20/603*100]   # % of dataset corrupted
delta_km    = [249.8, 493.5]

scatter_colors = [C_APOPHIS, C_BENNU]
sizes = [400, 400]

for i, (obj, pct, delta, col) in enumerate(zip(objects, pct_corrupt, delta_km, scatter_colors)):
    ax.scatter(pct, delta, s=sizes[i], color=col, zorder=5, edgecolors='white', linewidth=0.8)
    ax.annotate(obj,
                xy=(pct, delta),
                xytext=(pct + 0.05, delta + 15),
                color=col, fontsize=9.5, fontweight='bold')

# Trend line
x_line = np.linspace(0, 4, 100)
y_line = 150 * x_line  # rough proportional relationship
ax.plot(x_line, y_line, color=MUTED, linestyle='--', linewidth=1, alpha=0.5,
        label='Proportional vulnerability (illustrative)')

ax.set_xlabel('Percentage of Dataset Corrupted (%)', color=MUTED, fontsize=10)
ax.set_ylabel('CAD Delta from Targeted Outlier Attack (km)', color=MUTED, fontsize=10)
ax.set_title('Figure 2: Observation Density as a Security Variable\n'
             'Sparse datasets are disproportionately vulnerable to targeted injection',
             color=TEXT, fontsize=12, fontweight='bold', pad=15)
ax.legend(facecolor=SURF, edgecolor=GRID, labelcolor=MUTED, fontsize=8)
ax.set_xlim(0, 4.5)
ax.set_ylim(0, 650)

fig.text(0.5, 0.01,
         'Finding: Bennu (0.21% → 603 obs) vs Apophis (0.21% → 9,337 obs) — '
         'sparser record = larger orbital perturbation per injected observation',
         ha='center', color=MUTED, fontsize=7.5)

plt.tight_layout(rect=[0, 0.04, 1, 1])
path2 = os.path.join(OUTPUT_DIR, "fig2_observation_density_vulnerability.png")
plt.savefig(path2, dpi=180, bbox_inches='tight', facecolor=BG)
plt.close()
print(f"Saved: {path2}")


# ── Figure 3: Injection magnitude vs orbital impact — both objects ──
fig, ax = plt.subplots(figsize=(10, 6))
style_dark(ax, fig)

# Mean injection in arcsec for each archetype
inj_magnitudes = [2.0, 1.2, 0.064]  # mean arcsec shift (systematic, stochastic, targeted mean)

ax.plot(inj_magnitudes, apophis_delta,
        'o-', color=C_APOPHIS, linewidth=2, markersize=9,
        label='Apophis (99942)', markeredgecolor='white', markeredgewidth=0.8, zorder=5)
ax.plot(inj_magnitudes, bennu_delta,
        's-', color=C_BENNU, linewidth=2, markersize=9,
        label='Bennu (101955)', markeredgecolor='white', markeredgewidth=0.8, zorder=5)

# Annotate points
labels = ['Systematic\nBias', 'Stochastic\nNoise', 'Targeted\nOutlier']
for i, (mag, la, da, db) in enumerate(zip(inj_magnitudes, labels, apophis_delta, bennu_delta)):
    ax.annotate(la, xy=(mag, da), xytext=(mag+0.05, da+150),
                color=C_APOPHIS, fontsize=8, ha='left')
    if i == 2:
        ax.annotate(la, xy=(mag, db), xytext=(mag+0.05, db-300),
                    color=C_BENNU, fontsize=8, ha='left')

ax.set_xlabel('Mean Injection Magnitude (arcseconds)', color=MUTED, fontsize=10)
ax.set_ylabel('CAD Delta (km)', color=MUTED, fontsize=10)
ax.set_title('Figure 3: Injection Magnitude vs Orbital Prediction Error\n'
             'Relationship between astrometric perturbation and close approach distance shift',
             color=TEXT, fontsize=12, fontweight='bold', pad=15)
ax.legend(facecolor=SURF, edgecolor=GRID, labelcolor=TEXT, fontsize=9)
ax.invert_xaxis()  # higher magnitude on left

fig.text(0.5, 0.01,
         'Note: Targeted outlier mean magnitude is low (0.064 arcsec) because only 20/9337 '
         'or 20/603 observations are corrupted; individual outlier magnitude = 30 arcsec',
         ha='center', color=MUTED, fontsize=7.5)

plt.tight_layout(rect=[0, 0.04, 1, 1])
path3 = os.path.join(OUTPUT_DIR, "fig3_magnitude_vs_orbital_impact.png")
plt.savefig(path3, dpi=180, bbox_inches='tight', facecolor=BG)
plt.close()
print(f"Saved: {path3}")


# ── Figure 4: Summary heatmap ───────────────────────────────────────
fig, ax = plt.subplots(figsize=(8, 4))
style_dark(ax, fig)

data = np.array([apophis_delta, bennu_delta])
im = ax.imshow(data, cmap='YlOrRd', aspect='auto', vmin=0, vmax=5500)

ax.set_xticks([0, 1, 2])
ax.set_xticklabels(['Systematic Bias\n(2.0 arcsec)', 'Stochastic Noise\n(1.5 arcsec std)',
                    'Targeted Outlier\n(30 arcsec, 20 obs)'], color=TEXT, fontsize=9)
ax.set_yticks([0, 1])
ax.set_yticklabels(['Apophis\n(9,337 obs)', 'Bennu\n(603 obs)'], color=TEXT, fontsize=10)

for i in range(2):
    for j in range(3):
        val = data[i, j]
        ax.text(j, i, f'{val:,.0f} km', ha='center', va='center',
                color='white' if val > 2500 else 'black',
                fontsize=10, fontweight='bold')

cbar = fig.colorbar(im, ax=ax, pad=0.02)
cbar.ax.tick_params(colors=MUTED, labelsize=8)
cbar.set_label('CAD Delta (km)', color=MUTED, fontsize=9)

ax.set_title('Figure 4: Orbital Impact Heatmap — CAD Delta by Object and Attack Type',
             color=TEXT, fontsize=11, fontweight='bold', pad=12)

plt.tight_layout()
path4 = os.path.join(OUTPUT_DIR, "fig4_heatmap.png")
plt.savefig(path4, dpi=180, bbox_inches='tight', facecolor=BG)
plt.close()
print(f"Saved: {path4}")

print(f"\nAll 4 figures saved to {OUTPUT_DIR}/")
print("These go directly into Chapter 5 — Results of your dissertation.")
