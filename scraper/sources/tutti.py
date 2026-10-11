"""tutti.ch (incl. ricardo / anibis real-estate ads) - many private sellers.

The search URL carries a msgpack+base64 token. We filter "apartment" + "BUY"
and use a free-text location query per town, then keep only BS/BL postcodes.
"""
import base64
import json
import re

import msgpack

from ..listing import extract_from_text, parse_int

NAME = "tutti"
LABEL = "tutti.ch / anibis"
QUERIES = ["basel", "riehen", "baselland", "allschwil", "binningen", "reinach", "muttenz", "münchenstein",
           "pratteln", "liestal", "oberwil", "therwil", "aesch", "arlesheim", "birsfelden", "bottmingen",
           "sissach", "gelterkinden", "laufen", "frenkendorf"]


def _token(query):
    v = [query, "realEstate", [[["listingType", "apartment"], ["priceType", "BUY"]], None, None, None]]
    return "A" + base64.urlsafe_b64encode(msgpack.packb(v)).decode().rstrip("=")


def scrape(http, ctx):
    seen = set()
    for q in QUERIES:
        r = http.get(f"https://www.tutti.ch/de/q/immobilien-wohnungen/{_token(q)}", allow_404=True)
        if r is None:
            continue
        m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', r.text, re.S)
        if not m:
            continue
        data = json.loads(m.group(1))
        try:
            edges = data["props"]["pageProps"]["dehydratedState"]["queries"][0]["state"]["data"]["listings"]["edges"]
        except (KeyError, IndexError, TypeError):
            continue
        for e in edges:
            n = e.get("node") or {}
            lid = n.get("listingID")
            if not lid or lid in seen:
                continue
            seen.add(lid)
            loc = n.get("localization") or {}
            pc = n.get("postcodeInformation") or {}
            text = f"{loc.get('title', '')}\n{loc.get('body', '')}"
            ex = extract_from_text(text)
            price = parse_int(n.get("formattedPrice"))
            slug = (n.get("seoInformation") or {}).get("deSlug") or "immobilien"
            thumb = ((n.get("thumbnail") or {}).get("retinaRendition") or {}).get("src")
            seller = (n.get("sellerInfo") or {}).get("alias")
            src = (n.get("source") or {}).get("id") or "tutti"
            yield {
                "source": NAME,
                "source_id": lid,
                "url": f"https://www.tutti.ch/de/vi/{slug}/{lid}",
                "title": loc.get("title"),
                "description": loc.get("body"),
                "price": price if price and price > 50_000 else ex.get("price"),
                "rooms": ex.get("rooms"),
                "living_area": ex.get("living_area"),
                "zip": pc.get("postcode"),
                "city": pc.get("locationName"),
                "images": [thumb] if thumb else [],
                "agency": f"{seller} (via {src})" if seller else src,
                "published": n.get("timestamp"),
                "private_seller": not (n.get("sellerInfo") or {}).get("logoURL"),
            }
