import argparse
import csv
from collections import defaultdict


NUMERIC_FIELDS = [
    "initial_calculation_time",
    "initial_visited_count",
    "initial_path_length",
    "total_replanning_time",
    "total_replanning_visited_count",
    "reroute_count",
    "travelled_distance",
    "delivery_delay",
    "total_calculation_time",
]


def to_float(value):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def is_true(value):
    return str(value).strip().lower() == "true"


def mean(values):
    values = [value for value in values if value is not None]
    if not values:
        return None
    return sum(values) / len(values)


def format_value(value):
    if value is None:
        return "-"
    return f"{value:.6f}"


def main():
    parser = argparse.ArgumentParser(description="Tee yhteenveto run_experiments.py:n CSV-tuloksista.")
    parser.add_argument("input", nargs="?", default="experiment_results.csv")
    args = parser.parse_args()

    with open(args.input, newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))

    groups = defaultdict(list)
    for row in rows:
        key = (row["dynamic_obstacle_count_requested"], row["algorithm"])
        groups[key].append(row)

    print("\nYHTEENVETO ALGORITMEITTAIN")
    print("=" * 120)
    print(
        f"{'Esteitä':>7}  {'Algoritmi':<10}  {'N':>4}  {'Onnistui %':>10}  "
        f"{'Alkuaika ms':>12}  {'Uud.aika ms':>12}  {'Kok.aika ms':>12}  "
        f"{'Alku solmut':>12}  {'Uud. solmut':>12}  {'Viive':>10}"
    )
    print("-" * 120)

    for key in sorted(groups.keys(), key=lambda item: (int(item[0]), item[1])):
        dynamic_count, algorithm = key
        group_rows = groups[key]
        n = len(group_rows)
        success_rate = 100 * sum(is_true(row["success"]) for row in group_rows) / n

        initial_time_ms = mean([to_float(row["initial_calculation_time"]) * 1000 for row in group_rows])
        replanning_time_ms = mean([to_float(row["total_replanning_time"]) * 1000 for row in group_rows])
        total_time_ms = mean([to_float(row["total_calculation_time"]) * 1000 for row in group_rows])
        initial_visited = mean([to_float(row["initial_visited_count"]) for row in group_rows])
        replanning_visited = mean([to_float(row["total_replanning_visited_count"]) for row in group_rows])
        delay = mean([to_float(row["delivery_delay"]) for row in group_rows if is_true(row["success"])])

        print(
            f"{dynamic_count:>7}  {algorithm:<10}  {n:>4}  {success_rate:>9.1f}%  "
            f"{format_value(initial_time_ms):>12}  {format_value(replanning_time_ms):>12}  "
            f"{format_value(total_time_ms):>12}  {format_value(initial_visited):>12}  "
            f"{format_value(replanning_visited):>12}  {format_value(delay):>10}"
        )

    print("=" * 120)
    print("Huomio: Viiveen keskiarvo lasketaan vain onnistuneista ajoista.")


if __name__ == "__main__":
    main()
