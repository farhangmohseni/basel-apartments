"""Travel times to the workplace.

* Car: OSRM (router.project-osrm.org, OpenStreetMap road network, free-flow
  times - add a few minutes for rush hour). Many origins per request.
* Public transport: search.ch timetable API, best connection arriving around
  the configured time on a working day, door to door (walking included).

Results for exact listing coordinates are cached in docs/data/commute_cache.json,
so every address is looked up only once.
"""
import datetime as dt
import json
import logging
import time
from pathlib import Path

from curl_cffi import requests as cffi_requests

ROOT = Path(__file__).resolve().parents[1]
SEARCH = json.loads((ROOT / "config" / "search.json").read_text(encoding="utf-8"))
WORK = (SEARCH["workplace"]["lat"], SEARCH["workplace"]["lng"])
CACHE = ROOT / "docs" / "data" / "commute_cache.json"
UA = {"User-Agent": "neuchatel-studio-finder/1.0 (private apartment search; github.com/farhangmohseni/basel-apartments)"}
OSRM = "https://router.project-osrm.org/table/v1/driving/"
SEARCH_CH = "https://timetable.search.ch/api/route.json"
PT_PAUSE = 6.5  # search.ch allows only a few route queries per minute (HTTP 429 "Too many requests this minute")
PT_TIME_BUDGET = 12 * 60  # seconds of public-transport lookups per run; the rest is done in the next runs

log = logging.getLogger(__name__)


def next_workday(weekday=1):
    """Date of the next Tuesday (default) - a normal working day for timetable queries."""
    d = dt.date.today() + dt.timedelta(days=1)
    while d.weekday() != weekday:
        d += dt.timedelta(days=1)
    return d


def car_times(points):
    """[(lat, lng), ...] -> [(minutes, km) or (None, None)], batched (OSRM demo allows ~100 coordinates)."""
    out = []
    for i in range(0, len(points), 90):
        batch = points[i:i + 90]
        coords = ";".join(f"{lng:.5f},{lat:.5f}" for lat, lng in batch) + f";{WORK[1]},{WORK[0]}"
        url = (f"{OSRM}{coords}?sources=" + ";".join(map(str, range(len(batch))))
               + f"&destinations={len(batch)}&annotations=duration,distance")
        try:
            r = cffi_requests.get(url, headers=UA, timeout=60)
            data = r.json()
            for dur, dist in zip(data["durations"], data["distances"]):
                out.append((round(dur[0] / 60, 1) if dur[0] is not None else None,
                            round(dist[0] / 1000, 1) if dist[0] is not None else None))
        except Exception as e:  # keep going - car time just stays unknown
            log.warning("OSRM failed: %s", e)
            out.extend([(None, None)] * len(batch))
        time.sleep(1.2)
    return out


def pt_time(lat, lng, date=None, arrival=None):
    """Best public-transport door-to-door time (minutes) and number of changes, or (None, None)."""
    date = date or next_workday()
    arrival = arrival or SEARCH.get("commute_arrival_time", "08:00")
    params = {"from": f"{lat:.5f},{lng:.5f}", "to": f"{WORK[0]},{WORK[1]}", "date": date.strftime("%m/%d/%Y"),
              "time": arrival, "time_type": "arrival", "num": 4}
    cons = None
    for attempt in range(3):
        try:
            r = cffi_requests.get(SEARCH_CH, params=params, headers=UA, timeout=40)
            if r.status_code == 429:  # "Too many requests this minute": wait for the next minute
                time.sleep(65)
                continue
            cons = r.json().get("connections") or []
            break
        except Exception as e:
            log.warning("search.ch failed: %s", e)
            time.sleep(5)
    if cons is None:
        return None, None
    best = None
    for c in cons:
        dur = c.get("duration")
        if not dur:
            continue
        rides = [l for l in c.get("legs") or [] if l.get("type") not in (None, "walk")]
        cand = (round(dur / 60), max(len(rides) - 1, 0))
        if best is None or cand[0] < best[0]:
            best = cand
    return best if best else (None, None)


def _key(lat, lng):
    return f"{lat:.3f},{lng:.3f}"  # ~100 m grid


def load_cache():
    try:
        return json.loads(CACHE.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return {}


def _save(cache):
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(cache, separators=(",", ":"), sort_keys=True), encoding="utf-8")


def enrich(properties, localities_by_zip, max_pt_lookups=100):
    """Add car / public-transport commute to every active property: exact (from its coordinates, cached) or from
    the centre of its locality. Car routes are cheap (all at once); public-transport lookups are rate-limited, so
    each run does a limited number - cheapest studios first - and saves progress as it goes."""
    cache = load_cache()
    need_car, need_pt = [], {}
    for p in properties:
        if not p.get("active"):
            continue
        if p.get("lat") and p.get("lng"):
            k = _key(p["lat"], p["lng"])
            c = cache.setdefault(k, {})
            if "car_min" not in c and k not in need_car:
                need_car.append(k)
            if c.get("pt_min") is None and c.get("pt_tries", 0) < 2:
                rank = (p.get("property_type") != "studio", p.get("price") or 99999)
                need_pt[k] = min(need_pt.get(k, rank), rank)
    if need_car:
        pts = [tuple(map(float, k.split(","))) for k in need_car]
        for k, (mins, km) in zip(need_car, car_times(pts)):
            cache[k]["car_min"], cache[k]["car_km"] = mins, km
        _save(cache)
    date, t0, done = next_workday(), time.time(), 0
    for k in sorted(need_pt, key=need_pt.get)[:max_pt_lookups]:
        if time.time() - t0 > PT_TIME_BUDGET:
            break
        lat, lng = map(float, k.split(","))
        mins, changes = pt_time(lat, lng, date)
        if mins is None:
            cache[k]["pt_tries"] = cache[k].get("pt_tries", 0) + 1
        else:
            cache[k]["pt_min"], cache[k]["pt_changes"] = mins, changes
        done += 1
        if done % 20 == 0:
            _save(cache)
            log.info("public transport: %d of %d addresses done", done, min(len(need_pt), max_pt_lookups))
        time.sleep(PT_PAUSE)
    for p in properties:
        if not p.get("active"):
            continue
        loc = localities_by_zip.get(str(p.get("zip") or ""), {})
        c = cache.get(_key(p["lat"], p["lng"]), {}) if p.get("lat") and p.get("lng") else {}
        car_exact, pt_exact = c.get("car_min") is not None, c.get("pt_min") is not None
        p["car_min"] = c["car_min"] if car_exact else loc.get("car_min")
        p["car_km"] = c.get("car_km") if car_exact else loc.get("car_km")
        p["pt_min"] = c["pt_min"] if pt_exact else loc.get("pt_min")
        p["pt_changes"] = c.get("pt_changes") if pt_exact else loc.get("pt_changes")
        p["commute_exact"], p["pt_exact"] = car_exact, pt_exact
    _save(cache)
    return len(need_car), done
