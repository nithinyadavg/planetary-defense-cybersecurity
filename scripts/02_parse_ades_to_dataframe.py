"""
Objective 1 — Step 2: ADES Parsing
Parses the raw ADES XML downloaded from the MPC API into a clean
pandas DataFrame with one row per observation, containing the fields
needed for the adversarial injection module (Step 3).

Dissertation: Integrity Assurance in Planetary Defense
Author: Nithin Yadav Gopinath (C5003001)
"""

import os
import glob
import xml.etree.ElementTree as ET
import pandas as pd
from datetime import datetime

RAW_DATA_DIR = "data/raw"
PROCESSED_DIR = "data/processed"


def find_latest_ades_xml():
    """Finds the most recently saved ADES XML file in data/raw."""
    pattern = os.path.join(RAW_DATA_DIR, "apophis_ades_*.xml")
    files = glob.glob(pattern)
    if not files:
        raise FileNotFoundError(
            f"No ADES XML files found in {RAW_DATA_DIR}. "
            "Run 01_fetch_apophis_data.py first."
        )
    latest = max(files, key=os.path.getmtime)
    print(f"Using ADES file: {latest}")
    return latest


def parse_ades_xml(xml_path):
    """
    Parses an ADES XML file and extracts one record per <optical>
    observation block. Returns a list of dicts.

    ADES XML structure (relevant fields):
        <optical>
            <permID>99942</permID>
            <provID>2004 MN4</provID>
            <trkSub>K04M04N</trkSub>
            <obsTime>2004-03-15T02:35:21.696Z</obsTime>
            <ra>61.53367</ra>
            <dec>16.91794</dec>
            <mag>...</mag>          (optional)
            <band>...</band>        (optional)
            <stn>691</stn>
            <astCat>USNOB1</astCat>
        </optical>
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()

    records = []
    # ADES XML has no namespace prefix in this export, so plain tags work
    for optical in root.iter("optical"):
        def get_text(tag):
            el = optical.find(tag)
            return el.text.strip() if el is not None and el.text else None

        record = {
            "permID": get_text("permID"),
            "provID": get_text("provID"),
            "trkSub": get_text("trkSub"),
            "obsTime": get_text("obsTime"),
            "ra_deg": get_text("ra"),
            "dec_deg": get_text("dec"),
            "mag": get_text("mag"),
            "band": get_text("band"),
            "station": get_text("stn"),
            "astCat": get_text("astCat"),
            "mode": get_text("mode"),
        }
        records.append(record)

    print(f"Parsed {len(records)} observation records")
    return records


def build_dataframe(records):
    """Converts parsed records into a typed, sorted pandas DataFrame."""
    df = pd.DataFrame(records)

    # Convert types
    df["obsTime"] = pd.to_datetime(df["obsTime"], errors="coerce", utc=True)
    df["ra_deg"] = pd.to_numeric(df["ra_deg"], errors="coerce")
    df["dec_deg"] = pd.to_numeric(df["dec_deg"], errors="coerce")
    df["mag"] = pd.to_numeric(df["mag"], errors="coerce")

    # Drop rows with missing core fields (no usable RA/Dec/time)
    before = len(df)
    df = df.dropna(subset=["obsTime", "ra_deg", "dec_deg"])
    after = len(df)
    if before != after:
        print(f"Dropped {before - after} incomplete rows (missing RA/Dec/time)")

    # Sort chronologically — important for tracklet-level analysis later
    df = df.sort_values("obsTime").reset_index(drop=True)

    # Add a simple sequential observation index — useful for referencing
    # specific observations when building injection scenarios
    df.insert(0, "obs_index", range(len(df)))

    return df


def save_processed(df):
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    csv_path = os.path.join(PROCESSED_DIR, f"apophis_clean_{timestamp}.csv")
    df.to_csv(csv_path, index=False)
    print(f"Saved clean CSV -> {csv_path}")

    # Also save as a pickle so dtypes (esp. datetime) are preserved exactly
    # for the next script (the injection module) without re-parsing
    pkl_path = os.path.join(PROCESSED_DIR, f"apophis_clean_{timestamp}.pkl")
    df.to_pickle(pkl_path)
    print(f"Saved pickle    -> {pkl_path}")

    return csv_path, pkl_path


def summarise(df):
    print("\n--- Dataset summary ---")
    print(f"Total observations : {len(df)}")
    print(f"Date range          : {df['obsTime'].min()}  to  {df['obsTime'].max()}")
    print(f"RA range (deg)      : {df['ra_deg'].min():.5f}  to  {df['ra_deg'].max():.5f}")
    print(f"Dec range (deg)     : {df['dec_deg'].min():.5f}  to  {df['dec_deg'].max():.5f}")
    print(f"Unique stations     : {df['station'].nunique()}")
    print(f"Unique trkSub groups: {df['trkSub'].nunique()}")
    print("\n--- First 5 rows ---")
    print(df[["obs_index", "obsTime", "ra_deg", "dec_deg", "station"]].head())


if __name__ == "__main__":
    xml_path = find_latest_ades_xml()
    records = parse_ades_xml(xml_path)
    df = build_dataframe(records)
    summarise(df)
    save_processed(df)
    print("\nDone. Clean DataFrame ready for the injection module (Step 3).")
