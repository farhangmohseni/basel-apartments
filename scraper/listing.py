"""Listing helpers: parsing numbers, feature extraction from free text, normalisation."""
import hashlib
import html as htmllib
import re

from .regions import lookup_zip

# --------------------------------------------------------------------------- numbers

_NUM = "|".join([r"\d{1,3}(?:%s\d{3})+" % sep for sep in (r"[’'`´]", r"\.", r",", r" ")] + [r"\d+"])


def parse_int(text):
    """'CHF 1'250'000.–' -> 1250000 ; returns None when no number."""
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


PRICE_RE = re.compile(r"(?:CHF|Fr\.|SFr\.?)\s*(" + _NUM + r")(?:\.[-–—]+|\.00)?", re.I)
PRICE_RE2 = re.compile(r"(" + _NUM + r")\s*(?:CHF|Fr\.)", re.I)
ROOMS_RE = re.compile(r"(\d{1,2}(?:[.,]5)?|\d{1,2}\s*½)\s*[- ]?(?:Zimmer|Zi\b|Zi\.|rooms?\b|pièces?|pcs\b|Zimmerwohnung|-Zimmer)", re.I)
AREA_RE = re.compile(r"(\d{2,4}(?:[.,]\d)?)\s*(?:m²|m2|qm|m\s*2\b)", re.I)
ZIP_CITY_RE = re.compile(r"\b(4\d{3}|2814)\s+([A-ZÄÖÜ][\wäöüéèÄÖÜ .()-]{1,40})")


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


def extract_from_text(text):
    """Best-effort price / rooms / area / zip from a blob of card text."""
    out = {}
    if not text:
        return out
    m = PRICE_RE.search(text) or PRICE_RE2.search(text)
    if m:
        v = parse_int(m.group(1))
        if v and 50_000 <= v <= 40_000_000:  # ignore rents / parking etc.
            out["price"] = v
    m = ROOMS_RE.search(text)
    if m:
        r = m.group(1).replace("½", ".5").replace(" ", "").replace(",", ".")
        try:
            rv = float(r)
            if 1 <= rv <= 15:
                out["rooms"] = rv
        except ValueError:
            pass
    if "rooms" not in out:
        # widget cards (Immomig) print "… 129 m² [205 m²] 4.5 1" without the word "Zimmer"
        m = re.search(r"m²\s+(?:~?\s*[\d'.]+\s*m²\s+)?(\d{1,2}(?:\.5)?)\s", text + " ")
        if m and 1 <= float(m.group(1)) <= 12:
            out["rooms"] = float(m.group(1))
    m = re.search(r"(?:Wohnfläche|Wohnflaeche|Nettowohnfläche|NWF|BWF|living area|surface habitable)[^\d]{0,25}(\d{2,4}(?:[.,]\d)?)", text, re.I)
    area = parse_float(m.group(1)) if m else None
    if not area:
        for m in AREA_RE.finditer(text):
            before = text[max(0, m.start() - 30):m.start()].lower()
            if re.search(r"balkon|terrass|garten|grundst|parzelle|land|keller|loggia|sitzplatz|estrich|hobby|reduit|plot|garage", before):
                continue
            area = parse_float(m.group(1))
            break
    if area and 20 <= area <= 1500:
        out["living_area"] = int(round(area))
    m = ZIP_CITY_RE.search(text)
    if m:
        out["zip"] = m.group(1)
        out["city"] = m.group(2).strip()
    return out


# --------------------------------------------------------------------------- features

# feature key -> regex over title + description (German / English / French)
FEATURE_PATTERNS = {
    "balcony": r"balkon|balcon|balcony|loggia",
    "terrace": r"terrass|dachterrasse|terrace",
    "garden": r"garten|gartensitzplatz|jardin|garden|gartenanteil",
    "lift": r"\blift\b|aufzug|ascenseur|elevator|personenlift",
    "parking": r"parkplatz|einstellhalle|tiefgarage|garage|autoeinstell|parking|abstellplatz|\bEHP\b|\bPP\b",
    "cellar": r"keller|kellerabteil|cave\b|cellar|estrich",
    "new_build": r"neubau|erstbezug|neubauprojekt|new build|newly built|nouvelle construction|bezugsbereit ab|baustart|projekt\b|im bau",
    "renovated": r"saniert|renoviert|totalsaniert|modernisiert|renovated|rénové|kernsaniert",
    "attic": r"attika|penthouse|dachwohnung|dachgeschoss|attique",
    "maisonette": r"maisonette|duplex",
    "loft": r"\bloft\b",
    "ground_floor": r"erdgeschoss|parterre|hochparterre|rez-de-chaussée|ground floor|\bEG\b",
    "view": r"aussicht|weitsicht|fernsicht|seesicht|rheinblick|blick auf|vue\b|view",
    "quiet": r"ruhig|ruhige lage|calme|quiet",
    "fireplace": r"cheminée|cheminee|kamin|schwedenofen|fireplace",
    "minergie": r"minergie|wärmepumpe|erdsonde|photovoltaik|solaranlage|fernwärme|heat pump",
    "own_laundry": r"waschturm|eigene waschmaschine|waschmaschine und tumbler|eigener waschturm|washing machine",
    "accessible": r"rollstuhl|hindernisfrei|barrierefrei|altersgerecht|accessible|schwellenlos",
    "pets": r"haustiere|pets allowed|animaux",
    "two_bathrooms": r"zwei nasszellen|2 nasszellen|zwei badezimmer|2 badezimmer|2 bäder|zwei bäder|bad/wc und dusche/wc|separates gäste-wc|gäste-wc",
    "storage": r"reduit|réduit|abstellraum|storage room",
    "family": r"familien|kinderfreundlich|schulen|kindergarten",
    "near_transport": r"tram|bushaltestelle|bahnhof|s-bahn|öv\b|öffentlichen verkehr|public transport",
    "investment_rented": r"vermietet|rendite|kapitalanlage|anlageobjekt|investment|renditeobjekt",
    "leasehold": r"baurecht|droit de superficie|leasehold",
    "auction": r"versteigerung|auktion|gant\b|auction",
    "reserved": r"reserviert|verkauft\b|sold\b|réservé",
}
_FEATURE_RE = {k: re.compile(v, re.I) for k, v in FEATURE_PATTERNS.items()}

TYPE_PATTERNS = [
    ("attic", r"attika|penthouse"),
    ("maisonette", r"maisonette|duplex"),
    ("loft", r"\bloft\b"),
    ("garden_apartment", r"gartenwohnung|garden apartment"),
    ("studio", r"studio\b|1-zimmer|1 zimmer|1\.5-zimmer"),
    ("apartment", r"wohnung|apartment|appartement|eigentumswohnung|stockwerkeigentum|stwe"),
]
NON_APARTMENT_RE = re.compile(
    r"^haus\b|häuser\b|haeuser\b|\bhaus (?:in|mit|an)\b|\bhouse\b|familienhaus|generationenhaus|reihenhaus|doppelhaus|villa\b|geschäftsgebäude|landhaus|herrenhaus|"
    r"bauland|grundstück|gewerbe|büro|lager|parkplatz|einstellhallenplatz|garagenbox|"
    r"wohn- und geschäftshaus|geschäftshaus|bauernhaus|chalet|ferienhaus|terrain|maison individuelle", re.I)
APARTMENT_RE = re.compile(r"wohnung|attika|maisonette|loft|apartment|appartement|stockwerkeigentum|\bSTWE\b|\d[.,]?5?\s*-?\s*zimmer", re.I)
# any "...wohnung" compound in singular (Geschosswohnung, Terrassenwohnung) - plural "3 Wohnungen" means a building
EXPLICIT_APT_RE = re.compile(r"wohnung\b|eigentumswohnungen|neubauwohnungen|attika|maisonette|\bloft\b|stockwerkeigentum|penthouse|apartment\b|appartement\b", re.I)
SALE_RE = re.compile(r"kaufpreis|verkaufspreis|zu verkaufen|\bkaufen\b|\bverkauf\b|for sale|à vendre", re.I)
RENT_RE = re.compile(r"/\s*mt\.?|/\s*monat|pro monat|monatlich|mietzins|zu vermieten|\bmieten\b|nettomiete|bruttomiete|/month|par mois|\bmiete\b", re.I)


def detect_features(text):
    if not text:
        return {}
    return {k: True for k, rx in _FEATURE_RE.items() if rx.search(text)}


def detect_type(text):
    for t, pat in TYPE_PATTERNS:
        if re.search(pat, text or "", re.I):
            return t
    return None


def floor_from_text(text):
    if not text:
        return None
    if re.search(r"erdgeschoss|hochparterre|parterre|\bEG\b|rez-de-chauss", text, re.I):
        return 0
    m = re.search(r"(\d{1,2})\.\s*(?:OG|Obergeschoss|Stock|Etage|étage)", text, re.I)
    if m:
        return int(m.group(1))
    return None


# --------------------------------------------------------------------------- normalise

def norm_street(s):
    if not s:
        return ""
    s = s.lower()
    s = s.replace("strasse", "str").replace("straße", "str").replace("str.", "str")
    s = re.sub(r"[^a-z0-9äöü]", "", s)
    return s


def norm_title(t):
    t = re.sub(r"[^a-z0-9äöü]", "", (t or "").lower())
    return t[:60] if len(t) >= 15 else ""


def similar(a, b):
    """Score how likely listing-record a and property b are the same apartment (0 = different)."""
    if str(a.get("zip") or "") != str(b.get("zip") or "") or not a.get("zip"):
        return 0
    sa, sb = norm_street(a.get("street")), norm_street(b.get("street"))
    street_eq = bool(sa and sa == sb and re.search(r"\d", sa))
    if sa and sb and re.search(r"\d", sa) and re.search(r"\d", sb) and not street_eq:
        return 0
    ta, tb = norm_title(a.get("title")), norm_title(b.get("title"))
    title_eq = bool(ta and ta == tb)
    if a.get("numbers_hidden") or b.get("numbers_hidden"):
        return 3 * title_eq + 2 * street_eq
    hits = 0
    ra, rb = a.get("rooms"), b.get("rooms")
    if ra and rb:
        if abs(float(ra) - float(rb)) > 0.01:
            return 0
        hits += 1
    for k, tol in (("living_area", 0.04), ("price", 0.035)):
        va, vb = a.get(k), b.get(k)
        if va and vb:
            if abs(va - vb) / max(va, vb) > tol:
                return 0
            hits += 1
    score = hits + 2 * street_eq + 3 * title_eq
    return score if (title_eq or hits + street_eq >= 3) else 0


def identical(a, b):
    """Exactly the same ad content (the aggregator lists one flat twice)."""
    return (norm_title(a.get("title")) and norm_title(a.get("title")) == norm_title(b.get("title"))
            and all(a.get(k) == b.get(k) for k in ("price", "rooms", "living_area", "zip")))


def fingerprint(rec):
    """Key used to recognise the same apartment advertised on several portals."""
    z = str(rec.get("zip") or "")
    rooms = rec.get("rooms")
    area = rec.get("living_area")
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


def finalize(rec):
    """Fill derived fields: location info, price/m², features, type. Returns rec or None if out of area."""
    if rec.get("parsed_from_text"):
        # broker pages mix all property types; portals were already queried in their apartment category
        head = f"{rec.get('title') or ''} {rec.get('url') or ''} {(rec.get('description') or '')[:200]}".replace("-", " ")
        if NON_APARTMENT_RE.search(head) and not EXPLICIT_APT_RE.search(head):
            return None  # a house / plot / commercial object, not an apartment
    if rec.get("parsed_from_text") and RENT_RE.search((rec.get("description") or "")[:400]) \
            and not SALE_RE.search((rec.get("description") or "")[:400]):
        return None  # rental ad on a broker page
    z = rec.get("zip")
    info = lookup_zip(z) if z else None
    if z and not info:
        return None  # outside Basel-Stadt / Basel-Landschaft
    if info:
        rec["zip"] = str(z)[:4]
        rec["municipality"] = info["municipality"]
        rec["canton"] = info["canton"]
        rec["district"] = info["district"]
    else:
        rec.setdefault("municipality", rec.get("city") or "")
        rec["canton"] = rec.get("canton") or "?"
    for k in ("title", "description"):
        rec[k] = fix_mojibake(clean_text(rec.get(k), 2500 if k == "description" else 200))
    t = re.split(r"\s+(?:CHF|Fr\.)\s*[\d']|\s+Preis auf Anfrage", rec.get("title") or "")[0].strip()
    rec["title"] = t
    if len(t) < 12 or re.fullmatch(r"\d{4}\s+[\w ()äöüÄÖÜ.-]+", t):
        rooms = f"{rec['rooms']:g}-room " if rec.get("rooms") else ""
        rec["title"] = f"{rooms}apartment in {rec.get('municipality') or rec.get('city') or 'Basel area'}"
    text = f"{rec.get('title', '')}\n{rec.get('description', '')}"
    feats = detect_features(text)
    feats.update({k: v for k, v in (rec.get("features") or {}).items() if v})
    rec["features"] = feats
    if not rec.get("property_type"):
        rec["property_type"] = detect_type(text) or "apartment"
    if rec.get("floor") is None:
        rec["floor"] = floor_from_text(text)
    p, a = rec.get("price"), rec.get("living_area")
    text_parsed = rec.get("source") in ("tutti", "web")
    lo, hi = (3000, 25000) if text_parsed else (1500, 40000)
    if a and ((p and not (lo <= p / a <= hi)) or (text_parsed and rec.get("rooms") and a < rec["rooms"] * 14)):
        rec["living_area"] = a = None  # balcony / plot size misread as living area
    if p and a:
        rec["price_per_m2"] = int(round(p / a))
    if rec.get("rooms") is not None:
        rec["rooms"] = float(rec["rooms"])
    rec["images"] = [i for i in (rec.get("images") or []) if i][:6]
    return rec
