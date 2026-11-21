"""flatfox.ch - public JSON API (map pins in a bounding box, then listing details).

Flatfox is where many Swiss property managers publish rentals; it gives net rent,
charges, move-in date and furnished/temporary flags.
"""
from ..commute import SEARCH
from ..listing import parse_float
from ..regions import LOCALITIES, lookup_zip

NAME = "flatfox"
LABEL = "Flatfox"
TILES = 3  # split the area into 3x3 tiles - the pin API returns at most 1000 pins per call

ATTR_MAP = {"balconygarden": "balcony", "lift": "lift", "parkingspace": "parking", "garage": "parking",
            "view": "view", "washingmachine": "own_laundry", "dishwasher": "dishwasher", "petsallowed": "pets",
            "wheelchair": "accessible", "fireplace": "fireplace", "minergie": "minergie", "cellar": "cellar"}


def _features(attrs):
    out = {}
    for a in attrs or []:
        key = ATTR_MAP.get(a.get("name")) if isinstance(a, dict) else None
        if key:
            out[key] = True
    return out


def _tiles():
    lats = [l["lat"] for l in LOCALITIES]
    lngs = [l["lng"] for l in LOCALITIES]
    s, n, w, e = min(lats) - 0.01, max(lats) + 0.01, min(lngs) - 0.01, max(lngs) + 0.01
    dy, dx = (n - s) / TILES, (e - w) / TILES
    for i in range(TILES):
        for j in range(TILES):
            yield dict(south=s + i * dy, north=s + (i + 1) * dy, west=w + j * dx, east=w + (j + 1) * dx)


def scrape(http, ctx):
    max_rent = SEARCH.get("max_rent", 2500)
    pks = []
    for bb in _tiles():
        params = {k: round(v, 5) for k, v in bb.items()}
        params.update(offer_type="RENT", object_category="APARTMENT", max_count=1000)
        r = http.get("https://flatfox.ch/api/v1/pin/", params=params, delay=(1, 2))
        for p in (r.json() if r is not None else []):
            if (p.get("price_display") or 0) <= max_rent and p["pk"] not in pks:
                pks.append(p["pk"])
    for i in range(0, len(pks), 40):
        q = "&".join(f"pk={pk}" for pk in pks[i:i + 40])
        r = http.get(f"https://flatfox.ch/api/v1/public-listing/?{q}&expand=images&limit=40", delay=(1, 2))
        if r is None:
            continue
        for x in r.json().get("results", []):
            if x.get("offer_type") != "RENT" or not lookup_zip(x.get("zipcode")):
                continue
            rooms = parse_float(x.get("number_of_rooms"))
            if rooms and rooms > SEARCH.get("max_rooms", 3):
                continue
            agency = x.get("agency") or {}
            yield {
                "source": NAME,
                "source_id": x["pk"],
                "url": "https://flatfox.ch" + x["url"],
                "title": x.get("description_title") or x.get("public_title"),
                "description": x.get("description"),
                "price": x.get("rent_gross") or x.get("price_display"),
                "rent_net": x.get("rent_net"),
                "charges": x.get("rent_charges"),
                "rooms": rooms,
                "living_area": x.get("surface_living") or x.get("livingspace"),
                "floor": x.get("floor"),
                "street": x.get("street"),
                "zip": x.get("zipcode"),
                "city": x.get("city"),
                "lat": x.get("latitude"),
                "lng": x.get("longitude"),
                "year_built": x.get("year_built"),
                "year_renovated": x.get("year_renovated"),
                "images": ["https://flatfox.ch" + im["url_thumb_m"] for im in (x.get("images") or [])[:6]
                           if isinstance(im, dict) and im.get("url_thumb_m")],
                "agency": agency.get("name") or None,
                "published": x.get("published") or x.get("created"),
                "available_from": x.get("moving_date") if x.get("moving_date_type") == "dat" else
                                  ("immediately" if x.get("moving_date_type") == "imm" else None),
                "furnished": bool(x.get("is_furnished")),
                "temporary": bool(x.get("is_temporary")),
                "property_type": "room" if x.get("object_type") == "SHARED_ROOM" else None,
                "features": _features(x.get("attributes")),
            }
