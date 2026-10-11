"""Daily job: scrape every source, merge duplicates, track new ads / price changes, send the email.

    python -m scraper.run                 # full run + email (if SMTP env vars are set)
    python -m scraper.run --no-email      # scrape only
    python -m scraper.run --only comparis,flatfox
"""
import argparse
import concurrent.futures as cf
import datetime as dt
import json
import logging
import time
import traceback
from pathlib import Path

from . import emailer
from .http import Blocked, Http
from .listing import finalize, fingerprint, identical, make_id, similar
from .regions import slugify
from .sources import comparis, engelvoelkers, flatfox, generic, realadvisor, smg_satellite, tutti

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "docs" / "data" / "listings.json"
STALE_DAYS = 10        # not seen for this long -> marked inactive (probably sold / removed)
DROP_AFTER_DAYS = 120  # inactive records are deleted after this long

STRUCTURED = [comparis, realadvisor, flatfox, engelvoelkers, tutti, smg_satellite]
# which source's numbers we trust most when the same flat is on several portals
PRIORITY = ["comparis", "realadvisor", "flatfox", "engelvoelkers", "web", "tutti", "homegate_is24"]
FIELDS = ["title", "description", "price", "rooms", "living_area", "usable_area", "price_per_m2", "floor",
          "bathrooms", "street", "zip", "municipality", "canton", "district", "lat", "lng", "year_built",
          "year_renovated", "agency", "agency_phone", "property_type", "type_label", "private_seller", "published"]

log = logging.getLogger("run")


def today():
    return dt.date.today().isoformat()


def load_state():
    if DATA.exists():
        return json.loads(DATA.read_text(encoding="utf-8"))
    return {"properties": [], "sources": {}, "runs": []}


# ----------------------------------------------------------------------------- scraping

def run_source(mod, http, ctx):
    t0 = time.time()
    recs, status = [], "ok"
    seen = set()
    try:
        for r in mod.scrape(http, ctx):
            if r["source_id"] not in seen:  # sources may return an ad on several of their pages
                seen.add(r["source_id"])
                recs.append(r)
    except Blocked as e:
        status = f"blocked ({e})"
    except Exception as e:  # keep the other sources running
        status = f"error: {e.__class__.__name__}: {e}"
        log.error("source %s failed:\n%s", mod.NAME, traceback.format_exc())
    return mod.NAME, mod.LABEL, recs, status, round(time.time() - t0)


def run_generic(http, ctx):
    results = []
    for site in generic.load_config()["sites"]:
        t0 = time.time()
        recs, status = [], "ok"
        try:
            recs = list(generic.scrape_site(http, site))
            if not recs:
                status = "no ads found"
        except Blocked as e:
            status = f"blocked ({e})"
        except Exception as e:
            status = f"error: {e.__class__.__name__}: {e}"
        results.append((f"web:{site['name']}", site["name"], recs, status, round(time.time() - t0),
                        site["url"], site.get("type", "broker")))
    return results


def scrape_all(only=None):
    http = Http()
    ctx = {"day": dt.date.today().toordinal()}
    out = []
    with cf.ThreadPoolExecutor(max_workers=7) as ex:
        futs = [ex.submit(run_source, m, http, ctx) for m in STRUCTURED if not only or m.NAME in only]
        gen_fut = ex.submit(run_generic, http, ctx) if not only or "web" in only else None
        for f in cf.as_completed(futs):
            name, label, recs, status, secs = f.result()
            log.info("%-14s %-10s %4d listings %4ds", name, status[:10], len(recs), secs)
            out.append({"key": name, "label": label, "recs": recs, "status": status, "secs": secs,
                        "kind": "portal"})
        if gen_fut:
            for key, label, recs, status, secs, url, kind in gen_fut.result():
                out.append({"key": key, "label": label, "recs": recs, "status": status, "secs": secs,
                            "url": url, "kind": kind})
    log.info("HTTP requests: %d", http.request_count)
    return out


# ----------------------------------------------------------------------------- merging

def _prio(src):
    return PRIORITY.index(src) if src in PRIORITY else len(PRIORITY)


def _apply_best(prop):
    """Recompute the property's visible fields from its best (highest-priority, most recent) listing."""
    ref = dt.date.fromisoformat(prop["last_seen"])
    listings = sorted(prop["listings"].values(),
                      key=lambda l: ((ref - dt.date.fromisoformat(l["last_seen"])).days > STALE_DAYS,
                                     _prio(l["source"])))
    for f in FIELDS:
        prop[f] = None
        for l in listings:
            v = l["data"].get(f)
            if v not in (None, "", []):
                prop[f] = v
                break
    feats, images = {}, []
    for l in listings:
        feats.update(l["data"].get("features") or {})
        for im in l["data"].get("images") or []:
            if im not in images:
                images.append(im)
    prop["features"] = feats
    prop["images"] = images[:6]
    prop["sources"] = sorted({l["source_label"] for l in listings})
    prop["links"], labels = [], set()
    for l in listings:
        if l["source_label"] in labels:
            continue
        labels.add(l["source_label"])
        prop["links"].append({"label": l["source_label"], "url": l["url"],
                              "active": (ref - dt.date.fromisoformat(l["last_seen"])).days <= STALE_DAYS})
    prop["url"] = listings[0]["url"]
    prop["numbers_hidden"] = all(l["data"].get("numbers_hidden") for l in listings)
    prop["parsed_from_text"] = all(l["data"].get("parsed_from_text") or l["data"].get("numbers_hidden")
                                   for l in listings)


def _same_source_conflict(prop, rec, lkey):
    """Two different ads of the same portal are usually different flats (e.g. units of one new-build
    project) - unless their content is identical (aggregators sometimes list a flat twice)."""
    prefix = lkey.split(":", 1)[0]
    for k, l in prop["listings"].items():
        if k != lkey and k.split(":", 1)[0] == prefix and not identical(rec, l["data"]):
            return True
    return False


def merge(state, results, run_day):
    props = {p["id"]: p for p in state["properties"]}
    by_listing, by_fp, by_zip = {}, {}, {}
    for p in props.values():
        for lk in p["listings"]:
            by_listing[lk] = p["id"]
        if p.get("fingerprint"):
            by_fp[p["fingerprint"]] = p["id"]
        if p.get("zip"):
            by_zip.setdefault(str(p["zip"]), set()).add(p["id"])

    known_sources = set(state.get("sources", {}).keys())
    before = {pid: p.get("price") for pid, p in props.items()}
    new_ids, price_changes = [], []

    def order(res):
        k = res["key"]
        return _prio("web" if k.startswith("web:") else k)

    for res in sorted(results, key=order):
        baseline = res["key"] not in known_sources  # first time we see a source: don't flood the email
        seen_here = set()
        for raw in res["recs"]:
            rec = finalize(dict(raw))
            if not rec:
                continue
            src = rec["source"]
            lkey = make_id("web-" + slugify(res["label"]) if src == "web" else src, rec["source_id"])
            if lkey in seen_here:
                continue
            seen_here.add(lkey)
            fp = fingerprint(rec)
            pid = by_listing.get(lkey) or (fp and by_fp.get(fp))
            if pid and pid in props and _same_source_conflict(props[pid], rec, lkey):
                pid = None
            if not pid:
                best = 0
                for c in sorted(by_zip.get(str(rec.get("zip") or ""), ())):
                    if c not in props or _same_source_conflict(props[c], rec, lkey):
                        continue
                    sc = similar(rec, props[c])
                    if sc > best:
                        best, pid = sc, c
            listing = {
                "source": src,
                "source_label": f"{res['label']}" + (f" ({rec['origin']})" if rec.get("origin") and src != "homegate_is24" else ""),
                "url": rec["url"],
                "last_seen": run_day,
                "data": {k: v for k, v in rec.items() if k not in ("source", "source_id", "url")},
            }
            if pid and pid in props:
                p = props[pid]
                old = p["listings"].get(lkey)
                listing["first_seen"] = old["first_seen"] if old else run_day
                p["listings"][lkey] = listing
            else:
                pid = lkey
                p = props[pid] = {"id": pid, "first_seen": run_day, "listings": {},
                                  "price_history": [], "baseline": baseline}
                listing["first_seen"] = run_day
                p["listings"][lkey] = listing
                if not baseline:
                    new_ids.append(pid)
            by_listing[lkey] = pid
            p["last_seen"] = run_day
            _apply_best(p)
            if fp and not p.get("fingerprint"):
                p["fingerprint"] = fp
                by_fp[fp] = pid
            if p.get("zip"):
                by_zip.setdefault(str(p["zip"]), set()).add(pid)

    # second pass: merge properties that turned out to be the same flat
    for z, ids in by_zip.items():
        ids = sorted((i for i in ids if i in props), key=lambda i: (props[i]["first_seen"], i))
        for i, a_id in enumerate(ids):
            if a_id not in props:
                continue
            for b_id in ids[i + 1:]:
                if b_id not in props or a_id not in props:
                    continue
                a, b = props[a_id], props[b_id]
                if similar(a, b) < 4:
                    continue
                if any(_same_source_conflict(a, l["data"], k) for k, l in b["listings"].items()):
                    continue
                a["listings"].update(b["listings"])
                a["first_seen"] = min(a["first_seen"], b["first_seen"])
                a["last_seen"] = max(a["last_seen"], b["last_seen"])
                a["baseline"] = a.get("baseline") and b.get("baseline")
                for k in b["listings"]:
                    by_listing[k] = a_id
                if b_id in new_ids:
                    new_ids.remove(b_id)
                del props[b_id]
                _apply_best(a)

    # price history: compare with the price the property had before this run
    for pid, p in props.items():
        if p.get("last_seen") != run_day or not p.get("price") or p.get("numbers_hidden"):
            continue
        hist = p.setdefault("price_history", [])
        if not hist or hist[-1][1] != p["price"]:
            old_price = before.get(pid)
            hist.append([run_day, p["price"]])
            if old_price and old_price != p["price"]:
                price_changes.append((pid, old_price, p["price"]))

    # activity / cleanup
    d_today = dt.date.fromisoformat(run_day)
    for pid in list(props):
        p = props[pid]
        last = dt.date.fromisoformat(p["last_seen"])
        p["active"] = (d_today - last).days <= STALE_DAYS
        if not p["active"] and not p.get("removed_on"):
            p["removed_on"] = run_day
        if p["active"]:
            p.pop("removed_on", None)
        if (d_today - last).days > DROP_AFTER_DAYS:
            del props[pid]
        else:
            prices = [h[1] for h in p.get("price_history", [])]
            p["price_drop"] = bool(len(prices) > 1 and prices[-1] < max(prices))
            p["days_online"] = (d_today - dt.date.fromisoformat(p["first_seen"])).days

    # de-duplicate dropped duplicates caused by merges
    state["properties"] = sorted(props.values(), key=lambda p: (p["first_seen"], p["id"]), reverse=True)
    for res in results:
        prev = state.setdefault("sources", {}).get(res["key"], {})
        state["sources"][res["key"]] = {
            "label": res["label"], "kind": res["kind"], "url": res.get("url"),
            "status": res["status"], "count": len(res["recs"]), "seconds": res["secs"],
            "last_ok": run_day if res["status"] == "ok" else prev.get("last_ok"),
        }
    return new_ids, price_changes


# ----------------------------------------------------------------------------- output

def public_view(state):
    """Strip the per-listing raw data to keep the JSON served to the web app small."""
    props = []
    for p in state["properties"]:
        q = {k: v for k, v in p.items() if k != "listings"}
        if q.get("description") and len(q["description"]) > 1800:
            q["description"] = q["description"][:1800] + " …"
        props.append(q)
    return props


def _dump_lines(obj, list_key):
    """JSON with one array element per line: compact, yet git stores daily changes as small diffs."""
    head = {k: v for k, v in obj.items() if k != list_key}
    items = ",\n".join(json.dumps(x, ensure_ascii=False, separators=(",", ":")) for x in obj[list_key])
    head_json = json.dumps(head, ensure_ascii=False, separators=(",", ":"))[:-1]
    sep = "," if head else ""
    return f'{head_json}{sep}"{list_key}":[\n{items}\n]}}\n'


def save(state):
    DATA.parent.mkdir(parents=True, exist_ok=True)
    DATA.write_text(_dump_lines(state, "properties"), encoding="utf-8")
    pub = {"generated": dt.datetime.now().isoformat(timespec="minutes"), "sources": state["sources"],
           "runs": state.get("runs", [])[-30:], "properties": public_view(state)}
    (DATA.parent / "public.json").write_text(_dump_lines(pub, "properties"), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-email", action="store_true")
    ap.add_argument("--save-cache", action="store_true", help="store raw scrape results in out/scrape_cache.json")
    ap.add_argument("--from-cache", action="store_true", help="skip scraping, re-use out/scrape_cache.json (development)")
    ap.add_argument("--only", help="comma separated source keys (comparis,realadvisor,flatfox,engelvoelkers,tutti,homegate_is24,web)")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    run_day = today()
    state = load_state()
    cache = ROOT / "out" / "scrape_cache.json"
    if args.from_cache:
        results = json.loads(cache.read_text(encoding="utf-8"))
    else:
        results = scrape_all(set(args.only.split(",")) if args.only else None)
    if args.save_cache:
        cache.parent.mkdir(exist_ok=True)
        cache.write_text(json.dumps(results, ensure_ascii=False), encoding="utf-8")
    new_ids, price_changes = merge(state, results, run_day)
    active = sum(1 for p in state["properties"] if p["active"])
    state.setdefault("runs", []).append({"day": run_day, "new": len(new_ids), "price_changes": len(price_changes),
                                         "active": active})
    state["runs"] = state["runs"][-60:]
    save(state)
    log.info("done: %d active properties, %d new, %d price changes", active, len(new_ids), len(price_changes))

    if not args.no_email:
        emailer.send_daily(state, new_ids, price_changes, run_day)


if __name__ == "__main__":
    main()
