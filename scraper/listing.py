"""Listing helpers: parsing rents / rooms / sizes, feature extraction (French, German, English), normalisation."""
import hashlib
import html as htmllib
import re
import unicodedata

from .regions import lookup_zip, zip_for_name

# --------------------------------------------------------------------------- numbers

_NUM = "|".join([r"\d{1,3}(?:%s\d{3})+" % sep for sep in (r"[’'`´]", r"\.", r",", r" ")] + [r"\d+"])
MIN_RENT, MAX_RENT = 150, 8000  # monthly; anything else is a sale price, a parking spot or a typo


def parse_int(text):
    """"CHF 1'250.–" -> 1250 ; returns None when no number."""
    if text is None:
        return None
    if isinstance(text, (int, float)):
        return int(text)
    m = re.search(_NUM, str(text))
    if not m:
        return None
    digits = re.sub(r"\D", "", m.group(0))
    return int(digits) if digits else None


def parse_float(text):
    if text is None:
        return None
    if isinstance(text, (int, float)):
        return float(text)
    m = re.search(r"\d+(?:[.,]\d+)?", str(text))
    return float(m.group(0).replace(",", ".")) if m else None


PRICE_RE = re.compile(r"(?:CHF|Fr\.?|SFr\.?|Frs\.?)\s*(" + _NUM + r")(?:\s*[.,]\s*[-–—]+|\.00)?", re.I)
PRICE_RE2 = re.compile(r"(" + _NUM + r")\s*(?:[.,]\s*[-–—]+\s*)?(?:CHF|Fr\.|francs)", re.I)
PRICE_RE3 = re.compile(r"(?<![\d'’])(\d{1,2}[’']\d{3}|\d{3,4})\s*\.\s*[-–—]+")  # Swiss "690.-" / "1'250.--"
CHARGES_RE = re.compile(r"\+\s*(?:CHF|Fr\.?)?\s*(" + _NUM + r")\s*(?:[.,]\s*[-–—]+)?\s*(?:de\s+|d')?(?:charges|ch\.|frais|acompte|NK|Nebenkosten)"
                        r"|(?:charges|acompte de charges|frais accessoires|Nebenkosten|NK)\s*[:=]?\s*(?:CHF|Fr\.?)?\s*(" + _NUM + r")", re.I)
GROSS_RE = re.compile(r"charges\s+compris|\bc\.?\s?c\.?\b|ch\.\s*compr|tout compris|inkl\.?\s*(?:NK|Nebenkosten)|brutto|toutes charges", re.I)
ROOMS_RE = re.compile(r"(\d{1,2}(?:[.,]5)?|\d{1,2}\s*½)\s*[- ]?(?:pi[eè]ces?|pces?\b|p\.\s|Zimmer|Zi\b|Zi\.|rooms?\b|-Zimmer)", re.I)
AREA_RE = re.compile(r"(\d{2,3}(?:[.,]\d)?)\s*(?:m²|m2|qm|m\s*2\b)", re.I)
ZIP_CITY_RE = re.compile(r"\b([1-9]\d{3})\s+([A-ZÀ-ÝÄÖÜ][\w'’àâäçéèêëîïôöûüÀ-ÝÄÖÜ .()\-]{1,40})")
AREA_EXCLUDE = re.compile(r"balcon|terrasse|jardin|cave|galetas|grenier|parcelle|terrain|loggia|"
                          r"balkon|terrass|garten|keller|estrich|grundst|parzelle|sitzplatz|garage", re.I)


def clean_text(s, limit=None):
    if not s:
        return ""
    s = htmllib.unescape(str(s))
    s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"[ \t\r\f\v]+", " ", s)
    s = re.sub(r"\n\s*\n+", "\n", s).strip()
    if limit and len(s) > limit:
        s = s[:limit].rsplit(" ", 1)[0] + " …"
    return s


def fix_mojibake(s):
    if s and ("Ã" in s or "Â" in s):
        try:
            return s.encode("latin-1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            return s
    return s


def extract_rent(text):
    """-> dict(rent=..., charges=..., price=gross) from card text such as
    "CHF 1'045.-/mois (+145.- charges)" or "Loyer 850.- charges comprises"."""
    out = {}
    m = PRICE_RE.search(text) or PRICE_RE2.search(text) or PRICE_RE3.search(text)
    if not m:
        return out
    v = parse_int(m.group(1))
    if not v or not (MIN_RENT <= v <= MAX_RENT):
        return out
    out["rent"] = v
    c = CHARGES_RE.search(text[m.start():m.start() + 160])
    charges = parse_int(c.group(1) or c.group(2)) if c else None
    if charges and 0 < charges < v:
        out["charges"] = charges
        out["price"] = v + charges
        out["rent_net"] = v
    else:
        out["price"] = v
        if GROSS_RE.search(text[m.start():m.start() + 160]):
            out["charges_included"] = True
    return out


def extract_from_text(text):
    """Best-effort rent / rooms / living area / postcode from a blob of card text."""
    out = {}
    if not text:
        return out
    out.update(extract_rent(text))
    m = ROOMS_RE.search(text)
    if m:
        r = m.group(1).replace("½", ".5").replace(" ", "").replace(",", ".")
        try:
            rv = float(r)
            if 1 <= rv <= 12:
                out["rooms"] = rv
        except ValueError:
            pass
    if "rooms" not in out and re.search(r"\bstudio\b|einzimmer|1-zimmer", text, re.I):
        out["rooms"] = 1.0
    m = re.search(r"(?:surface habitable|surface|Wohnfläche|living area)[^\d]{0,20}(\d{2,3}(?:[.,]\d)?)\s*m", text, re.I)
    area = parse_float(m.group(1)) if m else None
    if not area:
        for m in AREA_RE.finditer(text):
            if AREA_EXCLUDE.search(text[max(0, m.start() - 30):m.start()]):
                continue
            area = parse_float(m.group(1))
            break
    if area and 10 <= area <= 400:
        out["living_area"] = int(round(area))
    for m in ZIP_CITY_RE.finditer(text):
        if lookup_zip(m.group(1)):
            out["zip"], out["city"] = m.group(1), m.group(2).strip()
            break
    return out


# --------------------------------------------------------------------------- features

# feature key -> regex over title + description (French / German / English)
FEATURE_PATTERNS = {
    "balcony": r"balcon|loggia|balkon|balcony",
    "terrace": r"terrasse|terrace",
    "garden": r"jardin|garten|garden|pelouse",
    "lift": r"ascenseur|\blift\b|aufzug|elevator",
    "parking": r"place[s]? de parc|garage|parking|stationnement|\bbox\b|parkplatz|einstellhalle",
    "cellar": r"\bcave\b|galetas|grenier|keller|estrich|cellar",
    "new_build": r"\bneuf\b|neuve|nouvelle construction|construction r[ée]cente|premi[eè]re location|premier occupant|neubau|erstbezug|new build",
    "renovated": r"r[ée]nov[ée]|refait|rafra[iî]chi|saniert|renoviert|renovated",
    "furnished": r"meubl[ée]|m[öo]bliert|furnished|équipé et meublé",
    "attic": r"attique|combles|mansard|sous les toits|dachwohnung|attika|penthouse",
    "maisonette": r"duplex|maisonnette|maisonette",
    "loft": r"\bloft\b",
    "view": r"vue (?:sur le |sur |imprenable|d[ée]gag[ée]e|panoramique|magnifique)|vue lac|sur le lac|seesicht|aussicht|lake view",
    "quiet": r"\bcalme\b|tranquill|ruhig|quiet",
    "fireplace": r"chemin[ée]e|po[êe]le|kamin|fireplace",
    "equipped_kitchen": r"cuisine (?:agenc[ée]e|[ée]quip[ée]e|moderne|ouverte)|einbauk[üu]che",
    "dishwasher": r"lave-vaisselle|lave vaisselle|geschirrsp[üu]ler|dishwasher",
    "own_laundry": r"lave-linge|machine [àa] laver|colonne de lavage|lave et s[èe]che|lave-linge/s[èe]che|waschmaschine|waschturm|washing machine",
    "shared_laundry": r"buanderie",
    "bathtub": r"baignoire|badewanne|bathtub",
    "accessible": r"handicap|chaise roulante|sans barri[eè]re|hindernisfrei|rollstuhl|wheelchair",
    "pets": r"animaux (?:accept|admis|bienvenu|autoris)|haustiere erlaubt|pets allowed",
    "near_transport": r"transports? publics?|arr[êe]t (?:de bus|du bus|de tram)|proche (?:de la )?gare|littorail|\btram\b|bus [àa] proximit|öv|bahnhof",
    "near_shops": r"commerces|magasins|supermarch|migros|coop\b|einkauf",
    "lake": r"\blac\b|bord du lac|see\b",
    # warnings (shown in orange, easy to exclude)
    "temporary": r"sous-location|sous location|dur[ée]e d[ée]termin[ée]e|temporaire|courte dur[ée]e|limit[ée] (?:dans le temps|[àa])|"
                 r"befristet|untermiete|temporary|sublet|de mi-|jusqu'au \d",
    "shared_flat": r"colocation|colocataire|chambre (?:dans|en) (?:un|une)|\bwg\b|wg-zimmer|flatshare|shared flat",
    "students_only": r"(?:r[ée]serv[ée]e?s?|uniquement) (?:aux|pour) [ée]tudiant|nur f[üu]r studierende|students only",
    "seniors_only": r"r[ée]serv[ée]e?s? aux (?:personnes [âa]g[ée]es|seniors|retrait[ée]s)|pour (?:personnes [âa]g[ée]es|seniors)|senioren",
    "subsidized": r"subventionn|loyer mod[ée]r[ée]|\bLUP\b|logement d'utilit[ée] publique|soumis [àa] (?:des )?conditions|sozialwohnung",
    "swap": r"[ée]change d'appartement|[ée]change de logement|tauschwohnung|wohnungstausch",
}
_FEATURE_RE = {k: re.compile(v, re.I) for k, v in FEATURE_PATTERNS.items()}
WARNINGS = ("reserved", "temporary", "shared_flat", "students_only", "seniors_only", "subsidized", "swap")

TYPE_PATTERNS = [
    ("room", r"colocation|chambre (?:meubl[ée]e |ind[ée]pendante )?[àa] louer|chambre (?:dans|en) |\bwg\b|wg-zimmer|zimmer in"),
    ("studio", r"\bstudio\b|\b1[.,]?0? ?pi[eè]ce\b|1 pce\b|einzimmer|1-zimmer|1 zimmer"),
    ("loft", r"\bloft\b"),
    ("attic", r"attique|attika|penthouse|combles"),
    ("maisonette", r"duplex|maisonnette|maisonette"),
    ("apartment", r"appartement|logement|wohnung|apartment|flat\b"),
]
NON_APARTMENT_RE = re.compile(
    r"maison individuelle|maison mitoyenne|\bmaison\b|\bvilla\b|chalet|place[s]? de parc|garage[- ]box|\bbox\b|d[ée]p[ôo]t|"
    r"\blocal\b|locaux commerciaux|surface commerciale|\bbureaux?\b|atelier|arcade|entrep[ôo]t|terrain|parking|"
    r"einfamilienhaus|reihenhaus|parkplatz|einstellhallenplatz|gewerbe|b[üu]ro|lager|\bhaus\b|\bhouse\b", re.I)
EXPLICIT_APT_RE = re.compile(r"appartement|\bstudio\b|logement|duplex|attique|\bloft\b|\d[.,]?5?\s*pi[eè]ces?|wohnung\b|apartment\b",
                             re.I)
APARTMENT_RE = EXPLICIT_APT_RE
SALE_RE = re.compile(r"[àa] vendre|prix de vente|\bvente\b|achat|kaufpreis|zu verkaufen|for sale", re.I)
RENT_RE = re.compile(r"/\s*mois|par mois|\bloyer|[àa] louer|location|charges|/\s*mt\.?|/\s*monat|pro monat|miete|vermieten|per month",
                     re.I)


def detect_features(text):
    if not text:
        return {}
    feats = {k: True for k, rx in _FEATURE_RE.items() if rx.search(text)}
    if feats.get("pets") and re.search(r"animaux (?:non|pas) (?:admis|accept|autoris)|pas d'animaux|keine haustiere", text, re.I):
        feats.pop("pets")
    if feats.get("own_laundry") and re.search(r"buanderie commune|lave-linge commun", text, re.I):
        feats.pop("own_laundry")
    return feats


def detect_type(text, rooms=None):
    for t, pat in TYPE_PATTERNS:
        if re.search(pat, text or "", re.I):
            if t == "apartment" and rooms and rooms <= 1.5:
                return "studio"
            return t
    if rooms and rooms <= 1.5:
        return "studio"
    return None


def floor_from_text(text):
    if not text:
        return None
    if re.search(r"rez-de-chauss|\brez\b|erdgeschoss|hochparterre|parterre|\bEG\b", text, re.I):
        return 0
    m = re.search(r"(\d{1,2})\s*(?:e|er|ème|eme|è)\s*[ée]tage|(\d{1,2})\.\s*(?:OG|Obergeschoss|Stock|Etage)", text, re.I)
    if m:
        return int(m.group(1) or m.group(2))
    return None


# --------------------------------------------------------------------------- normalise / duplicates

_STREET_WORDS = r"\b(?:rue|chemin|ch|avenue|av|route|rte|place|pl|quai|faubourg|fbg|impasse|imp|all[ée]e|passage|sentier|" \
                r"ruelle|clos|cit[ée]|des|du|de|la|le|les|d|l|strasse|str|weg|gasse|platz)\b"


def _plain(s):
    return "".join(c for c in unicodedata.normalize("NFKD", (s or "").lower()) if not unicodedata.combining(c))


def norm_street(s):
    s = re.sub(_STREET_WORDS, " ", _plain(s).replace("'", " "))
    return re.sub(r"[^a-z0-9]", "", s)


def norm_title(t):
    t = re.sub(r"[^a-z0-9]", "", _plain(t))
    return t[:60] if len(t) >= 15 else ""


def _prices(r):
    return {v for v in (r.get("price"), r.get("rent_net"), r.get("rent_gross")) if v}


def similar(a, b):
    """Score how likely listing-record a and property b are the same flat (0 = different)."""
    if str(a.get("zip") or "") != str(b.get("zip") or "") or not a.get("zip"):
        return 0
    sa, sb = norm_street(a.get("street")), norm_street(b.get("street"))
    street_eq = bool(sa and sa == sb and re.search(r"\d", sa))
    if sa and sb and re.search(r"\d", sa) and re.search(r"\d", sb) and not street_eq:
        return 0
    ta, tb = norm_title(a.get("title")), norm_title(b.get("title"))
    title_eq = bool(ta and ta == tb)
    hits = 0
    ra, rb = a.get("rooms"), b.get("rooms")
    if ra and rb:
        if abs(float(ra) - float(rb)) > 0.01:
            return 0
        hits += 1
    va, vb = a.get("living_area"), b.get("living_area")
    if va and vb:
        if abs(va - vb) / max(va, vb) > 0.06:
            return 0
        hits += 1
    pa, pb = _prices(a), _prices(b)
    if pa and pb:
        if not any(abs(x - y) / max(x, y) <= 0.035 for x in pa for y in pb):
            return 0
        hits += 1
    if a.get("lat") and b.get("lat") and abs(a["lat"] - b["lat"]) < 0.0006 and abs(a["lng"] - b["lng"]) < 0.0008:
        hits += 1  # same building (within ~60 m)
    score = hits + 2 * street_eq + 3 * title_eq
    return score if (title_eq or hits + street_eq >= 3) else 0


def identical(a, b):
    """Exactly the same ad content (an aggregator lists one flat twice)."""
    return (norm_title(a.get("title")) and norm_title(a.get("title")) == norm_title(b.get("title"))
            and all(a.get(k) == b.get(k) for k in ("price", "rooms", "living_area", "zip")))


def fingerprint(rec):
    """Key used to recognise the same flat advertised on several portals."""
    z = str(rec.get("zip") or "")
    rooms, area = rec.get("rooms"), rec.get("living_area")
    street = norm_street(rec.get("street"))
    if z and street and re.search(r"\d", street) and rooms:
        return f"s|{z}|{street}|{rooms}"
    if z and rooms and area:
        return f"a|{z}|{rooms}|{int(area)}"
    return None


def make_id(source, source_id):
    sid = str(source_id)
    if len(sid) > 40:
        sid = hashlib.sha1(sid.encode()).hexdigest()[:16]
    return f"{source}:{sid}"


TYPE_TITLE = {"studio": "Studio", "room": "Room", "loft": "Loft", "attic": "Attic flat", "maisonette": "Duplex"}


def finalize(rec):
    """Fill derived fields (locality + commute defaults, rent/m², features, type).
    Returns rec, or None when the ad is outside the search area or not a rental flat."""
    text_parsed = bool(rec.get("parsed_from_text"))
    if text_parsed:
        head = f"{rec.get('title') or ''} {rec.get('url') or ''} {(rec.get('description') or '')[:200]}".replace("-", " ")
        if NON_APARTMENT_RE.search(head) and not EXPLICIT_APT_RE.search(head):
            return None  # house, parking space, office ... not a flat
        desc = (rec.get("description") or "")[:400]
        if SALE_RE.search(desc) and not RENT_RE.search(desc):
            return None  # an object for sale on a broker page
    loc = lookup_zip(rec.get("zip"), rec.get("city")) if rec.get("zip") else None
    if rec.get("zip") and not loc:
        return None  # outside the search area
    if not loc and rec.get("city"):
        z = zip_for_name(rec["city"])
        loc = lookup_zip(z, rec["city"]) if z else None
        if not loc and not text_parsed:
            return None  # a portal names the town and it is outside the search area
    if loc:
        rec["zip"] = loc["zip"]
        rec.update(municipality=loc["name"], canton=loc["canton"], district=loc.get("district"))
    else:
        rec.setdefault("municipality", rec.get("city") or "")
        rec["canton"] = rec.get("canton") or "?"
    for k in ("title", "description"):
        rec[k] = fix_mojibake(clean_text(rec.get(k), 2500 if k == "description" else 200))
    rec["title"] = re.split(r"\s+(?:CHF|Fr\.)\s*[\d']|\s+Prix sur demande|\s+Loyer sur demande", rec.get("title") or "")[0].strip()
    text = f"{rec.get('title', '')}\n{rec.get('description', '')}"
    # rent: gross (incl. charges) when known
    if rec.get("rent_net") and rec.get("charges") and not rec.get("price"):
        rec["price"] = rec["rent_net"] + rec["charges"]
    p = rec.get("price")
    if p is not None and not (MIN_RENT <= p <= MAX_RENT):
        rec["price"] = p = None
    feats = detect_features(text)
    feats.update({k: v for k, v in (rec.get("features") or {}).items() if v})
    if rec.get("furnished"):
        feats["furnished"] = True
    if rec.get("temporary"):
        feats["temporary"] = True
    if re.match(r"\W*(?:r[ée]serv[ée]e?|lou[ée]e?|d[ée]j[àa] lou[ée]e?|reserviert|vermietet)\b", rec.get("title") or "", re.I):
        feats["reserved"] = True  # "RESERVE - Studio ...": already promised to someone
    rec["features"] = feats
    if rec.get("rooms") is not None:
        rec["rooms"] = float(rec["rooms"])
    if re.match(r"\s*(?:chambres?|room|zimmer|wg-zimmer|colocation)\b", rec.get("title") or "", re.I) \
            and not re.search(r"\bstudio\b|appartement", rec.get("title") or "", re.I):
        rec["property_type"] = "room"  # "Chambre meublée ...", "Chambres avec vue ..." = room in a shared flat/house
    if not rec.get("property_type"):
        rec["property_type"] = detect_type(text, rec.get("rooms")) or "apartment"
    if rec["property_type"] == "apartment" and rec.get("rooms") and rec["rooms"] <= 1.5:
        rec["property_type"] = "studio"
    if rec.get("floor") is None:
        rec["floor"] = floor_from_text(text)
    a = rec.get("living_area")
    if a and (a < 10 or a > 400 or (text_parsed and rec.get("rooms") and a < rec["rooms"] * 8)):
        rec["living_area"] = a = None
    if p and a:
        rec["price_per_m2"] = round(p / a, 1)  # CHF per m² per month
    t = rec.get("title") or ""
    if len(t) < 12 or re.fullmatch(r"\d{4}\s+[\w ()àâäçéèêëîïôöûü.'-]+", t, re.I):
        kind = TYPE_TITLE.get(rec["property_type"])
        rooms = f"{rec['rooms']:g}-room " if rec.get("rooms") and not kind else ""
        rec["title"] = f"{kind or rooms + 'apartment'} in {rec.get('municipality') or rec.get('city') or 'the area'}"
    rec["images"] = [i for i in (rec.get("images") or []) if i][:6]
    return rec
