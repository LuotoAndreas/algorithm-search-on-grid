"""Final-v2 lockstep experiment and non-timed feasibility preflight.

The primary study population is exactly:
"Initially reachable trips supporting five sequential route-disrupting but
route-preserving cell closures."
"""

from __future__ import annotations

import argparse
from collections import Counter
import csv
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import platform
import random
import statistics
import subprocess
import sys
import time
from typing import Iterable

from algorithms_v2 import (
    GridState,
    Node,
    SearchResult,
    astar_v2,
    canonical_bfs,
    dijkstra_v2,
    validate_path,
)
from dstar_lite_v2 import DStarLiteV2
from maps import get_city_maps


EXPERIMENT_VERSION = "final-v2"
STUDY_POPULATION = (
    "Initially reachable trips supporting five sequential route-disrupting "
    "but route-preserving cell closures."
)
ALGORITHMS = ("Dijkstra", "A*", "D* Lite")
TREATMENTS = (1, 3, 5)
TRIGGER_FRACTIONS = (0.15, 0.30, 0.45, 0.60, 0.75)
LEGACY_FILENAMES = {"experiment_results_final.csv", "summary_final.csv"}
DEFAULT_MASTER_SEED = 20261003


@dataclass(frozen=True)
class ClosureEvent:
    event_index: int
    trigger_cumulative_step: int
    movement_segment: tuple[Node, ...]
    vehicle_position: Node
    blocked_cell: Node
    distance_before_closure: int
    distance_after_closure: int
    canonical_path_before: tuple[Node, ...]
    canonical_path_after: tuple[Node, ...]
    candidate_pool_size: int
    candidate_rank_selected: int


@dataclass(frozen=True)
class BaseScenario:
    scenario_id: str
    scenario_seed: int
    base_scenario_index: int
    map_name: str
    map_display_name: str
    map_category: str
    map_sha256: str
    rows: int
    cols: int
    roads: frozenset[Node]
    start: Node
    goal: Node
    initial_shortest_distance_steps: int
    events: tuple[ClosureEvent, ...]
    candidate_attempt_number: int


@dataclass
class ValidationReport:
    scenarios_validated: int = 0
    graph_states_validated: int = 0
    paths_validated: int = 0
    dijkstra_oracle_matches: int = 0
    astar_oracle_matches: int = 0
    dstar_oracle_matches: int = 0
    identical_state_checks: int = 0


class TraceRejected(Exception):
    pass


def stable_seed(*parts: object) -> int:
    data = "|".join(str(part) for part in parts).encode("utf-8")
    return int.from_bytes(hashlib.sha256(data).digest()[:8], "big")


def map_sha256(map_info: dict) -> str:
    digest = hashlib.sha256()
    digest.update(f"{map_info['name']}|{map_info['rows']}|{map_info['cols']}|".encode())
    for row, col in sorted(map_info["roads"]):
        digest.update(f"{row},{col};".encode())
    return digest.hexdigest()


def trigger_steps(initial_distance: int) -> tuple[int, ...]:
    raw = [max(1, math.floor(initial_distance * fraction)) for fraction in TRIGGER_FRACTIONS]
    result: list[int] = []
    for value in raw:
        if result:
            value = max(value, result[-1] + 1)
        result.append(value)
    if result[-1] >= initial_distance:
        raise TraceRejected("trigger_at_or_after_initial_arrival")
    return tuple(result)


def build_five_event_trace(
    map_info: dict,
    start: Node,
    goal: Node,
    scenario_seed: int,
    minimum_distance: int,
) -> tuple[int, tuple[ClosureEvent, ...]]:
    grid = GridState(map_info["rows"], map_info["cols"], map_info["roads"])
    current_path = canonical_bfs(grid, start, goal)
    if not current_path:
        raise TraceRejected("initial_unreachable")
    initial_distance = len(current_path) - 1
    if initial_distance < minimum_distance:
        raise TraceRejected("distance_below_minimum")

    triggers = trigger_steps(initial_distance)
    current = start
    travelled = 0
    events: list[ClosureEvent] = []

    for event_index, trigger in enumerate(triggers, start=1):
        if current_path[0] != current:
            raise AssertionError("Canonical path does not start at the common vehicle position.")
        movement = trigger - travelled
        if movement <= 0 or movement >= len(current_path):
            raise TraceRejected(f"event_{event_index}_trigger_after_arrival")
        segment = tuple(current_path[: movement + 1])
        current = segment[-1]
        remaining = current_path[movement:]
        # Keep the closure at least two steps ahead and never block the goal.
        candidates = list(remaining[2:-1])
        if not candidates:
            raise TraceRejected(f"event_{event_index}_no_future_candidate")
        rng = random.Random(stable_seed(scenario_seed, "closure", event_index))
        rng.shuffle(candidates)

        chosen = None
        chosen_path: list[Node] = []
        chosen_rank = 0
        for rank, candidate in enumerate(candidates, start=1):
            trial = grid.clone()
            trial.block(candidate)
            alternative = canonical_bfs(trial, current, goal)
            if alternative:
                chosen = candidate
                chosen_path = alternative
                chosen_rank = rank
                break
        if chosen is None:
            raise TraceRejected(f"event_{event_index}_no_route_preserving_candidate")

        distance_before = len(remaining) - 1
        grid.block(chosen)
        current_path = chosen_path
        events.append(
            ClosureEvent(
                event_index=event_index,
                trigger_cumulative_step=trigger,
                movement_segment=segment,
                vehicle_position=current,
                blocked_cell=chosen,
                distance_before_closure=distance_before,
                distance_after_closure=len(chosen_path) - 1,
                canonical_path_before=tuple(remaining),
                canonical_path_after=tuple(chosen_path),
                candidate_pool_size=len(candidates),
                candidate_rank_selected=chosen_rank,
            )
        )
        travelled = trigger

    return initial_distance, tuple(events)


def _pair_from_index(roads: list[Node], pair_index: int) -> tuple[Node, Node]:
    count = len(roads)
    first_index, remainder = divmod(pair_index, count - 1)
    second_index = remainder if remainder < first_index else remainder + 1
    return roads[first_index], roads[second_index]


def preflight_map(
    map_info: dict,
    map_index: int,
    master_seed: int,
    minimum_distance: int,
    target_count: int,
    candidate_limit: int,
) -> tuple[list[BaseScenario], dict]:
    roads = sorted(map_info["roads"])
    possible_pair_count = len(roads) * (len(roads) - 1)
    tested_count = min(candidate_limit, possible_pair_count)
    rng = random.Random(stable_seed(master_seed, map_info["name"], "base-pairs"))
    pair_indexes = rng.sample(range(possible_pair_count), tested_count)
    accepted: list[BaseScenario] = []
    rejection_reasons: Counter[str] = Counter()
    eligible_count = 0
    attempts_to_target = None
    fingerprint = map_sha256(map_info)

    for attempt_number, pair_index in enumerate(pair_indexes, start=1):
        start, goal = _pair_from_index(roads, pair_index)
        scenario_seed = stable_seed(master_seed, map_info["name"], start, goal)
        try:
            initial_distance, events = build_five_event_trace(
                map_info, start, goal, scenario_seed, minimum_distance
            )
        except TraceRejected as error:
            rejection_reasons[str(error)] += 1
            continue

        eligible_count += 1
        if len(accepted) < target_count:
            base_index = len(accepted) + 1
            accepted.append(
                BaseScenario(
                    scenario_id=f"{map_info['name']}__{base_index:03d}",
                    scenario_seed=scenario_seed,
                    base_scenario_index=base_index,
                    map_name=map_info["name"],
                    map_display_name=map_info["display_name"],
                    map_category=map_info["category"],
                    map_sha256=fingerprint,
                    rows=map_info["rows"],
                    cols=map_info["cols"],
                    roads=frozenset(map_info["roads"]),
                    start=start,
                    goal=goal,
                    initial_shortest_distance_steps=initial_distance,
                    events=events,
                    candidate_attempt_number=attempt_number,
                )
            )
            if len(accepted) == target_count:
                attempts_to_target = attempt_number

    acceptance_rate = eligible_count / tested_count if tested_count else 0.0
    comfortable = (
        len(accepted) == target_count
        and eligible_count >= target_count * 2
        and attempts_to_target is not None
        and attempts_to_target <= candidate_limit // 2
    )
    report = {
        "map_index": map_index,
        "map_name": map_info["name"],
        "map_display_name": map_info["display_name"],
        "road_cell_count": len(roads),
        "possible_ordered_pair_count": possible_pair_count,
        "candidate_limit": candidate_limit,
        "candidate_attempts_tested": tested_count,
        "eligible_scenario_count": eligible_count,
        "selected_scenario_count": len(accepted),
        "attempts_required_for_30": attempts_to_target,
        "acceptance_rate": acceptance_rate,
        "comfortable": comfortable,
        "rejection_reasons": dict(sorted(rejection_reasons.items())),
    }
    return accepted, report


def generate_preflight_scenarios(
    master_seed: int = DEFAULT_MASTER_SEED,
    minimum_distance: int = 30,
    target_per_map: int = 30,
    candidate_limit: int = 5000,
    maps: Iterable[dict] | None = None,
) -> tuple[list[BaseScenario], list[dict]]:
    selected_maps = list(get_city_maps() if maps is None else maps)
    all_scenarios: list[BaseScenario] = []
    reports: list[dict] = []
    for map_index, map_info in enumerate(selected_maps):
        scenarios, report = preflight_map(
            map_info,
            map_index,
            master_seed,
            minimum_distance,
            target_per_map,
            candidate_limit,
        )
        all_scenarios.extend(scenarios)
        reports.append(report)
    return all_scenarios, reports


def _assert_result_matches(
    result: SearchResult,
    grid: GridState,
    start: Node,
    goal: Node,
    oracle_path: list[Node],
    label: str,
) -> None:
    valid, reason = validate_path(grid, result.path, start, goal)
    if not valid:
        raise AssertionError(f"{label} returned invalid path: {reason}")
    oracle_distance = len(oracle_path) - 1
    if result.distance != oracle_distance:
        raise AssertionError(
            f"{label} distance {result.distance} != oracle {oracle_distance}"
        )


def validate_base_scenario(scenario: BaseScenario) -> ValidationReport:
    report = ValidationReport(scenarios_validated=1)
    if len(scenario.events) != 5:
        raise AssertionError("Every base scenario must contain exactly five closure events.")
    if [event.event_index for event in scenario.events] != [1, 2, 3, 4, 5]:
        raise AssertionError("Closure event indexes are not the required five-event prefix.")
    triggers = [event.trigger_cumulative_step for event in scenario.events]
    if triggers != sorted(set(triggers)):
        raise AssertionError("Closure triggers must be unique and strictly increasing.")
    grids = {
        algorithm: GridState(scenario.rows, scenario.cols, scenario.roads)
        for algorithm in ALGORITHMS
    }
    oracle_grid = GridState(scenario.rows, scenario.cols, scenario.roads)
    oracle_path = canonical_bfs(oracle_grid, scenario.start, scenario.goal)

    dijkstra_result = dijkstra_v2(grids["Dijkstra"], scenario.start, scenario.goal)
    astar_result = astar_v2(grids["A*"], scenario.start, scenario.goal)
    planner = DStarLiteV2(grids["D* Lite"], scenario.start, scenario.goal)
    dstar_result = planner.initial_search()
    for label, result in (
        ("Dijkstra", dijkstra_result),
        ("A*", astar_result),
        ("D* Lite", dstar_result),
    ):
        _assert_result_matches(result, grids[label], scenario.start, scenario.goal, oracle_path, label)
        report.paths_validated += 1
    report.dijkstra_oracle_matches += 1
    report.astar_oracle_matches += 1
    report.dstar_oracle_matches += 1
    report.graph_states_validated += 1
    report.identical_state_checks += 1

    current = scenario.start
    for event in scenario.events:
        if event.movement_segment[0] != current or event.movement_segment[-1] != event.vehicle_position:
            raise AssertionError("Invalid common movement segment in scenario trace.")
        if event.canonical_path_before[0] != event.vehicle_position:
            raise AssertionError("Pre-closure canonical path starts at the wrong query position.")
        if event.blocked_cell not in event.canonical_path_before:
            raise AssertionError("Closure does not invalidate the canonical route.")
        if event.blocked_cell in (event.vehicle_position, scenario.goal):
            raise AssertionError("Closure blocks the vehicle position or goal.")
        for position in event.movement_segment[1:]:
            planner.move_start(position)
        current = event.vehicle_position
        for grid in grids.values():
            grid.block(event.blocked_cell)
        oracle_grid.block(event.blocked_cell)
        blocked_states = {tuple(sorted(grid.blocked)) for grid in grids.values()}
        if len(blocked_states) != 1 or next(iter(blocked_states)) != tuple(sorted(oracle_grid.blocked)):
            raise AssertionError("Algorithms do not have identical blocked-cell states.")

        oracle_path = canonical_bfs(oracle_grid, current, scenario.goal)
        if not oracle_path:
            raise AssertionError("Primary scenario became disconnected.")
        if tuple(oracle_path) != event.canonical_path_after:
            raise AssertionError("Stored post-closure canonical route is not reproducible.")
        if event.blocked_cell in oracle_path:
            raise AssertionError("Post-closure canonical route contains the blocked cell.")
        dijkstra_result = dijkstra_v2(grids["Dijkstra"], current, scenario.goal)
        astar_result = astar_v2(grids["A*"], current, scenario.goal)
        # Every change is communicated before repair, whether or not it appears
        # on D* Lite's previously returned tie-path.
        dstar_result = planner.apply_changed_cell(event.blocked_cell)
        for label, result in (
            ("Dijkstra", dijkstra_result),
            ("A*", astar_result),
            ("D* Lite", dstar_result),
        ):
            _assert_result_matches(result, grids[label], current, scenario.goal, oracle_path, label)
            report.paths_validated += 1
        report.dijkstra_oracle_matches += 1
        report.astar_oracle_matches += 1
        report.dstar_oracle_matches += 1
        report.graph_states_validated += 1
        report.identical_state_checks += 1
    return report


def validate_scenarios(scenarios: Iterable[BaseScenario]) -> ValidationReport:
    total = ValidationReport()
    for scenario in scenarios:
        report = validate_base_scenario(scenario)
        for field_name in asdict(total):
            setattr(total, field_name, getattr(total, field_name) + getattr(report, field_name))
    return total


def scenario_distance_for_treatment(scenario: BaseScenario, closure_count: int) -> int:
    event = scenario.events[closure_count - 1]
    return event.trigger_cumulative_step + event.distance_after_closure


def _git_metadata() -> dict:
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
        dirty = bool(
            subprocess.check_output(
                ["git", "status", "--porcelain"], text=True, stderr=subprocess.DEVNULL
            ).strip()
        )
        return {"git_commit": commit, "git_dirty": dirty}
    except (OSError, subprocess.CalledProcessError):
        return {"git_commit": None, "git_dirty": None}


def write_preflight_report(
    output: Path,
    reports: list[dict],
    validation: ValidationReport,
    master_seed: int,
    minimum_distance: int,
    target_per_map: int,
) -> None:
    payload = {
        "experiment_version": EXPERIMENT_VERSION,
        "report_type": "non_timed_feasibility_preflight",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "study_population": STUDY_POPULATION,
        "master_seed": master_seed,
        "minimum_initial_distance": minimum_distance,
        "target_base_scenarios_per_map": target_per_map,
        "full_timed_experiment_executed": False,
        "maps": reports,
        "validation": asdict(validation),
        **_git_metadata(),
    }
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def percentile(values: list[int], probability: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("No timing values.")
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(ordered[lower])
    fraction = position - lower
    return ordered[lower] + fraction * (ordered[upper] - ordered[lower])


def timing_statistics(values: list[int], prefix: str) -> dict[str, float | int]:
    median = statistics.median(values)
    deviations = [abs(value - median) for value in values]
    q1 = percentile(values, 0.25)
    q3 = percentile(values, 0.75)
    return {
        f"{prefix}_ns_median": median,
        f"{prefix}_ns_q1": q1,
        f"{prefix}_ns_q3": q3,
        f"{prefix}_ns_iqr": q3 - q1,
        f"{prefix}_ns_mad": statistics.median(deviations),
        f"{prefix}_ns_p05": percentile(values, 0.05),
        f"{prefix}_ns_p95": percentile(values, 0.95),
        f"{prefix}_ns_min": min(values),
        f"{prefix}_ns_max": max(values),
    }


def _search(algorithm: str, grid: GridState, start: Node, goal: Node, collect_work: bool) -> SearchResult:
    if algorithm == "Dijkstra":
        return dijkstra_v2(grid, start, goal, collect_work)
    if algorithm == "A*":
        return astar_v2(grid, start, goal, collect_work)
    raise ValueError(algorithm)


def replay_for_work(scenario: BaseScenario, closure_count: int, algorithm: str) -> dict:
    grid = GridState(scenario.rows, scenario.cols, scenario.roads)
    current = scenario.start
    if algorithm == "D* Lite":
        planner = DStarLiteV2(grid, current, scenario.goal, collect_work=True)
        initial = planner.initial_search()
    else:
        planner = None
        initial = _search(algorithm, grid, current, scenario.goal, True)
    events: list[dict] = []
    for event in scenario.events[:closure_count]:
        if planner is not None:
            for position in event.movement_segment[1:]:
                planner.move_start(position)
        current = event.vehicle_position
        grid.block(event.blocked_cell)
        if planner is not None:
            result = planner.apply_changed_cell(event.blocked_cell)
        else:
            result = _search(algorithm, grid, current, scenario.goal, True)
        events.append(result.work.to_dict())
    return {"initial": initial.work.to_dict(), "events": events}


def timed_replay(scenario: BaseScenario, closure_count: int, algorithm: str) -> list[dict]:
    grid = GridState(scenario.rows, scenario.cols, scenario.roads)
    current = scenario.start
    rows: list[dict] = []
    if algorithm == "D* Lite":
        started = time.perf_counter_ns()
        planner = DStarLiteV2(grid, current, scenario.goal, collect_work=False)
        planner.initial_search()
        elapsed = time.perf_counter_ns() - started
    else:
        planner = None
        started = time.perf_counter_ns()
        _search(algorithm, grid, current, scenario.goal, False)
        elapsed = time.perf_counter_ns() - started
    rows.append({"phase": "initial", "event_index": 0, "elapsed_ns": elapsed})

    for event in scenario.events[:closure_count]:
        movement_ns = 0
        if planner is not None:
            move_started = time.perf_counter_ns()
            for position in event.movement_segment[1:]:
                planner.move_start(position)
            movement_ns = time.perf_counter_ns() - move_started
        current = event.vehicle_position
        grid.block(event.blocked_cell)  # common environmental mutation is outside timing
        started = time.perf_counter_ns()
        if planner is not None:
            planner.apply_changed_cell(event.blocked_cell)
        else:
            _search(algorithm, grid, current, scenario.goal, False)
        elapsed = time.perf_counter_ns() - started
        rows.append(
            {
                "phase": "replan",
                "event_index": event.event_index,
                "elapsed_ns": elapsed,
                "movement_maintenance_ns": movement_ns,
            }
        )
    return rows


def balanced_orders(seed: int, warmups: int, repetitions: int) -> list[tuple[str, ...]]:
    permutations = [
        (a, b, c)
        for a in ALGORITHMS
        for b in ALGORITHMS
        for c in ALGORITHMS
        if len({a, b, c}) == 3
    ]
    rng = random.Random(seed)
    warmup_orders = [tuple(rng.sample(ALGORITHMS, len(ALGORITHMS))) for _ in range(warmups)]
    measured: list[tuple[str, ...]] = []
    while len(measured) < repetitions:
        cycle = list(permutations)
        rng.shuffle(cycle)
        measured.extend(cycle)
    return warmup_orders + measured[:repetitions]


def _ensure_v2_outputs_safe(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for legacy in LEGACY_FILENAMES:
        if (output_dir / legacy).exists():
            raise FileExistsError(f"Refusing to touch legacy artifact: {output_dir / legacy}")
    names = (
        "scenario_manifest_final_v2.csv",
        "scenario_events_final_v2.csv",
        "experiment_results_final_v2.csv",
        "experiment_event_results_final_v2.csv",
        "timing_samples_final_v2.csv",
        "experiment_metadata_final_v2.json",
    )
    existing = [output_dir / name for name in names if (output_dir / name).exists()]
    if existing:
        raise FileExistsError(f"V2 output already exists: {existing[0]}")


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError(f"Refusing to write empty CSV: {path}")
    fieldnames: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                fieldnames.append(key)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def _scenario_manifest_rows(scenarios: list[BaseScenario], master_seed: int, minimum_distance: int) -> list[dict]:
    rows = []
    for scenario in scenarios:
        row = {
            "experiment_version": EXPERIMENT_VERSION,
            "master_seed": master_seed,
            "scenario_id": scenario.scenario_id,
            "scenario_seed": scenario.scenario_seed,
            "base_scenario_index": scenario.base_scenario_index,
            "map_name": scenario.map_name,
            "map_display_name": scenario.map_display_name,
            "map_category": scenario.map_category,
            "map_sha256": scenario.map_sha256,
            "grid_rows": scenario.rows,
            "grid_cols": scenario.cols,
            "start_row": scenario.start[0],
            "start_col": scenario.start[1],
            "goal_row": scenario.goal[0],
            "goal_col": scenario.goal[1],
            "minimum_initial_distance": minimum_distance,
            "initial_shortest_distance_steps": scenario.initial_shortest_distance_steps,
            "candidate_attempt_number": scenario.candidate_attempt_number,
            "closure_policy": "canonical_route_cell_seeded_route_preserving",
            "reachability_policy": "route_preserving",
            "canonical_neighbor_order": "up,left,right,down",
            "study_population": STUDY_POPULATION,
        }
        for event in scenario.events:
            row[f"trigger_step_{event.event_index}"] = event.trigger_cumulative_step
            row[f"closure_{event.event_index}_row"] = event.blocked_cell[0]
            row[f"closure_{event.event_index}_col"] = event.blocked_cell[1]
        rows.append(row)
    return rows


def _scenario_event_rows(scenarios: list[BaseScenario]) -> list[dict]:
    return [
        {
            "scenario_id": scenario.scenario_id,
            "event_index": event.event_index,
            "trigger_cumulative_step": event.trigger_cumulative_step,
            "vehicle_row": event.vehicle_position[0],
            "vehicle_col": event.vehicle_position[1],
            "blocked_row": event.blocked_cell[0],
            "blocked_col": event.blocked_cell[1],
            "distance_before_closure": event.distance_before_closure,
            "distance_after_closure": event.distance_after_closure,
            "reachable_after_closure": True,
            "canonical_path_invalidated": True,
            "candidate_pool_size": event.candidate_pool_size,
            "candidate_rank_selected": event.candidate_rank_selected,
        }
        for scenario in scenarios
        for event in scenario.events
    ]


def _sum_work(event_work: list[dict], field: str) -> int:
    return sum(int(row[field]) for row in event_work)


def _execute_timed_treatment(
    scenario: BaseScenario,
    closure_count: int,
    warmups: int,
    repetitions: int,
    master_seed: int,
) -> tuple[dict[str, list[dict]], list[dict]]:
    orders = balanced_orders(
        stable_seed(master_seed, scenario.scenario_id, closure_count, "algorithm-order"),
        warmups,
        repetitions,
    )
    per_algorithm: dict[str, list[dict]] = {algorithm: [] for algorithm in ALGORITHMS}
    raw_rows: list[dict] = []
    for replay_index, order in enumerate(orders):
        measured = replay_index >= warmups
        repetition_index = replay_index - warmups if measured else None
        for order_position, algorithm in enumerate(order, start=1):
            phase_rows = timed_replay(scenario, closure_count, algorithm)
            if not measured:
                continue
            initial_ns = phase_rows[0]["elapsed_ns"]
            replanning_ns = sum(row["elapsed_ns"] for row in phase_rows[1:])
            movement_ns = sum(row.get("movement_maintenance_ns", 0) for row in phase_rows[1:])
            totals = {
                "initial": initial_ns,
                "replanning": replanning_ns,
                "movement_maintenance": movement_ns,
                "total_online": initial_ns + replanning_ns + movement_ns,
            }
            per_algorithm[algorithm].append(totals)
            for phase_row in phase_rows:
                raw_rows.append(
                    {
                        "scenario_id": scenario.scenario_id,
                        "closure_count": closure_count,
                        "algorithm": algorithm,
                        "repetition_index": repetition_index,
                        "execution_order_position": order_position,
                        "phase": phase_row["phase"],
                        "event_index": phase_row["event_index"],
                        "elapsed_ns": phase_row["elapsed_ns"],
                        "movement_maintenance_ns": phase_row.get("movement_maintenance_ns", 0),
                    }
                )
    return per_algorithm, raw_rows


def run_full_experiment(
    output_dir: Path,
    master_seed: int,
    minimum_distance: int,
    candidate_limit: int,
    warmups: int,
    repetitions: int,
) -> None:
    if repetitions != 30:
        raise ValueError("Final methodology requires exactly 30 measured repetitions.")
    if warmups != 5:
        raise ValueError("Final methodology requires exactly 5 warm-up repetitions.")
    _ensure_v2_outputs_safe(output_dir)
    scenarios, reports = generate_preflight_scenarios(
        master_seed, minimum_distance, 30, candidate_limit
    )
    if len(scenarios) != 300 or any(report["selected_scenario_count"] != 30 for report in reports):
        raise RuntimeError("Balanced 30-scenario-per-map requirement was not met.")
    validation = validate_scenarios(scenarios)
    if validation.scenarios_validated != 300:
        raise RuntimeError("Pre-timing validation did not cover all scenarios.")
    run_identifier = datetime.now(timezone.utc).strftime("final-v2-%Y%m%dT%H%M%SZ")
    result_rows: list[dict] = []
    event_result_rows: list[dict] = []
    timing_rows: list[dict] = []

    for scenario in scenarios:
        for closure_count in TREATMENTS:
            timed, raw = _execute_timed_treatment(
                scenario, closure_count, warmups, repetitions, master_seed
            )
            timing_rows.extend({"run_identifier": run_identifier, **row} for row in raw)
            scenario_distance = scenario_distance_for_treatment(scenario, closure_count)
            excess_distance = scenario_distance - scenario.initial_shortest_distance_steps
            for algorithm in ALGORITHMS:
                work = replay_for_work(scenario, closure_count, algorithm)
                initial_work = work["initial"]
                event_work = work["events"]
                samples = timed[algorithm]
                result = {
                    "experiment_version": EXPERIMENT_VERSION,
                    "run_identifier": run_identifier,
                    "scenario_id": scenario.scenario_id,
                    "base_scenario_index": scenario.base_scenario_index,
                    "map_name": scenario.map_name,
                    "treatment_id": f"closures_{closure_count}",
                    "closure_count": closure_count,
                    "algorithm": algorithm,
                    "start_row": scenario.start[0],
                    "start_col": scenario.start[1],
                    "goal_row": scenario.goal[0],
                    "goal_col": scenario.goal[1],
                    "initial_shortest_distance_steps": scenario.initial_shortest_distance_steps,
                    "travelled_distance_steps": scenario_distance,
                    "excess_distance_steps": excess_distance,
                    "arrived": True,
                    "success": True,
                    "all_paths_valid": True,
                    "all_paths_optimal": True,
                    "updates_received": closure_count,
                    "replanning_queries": closure_count,
                    "warmup_repetitions": warmups,
                    "measured_repetitions": repetitions,
                    **{f"initial_{key}": value for key, value in initial_work.items()},
                    **{
                        f"replanning_{field}_total": _sum_work(event_work, field)
                        for field in initial_work
                    },
                }
                for prefix in ("initial", "replanning", "movement_maintenance", "total_online"):
                    result.update(timing_statistics([sample[prefix] for sample in samples], prefix))
                result_rows.append(result)

                event_result_rows.append(
                    {
                        "run_identifier": run_identifier,
                        "scenario_id": scenario.scenario_id,
                        "closure_count": closure_count,
                        "algorithm": algorithm,
                        "phase": "initial",
                        "event_index": 0,
                        **initial_work,
                    }
                )
                for event_index, event_metrics in enumerate(event_work, start=1):
                    event_result_rows.append(
                        {
                            "run_identifier": run_identifier,
                            "scenario_id": scenario.scenario_id,
                            "closure_count": closure_count,
                            "algorithm": algorithm,
                            "phase": "replan",
                            "event_index": event_index,
                            **event_metrics,
                        }
                    )

    if len(result_rows) != 2700:
        raise AssertionError(f"Expected 2700 logical result rows, got {len(result_rows)}")
    if any(row["updates_received"] != row["closure_count"] for row in result_rows):
        raise AssertionError("Unequal update workload detected.")
    distance_groups: dict[tuple[str, int], set[tuple[int, int]]] = {}
    for row in result_rows:
        key = (row["scenario_id"], row["closure_count"])
        distance_groups.setdefault(key, set()).add(
            (row["travelled_distance_steps"], row["excess_distance_steps"])
        )
    if any(len(values) != 1 for values in distance_groups.values()):
        raise AssertionError("Scenario-level distance differs across algorithms.")

    _write_csv(output_dir / "scenario_manifest_final_v2.csv", _scenario_manifest_rows(scenarios, master_seed, minimum_distance))
    _write_csv(output_dir / "scenario_events_final_v2.csv", _scenario_event_rows(scenarios))
    _write_csv(output_dir / "experiment_results_final_v2.csv", result_rows)
    _write_csv(output_dir / "experiment_event_results_final_v2.csv", event_result_rows)
    _write_csv(output_dir / "timing_samples_final_v2.csv", timing_rows)
    metadata = {
        "experiment_version": EXPERIMENT_VERSION,
        "run_identifier": run_identifier,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "study_population": STUDY_POPULATION,
        "master_seed": master_seed,
        "minimum_initial_distance": minimum_distance,
        "candidate_limit": candidate_limit,
        "base_scenarios_per_map": 30,
        "closure_treatments": list(TREATMENTS),
        "warmup_repetitions": warmups,
        "measured_repetitions": repetitions,
        "timer": "time.perf_counter_ns",
        "python_version": sys.version,
        "python_implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "command": " ".join(sys.argv),
        "validation": asdict(validation),
        "preflight_maps": reports,
        **_git_metadata(),
    }
    (output_dir / "experiment_metadata_final_v2.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def print_preflight(reports: list[dict], validation: ValidationReport) -> None:
    print("\nFINAL-V2 NON-TIMED FEASIBILITY PREFLIGHT")
    print("=" * 100)
    for report in reports:
        print(
            f"{report['map_name']:<24} eligible={report['eligible_scenario_count']:>4}/"
            f"{report['candidate_attempts_tested']:<5} selected={report['selected_scenario_count']:>2} "
            f"attempt_to_30={str(report['attempts_required_for_30']):>5} "
            f"comfortable={report['comfortable']}"
        )
        print(f"  rejections: {report['rejection_reasons']}")
    print("=" * 100)
    print(f"Validated scenarios: {validation.scenarios_validated}")
    print(f"Validated graph states: {validation.graph_states_validated}")
    print(f"Validated returned paths: {validation.paths_validated}")
    print(f"Dijkstra/oracle matches: {validation.dijkstra_oracle_matches}")
    print(f"A*/oracle matches: {validation.astar_oracle_matches}")
    print(f"D* Lite/oracle matches: {validation.dstar_oracle_matches}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Final-v2 lockstep path-planning experiment")
    subparsers = parser.add_subparsers(dest="command", required=True)

    preflight = subparsers.add_parser("preflight", help="Run non-timed feasibility and correctness checks")
    preflight.add_argument("--master-seed", type=int, default=DEFAULT_MASTER_SEED)
    preflight.add_argument("--min-initial-distance", type=int, default=30)
    preflight.add_argument("--base-scenarios-per-map", type=int, default=30)
    preflight.add_argument("--candidate-limit", type=int, default=5000)
    preflight.add_argument("--output", default="preflight_report_final_v2.json")

    run = subparsers.add_parser("run", help="Safety-gated full final-v2 experiment")
    run.add_argument("--output-dir", default="final_v2_output")
    run.add_argument("--master-seed", type=int, default=DEFAULT_MASTER_SEED)
    run.add_argument("--min-initial-distance", type=int, default=30)
    run.add_argument("--candidate-limit", type=int, default=5000)
    run.add_argument("--warmups", type=int, default=5)
    run.add_argument("--repetitions", type=int, default=30)
    run.add_argument("--enable-final-run", action="store_true")
    args = parser.parse_args()

    if args.command == "preflight":
        scenarios, reports = generate_preflight_scenarios(
            args.master_seed,
            args.min_initial_distance,
            args.base_scenarios_per_map,
            args.candidate_limit,
        )
        expected = len(get_city_maps()) * args.base_scenarios_per_map
        if len(scenarios) != expected:
            # Validate every scenario that was feasible, while still treating
            # the missing balanced cell as a hard preflight failure.
            validation = validate_scenarios(scenarios)
            print_preflight(reports, validation)
            write_preflight_report(
                Path(args.output), reports, validation, args.master_seed,
                args.min_initial_distance, args.base_scenarios_per_map,
            )
            print(f"Failed preflight report written to {args.output}")
            raise RuntimeError(f"Preflight selected {len(scenarios)}/{expected} required scenarios.")
        validation = validate_scenarios(scenarios)
        print_preflight(reports, validation)
        write_preflight_report(
            Path(args.output), reports, validation, args.master_seed,
            args.min_initial_distance, args.base_scenarios_per_map,
        )
        print(f"Preflight report written to {args.output}")
        return

    if not args.enable_final_run:
        raise RuntimeError(
            "Full final generation is disabled. Explicitly pass --enable-final-run only after approval."
        )
    run_full_experiment(
        Path(args.output_dir), args.master_seed, args.min_initial_distance,
        args.candidate_limit, args.warmups, args.repetitions,
    )


if __name__ == "__main__":
    main()
