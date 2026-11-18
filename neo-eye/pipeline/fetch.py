#!/usr/bin/env python3
"""
NEO-EYE data pipeline — stage 1: acquisition with provenance.

Pulls only public, legally redistributable sources:
  * NASA/JPL SBDB Query API      — every catalogued near-Earth asteroid and comet (osculating elements + quality fields)
  * NASA/JPL CNEOS CAD API        — close approaches to Earth (past 30 d, next 365 d)
  * NASA/JPL CNEOS Sentry API     — impact-monitoring list
  * NASA/JPL Horizons API         — high-fidelity geocentric flyby tracks for the closest approaches
  * CelesTrak GP data             — active satellites + major debris clouds (OMM/CSV)

Every response is written verbatim into a timestamped "packet" directory together with a
manifest recording URL, UTC fetch time, byte count and SHA-256. A packet is therefore a
traceable, replayable test snapshot: the visualiser can be pointed at any packet.

Usage:  python3 pipeline/fetch.py [--out data/packets] [--horizons-max 60]
Std-lib only (no third-party packages) so it runs anywhere, including GitHub Actions.
"""
import argparse, datetime as dt, hashlib, json, os, sys, time, urllib.parse, urllib.request

UA = "NEO-EYE research pipeline (MSc planetary-defence research; contact via github.com/nithinyadavg)"

SBDB_AST_FIELDS = ("spkid,full_name,pdes,name,prefix,kind,neo,pha,a,e,i,om,w,ma,epoch,H,diameter,albedo,"
                   "moid,condition_code,data_arc,n_obs_used,first_obs,last_obs,class")
SBDB_COM_FIELDS = ("spkid,full_name,pdes,prefix,kind,neo,pha,a,e,i,om,w,ma,tp,epoch,M1,diameter,moid,"
                   "condition_code,data_arc,first_obs,last_obs,class")

SOURCES = {
    "neo_asteroids.json": ("https://ssd-api.jpl.nasa.gov/sbdb_query.api",
                           {"fields": SBDB_AST_FIELDS, "sb-group": "neo", "sb-kind": "a"}),
    "neo_comets.json":    ("https://ssd-api.jpl.nasa.gov/sbdb_query.api",
                           {"fields": SBDB_COM_FIELDS, "sb-group": "neo", "sb-kind": "c"}),
    "cad_future.json":    ("https://ssd-api.jpl.nasa.gov/cad.api",
                           {"dist-max": "0.2", "date-min": "now", "date-max": "+365", "diameter": "true", "fullname": "true"}),
    "cad_past.json":      ("https://ssd-api.jpl.nasa.gov/cad.api",
                           {"dist-max": "0.05", "date-min": "-30", "date-max": "now", "diameter": "true", "fullname": "true"}),
    "sentry.json":        ("https://ssd-api.jpl.nasa.gov/sentry.api", {}),
    "sat_active.csv":     ("https://celestrak.org/NORAD/elements/gp.php", {"GROUP": "active", "FORMAT": "csv"}),
}
for g in ["cosmos-1408-debris", "fengyun-1c-debris", "iridium-33-debris", "cosmos-2251-debris"]:
    SOURCES[f"deb_{g}.csv"] = ("https://celestrak.org/NORAD/elements/gp.php", {"GROUP": g, "FORMAT": "csv"})

HORIZONS = "https://ssd.jpl.nasa.gov/api/horizons.api"


def get(url, params, tries=6, timeout=180):
    full = url + ("?" + urllib.parse.urlencode(params) if params else "")
    last = None
    for n in range(tries):
        try:
            req = urllib.request.Request(full, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                body = r.read()
                if not body:
                    raise IOError("empty body")
                return full, r.status, body
        except Exception as ex:  # network flakiness (CelesTrak resets connections under load)
            last = ex
            time.sleep(3 * (n + 1))
    raise RuntimeError(f"failed after {tries} tries: {full}: {last}")


def record(manifest, outdir, name, url, status, body, note=None):
    path = os.path.join(outdir, name)
    with open(path, "wb") as f:
        f.write(body)
    manifest["files"][name] = {
        "url": url, "http_status": status, "bytes": len(body),
        "sha256": hashlib.sha256(body).hexdigest(),
        "fetched_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        **({"note": note} if note else {}),
    }


def horizons_track(des, jd_ca, half_days=5.0, step="1h"):
    """Geocentric ecliptic J2000 state vectors (au, au/d) around a close approach."""
    t0 = jd_ca - half_days
    t1 = jd_ca + half_days
    params = {
        "format": "json", "COMMAND": (f"'{des};'" if des.isdigit() else f"'DES={des};'"), "EPHEM_TYPE": "VECTORS",
        "CENTER": "'500@399'", "START_TIME": f"'JD{t0:.4f}'", "STOP_TIME": f"'JD{t1:.4f}'",
        "STEP_SIZE": f"'{step}'", "REF_PLANE": "ECLIPTIC", "REF_SYSTEM": "ICRF", "VEC_TABLE": "1",
        "OUT_UNITS": "AU-D", "CSV_FORMAT": "YES", "OBJ_DATA": "NO",
    }
    return get(HORIZONS, params, tries=3, timeout=90)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/packets")
    ap.add_argument("--horizons-max", type=int, default=60, help="max flyby tracks to pull from Horizons")
    ap.add_argument("--horizons-dist", type=float, default=0.05, help="au; CAD threshold for Horizons tracks")
    a = ap.parse_args()

    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    outdir = os.path.join(a.out, stamp)
    os.makedirs(outdir, exist_ok=True)
    manifest = {"packet": stamp, "pipeline": "neo-eye/fetch.py v1", "files": {}, "errors": []}

    for name, (url, params) in SOURCES.items():
        try:
            full, st, body = get(url, params)
            record(manifest, outdir, name, full, st, body)
            print(f"ok   {name:32s} {len(body):>10,d} B", flush=True)
        except Exception as ex:
            manifest["errors"].append({"file": name, "error": str(ex)})
            print(f"FAIL {name}: {ex}", file=sys.stderr, flush=True)
        time.sleep(1.5)

    # Horizons flyby tracks for the closest approaches inside the CAD window
    tracks_dir = os.path.join(outdir, "horizons")
    os.makedirs(tracks_dir, exist_ok=True)
    cands = []
    for f in ("cad_past.json", "cad_future.json"):
        p = os.path.join(outdir, f)
        if not os.path.exists(p):
            continue
        cad = json.load(open(p))
        idx = {k: i for i, k in enumerate(cad["fields"])}
        for row in cad.get("data", []):
            if float(row[idx["dist"]]) <= a.horizons_dist:
                cands.append((float(row[idx["dist"]]), row[idx["des"]], float(row[idx["jd"]])))
    cands.sort()
    seen = set()
    for dist, des, jd in cands:
        if len(seen) >= a.horizons_max:
            break
        if (des, round(jd)) in seen:
            continue
        seen.add((des, round(jd)))
        try:
            full, st, body = horizons_track(des, jd)
            if b"$$SOE" not in body:
                raise RuntimeError("Horizons returned no ephemeris block")
            safe = des.replace(" ", "_").replace("/", "-")
            record(manifest, tracks_dir, f"{safe}_{int(jd)}.json", full, st, body,
                   note=f"CA dist {dist:.5f} au at JD {jd:.4f}")
            manifest["files"][f"horizons/{safe}_{int(jd)}.json"] = manifest["files"].pop(f"{safe}_{int(jd)}.json")
            print(f"ok   horizons {des:20s} {dist:.5f} au", flush=True)
        except Exception as ex:
            manifest["errors"].append({"file": f"horizons/{des}", "error": str(ex)})
            print(f"FAIL horizons {des}: {ex}", file=sys.stderr, flush=True)
        time.sleep(1.0)

    # Packet seal: hash over the sorted per-file hashes
    seal = hashlib.sha256("".join(v["sha256"] for k, v in sorted(manifest["files"].items())).encode()).hexdigest()
    manifest["packet_sha256"] = seal
    with open(os.path.join(outdir, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=1)
    latest = os.path.join(a.out, "LATEST")
    with open(latest, "w") as f:
        f.write(stamp + "\n")
    print(f"packet {stamp} sealed {seal[:16]}… ({len(manifest['files'])} files, {len(manifest['errors'])} errors)")


if __name__ == "__main__":
    main()
