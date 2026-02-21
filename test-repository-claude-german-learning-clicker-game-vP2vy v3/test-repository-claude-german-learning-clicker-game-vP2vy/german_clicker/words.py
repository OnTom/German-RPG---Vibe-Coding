"""
Databáze německých slov s českými překlady.

Formát každého záznamu:
  {"de": "německé slovo", "cz": "český překlad"}

Slova jsou seskupena do kategorií. Hra náhodně vybírá
ze VŠECH kategorií a zobrazuje český výraz — hráč píše německy.
"""

CATEGORIES: dict[str, list[dict]] = {
    "Čísla": [
        {"de": "eins",   "cz": "jedna"},
        {"de": "zwei",   "cz": "dva"},
        {"de": "drei",   "cz": "tři"},
        {"de": "vier",   "cz": "čtyři"},
        {"de": "fünf",   "cz": "pět"},
        {"de": "sechs",  "cz": "šest"},
        {"de": "sieben", "cz": "sedm"},
        {"de": "acht",   "cz": "osm"},
        {"de": "neun",   "cz": "devět"},
        {"de": "zehn",   "cz": "deset"},
    ],
    "Barvy": [
        {"de": "rot",    "cz": "červená"},
        {"de": "blau",   "cz": "modrá"},
        {"de": "grün",   "cz": "zelená"},
        {"de": "gelb",   "cz": "žlutá"},
        {"de": "schwarz","cz": "černá"},
        {"de": "weiß",   "cz": "bílá"},
        {"de": "orange", "cz": "oranžová"},
        {"de": "lila",   "cz": "fialová"},
        {"de": "braun",  "cz": "hnědá"},
        {"de": "grau",   "cz": "šedá"},
    ],
    "Zvířata": [
        {"de": "Hund",     "cz": "pes"},
        {"de": "Katze",    "cz": "kočka"},
        {"de": "Pferd",    "cz": "kůň"},
        {"de": "Vogel",    "cz": "pták"},
        {"de": "Kuh",      "cz": "kráva"},
        {"de": "Schwein",  "cz": "prase"},
        {"de": "Fisch",    "cz": "ryba"},
        {"de": "Hase",     "cz": "zajíc"},
        {"de": "Maus",     "cz": "myš"},
        {"de": "Bär",      "cz": "medvěd"},
        {"de": "Löwe",     "cz": "lev"},
        {"de": "Elefant",  "cz": "slon"},
    ],
    "Jídlo": [
        {"de": "Brot",      "cz": "chléb"},
        {"de": "Apfel",     "cz": "jablko"},
        {"de": "Milch",     "cz": "mléko"},
        {"de": "Ei",        "cz": "vejce"},
        {"de": "Käse",      "cz": "sýr"},
        {"de": "Kartoffel", "cz": "brambor"},
        {"de": "Tomate",    "cz": "rajče"},
        {"de": "Fleisch",   "cz": "maso"},
        {"de": "Kuchen",    "cz": "dort"},
        {"de": "Wasser",    "cz": "voda"},
        {"de": "Kaffee",    "cz": "káva"},
        {"de": "Bier",      "cz": "pivo"},
    ],
    "Dny v týdnu": [
        {"de": "Montag",    "cz": "pondělí"},
        {"de": "Dienstag",  "cz": "úterý"},
        {"de": "Mittwoch",  "cz": "středa"},
        {"de": "Donnerstag","cz": "čtvrtek"},
        {"de": "Freitag",   "cz": "pátek"},
        {"de": "Samstag",   "cz": "sobota"},
        {"de": "Sonntag",   "cz": "neděle"},
    ],
    "Základní fráze": [
        {"de": "Hallo",           "cz": "ahoj"},
        {"de": "Guten Morgen",    "cz": "dobré ráno"},
        {"de": "Guten Tag",       "cz": "dobrý den"},
        {"de": "Guten Abend",     "cz": "dobrý večer"},
        {"de": "Auf Wiedersehen", "cz": "na shledanou"},
        {"de": "Danke",           "cz": "díky"},
        {"de": "Bitte",           "cz": "prosím"},
        {"de": "Entschuldigung",  "cz": "promiňte"},
        {"de": "Ja",              "cz": "ano"},
        {"de": "Nein",            "cz": "ne"},
    ],
    "Rodina": [
        {"de": "Mutter",      "cz": "matka"},
        {"de": "Vater",       "cz": "otec"},
        {"de": "Schwester",   "cz": "sestra"},
        {"de": "Bruder",      "cz": "bratr"},
        {"de": "Großmutter",  "cz": "babička"},
        {"de": "Großvater",   "cz": "dědeček"},
        {"de": "Tochter",     "cz": "dcera"},
        {"de": "Sohn",        "cz": "syn"},
        {"de": "Frau",        "cz": "žena"},
        {"de": "Mann",        "cz": "muž"},
    ],
}
