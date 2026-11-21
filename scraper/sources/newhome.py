"""newhome.ch - the cantonal banks' portal, public ServiceStack JSON API at service.newhome.ch.

One radius search around the workplace: flats to rent, newest first, 20 per page.
newhome sometimes refuses requests from cloud servers - the source is then marked
"blocked" for that day and its ads still arrive through the aggregators.
"""
import re

from ..commute import SEARCH, WORK

NAME = "newhome"
LABEL = "Newhome"
API = "https://service.newhome.ch/api/SearchListingRequest"
HEADERS = {"Origin": "https://www.newhome.ch", "Referer": "https://www.newhome.ch/", "Accept": "application/json"}
OFFER_RENT, PROPERTY_APARTMENT, ORDER_NEWEST, PRICE_ON_REQUEST = 2, 2, 1, 5
PAGE_SIZE, MAX_PAGES = 20, 25

# newhome property sub types -> (German URL slug, our property_type)
SUBTYPES = {201: ("wohnung", "apartment"), 202: ("attikawohnung", "attic"), 203: ("dachwohnung", "attic"),
            204: ("maisonettewohnung", "maisonette"), 205: ("terrassenwohnung", "apartment"),
            206: ("studio-zimmer", "studio"), 208: ("loft", "loft"), 211: ("moeblierte-wohnung", "apartment"),
            212: ("zimmer-in-wg", "room")}
SKIP_SUBTYPES = {207}  # holiday flats
PUNCT = re.compile(r"[.,%:;\-+\"_=!?()\[\]{}/&*'|]")
LABEL_FEATURES = {"balcony": r"^balkon|^balcon", "terrace": r"^terrasse", "garden": r"^garten|^jardin",
                  "fireplace": r"kamin|chemin", "view": r"aussicht|panorama|vue"}


def _detail_url(x):
    """Same scheme as newhome's own buildDetailRouteUrl (German route names)."""
    sub = SUBTYPES.get(x.get("propertySubType"), (None,))[0]
    loc = (x.get("searchLocation") or {}).get("displayName") or x.get("city") or ""
    loc = PUNCT.sub("", loc).replace(" ", "-").replace("--", "-").lower()
    rooms = f"{float(x['rooms']):.1f}-zimmer" if x.get("rooms") else None
    parts = ["de", "mieten", "immobilien", "wohnung", sub, f"ort-{loc}" if loc else None, rooms, "detail",
             str(x["immocode"])]
    return "https://www.newhome.ch/" + "/".join(p for p in parts if p)


def _record(x):
    labels = [i.get("labels") or "" for i in x.get("images") or []]
    feats = {k: True for k, rx in LABEL_FEATURES.items() if any(re.search(rx, part.strip(), re.I)
                                                                 for lab in labels for part in lab.split(","))}
    sub = x.get("propertySubType")
    return {
        "source": NAME,
        "source_id": x["immocode"],
        "url": _detail_url(x),
        "title": x.get("title"),
        "description": "",
        "price": None if x.get("priceType") == PRICE_ON_REQUEST or not x.get("price") else int(x["price"]),
        "rooms": x.get("rooms"),
        "living_area": int(x["livingArea"]) if x.get("livingArea") else None,
        "floor": x.get("floor"),
        "street": x.get("street") or None,
        "zip": x.get("postalCode"),
        "city": x.get("city"),
        "lat": x.get("latitude"),
        "lng": x.get("longitude"),
        "year_built": x.get("constructionYear"),
        "images": [i["path"] for i in (x.get("images") or [])[:6] if i.get("path")],
        "agency": x.get("contactCompanyName"),
        "property_type": SUBTYPES.get(sub, (None, None))[1],
        "furnished": sub == 211,
        "features": feats,
    }


def scrape(http, ctx):
    # the API allows a radius of at most 20 km: one circle around the workplace, one for the
    # Lake Biel side of the area (La Neuveville, Erlach, Ins); ads outside the area are dropped later
    centers = [(f"{WORK[0]};{WORK[1]}", 20), ("47.04;7.09", 12)]
    for center, radius in centers:
        for page in range(MAX_PAGES):
            params = {"offerType": OFFER_RENT, "propertyType": PROPERTY_APARTMENT,
                      "radiusCenterCoordinate": center, "radius": radius,
                      "roomsMax": SEARCH.get("max_rooms", 3), "priceMax": SEARCH.get("max_rent", 2500),
                      "rowCount": PAGE_SIZE, "skipCount": page * PAGE_SIZE, "order": ORDER_NEWEST, "languageIso": "fr"}
            r = http.get(API, params=params, headers=HEADERS)
            if r is None:
                break
            data = r.json()
            entries = data.get("entries") or []
            for x in entries:
                if x.get("offerType") == OFFER_RENT and x.get("propertySubType") not in SKIP_SUBTYPES:
                    yield _record(x)
            if not entries or (page + 1) * PAGE_SIZE >= (data.get("totalResultCount") or 0):
                break
