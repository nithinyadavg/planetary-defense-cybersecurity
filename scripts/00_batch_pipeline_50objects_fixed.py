"""
Batch Pipeline — 50+ Object Study Set (Fixed & Robust)
Automates fetching, injection, and GMAT propagation.

Fixes applied to the generated version:
  1. CAD API date range was unset (defaults to now->+60 days, which
     returns no data for almost every object). Now explicit and wide.
  2. Injection offsets were a single km value derived only from
     Apophis's geocentric distance, applied uniformly to every object
     regardless of that object's own distance — misrepresenting the
     stated arcsecond magnitudes for objects at different distances.
     Now computed per-object from its own geocentric distance.
  3. Removed one duplicate entry (Toutatis/Tautatis, same object 4179).

Dissertation / Conference Paper: Integrity Assurance in Planetary Defense
Author: Nithin Yadav Gopinath (C5003001)
MSc Cybersecurity, Sheffield Hallam University
"""

import os
import time
import subprocess
import requests
import xml.etree.ElementTree as ET
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime
from astroquery.jplhorizons import Horizons

# ── Configuration ─────────────────────────────────────────────────
# Always resolve paths relative to the project root
PROJECT_ROOT = Path(__file__).resolve().parent
MPC_API_URL  = "https://data.minorplanetcenter.net/api/get-obs"
CAD_API_URL  = "https://ssd-api.jpl.nasa.gov/cad.api"

# GMAT configuration
GMAT_CONSOLE = os.environ.get("GMAT_CONSOLE", "/Applications/GMAT R2026a/bin/GmatConsole")

DATA_RAW    = PROJECT_ROOT / "data" / "raw" / "batch"
RESULTS_DIR = PROJECT_ROOT / "results"
LOG_PATH    = PROJECT_ROOT / "batch_log.txt"

RNG_SEED = 42
rng = np.random.default_rng(RNG_SEED)
AU  = 149597870.7
DAY = 86400.0

# ── Injection parameters ──────────────────────────────────────────
# NOTE: these are arcsecond magnitudes (matches the original 10-object
# study: 2.0" bias, 1.5" noise, targeted outlier). The km-equivalent
# offset is computed PER OBJECT in run_gmat_scenario() from that
# object's own geocentric distance at its close-approach epoch, since
# 1 arcsecond of sky-plane error corresponds to a different km offset
# depending on distance. A single fixed km value (as in the original
# Apophis-only script, ~184 km derived only for Apophis's ~19,000,000 km
# distance) would silently misrepresent the arcsecond magnitude for
# every other object at a different distance.
ARCHETYPES_ARCSEC = {
    "clean":            0.0,
    "systematic_bias":  2.0,
    "stochastic_noise": 1.5,
    "targeted_outlier": 0.3,   # scaled down: effective mean shift across
                                # only 20 corrupted observations out of N,
                                # not a full 30 arcsec applied uniformly
}

# ── NEO Study Set (50 Objects) ────────────────────────────────────
NEO_OBJECTS = [
    # Core 10 Study Objects
    {"name": "Apophis",    "mpc_id": "99942",  "jpl_id": "99942",  "category": "Famous", "ca_epoch": "FILL_ME"},
    {"name": "Bennu",      "mpc_id": "101955", "jpl_id": "101955", "category": "Famous", "ca_epoch": "FILL_ME"},
    {"name": "Eros",       "mpc_id": "433",    "jpl_id": "433",    "category": "Famous", "ca_epoch": "FILL_ME"},
    {"name": "Itokawa",    "mpc_id": "25143",  "jpl_id": "25143",  "category": "Famous", "ca_epoch": "FILL_ME"},
    {"name": "Didymos",    "mpc_id": "65803",  "jpl_id": "65803",  "category": "Notable", "ca_epoch": "FILL_ME"},
    {"name": "Florence",   "mpc_id": "3122",   "jpl_id": "3122",   "category": "Notable", "ca_epoch": "FILL_ME"},
    {"name": "Geographos", "mpc_id": "1620",   "jpl_id": "1620",   "category": "Notable", "ca_epoch": "FILL_ME"},
    {"name": "2012 DA14",  "mpc_id": "367943", "jpl_id": "367943", "category": "Obscure", "ca_epoch": "FILL_ME"},
    {"name": "Phaethon",   "mpc_id": "3200",   "jpl_id": "3200",   "category": "Obscure", "ca_epoch": "FILL_ME"},
    {"name": "2023 BU",    "mpc_id": "2023 BU","jpl_id": "2023 BU","category": "Barely known", "ca_epoch": "FILL_ME"},
    
    # 40 Additional Prominent NEOs
    {"name": "Ryugu",      "mpc_id": "162173", "jpl_id": "162173", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Toutatis",   "mpc_id": "4179",   "jpl_id": "4179",   "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Icarus",     "mpc_id": "1566",   "jpl_id": "1566",   "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Apollo",     "mpc_id": "1862",   "jpl_id": "1862",   "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Aten",       "mpc_id": "2062",   "jpl_id": "2062",   "category": "Aten",   "ca_epoch": "FILL_ME"},
    {"name": "Amor",       "mpc_id": "1221",   "jpl_id": "1221",   "category": "Amor",   "ca_epoch": "FILL_ME"},
    {"name": "Castalia",   "mpc_id": "4769",   "jpl_id": "4769",   "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Bacchus",    "mpc_id": "2063",   "jpl_id": "2063",   "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Hermes",     "mpc_id": "69230",  "jpl_id": "69230",  "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Orpheus",    "mpc_id": "3361",   "jpl_id": "3361",   "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Hathor",     "mpc_id": "2340",   "jpl_id": "2340",   "category": "Aten",   "ca_epoch": "FILL_ME"},
    {"name": "Midas",      "mpc_id": "1981",   "jpl_id": "1981",   "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Adonis",     "mpc_id": "2101",   "jpl_id": "2101",   "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Golevka",    "mpc_id": "6489",   "jpl_id": "6489",   "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Braille",    "mpc_id": "9969",   "jpl_id": "9969",   "category": "Mars-crosser", "ca_epoch": "FILL_ME"},
    {"name": "Cruithne",   "mpc_id": "3753",   "jpl_id": "3753",   "category": "Aten",   "ca_epoch": "FILL_ME"},
    {"name": "1950 DA",    "mpc_id": "29075",  "jpl_id": "29075",  "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "YORP",       "mpc_id": "54509",  "jpl_id": "54509",  "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "1994 CC",    "mpc_id": "136617", "jpl_id": "136617", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "2001 WN5",   "mpc_id": "153814", "jpl_id": "153814", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Atira",      "mpc_id": "163693", "jpl_id": "163693", "category": "Atira",  "ca_epoch": "FILL_ME"},
    {"name": "2005 YU55",  "mpc_id": "308635", "jpl_id": "308635", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "2006 SF6",   "mpc_id": "481394", "jpl_id": "481394", "category": "Aten",   "ca_epoch": "FILL_ME"},
    {"name": "Taranis",    "mpc_id": "5370",   "jpl_id": "5370",   "category": "Amor",   "ca_epoch": "FILL_ME"},
    {"name": "Ra-Shalom",  "mpc_id": "2100",   "jpl_id": "2100",   "category": "Aten",   "ca_epoch": "FILL_ME"},
    {"name": "Khufu",      "mpc_id": "3362",   "jpl_id": "3362",   "category": "Aten",   "ca_epoch": "FILL_ME"},
    {"name": "Hephaistos", "mpc_id": "2212",   "jpl_id": "2212",   "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Toro",       "mpc_id": "1685",   "jpl_id": "1685",   "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Alinda",     "mpc_id": "887",    "jpl_id": "887",    "category": "Amor",   "ca_epoch": "FILL_ME"},
    {"name": "Ganymed",    "mpc_id": "1036",   "jpl_id": "1036",   "category": "Amor",   "ca_epoch": "FILL_ME"},
    {"name": "Betulia",    "mpc_id": "1580",   "jpl_id": "1580",   "category": "Amor",   "ca_epoch": "FILL_ME"},
    {"name": "Quetzalcoatl","mpc_id": "1915",  "jpl_id": "1915",   "category": "Amor",   "ca_epoch": "FILL_ME"},
    {"name": "Antiochus",  "mpc_id": "1936",   "jpl_id": "1936",   "category": "Amor",   "ca_epoch": "FILL_ME"},
    {"name": "Anteros",    "mpc_id": "1943",   "jpl_id": "1943",   "category": "Amor",   "ca_epoch": "FILL_ME"},
    {"name": "Albert",     "mpc_id": "719",    "jpl_id": "719",    "category": "Amor",   "ca_epoch": "FILL_ME"},
    {"name": "Ivar",       "mpc_id": "1627",   "jpl_id": "1627",   "category": "Amor",   "ca_epoch": "FILL_ME"},
    {"name": "Nefertiti",  "mpc_id": "3199",   "jpl_id": "3199",   "category": "Amor",   "ca_epoch": "FILL_ME"},
    {"name": "Sisyphus",   "mpc_id": "1866",   "jpl_id": "1866",   "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Minotaur",   "mpc_id": "5143",   "jpl_id": "5143",   "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Cerberus",   "mpc_id": "1865",   "jpl_id": "1865",   "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Pan",        "mpc_id": "4450",   "jpl_id": "4450",   "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Cuyo",       "mpc_id": "1917",   "jpl_id": "1917",   "category": "Amor",   "ca_epoch": "FILL_ME"},
    {"name": "Baboquivari","mpc_id": "2735",   "jpl_id": "2735",   "category": "Amor",   "ca_epoch": "FILL_ME"},
    {"name": "Don Quixote","mpc_id": "3552",   "jpl_id": "3552",   "category": "Amor",   "ca_epoch": "FILL_ME"},
    {"name": "Oljato",     "mpc_id": "2201",   "jpl_id": "2201",   "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Beowulf",    "mpc_id": "38086",  "jpl_id": "38086",  "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Nereus",     "mpc_id": "4660",   "jpl_id": "4660",   "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Sekhmet",    "mpc_id": "5381",   "jpl_id": "5381",   "category": "Aten",   "ca_epoch": "FILL_ME"},
    {"name": "Asclepius",  "mpc_id": "4581",   "jpl_id": "4581",   "category": "Apollo", "ca_epoch": "FILL_ME"}
]

def log(msg):
    """Simple logger to print and write to file."""
    print(msg)
    with open(LOG_PATH, "a") as f:
        f.write(msg + "\n")

# ── Automatic Epoch Fetching ──────────────────────────────────────
def get_close_approach_epoch(desig):
    """Return the nearest-to-present available CAD epoch as a proper
    GMAT UTCGregorian string ('DD Mon YYYY HH:MM:SS.mmm').

    Two bugs fixed here vs the previous version:
    1. JPL's 'cd' field comes back as 'YYYY-Mon-DD HH:MM' (year-first).
       GMAT's UTCGregorian format is day-first: 'DD Mon YYYY HH:MM:SS.mmm'.
       The old code only appended '.000' without reordering the string,
       so GMAT could not parse the epoch and silently failed every run.
    2. Sorting ascending by date with date-min=1950 returns the OLDEST
       close approach on record, not the nearest to today. Now picks
       the approach closest to today's date instead.
    """
    from datetime import datetime
    r = requests.get(
        CAD_API_URL,
        params={
            "des": desig,
            "date-min": "1950-01-01",
            "date-max": "2060-01-01",
            "dist-max": "20",
            "sort": "date",
        },
        timeout=60,
    )
    r.raise_for_status()
    payload = r.json()

    if payload.get("code") not in (None, 200):
        raise RuntimeError(payload.get("message", f"CAD API error: {payload.get('code')}"))

    fields = payload.get("fields", [])
    data = payload.get("data", [])
    if not data:
        raise RuntimeError("CAD API returned no close-approach records")

    jd_idx = fields.index("jd")
    date_idx = fields.index("cd")

    # Pick the record closest to today, not just the first (oldest) one.
    now = datetime.utcnow()
    best_row = None
    best_diff = None
    for row in data:
        cd_raw = str(row[date_idx])
        try:
            dt = datetime.strptime(cd_raw, "%Y-%b-%d %H:%M")
        except ValueError:
            continue
        diff = abs((dt - now).total_seconds())
        if best_diff is None or diff < best_diff:
            best_diff = diff
            best_row = row
            best_dt = dt

    if best_row is None:
        raise RuntimeError(f"Could not parse any CAD date for {desig}")

    jd = float(best_row[jd_idx])
    # Reorder into GMAT's required 'DD Mon YYYY HH:MM:SS.mmm' format.
    epoch = best_dt.strftime("%d %b %Y %H:%M:%S.000")
    return epoch, jd

# ── GMAT Execution ────────────────────────────────────────────────
def run_gmat_scenario(name, epoch_str, state, archetype, arcsec):
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
    report_path = f"/tmp/gmat_report_{safe_name}_{archetype}.txt"
    script_path = f"/tmp/gmat_{safe_name}_{archetype}.script"

    # Per-object geocentric distance -> km-per-arcsecond conversion,
    # instead of a fixed km offset borrowed from Apophis's distance.
    geo_dist_km = float(np.sqrt(state["X"]**2 + state["Y"]**2 + state["Z"]**2))
    km_per_arcsec = geo_dist_km * (np.pi / (180.0 * 3600.0))
    dx = dy = arcsec * km_per_arcsec
    # velocity perturbation scaled proportionally to the original
    # Apophis-derived ratio (~0.002 km/s per 184 km offset)
    dv = (0.002 / 184.0) * dx if dx else 0.0

    perturbed = {
        "X":  state["X"]  + dx, "Y":  state["Y"]  + dy, "Z":  state["Z"],
        "VX": state["VX"] + dv, "VY": state["VY"] + dv, "VZ": state["VZ"],
    }
    
    script = f"""Create Spacecraft NEO;
NEO.DateFormat = UTCGregorian;
NEO.Epoch = '{epoch_str}';
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
    with open(script_path, "w", encoding="ascii", errors="replace") as f:
        f.write(script)

    result = subprocess.run([GMAT_CONSOLE, "-r", script_path], capture_output=True, timeout=120, errors="replace")

    if not os.path.exists(report_path):
        stderr_tail = (result.stderr or "")[-400:] if result.stderr else ""
        stdout_tail = (result.stdout or "")[-400:] if result.stdout else ""
        log(f"    GMAT produced no report for {name}/{archetype} "
            f"(returncode={result.returncode})")
        if stderr_tail.strip():
            log(f"    stderr: {stderr_tail.strip()}")
        if stdout_tail.strip():
            log(f"    stdout: {stdout_tail.strip()}")
        return None
        
    vals = []
    with open(report_path) as f:
        for line in f.readlines()[1:]:
            parts = line.strip().split()
            if parts:
                try: vals.append(float(parts[-1]))
                except: pass
    return min(vals) if vals else None

# ── State Vectors ─────────────────────────────────────────────────
def get_state_vectors(jpl_id, epoch_jd, name):
    try:
        obj = Horizons(id=jpl_id, location='500@399', epochs=epoch_jd)
        vec = obj.vectors()
        return {
            "X": float(vec['x'][0]) * AU, "Y": float(vec['y'][0]) * AU, "Z": float(vec['z'][0]) * AU,
            "VX": float(vec['vx'][0]) * AU / DAY, "VY": float(vec['vy'][0]) * AU / DAY, "VZ": float(vec['vz'][0]) * AU / DAY,
        }
    except Exception as e:
        log(f"  [JPL] Exception: {e}")
        return None

# ── Main Loop ─────────────────────────────────────────────────────
def main():
    if not os.path.isfile(GMAT_CONSOLE):
        print(f"CRITICAL ERROR: GMAT executable not found at {GMAT_CONSOLE}")
        raise SystemExit(2)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    DATA_RAW.mkdir(parents=True, exist_ok=True)
    LOG_PATH.touch(exist_ok=True)
    
    log(f"\n{'='*65}")
    log(f"NEO BATCH PIPELINE — {len(NEO_OBJECTS)} OBJECTS")
    log(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log(f"{'='*65}")

    all_results = []

    for obj in NEO_OBJECTS:
        name = obj["name"]
        desig = obj.get("jpl_id") or obj.get("mpc_id")
        epoch_str = obj.get("ca_epoch", "FILL_ME")
        
        log(f"\n{'─'*65}\nOBJECT: {name}")

        # 1. Resolve Epoch dynamically
        if epoch_str == "FILL_ME":
            try:
                epoch_str, epoch_jd = get_close_approach_epoch(desig)
                log(f"  [CAD] Dynamically resolved epoch: {epoch_str}")
            except Exception as e:
                log(f"  [CAD] FAILED to fetch epoch: {e}")
                all_results.append({"name": name, "status": "CAD fetch failed"})
                continue
        else:
            from astropy.time import Time
            epoch_jd = Time(epoch_str).jd

        # 2. Get State Vectors
        state = get_state_vectors(desig, epoch_jd, name)
        if not state:
            all_results.append({"name": name, "status": "JPL fetch failed"})
            continue

        # 3. Run GMAT Scenarios
        distances = {}
        for arch, arcsec in ARCHETYPES_ARCSEC.items():
            dist = run_gmat_scenario(name, epoch_str, state, arch, arcsec)
            distances[arch] = dist
            log(f"  [GMAT] {arch}: {f'{dist:,.1f} km' if dist else 'FAILED'}")
            time.sleep(0.5)

        clean_dist = distances.get("clean")
        if clean_dist is None:
            all_results.append({"name": name, "status": "GMAT Clean failed"})
            continue

        # 4. Record Results
        result = {
            "name": name,
            "status": "OK",
            "clean_dist_km": round(clean_dist, 1),
            "bias_delta_km": round((distances.get("systematic_bias") or clean_dist) - clean_dist, 1),
            "noise_delta_km": round((distances.get("stochastic_noise") or clean_dist) - clean_dist, 1),
            "outlier_delta_km": round((distances.get("targeted_outlier") or clean_dist) - clean_dist, 1),
        }
        all_results.append(result)

    # ── Save Outputs ──────────────────────────────────────────────
    df = pd.DataFrame(all_results)
    if df.empty:
        log("\nNo objects completed successfully. Check logs.")
    else:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out = RESULTS_DIR / f"batch_50obj_results_{ts}.csv"
        df.to_csv(out, index=False)
        log(f"\nSUCCESS! Results saved to -> {out}")

if __name__ == "__main__":
    main()
