"""Generic "new listing link" monitor for broker / developer / bank / small-portal websites.

Configured in config/sources.json. For every page we collect links that look
like property detail pages, read price / rooms / m² / postcode from the
surrounding card text, and drop rentals, houses and out-of-area objects.
This catches ads that a broker publishes on its own site before (or instead
of) the big portals.
"""
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from ..listing import (APARTMENT_RE, NON_APARTMENT_RE, RENT_RE, SALE_RE, clean_text,
                       extract_from_text)
from ..regions import lookup_zip, zip_for_name

CONFIG = Path(__file__).resolve().parents[2] / "config" / "sources.json"

DETAIL_HINT = re.compile(
    r"objekt|object|immobilie|immobilien/|detail|expose|angebot|listing|/o/|property|properties|"
    r"wohnung|kaufen/.+|projekt|/\d{4,}", re.I)
SKIP_HINT = re.compile(
    r"kontakt|contact|impressum|datenschutz|privacy|agb|bewert|verkaufen|sell|team|about|ueber-uns|"
    r"blog|news|jobs|karriere|login|register|newsletter|suchabo|suchprofil|faq|cookie|mieten|vermiet|"
    r"\.pdf$|\.jpg$|\.png$|mailto:|tel:|javascript:|#", re.I)


def load_config():
    return json.loads(CONFIG.read_text(encoding="utf-8"))


NAV_CLASS = re.compile(r"^(nav|navbar|navigation|menu|main-menu|mainmenu|footer|site-footer|header|site-header|"
                       r"breadcrumbs?)$|^(nav|navbar|menu|footer|breadcrumb)[-_]", re.I)


def _in_navigation(a):
    node = a
    for _ in range(6):
        node = node.parent
        if node is None:
            return False
        if any(NAV_CLASS.search(c) for c in node.get("class") or []):
            return True
    return False


PRICEISH = re.compile(r"^\s*(CHF|Fr\.|Preis|Price|ab\s+CHF|\d[\d'’ .]*$)", re.I)


def _title(card, a, href):
    for el in card.find_all(["h1", "h2", "h3", "h4", "h5", "strong", "b"]):
        t = el.get_text(" ", strip=True)
        if len(t) > 8 and not PRICEISH.search(t):
            return t
    for t in (a.get("title"), a.get_text(" ", strip=True)):
        if t and len(t) > 8 and not PRICEISH.search(t):
            return t
    slug = urlparse(href).path.rstrip("/").rsplit("/", 1)[-1]
    slug = re.sub(r"[-_]?\d{4,}$", "", slug)
    slug = re.sub(r"^\d+[a-z]{0,2}-", "", slug)
    return slug.replace("-", " ").strip().capitalize() if len(slug) > 8 else None


def _card(a, is_detail):
    """Largest ancestor of the link that still contains only this one listing."""
    own = a.get("href")
    node = a
    best = a
    for _ in range(6):
        node = node.parent
        if node is None or node.name in ("body", "html"):
            break
        txt = node.get_text(" ", strip=True)
        if len(txt) > 900:
            break
        others = {x.get("href") for x in node.find_all("a", href=True)
                  if x.get("href") != own and is_detail(x.get("href"))}
        if others:
            break
        best = node
        if re.search(r"CHF|Fr\.|Zimmer|m²|m2", txt) and len(txt) > 60:
            break
    return best


def scrape_site(http, site):
    r = http.get(site["url"], allow_404=True, delay=(2, 4))
    if r is None:
        return
    base_host = urlparse(r.url).netloc.replace("www.", "")
    allowed = {base_host} | {h.replace("www.", "") for h in site.get("hosts", [])}
    pattern = re.compile(site["link_pattern"], re.I) if site.get("link_pattern") else None
    soup = BeautifulSoup(r.text, "lxml")
    seen = set()

    def is_detail(h):
        h = (h or "").split("#")[0]
        if not h or h.rstrip("/") == site["url"].rstrip("/"):
            return False
        pth = urlparse(urljoin(r.url, h)).path + "?" + urlparse(urljoin(r.url, h)).query
        if pattern:
            return bool(pattern.search(pth))
        return bool(DETAIL_HINT.search(pth)) and not SKIP_HINT.search(pth)
    for a in soup.find_all("a", href=True):
        href = urljoin(r.url, a["href"].strip())
        p = urlparse(href)
        if p.scheme not in ("http", "https") or p.netloc.replace("www.", "") not in allowed:
            continue
        href = href.split("#")[0]
        if site.get("strip_query"):
            href = href.split("?")[0]
        if href.rstrip("/") == site["url"].rstrip("/") or href in seen:
            continue
        path = p.path + ("?" + p.query if p.query else "")
        if pattern:
            if not pattern.search(path):
                continue
        elif not DETAIL_HINT.search(path) or SKIP_HINT.search(path) or path.count("/") < 2:
            continue
        if a.find_parent(["nav", "footer"]) or _in_navigation(a):
            continue
        seen.add(href)
        card = _card(a, is_detail)
        text = clean_text(card.get_text(" ", strip=True), 900)
        if not text or len(text) < 8:
            continue
        if not pattern and not re.search(r"CHF|Fr\.\s*\d|\d\s*(?:Zimmer|Zi\b|½)|\d\s*m²|\d\s*m2|Preis auf Anfrage", text, re.I):
            continue
        if RENT_RE.search(text) and not SALE_RE.search(text):
            continue
        if NON_APARTMENT_RE.search(text) and not APARTMENT_RE.search(text):
            continue
        ex = extract_from_text(text)
        zipcode = ex.get("zip")
        if not zipcode:
            # try a municipality name in the text
            for word in re.findall(r"[A-ZÄÖÜ][a-zäöüé-]{3,}", text):
                z = zip_for_name(word)
                if z:
                    zipcode = z
                    break
        if zipcode and not lookup_zip(zipcode):
            continue
        if not zipcode and site.get("require_zip"):
            continue
        title = _title(card, a, href) or text[:90]

        img = card.find("img")
        img_src = None
        if img:
            img_src = img.get("src") or img.get("data-src") or img.get("data-lazy-src")
            if img_src and img_src.startswith("data:"):
                img_src = img.get("data-src") or img.get("data-lazy-src")
            if img_src:
                img_src = urljoin(r.url, img_src)
        yield {
            "source": "web",
            "source_id": href,
            "site": site["name"],
            "url": href,
            "title": title[:160],
            "description": text,
            "price": ex.get("price"),
            "rooms": ex.get("rooms"),
            "living_area": ex.get("living_area"),
            "zip": zipcode,
            "city": ex.get("city"),
            "images": [img_src] if img_src else [],
            "agency": site["name"],
            "canton": site.get("canton_hint"),
            "parsed_from_text": True,
        }
