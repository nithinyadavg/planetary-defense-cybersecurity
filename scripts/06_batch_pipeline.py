"""
Batch Pipeline — Full NEO Study Set (10 Objects)
Runs the complete pipeline automatically for all objects:
  1. Fetch ADES data from MPC API
  2. Parse into clean DataFrame
  3. Apply 3 injection archetypes
  4. Fetch JPL state vectors
  5. Run GMAT for clean + 3 attacked scenarios
  6. Record CAD deltas
  7. Output complete results table

Dissertation: Integrity Assurance in Planetary Defense
Author: Nithin Yadav Gopinath (C5003001)
"""

import os
import subprocess
import time
import json
import xml.etree.ElementTree as ET
from datetime import datetime

import requests
import numpy as np
import pandas as pd
from astroquery.jplhorizons import Horizons

# ── Configuration ─────────────────────────────────────────────────
GMAT_CONSOLE = "/Applications/GMAT R2026a/bin/GmatConsole"
RESULTS_DIR  = "results"
RAW_DIR      = "data/raw/batch"
RNG_SEED     = 42
rng          = np.random.default_rng(RNG_SEED)
AU           = 149597870.7
DAY          = 86400.0

os.makedirs(RESULTS_DIR, exist_ok=True)
os.makedirs(RAW_DIR,     exist_ok=True)

# ── NEO Study Set ─────────────────────────────────────────────────
NEO_OBJECTS = [
    {"name": "Apophis",    "mpc_id": "99942",   "jpl_id": "99942",   "category": "Famous"},
    {"name": "Bennu",      "mpc_id": "101955",  "jpl_id": "101955",  "category": "Famous"},
    {"name": "Eros",       "mpc_id": "433",     "jpl_id": "433",     "category": "Famous"},
    {"name": "Itokawa",    "mpc_id": "25143",   "jpl_id": "25143",   "category": "Famous"},
    {"name": "Didymos",    "mpc_id": "65803",   "jpl_id": "65803",   "category": "Notable"},
    {"name": "Florence",   "mpc_id": "3122",    "jpl_id": "3122",    "category": "Notable"},
    {"name": "Geographos", "mpc_id": "1620",    "jpl_id": "1620",    "category": "Notable"},
    {"name": "2012 DA14",  "mpc_id": "367943",  "jpl_id": "367943",  "category": "Obscure"},
    {"name": "Phaethon",   "mpc_id": "3200",    "jpl_id": "3200",    "category": "Obscure"},
    {"name": "2023 BU",    "mpc_id": "2023 BU", "jpl_id": "2023 BU", "category": "Barely known"},
]

# ── Injection parameters ──────────────────────────────────────────
ARCHETYPES = {
    "clean":            {"dx": 0.0,   "dy": 0.0,   "dvx": 0.0,    "dvy": 0.0},
    "systematic_bias":  {"dx": 184.0, "dy": 184.0, "dvx": 0.002,  "dvy": 0.002},
    "stochastic_noise": {"dx": 110.0, "dy": 110.0, "dvx": 0.001,  "dvy": 0.001},
    "targeted_outlier": {"dx": 18.0,  "dy": 18.0,  "dvx": 0.0003, "dvy": 0.0003},
}


# ── Step 1: Fetch MPC data ────────────────────────────────────────
def fetch_mpc(mpc_id, name):
    print(f"  [MPC] Fetching {name} ({mpc_id})...")
    try:
        resp = requests.get(
            "https://data.minorplanetcenter.net/api/get-obs",
            json={"desigs": [mpc_id], "output_format": ["XML"]},
            timeout=60
        )
        if not resp.ok:
            print(f"  [MPC] ERROR {resp.status_code}")
            return None
        data = resp.json()
        xml_content = data[0].get("XML") if data else None
        if not xml_content:
            print(f"  [MPC] No XML returned")
            return None
        xml_path = os.path.join(RAW_DIR, f"{name.replace(' ','_')}_ades.xml")
        with open(xml_path, "w") as f:
            f.write(xml_content)
        return xml_path
    except Exception as e:
        print(f"  [MPC] Exception: {e}")
        return None


# ── Step 2: Parse ADES XML ────────────────────────────────────────
def parse_ades(xml_path, name):
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        records = []
        for optical in root.iter("optical"):
            def g(tag):
                el = optical.find(tag)
                return el.text.strip() if el is not None and el.text else None
            records.append({
                "obsTime": g("obsTime"),
                "ra_deg":  g("ra"),
                "dec_deg": g("dec"),
                "station": g("stn"),
            })
        df = pd.DataFrame(records)
        df["ra_deg"]  = pd.to_numeric(df["ra_deg"],  errors="coerce")
        df["dec_deg"] = pd.to_numeric(df["dec_deg"], errors="coerce")
        df["obsTime"] = pd.to_datetime(df["obsTime"], errors="coerce", utc=True)
        df = df.dropna(subset=["obsTime","ra_deg","dec_deg"]).reset_index(drop=True)
        print(f"  [PARSE] {len(df)} clean observations")
        return df
    except Exception as e:
        print(f"  [PARSE] Exception: {e}")
        return None


# ── Step 3: Injection ─────────────────────────────────────────────
def inject(df, archetype):
    attacked = df.copy()
    n = len(attacked)
    if archetype == "systematic_bias":
        shift = 2.0 / 3600.0
        attacked["ra_deg"]  += shift
        attacked["dec_deg"] += shift
        n_changed = n
        mean_shift = 2.0
    elif archetype == "stochastic_noise":
        std = 1.5 / 3600.0
        attacked["ra_deg"]  += rng.normal(0, std, n)
        attacked["dec_deg"] += rng.normal(0, std, n)
        n_changed = n
        mean_shift = 1.5
    elif archetype == "targeted_outlier":
        n_targets = min(20, n)
        targets = rng.choice(attacked.index, size=n_targets, replace=False)
        shift = 30.0 / 3600.0
        for idx in targets:
            d = rng.choice([-1,1])
            attacked.loc[idx, "ra_deg"]  += d * shift
            attacked.loc[idx, "dec_deg"] += d * shift
        n_changed = n_targets
        mean_shift = (n_targets * 30.0) / n
    else:
        n_changed = 0
        mean_shift = 0.0
    return attacked, n_changed, mean_shift


# ── Step 4: JPL state vectors ─────────────────────────────────────
def get_state_vectors(jpl_id, name):
    print(f"  [JPL] Fetching state vectors for {name}...")
    try:
        # Geocentric state vectors at 2020-Jan-01
        obj = Horizons(id=jpl_id, location='500@399', epochs=2458849.5)
        vec = obj.vectors()
        state = {
            "X":  float(vec['x'][0])  * AU,
            "Y":  float(vec['y'][0])  * AU,
            "Z":  float(vec['z'][0])  * AU,
            "VX": float(vec['vx'][0]) * AU / DAY,
            "VY": float(vec['vy'][0]) * AU / DAY,
            "VZ": float(vec['vz'][0]) * AU / DAY,
        }
        print(f"  [JPL] Got state vectors (dist from Earth: {np.sqrt(state['X']**2+state['Y']**2+state['Z']**2):,.0f} km)")
        return state
    except Exception as e:
        print(f"  [JPL] Exception: {e}")
        return None


# ── Step 5: GMAT run ──────────────────────────────────────────────
def run_gmat_scenario(name, state, archetype, delta):
    perturbed = {
        "X":  state["X"]  + delta["dx"],
        "Y":  state["Y"]  + delta["dy"],
        "Z":  state["Z"],
        "VX": state["VX"] + delta["dvx"],
        "VY": state["VY"] + delta["dvy"],
        "VZ": state["VZ"],
    }
    safe_name = name.replace(' ','_').replace('/','_')
    report_path = f"/tmp/gmat_{safe_name}_{archetype}.txt"
    script = f"""Create Spacecraft NEO;
NEO.DateFormat = UTCGregorian;
NEO.Epoch = '01 Jan 2020 00:00:00.000';
NEO.CoordinateSystem = EarthMJ2000Eq;
NEO.DisplayStateType = Cartesian;
NEO.X  = {perturbed['X']:.3f};
NEO.Y  = {perturbed['Y']:.3f};
NEO.Z  = {perturbed['Z']:.3f};
NEO.VX = {perturbed['VX']:.6f};
NEO.VY = {perturbed['VY']:.6f};
NEO.VZ = {perturbed['VZ']:.6f};
Create ForceModel EarthForces;
EarthForces.CentralBody = Earth;
EarthForces.PrimaryBodies = {{Earth}};
EarthForces.PointMasses = {{Sun, Luna, Jupiter}};
EarthForces.GravityField.Earth.Degree = 0;
EarthForces.GravityField.Earth.Order = 0;
Create Propagator EarthProp;
EarthProp.FM = EarthForces;
EarthProp.Type = RungeKutta89;
Create ReportFile R;
R.Filename = '{report_path}';
R.WriteHeaders = true;
R.Add = {{NEO.UTCGregorian, NEO.Earth.RMAG}};
BeginMissionSequence;
Propagate EarthProp(NEO) {{NEO.ElapsedDays = 30}};
"""
    script_path = f"/tmp/gmat_{safe_name}_{archetype}.script"
    with open(script_path, "w", encoding="ascii", errors="replace") as f:
        f.write(script)

    result = subprocess.run(
        [GMAT_CONSOLE, "-r", script_path],
        capture_output=True, timeout=120,
        errors="replace"
    )

    # Parse report
    if not os.path.exists(report_path):
        return None
    vals = []
    with open(report_path) as f:
        for line in f.readlines()[1:]:
            parts = line.strip().split()
            if parts:
                try: vals.append(float(parts[-1]))
                except: pass
    return min(vals) if vals else None


# ── Main batch runner ─────────────────────────────────────────────
def main():
    print(f"\n{'='*65}")
    print(f"NEO BATCH PIPELINE — {len(NEO_OBJECTS)} objects")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*65}\n")

    all_results = []

    for obj in NEO_OBJECTS:
        name     = obj["name"]
        mpc_id   = obj["mpc_id"]
        jpl_id   = obj["jpl_id"]
        category = obj["category"]

        print(f"\n{'─'*65}")
        print(f"OBJECT: {name}  [{category}]")
        print(f"{'─'*65}")

        # Step 1: fetch
        xml_path = fetch_mpc(mpc_id, name)
        if not xml_path:
            print(f"  SKIP: could not fetch MPC data for {name}")
            all_results.append({"name": name, "category": category,
                                 "n_obs": 0, "status": "MPC fetch failed"})
            continue

        # Step 2: parse
        df = parse_ades(xml_path, name)
        if df is None or len(df) == 0:
            print(f"  SKIP: no usable observations for {name}")
            all_results.append({"name": name, "category": category,
                                 "n_obs": 0, "status": "No usable obs"})
            continue
        n_obs = len(df)

        # Step 3: injection stats
        injection_stats = {}
        for arch in ["systematic_bias", "stochastic_noise", "targeted_outlier"]:
            _, n_changed, mean_shift = inject(df, arch)
            pct = (n_changed / n_obs) * 100
            injection_stats[arch] = {"n_changed": n_changed, "pct": pct, "mean_shift_arcsec": mean_shift}

        # Step 4: JPL state vectors
        state = get_state_vectors(jpl_id, name)
        if not state:
            print(f"  SKIP: could not get JPL state vectors for {name}")
            all_results.append({"name": name, "category": category,
                                 "n_obs": n_obs, "status": "JPL fetch failed"})
            continue

        # Step 5: GMAT runs
        distances = {}
        for arch, delta in ARCHETYPES.items():
            print(f"  [GMAT] Running {arch}...")
            dist = run_gmat_scenario(name, state, arch, delta)
            distances[arch] = dist
            if dist:
                print(f"         Min dist = {dist:,.1f} km")
            else:
                print(f"         No result")
            time.sleep(0.5)  # small pause between runs

        # Calculate deltas
        clean_dist = distances.get("clean")
        if clean_dist is None:
            print(f"  SKIP: GMAT clean run failed for {name}")
            all_results.append({"name": name, "category": category,
                                 "n_obs": n_obs, "status": "GMAT failed"})
            continue

        result = {
            "name":               name,
            "category":           category,
            "n_obs":              n_obs,
            "status":             "OK",
            "pct_corrupted_targeted": round(injection_stats["targeted_outlier"]["pct"], 3),
            "clean_dist_km":      round(clean_dist, 1),
            "bias_dist_km":       round(distances.get("systematic_bias", 0) or 0, 1),
            "noise_dist_km":      round(distances.get("stochastic_noise", 0) or 0, 1),
            "outlier_dist_km":    round(distances.get("targeted_outlier", 0) or 0, 1),
            "bias_delta_km":      round((distances.get("systematic_bias") or clean_dist) - clean_dist, 1),
            "noise_delta_km":     round((distances.get("stochastic_noise") or clean_dist) - clean_dist, 1),
            "outlier_delta_km":   round((distances.get("targeted_outlier") or clean_dist) - clean_dist, 1),
        }
        all_results.append(result)

        print(f"\n  RESULTS for {name}:")
        print(f"  Observations: {n_obs}  |  Targeted outlier: {result['pct_corrupted_targeted']}% of dataset")
        print(f"  Systematic bias delta : {result['bias_delta_km']:+,.1f} km")
        print(f"  Stochastic noise delta: {result['noise_delta_km']:+,.1f} km")
        print(f"  Targeted outlier delta: {result['outlier_delta_km']:+,.1f} km")

    # ── Final results table ───────────────────────────────────────
    print(f"\n\n{'='*65}")
    print("COMPLETE RESULTS TABLE")
    print(f"{'='*65}")

    df_results = pd.DataFrame(all_results)
    print(df_results.to_string(index=False))

    ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = os.path.join(RESULTS_DIR, f"batch_results_{ts}.csv")
    df_results.to_csv(out, index=False)
    print(f"\nSaved -> {out}")
    print(f"\nFinished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("All done. Upload the CSV and I will generate the full results table and charts.")


if __name__ == "__main__":
    main()
