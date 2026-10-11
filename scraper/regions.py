"""Municipalities of Basel-Stadt (BS) and Basel-Landschaft (BL) with postcodes.

Used to (a) decide whether a listing is inside the search area and
(b) build per-municipality search URLs for the portals.
"""

# (name, canton, district, [postcodes])
MUNICIPALITIES = [
    # --- Basel-Stadt ---
    ("Basel", "BS", "Basel", [4000, 4001, 4002, 4003, 4005, 4009, 4010, 4018, 4019, 4020, 4030, 4031, 4039,
                              4051, 4052, 4053, 4054, 4055, 4056, 4057, 4058, 4059]),
    ("Riehen", "BS", "Basel", [4125]),
    ("Bettingen", "BS", "Basel", [4126]),
    # --- Basel-Landschaft: Bezirk Arlesheim ---
    ("Aesch", "BL", "Arlesheim", [4147]),
    ("Allschwil", "BL", "Arlesheim", [4123]),
    ("Arlesheim", "BL", "Arlesheim", [4144]),
    ("Biel-Benken", "BL", "Arlesheim", [4105]),
    ("Binningen", "BL", "Arlesheim", [4102]),
    ("Birsfelden", "BL", "Arlesheim", [4127]),
    ("Bottmingen", "BL", "Arlesheim", [4103]),
    ("Ettingen", "BL", "Arlesheim", [4107]),
    ("Münchenstein", "BL", "Arlesheim", [4142]),
    ("Muttenz", "BL", "Arlesheim", [4132]),
    ("Oberwil", "BL", "Arlesheim", [4104]),
    ("Pfeffingen", "BL", "Arlesheim", [4148]),
    ("Reinach", "BL", "Arlesheim", [4153]),
    ("Schönenbuch", "BL", "Arlesheim", [4124]),
    ("Therwil", "BL", "Arlesheim", [4106]),
    # --- Bezirk Laufen ---
    ("Blauen", "BL", "Laufen", [4223]),
    ("Brislach", "BL", "Laufen", [4225]),
    ("Burg im Leimental", "BL", "Laufen", [4117]),
    ("Dittingen", "BL", "Laufen", [4243]),
    ("Duggingen", "BL", "Laufen", [4202]),
    ("Grellingen", "BL", "Laufen", [4203]),
    ("Laufen", "BL", "Laufen", [4242]),
    ("Liesberg", "BL", "Laufen", [4253, 4254]),
    ("Nenzlingen", "BL", "Laufen", [4224]),
    ("Roggenburg", "BL", "Laufen", [2814]),
    ("Röschenz", "BL", "Laufen", [4244]),
    ("Wahlen", "BL", "Laufen", [4246]),
    ("Zwingen", "BL", "Laufen", [4222]),
    # --- Bezirk Liestal ---
    ("Arisdorf", "BL", "Liestal", [4422]),
    ("Augst", "BL", "Liestal", [4302]),
    ("Bubendorf", "BL", "Liestal", [4416]),
    ("Frenkendorf", "BL", "Liestal", [4402]),
    ("Füllinsdorf", "BL", "Liestal", [4414]),
    ("Giebenach", "BL", "Liestal", [4304]),
    ("Hersberg", "BL", "Liestal", [4423]),
    ("Lausen", "BL", "Liestal", [4415]),
    ("Liestal", "BL", "Liestal", [4410]),
    ("Lupsingen", "BL", "Liestal", [4419]),
    ("Pratteln", "BL", "Liestal", [4133]),
    ("Ramlinsburg", "BL", "Liestal", [4433]),
    ("Seltisberg", "BL", "Liestal", [4411]),
    ("Ziefen", "BL", "Liestal", [4417]),
    # --- Bezirk Sissach ---
    ("Anwil", "BL", "Sissach", [4469]),
    ("Böckten", "BL", "Sissach", [4461]),
    ("Buckten", "BL", "Sissach", [4446]),
    ("Buus", "BL", "Sissach", [4463]),
    ("Diepflingen", "BL", "Sissach", [4442]),
    ("Gelterkinden", "BL", "Sissach", [4460]),
    ("Häfelfingen", "BL", "Sissach", [4445]),
    ("Hemmiken", "BL", "Sissach", [4465]),
    ("Itingen", "BL", "Sissach", [4452]),
    ("Känerkinden", "BL", "Sissach", [4447]),
    ("Kilchberg", "BL", "Sissach", [4496]),
    ("Läufelfingen", "BL", "Sissach", [4448]),
    ("Maisprach", "BL", "Sissach", [4464]),
    ("Nusshof", "BL", "Sissach", [4453]),
    ("Oltingen", "BL", "Sissach", [4494]),
    ("Ormalingen", "BL", "Sissach", [4466]),
    ("Rickenbach", "BL", "Sissach", [4462]),
    ("Rothenfluh", "BL", "Sissach", [4467]),
    ("Rümlingen", "BL", "Sissach", [4444]),
    ("Rünenberg", "BL", "Sissach", [4497]),
    ("Sissach", "BL", "Sissach", [4450]),
    ("Tecknau", "BL", "Sissach", [4492]),
    ("Tenniken", "BL", "Sissach", [4456]),
    ("Thürnen", "BL", "Sissach", [4441]),
    ("Wenslingen", "BL", "Sissach", [4493]),
    ("Wintersingen", "BL", "Sissach", [4451]),
    ("Wittinsburg", "BL", "Sissach", [4443]),
    ("Zeglingen", "BL", "Sissach", [4495]),
    ("Zunzgen", "BL", "Sissach", [4455]),
    # --- Bezirk Waldenburg ---
    ("Arboldswil", "BL", "Waldenburg", [4424]),
    ("Bennwil", "BL", "Waldenburg", [4431]),
    ("Bretzwil", "BL", "Waldenburg", [4207]),
    ("Diegten", "BL", "Waldenburg", [4457]),
    ("Eptingen", "BL", "Waldenburg", [4458]),
    ("Hölstein", "BL", "Waldenburg", [4434]),
    ("Lampenberg", "BL", "Waldenburg", [4432]),
    ("Langenbruck", "BL", "Waldenburg", [4438]),
    ("Lauwil", "BL", "Waldenburg", [4426]),
    ("Liedertswil", "BL", "Waldenburg", [4436]),
    ("Niederdorf", "BL", "Waldenburg", [4435]),
    ("Oberdorf", "BL", "Waldenburg", [4436]),
    ("Reigoldswil", "BL", "Waldenburg", [4418]),
    ("Titterten", "BL", "Waldenburg", [4425]),
    ("Waldenburg", "BL", "Waldenburg", [4437]),
]

# Larger municipalities get extra search requests (room splits) to cover their whole stock.
LARGE = {"Basel", "Riehen", "Allschwil", "Reinach", "Muttenz", "Binningen", "Münchenstein",
         "Pratteln", "Liestal", "Oberwil", "Therwil", "Aesch", "Birsfelden", "Arlesheim"}

ZIP_INFO = {}
for _name, _canton, _district, _zips in MUNICIPALITIES:
    for _z in _zips:
        # first definition wins (4436 is shared by Oberdorf and Liedertswil)
        ZIP_INFO.setdefault(_z, {"municipality": _name, "canton": _canton, "district": _district})


def lookup_zip(zipcode):
    """Return {'municipality', 'canton', 'district'} for a postcode in BS/BL, else None."""
    try:
        return ZIP_INFO.get(int(str(zipcode).strip()[:4]))
    except (TypeError, ValueError):
        return None


def slugify(name):
    s = name.lower()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("é", "e"), ("è", "e"), ("â", "a")):
        s = s.replace(a, b)
    out = []
    for ch in s:
        out.append(ch if ch.isalnum() else "-")
    return "-".join(p for p in "".join(out).split("-") if p)


def slugify_keep_umlaut_base(name):
    """Variant that drops umlauts to the base letter (ü -> u), as some portals do."""
    s = name.lower()
    for a, b in (("ä", "a"), ("ö", "o"), ("ü", "u"), ("é", "e"), ("è", "e")):
        s = s.replace(a, b)
    return "-".join(p for p in "".join(c if c.isalnum() else "-" for c in s).split("-") if p)


# Verified URL slugs per portal (only where they differ from slugify(name)).
COMPARIS_SLUG = {"Aesch": "aesch-bl", "Oberwil": "oberwil-bl", "Reinach": "reinach-bl",
                 "Kilchberg": "kilchberg-bl", "Rickenbach": "rickenbach-bl", "Oberdorf": "oberdorf-bl",
                 "Augst": "augst-bl"}

REALADVISOR_SLUG = {
    "Basel": "4051-basel", "Aesch": "4147-aesch-bl", "Biel-Benken": "4105-biel-benken-bl",
    "Münchenstein": "4142-munchenstein", "Oberwil": "4104-oberwil-bl", "Reinach": "4153-reinach-bl",
    "Schönenbuch": "4124-schonenbuch", "Röschenz": "4244-roschenz", "Augst": "4302-augst-bl",
    "Füllinsdorf": "4414-fullinsdorf", "Böckten": "4461-bockten", "Häfelfingen": "4445-hafelfingen",
    "Känerkinden": "4447-kanerkinden", "Kilchberg": "4496-kilchberg-bl", "Läufelfingen": "4448-laufelfingen",
    "Rickenbach": "4462-rickenbach-bl", "Rümlingen": "4444-rumlingen", "Rünenberg": "4497-runenberg",
    "Thürnen": "4441-thurnen", "Hölstein": "4434-holstein", "Oberdorf": "4436-oberdorf-bl",
    "Wahlen": None,
}


def comparis_slug(name):
    return COMPARIS_SLUG.get(name, slugify(name))


def realadvisor_slug(name, zips):
    if name in REALADVISOR_SLUG:
        return REALADVISOR_SLUG[name]
    return f"{zips[0]}-{slugify_keep_umlaut_base(name)}"


_NAME_INDEX = {}
for _name, _canton, _district, _zips in MUNICIPALITIES:
    _NAME_INDEX[slugify(_name)] = _zips[0]
    _NAME_INDEX[slugify_keep_umlaut_base(_name)] = _zips[0]


def zip_for_name(name):
    """'Reinach (BL)' / 'Münchenstein' -> first postcode, or None."""
    if not name:
        return None
    base = name.split("(")[0].replace(" BL", "").strip()
    return _NAME_INDEX.get(slugify(base)) or _NAME_INDEX.get(slugify_keep_umlaut_base(base))
