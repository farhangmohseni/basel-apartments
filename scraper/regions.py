"""Search area: every locality within the configured driving time of the workplace.

The list (with car / public-transport times) lives in config/localities.json and is
built by `python -m scraper.tools.build_localities`.
"""
import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_DATA = json.loads((ROOT / "config" / "localities.json").read_text(encoding="utf-8"))
WORKPLACE = _DATA["workplace"]
LOCALITIES = _DATA["localities"]
OUTSIDE = _DATA.get("nearby_outside", [])  # places just outside the area (ads there are dropped)

# postcode -> locality (when several places share a postcode, the one closest by car wins)
ZIP_INFO = {}
for _l in sorted(LOCALITIES, key=lambda l: l["car_min"]):
    ZIP_INFO.setdefault(_l["zip"], _l)

_STOP = {"la", "le", "les", "de", "du", "des", "sur", "sous", "pres", "l", "d", "st", "ste", "saint", "sainte",
         "ne", "vd", "be", "fr", "bei", "am", "an", "im"}


def strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFKD", s or "") if not unicodedata.combining(c))


def slugify(name):
    """'La Chaux-de-Fonds' -> 'la-chaux-de-fonds', 'Neuchâtel' -> 'neuchatel'."""
    s = strip_accents(name).lower()
    return "-".join(p for p in re.split(r"[^a-z0-9]+", s) if p)


def _key(name):
    """Order-preserving key without articles/prepositions: 'La Chaux-de-Fonds' -> 'chaux-fonds'."""
    return "-".join(t for t in slugify(name).split("-") if t not in _STOP)


_NAME_INDEX = {}
for _fields in (("name", "geo_name"), ("municipality",)):  # place names win over (merged) municipality names
    for _l in sorted(LOCALITIES, key=lambda l: l["car_min"]):
        for _n in {_l[f] for f in _fields}:
            for k in (slugify(_n), _key(_n)):
                if k:
                    _NAME_INDEX.setdefault(k, _l["zip"])


def lookup_zip(zipcode, city=None):
    """Locality dict for a postcode inside the search area, else None. `city` picks the right place
    when several share one postcode (e.g. 2063 Fenin / Vilars / Saules / Engollon)."""
    z = re.sub(r"\D", "", str(zipcode or ""))[:4]
    if z not in ZIP_INFO:
        return None
    if city:
        k = _key(city)
        for l in LOCALITIES:
            if l["zip"] == z and _key(l["name"]) == k:
                return l
    return ZIP_INFO[z]


def zip_for_name(name):
    """'Hauterive (NE)' / 'chaux-fonds' / 'Colombier NE' -> postcode inside the area, or None."""
    if not name:
        return None
    base = re.sub(r"\(.*?\)", " ", str(name))
    return (_NAME_INDEX.get(slugify(name)) or _NAME_INDEX.get(_key(name))
            or _NAME_INDEX.get(slugify(base)) or _NAME_INDEX.get(_key(base)))


def canton_of(zipcode):
    l = lookup_zip(zipcode)
    return l["canton"] if l else None


def _norm(text):
    return re.sub(r"[-_/]+", " ", strip_accents(text or "").lower())


# place names (not merged municipality names such as "Val-de-Travers") inside and just outside the area
_PLACES = {}
for _l in OUTSIDE:
    _PLACES.setdefault(_norm(_l["name"]), None)
for _l in LOCALITIES:
    for _n in (_l["name"], _l["geo_name"]):
        _PLACES[_norm(_n)] = _l["zip"]
_REGION = "region"  # regional names say nothing precise ("Val-de-Travers" contains the village "Travers")
for _n in ("val de travers", "val de ruz", "la grande beroche", "beroche", "milvignes", "latena", "la tene",
           "entre deux lacs", "littoral", "montagnes neuchateloises", "vully les lacs", "mont vully", "seeland"):
    _PLACES[_n] = _REGION
_PLACE_RE = re.compile(r"(?<![\w])(" + "|".join(re.escape(n) for n in sorted((n for n in _PLACES if len(n) >= 4),
                                                                              key=len, reverse=True)) + r")(?![\w])")


def place_in_text(text):
    """First place of the region named in a text or URL -> ("in", postcode) / ("out", name) / None."""
    for m in _PLACE_RE.finditer(_norm(text)):
        z = _PLACES[m.group(1)]
        if z == _REGION:
            continue
        return ("in", z) if z else ("out", m.group(1))
    return None


def find_locality_in_text(text):
    """Postcode of the first area locality named in a free text, or None (also when the place is outside)."""
    hit = place_in_text(text)
    return hit[1] if hit and hit[0] == "in" else None
