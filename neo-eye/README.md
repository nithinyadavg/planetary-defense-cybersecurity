# NEO·EYE — Near-Earth Objects · Early-warning, Yield & Exposure
*by NYG — Nithin Yadav Gopinath*

- **Early-warning** — what is coming close, and when (JPL CAD, Sentry, Horizons flybys)
- **Yield** — impact energy if an object hit Earth (sphere of rock, 2,600 kg/m³; v from v∞ + escape speed)
- **Exposure** — how close Earth and its satellite shells come to it

Near-Earth space situational awareness: every catalogued near-Earth asteroid and comet, the
active satellite catalogue and major debris clouds, real flyby trajectories, and a modelled
stand-in for the population not yet discovered — in one Earth-centred (or Sun-centred) 3D view.

Part of the *Integrity Assurance in Planetary Defence* research line (MSc dissertation / ICGS3-26).
**Live viewer:** https://nithinyadavg.github.io/planetary-defense-cybersecurity/ (refreshed every 6 h)

## Layout
```
pipeline/fetch.py   stage 1 — acquire public data, write a hash-sealed "packet" (std-lib only)
pipeline/build.py   stage 2 — compile a packet into compact web data (+ SHA-256 of each derived file)
web/                static viewer (three.js, satellite.js, astronomy-engine via CDN)
  js/app.js         renderer, GPU two-body propagation, SGP4, UI
  js/population.js  modelled undiscovered population (documented, seeded, clearly labelled)
../.github/workflows/neo-eye-pages.yml   fetch → build → deploy to GitHub Pages every 6 h
```

## Sources (all public)
| Source | What | Notes |
|---|---|---|
| JPL SBDB Query API | ~43k NEAs + NECs, osculating elements, H, U, arc, n_obs, MOID | heliocentric ecliptic J2000 |
| JPL CNEOS CAD API | close approaches, −30 d … +365 d, ≤ 0.2 au | authoritative miss distances |
| JPL CNEOS Sentry API | impact-monitoring list | IP, Palermo, Torino |
| JPL Horizons API | geocentric ecliptic vectors, 1 h step, ±5 d, for every CA ≤ 0.05 au | flyby tracks |
| CelesTrak GP | active satellites + COSMOS-1408, COSMOS-2251, FENGYUN-1C, IRIDIUM-33 debris | SGP4 in-browser |
| Natural Earth 1:110m | coastlines | public domain |

## Run locally (no install, ~25 MB disk)
```
python3 pipeline/fetch.py && python3 pipeline/build.py
cd web && python3 -m http.server 8000   # from inside neo-eye/      # open http://localhost:8000
```
Disk: one packet ≈ 12 MB raw, web/data ≈ 10 MB.

## Accuracy budget (be explicit in any write-up)
* Asteroid positions in the viewer are **two-body Keplerian** from the SBDB osculating epoch — visual only.
  Checked against Horizons on 2026-11-18: Apophis 62,700 km, Eros 84,200 km, 2024 YR4 58,800 km
  after 162 d; Bennu 417,000 km (elements epoch 5,800 d old).
* Close-approach distances shown are JPL CAD values; flyby tracks are Horizons n-body ephemerides.
* Satellites: SGP4 on CelesTrak GP elements (TEME treated as equatorial-of-date ≈ J2000 for display).
* Modelled population: log-linear N(<H) through N(H<17.75)=964 (Deienno+25) and N(H<22)=22,800
  (mean of NEOMOD, Harris & Chodas 2021, Grav+23), extrapolated to H 24; orbits resampled from known
  H<20 objects. Illustrative, not predictive.

## Integrity lens
Colours every object by JPL orbit-uncertainty parameter U (0–9). In the 2026-11-18 packet,
over half (52 %) of catalogued NEAs have U ≥ 7 — the catalogue itself is a data-integrity problem.
