#!/usr/bin/env python3
"""
NEO-EYE data pipeline — stage 2: compile a packet into compact web data.

Reads   data/packets/<stamp>/   (verbatim API responses + manifest)
Writes  web/data/{neo,sats,cad,sentry,tracks,manifest}.json

Nothing is invented here: values are re-shaped and rounded only. The modelled
(undiscovered) population is generated client-side from documented parameters
in web/js/population.js so that real and modelled objects can never be confused.
"""
import csv, glob, hashlib, json, math, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PK = os.path.join(ROOT, "data", "packets")
OUT = os.path.join(ROOT, "web", "data")
GM_DEG = 0.9856076686  # Gaussian gravitational constant k in deg/day (n = k / a^1.5)

CLASS_CODES = {"ATE": 1, "APO": 2, "AMO": 3, "IEO": 4, "JFc": 5, "HTC": 6, "ETc": 7, "CTc": 8, "PAR": 9, "HYP": 9, "COM": 8}


def f(x, nd=6):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    if math.isnan(v):
        return None
    return round(v, nd)


def sbdb_rows(path):
    d = json.load(open(path))
    flds = d["fields"]
    for r in d["data"]:
        yield dict(zip(flds, r))


def short_name(row):
    fn = (row.get("full_name") or "").strip()
    return fn


def build_neo(P, sentry_ids):
    cols = {k: [] for k in ["name", "pdes", "a", "e", "i", "om", "w", "ma", "ep", "H", "D", "U", "pha", "sen", "cls", "moid", "arc", "nobs", "kind", "last"]}
    skipped = 0
    for kind, fn in (("a", "neo_asteroids.json"), ("c", "neo_comets.json")):
        p = os.path.join(P, fn)
        if not os.path.exists(p):
            continue
        for r in sbdb_rows(p):
            a, e = f(r.get("a")), f(r.get("e"))
            if a is None or e is None or e >= 1 or a <= 0:
                skipped += 1  # hyperbolic/parabolic or missing elements
                continue
            ep = f(r.get("epoch"), 2)
            ma = f(r.get("ma"), 4)
            if ma is None and r.get("tp") is not None and ep is not None:
                n = GM_DEG / a ** 1.5
                ma = round(((n * (ep - float(r["tp"]))) % 360 + 360) % 360, 4)
            if ma is None or ep is None:
                skipped += 1
                continue
            pdes = (r.get("pdes") or "").strip()
            cols["name"].append(short_name(r))
            cols["pdes"].append(pdes)
            cols["a"].append(f(a, 6)); cols["e"].append(f(e, 6))
            cols["i"].append(f(r.get("i"), 4)); cols["om"].append(f(r.get("om"), 4)); cols["w"].append(f(r.get("w"), 4))
            cols["ma"].append(ma); cols["ep"].append(ep)
            H = f(r.get("H"), 2) if kind == "a" else f(r.get("M1"), 2)
            cols["H"].append(H)
            cols["D"].append(f(r.get("diameter"), 3))
            cu = r.get("condition_code")
            cols["U"].append(int(cu) if cu not in (None, "", "D", "E") and str(cu).isdigit() else -1)
            cols["pha"].append(1 if r.get("pha") == "Y" else 0)
            cols["sen"].append(1 if pdes in sentry_ids else 0)
            cols["cls"].append(CLASS_CODES.get(r.get("class"), 0))
            cols["moid"].append(f(r.get("moid"), 5))
            cols["arc"].append(int(float(r["data_arc"])) if r.get("data_arc") not in (None, "") else None)
            cols["nobs"].append(int(r["n_obs_used"]) if r.get("n_obs_used") not in (None, "") else None)
            cols["kind"].append(kind)
            cols["last"].append(r.get("last_obs"))
    print(f"neo: {len(cols['a'])} objects ({skipped} skipped: unbound or incomplete)")
    return cols


def build_sats(P):
    keep = ["OBJECT_NAME", "OBJECT_ID", "EPOCH", "MEAN_MOTION", "ECCENTRICITY", "INCLINATION", "RA_OF_ASC_NODE",
            "ARG_OF_PERICENTER", "MEAN_ANOMALY", "NORAD_CAT_ID", "BSTAR", "MEAN_MOTION_DOT", "MEAN_MOTION_DDOT"]
    groups, rows, seen = [], [], set()
    files = [("active", "sat_active.csv")] + [(os.path.basename(x)[4:-4], os.path.basename(x)) for x in sorted(glob.glob(os.path.join(P, "deb_*.csv")))]
    for gi, (g, fn) in enumerate(files):
        p = os.path.join(P, fn)
        if not os.path.exists(p):
            continue
        groups.append(g)
        for r in csv.DictReader(open(p)):
            if r["NORAD_CAT_ID"] in seen:
                continue
            seen.add(r["NORAD_CAT_ID"])
            rows.append([r[k] for k in keep] + [len(groups) - 1])
    print(f"sats: {len(rows)} objects in groups {groups}")
    return {"fields": keep + ["G"], "groups": groups, "rows": rows}


def build_cad(P):
    out = []
    for fn in ("cad_past.json", "cad_future.json"):
        p = os.path.join(P, fn)
        if not os.path.exists(p):
            continue
        d = json.load(open(p))
        for r in d.get("data", []):
            out.append(dict(zip(d["fields"], r)))
    out.sort(key=lambda r: float(r["jd"]))
    slim = [{"des": r["des"], "name": (r.get("fullname") or r["des"]).strip(), "jd": f(r["jd"], 5), "cd": r["cd"],
             "dist": f(r["dist"], 7), "dmin": f(r["dist_min"], 7), "dmax": f(r["dist_max"], 7),
             "v": f(r["v_rel"], 3), "h": f(r["h"], 2), "D": f(r.get("diameter"), 4), "ts": r["t_sigma_f"]} for r in out]
    print(f"cad: {len(slim)} approaches")
    return slim


def build_sentry(P):
    p = os.path.join(P, "sentry.json")
    if not os.path.exists(p):
        return [], set()
    d = json.load(open(p))["data"]
    rows = [{"des": r["des"], "name": r["fullname"], "ip": f(r["ip"], 12), "ps": f(r["ps_cum"], 2), "ts": int(r["ts_max"] or 0),
             "D": f(r["diameter"], 4), "range": r["range"], "n": r["n_imp"], "h": f(r["h"], 2), "last": r["last_obs"]} for r in d]
    rows.sort(key=lambda r: -(r["ps"] if r["ps"] is not None else -99))
    print(f"sentry: {len(rows)} objects")
    return rows, {r["des"] for r in rows}


def build_tracks(P, manifest):
    tracks = []
    for fp in sorted(glob.glob(os.path.join(P, "horizons", "*.json"))):
        res = json.load(open(fp)).get("result", "")
        if "$$SOE" not in res:
            continue
        body = res.split("$$SOE")[1].split("$$EOE")[0]
        jd, xyz = [], []
        for line in body.strip().splitlines():
            parts = [s.strip() for s in line.split(",")]
            if len(parts) < 5:
                continue
            jd.append(float(parts[0]))
            xyz += [round(float(parts[2]), 9), round(float(parts[3]), 9), round(float(parts[4]), 9)]
        if len(jd) < 3:
            continue
        key = "horizons/" + os.path.basename(fp)
        note = manifest["files"].get(key, {}).get("note", "")
        des = os.path.basename(fp).rsplit("_", 1)[0].replace("_", " ")
        tracks.append({"des": des, "jd0": jd[0], "step": round((jd[-1] - jd[0]) / (len(jd) - 1), 8), "xyz": xyz, "note": note,
                       "sha256": manifest["files"].get(key, {}).get("sha256")})
    print(f"tracks: {len(tracks)} Horizons flyby tracks")
    return tracks


def build_land():
    """Natural Earth 1:110m land polygons (public domain) -> flat [lon,lat,...] rings for coastline drawing."""
    p = os.path.join(ROOT, "data", "ne_110m_land.geojson")
    if not os.path.exists(p):
        return []
    rings = []
    for feat in json.load(open(p))["features"]:
        g = feat["geometry"]
        polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        for poly in polys:
            for ring in poly:
                rings.append([round(v, 2) for pt in ring for v in pt[:2]])
    print(f"land: {len(rings)} coastline rings")
    return rings


def main():
    stamp = sys.argv[1] if len(sys.argv) > 1 else open(os.path.join(PK, "LATEST")).read().strip()
    P = os.path.join(PK, stamp)
    os.makedirs(OUT, exist_ok=True)
    manifest = json.load(open(os.path.join(P, "manifest.json")))
    sentry, sentry_ids = build_sentry(P)
    payload = {
        "neo": build_neo(P, sentry_ids),
        "sats": build_sats(P),
        "cad": build_cad(P),
        "sentry": sentry,
        "tracks": build_tracks(P, manifest),
        "land": build_land(),
    }
    for k, v in payload.items():
        with open(os.path.join(OUT, f"{k}.json"), "w") as fh:
            json.dump(v, fh, separators=(",", ":"))
    derived = {}
    for k in payload:
        with open(os.path.join(OUT, f"{k}.json"), "rb") as fh:
            derived[f"{k}.json"] = hashlib.sha256(fh.read()).hexdigest()
    slim_manifest = {"packet": manifest["packet"], "derived": derived, "packet_sha256": manifest["packet_sha256"], "errors": manifest["errors"],
                     "files": {k: {kk: v[kk] for kk in ("url", "bytes", "sha256", "fetched_utc") if kk in v} for k, v in manifest["files"].items()}}
    json.dump(slim_manifest, open(os.path.join(OUT, "manifest.json"), "w"), indent=1)
    for fn in sorted(os.listdir(OUT)):
        print(f"  web/data/{fn:16s} {os.path.getsize(os.path.join(OUT, fn)):>10,d} B")


if __name__ == "__main__":
    main()
