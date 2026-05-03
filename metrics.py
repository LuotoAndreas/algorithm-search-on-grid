import csv
import os

from config import GRID_ROWS, GRID_COLS

def set_scenario_info(self, grid):
        """
        Tallentaa ruudukon ja skenaarion perustiedot.
        """
        self.start = grid.start
        self.goal = grid.goal
        self.initial_obstacle_count = len(grid.obstacles)

class SimulationMetrics:
    """
    Kerää yhden simulaatioajon mittarit.

    Tämän luokan tarkoitus on pitää tutkimusmittarit erillään
    visualisoinnista ja käyttöliittymästä.
    """

    def __init__(self, algorithm_name):
        self.algorithm_name = algorithm_name

        self.grid_rows = GRID_ROWS
        self.grid_cols = GRID_COLS
        self.start = None
        self.goal = None
        self.initial_obstacle_count = 0

        self.initial_path_length = 0
        self.initial_calculation_time = 0.0
        self.initial_visited_count = 0

        self.dynamic_obstacle_added = False
        self.dynamic_obstacle_position = None

        # Kaikki ajon aikana lisätyt dynaamiset esteet
        self.dynamic_obstacle_positions = []

        # Ne dynaamiset esteet, jotka osuivat jäljellä olevalle reitille
        # ja aiheuttivat uudelleenreitityksen
        self.effective_obstacle_positions = []

        self.reroute_count = 0
        self.total_replanning_time = 0.0
        self.total_replanning_visited_count = 0

        self.travelled_distance = 0
        self.delivery_delay = 0
        self.total_calculation_time = 0.0

        self.success = False

    def set_scenario_info(self, grid):
        """
        Tallentaa ruudukon ja skenaarion perustiedot.
        """
        self.start = grid.start
        self.goal = grid.goal
        self.initial_obstacle_count = len(grid.obstacles)

    def set_initial_result(self, result):
        """
        Tallentaa alkuperäisen reitinhaun tulokset.
        """
        self.algorithm_name = result["algorithm"]
        self.initial_path_length = result["path_length"]
        self.initial_calculation_time = result["calculation_time"]
        self.initial_visited_count = result["visited_count"]
        self.success = result["success"]

        self.update_totals()

    def set_dynamic_obstacle(self, position):
        """
        Tallentaa tiedon ajon aikana lisätystä dynaamisesta esteestä.

        Jos esteitä lisätään useita, kaikki sijainnit tallennetaan listaan.
        dynamic_obstacle_position säilytetään viimeisimmän esteen sijaintina
        taaksepäin yhteensopivuuden vuoksi.
        """
        self.dynamic_obstacle_added = True
        self.dynamic_obstacle_position = position
        self.dynamic_obstacle_positions.append(position)

    def add_effective_obstacle(self, position):
        """
        Tallentaa esteen, joka vaikutti jäljellä olevaan reittiin
        ja aiheutti uudelleenreitityksen.
        """
        self.effective_obstacle_positions.append(position)

    def add_reroute_result(self, result):
        """
        Tallentaa yhden uudelleenreitityksen tulokset.
        """
        self.reroute_count += 1
        self.total_replanning_time += result["calculation_time"]
        self.total_replanning_visited_count += result["visited_count"]
        self.success = result["success"]

        self.update_totals()

    def set_travelled_path(self, travelled_path):
        """
        Tallentaa toteutuneen kuljetun matkan.

        Jos reitillä on N ruutua, askelten määrä on N - 1.
        """
        self.travelled_distance = max(0, len(travelled_path) - 1)
        self.delivery_delay = self.travelled_distance - self.initial_path_length

    def set_success(self, success):
        """
        Tallentaa, pääsikö ajoneuvo kohteeseen.
        """
        self.success = success

    def update_totals(self):
        """
        Päivittää kokonaislaskenta-ajan.
        """
        self.total_calculation_time = (
            self.initial_calculation_time + self.total_replanning_time
        )

    def to_dict(self):
        """
        Palauttaa mittarit sanakirjana CSV-tallennusta varten.
        """
        return {
            "algorithm": self.algorithm_name,
            "grid_rows": self.grid_rows,
            "grid_cols": self.grid_cols,
            "start": self.start,
            "goal": self.goal,
            "initial_obstacle_count": self.initial_obstacle_count,
            "initial_path_length": self.initial_path_length,
            "initial_calculation_time": self.initial_calculation_time,
            "initial_visited_count": self.initial_visited_count,
            "dynamic_obstacle_added": self.dynamic_obstacle_added,
            "dynamic_obstacle_position": self.dynamic_obstacle_position,
            "dynamic_obstacle_count": len(self.dynamic_obstacle_positions),
            "dynamic_obstacle_positions": self.dynamic_obstacle_positions,
            "effective_obstacle_count": len(self.effective_obstacle_positions),
            "effective_obstacle_positions": self.effective_obstacle_positions,
            "reroute_count": self.reroute_count,
            "total_replanning_time": self.total_replanning_time,
            "total_replanning_visited_count": self.total_replanning_visited_count,
            "travelled_distance": self.travelled_distance,
            "delivery_delay": self.delivery_delay,
            "total_calculation_time": self.total_calculation_time,
            "success": self.success,
        }

    def save_to_csv(self, filename="results.csv"):
        """
        Tallentaa mittarit CSV-tiedostoon.

        Jos tiedostoa ei vielä ole, kirjoitetaan ensin otsikkorivi.
        Jos tiedosto on olemassa, uusi ajo lisätään sen loppuun.
        """
        row = self.to_dict()
        file_exists = os.path.exists(filename)

        with open(filename, mode="a", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=row.keys())

            if not file_exists:
                writer.writeheader()

            writer.writerow(row)

    def print_summary(self):
        """
        Tulostaa simulaatioajon yhteenvedon terminaaliin.
        """
        print("\n==============================")
        print("SIMULAATION YHTEENVETO")
        print("==============================")
        print(f"Algoritmi: {self.algorithm_name}")

        print("\nSkenaario")
        print(f"- Ruudukon koko: {self.grid_rows} x {self.grid_cols}")
        print(f"- Lähtöpiste: {self.start}")
        print(f"- Kohdepiste: {self.goal}")
        print(f"- Alkuperäisten esteiden määrä: {self.initial_obstacle_count}")

        print("\nAlkuperäinen reitinhaku")
        print(f"- Reitin pituus: {self.initial_path_length} askelta")
        print(f"- Laskenta-aika: {self.initial_calculation_time:.8f} sekuntia")
        print(f"- Tutkitut ruudut: {self.initial_visited_count}")

        print("\nDynaaminen muutos")
        print(f"- Este lisätty: {self.dynamic_obstacle_added}")
        print(f"- Esteen sijainti: {self.dynamic_obstacle_position}")

        print("\nUudelleenreititys")
        print(f"- Uudelleenreititysten määrä: {self.reroute_count}")
        print(f"- Uudelleenreititysten laskenta-aika yhteensä: {self.total_replanning_time:.8f} sekuntia")
        print(f"- Uudelleenreitityksissä tutkitut ruudut yhteensä: {self.total_replanning_visited_count}")

        print("\nToteutunut toimitus")
        print(f"- Toteutunut kuljettu matka: {self.travelled_distance} askelta")
        print(f"- Toimitusviive: {self.delivery_delay} askelta")
        print(f"- Kokonaislaskenta-aika: {self.total_calculation_time:.8f} sekuntia")
        print(f"- Onnistui: {self.success}")
        print("==============================\n")