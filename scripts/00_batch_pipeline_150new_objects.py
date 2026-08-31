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
    {"name": "AlbertA911TB", "mpc_id": "719", "jpl_id": "719", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "GanymedA924UB", "mpc_id": "1036", "jpl_id": "1036", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Daedalus1971FA", "mpc_id": "1864", "jpl_id": "1864", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Boreas1953RA", "mpc_id": "1916", "jpl_id": "1916", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Tezcatlipoca1950LA", "mpc_id": "1980", "jpl_id": "1980", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Baboquivari1963UA", "mpc_id": "2059", "jpl_id": "2059", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Anza1960UA", "mpc_id": "2061", "jpl_id": "2061", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Tantalus1975YA", "mpc_id": "2102", "jpl_id": "2102", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Aristaeus1977HA", "mpc_id": "2135", "jpl_id": "2135", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Pele1972RA", "mpc_id": "2202", "jpl_id": "2202", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Orthos1976WA", "mpc_id": "2329", "jpl_id": "2329", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Beltrovata1977RA", "mpc_id": "2368", "jpl_id": "2368", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Seneca1978DA", "mpc_id": "2608", "jpl_id": "2608", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Krok1981QA", "mpc_id": "3102", "jpl_id": "3102", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Eger1982BB", "mpc_id": "3103", "jpl_id": "3103", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Nefertiti1982RA", "mpc_id": "3199", "jpl_id": "3199", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Ul1982RB", "mpc_id": "3271", "jpl_id": "3271", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Seleucus1982DV", "mpc_id": "3288", "jpl_id": "3288", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "McAuliffe1981CW", "mpc_id": "3352", "jpl_id": "3352", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Syrinx1981VA", "mpc_id": "3360", "jpl_id": "3360", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Verenia1983RD", "mpc_id": "3551", "jpl_id": "3551", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Mera1985JA", "mpc_id": "3553", "jpl_id": "3553", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Amun1986EB", "mpc_id": "3554", "jpl_id": "3554", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Bede1982FT", "mpc_id": "3691", "jpl_id": "3691", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Camillo1985PA", "mpc_id": "3752", "jpl_id": "3752", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Cruithne1986TO", "mpc_id": "3753", "jpl_id": "3753", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Huma1986LA", "mpc_id": "3988", "jpl_id": "3988", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "WilsonHarrington1979VA", "mpc_id": "4015", "jpl_id": "4015", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Vishnu1986PA", "mpc_id": "4034", "jpl_id": "4034", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Magellan1985DO2", "mpc_id": "4055", "jpl_id": "4055", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Morpheus1982TA", "mpc_id": "4197", "jpl_id": "4197", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Ubasti1987QA", "mpc_id": "4257", "jpl_id": "4257", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Poseidon1987KF", "mpc_id": "4341", "jpl_id": "4341", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Aditi1985TB", "mpc_id": "4401", "jpl_id": "4401", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Pocahontas1987UA", "mpc_id": "4487", "jpl_id": "4487", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Cleobulus1989WM", "mpc_id": "4503", "jpl_id": "4503", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Xanthus1989FB", "mpc_id": "4544", "jpl_id": "4544", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "QB", "mpc_id": "4596", "jpl_id": "4596", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "WF", "mpc_id": "4688", "jpl_id": "4688", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Ninkasi1988TJ1", "mpc_id": "4947", "jpl_id": "4947", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "MU", "mpc_id": "4953", "jpl_id": "4953", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Eric1990SQ", "mpc_id": "4954", "jpl_id": "4954", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Brucemurray1990XJ", "mpc_id": "4957", "jpl_id": "4957", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Ptah6743PL", "mpc_id": "5011", "jpl_id": "5011", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "BG", "mpc_id": "5131", "jpl_id": "5131", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "UQ", "mpc_id": "5189", "jpl_id": "5189", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Lyapunov1987SL", "mpc_id": "5324", "jpl_id": "5324", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Davidaguilar1990DA", "mpc_id": "5332", "jpl_id": "5332", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Taranis1986RA", "mpc_id": "5370", "jpl_id": "5370", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "NA", "mpc_id": "5496", "jpl_id": "5496", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "SB", "mpc_id": "5587", "jpl_id": "5587", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "VA", "mpc_id": "5590", "jpl_id": "5590", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "FE", "mpc_id": "5604", "jpl_id": "5604", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Jasonwheeler1990OA", "mpc_id": "5620", "jpl_id": "5620", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Melissabrucker1991FE", "mpc_id": "5626", "jpl_id": "5626", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "SP", "mpc_id": "5645", "jpl_id": "5645", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "TR", "mpc_id": "5646", "jpl_id": "5646", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Camarillo1992WD5", "mpc_id": "5653", "jpl_id": "5653", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "MA", "mpc_id": "5660", "jpl_id": "5660", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "EA", "mpc_id": "5693", "jpl_id": "5693", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Zeus1988VP4", "mpc_id": "5731", "jpl_id": "5731", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Zao1992AC", "mpc_id": "5751", "jpl_id": "5751", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Talos1991RC", "mpc_id": "5786", "jpl_id": "5786", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Bivoj1980AA", "mpc_id": "5797", "jpl_id": "5797", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "AM", "mpc_id": "5828", "jpl_id": "5828", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "MF", "mpc_id": "5836", "jpl_id": "5836", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Tara1983RB", "mpc_id": "5863", "jpl_id": "5863", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Tanith1988VN4", "mpc_id": "5869", "jpl_id": "5869", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Almeria1992CH1", "mpc_id": "5879", "jpl_id": "5879", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "EG", "mpc_id": "6037", "jpl_id": "6037", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "TB1", "mpc_id": "6047", "jpl_id": "6047", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Miwablock1992AE", "mpc_id": "6050", "jpl_id": "6050", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "BW3", "mpc_id": "6053", "jpl_id": "6053", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Jason1984KB", "mpc_id": "6063", "jpl_id": "6063", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "DA", "mpc_id": "6178", "jpl_id": "6178", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Minos1989QF", "mpc_id": "6239", "jpl_id": "6239", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "HE", "mpc_id": "6455", "jpl_id": "6455", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Golombek1992OM", "mpc_id": "6456", "jpl_id": "6456", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "OA", "mpc_id": "6491", "jpl_id": "6491", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Ondaatje1993MO", "mpc_id": "6569", "jpl_id": "6569", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "VW", "mpc_id": "6611", "jpl_id": "6611", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "QA", "mpc_id": "7025", "jpl_id": "7025", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Ishtar1992AA", "mpc_id": "7088", "jpl_id": "7088", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Cadmus1992LC", "mpc_id": "7092", "jpl_id": "7092", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "PA", "mpc_id": "7236", "jpl_id": "7236", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "JA", "mpc_id": "7335", "jpl_id": "7335", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Saunders1989RS1", "mpc_id": "7336", "jpl_id": "7336", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "VK", "mpc_id": "7341", "jpl_id": "7341", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "VA", "mpc_id": "7350", "jpl_id": "7350", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Oze1995YA3", "mpc_id": "7358", "jpl_id": "7358", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "TC", "mpc_id": "7474", "jpl_id": "7474", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Norwan1994PC", "mpc_id": "7480", "jpl_id": "7480", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "PC1", "mpc_id": "7482", "jpl_id": "7482", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "XB", "mpc_id": "7753", "jpl_id": "7753", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "CS", "mpc_id": "7822", "jpl_id": "7822", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "ND", "mpc_id": "7839", "jpl_id": "7839", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "UC", "mpc_id": "7888", "jpl_id": "7888", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "LX", "mpc_id": "7889", "jpl_id": "7889", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "QQ5", "mpc_id": "7977", "jpl_id": "7977", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Gordonmoore1990KA", "mpc_id": "8013", "jpl_id": "8013", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "MF", "mpc_id": "8014", "jpl_id": "8014", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Akka1992LR", "mpc_id": "8034", "jpl_id": "8034", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "TB", "mpc_id": "8035", "jpl_id": "8035", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "HO1", "mpc_id": "8037", "jpl_id": "8037", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "WA", "mpc_id": "8176", "jpl_id": "8176", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "AH2", "mpc_id": "8201", "jpl_id": "8201", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "CB1", "mpc_id": "8507", "jpl_id": "8507", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "EN", "mpc_id": "8566", "jpl_id": "8566", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "HW1", "mpc_id": "8567", "jpl_id": "8567", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Kadlu1994JF1", "mpc_id": "8709", "jpl_id": "8709", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "JB", "mpc_id": "9058", "jpl_id": "9058", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Kwiila1987OA", "mpc_id": "9162", "jpl_id": "9162", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Abhramu1989OB", "mpc_id": "9172", "jpl_id": "9172", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "PB", "mpc_id": "9202", "jpl_id": "9202", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "TW1", "mpc_id": "9400", "jpl_id": "9400", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "EE", "mpc_id": "9856", "jpl_id": "9856", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "ESA1990VB", "mpc_id": "9950", "jpl_id": "9950", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "SK", "mpc_id": "10115", "jpl_id": "10115", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "CK1", "mpc_id": "10145", "jpl_id": "10145", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "PN", "mpc_id": "10150", "jpl_id": "10150", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "BL2", "mpc_id": "10165", "jpl_id": "10165", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "ML", "mpc_id": "10302", "jpl_id": "10302", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Izhdubar1993WD", "mpc_id": "10563", "jpl_id": "10563", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "QK56", "mpc_id": "10636", "jpl_id": "10636", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "LE", "mpc_id": "10860", "jpl_id": "10860", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "FA", "mpc_id": "11054", "jpl_id": "11054", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Sigurd1992CC1", "mpc_id": "11066", "jpl_id": "11066", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Belenus1990BA", "mpc_id": "11284", "jpl_id": "11284", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Peleus1993XN2", "mpc_id": "11311", "jpl_id": "11311", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "YP11", "mpc_id": "11398", "jpl_id": "11398", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "CV3", "mpc_id": "11405", "jpl_id": "11405", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Tomaiyowit1989UR", "mpc_id": "11500", "jpl_id": "11500", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Summanus1990SS", "mpc_id": "11885", "jpl_id": "11885", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "OH", "mpc_id": "12538", "jpl_id": "12538", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Tukmit1991BB", "mpc_id": "12711", "jpl_id": "12711", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Zephyr1999GK4", "mpc_id": "12923", "jpl_id": "12923", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Masaakikoyama1992JE", "mpc_id": "13553", "jpl_id": "13553", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "BR", "mpc_id": "13651", "jpl_id": "13651", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "DB", "mpc_id": "14402", "jpl_id": "14402", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Hypnos1986JK", "mpc_id": "14827", "jpl_id": "14827", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Yuliya1991PM5", "mpc_id": "15745", "jpl_id": "15745", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Lucianotesi1994QC", "mpc_id": "15817", "jpl_id": "15817", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Davidharvey1999RH27", "mpc_id": "16064", "jpl_id": "16064", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "QP", "mpc_id": "16636", "jpl_id": "16636", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "UB", "mpc_id": "16657", "jpl_id": "16657", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "UF9", "mpc_id": "16816", "jpl_id": "16816", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "WU22", "mpc_id": "16834", "jpl_id": "16834", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "Rhiannon1998EP8", "mpc_id": "16912", "jpl_id": "16912", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "QS52", "mpc_id": "16960", "jpl_id": "16960", "category": "Apollo", "ca_epoch": "FILL_ME"},
    {"name": "UM3", "mpc_id": "17181", "jpl_id": "17181", "category": "Apollo", "ca_epoch": "FILL_ME"},
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
