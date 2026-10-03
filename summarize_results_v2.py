"""Schema-checked descriptive and paired summaries for final-v2 results."""

from __future__ import annotations

import argparse
from collections import defaultdict
import csv
import math
from pathlib import Path
import statistics

from run_experiments_v2 import ALGORITHMS, EXPERIMENT_VERSION, percentile


PRIMARY_METRICS = (
    "initial_ns_median",
    "replanning_ns_median",
    "movement_maintenance_ns_median",
    "total_online_ns_median",
    "initial_expansion_events",
    "initial_unique_expanded_cells",
    "replanning_expansion_events_total",
    "replanning_unique_expanded_cells_total",
)


def describe(values: list[float]) -> dict[str, float | int]:
    if not values:
        raise ValueError("Cannot summarize an empty group.")
    median = statistics.median(values)
    q1 = percentile(values, 0.25)
    q3 = percentile(values, 0.75)
    return {
        "n": len(values),
        "mean": statistics.mean(values),
        "standard_deviation": statistics.stdev(values) if len(values) > 1 else 0.0,
        "median": median,
        "q1": q1,
        "q3": q3,
        "iqr": q3 - q1,
        "mad": statistics.median(abs(value - median) for value in values),
        "p05": percentile(values, 0.05),
        "p95": percentile(values, 0.95),
        "minimum": min(values),
        "maximum": max(values),
    }


def validate_result_rows(rows: list[dict], require_final_counts: bool = True) -> None:
    if not rows:
        raise ValueError("Final-v2 result CSV is empty.")
    if any(row.get("experiment_version") != EXPERIMENT_VERSION for row in rows):
        raise ValueError("Input contains a non-final-v2 schema/version.")
    required = {
        "scenario_id", "map_name", "closure_count", "algorithm",
        "travelled_distance_steps", "excess_distance_steps", *PRIMARY_METRICS,
    }
    missing = required - set(rows[0])
    if missing:
        raise ValueError(f"Missing final-v2 columns: {sorted(missing)}")
    by_scenario: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in rows:
        by_scenario[(row["scenario_id"], row["closure_count"])].append(row)
    for key, group in by_scenario.items():
        if {row["algorithm"] for row in group} != set(ALGORITHMS):
            raise ValueError(f"Incomplete algorithm triplet for {key}")
        distances = {
            (row["travelled_distance_steps"], row["excess_distance_steps"])
            for row in group
        }
        if len(distances) != 1:
            raise ValueError(f"Scenario-level distance differs across algorithms for {key}")
    if require_final_counts:
        if len(rows) != 2700 or len(by_scenario) != 900:
            raise ValueError(f"Expected 2700 rows and 900 treatments, got {len(rows)} and {len(by_scenario)}")
        for algorithm in ALGORITHMS:
            if sum(row["algorithm"] == algorithm for row in rows) != 900:
                raise ValueError(f"Algorithm count is not 900 for {algorithm}")


def build_descriptive_summary(rows: list[dict]) -> list[dict]:
    output: list[dict] = []
    group_specs = (
        ("algorithm_by_closure_count", lambda row: (row["closure_count"], row["algorithm"])),
        ("map_algorithm_by_closure_count", lambda row: (row["map_name"], row["closure_count"], row["algorithm"])),
    )
    for group_name, key_function in group_specs:
        groups: dict[tuple, list[dict]] = defaultdict(list)
        for row in rows:
            groups[key_function(row)].append(row)
        for key, group in sorted(groups.items(), key=lambda item: tuple(str(value) for value in item[0])):
            for metric in PRIMARY_METRICS:
                summary = describe([float(row[metric]) for row in group])
                output.append(
                    {
                        "group": group_name,
                        "map_name": key[0] if group_name.startswith("map_") else "",
                        "closure_count": key[-2],
                        "algorithm": key[-1],
                        "metric": metric,
                        **summary,
                    }
                )
    return output


def build_paired_summary(rows: list[dict]) -> list[dict]:
    by_treatment: dict[tuple[str, str], dict[str, dict]] = defaultdict(dict)
    for row in rows:
        by_treatment[(row["scenario_id"], row["closure_count"])][row["algorithm"]] = row
    pairs = (("A*", "Dijkstra"), ("D* Lite", "Dijkstra"), ("D* Lite", "A*"))
    output: list[dict] = []
    for closure_count in ("1", "3", "5"):
        groups = [group for (scenario_id, count), group in by_treatment.items() if count == closure_count]
        for first, second in pairs:
            for metric in PRIMARY_METRICS:
                differences = [float(group[first][metric]) - float(group[second][metric]) for group in groups]
                output.append(
                    {
                        "closure_count": closure_count,
                        "comparison": f"{first} minus {second}",
                        "metric": metric,
                        **describe(differences),
                    }
                )
    return output


def write_rows(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError("No summary rows.")
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize final-v2 experimental data")
    parser.add_argument("input", nargs="?", default="final_v2_output/experiment_results_final_v2.csv")
    parser.add_argument("--descriptive-output", default="final_v2_output/summary_descriptive_final_v2.csv")
    parser.add_argument("--paired-output", default="final_v2_output/summary_paired_final_v2.csv")
    args = parser.parse_args()
    with Path(args.input).open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    validate_result_rows(rows, require_final_counts=True)
    write_rows(Path(args.descriptive_output), build_descriptive_summary(rows))
    write_rows(Path(args.paired_output), build_paired_summary(rows))


if __name__ == "__main__":
    main()
