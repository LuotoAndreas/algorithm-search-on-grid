from config import GRID_ROWS, GRID_COLS, RANDOM_OBSTACLE_PROBABILITY, RANDOM_SEED
import random

try:
    from maps import get_city_map
except ImportError:
    get_city_map = None


class Grid:
    """
    Grid-luokka kuvaa ruudukkoympäristöä.

    Jokainen ruutu voidaan ajatella verkon solmuna.
    Esteelliset ruudut vastaavat solmuja, joiden kautta ei saa kulkea.

    Kaupunkikarttamallissa:
    - road_cells sisältää tieverkkoon kuuluvat ruudut
    - base_obstacles sisältää rakennukset/korttelit eli pysyvät esteet
    - obstacles sisältää sekä pysyvät esteet että mahdolliset tiesulut

    start = lähtösolmu
    goal = kohdesolmu
    """

    def __init__(self):
        self.rows = GRID_ROWS
        self.cols = GRID_COLS
        self.obstacles = set()
        self.base_obstacles = set()
        self.road_cells = None
        self.map_name = None
        self.map_display_name = None
        self.map_category = None
        self.start = None
        self.goal = None

    def load_city_map(self, map_name):
        """
        Lataa valmiin synteettisen kaupunkikartan.

        Kartassa kuljettavat ruudut ovat teitä ja muut ruudut ovat rakennuksia,
        kortteleita tai muita pysyviä esteitä.
        """
        if get_city_map is None:
            raise RuntimeError("maps.py-tiedostoa ei löytynyt, joten kaupunkikarttaa ei voida ladata.")

        city_map = get_city_map(map_name)

        self.rows = city_map["rows"]
        self.cols = city_map["cols"]
        self.road_cells = set(city_map["roads"])
        self.base_obstacles = set(city_map["obstacles"])
        self.obstacles = set(self.base_obstacles)
        self.start = city_map["start"]
        self.goal = city_map["goal"]
        self.map_name = city_map["name"]
        self.map_display_name = city_map["display_name"]
        self.map_category = city_map["category"]

    def reset_to_base_map(self):
        """
        Palauttaa ladatun kaupunkikartan alkuperäiseen tilaan.

        Tämä poistaa ajonaikaiset tiesulut, mutta säilyttää rakennukset,
        korttelit, lähtöpisteen ja maalipisteen.
        """
        if self.road_cells is None:
            self.obstacles.clear()
            return

        self.obstacles = set(self.base_obstacles)

    def is_city_map_loaded(self):
        """Palauttaa True, jos ruudukkoon on ladattu valmis kaupunkikartta."""
        return self.road_cells is not None

    def is_road(self, row, col):
        """Tarkistaa, onko ruutu tieverkon osa."""
        if not self.in_bounds(row, col):
            return False

        if self.road_cells is None:
            return True

        return (row, col) in self.road_cells

    def get_road_cells(self):
        """Palauttaa tieverkon ruudut."""
        if self.road_cells is None:
            return {
                (row, col)
                for row in range(self.rows)
                for col in range(self.cols)
                if not self.is_obstacle(row, col)
            }

        return set(self.road_cells)

    def generate_random_obstacles(self):
        """
        Generoi satunnaiset esteet.

        Jos valmista kaupunkikarttaa ei ole ladattu, toiminto vastaa vanhaa
        satunnaisruudukkoa.

        Jos kaupunkikartta on ladattu, pysyvät rakennukset säilytetään ja
        satunnaisuus kohdistuu vain tieverkon ruutuihin. Tällöin toiminto
        muistuttaa satunnaisia tiesulkuja eikä hajallaan olevia rakennuksia.
        """
        random.seed(RANDOM_SEED)

        if self.road_cells is not None:
            self.obstacles = set(self.base_obstacles)

            for position in self.road_cells:
                if position == self.start or position == self.goal:
                    continue

                if random.random() < RANDOM_OBSTACLE_PROBABILITY:
                    self.obstacles.add(position)

            return

        self.obstacles.clear()

        for row in range(self.rows):
            for col in range(self.cols):
                position = (row, col)

                if position == self.start or position == self.goal:
                    continue

                if random.random() < RANDOM_OBSTACLE_PROBABILITY:
                    self.obstacles.add(position)

    def in_bounds(self, row, col):
        """
        Tarkistaa, onko annettu ruutu ruudukon sisällä.
        """
        return 0 <= row < self.rows and 0 <= col < self.cols

    def is_obstacle(self, row, col):
        """
        Tarkistaa, onko ruutu este.
        """
        return (row, col) in self.obstacles

    def is_walkable(self, row, col):
        """
        Tarkistaa, voiko ruutuun kulkea.
        """
        return self.in_bounds(row, col) and not self.is_obstacle(row, col)

    def get_neighbors(self, position):
        """
        Palauttaa ruudun kulkukelpoiset naapurit.

        Tässä mallissa liikkuminen sallitaan neljään suuntaan:
        - ylös
        - alas
        - vasemmalle
        - oikealle

        Jokainen siirtymä maksaa tässä vaiheessa 1.
        """
        row, col = position

        possible_neighbors = [
            (row - 1, col),  # ylös
            (row + 1, col),  # alas
            (row, col - 1),  # vasemmalle
            (row, col + 1),  # oikealle
        ]

        valid_neighbors = []

        for neighbor_row, neighbor_col in possible_neighbors:
            if self.is_walkable(neighbor_row, neighbor_col):
                valid_neighbors.append((neighbor_row, neighbor_col))

        return valid_neighbors

    def toggle_obstacle(self, row, col):
        """
        Lisää esteen ruutuun tai poistaa sen, jos ruutu on jo este.

        Jos kaupunkikartta on ladattu, rakennusruutuja ei voi muuttaa teiksi.
        Tällöin käyttäjä voi sulkea ja avata vain tieverkon ruutuja.
        """
        if not self.in_bounds(row, col):
            return

        position = (row, col)

        if position == self.start or position == self.goal:
            return

        if self.road_cells is not None and position not in self.road_cells:
            return

        if position in self.obstacles:
            self.obstacles.remove(position)
        else:
            self.obstacles.add(position)

    def add_obstacle(self, row, col):
        """
        Lisää esteen ruutuun.

        Kaupunkikartassa tätä käytetään käytännössä tiesulun lisäämiseen.
        Lähtö- tai kohdepistettä ei muuteta esteeksi.
        """
        if not self.in_bounds(row, col):
            return

        position = (row, col)

        if position == self.start or position == self.goal:
            return

        self.obstacles.add(position)

    def remove_obstacle(self, row, col):
        """
        Poistaa esteen ruudusta.

        Kaupunkikartassa pysyviä rakennusesteitä ei poisteta.
        Vain tieverkolle lisätty tiesulku voidaan poistaa.
        """
        if not self.in_bounds(row, col):
            return

        position = (row, col)

        if self.road_cells is not None and position not in self.road_cells:
            return

        if position in self.obstacles:
            self.obstacles.remove(position)

    def clear(self):
        """
        Tyhjentää koko ruudukon.

        Poistaa:
        - esteet
        - lähtöpisteen
        - kohdepisteen
        - mahdollisen ladatun kaupunkikartan
        """
        self.obstacles.clear()
        self.base_obstacles.clear()
        self.road_cells = None
        self.map_name = None
        self.map_display_name = None
        self.map_category = None
        self.start = None
        self.goal = None
        self.rows = GRID_ROWS
        self.cols = GRID_COLS

    def set_start(self, row, col):
        """
        Asettaa lähtöpisteen.

        Lähtöpiste ei voi olla pysyvän rakennusesteen päällä.
        Kaupunkikartassa lähtöpisteen täytyy olla tieverkolla.
        """
        if not self.in_bounds(row, col):
            return

        position = (row, col)

        if self.road_cells is not None and position not in self.road_cells:
            return

        if position in self.obstacles:
            self.obstacles.remove(position)

        if position == self.goal:
            self.goal = None

        self.start = position

    def set_goal(self, row, col):
        """
        Asettaa kohdepisteen.

        Kohdepiste ei voi olla pysyvän rakennusesteen päällä.
        Kaupunkikartassa kohdepisteen täytyy olla tieverkolla.
        """
        if not self.in_bounds(row, col):
            return

        position = (row, col)

        if self.road_cells is not None and position not in self.road_cells:
            return

        if position in self.obstacles:
            self.obstacles.remove(position)

        if position == self.start:
            self.start = None

        self.goal = position
