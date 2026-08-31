"""
Fetches 150 GENUINELY NEW Near-Earth Object designations directly from
JPL's live Small-Body Database Query API, automatically excluding every
object already used across the original 10-object study and the
59-object batch run. No object names are hand-typed or recalled from
memory anywhere in this script — every designation comes straight from
JPL's database at run time, so there is no risk of duplicating or
misremembering a name.

Writes 00_batch_pipeline_150new_objects.py, a full copy of the working,
already-fixed 150-object-capable pipeline (same per-object CAD epoch
resolution, same per-object geocentric-distance offset scaling, same
GMAT execution and diagnostic logging as the version that successfully
completed 48/59 objects), pre-loaded with the new object list.

Run this FIRST, then run the generated pipeline script exactly the way
you ran 00_batch_pipeline_50objects_fixed.py before.

Dissertation / Conference Paper: Integrity Assurance in Planetary Defence
Author: Nithin Yadav Gopinath (C5003001)
MSc Cybersecurity, Sheffield Hallam University
"""

import re
import requests

SBDB_QUERY_URL = "https://ssd-api.jpl.nasa.gov/sbdb_query.api"
TARGET_COUNT = 150

# Every designation already used in the dissertation (10) and the
# 59-object conference-paper batch run, so JPL's live list can be
# filtered against it automatically. Numbers only (JPL 'pdes' field),
# not names, since that's the reliable, unambiguous key.
ALREADY_USED = {
    # Original 10 (dissertation)
    "99942", "101955", "433", "25143", "65803", "3122", "1620",
    "367943", "3200", "2023 BU",
    # 48/59-object conference batch
    "1862", "4179", "162173", "1566", "2062", "1221", "3908", "4769",
    "6489", "2100", "3671", "1685", "5535", "4486", "1580", "4183",
    "3838", "2201", "1863", "3757", "2340", "4581", "385186", "162421",
    "137924", "68950", "152563", "175706", "276033", "469219", "66391",
    "2063", "69230", "3361", "1981", "2101", "29075", "54509", "136617",
    "153814", "308635", "481394", "3362", "2212", "887", "1915", "1943",
    "1627", "1866", "5143", "1865", "4450", "1917", "4660", "5381",
    "3552",  # Don Quixote — failed CAD lookup previously but reserve it anyway
}


def fetch_candidate_neos():
    """
    Pulls numbered NEOs directly from JPL's live SBDB Query API.
    Numbered objects (sb-ns=n) are used because they have stable,
    unambiguous designations, unlike provisional ('2023 XY1'-style)
    designations which are more likely to fail CAD/Horizons lookups.
    """
    params = {
        "fields": "full_name,pdes,neo",
        "sb-group": "neo",
        "sb-ns": "n",   # numbered only
        "sb-kind": "a",  # asteroids only, not comets
    }
    r = requests.get(SBDB_QUERY_URL, params=params, timeout=60)
    r.raise_for_status()
    payload = r.json()

    if "data" not in payload:
        raise RuntimeError(f"Unexpected SBDB response: {payload}")

    fields = payload["fields"]
    full_name_idx = fields.index("full_name")
    pdes_idx = fields.index("pdes")

    candidates = []
    for row in payload["data"]:
        full_name = row[full_name_idx].strip()
        pdes = row[pdes_idx].strip()
        candidates.append((full_name, pdes))

    print(f"JPL returned {len(candidates)} numbered NEOs total.")
    return candidates


def clean_name(full_name):
    """Turns '(1862) Apollo' or '1862 Apollo' into a safe short name."""
    # Strip leading number/parens, keep the actual name
    m = re.search(r"[A-Za-z].*", full_name)
    name = m.group(0).strip() if m else full_name
    # Remove anything that isn't alphanumeric/space for use as an identifier
    name = re.sub(r"[^A-Za-z0-9 ]", "", name).strip()
    return name.replace(" ", "") or f"NEO{full_name.strip()}"


def main():
    candidates = fetch_candidate_neos()

    new_objects = []
    seen_pdes = set()
    for full_name, pdes in candidates:
        if pdes in ALREADY_USED or pdes in seen_pdes:
            continue
        seen_pdes.add(pdes)
        name = clean_name(full_name)
        new_objects.append((name, pdes))
        if len(new_objects) >= TARGET_COUNT:
            break

    print(f"Selected {len(new_objects)} genuinely new objects "
          f"(excluded {len(ALREADY_USED)} already-used designations).")

    if len(new_objects) < TARGET_COUNT:
        print(f"WARNING: only found {len(new_objects)} new objects, "
              f"fewer than the requested {TARGET_COUNT}. JPL's numbered-NEO "
              f"catalogue may be smaller than expected, or too many overlapped "
              f"with ALREADY_USED. Proceeding with what was found.")

    # Build the NEO_OBJECTS list text, matching the exact schema the
    # working pipeline script expects.
    lines = []
    for name, pdes in new_objects:
        lines.append(
            f'    {{"name": "{name}", "mpc_id": "{pdes}", "jpl_id": "{pdes}", '
            f'"category": "Apollo", "ca_epoch": "FILL_ME"}},'
        )
    objects_block = "\n".join(lines)

    # Read the last known-good pipeline script and swap in the new list.
    try:
        with open("00_batch_pipeline_50objects_fixed.py", encoding="utf-8") as f:
            template = f.read()
    except FileNotFoundError:
        raise SystemExit(
            "Could not find 00_batch_pipeline_50objects_fixed.py in this folder. "
            "Copy it into the same directory as this script before running."
        )

    start_marker = "NEO_OBJECTS = ["
    end_marker = "\n]"
    start = template.find(start_marker)
    if start == -1:
        raise SystemExit("Could not find NEO_OBJECTS = [ ... ] in the template script.")
    end = template.find(end_marker, start)
    if end == -1:
        raise SystemExit("Could not find the closing ] of NEO_OBJECTS in the template script.")

    new_template = (
        template[:start]
        + "NEO_OBJECTS = [\n"
        + objects_block
        + template[end:]
    )

    out_path = "00_batch_pipeline_150new_objects.py"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(new_template)

    print(f"\nWrote {out_path} with {len(new_objects)} new objects.")
    print("Run it exactly the way you ran the 50-object version:")
    print(f"  python3 {out_path}")


if __name__ == "__main__":
    main()
