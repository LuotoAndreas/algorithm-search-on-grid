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
    """
    x, y = mouse_pos
    row = y // CELL_SIZE
    col = x // CELL_SIZE
    return row, col


def draw_grid(screen, grid, path=None, visited=None, vehicle_position=None):
    """
    Piirtää ruudukon, esteet, lähtöpisteen, kohdepisteen,
    algoritmin tutkimat ruudut, löydetyn reitin ja ajoneuvon.
    """
    if path is None:
        path = []

    if visited is None:
        visited = []

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
            elif grid.is_obstacle(row, col):
                pygame.draw.rect(screen, BLACK, rect)
            elif position in path_set:
                pygame.draw.rect(screen, BLUE, rect)
            elif position in visited_set:
                pygame.draw.rect(screen, YELLOW, rect)
            else:
                pygame.draw.rect(screen, WHITE, rect)

            pygame.draw.rect(screen, LIGHT_GRAY, rect, 1)


def animate_search(screen, grid, visited_order, path, vehicle_position=None):
    """
    Näyttää algoritmin etenemisen vaiheittain.

    Varsinainen laskenta on tehty ennen tätä, joten animaation viive
    ei vaikuta mitattuun laskenta-aikaan.
    """
    shown_visited = []

    for cell in visited_order:
        shown_visited.append(cell)

        draw_grid(
            screen,
            grid,
            path=[],
            visited=shown_visited,
            vehicle_position=vehicle_position
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
            vehicle_position=vehicle_position
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


def handle_dynamic_click(grid, vehicle_position):
    """
    Käsittelee ajon aikana tehdyn klikkauksen.

    Klikattu ruutu muuttuu esteeksi, jos se ei ole:
    - ajoneuvon nykyinen sijainti
    - lähtöpiste
    - kohdepiste

    Palauttaa lisätyn esteen sijainnin tai None.
    """
    row, col = mouse_position_to_cell(pygame.mouse.get_pos())
    obstacle_position = (row, col)

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
    initial_result
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

    if not initial_path:
        print("Reittiä ei ole, joten ajoneuvo ei voi liikkua.")
        metrics.set_success(False)
        metrics.print_summary()
        metrics.save_to_csv("results.csv")
        print("Tulokset tallennettu tiedostoon results.csv")
        grid.obstacles = set(base_obstacles)
        return [], [], None

    current_path = initial_path
    current_visited = initial_visited
    vehicle_position = current_path[0]

    travelled_path = []
    current_index = 0

    while current_index < len(current_path):
        vehicle_position = current_path[current_index]
        travelled_path.append(vehicle_position)

        draw_grid(
            screen,
            grid,
            path=current_path,
            visited=current_visited,
            vehicle_position=vehicle_position
        )
        pygame.display.flip()

        start_tick = pygame.time.get_ticks()
        rerouted = False

        while pygame.time.get_ticks() - start_tick < VEHICLE_MOVE_DELAY_MS:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()

                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    obstacle_position = handle_dynamic_click(
                        grid,
                        vehicle_position
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
                            return travelled_path, current_visited, vehicle_position

                        current_path = reroute_result["path"]
                        current_visited = reroute_result["visited_order"]

                        animate_search(
                            screen,
                            grid,
                            current_visited,
                            current_path,
                            vehicle_position=vehicle_position
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

    return current_path, current_visited, vehicle_position

def animate_vehicle_with_dstar_lite(
    screen,
    grid,
    initial_path,
    initial_visited,
    initial_result
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

    if not initial_path:
        print("Reittiä ei ole, joten ajoneuvo ei voi liikkua.")
        metrics.set_success(False)
        metrics.print_summary()
        metrics.save_to_csv("results.csv")
        print("Tulokset tallennettu tiedostoon results.csv")
        grid.obstacles = set(base_obstacles)
        return [], [], None

    # Luodaan D* Lite -planner kerran koko ajon ajaksi.
    planner = DStarLite(grid, grid.start, grid.goal)
    planner.compute_shortest_path(reset_visited=True)

    current_path = planner.get_path()
    current_visited = list(planner.visited_order)

    vehicle_position = current_path[0]
    travelled_path = []
    current_index = 0

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
            vehicle_position=vehicle_position
        )
        pygame.display.flip()

        start_tick = pygame.time.get_ticks()
        rerouted = False

        while pygame.time.get_ticks() - start_tick < VEHICLE_MOVE_DELAY_MS:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()

                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    obstacle_position = handle_dynamic_click(
                        grid,
                        vehicle_position
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
                            return travelled_path, current_visited, vehicle_position

                        current_path = new_path
                        current_visited = new_visited

                        animate_search(
                            screen,
                            grid,
                            current_visited,
                            current_path,
                            vehicle_position=vehicle_position
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

    return current_path, current_visited, vehicle_position

def main():
    pygame.init()

    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption("Ruudukkopohjainen reitinhakusimulaatio")

    clock = pygame.time.Clock()
    grid = Grid()

    selected_algorithm = "dijkstra"

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

    print("Valittu algoritmi: Dijkstra")
    print("Komennot:")
    print("S = valitse lähtöpisteen asetus, sitten klikkaa ruutua")
    print("G = valitse kohdepisteen asetus, sitten klikkaa ruutua")
    print("Vasen veto = piirrä alkuperäisiä esteitä")
    print("Oikea veto = poista alkuperäisiä esteitä")
    print("D = valitse Dijkstra")
    print("A = valitse A*")
    print("L = valitse D* Lite")
    print("C = tyhjennä ruudukko")
    print("Välilyönti = suorita valittu algoritmi")
    print("Enter = aloita ajo")
    print("Ajon aikana vasen klikkaus = lisää dynaaminen este")

    running = True

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.MOUSEBUTTONDOWN:
                row, col = mouse_position_to_cell(pygame.mouse.get_pos())

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
                if drawing_obstacles or erasing_obstacles:
                    row, col = mouse_position_to_cell(pygame.mouse.get_pos())
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
                if event.key == pygame.K_s:
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

                    print("\nValittu algoritmi: Dijkstra")

                elif event.key == pygame.K_a:
                    selected_algorithm = "astar"
                    placement_mode = None

                    path = []
                    visited = []
                    vehicle_position = None
                    last_result = None

                    print("\nValittu algoritmi: A*")

                elif event.key == pygame.K_l:
                    selected_algorithm = "dstar_lite"
                    placement_mode = None

                    path = []
                    visited = []
                    vehicle_position = None
                    last_result = None

                    print("\nValittu algoritmi: D* Lite")

                elif event.key == pygame.K_c:
                    grid.clear()
                    placement_mode = None

                    path = []
                    visited = []
                    vehicle_position = None
                    last_result = None

                    print("\nRuudukko tyhjennetty.")

                elif event.key == pygame.K_SPACE:
                    placement_mode = None

                    if grid.start is None or grid.goal is None:
                        print("Aseta ensin lähtöpiste S-näppäimellä ja kohdepiste G-näppäimellä.")
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
                        animate_search(screen, grid, visited, path)

                elif event.key == pygame.K_RETURN:
                    placement_mode = None

                    if not path or last_result is None:
                        print("Laske ensin reitti välilyönnillä.")
                    else:
                        if selected_algorithm == "dstar_lite":
                            path, visited, vehicle_position = animate_vehicle_with_dstar_lite(
                                screen,
                                grid,
                                path,
                                visited,
                                last_result
                            )
                        else:
                            path, visited, vehicle_position = animate_vehicle_with_manual_obstacles(
                                screen,
                                grid,
                                path,
                                visited,
                                selected_algorithm,
                                last_result
                            )

        draw_grid(
            screen,
            grid,
            path=path,
            visited=visited,
            vehicle_position=vehicle_position
        )
        pygame.display.flip()

        clock.tick(60)

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()