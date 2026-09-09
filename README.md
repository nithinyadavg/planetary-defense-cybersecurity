# Integrity Assurance in Planetary Defence
### An Experimental Cybersecurity Framework for NEO Tracking Pipelines

MSc Dissertation — Cybersecurity and Computer Networks
**Author:** Nithin Yadav Gopinath (C5003001)
**Supervisor:** Dr Sina Pournouri
**Institution:** Sheffield Hallam University

---

## 1. Overview

This project investigates adversarial data-integrity attacks against the
Minor Planet Center (MPC) astrometric pipeline used to track Near-Earth
Objects (NEOs), and quantifies how corrupted observation data propagates
into errors in predicted Close Approach Distance (CAD).

The pipeline:

1. Pulls real astrometric observations from the MPC API (ADES XML format).
2. Applies three adversarial injection archetypes to the observation data.
3. Converts clean and attacked datasets into orbital state vectors via
   JPL Horizons.
4. Propagates each scenario forward in GMAT (General Mission Analysis
   Tool) to the object's close-approach epoch.
5. Compares the resulting minimum Earth distance across scenarios to
   measure how much each attack shifts the predicted orbit.

This has been run both as a focused two-object study (Apophis, Bennu)
and as a wider batch across ~150 additional NEOs to test generality.

---

## 2. Injection Archetypes

| Archetype | Description | Parameters |
|---|---|---|
| **Systematic Bias** | Every observation shifted by the same fixed amount — models a calibration fault or uniform spoofing | 2.0 arcsec, applied to 100% of observations |
| **Stochastic Noise** | Random per-observation jitter — models signal degradation | 1.5 arcsec std, applied to 100% of observations |
| **Targeted Outlier** | A small subset of observations heavily corrupted — models a precise, low-visibility attack | 30 arcsec, 20 observations only |

---

## 3. Repository Structure

```
scripts/
├── setup_mac_&_linux_env.sh           # One-shot environment setup script
├── 01_fetch_apophis_data.py           # Step 1: pull ADES XML from MPC API (Apophis)
├── 01_fetch_bennu_data.py             # Step 1: pull ADES XML from MPC API (Bennu)
├── 02_parse_ades_to_dataframe.py      # Step 2: parse ADES XML -> clean pandas DataFrame
├── 03_injection_module.py             # Step 3: apply the 3 injection archetypes
├── 04_gmat_orbital_impact.py          # Step 4 (v1): GMAT run, heliocentric Keplerian approach
├── 04_gmat_orbital_impact_v2.py       # Step 4 (v2, final): geocentric Cartesian state near CA epoch
├── 05_generate_charts.py              # Chapter 5 figures — dark theme
├── 06_batch_pipeline.py               # End-to-end pipeline for the 10-object study set
├── 07_generate_clean_charts.py        # Chapter 4 figures — clean academic (print) theme
├── chapter4v2_figures.py              # Chapter 4 figures — full 10-object comparison
├── 00_batch_pipeline_50objects_fixed.py   # Batch pipeline, 50+ curated NEOs, dynamic CAD epoch
├── 00_batch_pipeline_150new_objects.py    # Batch pipeline, 150 additional NEOs (generated)
├── 00d_fetch_150_new_objects.py       # Selects 150 NEOs not already used, from live JPL SBDB
├── 00e_fetch_150_nobs.py              # Back-fills MPC observation counts for the 150-object run
├── batch_log.txt                      # Log output from batch pipeline runs
├── batch150_results_with_nobs.csv     # 150-object batch results + observation counts
└── apophis_template.script            # GMAT script template (heliocentric Keplerian)
 
```

---

## 4. Environment Setup

### Requirements
- macOS or Linux (native execution — no VM required)
- Python 3.x with `venv`
- GMAT R2026a
- Network access (MPC API, JPL Horizons/CAD API, PyPI)

### Project Workspace

The setup script expects the project at:

```
$HOME/Demon/GMAT/
```

Adjust `PROJECT_DIR` at the top of `setup_mac_&_linux_env.sh` if your
path differs.

### Quick Start

```bash
chmod +x scripts/setup_mac_&_linux_env.sh
./scripts/setup_mac_&_linux_env.sh
```

This will:
- Detect `python3` on `PATH`
- Remove and recreate a clean `venv/` inside the project workspace
- Upgrade pip and install: `requests`, `pandas`, `numpy`, `matplotlib`,
  `astropy`, `astroquery`
- Verify all imports succeed
- Check for GMAT at `/Applications/GMAT R2026a/bin/GmatConsole`
  (override with `export GMAT_CONSOLE="/path/to/your/GmatConsole"`)

### Every New Terminal Session

```bash
cd "$HOME/Demon/GMAT/"
source venv/bin/activate
which python3      # should resolve to .../venv/bin/python3
```

### GMAT Notes

- GMAT must be installed independently of the Python virtual environment.
- On macOS, missing bundled plugin libraries (Python/MATLAB/proprietary
  interfaces) at startup are expected and harmless — GMAT continues to
  run the core propagation engine without them.
- Report files parsed by the pipeline use whitespace-delimited columns;
  parse with `sep=r'\s+'`, not a fixed multi-space separator, since GMAT's
  column padding is not exactly reproducible.

---

## 5. Pipeline Usage

Run in order from the project root, with the virtual environment active:

```bash
# Step 1 — fetch raw observations
python3 scripts/01_fetch_apophis_data.py
python3 scripts/01_fetch_bennu_data.py

# Step 2 — parse into a clean DataFrame
python3 scripts/02_parse_ades_to_dataframe.py

# Step 3 — generate the three attacked datasets
python3 scripts/03_injection_module.py

# Step 4 — GMAT orbital impact assessment (final geocentric version)
python3 scripts/04_gmat_orbital_impact_v2.py

# Figures
python3 scripts/05_generate_charts.py
python3 scripts/07_generate_clean_charts.py
```

For the wider generality study across additional NEOs:

```bash
python3 scripts/00_batch_pipeline_50objects_fixed.py
python3 scripts/00d_fetch_150_new_objects.py
python3 scripts/00_batch_pipeline_150new_objects.py
python3 scripts/00e_fetch_150_nobs.py
```

Batch runs write timestamped CSVs to `results/` and append progress to
`batch_log.txt`. Many CAD lookups fail for provisional/obscure
designations (no close-approach record in JPL's 1950–2060 window, or
transient SSL errors from the JPL API) — these are logged as
`CAD fetch failed` and skipped rather than halting the run.

---

## 6. Key Results

Two-object headline comparison (geocentric state, CA epoch, per
`04_gmat_orbital_impact_v2.py`). These figures reflect a specific MPC/JPL
data pull and GMAT run — re-fetching observations or state vectors later
(new observations added to MPC, updated JPL solutions, etc.) will shift
these numbers, so treat this table as a snapshot rather than a fixed
reference:

| Scenario | Apophis CAD Δ (km) | Bennu CAD Δ (km) |
|---|---:|---:|
| Systematic Bias (2.0″) | 822.3 | 3,334.6 |
| Stochastic Noise (1.5″) | 428.0 | 1,679.7 |
| Targeted Outlier (30″, 20 obs) | 114.5 | 493.5 |

Bennu (603 observations) shows a consistently larger CAD shift than
Apophis (9,337 observations) for the same injection magnitude —
sparser observation records are more vulnerable per unit of corrupted
data, since each observation carries proportionally more weight in the
orbit determination.

Full ten-object and 150-object study results are in
`chapter4v2_figures.py` / `07_generate_clean_charts.py` and
`batch150_results_with_nobs.csv` respectively.

---

## 7. Known Issues / Fixed Bugs

- **Stale epoch:** early versions propagated from a fixed 2020-01-01
  epoch, accumulating ~103 days of unnecessary integration error before
  reaching the 2029 close approach. Fixed in v2 by starting from a
  geocentric state just before the CA epoch.
- **Placeholder substitution:** an intermediate script version left
  literal `PASTE_X_HERE`-style placeholders in the GMAT template instead
  of the actual JPL Horizons values, which GMAT correctly rejected as
  invalid Real values.
- **Report parsing:** GMAT `ReportFile` output uses variable-width
  whitespace padding, not a fixed separator — use
  `pd.read_csv(path, sep=r'\s+', ...)` or manual line-splitting, not
  `sep='   '` (fixed 3-space).
- **CAD API instability:** the JPL `cad.api` endpoint intermittently
  returns SSL errors under batch load; these are treated as fetch
  failures for that object rather than aborting the whole run.

---

## 8. Author

**Nithin Yadav Gopinath** — C5003001
MSc Cybersecurity and Computer Networks,
_Sheffield Hallam University_

Supervisor:** Dr Sina Pournouri**
