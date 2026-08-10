"""
Objective 1 — Step 3: Adversarial Injection Module
Takes the clean Apophis observation DataFrame (from Step 2) and creates
THREE separate "attacked" copies of it, each using a different method
of corrupting the RA/Dec coordinates.

This is the core experimental tool of the dissertation. Nothing here
touches any real system — it only modifies a local copy of data already
saved on your machine.

Dissertation: Integrity Assurance in Planetary Defense
Author: Nithin Yadav Gopinath (C5003001)
"""

import os
import glob
import numpy as np
import pandas as pd
from datetime import datetime

PROCESSED_DIR = "data/processed"
MANIPULATED_DIR = "data/manipulated"

# Random seed fixed for reproducibility — same "random" noise every run,
# so your dissertation results can be exactly reproduced by your supervisor
RNG_SEED = 42
rng = np.random.default_rng(RNG_SEED)


def find_latest_clean_pickle():
    """Finds the most recently saved cleaned dataset from Step 2."""
    pattern = os.path.join(PROCESSED_DIR, "apophis_clean_*.pkl")
    files = glob.glob(pattern)
    if not files:
        raise FileNotFoundError(
            f"No cleaned dataset found in {PROCESSED_DIR}. "
            "Run 02_parse_ades_to_dataframe.py first."
        )
    latest = max(files, key=os.path.getmtime)
    print(f"Using clean dataset: {latest}")
    return latest


# ── The three injection archetypes ──────────────────────────────────

def inject_systematic_bias(df, bias_arcsec=2.0):
    """
    ARCHETYPE 1: Systematic Bias
    --------------------------------
    Shifts EVERY observation by the same fixed amount, in the same
    direction. Simulates a consistent calibration error or a deliberate,
    uniform spoofing of the data feed — like a faulty instrument that's
    always off by the same amount.

    bias_arcsec: how far to shift, in arcseconds (1 arcsec = 1/3600 of a degree)
    """
    df_attacked = df.copy()
    bias_deg = bias_arcsec / 3600.0  # convert arcseconds to degrees

    df_attacked["ra_deg"] = df_attacked["ra_deg"] + bias_deg
    df_attacked["dec_deg"] = df_attacked["dec_deg"] + bias_deg

    df_attacked["injection_type"] = "systematic_bias"
    df_attacked["injection_magnitude_arcsec"] = bias_arcsec
    return df_attacked


def inject_stochastic_noise(df, noise_std_arcsec=1.5):
    """
    ARCHETYPE 2: Stochastic Noise Amplification
    --------------------------------------------
    Adds RANDOM jitter to every observation, drawn from a normal
    (bell-curve) distribution. Each point gets a different, unpredictable
    nudge. Simulates degraded signal quality or random interference
    rather than a deliberate, consistent attack.

    noise_std_arcsec: the "spread" of the random noise, in arcseconds
    """
    df_attacked = df.copy()
    noise_std_deg = noise_std_arcsec / 3600.0

    n = len(df_attacked)
    ra_noise = rng.normal(loc=0, scale=noise_std_deg, size=n)
    dec_noise = rng.normal(loc=0, scale=noise_std_deg, size=n)

    df_attacked["ra_deg"] = df_attacked["ra_deg"] + ra_noise
    df_attacked["dec_deg"] = df_attacked["dec_deg"] + dec_noise

    df_attacked["injection_type"] = "stochastic_noise"
    df_attacked["injection_magnitude_arcsec"] = noise_std_arcsec
    return df_attacked


def inject_targeted_outliers(df, n_targets=20, outlier_arcsec=30.0):
    """
    ARCHETYPE 3: Targeted Outlier Insertion
    -----------------------------------------
    Leaves MOST observations untouched, but heavily corrupts a small,
    specific subset of them. Simulates a precise, deliberate attack
    that focuses effort on a few high-leverage observations rather
    than blanket-corrupting everything — harder to spot via simple
    statistics since most of the dataset still looks clean.

    n_targets: how many observations to corrupt
    outlier_arcsec: how far those specific points are shifted
    """
    df_attacked = df.copy()
    outlier_deg = outlier_arcsec / 3600.0

    n = len(df_attacked)
    n_targets = min(n_targets, n)  # safety check

    # Randomly choose which specific rows to corrupt
    target_indices = rng.choice(df_attacked.index, size=n_targets, replace=False)

    # Apply a large, random-direction shift only to those targeted rows
    for idx in target_indices:
        direction = rng.choice([-1, 1])
        df_attacked.loc[idx, "ra_deg"] += direction * outlier_deg
        df_attacked.loc[idx, "dec_deg"] += direction * outlier_deg

    df_attacked["injection_type"] = "targeted_outlier"
    df_attacked["injection_magnitude_arcsec"] = outlier_arcsec
    df_attacked["is_targeted_row"] = df_attacked.index.isin(target_indices)

    return df_attacked


def save_attacked_dataset(df_attacked, archetype_name):
    os.makedirs(MANIPULATED_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    csv_path = os.path.join(MANIPULATED_DIR, f"apophis_{archetype_name}_{timestamp}.csv")
    df_attacked.to_csv(csv_path, index=False)
    print(f"Saved {archetype_name:18s} -> {csv_path}")
    return csv_path


def summarise_difference(df_clean, df_attacked, archetype_name):
    """Prints a quick before/after comparison so you can SEE the
    injection actually happened, in plain numbers."""
    ra_diff = (df_attacked["ra_deg"] - df_clean["ra_deg"]).abs()
    dec_diff = (df_attacked["dec_deg"] - df_clean["dec_deg"]).abs()

    print(f"\n--- {archetype_name} : before vs after ---")
    print(f"Rows changed at all       : {(ra_diff > 0).sum()} / {len(df_clean)}")
    print(f"Mean RA shift (arcsec)    : {(ra_diff * 3600).mean():.4f}")
    print(f"Max RA shift (arcsec)     : {(ra_diff * 3600).max():.4f}")
    print(f"Mean Dec shift (arcsec)   : {(dec_diff * 3600).mean():.4f}")
    print(f"Max Dec shift (arcsec)    : {(dec_diff * 3600).max():.4f}")


if __name__ == "__main__":
    pkl_path = find_latest_clean_pickle()
    df_clean = pd.read_pickle(pkl_path)
    print(f"Loaded {len(df_clean)} clean observations\n")

    # Run all three archetypes
    df_bias = inject_systematic_bias(df_clean, bias_arcsec=2.0)
    df_noise = inject_stochastic_noise(df_clean, noise_std_arcsec=1.5)
    df_outlier = inject_targeted_outliers(df_clean, n_targets=20, outlier_arcsec=30.0)

    # Save each attacked version separately
    save_attacked_dataset(df_bias, "systematic_bias")
    save_attacked_dataset(df_noise, "stochastic_noise")
    save_attacked_dataset(df_outlier, "targeted_outlier")

    # Show the before/after numbers for each, so the effect is visible
    summarise_difference(df_clean, df_bias, "Systematic Bias")
    summarise_difference(df_clean, df_noise, "Stochastic Noise")
    summarise_difference(df_clean, df_outlier, "Targeted Outlier")

    print("\nDone. Three manipulated datasets created in data/manipulated/.")
    print("Next step: feed the clean dataset AND each manipulated dataset")
    print("into GMAT to see how much each one changes the predicted orbit.")
