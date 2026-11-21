"""realadvisor.ch - aggregator of the big Swiss portals and agency feeds.

Server-rendered pages (React Router) that embed the listings as JSON in a
`data-island="analytics" data-props="..."` attribute, ~24 newest ads per page (deeper pages are
not reliably served). So we read many small slices: the canton per room segment, every town of
the area, and room segments for the bigger towns - each new ad is caught while it is on top.
"""
import html as htmllib
import json
import re

from bs4 import BeautifulSoup
from hashids import Hashids

from ..regions import LOCALITIES, slugify

NAME = "realadvisor"
LABEL = "RealAdvisor"
BASE = "https://realadvisor.ch/fr/louer/{place}/appartement{segment}"
DETAIL = "https://realadvisor.ch/fr/louer/appartement/{code}"
SEGMENTS = ["/1-piece", "/2-pieces", "/3-pieces"]
_hash = Hashids(salt="honey doesn't spoil", min_length=8, alphabet="0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ")


def _code(listing_id):
    c = _hash.encode(int(listing_id))
    return f"{c[:4]}-{c[4:]}"


def _parse(page_html):
    """-> (listings, total_count)"""
    m = re.search(r'data-island="analytics" data-props="([^"]*)"', page_html)
    listings = json.loads(htmllib.unescape(m.group(1))).get("listings", []) if m else []
    t = re.search(r"<title>[^<]*?([\d'’]+)\s+(?:annonces|offres|biens)", page_html)
    total = int(re.sub(r"\D", "", t.group(1))) if t else len(listings)
    images = {}
    if listings:
        soup = BeautifulSoup(page_html, "lxml")
        for a in soup.find_all("a", href=re.compile(r"-[A-Z0-9]{4}-[A-Z0-9]{4}$")):
            code = a["href"][-9:]
            img = a.find("img")
            if img and code not in images:
                src = img.get("src") or (img.get("srcset") or img.get("srcSet") or "").split(" ")[0]
                if src and not src.startswith("data:"):
                    images[code] = src
    return listings, total, images


def _record(o, images):
    if o.get("offer_type") != "rent":
        return None
    code = _code(o["id"])
    street = " ".join(x for x in (o.get("route"), o.get("street_number")) if x) or None
    return {
        "source": NAME,
        "source_id": o["id"],
        "url": DETAIL.format(code=code),
        "title": o.get("title"),
        "description": "",
        "price": o.get("gross_rent_monthly"),
        "rooms": o.get("number_of_rooms"),
        "living_area": o.get("computed_surface"),
        "bathrooms": o.get("number_of_bathrooms"),
        "street": street,
        "zip": o.get("postcode"),
        "city": o.get("locality"),
        "lat": o.get("lat"),
        "lng": o.get("lng"),
        "year_built": o.get("construction_year"),
        "images": [images[code]] if code in images else [],
        "agency": o.get("agency_name"),
        "published": o.get("min_created_at") or o.get("created_at"),
    }


def _crawl(http, ctx, place, segment, daily_pages):
    r = http.get(BASE.format(place=place, segment=segment), allow_404=True)
    if r is None:
        return
    listings, total, images = _parse(r.text)
    for o in listings:
        rec = _record(o, images)
        if rec:
            yield rec
    # ?page=N is only partly honoured by the site (page 3+ repeat page 2): read at most `daily_pages`
    for page in range(2, min(daily_pages, -(-total // 24)) + 1):
        r = http.get(BASE.format(place=place, segment=segment), params={"page": page}, allow_404=True)
        if r is None:
            break
        listings, _, images = _parse(r.text)
        if not listings:
            break
        for o in listings:
            rec = _record(o, images)
            if rec:
                yield rec


# towns with many ads get their own room-segment pages every day (each page shows the ~24 newest ads)
BIG_TOWNS = {"2000", "2300", "2034", "2017", "2013", "2016", "2074", "2072", "2068", "2525", "2022", "2053", "2035",
             "2052", "2520", "2105", "2206", "2056", "2088", "2087", "2012"}


def scrape(http, ctx):
    for segment in SEGMENTS:
        yield from _crawl(http, ctx, "canton-neuchatel", segment, 2)
    places = []
    for l in sorted(LOCALITIES, key=lambda l: l["car_min"]):
        if l["zip"] not in {z for z, _ in places}:
            places.append((l["zip"], l["geo_name"]))
    for i, (z, name) in enumerate(places):
        big = z in BIG_TOWNS
        if not big and (i + ctx["day"]) % 2:  # small places every second day
            continue
        slug = f"{z}-{slugify(name)}"
        for segment in (SEGMENTS if big else [""]):
            yield from _crawl(http, ctx, slug, segment, 1)
