"""comparis.ch - aggregator (Homegate, ImmoScout24, Newhome, Flatfox, many agencies).

One bounding-box search over the whole area (flats to rent, <= max rooms, <= max rent,
newest first, 10 per page). Comparis limits automated traffic, so we stay well below:
the newest pages every day plus a few older pages on a rotation.
"""
import json
import re
from urllib.parse import quote

from ..commute import SEARCH
from ..listing import parse_float, parse_int
from ..regions import LOCALITIES

NAME = "comparis"
LABEL = "Comparis"
URL = "https://www.comparis.ch/immobilien/result/list?requestobject={ro}&page={page}"
DETAIL = "https://www.comparis.ch/immobilien/marktplatz/details/show/{id}"
DAILY_PAGES, ROTATING_PAGES, MAX_PAGES = 6, 8, 100
DELAY = (6, 11)  # seconds between requests


def _request_object():
    lats = [l["lat"] for l in LOCALITIES]
    lngs = [l["lng"] for l in LOCALITIES]
    return {"DealType": 10, "SiteId": 0, "RootPropertyTypes": [1], "PropertyTypes": [],
            "RoomsTo": SEARCH.get("max_rooms", 3), "PriceTo": SEARCH.get("max_rent", 2500),
            "LowerLeftLatitude": round(min(lats) - 0.01, 3), "LowerLeftLongitude": round(min(lngs) - 0.01, 3),
            "UpperRightLatitude": round(max(lats) + 0.01, 3), "UpperRightLongitude": round(max(lngs) + 0.01, 3),
            "Sort": 3}  # 3 = newest first


def _parse(html):
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        return None
    props = json.loads(m.group(1)).get("props", {}).get("pageProps", {})
    for q in props.get("dehydratedState", {}).get("queries", []):  # layout since Oct 2026
        data = (q.get("state") or {}).get("data")
        if isinstance(data, dict) and "ResultItems" in data:
            return {"items": data.get("ResultItems") or [], "pages": data.get("TotalPages") or 1}
    old = props.get("initialResultData")  # earlier layout
    if old:
        return {"items": old.get("resultItems") or [], "pages": old.get("totalPages") or 1}
    return None


def _g(it, key):
    return it.get(key, it.get(key[:1].lower() + key[1:]))


def _record(it):
    addr = _g(it, "Address") or []
    zipcity = addr[-1] if addr else ""
    zm = re.match(r"(\d{4})\s+(.*)", zipcity)
    rooms = floor = None
    for e in _g(it, "EssentialInformation") or []:
        if "Zimmer" in e or "pièce" in e:
            rooms = parse_float(e)
        elif "Etage" in e or "étage" in e:
            floor = parse_int(e)
        elif "Erdgeschoss" in e or "rez" in e.lower():
            floor = 0
    contact = _g(it, "ContactInformation") or {}
    vendor = contact.get("VendorInformation") or {}
    coord = _g(it, "Coordinate") or {}
    return {
        "source": NAME,
        "source_id": _g(it, "AdId"),
        "url": DETAIL.format(id=_g(it, "AdId")),
        "title": _g(it, "Title"),
        "description": _g(it, "Remarks"),
        "price": _g(it, "PriceValue"),
        "rooms": rooms,
        "living_area": _g(it, "AreaValue"),
        "floor": floor,
        "street": addr[0] if len(addr) > 1 else None,
        "zip": zm.group(1) if zm else None,
        "city": zm.group(2) if zm else zipcity,
        "lat": coord.get("Latitude"),
        "lng": coord.get("Longitude"),
        "year_built": _g(it, "YearOfConstruction"),
        "images": (_g(it, "ImageUrls") or [_g(it, "ImageUrl")])[:6],
        "agency": vendor.get("Name") or _g(it, "PartnerName"),
        "origin": _g(it, "PartnerName"),
        "published": _g(it, "Date"),
    }


def scrape(http, ctx):
    ro = quote(json.dumps(_request_object(), separators=(",", ":")))
    total = DAILY_PAGES
    pages = list(range(DAILY_PAGES))
    for page in range(MAX_PAGES):
        if page >= total:
            break
        if page not in pages:
            continue
        r = http.get(URL.format(ro=ro, page=page), allow_404=True, delay=DELAY)
        data = _parse(r.text) if r is not None else None
        if not data or not data["items"]:
            break
        if page == 0:
            total = min(data["pages"], MAX_PAGES)
            deeper = list(range(DAILY_PAGES, total))
            if deeper:  # a few older pages each day, so the whole stock is refreshed regularly
                start = (ctx["day"] * ROTATING_PAGES) % len(deeper)
                pages += [deeper[(start + i) % len(deeper)] for i in range(min(ROTATING_PAGES, len(deeper)))]
        for it in data["items"]:
            yield _record(it)
