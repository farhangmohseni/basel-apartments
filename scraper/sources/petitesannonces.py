"""petitesannonces.ch - free classifieds of French-speaking Switzerland (many private landlords and
lease take-overs, "reprise de bail"). Category "Immobilier > Location" per canton; the list pages
show postcode, address, type, rooms, m², rent and date; titles come from the RSS feed.
"""
import datetime as dt
import html as htmllib
import re

from bs4 import BeautifulSoup

from ..listing import parse_float, parse_int
from ..regions import lookup_zip

NAME = "petitesannonces"
LABEL = "petitesannonces.ch"
BASE = "https://www.petitesannonces.ch"
# category ids of "Immobilier > Location > <canton>": pages read per run (newest first)
CATEGORIES = {270113: 4, 270106: 2, 270124: 2, 270107: 1}  # Neuchâtel, Berne, Vaud, Fribourg
TYPES = {"appartement": "apartment", "studio": "studio", "chambre": "room", "loft": "loft", "duplex": "maisonette",
         "attique": "attic", "colocation": "room", "meublé": "apartment"}


def _titles(http, cat):
    r = http.get(f"{BASE}/rss/a/r.php", params={"id": cat}, allow_404=True)
    if r is None:
        return {}
    out = {}
    for item in re.findall(r"<item>(.*?)</item>", r.text, re.S):
        t = re.search(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", item, re.S)
        l = re.search(r"/a/(\d+)", item)
        if t and l:
            out[l.group(1)] = htmllib.unescape(t.group(1)).strip()
    return out


def _date(ddmm):
    try:
        d, m = map(int, ddmm.split(".")[:2])
        today = dt.date.today()
        year = today.year if (m, d) <= (today.month, today.day) else today.year - 1
        return dt.date(year, m, d).isoformat()
    except (ValueError, AttributeError):
        return None


def scrape(http, ctx):
    for cat, pages in CATEGORIES.items():
        titles = _titles(http, cat)
        for page in range(1, pages + 1):
            r = http.get(f"{BASE}/r/{cat}", params={"p": page} if page > 1 else None, allow_404=True)
            if r is None:
                break
            rows = BeautifulSoup(r.text, "lxml").select("div.ele")
            if not rows:
                break
            for row in rows:
                link = row.select_one("div.elm a[href^='/a/']")
                if not link:
                    continue
                ad_id = link["href"].split("/")[-1]
                place = link.get_text(" ", strip=True)  # "2034 Peseux, Rue des Uttins 7"
                m = re.match(r"(\d{4})\s+([^,]+)(?:,\s*(.*))?", place)
                if not m or not lookup_zip(m.group(1)):
                    continue
                cell = lambda cls: (row.select_one(f"div.{cls}").get_text(" ", strip=True) if row.select_one(f"div.{cls}") else "")
                kind = cell("elht").lower()
                ptype = next((v for k, v in TYPES.items() if k in kind), None)
                if not ptype:
                    continue  # offices, parking spaces, houses, storage ...
                img = row.select_one("img")
                yield {
                    "source": NAME,
                    "source_id": ad_id,
                    "url": f"{BASE}/a/{ad_id}",
                    "title": titles.get(ad_id) or "",
                    "description": f"{cell('elht')} {place}",
                    "price": parse_int(cell("elsp")),
                    "rooms": parse_float(cell("elhr")),
                    "living_area": parse_int(cell("elhs")),
                    "street": m.group(3),
                    "zip": m.group(1),
                    "city": m.group(2).strip(),
                    "images": [BASE + img["src"]] if img and img.get("src", "").startswith("/") else [],
                    "agency": "private / petitesannonces.ch",
                    "property_type": ptype,
                    "published": _date(cell("elss")),
                    "private_seller": True,
                }
