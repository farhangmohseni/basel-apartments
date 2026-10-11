"""alle-immobilien.ch - an SMG "satellite" that renders Homegate / ImmoScout24 ads server-side.

Homegate and ImmoScout24 block automated requests outright, so this is how we
discover their ads directly. IMPORTANT: the satellite serves *distorted*
numbers to bots (prices/areas scaled), so we only keep title, address, photo
and the link to the original ad; numbers come from the aggregators when the
same ad is matched there.
"""
import re

from bs4 import BeautifulSoup

NAME = "homegate_is24"
LABEL = "Homegate / ImmoScout24 (via alle-immobilien.ch)"
PAGES = {
    "https://www.alle-immobilien.ch/de/kaufen/wohnung/kanton-basel-stadt": 8,
    "https://www.alle-immobilien.ch/de/kaufen/wohnung/kanton-baselland": 12,
}


def scrape(http, ctx):
    for base, max_pages in PAGES.items():
        for page in range(1, max_pages + 1):
            r = http.get(base, params={"pageNum": page} if page > 1 else None, allow_404=True)
            if r is None:
                break
            soup = BeautifulSoup(r.text, "lxml")
            cards = soup.select("a.search-results__list__item")
            if not cards:
                break
            for a in cards:
                ad_id = a.get("data-ad-id")
                href = (a.get("href") or "").split("?")[0]
                if not ad_id or not href:
                    continue
                title_el = a.select_one(".search-results__list__item__meta__title")
                desc_el = a.select_one(".search-results__list__item__meta__description")
                addr_el = a.select_one(".tag__address")
                addr = addr_el.get_text(" ", strip=True).replace("Adresse", "").strip() if addr_el else ""
                m = re.search(r"(.*?)\s*(\d{4})\s+(.+)$", addr)
                img = a.select_one("img")
                portal = "Homegate" if "homegate" in href else "ImmoScout24"
                yield {
                    "source": NAME,
                    "source_id": ad_id,
                    "url": href,
                    "title": title_el.get_text(" ", strip=True) if title_el else f"Wohnung ({portal})",
                    "description": desc_el.get_text(" ", strip=True) if desc_el else "",
                    "street": (m.group(1).strip() or None) if m else None,
                    "zip": m.group(2) if m else None,
                    "city": m.group(3).strip() if m else None,
                    "images": [img["src"]] if img and img.get("src") else [],
                    "origin": portal,
                    "numbers_hidden": True,
                }
