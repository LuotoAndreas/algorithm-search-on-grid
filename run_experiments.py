import argparse
import copy
import csv
import random
import time
from pathlib import Path

from grid import Grid
from maps import get_city_map, get_city_map_names, get_city_maps
from algorithms import dijkstra, astar
from dstar_lite import DStarLite


ALGORITHMS = ("Dijkstra", "A*", "D* Lite")


def make_grid(rows, cols, start, goal, obstacles, map_info=None):
    """
    Luo Grid-olion kokeellista ajoa varten.

    Kokeissa ruudukko perustuu valmiiseen kaupunkikarttaan, jossa esteet ovat
    rakennuksia, kortteleita tai aiemmin lisättyjä tiesulkuja. Algoritmien
    kannalta oleellista on, mitkä ruudut ovat kulkukelpoisia.
    """
    grid = Grid()
    grid.rows = rows
    grid.cols = cols
    grid.start = start
    grid.goal = goal
    grid.obstacles = set(obstacles)

    if map_info is not None:
        grid.map_name = map_info.get("name")
        grid.map_display_name = map_info.get("display_name")
        grid.map_category = map_info.get("category")
        grid.road_cells = set(map_info.get("roads", set()))
        grid.base_obstacles = set(map_info.get("obstacles", set()))

    return grid


def path_length(path):
    return max(0, len(path) - 1)


def run_initial_search(algorithm_name, grid, start, goal):
    if algorithm_name == "Dijkstra":
        return dijkstra(grid, start, goal), None

    if algorithm_name == "A*":
        return astar(grid, start, goal), None

    if algorithm_name == "D* Lite":
        start_time = time.perf_counter()
        planner = DStarLite(grid, start, goal)
        planner.compute_shortest_path(reset_visited=True)
        end_time = time.perf_counter()

        path = planner.get_path()
        result = {
            "algorithm": "D* Lite",
            "path": path,
            "visited_order": list(planner.visited_order),
            "calculation_time": end_time - start_time,
            "visited_count": len(planner.visited_order),
            "path_length": path_length(path),
            "success": len(path) > 0,
        }
        return result, planner

    raise ValueError(f"Tuntematon algoritmi: {algorithm_name}")


def route_still_exists_after_obstacles(rows, cols, start, goal, initial_obstacles, extra_obstacles, map_info):
    """
    Tarkistaa Dijkstralla, että lisättyjen tiesulkujen jälkeen maaliin on yhä reitti.

    Tätä käytetään vain skenaarion muodostamiseen. Varsinainen vertailu tehdään
    myöhemmin jokaisella algoritmilla erikseen.
    """
    test_obstacles = set(initial_obstacles) | set(extra_obstacles)
    test_grid = make_grid(rows, cols, start, goal, test_obstacles, map_info=map_info)
    result = dijkstra(test_grid, start, goal)
    return result["success"]


def select_dynamic_obstacles_for_path(
    path,
    count,
    rows,
    cols,
    start,
    goal,
    initial_obstacles,
    map_info,
    middle_start_ratio=0.25,
    middle_end_ratio=0.75,
):
    """
    Valitsee skenaariolle yhteiset ajonaikaiset tiesulut viitereitiltä.

    Tiesulut valitaan yhden viitereitin keskiosasta ja pidetään samoina kaikille
    algoritmeille. Näin Dijkstra, A* ja D* Lite kohtaavat saman kartan, saman
    lähtöpisteen, saman maalipisteen ja samat ympäristömuutokset.

    Asetelma on silti dynaaminen, koska tiesulkuja ei lisätä alkuperäiseen
    karttaan ennen alkureititystä. Ne lisätään vasta simuloidun ajon aikana.
    """
    if count <= 0:
        return []

    if len(path) < 3:
        return None

    first_allowed_index = max(1, int(len(path) * middle_start_ratio))
    last_allowed_index = min(len(path) - 2, int(len(path) * middle_end_ratio))

    if first_allowed_index > last_allowed_index:
        return None

    road_cells = set(map_info.get("roads", set()))

    candidates = [
        cell
        for index, cell in enumerate(path)
        if first_allowed_index <= index <= last_allowed_index
        and cell != start
        and cell != goal
        and cell not in initial_obstacles
        and (not road_cells or cell in road_cells)
    ]

    if len(candidates) < count:
        return None

    # Valitaan tiesulut tasaisesti reitin keskiosasta. Kokeillaan pieniä siirtymiä,
    # jotta löydetään ryhmä, joka ei tee koko reittiä mahdottomaksi.
    max_group_attempts = min(60, len(candidates))

    for shift in range(max_group_attempts):
        selected = []

        for i in range(1, count + 1):
            base_index = round(i * (len(candidates) / (count + 1)))
            index = (base_index + shift) % len(candidates)
            cell = candidates[index]

            if cell not in selected:
                selected.append(cell)

        if len(selected) < count:
            for cell in candidates:
                if cell not in selected:
                    selected.append(cell)
                if len(selected) == count:
                    break

        selected = selected[:count]

        if route_still_exists_after_obstacles(
            rows=rows,
            cols=cols,
            start=start,
            goal=goal,
            initial_obstacles=initial_obstacles,
            extra_obstacles=selected,
            map_info=map_info,
        ):
            return selected

    return None


def make_event_schedule(reference_path, dynamic_obstacles):
    """
    Palauttaa listan (trigger_step, obstacle)-pareja viitereitin perusteella.

    Kaikki algoritmit saavat saman aikataulun. Jos tiesulku ei osu jonkin
    algoritmin jäljellä olevalle reitille, se lisätään silti karttaan, mutta se ei
    aiheuta kyseiselle algoritmille uudelleenreititystä.
    """
    schedule = []

    for obstacle in dynamic_obstacles:
        try:
            obstacle_index = reference_path.index(obstacle)
        except ValueError:
            continue

        trigger_step = max(0, obstacle_index - 2)
        schedule.append((trigger_step, obstacle))

    schedule.sort(key=lambda item: item[0])
    return schedule


def simulate_algorithm(
    algorithm_name,
    map_info,
    start,
    goal,
    initial_obstacles,
    selected_dynamic_obstacles,
    event_schedule,
):
    """
    Ajaa yhden algoritmin yhdessä kaupunkikarttaskenaariossa ilman Pygame-visualisointia.

    Alkuympäristö ei ole satunnainen estekenttä, vaan valmis tieverkkokartta.
    Ajonaikaiset muutokset ovat skenaariokohtaisia tiesulkuja, jotka ovat samat
    kaikille algoritmeille ja ilmestyvät vasta ajon aikana.
    """
    rows = map_info["rows"]
    cols = map_info["cols"]
    grid = make_grid(rows, cols, start, goal, initial_obstacles, map_info=map_info)
    initial_result, planner = run_initial_search(algorithm_name, grid, start, goal)

    selected_dynamic_obstacles = list(selected_dynamic_obstacles)
    dynamic_obstacle_positions = []
    effective_obstacle_positions = []
    reroute_count = 0
    total_replanning_time = 0.0
    total_replanning_visited_count = 0

    if not initial_result["success"]:
        return build_result_row(
            algorithm_name,
            map_info,
            start,
            goal,
            initial_obstacles,
            initial_result,
            selected_dynamic_obstacles,
            dynamic_obstacle_positions,
            effective_obstacle_positions,
            reroute_count,
            total_replanning_time,
            total_replanning_visited_count,
            travelled_distance=0,
            delivery_delay=None,
            success=False,
        )

    current_path = list(initial_result["path"])
    current_index = 0
    travelled_path = []
    event_schedule = list(event_schedule)
    next_event_index = 0
    success = True

    while current_index < len(current_path):
        vehicle_position = current_path[current_index]

        if not travelled_path or travelled_path[-1] != vehicle_position:
            travelled_path.append(vehicle_position)

        travelled_steps = path_length(travelled_path)

        if algorithm_name == "D* Lite" and planner is not None:
            planner.move_start(vehicle_position)

        rerouted = False

        while next_event_index < len(event_schedule):
            trigger_step, obstacle_position = event_schedule[next_event_index]

            if travelled_steps < trigger_step:
                break

            next_event_index += 1

            if obstacle_position == vehicle_position or obstacle_position == goal:
                continue

            grid.add_obstacle(*obstacle_position)
            dynamic_obstacle_positions.append(obstacle_position)

            remaining_path = current_path[current_index + 1:]

            if obstacle_position not in remaining_path:
                continue

            effective_obstacle_positions.append(obstacle_position)

            if algorithm_name == "Dijkstra":
                reroute_result = dijkstra(grid, vehicle_position, goal)
            elif algorithm_name == "A*":
                reroute_result = astar(grid, vehicle_position, goal)
            else:
                replanning_start_time = time.perf_counter()
                planner.update_obstacle(obstacle_position)
                planner.compute_shortest_path(reset_visited=True)
                replanning_end_time = time.perf_counter()

                new_path = planner.get_path()
                new_visited = list(planner.visited_order)
                reroute_result = {
                    "algorithm": "D* Lite",
                    "path": new_path,
                    "visited_order": new_visited,
                    "calculation_time": replanning_end_time - replanning_start_time,
                    "visited_count": len(new_visited),
                    "path_length": path_length(new_path),
                    "success": len(new_path) > 0,
                }

            reroute_count += 1
            total_replanning_time += reroute_result["calculation_time"]
            total_replanning_visited_count += reroute_result["visited_count"]

            if not reroute_result["success"]:
                success = False
                current_path = []
                break

            current_path = list(reroute_result["path"])
            current_index = 0
            rerouted = True
            break

        if not success:
            break

        if rerouted:
            continue

        current_index += 1

    travelled_distance = path_length(travelled_path)
    arrived = success and bool(travelled_path) and travelled_path[-1] == goal
    delivery_delay = travelled_distance - initial_result["path_length"] if arrived else None

    return build_result_row(
        algorithm_name,
        map_info,
        start,
        goal,
        initial_obstacles,
        initial_result,
        selected_dynamic_obstacles,
        dynamic_obstacle_positions,
        effective_obstacle_positions,
        reroute_count,
        total_replanning_time,
        total_replanning_visited_count,
        travelled_distance=travelled_distance,
        delivery_delay=delivery_delay,
        success=arrived,
    )


def build_result_row(
    algorithm_name,
    map_info,
    start,
    goal,
    initial_obstacles,
    initial_result,
    selected_dynamic_obstacles,
    dynamic_obstacle_positions,
    effective_obstacle_positions,
    reroute_count,
    total_replanning_time,
    total_replanning_visited_count,
    travelled_distance,
    delivery_delay,
    success,
):
    return {
        "algorithm": algorithm_name,
        "map_name": map_info["name"],
        "map_display_name": map_info["display_name"],
        "map_category": map_info["category"],
        "grid_rows": map_info["rows"],
        "grid_cols": map_info["cols"],
        "road_cell_count": len(map_info["roads"]),
        "building_obstacle_count": len(map_info["obstacles"]),
        "start": start,
        "goal": goal,
        "initial_obstacle_count": len(initial_obstacles),
        "initial_path_length": initial_result["path_length"],
        "initial_calculation_time": initial_result["calculation_time"],
        "initial_visited_count": initial_result["visited_count"],
        "selected_dynamic_obstacles": selected_dynamic_obstacles,
        "dynamic_obstacle_added": len(dynamic_obstacle_positions) > 0,
        "dynamic_obstacle_position": dynamic_obstacle_positions[-1] if dynamic_obstacle_positions else None,
        "dynamic_obstacle_count": len(dynamic_obstacle_positions),
        "dynamic_obstacle_positions": dynamic_obstacle_positions,
        "effective_obstacle_count": len(effective_obstacle_positions),
        "effective_obstacle_positions": effective_obstacle_positions,
        "reroute_count": reroute_count,
        "total_replanning_time": total_replanning_time,
        "total_replanning_visited_count": total_replanning_visited_count,
        "travelled_distance": travelled_distance,
        "delivery_delay": delivery_delay,
        "total_calculation_time": initial_result["calculation_time"] + total_replanning_time,
        "success": success,
    }


def choose_start_goal(road_cells, rng):
    """Valitsee lähtö- ja maalipisteen tieverkolta."""
    start = rng.choice(road_cells)
    goal = rng.choice(road_cells)

    while goal == start:
        goal = rng.choice(road_cells)

    return start, goal


def create_valid_city_scenario(map_info, seed, max_attempts, min_path_length):
    """
    Luo yhden kaupunkikarttaan perustuvan skenaarion.

    Lähtö- ja maalipiste valitaan kartan tieverkolta. Skenaario hyväksytään,
    jos kaikki algoritmit löytävät alkuperäisen reitin ja reitti on riittävän
    pitkä dynaamisten tiesulkujen mielekästä testaamista varten.
    """
    rng = random.Random(seed)
    road_cells = sorted(map_info["roads"])
    initial_obstacles = set(map_info["obstacles"])

    for attempt in range(1, max_attempts + 1):
        start, goal = choose_start_goal(road_cells, rng)
        base_grid = make_grid(
            map_info["rows"],
            map_info["cols"],
            start,
            goal,
            initial_obstacles,
            map_info=map_info,
        )

        reference_result = dijkstra(base_grid, start, goal)

        if not reference_result["success"]:
            continue

        if reference_result["path_length"] < min_path_length:
            continue

        all_success = True
        for algorithm_name in ALGORITHMS:
            grid_copy = copy.deepcopy(base_grid)
            result, _ = run_initial_search(algorithm_name, grid_copy, start, goal)
            if not result["success"]:
                all_success = False
                break

        if not all_success:
            continue

        return {
            "start": start,
            "goal": goal,
            "obstacles": initial_obstacles,
            "attempts_used": attempt,
        }

    return None


def build_shared_dynamic_obstacle_scenario(map_info, start, goal, initial_obstacles, dynamic_count):
    """
    Laskee viitereitin ja valitsee kaikille algoritmeille yhteiset tiesulut.

    Viitereittinä käytetään A*:a. A* sopii tähän, koska se tuottaa lyhimmän
    reitin kuten Dijkstra, mutta vastaa paremmin heuristista reitinhakua.
    Tiesulut eivät kuitenkaan ole A*:n etu, koska samat sulut annetaan myös
    Dijkstralle ja D* Litelle.
    """
    reference_grid = make_grid(
        map_info["rows"],
        map_info["cols"],
        start,
        goal,
        initial_obstacles,
        map_info=map_info,
    )
    reference_result = astar(reference_grid, start, goal)

    if not reference_result["success"]:
        return None

    selected_dynamic_obstacles = select_dynamic_obstacles_for_path(
        path=reference_result["path"],
        count=dynamic_count,
        rows=map_info["rows"],
        cols=map_info["cols"],
        start=start,
        goal=goal,
        initial_obstacles=initial_obstacles,
        map_info=map_info,
    )

    if selected_dynamic_obstacles is None or len(selected_dynamic_obstacles) < dynamic_count:
        return None

    event_schedule = make_event_schedule(reference_result["path"], selected_dynamic_obstacles)

    if len(event_schedule) < dynamic_count:
        return None

    return {
        "reference_algorithm": "A*",
        "reference_path": reference_result["path"],
        "selected_dynamic_obstacles": selected_dynamic_obstacles,
        "event_schedule": event_schedule,
    }


def write_rows(output_path, rows):
    if not rows:
        return

    fieldnames = list(rows[0].keys())

    with open(output_path, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def parse_int_list(value):
    return [int(item.strip()) for item in value.split(",") if item.strip()]


def resolve_maps(value):
    """
    Palauttaa kokeissa käytettävät kartat.

    --maps all käyttää kaikkia valmiita karttoja.
    Muuten arvo annetaan pilkulla erotettuna listana karttojen sisäisiä nimiä.
    """
    if value.strip().lower() == "all":
        return get_city_maps()

    selected = []
    for name in value.split(","):
        cleaned = name.strip()
        if cleaned:
            selected.append(get_city_map(cleaned))

    if not selected:
        raise ValueError("Yhtään karttaa ei valittu.")

    return selected


def main():
    parser = argparse.ArgumentParser(
        description="Aja reitinhakualgoritmien vertailukokeita valmiilla kaupunkimaisilla ruudukkokartoilla."
    )
    parser.add_argument("--output", default="experiment_results.csv")
    parser.add_argument(
        "--maps",
        default="all",
        help=(
            "Käytettävät kartat. Arvo 'all' käyttää kaikkia karttoja. "
            f"Yksittäisiä karttoja voi antaa pilkulla erotettuna. Saatavilla: {', '.join(get_city_map_names())}"
        ),
    )
    parser.add_argument("--scenarios", type=int, default=10, help="Skenaarioiden määrä per kartta ja tiesulkumäärä")
    parser.add_argument("--dynamic-obstacles", default="1,3,5", help="Ajonaikaisten tiesulkujen määrät, esim. 1,3,5")
    parser.add_argument("--seed", type=int, default=12345)
    parser.add_argument("--max-attempts", type=int, default=500)
    parser.add_argument("--min-path-length", type=int, default=25)
    args = parser.parse_args()

    selected_maps = resolve_maps(args.maps)
    dynamic_obstacle_counts = parse_int_list(args.dynamic_obstacles)
    output_path = Path(args.output)
    all_rows = []
    scenario_id = 1
    master_rng = random.Random(args.seed)

    for map_info in selected_maps:
        for dynamic_count in dynamic_obstacle_counts:
            created = 0
            attempts = 0

            while created < args.scenarios:
                attempts += 1
                if attempts > args.max_attempts:
                    print(
                        f"Varoitus: skenaarioita löytyi vain {created}/{args.scenarios} "
                        f"kartalla {map_info['display_name']}, tiesulkuja {dynamic_count}."
                    )
                    break

                scenario_seed = master_rng.randint(1, 10_000_000)
                scenario = create_valid_city_scenario(
                    map_info=map_info,
                    seed=scenario_seed,
                    max_attempts=50,
                    min_path_length=args.min_path_length,
                )

                if scenario is None:
                    continue

                shared_dynamic_scenario = build_shared_dynamic_obstacle_scenario(
                    map_info=map_info,
                    start=scenario["start"],
                    goal=scenario["goal"],
                    initial_obstacles=scenario["obstacles"],
                    dynamic_count=dynamic_count,
                )

                if shared_dynamic_scenario is None:
                    continue

                scenario_rows = []

                for algorithm_name in ALGORITHMS:
                    result_row = simulate_algorithm(
                        algorithm_name=algorithm_name,
                        map_info=map_info,
                        start=scenario["start"],
                        goal=scenario["goal"],
                        initial_obstacles=scenario["obstacles"],
                        selected_dynamic_obstacles=shared_dynamic_scenario["selected_dynamic_obstacles"],
                        event_schedule=shared_dynamic_scenario["event_schedule"],
                    )

                    scenario_rows.append(result_row)

                for result_row in scenario_rows:
                    result_row = {
                        "scenario_id": scenario_id,
                        "scenario_seed": scenario_seed,
                        "dynamic_obstacle_count_requested": dynamic_count,
                        "dynamic_obstacle_reference_algorithm": shared_dynamic_scenario["reference_algorithm"],
                        "dynamic_obstacle_event_schedule": shared_dynamic_scenario["event_schedule"],
                        **result_row,
                    }
                    all_rows.append(result_row)

                print(
                    f"Skenaario {scenario_id}: {map_info['display_name']}, "
                    f"lähtö {scenario['start']}, maali {scenario['goal']}, "
                    f"yhteisiä ajonaikaisia tiesulkuja {dynamic_count}."
                )

                scenario_id += 1
                created += 1

    write_rows(output_path, all_rows)
    print(f"\nValmis. Tallennettiin {len(all_rows)} riviä tiedostoon {output_path}.")


if __name__ == "__main__":
    main()
