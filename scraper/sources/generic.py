"""Generic "new listing link" monitor for property-manager (régie) / agency / city websites.

Configured in config/sources.json ("sites"). For every page we collect links that look
like property detail pages, read rent / rooms / m² / postcode from the surrounding card
text, and drop objects for sale, houses, parking spaces, offices and out-of-area objects.
This catches flats that a régie publishes on its own website before (or instead of)
the big portals.
"""
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from ..listing import (APARTMENT_RE, NON_APARTMENT_RE, RENT_RE, SALE_RE, clean_text,
                       extract_from_text)
from ..regions import lookup_zip, place_in_text

CONFIG = Path(__file__).resolve().parents[2] / "config" / "sources.json"
GARAGE_PATH = re.compile(r"garage|parking|place-de-parc|depot|local-commercial|bureau|commerce/", re.I)

DETAIL_HINT = re.compile(
    r"objet|object|objekt|immobili|detail|annonce|listing|/o/|propert|bien|logement|appartement|studio|"
    r"location/.+|louer/.+|wohnung|/\d{3,}", re.I)
SKIP_HINT = re.compile(
    r"contact|kontakt|mentions|impressum|confidentialit|protection-des-donnees|datenschutz|privacy|cookie|"
    r"vendre|vente|acheter|achat|kaufen|verkauf|estimation|bewert|equipe|team|a-propos|qui-sommes|about|"
    r"blog|actualit|news|emploi|jobs|carriere|karriere|login|connexion|inscription|register|newsletter|"
    r"faq|formulaire|demande-de-location|parking|place-de-parc|commercial|bureau|"
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


PRICEISH = re.compile(r"^\s*(CHF|Fr\.|Prix|Loyer|Preis|Price|d[èe]s\s+CHF|\d[\d'’ .]*$)", re.I)


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
        if re.search(r"CHF|Fr\.|pi[eè]ces?|Zimmer|m²|m2|loyer", txt, re.I) and len(txt) > 60:
            break
    return best


ZIP_ANY_RE = re.compile(r"\b([1-9]\d{3})\s+([A-ZÀ-Ý][\w'’àâäçéèêëîïôöûü .()\-]{2,40})")
MAX_DETAIL_FETCHES = 8  # per site and run, only for links never seen before


def _place(url_path, text):
    """('in', zip) / ('out', name) / None: town from the link URL first, then a postcode, then a town name."""
    hit = place_in_text(url_path)
    if hit:
        return hit
    for m in ZIP_ANY_RE.finditer(text):
        z = m.group(1)
        if lookup_zip(z):
            return ("in", z)
        named = place_in_text(m.group(2))
        if named:  # "2123 St-Sulpice": a real postcode of a known place outside the area
            return named
    return place_in_text(text)


def _detail_text(http, url):
    r = http.get(url, allow_404=True, delay=(2, 4))
    if r is None:
        return ""
    soup = BeautifulSoup(r.text, "lxml")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    main = soup.find("main") or soup.find("article") or soup.body or soup
    return clean_text(main.get_text(" ", strip=True), 4000)


def scrape_site(http, site, known=frozenset()):
    r = http.get(site["url"], allow_404=True, delay=(2, 4))
    if r is None:
        return
    base_host = urlparse(r.url).netloc.replace("www.", "")
    allowed = {base_host} | {h.replace("www.", "") for h in site.get("hosts", [])}
    pattern = re.compile(site["link_pattern"], re.I) if site.get("link_pattern") else None
    soup = BeautifulSoup(r.text, "lxml")
    seen = set()
    details_left = MAX_DETAIL_FETCHES

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
        if GARAGE_PATH.search(path) or a.find_parent(["nav", "footer"]) or _in_navigation(a):
            continue
        seen.add(href)
        card = _card(a, is_detail)
        text = clean_text(card.get_text(" ", strip=True), 900)
        if not text or len(text) < 8:
            continue
        if not pattern and not re.search(r"CHF|Fr\.\s*\d|\d\s*(?:pi[eè]ces?|pces?|Zimmer|½)|\d\s*m²|\d\s*m2|\bstudio\b|loyer",
                                         text, re.I):
            continue
        if SALE_RE.search(text) and not RENT_RE.search(text):
            continue  # object for sale
        if NON_APARTMENT_RE.search(text) and not APARTMENT_RE.search(text):
            continue
        ex = extract_from_text(text)
        place = _place(path, text)
        if (not place or not ex.get("price")) and href not in known and details_left > 0:
            details_left -= 1  # read the ad page once to find its town / rent
            detail = _detail_text(http, href)
            if detail:
                more = extract_from_text(detail)
                for k, v in more.items():
                    ex.setdefault(k, v)
                place = place or _place("", detail)
        if place and place[0] == "out":
            continue  # outside the search area
        zipcode = place[1] if place else None
        if not zipcode and site.get("require_zip", True):
            continue  # without a town there is no commute time - skip (a site can opt out)
        if ex.get("price") and ex["price"] < 300 and not re.search(r"chambre|colocation|room", text, re.I):
            continue  # parking space / garage / storage
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
            "rent_net": ex.get("rent_net"),
            "charges": ex.get("charges"),
            "rooms": ex.get("rooms"),
            "living_area": ex.get("living_area"),
            "zip": zipcode,
            "city": None,
            "images": [img_src] if img_src else [],
            "agency": site["name"],
            "parsed_from_text": True,
        }
