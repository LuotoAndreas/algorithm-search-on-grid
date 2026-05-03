import heapq
import math
import time

from algorithms import manhattan_distance


class DStarLite:
    """
    D* Lite -algoritmin ruudukkopohjainen toteutus.

    Tämä luokka säilyttää sisäisen tilansa ajon aikana:
    - g-arvot
    - rhs-arvot
    - prioriteettijonon
    - nykyisen lähtöpisteen
    - kohdepisteen

    Kun ajoneuvo liikkuu, lähtöpiste päivitetään move_start-metodilla.
    Kun ympäristöön lisätään este, update_obstacle-metodi päivittää vain
    muutoksen kannalta olennaisia solmuja.

    Tämä erottaa D* Liten Dijkstrasta ja A*:sta, jotka laskevat muutostilanteessa
    uuden reitin alusta.
    """

    def __init__(self, grid, start, goal):
        self.grid = grid
        self.start = start
        self.goal = goal

        # D* Litessa k_m ottaa huomioon lähtöpisteen siirtymisen.
        self.k_m = 0

        # Edellinen lähtöpiste tarvitaan k_m-arvon päivittämiseen.
        self.last_start = start

        # g(s): nykyinen kustannusarvio solmusta s kohteeseen.
        self.g = {}

        # rhs(s): yhden askeleen perusteella laskettu kustannusarvio.
        self.rhs = {}

        # Prioriteettijono ja voimassa olevien alkioiden seuranta.
        self.open_list = []
        self.open_entries = {}

        # Visualisointia ja mittaamista varten.
        self.visited_order = []

        self.initialize()

    def get_g(self, node):
        """
        Palauttaa solmun g-arvon.
        Jos arvoa ei ole, se tulkitaan äärettömäksi.
        """
        return self.g.get(node, math.inf)

    def get_rhs(self, node):
        """
        Palauttaa solmun rhs-arvon.
        Jos arvoa ei ole, se tulkitaan äärettömäksi.
        """
        return self.rhs.get(node, math.inf)

    def set_g(self, node, value):
        """
        Asettaa solmun g-arvon.
        """
        self.g[node] = value

    def set_rhs(self, node, value):
        """
        Asettaa solmun rhs-arvon.
        """
        self.rhs[node] = value

    def calculate_key(self, node):
        """
        Laskee D* Liten prioriteettiavaimen solmulle.

        Avain on pari:
            (k1, k2)

        missä:
            k1 = min(g, rhs) + h(start, node) + k_m
            k2 = min(g, rhs)

        Pienempi avain käsitellään ensin.
        """
        min_g_rhs = min(self.get_g(node), self.get_rhs(node))

        return (
            min_g_rhs + manhattan_distance(self.start, node) + self.k_m,
            min_g_rhs
        )

    def initialize(self):
        """
        Alustaa D* Lite -algoritmin.

        Kohdesolmun rhs-arvo asetetaan nollaksi, koska kohteesta kohteeseen
        pääsemisen kustannus on nolla. Haku käynnistyy siis kohdesolmusta.
        """
        self.open_list = []
        self.open_entries = {}
        self.visited_order = []

        self.g = {}
        self.rhs = {}

        self.set_rhs(self.goal, 0)
        self.insert_or_update(self.goal)

    def insert_or_update(self, node):
        """
        Lisää solmun prioriteettijonoon tai päivittää sen prioriteetin.

        Pythonin heapq ei tue suoraa prioriteetin päivitystä, joten uusi merkintä
        lisätään jonoon ja vanhat merkinnät ohitetaan myöhemmin.
        """
        key = self.calculate_key(node)
        self.open_entries[node] = key
        heapq.heappush(self.open_list, (key, node))

    def remove_from_open(self, node):
        """
        Poistaa solmun voimassa olevista prioriteettijonon alkioista.

        Itse heapq-alkio voi jäädä jonoon, mutta sitä ei enää hyväksytä
        voimassa olevaksi.
        """
        if node in self.open_entries:
            del self.open_entries[node]

    def remove_invalid_open_entries(self):
        """
        Poistaa prioriteettijonon kärjestä vanhentuneet alkiot.
        """
        while self.open_list:
            key, node = self.open_list[0]

            if node in self.open_entries and self.open_entries[node] == key:
                break

            heapq.heappop(self.open_list)

    def top_key(self):
        """
        Palauttaa prioriteettijonon pienimmän voimassa olevan avaimen.
        """
        self.remove_invalid_open_entries()

        if not self.open_list:
            return (math.inf, math.inf)

        return self.open_list[0][0]

    def cost(self, from_node, to_node):
        """
        Palauttaa siirtymän kustannuksen kahden vierekkäisen ruudun välillä.

        Tässä mallissa:
        - normaali siirtymä maksaa 1
        - esteeseen ei voi siirtyä, joten kustannus on ääretön
        """
        row, col = to_node

        if self.grid.is_obstacle(row, col):
            return math.inf

        return 1

    def get_all_neighbors(self, node):
        """
        Palauttaa kaikki ruudukon sisällä olevat nelisuuntaiset naapurit.

        Tätä käytetään D* Liten päivityksissä, koska myös esteen ympärillä olevat
        solmut täytyy voida päivittää. Tässä ei suodateta esteitä pois.
        """
        row, col = node

        possible_neighbors = [
            (row - 1, col),
            (row + 1, col),
            (row, col - 1),
            (row, col + 1),
        ]

        neighbors = []

        for neighbor_row, neighbor_col in possible_neighbors:
            if self.grid.in_bounds(neighbor_row, neighbor_col):
                neighbors.append((neighbor_row, neighbor_col))

        return neighbors

    def get_successors(self, node):
        """
        Palauttaa solmun seuraajat.

        D* Liten päivityksessä käytetään kaikkia ruudukon sisällä olevia naapureita.
        Siirtymän mahdottomuus käsitellään cost-funktiossa.
        """
        return self.get_all_neighbors(node)

    def get_predecessors(self, node):
        """
        Palauttaa solmun edeltäjät.

        Nelisuuntaisessa symmetrisessä ruudukossa edeltäjät ovat samat kuin naapurit.
        """
        return self.get_all_neighbors(node)

    def update_vertex(self, node):
        """
        Päivittää yksittäisen solmun rhs-arvon ja prioriteettijonotilan.

        Jos solmu ei ole kohdesolmu, rhs-arvoksi asetetaan pienin mahdollinen
        kustannus jonkin seuraajasolmun kautta.

        Jos g(s) ja rhs(s) poikkeavat toisistaan, solmu on epäjohdonmukainen
        ja se lisätään prioriteettijonoon.
        """
        if node != self.goal:
            best_rhs = math.inf

            for successor in self.get_successors(node):
                candidate_rhs = self.cost(node, successor) + self.get_g(successor)

                if candidate_rhs < best_rhs:
                    best_rhs = candidate_rhs

            self.set_rhs(node, best_rhs)

        self.remove_from_open(node)

        if self.get_g(node) != self.get_rhs(node):
            self.insert_or_update(node)

    def compute_shortest_path(self, reset_visited=True):
        """
        Laskee tai päivittää lyhimmän reitin.

        Jos reset_visited=True, käsiteltyjen solmujen lista nollataan.
        Tätä käytetään mittaamiseen:
        - alkuperäinen haku näyttää alkuperäisen käsittelyn
        - uudelleenreititys näyttää vain muutoksen jälkeisen käsittelyn
        """
        if reset_visited:
            self.visited_order = []

        while (
            self.top_key() < self.calculate_key(self.start)
            or self.get_rhs(self.start) != self.get_g(self.start)
        ):
            self.remove_invalid_open_entries()

            if not self.open_list:
                break

            old_key, current = heapq.heappop(self.open_list)

            if current not in self.open_entries:
                continue

            del self.open_entries[current]

            new_key = self.calculate_key(current)

            if old_key < new_key:
                self.insert_or_update(current)

            elif self.get_g(current) > self.get_rhs(current):
                self.set_g(current, self.get_rhs(current))
                self.visited_order.append(current)

                for predecessor in self.get_predecessors(current):
                    self.update_vertex(predecessor)

            else:
                old_g = self.get_g(current)
                self.set_g(current, math.inf)
                self.visited_order.append(current)

                affected_nodes = self.get_predecessors(current)
                affected_nodes.append(current)

                for predecessor in affected_nodes:
                    if self.get_rhs(predecessor) == self.cost(predecessor, current) + old_g:
                        self.update_vertex(predecessor)
                    else:
                        self.update_vertex(predecessor)

    def get_path(self):
        """
        Muodostaa reitin nykyisestä lähtöpisteestä kohdepisteeseen.

        Reitti muodostetaan g-arvojen perusteella:
        jokaisessa ruudussa valitaan naapuri, jolla on pienin
        cost(current, neighbor) + g(neighbor).
        """
        if self.get_rhs(self.start) == math.inf:
            return []

        path = [self.start]
        current = self.start
        visited_in_path = set()

        while current != self.goal:
            if current in visited_in_path:
                return []

            visited_in_path.add(current)

            best_neighbor = None
            best_cost = math.inf

            for neighbor in self.get_successors(current):
                candidate_cost = self.cost(current, neighbor) + self.get_g(neighbor)

                if candidate_cost < best_cost:
                    best_cost = candidate_cost
                    best_neighbor = neighbor

            if best_neighbor is None or best_cost == math.inf:
                return []

            current = best_neighbor
            path.append(current)

        return path

    def move_start(self, new_start):
        """
        Päivittää D* Liten nykyisen lähtöpisteen ajoneuvon sijaintiin.

        k_m-arvo kasvaa sen mukaan, kuinka paljon lähtöpiste on liikkunut.
        Tämä on D* Liten mekanismi, jolla aiempi laskenta pysyy käyttökelpoisena,
        vaikka agentin sijainti muuttuu.
        """
        self.k_m += manhattan_distance(self.last_start, new_start)
        self.last_start = new_start
        self.start = new_start

    def update_obstacle(self, obstacle_position):
        """
        Päivittää D* Lite -tilan, kun ruutu muuttuu esteeksi.

        Este on jo lisätty grid.obstacles-joukkoon ennen tämän kutsumista.
        Päivityksessä käsitellään esteen ympärillä olevat solmut, koska niiden
        paras reitti kohteeseen voi muuttua.
        """
        affected_nodes = self.get_predecessors(obstacle_position)
        affected_nodes.append(obstacle_position)

        for node in affected_nodes:
            self.update_vertex(node)

    def get_current_result(self, calculation_time):
        """
        Palauttaa D* Liten nykyisen reitin ja mittarit result-sanakirjana.
        """
        path = self.get_path()

        return {
            "algorithm": "D* Lite",
            "path": path,
            "visited_order": list(self.visited_order),
            "calculation_time": calculation_time,
            "visited_count": len(self.visited_order),
            "path_length": max(0, len(path) - 1),
            "success": len(path) > 0,
        }


def dstar_lite_search(grid, start, goal):
    """
    Staattinen apufunktio, jotta D* Litea voidaan käyttää samalla tavalla
    kuin Dijkstraa ja A*:aa.

    Huomaa:
    Tämä luo uuden plannerin. Siksi tämä sopii alkuperäiseen staattiseen hakuun
    ja validointiin, mutta varsinainen dynaaminen hyöty saadaan käyttämällä
    samaa DStarLite-oliota ajon aikana.
    """
    start_time = time.perf_counter()

    planner = DStarLite(grid, start, goal)
    planner.compute_shortest_path(reset_visited=True)
    path = planner.get_path()

    end_time = time.perf_counter()

    result = {
        "algorithm": "D* Lite",
        "path": path,
        "visited_order": planner.visited_order,
        "calculation_time": end_time - start_time,
        "visited_count": len(planner.visited_order),
        "path_length": max(0, len(path) - 1),
        "success": len(path) > 0,
    }

    return result