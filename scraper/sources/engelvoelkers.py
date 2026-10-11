"""Engel & Völkers (Basel-City / Basel-Land shops) - Next.js __NEXT_DATA__."""
import json
import re

from ..regions import zip_for_name

NAME = "engelvoelkers"
LABEL = "Engel & Völkers"
PAGES = [
    "https://www.engelvoelkers.com/ch/de/immobilien/res/kaufen/wohnung/basel-stadt",
    "https://www.engelvoelkers.com/ch/de/immobilien/res/kaufen/wohnung/basel-landschaft",
]


def _rng(d, *keys):
    for k in keys:
        d = (d or {}).get(k)
    if isinstance(d, dict):
        return d.get("min")
    return d


def scrape(http, ctx):
    for page in PAGES:
        r = http.get(page, allow_404=True)
        if r is None:
            continue
        m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', r.text, re.S)
        if not m:
            continue
        data = json.loads(m.group(1))
        for q in data["props"]["pageProps"].get("dehydratedState", {}).get("queries", []):
            d = (q.get("state") or {}).get("data") or {}
            for wrap in d.get("listings") or []:
                l = wrap.get("listing") or {}
                if l.get("propertyMarketingType") != "sale":
                    continue
                locality = next((a["text"] for a in l.get("addressComponents") or []
                                 if a.get("placeType") == "locality"), None)
                z = zip_for_name(locality)
                rooms = _rng(l, "rooms")
                yield {
                    "source": NAME,
                    "source_id": l["id"],
                    "url": f"https://www.engelvoelkers.com/ch/de/exposes/{l['id']}",
                    "title": l.get("title") or l.get("headline") or
                             f"{rooms or ''} Zimmer {l.get('propertyType', 'Wohnung')} in {locality or ''}".strip(),
                    "description": l.get("description") or "",
                    "price": None if l.get("hasPriceOnRequest") else _rng(l, "basePrice", "salesPrice"),
                    "rooms": rooms,
                    "living_area": _rng(l, "area", "livingSurface"),
                    "bathrooms": _rng(l, "bathrooms"),
                    "zip": z,
                    "city": locality,
                    "images": [f"https://uploadcare.engelvoelkers.com/{i}/-/resize/750x/" for i in
                               (l.get("uploadCareImageIds") or [])[:6]],
                    "agency": l.get("shopName") or "Engel & Völkers",
                    "features": {"new_build": bool(l.get("isDevelopmentProject") or l.get("isDevelopmentUnit")),
                                 "terrace": bool(_rng(l, "area", "terraceSurface"))},
                }
