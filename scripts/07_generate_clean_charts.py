"""
Chapter 4 Figures — Clean Academic Style
Generates 4 publication-quality charts matching the dissertation's
plain, no-colour, formal style (light background, black/grey text,
minimal colour used only functionally to distinguish data series).

Dissertation: Integrity Assurance in Planetary Defense
Author: Nithin Yadav Gopinath (C5003001)
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import os

OUTPUT_DIR = "results/figures_clean"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── Clean academic palette ─────────────────────────────────────────
INK      = "#1A1A1A"
GRID     = "#D9D9D9"
BLUE     = "#2E5C8A"
GRAY     = "#8C8C8C"
LIGHTBG  = "#FFFFFF"
BAR1     = "#2E5C8A"   # primary series
BAR2     = "#8C8C8C"   # secondary series (greyscale-safe for print)

plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Calibri ", "Miriam Libre", ],
    "axes.edgecolor": GRID,
    "axes.labelcolor": INK,
    "text.color": INK,
    "xtick.color": INK,
    "ytick.color": INK,
})

def style_light(ax, fig):
    fig.patch.set_facecolor(LIGHTBG)
    ax.set_facecolor(LIGHTBG)
    ax.grid(axis='y', color=GRID, linewidth=0.6, linestyle='-', alpha=0.8)
    ax.set_axisbelow(True)
    for spine in ['top', 'right']:
        ax.spines[spine].set_visible(False)
    for spine in ['left', 'bottom']:
        ax.spines[spine].set_color('#444444')


# ── Data: full 10-object study set ──────────────────────────────────
objects_all = ["2012 DA14", "Didymos", "Bennu", "Florence", "Apophis",
               "2023 BU", "Phaethon", "Geographos", "Eros", "Itokawa"]
n_obs_all   = [1071, 5930, 603, 9817, 9337, 1758, 8809, 9493, 17975, 1260]
bias_all    = [-7198.0, -5385.1, 3334.6, 1158.6, 822.3, 218.0, 215.2, 193.2, -77.7, 39.5]
noise_all   = [-3620.9, -2711.0, 1679.7, 584.9, 428.0, 130.3, 128.7, 115.5, -46.4, 23.6]
outlier_all = [-1068.0, -797.9, 493.5, 170.5, 114.5, 21.3, 21.1, 18.9, -7.6, 3.9]
pct_corrupt = [1.867, 0.337, 3.317, 0.204, 0.214, 1.138, 0.227, 0.211, 0.111, 1.587]


# ═════════════════════ FIGURE 1: CAD Delta by archetype (all 10 objects) ═════════
fig, ax = plt.subplots(figsize=(10, 6))
style_light(ax, fig)

abs_bias    = [abs(v) for v in bias_all]
abs_noise   = [abs(v) for v in noise_all]
abs_outlier = [abs(v) for v in outlier_all]

# Sort by abs_outlier descending for readability
order = sorted(range(len(objects_all)), key=lambda i: -abs_outlier[i])
objs_sorted    = [objects_all[i] for i in order]
bias_sorted    = [abs_bias[i] for i in order]
noise_sorted   = [abs_noise[i] for i in order]
outlier_sorted = [abs_outlier[i] for i in order]

x = np.arange(len(objs_sorted))
width = 0.26

ax.bar(x - width, bias_sorted,    width, label='Systematic Bias',  color=BLUE,  edgecolor='#1A3A5C', linewidth=0.5)
ax.bar(x,          noise_sorted,   width, label='Stochastic Noise', color=GRAY,  edgecolor='#555555', linewidth=0.5)
ax.bar(x + width,  outlier_sorted, width, label='Targeted Outlier', color='#C9C9C9', edgecolor='#888888', linewidth=0.5)

ax.set_xticks(x)
ax.set_xticklabels(objs_sorted, rotation=35, ha='right', fontsize=9)
ax.set_ylabel('Absolute Close Approach Distance (CAD) Delta (km)', fontsize=10)
ax.set_title('Figure 4.1: CAD Delta by Injection Archetype Across the Ten-Object Study Set',
             fontsize=12, fontweight='bold', pad=14)
ax.legend(frameon=False, fontsize=9, loc='upper right')

plt.tight_layout()
path1 = os.path.join(OUTPUT_DIR, "fig4_1_cad_delta_all_objects.png")
plt.savefig(path1, dpi=200, bbox_inches='tight', facecolor=LIGHTBG)
plt.close()
print(f"Saved: {path1}")


# ═════════════════════ FIGURE 2: Observation density vs vulnerability (scatter) ═
fig, ax = plt.subplots(figsize=(8.5, 5.5))
style_light(ax, fig)

ax.scatter(n_obs_all, abs_outlier, s=90, color=BLUE, edgecolors='#1A3A5C',
           linewidth=1.0, zorder=5, alpha=0.85)

for i, name in enumerate(objects_all):
    ax.annotate(name, (n_obs_all[i], abs_outlier[i]),
                xytext=(6, 6), textcoords='offset points',
                fontsize=8.5, color=INK)

# Trend line (linear fit on log-x for visual clarity)
z = np.polyfit(np.log(n_obs_all), abs_outlier, 1)
x_fit = np.linspace(min(n_obs_all), max(n_obs_all), 100)
y_fit = z[0] * np.log(x_fit) + z[1]
ax.plot(x_fit, y_fit, color=GRAY, linestyle='--', linewidth=1.2, alpha=0.8, label='Trend (log fit)')

ax.set_xlabel('Number of Observations', fontsize=10)
ax.set_ylabel('Targeted Outlier CAD Delta (km, absolute)', fontsize=10)
ax.set_title('Figure 4.2: Observation Density as a Security Variable\n(Pearson r = \u22120.44)',
             fontsize=12, fontweight='bold', pad=14)
ax.legend(frameon=False, fontsize=9)
ax.set_xscale('log')

plt.tight_layout()
path2 = os.path.join(OUTPUT_DIR, "fig4_2_observation_density_scatter.png")
plt.savefig(path2, dpi=200, bbox_inches='tight', facecolor=LIGHTBG)
plt.close()
print(f"Saved: {path2}")


# ═════════════════════ FIGURE 3: Magnitude vs impact (line, Apophis/Bennu focus) ═
fig, ax = plt.subplots(figsize=(9, 5.5))
style_light(ax, fig)

inj_magnitudes = [2.0, 1.2, 0.064]  # Apophis mean arcsec per archetype
inj_magnitudes_bennu = [2.0, 1.163, 0.995]
apophis_deltas = [822.3, 428.0, 114.5]
bennu_deltas   = [3334.6, 1679.7, 493.5]
labels = ['Systematic\nBias', 'Stochastic\nNoise', 'Targeted\nOutlier']

x_pos = np.arange(3)
ax.plot(x_pos, apophis_deltas, marker='o', color=BLUE, linewidth=2,
        markersize=9, label='Apophis (9,337 obs)', markeredgecolor='#1A3A5C', markeredgewidth=1)
ax.plot(x_pos, bennu_deltas, marker='s', color=GRAY, linewidth=2,
        markersize=9, label='Bennu (603 obs)', markeredgecolor='#555555', markeredgewidth=1)

ax.set_xticks(x_pos)
ax.set_xticklabels(labels, fontsize=10)
ax.set_ylabel('CAD Delta (km)', fontsize=10)
ax.set_title('Figure 4.3: Injection Archetype vs Orbital Impact\nApophis and Bennu Compared',
             fontsize=12, fontweight='bold', pad=14)
ax.legend(frameon=False, fontsize=9)

plt.tight_layout()
path3 = os.path.join(OUTPUT_DIR, "fig4_3_magnitude_vs_impact.png")
plt.savefig(path3, dpi=200, bbox_inches='tight', facecolor=LIGHTBG)
plt.close()
print(f"Saved: {path3}")


# ═════════════════════ FIGURE 4: Heatmap of all results ═══════════════════════
fig, ax = plt.subplots(figsize=(9, 6))
fig.patch.set_facecolor(LIGHTBG)

data_matrix = np.array([bias_sorted, noise_sorted, outlier_sorted])

im = ax.imshow(data_matrix, cmap='Greys', aspect='auto', vmin=0, vmax=max(bias_sorted))

ax.set_xticks(range(len(objs_sorted)))
ax.set_xticklabels(objs_sorted, rotation=35, ha='right', fontsize=9, color=INK)
ax.set_yticks([0, 1, 2])
ax.set_yticklabels(['Systematic\nBias', 'Stochastic\nNoise', 'Targeted\nOutlier'], fontsize=9, color=INK)

for i in range(3):
    for j in range(len(objs_sorted)):
        val = data_matrix[i, j]
        text_color = 'white' if val > (max(bias_sorted) * 0.5) else 'black'
        ax.text(j, i, f'{val:,.0f}', ha='center', va='center', color=text_color, fontsize=8)

cbar = fig.colorbar(im, ax=ax, pad=0.02)
cbar.ax.tick_params(labelsize=8, colors=INK)
cbar.set_label('Absolute CAD Delta (km)', fontsize=9, color=INK)

ax.set_title('Figure 4.4: CAD Delta Heatmap Across All Objects and Archetypes',
             fontsize=12, fontweight='bold', color=INK, pad=14)

for spine in ax.spines.values():
    spine.set_visible(False)

plt.tight_layout()
path4 = os.path.join(OUTPUT_DIR, "fig4_4_heatmap_all_objects.png")
plt.savefig(path4, dpi=200, bbox_inches='tight', facecolor=LIGHTBG)
plt.close()
print(f"Saved: {path4}")

print(f"\nAll 4 figures saved to {OUTPUT_DIR}/")
print("Ready to insert into Chapter 4 of the dissertation.")
