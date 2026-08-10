"""
Objective 1 — Step 1: Data Collection
Pulls real astrometric observation data for (99942) Apophis from the
Minor Planet Center (MPC) Observations API in ADES XML format.

Dissertation: Integrity Assurance in Planetary Defense
Author: Nithin Yadav Gopinath (C5003001)
"""

import requests
import json
import os
from datetime import datetime

# ── Configuration ─────────────────────────────────────────────────
MPC_API_URL = "https://data.minorplanetcenter.net/api/get-obs"
TARGET_OBJECT = "101955"  # Apophis — using permanent designation number
OUTPUT_DIR = "data/raw"


def fetch_apophis_observations():
    """
    Sends a GET request to the MPC Observations API requesting
    ADES XML and OBS80 formats for Apophis.
    """
    print(f"Requesting observation data for object: {TARGET_OBJECT}")

    payload = {
        "desigs": [TARGET_OBJECT],
        "output_format": ["XML", "OBS80"]
    }

    response = requests.get(MPC_API_URL, json=payload)

    if not response.ok:
        print(f"ERROR: Request failed with status {response.status_code}")
        print(response.content)
        return None

    data = response.json()
    print(f"Success — received response for {len(data)} object(s)")
    return data


def save_raw_data(data):
    """
    Saves the raw XML and OBS80 outputs to the data/raw directory
    for later parsing by the ADES synthesis script.
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # The API returns a list with one dict per requested designation
    record = data[0]

    # Save the ADES XML
    xml_content = record.get("XML")
    if xml_content:
        xml_path = os.path.join(OUTPUT_DIR, f"apophis_ades_{timestamp}.xml")
        with open(xml_path, "w") as f:
            f.write(xml_content)
        print(f"Saved ADES XML  -> {xml_path}")
    else:
        print("WARNING: No XML data returned for this object")

    # Save the OBS80 raw string (legacy 80-column format, useful for
    # cross-validation against the ADES parse)
    obs80_content = record.get("OBS80")
    if obs80_content:
        obs80_path = os.path.join(OUTPUT_DIR, f"apophis_obs80_{timestamp}.txt")
        with open(obs80_path, "w") as f:
            f.write(obs80_content)
        print(f"Saved OBS80 text -> {obs80_path}")
    else:
        print("WARNING: No OBS80 data returned for this object")

    # Save the full raw JSON response too, for safety/reproducibility
    json_path = os.path.join(OUTPUT_DIR, f"apophis_raw_response_{timestamp}.json")
    with open(json_path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Saved raw JSON   -> {json_path}")

    return xml_path if xml_content else None


def quick_preview(xml_path, n_chars=600):
    """Prints the first chunk of the saved XML so you can visually
    confirm real data came back."""
    if not xml_path:
        return
    print("\n--- Preview of saved ADES XML ---")
    with open(xml_path, "r") as f:
        content = f.read()
    print(content[:n_chars])
    print("...\n")
    print(f"Total file length: {len(content)} characters")


if __name__ == "__main__":
    data = fetch_apophis_observations()
    if data:
        xml_path = save_raw_data(data)
        quick_preview(xml_path)
        print("\nDone. Real Apophis observation data is now saved locally.")
    else:
        print("\nNo data retrieved — check your internet connection or the API status.")
