import pygame
import sys
import time

from config import (
    WINDOW_WIDTH,
    WINDOW_HEIGHT,
    CELL_SIZE,
    WHITE,
    LIGHT_GRAY,
    BLACK,
    GREEN,
    RED,
    BLUE,
    YELLOW,
    ORANGE,
    DARK_GRAY,
    VISITED_ANIMATION_DELAY_MS,
    PATH_ANIMATION_DELAY_MS,
    VEHICLE_MOVE_DELAY_MS,
)
from grid import Grid
from algorithms import dijkstra, astar
from dstar_lite import DStarLite, dstar_lite_search
from metrics import SimulationMetrics


def mouse_position_to_cell(mouse_pos):
    """
    Muuntaa hiiren pikselisijainnin ruudukon riviksi ja sarakkeeksi.

    Tätä funktiota kutsutaan vasta sen jälkeen, kun on tarkistettu,
    että hiiren sijainti on ruudukkoalueella.
    """
    x, y = mouse_pos
    row = y // CELL_SIZE
    col = x // CELL_SIZE
    return row, col


def is_inside_grid_area(mouse_pos):
    """Palauttaa True, jos hiiren sijainti on varsinaisella ruudukkoalueella."""
    x, y = mouse_pos
    return 0 <= x < WINDOW_WIDTH and 0 <= y < WINDOW_HEIGHT


def algorithm_display_name(selected_algorithm):
    """Muuntaa sisäisen algoritmiavaimen käyttäjälle näytettäväksi nimeksi."""
    names = {
        "dijkstra": "Dijkstra",
        "astar": "A*",
        "dstar_lite": "D* Lite",
    }
    return names.get(selected_algorithm, selected_algorithm or "---")


def next_click_display_name(placement_mode):
    """Kertoo käyttäjälle, mitä seuraava ruudukkoklikkaus tekee."""
    names = {
        "start": "asettaa lähtöpisteen",
        "goal": "asettaa maalin",
    }
    return names.get(placement_mode, "piirtää esteen")


# Ruudukon alapuolelle varattu käyttöliittymäpaneeli.
# Korkeus riittää ohjeteksteille ja kahdelle painikeriville.
PANEL_HEIGHT = 184
GUIDE_HEIGHT = 88
BUTTON_WIDTH = 112
BUTTON_HEIGHT = 28
BUTTON_MARGIN = 6
DISABLED_BUTTON_COLOR = (150, 150, 150)
DISABLED_TEXT_COLOR = (90, 90, 90)
AUTO_OBSTACLE_COLOR = (160, 80, 200)
AUTO_OBSTACLE_MIN = 0
AUTO_OBSTACLE_MAX = 10
AUTO_OBSTACLE_DECREASE_KEY = pygame.K_MINUS
AUTO_OBSTACLE_INCREASE_KEY = pygame.K_EQUALS


class Button:
    """Yksinkertainen Pygame-painike."""
    def __init__(self, x, y, w, h, label, key=None, color=LIGHT_GRAY, hover_color=(200, 200, 200)):
        self.rect = pygame.Rect(x, y, w, h)
        self.label = label
        self.key = key
        self.color = color
        self.hover_color = hover_color
        self.hover = False
        self.enabled = True

    def draw(self, screen, font):
        if not self.enabled:
            color = DISABLED_BUTTON_COLOR
            text_color = DISABLED_TEXT_COLOR
        else:
            color = self.hover_color if self.hover else self.color
            text_color = BLACK

        pygame.draw.rect(screen, color, self.rect)
        pygame.draw.rect(screen, BLACK, self.rect, 1)
        txt = font.render(self.label, True, text_color)
        txt_r = txt.get_rect(center=self.rect.center)
        screen.blit(txt, txt_r)

    def update_hover(self, mouse_pos):
        self.hover = self.enabled and self.rect.collidepoint(mouse_pos)

    def is_clicked(self, mouse_pos):
        return self.enabled and self.rect.collidepoint(mouse_pos)


def create_ui_buttons():
    """Luo käyttöliittymäpaneelin painikkeet käyttöjärjestyksen mukaiseen järjestykseen."""
    labels = [
        ("1 Aseta lähtö", pygame.K_s),
        ("2 Aseta maali", pygame.K_g),
        ("3 Satunnaiset", pygame.K_p),
        ("4 Dijkstra", pygame.K_d),
        ("4 A*", pygame.K_a),
        ("4 D* Lite", pygame.K_l),
        ("Esteet -", AUTO_OBSTACLE_DECREASE_KEY),
        ("Esteet +", AUTO_OBSTACLE_INCREASE_KEY),
        ("5 Laske reitti", pygame.K_SPACE),
        ("6 Aloita ajo", pygame.K_RETURN),
        ("Tyhjennä", pygame.K_c),
    ]

    buttons = []
    x = BUTTON_MARGIN
    y = WINDOW_HEIGHT + GUIDE_HEIGHT + BUTTON_MARGIN

    for label, key in labels:
        if x + BUTTON_WIDTH > WINDOW_WIDTH - BUTTON_MARGIN:
            x = BUTTON_MARGIN
            y += BUTTON_HEIGHT + BUTTON_MARGIN

        buttons.append(
            Button(x, y, BUTTON_WIDTH, BUTTON_HEIGHT, label, key)
        )
        x += BUTTON_WIDTH + BUTTON_MARGIN

    return buttons


def update_button_states(buttons, grid, selected_algorithm, path, last_result, auto_obstacle_count):
    """Päivittää painikkeiden käytössä/pois käytöstä -tilan nykyisen tilanteen perusteella."""
    has_start = grid.start is not None
    has_goal = grid.goal is not None
    has_start_and_goal = has_start and has_goal
    has_algorithm = selected_algorithm is not None
    can_calculate_route = has_start_and_goal and has_algorithm
    can_start_drive = bool(path) and last_result is not None and last_result.get("success", False)

    for button in buttons:
        if button.key == pygame.K_p:
            # Satunnaisesteet kannattaa luoda vasta, kun lähtö ja maali ovat olemassa.
            button.enabled = has_start_and_goal
        elif button.key == AUTO_OBSTACLE_DECREASE_KEY:
            # Ajonaikaisten esteiden valitsin aktivoituu vasta algoritmin valinnan jälkeen.
            button.enabled = has_algorithm and auto_obstacle_count > AUTO_OBSTACLE_MIN
        elif button.key == AUTO_OBSTACLE_INCREASE_KEY:
            button.enabled = has_algorithm and auto_obstacle_count < AUTO_OBSTACLE_MAX
        elif button.key in (pygame.K_d, pygame.K_a, pygame.K_l):
            # Algoritmin valinta tulee käyttöjärjestyksessä lähtö- ja maalipisteen jälkeen.
            button.enabled = has_start_and_goal
        elif button.key == pygame.K_SPACE:
            button.enabled = can_calculate_route
        elif button.key == pygame.K_RETURN:
            button.enabled = can_start_drive
        else:
            button.enabled = True


def draw_grid(screen, grid, path=None, visited=None, vehicle_position=None, buttons=None, font=None, selected_algorithm=None, placement_mode=None, auto_obstacle_count=0, auto_obstacle_positions=None):
    """
    Piirtää ruudukon, esteet, lähtöpisteen, kohdepisteen,
    algoritmin tutkimat ruudut, löydetyn reitin ja ajoneuvon.
    """
    if path is None:
        path = []

    if visited is None:
        visited = []

    if auto_obstacle_positions is None:
        auto_obstacle_positions = set()

    screen.fill(WHITE)

    path_set = set(path)
    visited_set = set(visited)

    for row in range(grid.rows):
        for col in range(grid.cols):
            position = (row, col)

            rect = pygame.Rect(
                col * CELL_SIZE,
                row * CELL_SIZE,
                CELL_SIZE,
                CELL_SIZE
            )

            if position == vehicle_position:
                pygame.draw.rect(screen, ORANGE, rect)
            elif position == grid.start:
                pygame.draw.rect(screen, GREEN, rect)
            elif position == grid.goal:
                pygame.draw.rect(screen, RED, rect)
            elif position in auto_obstacle_positions:
                pygame.draw.rect(screen, AUTO_OBSTACLE_COLOR, rect)
            elif grid.is_obstacle(row, col):
                pygame.draw.rect(screen, BLACK, rect)
            elif position in path_set:
                pygame.draw.rect(screen, BLUE, rect)
            elif position in visited_set:
                pygame.draw.rect(screen, YELLOW, rect)
            else:
                pygame.draw.rect(screen, WHITE, rect)

            pygame.draw.rect(screen, LIGHT_GRAY, rect, 1)

    # Piirretään UI-paneeli ruudukon alapuolelle, jos nappipaneeli annettu.
    if buttons is not None and font is not None:
        panel_rect = pygame.Rect(0, WINDOW_HEIGHT, WINDOW_WIDTH, PANEL_HEIGHT)
        pygame.draw.rect(screen, DARK_GRAY, panel_rect)

        obstacle_selector_state = "käytössä" if selected_algorithm is not None else "valitse ensin algoritmi"
        guide_lines = [
            "Käyttöjärjestys: 1) Aseta lähtö  2) Aseta maali  3) Piirrä esteet hiirellä tai valitse \"satunnaiset\"",
            "4) Valitse algoritmi  5) Valitse ajonaikaiset esteet  6) Laske reitti  7) Aloita ajo",
            f"Valittu algoritmi: {algorithm_display_name(selected_algorithm)}   |   Ajonaikaiset esteet: {auto_obstacle_count} ({obstacle_selector_state}, 0-10)",
            f"Seuraava klikkaus: {next_click_display_name(placement_mode)}",
        ]

        y = WINDOW_HEIGHT + 6
        for line in guide_lines:
            line_surf = font.render(line, True, WHITE)
            screen.blit(line_surf, (BUTTON_MARGIN, y))
            y += line_surf.get_height() + 3

        for b in buttons:
            b.draw(screen, font)

def animate_search(screen, grid, visited_order, path, vehicle_position=None, buttons=None, font=None, selected_algorithm=None, placement_mode=None, auto_obstacle_count=0, auto_obstacle_positions=None):
    """
    Näyttää algoritmin etenemisen vaiheittain.

    Varsinainen laskenta on tehty ennen tätä, joten animaation viive
    ei vaikuta mitattuun laskenta-aikaan.
    """
    if auto_obstacle_positions is None:
        auto_obstacle_positions = set()

    shown_visited = []
    visited_step = get_animation_step(len(visited_order))

    for index, cell in enumerate(visited_order):
        shown_visited.append(cell)
        is_last_cell = index == len(visited_order) - 1

        if index % visited_step != 0 and not is_last_cell:
            continue

        draw_grid(
            screen,
            grid,
            path=[],
            visited=shown_visited,
            vehicle_position=vehicle_position,
            buttons=buttons,
            font=font,
            selected_algorithm=selected_algorithm,
            placement_mode=placement_mode,
            auto_obstacle_count=auto_obstacle_count,
            auto_obstacle_positions=auto_obstacle_positions,
        )
        pygame.display.flip()
        pygame.time.delay(VISITED_ANIMATION_DELAY_MS)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

    shown_path = []

    for cell in path:
        shown_path.append(cell)

        draw_grid(
            screen,
            grid,
            path=shown_path,
            visited=visited_order,
            vehicle_position=vehicle_position,
            buttons=buttons,
            font=font,
            selected_algorithm=selected_algorithm,
            placement_mode=placement_mode,
            auto_obstacle_count=auto_obstacle_count,
            auto_obstacle_positions=auto_obstacle_positions,
        )
        pygame.display.flip()
        pygame.time.delay(PATH_ANIMATION_DELAY_MS)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()


def run_selected_algorithm(grid, selected_algorithm, start, goal):
    """
    Suorittaa käyttäjän valitseman algoritmin annetusta lähtöruudusta kohderuutuun.
    """
    if selected_algorithm == "dijkstra":
        return dijkstra(grid, start, goal)

    if selected_algorithm == "astar":
        return astar(grid, start, goal)

    if selected_algorithm == "dstar_lite":
        return dstar_lite_search(grid, start, goal)

    raise ValueError(f"Tuntematon algoritmi: {selected_algorithm}")

def print_result(result, prefix=None):
    """
    Tulostaa algoritmin tulokset terminaaliin.
    """
    title = result["algorithm"]

    if prefix is not None:
        title = f"{prefix}: {title}"

    print(f"\n{title}")
    print(f"Onnistui: {result['success']}")
    print(f"Reitin pituus: {result['path_length']} askelta")
    print(f"Tutkitut ruudut: {result['visited_count']}")
    print(f"Laskenta-aika: {result['calculation_time']:.8f} sekuntia")


def get_animation_step(total_items):
    """Nopeuttaa hakuvaiheen visualisointia, kun tutkittuja ruutuja on paljon."""
    if total_items <= 200:
        return 1
    if total_items <= 500:
        return 3
    if total_items <= 1000:
        return 5
    if total_items <= 3000:
        return 10
    return 20


def get_vehicle_delay(path_length):
    """Nopeuttaa ajoneuvon etenemisanimaatiota pitkillä reiteillä."""
    if path_length <= 50:
        return VEHICLE_MOVE_DELAY_MS
    if path_length <= 100:
        return max(20, VEHICLE_MOVE_DELAY_MS // 2)
    if path_length <= 200:
        return max(10, VEHICLE_MOVE_DELAY_MS // 4)
    return max(5, VEHICLE_MOVE_DELAY_MS // 8)


def get_auto_obstacle_trigger_fractions(auto_obstacle_count):
    """
    Palauttaa etenemiskohdat, joissa automaattiset esteet yritetään lisätä.

    Arvot jaetaan toimituksen alku- ja loppuosan väliin, jotta esteitä ei
    lisätä heti alussa tai aivan maaliruudun vieressä.
    """
    count = max(AUTO_OBSTACLE_MIN, min(AUTO_OBSTACLE_MAX, auto_obstacle_count))

    if count == 0:
        return []

    if count == 1:
        return [0.35]

    start_fraction = 0.20
    end_fraction = 0.80
    step = (end_fraction - start_fraction) / (count - 1)

    return [start_fraction + step * index for index in range(count)]


def find_future_obstacle_on_path(grid, current_path, current_index, vehicle_position):
    """
    Etsii nykyiseltä reitiltä ajoneuvon edestä ruudun, johon voidaan lisätä este.
    Maalia, lähtöä tai ajoneuvon nykyistä sijaintia ei käytetä esteenä.
    """
    if len(current_path) < 4:
        return None

    lookahead = max(2, len(current_path) // 10)
    preferred_index = min(len(current_path) - 2, current_index + lookahead)

    candidate_indexes = list(range(preferred_index, len(current_path) - 1))
    candidate_indexes += list(range(current_index + 1, preferred_index))

    for index in candidate_indexes:
        if index <= current_index or index >= len(current_path) - 1:
            continue

        position = current_path[index]
        row, col = position

        if position in (vehicle_position, grid.start, grid.goal):
            continue
        if grid.is_obstacle(row, col):
            continue

        return position

    return None


def should_add_automatic_obstacle(current_index, current_path_length, auto_obstacle_count, auto_obstacles_added):
    """Päättelee, onko seuraavan automaattisen esteen lisäämisen aika."""
    trigger_fractions = get_auto_obstacle_trigger_fractions(auto_obstacle_count)

    if auto_obstacles_added >= len(trigger_fractions):
        return False
    if current_path_length <= 1:
        return False

    progress = current_index / max(1, current_path_length - 1)
    return progress >= trigger_fractions[auto_obstacles_added]


def add_automatic_obstacle_if_needed(
    grid,
    current_path,
    current_index,
    vehicle_position,
    auto_obstacle_count,
    auto_obstacles_added,
):
    """
    Lisää automaattisen dynaamisen esteen nykyisen reitin loppuosalle,
    jos valittu etenemiskohta on saavutettu.
    """
    if not should_add_automatic_obstacle(
        current_index,
        len(current_path),
        auto_obstacle_count,
        auto_obstacles_added,
    ):
        return None

    obstacle_position = find_future_obstacle_on_path(
        grid,
        current_path,
        current_index,
        vehicle_position,
    )

    if obstacle_position is None:
        return None

    row, col = obstacle_position
    grid.add_obstacle(row, col)
    print(f"\nAutomaattinen dynaaminen este lisättiin ruutuun: {obstacle_position}")
    return obstacle_position


def handle_dynamic_click(grid, vehicle_position, mouse_pos):
    """
    Käsittelee ajon aikana tehdyn klikkauksen.

    Klikattu ruutu muuttuu esteeksi, jos se ei ole:
    - ajoneuvon nykyinen sijainti
    - lähtöpiste
    - kohdepiste

    Palauttaa lisätyn esteen sijainnin tai None.
    """
    if not is_inside_grid_area(mouse_pos):
        return None

    row, col = mouse_position_to_cell(mouse_pos)
    obstacle_position = (row, col)

    if not (0 <= row < grid.rows and 0 <= col < grid.cols):
        return None

    if obstacle_position == vehicle_position:
        print("Et voi lisätä estettä ajoneuvon nykyiseen sijaintiin.")
        return None

    if obstacle_position == grid.start or obstacle_position == grid.goal:
        print("Et voi lisätä estettä lähtö- tai kohdepisteeseen.")
        return None

    grid.add_obstacle(row, col)
    print(f"\nManuaalinen dynaaminen este lisättiin ruutuun: {obstacle_position}")

    return obstacle_position


def animate_vehicle_with_manual_obstacles(
    screen,
    grid,
    initial_path,
    initial_visited,
    selected_algorithm,
    initial_result,
    buttons=None,
    font=None,
    auto_obstacle_count=0
):
    """
    Liikuttaa ajoneuvoa reittiä pitkin.

    Ajon aikana käyttäjä voi lisätä esteen hiiren vasemmalla klikkauksella.
    Jos este osuu jäljellä olevalle reitille, algoritmi laskee uuden reitin
    ajoneuvon nykyisestä sijainnista kohdepisteeseen.
    """
    metrics = SimulationMetrics(initial_result["algorithm"])
    metrics.set_scenario_info(grid)
    metrics.set_initial_result(initial_result)

    # Tallennetaan alkuperäiset esteet, jotta manuaaliset dynaamiset esteet
    # eivät jää seuraavaan ajoon.
    base_obstacles = set(grid.obstacles)
    auto_obstacle_positions = set()

    if not initial_path:
        print("Reittiä ei ole, joten ajoneuvo ei voi liikkua.")
        metrics.set_success(False)
        metrics.print_summary()
        metrics.save_to_csv("results.csv")
        print("Tulokset tallennettu tiedostoon results.csv")
        grid.obstacles = set(base_obstacles)
        return [], [], None, auto_obstacle_positions

    current_path = initial_path
    current_visited = initial_visited
    vehicle_position = current_path[0]

    travelled_path = []
    current_index = 0
    auto_obstacles_added = 0

    while current_index < len(current_path):
        vehicle_position = current_path[current_index]
        travelled_path.append(vehicle_position)

        draw_grid(
            screen,
            grid,
            path=current_path,
            visited=current_visited,
            vehicle_position=vehicle_position,
            buttons=buttons,
            font=font,
            selected_algorithm=selected_algorithm,
            placement_mode=None,
            auto_obstacle_count=auto_obstacle_count,
            auto_obstacle_positions=auto_obstacle_positions,
        )
        pygame.display.flip()

        automatic_obstacle_position = add_automatic_obstacle_if_needed(
            grid,
            current_path,
            current_index,
            vehicle_position,
            auto_obstacle_count,
            auto_obstacles_added,
        )

        if automatic_obstacle_position is not None:
            auto_obstacles_added += 1
            auto_obstacle_positions.add(automatic_obstacle_position)
            metrics.set_dynamic_obstacle(automatic_obstacle_position)
            print("Automaattinen este vaikuttaa jäljellä olevaan reittiin. Lasketaan uusi reitti.")
            metrics.add_effective_obstacle(automatic_obstacle_position)

            reroute_result = run_selected_algorithm(
                grid,
                selected_algorithm,
                vehicle_position,
                grid.goal
            )

            metrics.add_reroute_result(reroute_result)
            print_result(reroute_result, prefix="Uudelleenreititys")

            if not reroute_result["success"]:
                print("Uutta reittiä ei löytynyt. Simulaatio keskeytyy.")
                metrics.set_travelled_path(travelled_path)
                metrics.set_success(False)
                metrics.print_summary()
                metrics.save_to_csv("results.csv")
                print("Tulokset tallennettu tiedostoon results.csv")
                grid.obstacles = set(base_obstacles)
                return travelled_path, current_visited, vehicle_position, auto_obstacle_positions

            current_path = reroute_result["path"]
            current_visited = reroute_result["visited_order"]

            animate_search(
                screen,
                grid,
                current_visited,
                current_path,
                vehicle_position=vehicle_position,
                buttons=buttons,
                font=font,
                selected_algorithm=selected_algorithm,
                placement_mode=None,
                auto_obstacle_count=auto_obstacle_count,
                auto_obstacle_positions=auto_obstacle_positions,
            )

            current_index = 0
            continue

        start_tick = pygame.time.get_ticks()
        rerouted = False
        vehicle_delay = get_vehicle_delay(len(current_path))

        while pygame.time.get_ticks() - start_tick < vehicle_delay:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()

                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mouse_pos = pygame.mouse.get_pos()

                    if not is_inside_grid_area(mouse_pos):
                        continue

                    obstacle_position = handle_dynamic_click(
                        grid,
                        vehicle_position,
                        mouse_pos
                    )

                    if obstacle_position is None:
                        continue

                    metrics.set_dynamic_obstacle(obstacle_position)

                    remaining_path = current_path[current_index + 1:]

                    if obstacle_position in remaining_path:
                        print("Este vaikuttaa jäljellä olevaan reittiin. Lasketaan uusi reitti.")
                        metrics.add_effective_obstacle(obstacle_position)

                        reroute_result = run_selected_algorithm(
                            grid,
                            selected_algorithm,
                            vehicle_position,
                            grid.goal
                        )

                        metrics.add_reroute_result(reroute_result)
                        print_result(reroute_result, prefix="Uudelleenreititys")

                        if not reroute_result["success"]:
                            print("Uutta reittiä ei löytynyt. Simulaatio keskeytyy.")
                            metrics.set_travelled_path(travelled_path)
                            metrics.set_success(False)
                            metrics.print_summary()
                            metrics.save_to_csv("results.csv")
                            print("Tulokset tallennettu tiedostoon results.csv")
                            grid.obstacles = set(base_obstacles)
                            return travelled_path, current_visited, vehicle_position, auto_obstacle_positions

                        current_path = reroute_result["path"]
                        current_visited = reroute_result["visited_order"]

                        animate_search(
                            screen,
                            grid,
                            current_visited,
                            current_path,
                            vehicle_position=vehicle_position,
                            buttons=buttons,
                            font=font,
                            selected_algorithm=selected_algorithm,
                            placement_mode=None,
                            auto_obstacle_count=auto_obstacle_count,
                            auto_obstacle_positions=auto_obstacle_positions,
                        )

                        # Uusi reitti alkaa ajoneuvon nykyisestä sijainnista.
                        current_index = 0
                        rerouted = True
                        break

                    else:
                        print("Este ei vaikuta jäljellä olevaan reittiin. Ajoneuvo jatkaa samaa reittiä.")

            if rerouted:
                break

        if rerouted:
            continue

        current_index += 1

    print("\nAjoneuvo saavutti kohdepisteen.")

    metrics.set_travelled_path(travelled_path)
    metrics.set_success(True)
    metrics.print_summary()
    metrics.save_to_csv("results.csv")
    print("Tulokset tallennettu tiedostoon results.csv")

    # Palautetaan alkuperäiset esteet, jotta seuraava ajo alkaa samasta lähtötilanteesta.
    grid.obstacles = set(base_obstacles)

    return current_path, current_visited, vehicle_position, auto_obstacle_positions

def animate_vehicle_with_dstar_lite(
    screen,
    grid,
    initial_path,
    initial_visited,
    initial_result,
    buttons=None,
    font=None,
    auto_obstacle_count=0
):
    """
    Liikuttaa ajoneuvoa D* Lite -reitillä inkrementaalisesti.

    Tässä versiossa D* Lite -planner säilytetään koko ajon ajan.
    Kun ajoneuvo liikkuu, plannerin lähtöpiste päivitetään.
    Kun käyttäjä lisää esteen ajon aikana, planner päivittää aiemmat
    g- ja rhs-arvot eikä aloita koko hakua alusta.
    """
    metrics = SimulationMetrics(initial_result["algorithm"])
    metrics.set_scenario_info(grid)
    metrics.set_initial_result(initial_result)

    base_obstacles = set(grid.obstacles)
    auto_obstacle_positions = set()

    if not initial_path:
        print("Reittiä ei ole, joten ajoneuvo ei voi liikkua.")
        metrics.set_success(False)
        metrics.print_summary()
        metrics.save_to_csv("results.csv")
        print("Tulokset tallennettu tiedostoon results.csv")
        grid.obstacles = set(base_obstacles)
        return [], [], None, auto_obstacle_positions

    # Luodaan D* Lite -planner kerran koko ajon ajaksi.
    planner = DStarLite(grid, grid.start, grid.goal)
    planner.compute_shortest_path(reset_visited=True)

    current_path = planner.get_path()
    current_visited = list(planner.visited_order)

    vehicle_position = current_path[0]
    travelled_path = []
    current_index = 0
    auto_obstacles_added = 0

    while current_index < len(current_path):
        vehicle_position = current_path[current_index]
        travelled_path.append(vehicle_position)

        # Päivitetään D* Liten nykyinen lähtöpiste ajoneuvon sijaintiin.
        planner.move_start(vehicle_position)

        draw_grid(
            screen,
            grid,
            path=current_path,
            visited=current_visited,
            vehicle_position=vehicle_position,
            buttons=buttons,
            font=font,
            selected_algorithm=initial_result.get("algorithm", "D* Lite"),
            placement_mode=None,
            auto_obstacle_count=auto_obstacle_count,
            auto_obstacle_positions=auto_obstacle_positions,
        )
        pygame.display.flip()

        automatic_obstacle_position = add_automatic_obstacle_if_needed(
            grid,
            current_path,
            current_index,
            vehicle_position,
            auto_obstacle_count,
            auto_obstacles_added,
        )

        if automatic_obstacle_position is not None:
            auto_obstacles_added += 1
            auto_obstacle_positions.add(automatic_obstacle_position)
            metrics.set_dynamic_obstacle(automatic_obstacle_position)
            print(
                "Automaattinen este vaikuttaa jäljellä olevaan reittiin. "
                "Päivitetään D* Lite -planneria inkrementaalisesti."
            )
            metrics.add_effective_obstacle(automatic_obstacle_position)

            replanning_start_time = time.perf_counter()
            planner.update_obstacle(automatic_obstacle_position)
            planner.compute_shortest_path(reset_visited=True)
            replanning_end_time = time.perf_counter()
            replanning_time = replanning_end_time - replanning_start_time

            new_path = planner.get_path()
            new_visited = list(planner.visited_order)

            reroute_result = {
                "algorithm": "D* Lite",
                "path": new_path,
                "visited_order": new_visited,
                "calculation_time": replanning_time,
                "visited_count": len(new_visited),
                "path_length": max(0, len(new_path) - 1),
                "success": len(new_path) > 0,
            }

            metrics.add_reroute_result(reroute_result)
            print_result(reroute_result, prefix="Uudelleenreititys")

            if not reroute_result["success"]:
                print("Uutta reittiä ei löytynyt. Simulaatio keskeytyy.")
                metrics.set_travelled_path(travelled_path)
                metrics.set_success(False)
                metrics.print_summary()
                metrics.save_to_csv("results.csv")
                print("Tulokset tallennettu tiedostoon results.csv")
                grid.obstacles = set(base_obstacles)
                return travelled_path, current_visited, vehicle_position, auto_obstacle_positions

            current_path = new_path
            current_visited = new_visited

            animate_search(
                screen,
                grid,
                current_visited,
                current_path,
                vehicle_position=vehicle_position,
                buttons=buttons,
                font=font,
                selected_algorithm=initial_result.get("algorithm", "D* Lite"),
                placement_mode=None,
                auto_obstacle_count=auto_obstacle_count,
                auto_obstacle_positions=auto_obstacle_positions,
            )

            current_index = 0
            continue

        start_tick = pygame.time.get_ticks()
        rerouted = False
        vehicle_delay = get_vehicle_delay(len(current_path))

        while pygame.time.get_ticks() - start_tick < vehicle_delay:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()

                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mouse_pos = pygame.mouse.get_pos()

                    if not is_inside_grid_area(mouse_pos):
                        continue

                    obstacle_position = handle_dynamic_click(
                        grid,
                        vehicle_position,
                        mouse_pos
                    )

                    if obstacle_position is None:
                        continue

                    metrics.set_dynamic_obstacle(obstacle_position)

                    remaining_path = current_path[current_index + 1:]

                    if obstacle_position in remaining_path:
                        print(
                            "Este vaikuttaa jäljellä olevaan reittiin. "
                            "Päivitetään D* Lite -planneria inkrementaalisesti."
                        )
                        metrics.add_effective_obstacle(obstacle_position)

                        replanning_start_time = time.perf_counter()

                        # Este on jo lisätty grid.obstacles-joukkoon.
                        # Nyt D* Lite päivittää aiempaa tilaansa.
                        planner.update_obstacle(obstacle_position)
                        planner.compute_shortest_path(reset_visited=True)

                        replanning_end_time = time.perf_counter()
                        replanning_time = replanning_end_time - replanning_start_time

                        new_path = planner.get_path()
                        new_visited = list(planner.visited_order)

                        reroute_result = {
                            "algorithm": "D* Lite",
                            "path": new_path,
                            "visited_order": new_visited,
                            "calculation_time": replanning_time,
                            "visited_count": len(new_visited),
                            "path_length": max(0, len(new_path) - 1),
                            "success": len(new_path) > 0,
                        }

                        metrics.add_reroute_result(reroute_result)
                        print_result(reroute_result, prefix="Uudelleenreititys")

                        if not reroute_result["success"]:
                            print("Uutta reittiä ei löytynyt. Simulaatio keskeytyy.")
                            metrics.set_travelled_path(travelled_path)
                            metrics.set_success(False)
                            metrics.print_summary()
                            metrics.save_to_csv("results.csv")
                            print("Tulokset tallennettu tiedostoon results.csv")
                            grid.obstacles = set(base_obstacles)
                            return travelled_path, current_visited, vehicle_position, auto_obstacle_positions

                        current_path = new_path
                        current_visited = new_visited

                        animate_search(
                            screen,
                            grid,
                            current_visited,
                            current_path,
                            vehicle_position=vehicle_position,
                            buttons=buttons,
                            font=font,
                            selected_algorithm=initial_result.get("algorithm", "D* Lite"),
                            placement_mode=None,
                            auto_obstacle_count=auto_obstacle_count,
                            auto_obstacle_positions=auto_obstacle_positions,
                        )

                        # Uusi reitti alkaa ajoneuvon nykyisestä sijainnista.
                        current_index = 0
                        rerouted = True
                        break

                    else:
                        print("Este ei vaikuta jäljellä olevaan reittiin. Ajoneuvo jatkaa samaa reittiä.")

            if rerouted:
                break

        if rerouted:
            continue

        current_index += 1

    print("\nAjoneuvo saavutti kohdepisteen.")

    metrics.set_travelled_path(travelled_path)
    metrics.set_success(True)
    metrics.print_summary()
    metrics.save_to_csv("results.csv")
    print("Tulokset tallennettu tiedostoon results.csv")

    grid.obstacles = set(base_obstacles)

    return current_path, current_visited, vehicle_position, auto_obstacle_positions

def main():
    pygame.init()
    # Ikkuna kasvatetaan paneelia varten
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT + PANEL_HEIGHT))
    pygame.display.set_caption("Ruudukkopohjainen reitinhakusimulaatio")

    clock = pygame.time.Clock()
    grid = Grid()

    # UI -fontti ja napit
    font = pygame.font.Font(None, 20)
    buttons = create_ui_buttons()

    selected_algorithm = None
    auto_obstacle_count = 0
    visible_auto_obstacle_positions = set()

    path = []
    visited = []
    vehicle_position = None
    last_result = None

    drawing_obstacles = False
    erasing_obstacles = False
    last_drawn_cell = None

    # Uusi, luotettavampi asetuslogiikka:
    # S painetaan kerran -> seuraava klikkaus asettaa lähtöpisteen.
    # G painetaan kerran -> seuraava klikkaus asettaa kohdepisteen.
    placement_mode = None

    print("Valitse ensin lähtöpiste, maali, esteet ja algoritmi käyttöliittymän painikkeilla.")
    print("Komennot:")
    print("S = valitse lähtöpisteen asetus, sitten klikkaa ruutua")
    print("G = valitse kohdepisteen asetus, sitten klikkaa ruutua")
    print("Vasen veto = piirrä alkuperäisiä esteitä")
    print("Oikea veto = poista alkuperäisiä esteitä")
    print("D = valitse Dijkstra")
    print("A = valitse A*")
    print("L = valitse D* Lite")
    print("C = tyhjennä ruudukko")
    print("P = generoi satunnaiset esteet")
    print("+ / - = muuta automaattisten ajonaikaisten esteiden määrää algoritmin valinnan jälkeen (0-10)")
    print("Välilyönti = suorita valittu algoritmi")
    print("Enter = aloita ajo")
    print("Ajon aikana vasen klikkaus = lisää dynaaminen este")

    running = True

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.MOUSEBUTTONDOWN:
                mouse_pos = pygame.mouse.get_pos()

                # Jos klikataan UI-paneelia, käsitellään napin klikkaus.
                if mouse_pos[1] >= WINDOW_HEIGHT:
                    for b in buttons:
                        if b.is_clicked(mouse_pos):
                            # Postataan vastaava keydown-event jotta olemassa oleva
                            # näppäinlogiikka hoitaa toiminnon.
                            ev = pygame.event.Event(pygame.KEYDOWN, key=b.key)
                            pygame.event.post(ev)
                            break
                    # UI-alueen klikkauksia ei käsitellä ruudukon klikkauksina
                    continue

                if not is_inside_grid_area(mouse_pos):
                    continue

                row, col = mouse_position_to_cell(mouse_pos)

                if placement_mode == "start":
                    grid.set_start(row, col)
                    placement_mode = None

                    path = []
                    visited = []
                    vehicle_position = None
                    last_result = None

                    print(f"Lähtöpiste asetettu: {(row, col)}")

                elif placement_mode == "goal":
                    grid.set_goal(row, col)
                    placement_mode = None

                    path = []
                    visited = []
                    vehicle_position = None
                    last_result = None

                    print(f"Kohdepiste asetettu: {(row, col)}")

                elif event.button == 1:
                    drawing_obstacles = True
                    erasing_obstacles = False
                    last_drawn_cell = (row, col)

                    grid.add_obstacle(row, col)

                    path = []
                    visited = []
                    vehicle_position = None
                    last_result = None

                elif event.button == 3:
                    erasing_obstacles = True
                    drawing_obstacles = False
                    last_drawn_cell = (row, col)

                    grid.remove_obstacle(row, col)

                    path = []
                    visited = []
                    vehicle_position = None
                    last_result = None

            elif event.type == pygame.MOUSEBUTTONUP:
                drawing_obstacles = False
                erasing_obstacles = False
                last_drawn_cell = None

            elif event.type == pygame.MOUSEMOTION:
                # Päivitetään nappien hover-tila
                for b in buttons:
                    b.update_hover(pygame.mouse.get_pos())

                if drawing_obstacles or erasing_obstacles:
                    mouse_pos = pygame.mouse.get_pos()

                    if not is_inside_grid_area(mouse_pos):
                        continue

                    row, col = mouse_position_to_cell(mouse_pos)
                    current_cell = (row, col)

                    if current_cell != last_drawn_cell:
                        if drawing_obstacles:
                            grid.add_obstacle(row, col)
                        elif erasing_obstacles:
                            grid.remove_obstacle(row, col)

                        last_drawn_cell = current_cell

                        path = []
                        visited = []
                        vehicle_position = None
                        last_result = None

            elif event.type == pygame.KEYDOWN:
                if event.key == AUTO_OBSTACLE_DECREASE_KEY:
                    if selected_algorithm is None:
                        print("\nValitse ensin algoritmi ennen ajonaikaisten esteiden määrää.")
                    else:
                        auto_obstacle_count = max(AUTO_OBSTACLE_MIN, auto_obstacle_count - 1)
                        print(f"\nAutomaattisia ajonaikaisia esteitä: {auto_obstacle_count}")

                elif event.key == AUTO_OBSTACLE_INCREASE_KEY:
                    if selected_algorithm is None:
                        print("\nValitse ensin algoritmi ennen ajonaikaisten esteiden määrää.")
                    else:
                        auto_obstacle_count = min(AUTO_OBSTACLE_MAX, auto_obstacle_count + 1)
                        print(f"\nAutomaattisia ajonaikaisia esteitä: {auto_obstacle_count}")

                elif event.key == pygame.K_s:
                    placement_mode = "start"
                    drawing_obstacles = False
                    erasing_obstacles = False
                    last_drawn_cell = None
                    print("\nLähtöpisteen asetus valittu. Klikkaa ruutua.")

                elif event.key == pygame.K_g:
                    placement_mode = "goal"
                    drawing_obstacles = False
                    erasing_obstacles = False
                    last_drawn_cell = None
                    print("\nKohdepisteen asetus valittu. Klikkaa ruutua.")

                elif event.key == pygame.K_d:
                    selected_algorithm = "dijkstra"
                    placement_mode = None

                    path = []
                    visited = []
                    vehicle_position = None
                    last_result = None
                    visible_auto_obstacle_positions.clear()
                    print("\nValittu algoritmi: Dijkstra")

                elif event.key == pygame.K_a:
                    selected_algorithm = "astar"
                    placement_mode = None

                    path = []
                    visited = []
                    vehicle_position = None
                    last_result = None
                    visible_auto_obstacle_positions.clear()
                    print("\nValittu algoritmi: A*")

                elif event.key == pygame.K_l:
                    selected_algorithm = "dstar_lite"
                    placement_mode = None

                    path = []
                    visited = []
                    vehicle_position = None
                    last_result = None
                    visible_auto_obstacle_positions.clear()
                    print("\nValittu algoritmi: D* Lite")

                elif event.key == pygame.K_c:
                    grid.clear()
                    placement_mode = None

                    path = []
                    visited = []
                    vehicle_position = None
                    last_result = None
                    visible_auto_obstacle_positions.clear()
                    print("\nRuudukko tyhjennetty.")

                elif event.key == pygame.K_p:
                    grid.generate_random_obstacles()
                    placement_mode = None

                    path = []
                    visited = []
                    vehicle_position = None
                    last_result = None

                    print("\nSatunnaiset esteet generoitu.")
                    print(f"Esteiden määrä: {len(grid.obstacles)}")

                elif event.key == pygame.K_SPACE:
                    placement_mode = None

                    if grid.start is None or grid.goal is None:
                        print("Aseta ensin lähtöpiste ja kohdepiste.")
                    elif selected_algorithm is None:
                        print("Valitse ensin algoritmi: Dijkstra, A* tai D* Lite.")
                    else:
                        result = run_selected_algorithm(
                            grid,
                            selected_algorithm,
                            grid.start,
                            grid.goal
                        )

                        last_result = result
                        path = result["path"]
                        visited = result["visited_order"]
                        vehicle_position = None

                        print_result(result)
                        animate_search(
                            screen,
                            grid,
                            visited,
                            path,
                            buttons=buttons,
                            font=font,
                            selected_algorithm=selected_algorithm,
                            placement_mode=placement_mode,
                            auto_obstacle_count=auto_obstacle_count,
                            auto_obstacle_positions=visible_auto_obstacle_positions,
                        )

                elif event.key == pygame.K_RETURN:
                    placement_mode = None

                    if not path or last_result is None or not last_result.get("success", False):
                        print("Laske ensin onnistunut reitti.")
                    else:
                        if selected_algorithm == "dstar_lite":
                            path, visited, vehicle_position, visible_auto_obstacle_positions = animate_vehicle_with_dstar_lite(
                                screen,
                                grid,
                                path,
                                visited,
                                last_result,
                                buttons=buttons,
                                font=font,
                                auto_obstacle_count=auto_obstacle_count
                            )
                        else:
                            path, visited, vehicle_position, visible_auto_obstacle_positions = animate_vehicle_with_manual_obstacles(
                                screen,
                                grid,
                                path,
                                visited,
                                selected_algorithm,
                                last_result,
                                buttons=buttons,
                                font=font,
                                auto_obstacle_count=auto_obstacle_count
                            )

        update_button_states(buttons, grid, selected_algorithm, path, last_result, auto_obstacle_count)

        draw_grid(
            screen,
            grid,
            path=path,
            visited=visited,
            vehicle_position=vehicle_position,
            buttons=buttons,
            font=font,
            selected_algorithm=selected_algorithm,
            placement_mode=placement_mode,
            auto_obstacle_count=auto_obstacle_count,
            auto_obstacle_positions=visible_auto_obstacle_positions,
        )
        pygame.display.flip()

        clock.tick(60)

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()