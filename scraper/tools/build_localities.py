"""Build config/localities.json: every Swiss postcode within the configured driving time of the workplace,
with car time/distance (OSRM) and public-transport time (search.ch) from the locality centre.

    python -m scraper.tools.build_localities

Data: GeoNames postal codes (CC BY 4.0, download.geonames.org/export/zip/CH.zip).
"""
import csv
import io
import json
import math
import re
import time
import zipfile
from pathlib import Path

from curl_cffi import requests as cffi_requests

from ..commute import PT_PAUSE, SEARCH, UA, WORK, car_times, next_workday, pt_time

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "config" / "localities.json"
GEONAMES = "https://download.geonames.org/export/zip/CH.zip"
CANTON_NAMES = {"NE": "Neuchâtel", "BE": "Bern", "VD": "Vaud", "FR": "Fribourg", "JU": "Jura", "SO": "Solothurn"}


def haversine(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h))


def clean_name(name):
    """'Colombier NE' -> 'Colombier', 'Mur (Vully) FR' -> 'Mur (Vully)'."""
    return re.sub(r"\s+(NE|VD|BE|FR|JU|SO)$", "", name).strip()


def main():
    max_min = SEARCH.get("max_car_minutes", 25)
    raw = cffi_requests.get(GEONAMES, headers=UA, timeout=120).content
    text = zipfile.ZipFile(io.BytesIO(raw)).read("CH.txt").decode("utf-8")
    cands = []
    for r in csv.reader(io.StringIO(text), delimiter="\t"):
        _, plz, place, _canton, ccode, district, _, muni, _bfs, lat, lon = (r + [""] * 12)[:11]
        if not lat or any(ch.isdigit() for ch in place) or "OFS" in place.split():
            continue  # PO-box / special postcodes
        p = (float(lat), float(lon))
        if haversine(WORK, p) <= max_min * 1.6:  # generous straight-line pre-filter
            cands.append({"zip": plz, "name": clean_name(place), "geo_name": place, "canton": ccode,
                          "district": district.replace("Bezirk ", "").replace("District de ", ""),
                          "municipality": muni, "lat": p[0], "lng": p[1]})
    print(f"{len(cands)} candidate postcodes, computing driving times ...")
    for c, (mins, km) in zip(cands, car_times([(c["lat"], c["lng"]) for c in cands])):
        c["car_min"], c["car_km"] = mins, km
    keep = sorted((c for c in cands if c["car_min"] is not None and c["car_min"] <= max_min),
                  key=lambda c: (c["car_min"], c["zip"]))
    # places just outside the area: lets the scrapers recognise (and drop) ads in e.g. Le Locle or Fleurier
    nearby = sorted(({"zip": c["zip"], "name": c["name"], "canton": c["canton"], "car_min": c["car_min"]}
                     for c in cands if c["car_min"] is not None and c["car_min"] > max_min),
                    key=lambda c: (c["car_min"], c["zip"]))
    previous = {}
    if OUT.exists():  # reuse public-transport times already computed (search.ch has a per-minute limit)
        for l in json.loads(OUT.read_text(encoding="utf-8")).get("localities", []):
            previous[(l["zip"], l["name"])] = (l.get("pt_min"), l.get("pt_changes"))
    print(f"{len(keep)} localities within {max_min} min, computing public-transport times ...")
    date = next_workday()
    for c in keep:
        c["canton_name"] = CANTON_NAMES.get(c["canton"], c["canton"])
        if previous.get((c["zip"], c["name"]), (None,))[0] is not None:
            c["pt_min"], c["pt_changes"] = previous[(c["zip"], c["name"])]
            continue
        c["pt_min"], c["pt_changes"] = pt_time(c["lat"], c["lng"], date)
        time.sleep(PT_PAUSE)
    OUT.write_text(json.dumps({"workplace": SEARCH["workplace"], "max_car_minutes": max_min,
                               "computed_for": date.isoformat(), "localities": keep, "nearby_outside": nearby},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {OUT} ({len(keep)} localities)")


if __name__ == "__main__":
    main()
