"""flatfox.ch - public JSON API (pins in a bounding box, then listing details)."""
from ..listing import parse_float

NAME = "flatfox"
LABEL = "Flatfox"
# Bounding box around Basel-Stadt + Basel-Landschaft (out-of-area hits are dropped by postcode)
BBOX = dict(west=7.33, east=7.98, south=47.33, north=47.63)


def scrape(http, ctx):
    params = dict(BBOX, offer_type="SALE", object_category="APARTMENT", max_count=800)
    r = http.get("https://flatfox.ch/api/v1/pin/", params=params, delay=(1, 2))
    pins = r.json() if r is not None else []
    pks = [p["pk"] for p in pins]
    for i in range(0, len(pks), 40):
        batch = pks[i:i + 40]
        q = "&".join(f"pk={pk}" for pk in batch)
        r = http.get(f"https://flatfox.ch/api/v1/public-listing/?{q}&expand=images&limit=40", delay=(1, 2))
        if r is None:
            continue
        for x in r.json().get("results", []):
            if x.get("offer_type") != "SALE" or x.get("object_category") not in ("APARTMENT", None):
                continue
            agency = x.get("agency") or {}
            yield {
                "source": NAME,
                "source_id": x["pk"],
                "url": "https://flatfox.ch" + x["url"],
                "title": x.get("description_title") or x.get("public_title"),
                "description": x.get("description"),
                "price": x.get("selling_price") or x.get("price_display"),
                "rooms": parse_float(x.get("number_of_rooms")),
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
                "published": x.get("published"),
                "features": _features(x.get("attributes")),
            }


ATTR_MAP = {"balconygarden": "balcony", "lift": "lift", "parkingspace": "parking", "garage": "parking",
            "view": "view", "cable": None, "dishwasher": None, "washingmachine": "own_laundry",
            "petsallowed": "pets", "wheelchair": "accessible", "fireplace": "fireplace", "minergie": "minergie"}


def _features(attrs):
    out = {}
    for a in attrs or []:
        key = ATTR_MAP.get(a.get("name")) if isinstance(a, dict) else None
        if key:
            out[key] = True
    return out
