import argparse
import copy
import csv
import random
import time
from pathlib import Path

from grid import Grid
from algorithms import dijkstra, astar
from dstar_lite import DStarLite


ALGORITHMS = ("Dijkstra", "A*", "D* Lite")


def make_grid(rows, cols, start, goal, obstacles):
    grid = Grid()
    grid.rows = rows
    grid.cols = cols
    grid.start = start
    grid.goal = goal
    grid.obstacles = set(obstacles)
    return grid


def generate_obstacles(rows, cols, start, goal, probability, rng):
    obstacles = set()

    for row in range(rows):
        for col in range(cols):
            position = (row, col)

            if position == start or position == goal:
                continue

            if rng.random() < probability:
                obstacles.add(position)

    return obstacles


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


def route_still_exists_after_obstacles(rows, cols, start, goal, initial_obstacles, extra_obstacles):
    """
    Tarkistaa Dijkstralla, että lisäesteiden jälkeen maaliin on yhä jokin reitti.

    Tätä käytetään vain skenaarion muodostamiseen. Varsinainen vertailu tehdään
    myöhemmin jokaisella algoritmilla erikseen.
    """
    test_obstacles = set(initial_obstacles) | set(extra_obstacles)
    test_grid = make_grid(rows, cols, start, goal, test_obstacles)
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
    middle_start_ratio=0.25,
    middle_end_ratio=0.75,
):
    """
    Valitsee ajonaikaiset esteet yhden algoritmin omalta alkuperäiseltä reitiltä.

    Tämä ratkaisee tilanteen, jossa Dijkstra, A* ja D* Lite löytävät yhtä pitkän
    mutta eri ruutuja pitkin kulkevan reitin. Esteet kohdistetaan jokaisen
    algoritmin omaan reittiin, jolloin häiriö on jokaiselle algoritmille
    vaikutuksellinen samalla periaatteella.
    """
    if count <= 0:
        return []

    if len(path) < 3:
        return None

    first_allowed_index = max(1, int(len(path) * middle_start_ratio))
    last_allowed_index = min(len(path) - 2, int(len(path) * middle_end_ratio))

    if first_allowed_index > last_allowed_index:
        return None

    candidates = [
        cell
        for index, cell in enumerate(path)
        if first_allowed_index <= index <= last_allowed_index
        and cell != start
        and cell != goal
        and cell not in initial_obstacles
    ]

    if len(candidates) < count:
        return None

    # Valitaan esteet tasaisesti reitin keskiosasta. Kokeillaan pieniä siirtymiä,
    # jotta löydetään ryhmä, joka ei tee koko reittiä mahdottomaksi.
    max_group_attempts = min(40, len(candidates))

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
        ):
            return selected

    return None


def make_event_schedule(reference_path, dynamic_obstacles):
    """
    Palauttaa listan (trigger_step, obstacle)-pareja.

    Este lisätään hieman ennen kuin ajoneuvo saavuttaisi kyseisen ruudun
    algoritmin omalla alkuperäisellä reitillä.
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
    rows,
    cols,
    start,
    goal,
    initial_obstacles,
    dynamic_obstacle_count,
):
    """
    Ajaa yhden algoritmin yhdessä skenaariossa ilman Pygame-visualisointia.

    Ajonaikaiset esteet valitaan tämän algoritmin omalta alkuperäiseltä reitiltä.
    Näin jokainen algoritmi kohtaa vaikutuksellisen häiriön, vaikka sen reitti
    olisi eri kuin muilla algoritmeilla.
    """
    grid = make_grid(rows, cols, start, goal, initial_obstacles)
    initial_result, planner = run_initial_search(algorithm_name, grid, start, goal)

    selected_dynamic_obstacles = []
    dynamic_obstacle_positions = []
    effective_obstacle_positions = []
    reroute_count = 0
    total_replanning_time = 0.0
    total_replanning_visited_count = 0

    if not initial_result["success"]:
        return build_result_row(
            algorithm_name,
            rows,
            cols,
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

    selected_dynamic_obstacles = select_dynamic_obstacles_for_path(
        path=initial_result["path"],
        count=dynamic_obstacle_count,
        rows=rows,
        cols=cols,
        start=start,
        goal=goal,
        initial_obstacles=initial_obstacles,
    )

    if selected_dynamic_obstacles is None:
        selected_dynamic_obstacles = []

    current_path = list(initial_result["path"])
    current_index = 0
    travelled_path = []
    event_schedule = make_event_schedule(current_path, selected_dynamic_obstacles)
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
        rows,
        cols,
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
    rows,
    cols,
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
        "grid_rows": rows,
        "grid_cols": cols,
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


def create_valid_scenario(rows, cols, obstacle_probability, seed, max_attempts):
    """
    Luo skenaarion, jossa kaikki algoritmit löytävät alkuperäisen reitin.

    Dynaamiset esteet valitaan myöhemmin jokaisen algoritmin omalta reitiltä,
    joten skenaarion ei tarvitse sisältää kaikille yhteistä reittiosuutta.
    """
    rng = random.Random(seed)
    start = (0, 0)
    goal = (rows - 1, cols - 1)

    for attempt in range(1, max_attempts + 1):
        scenario_seed = rng.randint(1, 10_000_000)
        scenario_rng = random.Random(scenario_seed)
        obstacles = generate_obstacles(rows, cols, start, goal, obstacle_probability, scenario_rng)
        base_grid = make_grid(rows, cols, start, goal, obstacles)

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
            "scenario_seed": scenario_seed,
            "start": start,
            "goal": goal,
            "obstacles": obstacles,
            "attempts_used": attempt,
        }

    return None


def write_rows(output_path, rows):
    if not rows:
        return

    fieldnames = list(rows[0].keys())

    with open(output_path, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def parse_grid_sizes(value):
    sizes = []
    for item in value.split(","):
        item = item.strip().lower()
        if "x" in item:
            rows, cols = item.split("x", 1)
            sizes.append((int(rows), int(cols)))
        else:
            number = int(item)
            sizes.append((number, number))
    return sizes


def parse_int_list(value):
    return [int(item.strip()) for item in value.split(",") if item.strip()]


def main():
    parser = argparse.ArgumentParser(
        description="Aja reitinhakualgoritmien vertailukokeita ilman Pygame-käyttöliittymää."
    )
    parser.add_argument("--output", default="experiment_results.csv")
    parser.add_argument("--grid-sizes", default="60x60", help="Esim. 60x60 tai 60x60,80x80")
    parser.add_argument("--scenarios", type=int, default=10, help="Skenaarioiden määrä per ruudukkokoko ja estemäärä")
    parser.add_argument("--dynamic-obstacles", default="1,3,5", help="Ajonaikaisten esteiden määrät, esim. 1,3,5")
    parser.add_argument("--obstacle-probability", type=float, default=0.20)
    parser.add_argument("--seed", type=int, default=12345)
    parser.add_argument("--max-attempts", type=int, default=500)
    args = parser.parse_args()

    grid_sizes = parse_grid_sizes(args.grid_sizes)
    dynamic_obstacle_counts = parse_int_list(args.dynamic_obstacles)
    output_path = Path(args.output)
    all_rows = []
    scenario_id = 1
    master_rng = random.Random(args.seed)

    for rows, cols in grid_sizes:
        for dynamic_count in dynamic_obstacle_counts:
            created = 0
            attempts = 0

            while created < args.scenarios:
                attempts += 1
                if attempts > args.max_attempts:
                    print(
                        f"Varoitus: skenaarioita löytyi vain {created}/{args.scenarios} "
                        f"asetuksilla {rows}x{cols}, esteitä {dynamic_count}."
                    )
                    break

                seed = master_rng.randint(1, 10_000_000)
                scenario = create_valid_scenario(
                    rows=rows,
                    cols=cols,
                    obstacle_probability=args.obstacle_probability,
                    seed=seed,
                    max_attempts=30,
                )

                if scenario is None:
                    continue

                scenario_rows = []
                valid_for_all_algorithms = True

                for algorithm_name in ALGORITHMS:
                    result_row = simulate_algorithm(
                        algorithm_name=algorithm_name,
                        rows=rows,
                        cols=cols,
                        start=scenario["start"],
                        goal=scenario["goal"],
                        initial_obstacles=scenario["obstacles"],
                        dynamic_obstacle_count=dynamic_count,
                    )

                    # Jos pyydettiin esteitä, mutta algoritmin omalta reitiltä ei
                    # saatu valittua niitä, hylätään skenaario kokonaan.
                    if dynamic_count > 0 and len(result_row["selected_dynamic_obstacles"]) < dynamic_count:
                        valid_for_all_algorithms = False
                        break

                    scenario_rows.append(result_row)

                if not valid_for_all_algorithms:
                    continue

                for result_row in scenario_rows:
                    result_row = {
                        "scenario_id": scenario_id,
                        "scenario_seed": scenario["scenario_seed"],
                        "obstacle_probability": args.obstacle_probability,
                        "dynamic_obstacle_count_requested": dynamic_count,
                        **result_row,
                    }
                    all_rows.append(result_row)

                print(
                    f"Skenaario {scenario_id}: {rows}x{cols}, "
                    f"ajonaikaisia esteitä {dynamic_count}, "
                    f"esteet valitaan kunkin algoritmin omalta reitiltä."
                )

                scenario_id += 1
                created += 1

    write_rows(output_path, all_rows)
    print(f"\nValmis. Tallennettiin {len(all_rows)} riviä tiedostoon {output_path}.")


if __name__ == "__main__":
    main()
