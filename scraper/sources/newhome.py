"""newhome.ch - the cantonal banks' portal (BLKB, BKB, ... and many local brokers).

The website is an Angular app; its data comes from a ServiceStack JSON API at
service.newhome.ch (request DTO name = URL path). We resolve the two cantons,
then page through "apartments to buy, newest first" (max. 20 per page).
"""
import re

NAME = "newhome"
LABEL = "Newhome"
API = "https://service.newhome.ch/api/"
HEADERS = {"Origin": "https://www.newhome.ch", "Referer": "https://www.newhome.ch/", "Accept": "application/json"}
CANTONS = {"kanton-basel-stadt": "4;6", "kanton-basel-landschaft": "4;5"}  # fallback identifiers
OFFER_BUY, PROPERTY_APARTMENT, ORDER_NEWEST, PRICE_ON_REQUEST = 1, 2, 1, 5
PAGE_SIZE, MAX_PAGES = 20, 30

# property sub types (newhome enum) -> URL slug and our property_type
SUBTYPES = {201: ("wohnung", "apartment"), 202: ("attikawohnung", "attic"), 203: ("dachwohnung", "attic"),
            204: ("maisonettewohnung", "maisonette"), 205: ("terrassenwohnung", "apartment"),
            206: ("studio-zimmer", "studio"), 207: ("ferienwohnung", "apartment"), 208: ("loft", "loft")}
SKIP_SUBTYPES = {207, 211, 212}  # holiday flats, furnished rentals, flat-share rooms
PUNCT = re.compile(r"[.,%:;\-+\"_=!?()\[\]{}/&*'|]")
# AI photo labels ("Balkon - Blick auf ...") -> features
LABEL_FEATURES = {"balcony": r"^balkon", "terrace": r"^terrasse|dachterrasse", "garden": r"^garten",
                  "fireplace": r"kamin|chemin", "view": r"aussicht|panorama"}


def _detail_url(x):
    """Same scheme as newhome's buildDetailRouteUrl: /de/kaufen/immobilien/wohnung/<subtype>/ort-<city>/<rooms>-zimmer/detail/<id>"""
    sub = SUBTYPES.get(x.get("propertySubType"), (None,))[0]
    loc = (x.get("searchLocation") or {}).get("displayName") or x.get("city") or ""
    loc = PUNCT.sub("", loc).replace(" ", "-").replace("--", "-").lower()
    rooms = f"{float(x['rooms']):.1f}-zimmer" if x.get("rooms") else None
    parts = ["de", "kaufen", "immobilien", "wohnung", sub, f"ort-{loc}" if loc else None, rooms, "detail",
             str(x["immocode"])]
    return "https://www.newhome.ch/" + "/".join(p for p in parts if p)


def _location_ids(http):
    ids = {}
    for keyword, fallback in CANTONS.items():
        r = http.get(API + "LocationResolveRequest", params={"keyword": keyword}, headers=HEADERS, allow_404=True)
        ids[keyword] = (r.json().get("identifier") if r is not None else None) or fallback
    return ids.values()


def _record(x):
    labels = " | ".join(i.get("labels") or "" for i in x.get("images") or [])
    feats = {k: True for k, rx in LABEL_FEATURES.items()
             if any(re.search(rx, part.strip(), re.I) for part in labels.split("|"))}
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
        "features": feats,
    }


def scrape(http, ctx):
    for location in _location_ids(http):
        for page in range(MAX_PAGES):
            params = {"offerType": OFFER_BUY, "propertyType": PROPERTY_APARTMENT, "location": location,
                      "rowCount": PAGE_SIZE, "skipCount": page * PAGE_SIZE, "order": ORDER_NEWEST,
                      "languageIso": "de"}
            r = http.get(API + "SearchListingRequest", params=params, headers=HEADERS)
            if r is None:
                break
            data = r.json()
            entries = data.get("entries") or []
            for x in entries:
                if x.get("offerType") == OFFER_BUY and x.get("propertySubType") not in SKIP_SUBTYPES:
                    yield _record(x)
            if not entries or (page + 1) * PAGE_SIZE >= (data.get("totalResultCount") or 0):
                break
