"""
Fetches real MPC observation counts for the 83 objects that completed
successfully in the 150-object batch run, using the real designations
recovered from 00_batch_pipeline_150new_objects.py's NEO_OBJECTS list
(not guessed from the mangled display names in the results CSV).

Merges the counts into a combined results file ready for the density/
geometry analysis, matching the same approach used for the original
48-object set.

Dissertation / Conference Paper: Integrity Assurance in Planetary Defence
Author: Nithin Yadav Gopinath (C5003001)
MSc Cybersecurity, Sheffield Hallam University
"""

import os
import re
import time
import requests
import pandas as pd

import glob

MPC_API_URL = "https://data.minorplanetcenter.net/api/get-obs"
RESULTS_CSV_PATTERN = "batch_50obj_results_*.csv"  # the actual filename
                                                     # pattern your pipeline
                                                     # script writes
PIPELINE_SCRIPT_NAME = "00_batch_pipeline_150new_objects.py"
OUT_CSV = "batch150_results_with_nobs.csv"


def find_file(filename):
    """Searches upward and downward from the current directory for the
    named file, so this script works no matter which folder you run it
    from — the project root, results/, or any subfolder. Walks up to
    3 levels above the current directory, then searches that whole
    subtree, so a file sitting in a sibling or parent folder is found
    either way."""
    start = os.path.abspath(".")
    for _ in range(3):
        parent = os.path.dirname(start)
        if parent == start:  # hit filesystem root
            break
        start = parent

    for root, dirs, files in os.walk(start):
        dirs[:] = [d for d in dirs if d not in ("venv", ".git") and not d.startswith(".")]
        if filename in files:
            return os.path.join(root, filename)
    raise FileNotFoundError(
        f"Could not find '{filename}' anywhere near the current directory "
        f"(searched from {start} downward). Make sure the file exists "
        f"somewhere under that folder."
    )


def recover_name_to_designation():
    """Pulls the real name -> MPC designation mapping directly from the
    generated pipeline script, not from the (possibly mangled) results CSV.
    Detects and excludes any name that maps to more than one designation —
    the name-cleaning step that generated this file can occasionally
    collapse two different objects to the same short name (e.g. two
    different provisional designations both cleaning down to 'VA'), and
    merging observation counts by an ambiguous name would silently
    attach the wrong count to one of them. Ambiguous names are dropped
    rather than guessed."""
    path = find_file(PIPELINE_SCRIPT_NAME)
    with open(path, encoding="utf-8") as f:
        text = f.read()
    start = text.find("NEO_OBJECTS = [")
    end = text.find("\n]", start)
    block = text[start:end]
    entries = re.findall(r'"name": "([^"]*)", "mpc_id": "([^"]+)"', block)

    from collections import defaultdict
    by_name = defaultdict(set)
    for name, desig in entries:
        by_name[name].add(desig)

    ambiguous = {name: desigs for name, desigs in by_name.items() if len(desigs) > 1}
    if ambiguous:
        print(f"WARNING: {len(ambiguous)} name(s) map to more than one designation "
              f"— excluding these from the merge rather than guessing which is which:")
        for name, desigs in ambiguous.items():
            print(f"    '{name}' -> {sorted(desigs)}")

    clean_mapping = {name: next(iter(desigs)) for name, desigs in by_name.items()
                      if len(desigs) == 1}
    return clean_mapping, set(ambiguous.keys())


def fetch_n_obs(desig):
    r = requests.get(
        MPC_API_URL,
        json={"desigs": [desig], "output_format": ["XML"]},
        timeout=60,
    )
    if not r.ok:
        return None
    data = r.json()
    if not data or "XML" not in data[0] or not data[0]["XML"]:
        return None
    return data[0]["XML"].count("<optical>")


def find_latest_results_csv():
    """Finds every batch_50obj_results_*.csv near the current directory
    (same up-and-down search as find_file) and returns the most
    recently modified one, so you don't have to know or type the exact
    timestamped filename."""
    start = os.path.abspath(".")
    for _ in range(3):
        parent = os.path.dirname(start)
        if parent == start:
            break
        start = parent

    matches = []
    for root, dirs, files in os.walk(start):
        dirs[:] = [d for d in dirs if d not in ("venv", ".git") and not d.startswith(".")]
        for f in files:
            if re.fullmatch(r"batch_50obj_results_.*\.csv", f):
                full = os.path.join(root, f)
                matches.append((os.path.getmtime(full), full))

    if not matches:
        raise FileNotFoundError(
            f"Could not find any file matching '{RESULTS_CSV_PATTERN}' "
            f"anywhere near the current directory (searched from {start})."
        )
    matches.sort()
    latest = matches[-1][1]
    if len(matches) > 1:
        print(f"Found {len(matches)} results files -- using the most recent: {latest}")
    return latest


def main():
    name_to_desig, ambiguous_names = recover_name_to_designation()
    print(f"Recovered {len(name_to_desig)} unambiguous real designations "
          f"from {PIPELINE_SCRIPT_NAME}.")

    results_path = find_latest_results_csv()
    print(f"Using results file: {results_path}")

    # keep_default_na=False stops pandas from turning the literal
    # object name "NA" into a missing value, which is what happened
    # in the first pass of this exact dataset.
    df = pd.read_csv(results_path, keep_default_na=False, na_values=[""])

    n_obs_col = []
    excluded_ambiguous = 0
    for _, row in df.iterrows():
        name = row["name"]
        if row.get("status") != "OK":
            n_obs_col.append(None)
            continue
        if name in ambiguous_names:
            n_obs_col.append(None)
            excluded_ambiguous += 1
            continue
        desig = name_to_desig.get(name)
        if not desig:
            print(f"  WARNING: no recovered designation for '{name}' — skipping")
            n_obs_col.append(None)
            continue
        n = fetch_n_obs(desig)
        print(f"  {name:22s} ({desig:>7s}) -> {n} observations" if n is not None
              else f"  {name:22s} ({desig:>7s}) -> FETCH FAILED")
        n_obs_col.append(n)
        time.sleep(1)  # be polite to the MPC API

    df["n_observations"] = n_obs_col
    df.to_csv(OUT_CSV, index=False)
    print(f"\nSaved -> {OUT_CSV}")

    if excluded_ambiguous:
        print(f"Excluded {excluded_ambiguous} row(s) with ambiguous names "
              f"(real GMAT results kept in the CSV with a blank n_observations, "
              f"so they're visibly excluded rather than silently dropped).")

    missing = df[(df["status"] == "OK") & (df["n_observations"].isna())]
    if len(missing):
        print(f"\n{len(missing)} OK objects have no n_observations "
              f"(ambiguous name exclusions + any fetch failures):")
        print(missing["name"].tolist())


if __name__ == "__main__":
    main()
