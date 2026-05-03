from config import GRID_ROWS, GRID_COLS


class Grid:
    """
    Grid-luokka kuvaa ruudukkoympäristöä.

    Jokainen ruutu voidaan ajatella verkon solmuna.
    Esteelliset ruudut vastaavat solmuja, joiden kautta ei saa kulkea.

    start = lähtösolmu
    goal = kohdesolmu
    """

    def __init__(self):
        self.rows = GRID_ROWS
        self.cols = GRID_COLS
        self.obstacles = set()
        self.start = None
        self.goal = None

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

        Lähtö- tai kohdepistettä ei muuteta esteeksi.
        """
        if not self.in_bounds(row, col):
            return

        position = (row, col)

        if position == self.start or position == self.goal:
            return

        if position in self.obstacles:
            self.obstacles.remove(position)
        else:
            self.obstacles.add(position)

    def add_obstacle(self, row, col):
        """
        Lisää esteen ruutuun.

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
        """
        if not self.in_bounds(row, col):
            return

        position = (row, col)

        if position in self.obstacles:
            self.obstacles.remove(position)

    def clear(self):
        """
        Tyhjentää koko ruudukon.

        Poistaa:
        - esteet
        - lähtöpisteen
        - kohdepisteen
        """
        self.obstacles.clear()
        self.start = None
        self.goal = None

    def set_start(self, row, col):
        """
        Asettaa lähtöpisteen.

        Lähtöpiste ei voi olla esteen päällä.
        """
        if not self.in_bounds(row, col):
            return

        position = (row, col)

        if position in self.obstacles:
            self.obstacles.remove(position)

        if position == self.goal:
            self.goal = None

        self.start = position

    def set_goal(self, row, col):
        """
        Asettaa kohdepisteen.

        Kohdepiste ei voi olla esteen päällä.
        """
        if not self.in_bounds(row, col):
            return

        position = (row, col)

        if position in self.obstacles:
            self.obstacles.remove(position)

        if position == self.start:
            self.start = None

        self.goal = position