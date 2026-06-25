"""
Valmiit synteettiset kaupunkikartat ruudukkosimulaatiota varten.

Tässä tiedostossa ruudukko tulkitaan ylhäältäpäin kuvatuksi kaupunkimaiseksi
tieverkoksi:
- kuljettavat ruudut ovat teitä
- muut ruudut ovat rakennuksia, kortteleita tai muuten ajokelvottomia alueita

Kartat eivät kuvaa oikeita kaupunkeja. Niiden tarkoitus on tarjota hallittuja,
toistettavia ja kaupunkimaisia testiverkkoja reitinhakualgoritmien vertailuun.
"""

from copy import deepcopy


DEFAULT_ROWS = 60
DEFAULT_COLS = 60


def add_horizontal(roads, row, col_start, col_end, width=1, rows=DEFAULT_ROWS, cols=DEFAULT_COLS):
    """Lisää vaakasuuntaisen tien."""
    for offset in range(width):
        r = row + offset
        if 0 <= r < rows:
            for c in range(max(0, col_start), min(cols - 1, col_end) + 1):
                roads.add((r, c))


def add_vertical(roads, col, row_start, row_end, width=1, rows=DEFAULT_ROWS, cols=DEFAULT_COLS):
    """Lisää pystysuuntaisen tien."""
    for offset in range(width):
        c = col + offset
        if 0 <= c < cols:
            for r in range(max(0, row_start), min(rows - 1, row_end) + 1):
                roads.add((r, c))


def add_rect_ring(roads, top, left, bottom, right, width=1):
    """Lisää suorakulmaisen kehätien."""
    for i in range(width):
        add_horizontal(roads, top + i, left, right)
        add_horizontal(roads, bottom - i, left, right)
        add_vertical(roads, left + i, top, bottom)
        add_vertical(roads, right - i, top, bottom)


def add_square_roundabout(roads, center_row, center_col, radius=4):
    """
    Lisää ruudukkoon yksinkertaisen pikselimäisen liikenneympyrän.

    Tämä ei ole geometrisesti täydellinen ympyrä, vaan ruudukkoympäristöön sopiva
    pieni kiertävä katu, jonka keskiosa jää esteeksi.
    """
    top = center_row - radius
    bottom = center_row + radius
    left = center_col - radius
    right = center_col + radius

    add_rect_ring(roads, top, left, bottom, right, width=1)

    # Liittymät pohjoiseen, etelään, länteen ja itään.
    add_vertical(roads, center_col, 0, top)
    add_vertical(roads, center_col, bottom, DEFAULT_ROWS - 1)
    add_horizontal(roads, center_row, 0, left)
    add_horizontal(roads, center_row, right, DEFAULT_COLS - 1)


def make_map(name, display_name, category, roads, start, goal, rows=DEFAULT_ROWS, cols=DEFAULT_COLS):
    """Muodostaa karttamäärittelyn tiejoukon perusteella."""
    all_cells = {(r, c) for r in range(rows) for c in range(cols)}
    road_cells = set(roads)

    if start not in road_cells:
        raise ValueError(f"Kartan {name} lähtöpiste {start} ei ole tiellä.")
    if goal not in road_cells:
        raise ValueError(f"Kartan {name} maalipiste {goal} ei ole tiellä.")

    return {
        "name": name,
        "display_name": display_name,
        "category": category,
        "rows": rows,
        "cols": cols,
        "roads": road_cells,
        "obstacles": all_cells - road_cells,
        "start": start,
        "goal": goal,
    }


def build_grid_city():
    roads = set()

    for row in range(4, 57, 8):
        add_horizontal(roads, row, 2, 57)

    for col in range(4, 57, 8):
        add_vertical(roads, col, 2, 57)

    return make_map(
        name="grid_city",
        display_name="Ruutukaavakaupunki",
        category="säännöllinen ruutukaava",
        roads=roads,
        start=(4, 4),
        goal=(52, 52),
    )


def build_ring_road_city():
    roads = set()

    add_rect_ring(roads, 6, 6, 53, 53, width=1)

    for row in [14, 22, 30, 38, 46]:
        add_horizontal(roads, row, 6, 53)

    for col in [14, 22, 30, 38, 46]:
        add_vertical(roads, col, 6, 53)

    # Muutama sisäinen pääkatu tekee kehätien käytöstä vaihtoehtoisen, ei pakollisen.
    add_horizontal(roads, 30, 0, 59)
    add_vertical(roads, 30, 0, 59)

    return make_map(
        name="ring_road_city",
        display_name="Ruutukaava ja kehätie",
        category="kehätie ja keskusta",
        roads=roads,
        start=(30, 6),
        goal=(30, 53),
    )


def build_dense_downtown():
    roads = set()

    for row in range(3, 58, 6):
        add_horizontal(roads, row, 2, 57)

    for col in range(3, 58, 6):
        add_vertical(roads, col, 2, 57)

    # Kaksi leveämpää pääkatua keskustan läpi.
    add_horizontal(roads, 27, 0, 59, width=2)
    add_vertical(roads, 33, 0, 59, width=2)

    return make_map(
        name="dense_downtown",
        display_name="Tiheä keskusta",
        category="tiheä katuverkko",
        roads=roads,
        start=(3, 3),
        goal=(57, 57),
    )


def build_sparse_suburb():
    roads = set()

    for row in [8, 24, 42, 54]:
        add_horizontal(roads, row, 4, 55)

    for col in [5, 18, 35, 52]:
        add_vertical(roads, col, 4, 55)

    # Umpikatuja asuinalueen tyyliin.
    add_horizontal(roads, 14, 18, 30)
    add_horizontal(roads, 18, 35, 48)
    add_horizontal(roads, 32, 5, 15)
    add_horizontal(roads, 48, 35, 55)
    add_vertical(roads, 28, 8, 18)
    add_vertical(roads, 45, 24, 34)

    return make_map(
        name="sparse_suburb",
        display_name="Harva esikaupunki",
        category="harva katuverkko",
        roads=roads,
        start=(8, 5),
        goal=(54, 52),
    )


def build_bottleneck_city():
    roads = set()

    # Vasemman alueen ruutukaava.
    for row in [6, 14, 22, 30, 38, 46, 54]:
        add_horizontal(roads, row, 3, 24)
    for col in [4, 12, 20]:
        add_vertical(roads, col, 4, 55)

    # Oikean alueen ruutukaava.
    for row in [6, 14, 22, 30, 38, 46, 54]:
        add_horizontal(roads, row, 35, 56)
    for col in [36, 44, 52]:
        add_vertical(roads, col, 4, 55)

    # Kaksi kapeaa yhteyttä alueiden välillä.
    add_horizontal(roads, 22, 20, 44)
    add_horizontal(roads, 38, 20, 44)

    return make_map(
        name="bottleneck_city",
        display_name="Pullonkaulakaupunki",
        category="pullonkaulat",
        roads=roads,
        start=(6, 4),
        goal=(54, 52),
    )


def build_bridge_city():
    roads = set()

    # Kaksi kaupunginosaa.
    for row in [8, 18, 28, 38, 48]:
        add_horizontal(roads, row, 3, 20)
        add_horizontal(roads, row, 39, 56)

    for col in [5, 13, 20]:
        add_vertical(roads, col, 5, 51)

    for col in [39, 47, 55]:
        add_vertical(roads, col, 5, 51)

    # Pääsilta ja pidempi varayhteys.
    add_horizontal(roads, 28, 20, 39)
    add_horizontal(roads, 48, 20, 39)

    return make_map(
        name="bridge_city",
        display_name="Silta ja varayhteys",
        category="kapea yhteys",
        roads=roads,
        start=(8, 5),
        goal=(38, 55),
    )


def build_cul_de_sac_suburb():
    roads = set()

    # Pääkadut.
    add_vertical(roads, 30, 4, 56)
    add_horizontal(roads, 8, 6, 54)
    add_horizontal(roads, 30, 6, 54)
    add_horizontal(roads, 52, 6, 54)

    # T-risteyksiä ja umpikatuja.
    for row in [14, 20, 26, 36, 42, 48]:
        add_horizontal(roads, row, 30, 50)
    for row in [18, 24, 40, 46]:
        add_horizontal(roads, row, 10, 30)

    for col in [12, 18, 24, 42, 48]:
        add_vertical(roads, col, 8, 14)
        add_vertical(roads, col, 52, 56)

    return make_map(
        name="cul_de_sac_suburb",
        display_name="T-risteykset ja umpikadut",
        category="asuinalue",
        roads=roads,
        start=(8, 6),
        goal=(52, 54),
    )


def build_roundabout_city():
    roads = set()

    # Pääkadut ja keskellä oleva liikenneympyrä.
    add_square_roundabout(roads, 30, 30, radius=5)

    # Ulompi katuverkko.
    for row in [8, 18, 42, 52]:
        add_horizontal(roads, row, 6, 54)
    for col in [8, 18, 42, 52]:
        add_vertical(roads, col, 6, 54)

    # Yhdistetään ulkoverkko keskustaan.
    add_horizontal(roads, 18, 18, 30)
    add_horizontal(roads, 42, 30, 42)
    add_vertical(roads, 18, 18, 30)
    add_vertical(roads, 42, 30, 42)

    return make_map(
        name="roundabout_city",
        display_name="Liikenneympyräkaupunki",
        category="liikenneympyrä",
        roads=roads,
        start=(8, 8),
        goal=(52, 52),
    )


def build_mixed_city():
    roads = set()

    # Vasemmalla säännöllisempi keskusta.
    for row in [6, 14, 22, 30, 38, 46, 54]:
        add_horizontal(roads, row, 3, 30)
    for col in [4, 12, 20, 28]:
        add_vertical(roads, col, 4, 55)

    # Oikealla epäsäännöllisempi alue.
    add_vertical(roads, 38, 6, 54)
    add_vertical(roads, 50, 6, 54)
    add_horizontal(roads, 10, 38, 56)
    add_horizontal(roads, 24, 30, 56)
    add_horizontal(roads, 36, 38, 56)
    add_horizontal(roads, 50, 30, 56)

    # Mutkitteleva yhdyskatu.
    add_horizontal(roads, 30, 28, 38)
    add_vertical(roads, 38, 24, 30)
    add_horizontal(roads, 24, 38, 50)

    return make_map(
        name="mixed_city",
        display_name="Sekaverkko",
        category="sekoitettu katuverkko",
        roads=roads,
        start=(6, 4),
        goal=(50, 56),
    )


def build_multi_district_city():
    roads = set()

    # Kolme kaupunginosaa.
    for row in [6, 14, 22]:
        add_horizontal(roads, row, 4, 24)
    for col in [5, 14, 23]:
        add_vertical(roads, col, 5, 23)

    for row in [36, 44, 52]:
        add_horizontal(roads, row, 4, 24)
    for col in [5, 14, 23]:
        add_vertical(roads, col, 35, 53)

    for row in [18, 30, 42]:
        add_horizontal(roads, row, 36, 56)
    for col in [37, 46, 55]:
        add_vertical(roads, col, 16, 44)

    # Kaupunginosia yhdistävät pääväylät.
    add_vertical(roads, 14, 22, 36)
    add_horizontal(roads, 30, 14, 46)
    add_vertical(roads, 46, 18, 42)

    return make_map(
        name="multi_district_city",
        display_name="Monikeskuksinen kaupunki",
        category="useita kaupunginosia",
        roads=roads,
        start=(6, 5),
        goal=(42, 55),
    )


_MAP_BUILDERS = [
    build_grid_city,
    build_ring_road_city,
    build_dense_downtown,
    build_sparse_suburb,
    build_bottleneck_city,
    build_bridge_city,
    build_cul_de_sac_suburb,
    build_roundabout_city,
    build_mixed_city,
    build_multi_district_city,
]


def get_city_maps():
    """Palauttaa kaikki valmiit kaupunkikartat."""
    return [builder() for builder in _MAP_BUILDERS]


def get_city_map_names():
    """Palauttaa karttojen sisäiset nimet siinä järjestyksessä kuin ne käydään läpi."""
    return [city_map["name"] for city_map in get_city_maps()]


def get_default_city_map_name():
    """Palauttaa oletuskartan nimen."""
    return get_city_map_names()[0]


def get_city_map(name):
    """Palauttaa yhden kartan sisäisen nimen perusteella."""
    for city_map in get_city_maps():
        if city_map["name"] == name:
            return deepcopy(city_map)

    valid_names = ", ".join(get_city_map_names())
    raise ValueError(f"Tuntematon kartta: {name}. Sallitut kartat: {valid_names}")


def get_city_map_by_index(index):
    """Palauttaa kartan indeksin perusteella. Indeksi kiertää listan ympäri."""
    maps = get_city_maps()
    if not maps:
        raise ValueError("Yhtään kaupunkikarttaa ei ole määritelty.")

    return deepcopy(maps[index % len(maps)])


def get_city_map_count():
    """Palauttaa valmiiden karttojen määrän."""
    return len(_MAP_BUILDERS)
