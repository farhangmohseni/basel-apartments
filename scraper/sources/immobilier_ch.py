"""immobilier.ch - the big French-speaking-Switzerland portal (agencies, the City of Neuchâtel's own
housing office, pension funds ...). Server-rendered cards with id, exact coordinates, rent + charges.

Canton Neuchâtel pages (24 ads each, newest first) plus the localities of the area in the
cantons of Bern, Vaud and Fribourg.
"""
import json
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..listing import ROOMS_RE, extract_rent, parse_float
from ..regions import LOCALITIES, _key, slugify, zip_for_name

NAME = "immobilier_ch"
LABEL = "immobilier.ch"
BASE = "https://www.immobilier.ch"
LIST = BASE + "/fr/louer/appartement/{path}/page-{page}"
CANTON_SLUG = {"BE": "berne", "VD": "vaud", "FR": "fribourg", "NE": "neuchatel"}
DAILY_PAGES, ROTATING_PAGES, MAX_PAGES = 5, 4, 60
DELAY = (5, 9)  # the site has a firewall that challenges fast clients
CARD_RE = re.compile(r"(?:pi[eè]ces?|Studio|Loft|Duplex|Attique)\s+([A-ZÀ-Ý][^,]{1,40}),\s+(.+?\d+\s?[a-zA-Z]?)(?=\s+\d+(?:[.,]\d)?\s*m\s*2|\s*$)")


def _parse(page_html):
    soup = BeautifulSoup(page_html, "lxml")
    names = {}
    for l in re.findall(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', page_html, re.S):
        try:
            j = json.loads(l)
        except ValueError:
            continue
        if j.get("@type") == "ItemList":
            names = {e.get("url"): e.get("name") for e in j.get("itemListElement", [])}
    title = (soup.title.get_text() if soup.title else "")
    out = []
    for card in soup.select("div.filter-item[data-id]"):
        a = card.find("a", href=re.compile(r"/fr/louer/.+-\d+$"))
        if not a:
            continue
        url = urljoin(BASE, a["href"])
        parts = a["href"].strip("/").split("/")  # fr/louer/appartement/<canton>/<city>/<agency>/<slug>-<id>
        city_slug = parts[4] if len(parts) > 6 else None
        agency_slug = parts[5] if len(parts) > 6 else None
        text = re.sub(r"\s+", " ", card.get_text(" ", strip=True))
        rent = extract_rent(text)
        m = ROOMS_RE.search(text)
        rooms = parse_float(m.group(1).replace("½", ".5")) if m else (1.0 if re.search(r"\bstudio\b", text, re.I) else None)
        am = re.search(r"(\d{2,3}(?:[.,]\d)?)\s*m\s*2", text)
        cm = CARD_RE.search(text)
        latlng = (card.get("data-latlng") or "").split(",")
        img = card.find("img")
        src = None
        if img:
            for attr in ("data-src", "data-original", "data-lazy", "src"):
                v = img.get(attr)
                if v and "loading" not in v and not v.startswith("data:"):
                    src = urljoin(BASE, v)
                    break
        city = cm.group(1).strip() if cm else (city_slug or "").replace("-", " ").title()
        out.append({
            "source": NAME,
            "source_id": card["data-id"],
            "url": url,
            "title": names.get(url) or "",
            "description": text,
            "price": rent.get("price"),
            "rent_net": rent.get("rent_net"),
            "charges": rent.get("charges"),
            "rooms": rooms,
            "living_area": int(parse_float(am.group(1))) if am else None,
            "street": cm.group(2).strip() if cm else None,
            "zip": zip_for_name(city) or zip_for_name(city_slug),
            "city": city,
            "lat": float(latlng[0]) if len(latlng) == 2 and latlng[0] else None,
            "lng": float(latlng[1]) if len(latlng) == 2 and latlng[1] else None,
            "images": [src] if src else [],
            "agency": re.sub(r"-\d+$", "", agency_slug or "").replace("-", " ").title() or None,
            "furnished": bool(re.search(r"meubl", text, re.I)),
        })
    return out, title


def scrape(http, ctx):
    r = http.get(LIST.format(path="neuchatel", page=1), allow_404=True, delay=DELAY)
    if r is None:
        return
    cards, title = _parse(r.text)
    yield from cards
    t = re.search(r"([\d'’]+)\s+appartements?", title)
    pages = min(-(-int(re.sub(r"\D", "", t.group(1))) // 24), MAX_PAGES) if t else 1
    deeper = list(range(DAILY_PAGES + 1, pages + 1))
    todo = list(range(2, min(DAILY_PAGES, pages) + 1))
    if deeper:
        start = (ctx["day"] * ROTATING_PAGES) % len(deeper)
        todo += [deeper[(start + i) % len(deeper)] for i in range(min(ROTATING_PAGES, len(deeper)))]
    for page in todo:
        r = http.get(LIST.format(path="neuchatel", page=page), allow_404=True, delay=DELAY)
        if r is None:
            break
        cards, _ = _parse(r.text)
        if not cards:
            break
        yield from cards
    # localities of the area outside canton Neuchâtel (small numbers of ads), every third day
    others = sorted({(l["canton"], l["geo_name"], l["name"]) for l in LOCALITIES if l["canton"] in ("BE", "VD", "FR")})
    for i, (canton, geo_name, name) in enumerate(others):
        if (i + ctx["day"]) % 3:
            continue
        for slug in dict.fromkeys([slugify(geo_name), _key(name)]):
            r = http.get(LIST.format(path=f"{CANTON_SLUG[canton]}/{slug}", page=1), allow_404=True, delay=DELAY)
            if r is None:
                continue
            cards, title = _parse(r.text)
            if "dans le canton" in title:  # unknown slug: the site fell back to the whole canton
                continue
            yield from cards
            break
