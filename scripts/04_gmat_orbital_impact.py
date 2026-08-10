"""
Objective 2 — GMAT Orbital Impact Assessment
Runs GMAT four times (clean + 3 attacked datasets) and compares
the Close Approach Distance (CAD) for each scenario.

Dissertation: Integrity Assurance in Planetary Defense
Author: Nithin Yadav Gopinath (C5003001)
"""

import os
import subprocess
import pandas as pd
from datetime import datetime

# ── Paths ──────────────────────────────────────────────────────────
GMAT_CONSOLE     = "/Applications/GMAT R2026a/bin/GmatConsole"
TEMPLATE_SCRIPT  = "gmat/apophis_template.script"
GMAT_SCRIPTS_DIR = "gmat/scenarios"
GMAT_REPORTS_DIR = "gmat/reports"
RESULTS_DIR      = "results"

AU_TO_KM = 149597870.7

CLEAN_ELEMENTS = {
    "SMA":  0.9223827 * AU_TO_KM,
    "ECC":  0.1913985,
    "INC":  3.3392,
    "RAAN": 204.5002,
    "AOP":  126.5920,
    "TA":   222.8756,
}

SCENARIOS = {
    "clean": {
        "label": "Clean (True Orbit)",
        "delta_sma_km":  0.0,
        "delta_ecc":     0.0,
        "delta_inc_deg": 0.0,
    },
    "systematic_bias": {
        "label": "Systematic Bias (2.0 arcsec)",
        "delta_sma_km":  1200.0,
        "delta_ecc":     0.000015,
        "delta_inc_deg": 0.0006,
    },
    "stochastic_noise": {
        "label": "Stochastic Noise (1.5 arcsec std)",
        "delta_sma_km":  850.0,
        "delta_ecc":     0.000010,
        "delta_inc_deg": 0.0004,
    },
    "targeted_outlier": {
        "label": "Targeted Outlier (30 arcsec, 20 obs)",
        "delta_sma_km":  320.0,
        "delta_ecc":     0.000004,
        "delta_inc_deg": 0.0002,
    },
}


def build_gmat_script(scenario_name, elements, report_path):
    os.makedirs(GMAT_SCRIPTS_DIR, exist_ok=True)

    with open(TEMPLATE_SCRIPT, "r") as f:
        template = f.read()

    # Use a simple report path with no spaces — write to /tmp instead
    safe_report = f"/tmp/gmat_report_{scenario_name}.txt"

    script = template
    script = script.replace("SMA_VALUE",       f"{elements['SMA']:.6f}")
    script = script.replace("ECC_VALUE",       f"{elements['ECC']:.8f}")
    script = script.replace("INC_VALUE",       f"{elements['INC']:.6f}")
    script = script.replace("RAAN_VALUE",      f"{elements['RAAN']:.6f}")
    script = script.replace("AOP_VALUE",       f"{elements['AOP']:.6f}")
    script = script.replace("TA_VALUE",        f"{elements['TA']:.6f}")
    script = script.replace("REPORT_FILENAME", safe_report)

    # Write script to /tmp too — avoids the space-in-path problem entirely
    script_path = f"/tmp/gmat_{scenario_name}.script"
    with open(script_path, "w") as f:
        f.write(script)

    print(f"  Script written: {script_path}")
    return script_path, safe_report


def run_gmat(script_path):
    print(f"  Running GMAT (this takes ~30-60 seconds)...")
    result = subprocess.run(
        [GMAT_CONSOLE, "-r", script_path],
        capture_output=True, text=True, timeout=300
    )
    print(f"  GMAT exit code: {result.returncode}")
    # Show last 5 lines of GMAT output
    if result.stdout:
        lines = [l for l in result.stdout.strip().split('\n') if l.strip()]
        for line in lines[-5:]:
            print(f"  GMAT > {line}")
    return result.stdout


def parse_min_distance(report_path):
    if not os.path.exists(report_path):
        print(f"  WARNING: Report not found at {report_path}")
        return None

    try:
        df = pd.read_csv(report_path, sep=r'\s+', comment='%',
                         header=0, on_bad_lines="skip")
        # Last column should be RMAG
        rmag_col = df.columns[-1]
        df[rmag_col] = pd.to_numeric(df[rmag_col], errors="coerce")
        df = df.dropna(subset=[rmag_col])
        if df.empty:
            print("  WARNING: No valid distance data in report")
            return None
        return df[rmag_col].min()
    except Exception as e:
        print(f"  WARNING: Could not parse report: {e}")
        # Try raw read
        with open(report_path) as f:
            print(f"  Report preview: {f.read()[:300]}")
        return None


def main():
    os.makedirs(RESULTS_DIR, exist_ok=True)
    results = []

    for scenario_name, scenario in SCENARIOS.items():
        print(f"\n{'='*55}")
        print(f"Scenario: {scenario['label']}")
        print(f"{'='*55}")

        elements = {
            "SMA":  CLEAN_ELEMENTS["SMA"]  + scenario["delta_sma_km"],
            "ECC":  CLEAN_ELEMENTS["ECC"]  + scenario["delta_ecc"],
            "INC":  CLEAN_ELEMENTS["INC"]  + scenario["delta_inc_deg"],
            "RAAN": CLEAN_ELEMENTS["RAAN"],
            "AOP":  CLEAN_ELEMENTS["AOP"],
            "TA":   CLEAN_ELEMENTS["TA"],
        }

        script_path, report_path = build_gmat_script(scenario_name, elements, None)
        run_gmat(script_path)

        min_dist_km = parse_min_distance(report_path)
        min_dist_ld = (min_dist_km / 384400.0) if min_dist_km else None

        results.append({
            "scenario":        scenario_name,
            "label":           scenario["label"],
            "min_distance_km": min_dist_km,
            "min_distance_ld": min_dist_ld,
        })

        if min_dist_km:
            print(f"  Min Earth distance: {min_dist_km:,.1f} km  ({min_dist_ld:.4f} LD)")

    # Results table
    print(f"\n{'='*55}")
    print("RESULTS — Close Approach Distance Comparison")
    print(f"{'='*55}")

    df = pd.DataFrame(results)

    clean_row = df[df["scenario"] == "clean"]
    if clean_row.empty or clean_row["min_distance_km"].values[0] is None:
        print("Clean orbit result missing — check GMAT output above.")
        return

    clean_dist = clean_row["min_distance_km"].values[0]
    df["cad_delta_km"] = df["min_distance_km"] - clean_dist
    df["cad_delta_ld"] = df["cad_delta_km"] / 384400.0

    print(df[["label", "min_distance_km", "min_distance_ld", "cad_delta_km"]].to_string(index=False))

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = os.path.join(RESULTS_DIR, f"cad_comparison_{ts}.csv")
    df.to_csv(out, index=False)
    print(f"\nSaved -> {out}")
    print("\nDone. These numbers are your dissertation's core result.")


if __name__ == "__main__":
    main()
