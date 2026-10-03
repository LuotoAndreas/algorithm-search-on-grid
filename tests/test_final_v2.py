import tempfile
import unittest
from pathlib import Path

from algorithms_v2 import GridState, astar_v2, canonical_bfs, dijkstra_v2, validate_path
from dstar_lite_v2 import DStarLiteV2
from maps import get_city_maps
from run_experiments_v2 import (
    ALGORITHMS,
    balanced_orders,
    build_five_event_trace,
    generate_preflight_scenarios,
    scenario_distance_for_treatment,
    stable_seed,
    validate_base_scenario,
    _ensure_v2_outputs_safe,
    map_sha256,
)
from summarize_results_v2 import (
    PRIMARY_METRICS,
    build_descriptive_summary,
    build_paired_summary,
    validate_result_rows,
)


class StaticAlgorithmTests(unittest.TestCase):
    def test_dijkstra_astar_and_oracle_agree_on_all_maps(self):
        for city_map in get_city_maps():
            roads = sorted(city_map["roads"])
            pairs = [
                (city_map["start"], city_map["goal"]),
                (roads[len(roads) // 5], roads[-len(roads) // 5]),
                (roads[len(roads) // 3], roads[-len(roads) // 3]),
            ]
            for start, goal in pairs:
                if start == goal:
                    continue
                grid = GridState(60, 60, city_map["roads"])
                oracle = canonical_bfs(grid, start, goal)
                dijkstra = dijkstra_v2(grid, start, goal)
                astar = astar_v2(grid, start, goal)
                self.assertEqual(bool(dijkstra.path), bool(oracle))
                self.assertEqual(bool(astar.path), bool(oracle))
                if oracle:
                    expected = len(oracle) - 1
                    self.assertEqual(dijkstra.distance, expected)
                    self.assertEqual(astar.distance, expected)
                    self.assertTrue(validate_path(grid, dijkstra.path, start, goal)[0])
                    self.assertTrue(validate_path(grid, astar.path, start, goal)[0])

    def test_manhattan_heuristic_is_consistent_on_all_map_edges(self):
        from algorithms_v2 import manhattan

        for city_map in get_city_maps():
            grid = GridState(60, 60, city_map["roads"])
            goal = city_map["goal"]
            for node, neighbors in grid.adjacency.items():
                for neighbor in neighbors:
                    self.assertLessEqual(manhattan(node, goal), 1 + manhattan(neighbor, goal))


class DStarLiteTests(unittest.TestCase):
    def test_initial_and_each_notified_update_match_dijkstra(self):
        city_map = get_city_maps()[0]
        seed = stable_seed(123, city_map["name"], city_map["start"], city_map["goal"])
        _, events = build_five_event_trace(
            city_map, city_map["start"], city_map["goal"], seed, 30
        )
        grid = GridState(60, 60, city_map["roads"])
        planner = DStarLiteV2(grid, city_map["start"], city_map["goal"])
        initial = planner.initial_search()
        fresh = dijkstra_v2(grid, city_map["start"], city_map["goal"])
        self.assertEqual(initial.distance, fresh.distance)
        current = city_map["start"]
        for event in events:
            for position in event.movement_segment[1:]:
                planner.move_start(position)
            current = event.vehicle_position
            grid.block(event.blocked_cell)
            updated = planner.apply_changed_cell(event.blocked_cell)
            fresh = dijkstra_v2(grid, current, city_map["goal"])
            self.assertEqual(updated.distance, fresh.distance)
            self.assertTrue(validate_path(grid, updated.path, current, city_map["goal"])[0])

    def test_off_route_then_on_route_regression(self):
        roads = {(row, col) for row in range(8) for col in range(8)}
        initial_obstacles = {
            (0, 7), (1, 0), (1, 3), (1, 4), (1, 5), (2, 0), (2, 7),
            (3, 0), (3, 3), (3, 4), (3, 5), (4, 2), (5, 5), (6, 5),
            (7, 1), (7, 4), (7, 6),
        }
        roads -= initial_obstacles
        grid = GridState(8, 8, roads)
        planner = DStarLiteV2(grid, (0, 0), (7, 7))
        self.assertTrue(planner.initial_search().success)

        off_route = (0, 6)
        grid.block(off_route)
        planner.notify_changed_cell(off_route)

        on_route = (2, 2)
        grid.block(on_route)
        planner.notify_changed_cell(on_route)
        planner.compute_shortest_path()
        updated = planner.result()
        fresh = dijkstra_v2(grid, (0, 0), (7, 7))
        self.assertTrue(updated.success)
        self.assertEqual(updated.distance, fresh.distance)
        self.assertTrue(validate_path(grid, updated.path, (0, 0), (7, 7))[0])


class ScenarioDesignTests(unittest.TestCase):
    def test_cul_de_sac_v2_connector_is_deterministic(self):
        city_map = next(city_map for city_map in get_city_maps() if city_map["name"] == "cul_de_sac_suburb")
        self.assertEqual(len(city_map["roads"]), 476)
        self.assertEqual(
            map_sha256(city_map),
            "97d5923d190b32d84412b8867e29ab5b2d9db3e0d13aa00a99d299de0af13871",
        )
        self.assertTrue(all((row, 42) in city_map["roads"] for row in range(8, 57)))

    def test_trace_has_five_route_invalidating_preserving_prefix_events(self):
        city_map = get_city_maps()[1]
        scenarios, reports = generate_preflight_scenarios(
            master_seed=9876,
            minimum_distance=30,
            target_per_map=1,
            candidate_limit=250,
            maps=[city_map],
        )
        self.assertEqual(len(scenarios), 1, reports)
        scenario = scenarios[0]
        self.assertEqual(len(scenario.events), 5)
        self.assertEqual([event.event_index for event in scenario.events], [1, 2, 3, 4, 5])
        self.assertEqual(sorted(event.trigger_cumulative_step for event in scenario.events), [
            event.trigger_cumulative_step for event in scenario.events
        ])
        for event in scenario.events:
            self.assertIn(event.blocked_cell, event.canonical_path_before)
            self.assertNotIn(event.blocked_cell, event.canonical_path_after)
            self.assertNotEqual(event.blocked_cell, event.vehicle_position)
            self.assertNotEqual(event.blocked_cell, scenario.goal)
            self.assertGreater(event.distance_after_closure, 0)
        self.assertLessEqual(
            scenario_distance_for_treatment(scenario, 1),
            scenario_distance_for_treatment(scenario, 5),
        )
        report = validate_base_scenario(scenario)
        self.assertEqual(report.graph_states_validated, 6)
        self.assertEqual(report.paths_validated, 18)

    def test_measured_execution_order_is_balanced(self):
        orders = balanced_orders(1234, warmups=5, repetitions=30)[5:]
        self.assertEqual(len(orders), 30)
        for position in range(3):
            counts = {algorithm: sum(order[position] == algorithm for order in orders) for algorithm in ALGORITHMS}
            self.assertEqual(set(counts.values()), {10})

    def test_work_metrics_distinguish_events_and_unique_cells(self):
        grid = GridState(4, 4, {(row, col) for row in range(4) for col in range(4)})
        result = dijkstra_v2(grid, (0, 0), (3, 3))
        self.assertGreaterEqual(result.work.expansion_events, result.work.unique_expanded_cells)
        self.assertGreater(result.work.neighbor_evaluation_events, 0)

    def test_legacy_output_names_are_protected(self):
        with tempfile.TemporaryDirectory() as directory:
            legacy = Path(directory) / "experiment_results_final.csv"
            legacy.write_text("legacy evidence", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                _ensure_v2_outputs_safe(Path(directory))
            self.assertEqual(legacy.read_text(encoding="utf-8"), "legacy evidence")


class CsvAndSummaryTests(unittest.TestCase):
    @staticmethod
    def make_rows():
        rows = []
        for scenario_index in range(300):
            map_name = f"map_{scenario_index // 30}"
            for closure_count in (1, 3, 5):
                for algorithm_index, algorithm in enumerate(ALGORITHMS):
                    row = {
                        "experiment_version": "final-v2",
                        "scenario_id": f"scenario_{scenario_index}",
                        "map_name": map_name,
                        "closure_count": str(closure_count),
                        "algorithm": algorithm,
                        "travelled_distance_steps": str(40 + closure_count),
                        "excess_distance_steps": str(closure_count),
                    }
                    for metric in PRIMARY_METRICS:
                        row[metric] = str(100 + scenario_index + closure_count + algorithm_index)
                    rows.append(row)
        return rows

    def test_final_csv_balance_and_shared_distance_invariants(self):
        rows = self.make_rows()
        validate_result_rows(rows, require_final_counts=True)
        with self.assertRaises(ValueError):
            validate_result_rows(rows[:-1], require_final_counts=True)
        corrupted = [dict(row) for row in rows]
        corrupted[0]["excess_distance_steps"] = "999"
        with self.assertRaises(ValueError):
            validate_result_rows(corrupted, require_final_counts=True)

    def test_summary_reproduction_is_deterministic(self):
        rows = self.make_rows()
        first_descriptive = build_descriptive_summary(rows)
        second_descriptive = build_descriptive_summary(rows)
        first_paired = build_paired_summary(rows)
        second_paired = build_paired_summary(rows)
        self.assertEqual(first_descriptive, second_descriptive)
        self.assertEqual(first_paired, second_paired)
        self.assertTrue(first_descriptive)
        self.assertTrue(first_paired)


if __name__ == "__main__":
    unittest.main()
