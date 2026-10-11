"""realadvisor.ch - aggregator of the big Swiss portals + broker feeds (IDX, Immomig, Flatfox...).

Listings are embedded in the Next.js RSC "flight" payload (self.__next_f.push).
Each page shows the 24 newest listings; pagination is not server-rendered, so
large municipalities are additionally split by room count.
"""
import base64
import json
import re

from hashids import Hashids

from ..regions import LARGE, MUNICIPALITIES, realadvisor_slug

NAME = "realadvisor"
LABEL = "RealAdvisor"
BASE = "https://realadvisor.ch/de/kaufen/{slug}/wohnung{suffix}"
ROOM_SPLITS = ["/1-zimmer", "/2-zimmer", "/3-zimmer", "/4-zimmer", "/5-zimmer", "/uber-6-zimmer"]
_hash = Hashids(salt="honey doesn't spoil", min_length=8, alphabet="0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ")


def _code(listing_id):
    c = _hash.encode(int(listing_id))
    return f"{c[:4]}-{c[4:]}"


def _image(img):
    raw = f"https://storage.googleapis.com/{img.get('bucket_name', 'aggregator-images')}/{img['file_name']}"
    enc = base64.b64encode(raw.encode()).decode()
    return f"https://img.realadvisor.ch/_/rs:fill:750:422:1:0/q:70/{enc}.webp"


def _listings(html):
    chunks = re.findall(r"self\.__next_f\.push\((\[.*?\])\)</script>", html, re.S)
    flight = ""
    for c in chunks:
        try:
            arr = json.loads(c)
        except ValueError:
            continue
        if len(arr) > 1 and isinstance(arr[1], str):
            flight += arr[1]
    dec = json.JSONDecoder()
    seen = set()
    for m in re.finditer(r'"listing":\{', flight):
        try:
            obj, _ = dec.raw_decode(flight, m.start() + len('"listing":'))
        except ValueError:
            continue
        if obj.get("id") in seen or obj.get("offer_type") != "buy":
            continue
        seen.add(obj.get("id"))
        desc = obj.get("description")
        if isinstance(desc, str) and desc.startswith("$"):
            # RSC back-reference ("$89") -> resolve "89:T...,<text>" chunk
            ref = desc[1:]
            mm = re.search(r"(?:^|\n)" + re.escape(ref) + r":T[0-9a-f]+,", flight)
            desc = flight[mm.end(): mm.end() + 4000] if mm else None
        obj["_description"] = desc
        yield obj


def _total(html):
    m = re.search(r"stehen [^.]*? (\d+) Wohnungen? zum Verkauf", html)
    return int(m.group(1)) if m else 0


def _record(o):
    title = o.get("title") or (o.get("translated_titles") or {}).get("de")
    bullets = (o.get("bullet_points") or {}).get("de") or []
    desc = (o.get("_description") or "")
    if bullets:
        desc = "• " + "\n• ".join(bullets) + "\n" + desc
    return {
        "source": NAME,
        "source_id": o["id"],
        "url": f"https://realadvisor.ch/de/kaufen/wohnung/{_code(o['id'])}",
        "title": title or f"{o.get('number_of_rooms') or ''} Zimmer Wohnung, {o.get('locality') or ''}",
        "description": desc,
        "price": o.get("sale_price"),
        "rooms": o.get("number_of_rooms"),
        "living_area": o.get("living_surface") or o.get("computed_surface"),
        "usable_area": o.get("usable_surface"),
        "bathrooms": o.get("number_of_bathrooms"),
        "parking_spaces": o.get("number_of_parking"),
        "street": " ".join(x for x in [o.get("route"), o.get("street_number")] if x) or None,
        "zip": o.get("postcode"),
        "city": o.get("locality"),
        "lat": o.get("lat"),
        "lng": o.get("lng"),
        "year_built": o.get("construction_year"),
        "year_renovated": o.get("renovation_year"),
        "images": [_image(i) for i in (o.get("images") or [])[:6] if i.get("file_name")],
        "agency": o.get("agency_name"),
        "agency_phone": o.get("agency_contact_phone_number"),
        "published": o.get("created_at"),
    }


def scrape(http, ctx):
    day = ctx["day"]
    for i, (name, canton, district, zips) in enumerate(MUNICIPALITIES):
        slug = realadvisor_slug(name, zips)
        if not slug:
            continue
        r = http.get(BASE.format(slug=slug, suffix=""), allow_404=True)
        if r is None:
            continue
        for o in _listings(r.text):
            yield _record(o)
        total = _total(r.text)
        if total > 24 and (name in LARGE or (i + day) % 3 == 0):
            for suffix in ROOM_SPLITS:
                r2 = http.get(BASE.format(slug=slug, suffix=suffix), allow_404=True)
                if r2 is None:
                    continue
                for o in _listings(r2.text):
                    yield _record(o)
