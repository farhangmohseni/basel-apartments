"""comparis.ch - aggregator (Homegate, ImmoScout24, Newhome, Properstar, brokers...).

Server-rendered Next.js page with a clean JSON payload; 10 results per page.
Comparis has aggressive bot protection, so we keep the request count low:
page 0 (newest) for every municipality every day, deeper pages on a rotation.
"""
import json
import re

from ..listing import parse_float, parse_int
from ..regions import LARGE, MUNICIPALITIES, comparis_slug

NAME = "comparis"
LABEL = "Comparis"
BASE = "https://www.comparis.ch/immobilien/marktplatz/{slug}/wohnung/kaufen"
DETAIL = "https://www.comparis.ch/immobilien/marktplatz/details/show/{id}"
MAX_PAGES = 12
MAX_REQUESTS = 70        # Comparis blocks an IP after ~60-100 fast requests: stay well below
DELAY = (6, 11)          # seconds between requests


def _parse(html):
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        return None
    data = json.loads(m.group(1))
    return data.get("props", {}).get("pageProps", {}).get("initialResultData")


def _record(it):
    addr = it.get("Address") or []
    zipcity = addr[-1] if addr else ""
    street = addr[0] if len(addr) > 1 else None
    zm = re.match(r"(\d{4})\s+(.*)", zipcity)
    ess = it.get("EssentialInformation") or []
    rooms = floor = None
    for e in ess:
        if "Zimmer" in e:
            rooms = parse_float(e)
        elif "Etage" in e or "Stock" in e:
            floor = 0 if "Erdgeschoss" in e or "EG" in e else parse_int(e)
        elif "Erdgeschoss" in e:
            floor = 0
    contact = it.get("ContactInformation") or {}
    vendor = contact.get("VendorInformation") or {}
    coord = it.get("Coordinate") or {}
    return {
        "source": NAME,
        "source_id": it["AdId"],
        "url": DETAIL.format(id=it["AdId"]),
        "title": it.get("Title"),
        "description": it.get("Remarks"),
        "price": it.get("PriceValue") if it.get("PriceType") == 1 or it.get("PriceValue") else None,
        "rooms": rooms,
        "living_area": it.get("AreaValue"),
        "floor": floor,
        "street": street,
        "zip": zm.group(1) if zm else None,
        "city": zm.group(2) if zm else zipcity,
        "lat": coord.get("Latitude"),
        "lng": coord.get("Longitude"),
        "year_built": it.get("YearOfConstruction"),
        "year_renovated": it.get("RenovationYear"),
        "images": (it.get("ImageUrls") or [it.get("ImageUrl")])[:6],
        "agency": vendor.get("Name") or it.get("PartnerName"),
        "agency_phone": vendor.get("Phone"),
        "origin": it.get("PartnerName"),
        "published": it.get("Date"),
        "type_label": it.get("PropertyTypeText"),
    }


def scrape(http, ctx):
    day = ctx["day"]
    budget = [MAX_REQUESTS]

    def get(url, params=None):
        if budget[0] <= 0:
            return None
        budget[0] -= 1
        return http.get(url, params=params, allow_404=True, delay=DELAY)

    # big towns every day, the ~75 small municipalities in 3 daily groups
    order = [m for m in MUNICIPALITIES if m[0] in LARGE] + \
            [m for k, m in enumerate(MUNICIPALITIES) if m[0] not in LARGE and (k + day) % 3 == 0]
    for i, (name, canton, district, zips) in enumerate(order):
        slug = comparis_slug(name)
        r = get(BASE.format(slug=slug))
        if r is None:
            continue
        data = _parse(r.text)
        if not data:
            continue
        for it in data.get("resultItems") or []:
            yield _record(it)
        pages = min(data.get("totalPages") or 1, MAX_PAGES)
        # deeper pages: big towns daily up to 3 pages, the rest rotates over the week
        for p in range(1, pages):
            if p > 2 and (p + i + day) % 4 != 0:
                continue
            r = get(BASE.format(slug=slug), params={"page": p})
            if r is None:
                break
            data = _parse(r.text)
            if not data or not data.get("resultItems"):
                break
            for it in data["resultItems"]:
                yield _record(it)
