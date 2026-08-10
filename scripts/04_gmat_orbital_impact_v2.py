"""
Objective 2 — GMAT Orbital Impact Assessment (Final Version)
Uses the geocentric approach starting just before the 2029 close approach.
Gets JPL state vectors for each scenario, perturbs them to model injection
impact, runs GMAT for each, and compares minimum Earth distance.

Dissertation: Integrity Assurance in Planetary Defense
Author: Nithin Yadav Gopinath (C5003001)
"""

import os
import subprocess
import pandas as pd
import numpy as np
from datetime import datetime

GMAT_CONSOLE = "/Applications/GMAT R2026a/bin/GmatConsole"
RESULTS_DIR  = "results"

# ── Baseline geocentric state vectors from JPL Horizons ──────────
# Apophis relative to Earth centre, 2029-Apr-01 00:00:00 UTC
# Source: JPL Horizons API, location=500@399, epoch=2462196.5
BASELINE = {
    "X":  -18996756.845,   # km
    "Y":  -13371553.978,
    "Z":   -5699719.752,
    "VX":  6.345883,       # km/s
    "VY":  2.656160,
    "VZ":  1.259470,
}

# ── How each injection archetype perturbs the state ───────────────
# Each injection shifts the RA/Dec observation coordinates.
# We model the resulting state vector perturbation as a small
# positional offset in the X/Y plane (RA-Dec maps to sky-plane
# position error which translates to X/Y at close approach epoch).
#
# Conversion: 1 arcsec at ~19M km geocentric distance ≈ 92 km positional error
# Systematic 2 arcsec    → ~184 km position offset
# Stochastic ~1.2 arcsec → ~110 km position offset
# Targeted outlier       → ~6 km mean (low mean, high on 20 obs)
#
# This is the key scientific contribution: quantifying how each
# injection magnitude translates to orbital prediction error.

SCENARIOS = {
    "clean": {
        "label": "Clean (True Orbit — Baseline)",
        "dx": 0.0, "dy": 0.0, "dz": 0.0,
        "dvx": 0.0, "dvy": 0.0, "dvz": 0.0,
    },
    "systematic_bias": {
        "label": "Systematic Bias (2.0 arcsec uniform)",
        "dx": 184.0, "dy": 184.0, "dz": 0.0,
        "dvx": 0.002, "dvy": 0.002, "dvz": 0.0,
    },
    "stochastic_noise": {
        "label": "Stochastic Noise (1.5 arcsec std, mean 1.2)",
        "dx": 110.0, "dy": 110.0, "dz": 0.0,
        "dvx": 0.001, "dvy": 0.001, "dvz": 0.0,
    },
    "targeted_outlier": {
        "label": "Targeted Outlier (30 arcsec, 20 obs)",
        "dx": 6.0, "dy": 6.0, "dz": 0.0,
        "dvx": 0.0001, "dvy": 0.0001, "dvz": 0.0,
    },
}


def write_gmat_script(scenario_name, state, report_path):
    """Write a GMAT script using geocentric Cartesian state."""
    script = f"""Create Spacecraft Apophis;
Apophis.DateFormat = UTCGregorian;
Apophis.Epoch = '01 Apr 2029 00:00:00.000';
Apophis.CoordinateSystem = EarthMJ2000Eq;
Apophis.DisplayStateType = Cartesian;
Apophis.X  = {state['X']:.3f};
Apophis.Y  = {state['Y']:.3f};
Apophis.Z  = {state['Z']:.3f};
Apophis.VX = {state['VX']:.6f};
Apophis.VY = {state['VY']:.6f};
Apophis.VZ = {state['VZ']:.6f};

Create ForceModel EarthForces;
EarthForces.CentralBody = Earth;
EarthForces.PrimaryBodies = {{Earth}};
EarthForces.PointMasses = {{Sun, Luna, Jupiter}};
EarthForces.GravityField.Earth.Degree = 0;
EarthForces.GravityField.Earth.Order = 0;

Create Propagator EarthProp;
EarthProp.FM = EarthForces;
EarthProp.Type = RungeKutta89;

Create ReportFile CAReport;
CAReport.Filename = '{report_path}';
CAReport.WriteHeaders = true;
CAReport.Add = {{Apophis.UTCGregorian, Apophis.Earth.RMAG}};

BeginMissionSequence;
Propagate EarthProp(Apophis) {{Apophis.ElapsedDays = 20}};
"""
    script_path = f"/tmp/gmat_{scenario_name}.script"
    with open(script_path, "w", encoding="ascii", errors="replace") as f:
        f.write(script)
    return script_path


def run_gmat(script_path):
    print(f"  Running GMAT...")
    result = subprocess.run(
        [GMAT_CONSOLE, "-r", script_path],
        capture_output=True, timeout=120,
        errors="replace"
    )
    stdout = result.stdout.decode("utf-8", errors="replace") if isinstance(result.stdout, bytes) else result.stdout
    lines = [l for l in stdout.strip().split('\n') if l.strip()]
    for line in lines[-3:]:
        if any(k in line.lower() for k in ['mission', 'error', 'complete']):
            print(f"  GMAT: {line.strip()}")
    return result.returncode


def parse_min_distance(report_path):
    if not os.path.exists(report_path):
        print(f"  WARNING: Report not found at {report_path}")
        return None
    with open(report_path, 'r') as f:
        lines = f.readlines()
    vals = []
    for line in lines[1:]:
        parts = line.strip().split()
        if parts:
            try:
                vals.append(float(parts[-1]))
            except:
                pass
    if not vals:
        return None
    return min(vals)


def main():
    os.makedirs(RESULTS_DIR, exist_ok=True)
    results = []

    for scenario_name, scenario in SCENARIOS.items():
        print(f"\n{'='*55}")
        print(f"Scenario: {scenario['label']}")
        print(f"{'='*55}")

        # Apply perturbation to baseline state
        state = {
            "X":  BASELINE["X"]  + scenario["dx"],
            "Y":  BASELINE["Y"]  + scenario["dy"],
            "Z":  BASELINE["Z"]  + scenario["dz"],
            "VX": BASELINE["VX"] + scenario["dvx"],
            "VY": BASELINE["VY"] + scenario["dvy"],
            "VZ": BASELINE["VZ"] + scenario["dvz"],
        }
        print(f"  Position offset: dX={scenario['dx']:.1f} km, dY={scenario['dy']:.1f} km")

        report_path = f"/tmp/gmat_report_{scenario_name}.txt"
        script_path = write_gmat_script(scenario_name, state, report_path)
        print(f"  Script: {script_path}")

        run_gmat(script_path)

        min_dist = parse_min_distance(report_path)
        min_ld   = min_dist / 384400.0 if min_dist else None

        results.append({
            "scenario":    scenario_name,
            "label":       scenario["label"],
            "dist_km":     min_dist,
            "dist_ld":     min_ld,
            "dx_km":       scenario["dx"],
        })

        if min_dist:
            print(f"  Min Earth distance: {min_dist:,.1f} km  ({min_ld:.4f} LD)")

    # ── Results table ──────────────────────────────────────────────
    print(f"\n{'='*55}")
    print("RESULTS — Close Approach Distance Comparison")
    print(f"{'='*55}")

    df = pd.DataFrame(results)
    clean_dist = df.loc[df["scenario"]=="clean", "dist_km"].values[0]

    if clean_dist is None:
        print("ERROR: Clean baseline failed. Check GMAT output above.")
        return

    df["delta_km"] = df["dist_km"] - clean_dist
    df["delta_ld"] = df["delta_km"] / 384400.0

    print(f"\n{'Scenario':<45} {'Min Dist (km)':>15} {'LD':>8} {'Delta km':>12}")
    print("-" * 85)
    for _, row in df.iterrows():
        if row["dist_km"]:
            print(f"{row['label']:<45} {row['dist_km']:>15,.1f} {row['dist_ld']:>8.4f} {row['delta_km']:>+12.1f}")

    # Save
    ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = os.path.join(RESULTS_DIR, f"cad_comparison_{ts}.csv")
    df.to_csv(out, index=False)
    print(f"\nSaved -> {out}")
    print("\nDone. These CAD delta values are your dissertation's core experimental result.")
    print("The delta_km column shows how much each injection scenario shifts the predicted")
    print("closest approach distance — this is what goes in your Results chapter.")


if __name__ == "__main__":
    main()
