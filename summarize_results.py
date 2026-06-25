import argparse
import csv
from collections import defaultdict
from pathlib import Path


SUMMARY_FIELDS = [
    "group",
    "dynamic_obstacle_count_requested",
    "map_name",
    "map_display_name",
    "map_category",
    "algorithm",
    "n",
    "success_rate_percent",
    "initial_calculation_time_ms_mean",
    "total_replanning_time_ms_mean",
    "total_calculation_time_ms_mean",
    "initial_visited_count_mean",
    "total_replanning_visited_count_mean",
    "initial_path_length_mean",
    "travelled_distance_mean",
    "delivery_delay_mean",
    "reroute_count_mean",
    "effective_obstacle_count_mean",
]


def to_float(value):
    """Muuntaa CSV-arvon liukuluvuksi."""
    if value in (None, ""):
        return None

    try:
        return float(value)
    except ValueError:
        return None


def is_true(value):
    """Tulkisee CSV:n totuusarvon."""
    return str(value).strip().lower() == "true"


def mean(values):
    """Laskee keskiarvon ohittaen None-arvot."""
    cleaned = [value for value in values if value is not None]

    if not cleaned:
        return None

    return sum(cleaned) / len(cleaned)


def format_value(value, decimals=3):
    """Muotoilee tulostettavan arvon."""
    if value is None:
        return "-"

    return f"{value:.{decimals}f}"


def get_ms(row, field):
    value = to_float(row.get(field))
    if value is None:
        return None
    return value * 1000


def summarize_group(group_rows, group_name, dynamic_count=None, map_name=None, map_display_name=None, map_category=None, algorithm=None):
    """Muodostaa yhden yhteenvetorivin."""
    n = len(group_rows)

    if n == 0:
        return None

    success_rate = 100 * sum(is_true(row.get("success")) for row in group_rows) / n
    successful_rows = [row for row in group_rows if is_true(row.get("success"))]

    return {
        "group": group_name,
        "dynamic_obstacle_count_requested": dynamic_count if dynamic_count is not None else "",
        "map_name": map_name if map_name is not None else "",
        "map_display_name": map_display_name if map_display_name is not None else "",
        "map_category": map_category if map_category is not None else "",
        "algorithm": algorithm if algorithm is not None else "",
        "n": n,
        "success_rate_percent": success_rate,
        "initial_calculation_time_ms_mean": mean([get_ms(row, "initial_calculation_time") for row in group_rows]),
        "total_replanning_time_ms_mean": mean([get_ms(row, "total_replanning_time") for row in group_rows]),
        "total_calculation_time_ms_mean": mean([get_ms(row, "total_calculation_time") for row in group_rows]),
        "initial_visited_count_mean": mean([to_float(row.get("initial_visited_count")) for row in group_rows]),
        "total_replanning_visited_count_mean": mean([to_float(row.get("total_replanning_visited_count")) for row in group_rows]),
        "initial_path_length_mean": mean([to_float(row.get("initial_path_length")) for row in group_rows]),
        "travelled_distance_mean": mean([to_float(row.get("travelled_distance")) for row in successful_rows]),
        "delivery_delay_mean": mean([to_float(row.get("delivery_delay")) for row in successful_rows]),
        "reroute_count_mean": mean([to_float(row.get("reroute_count")) for row in group_rows]),
        "effective_obstacle_count_mean": mean([to_float(row.get("effective_obstacle_count")) for row in group_rows]),
    }


def print_algorithm_summary(summary_rows):
    """Tulostaa yleisen algoritmikohtaisen yhteenvedon."""
    rows = [row for row in summary_rows if row["group"] == "algorithm_by_dynamic_count"]

    print("\nYHTEENVETO ALGORITMEITTAIN JA TIESULKUMÄÄRITTÄIN")
    print("=" * 142)
    print(
        f"{'Sulkuja':>7}  {'Algoritmi':<10}  {'N':>5}  {'Onnistui %':>10}  "
        f"{'Alkuaika ms':>12}  {'Uud.aika ms':>12}  {'Kok.aika ms':>12}  "
        f"{'Alku solmut':>12}  {'Uud. solmut':>12}  {'Reitti':>8}  "
        f"{'Matka':>8}  {'Viive':>8}  {'Uud.reit.':>9}"
    )
    print("-" * 142)

    def sort_key(row):
        try:
            dynamic_count = int(row["dynamic_obstacle_count_requested"])
        except ValueError:
            dynamic_count = 0
        return dynamic_count, row["algorithm"]

    for row in sorted(rows, key=sort_key):
        print(
            f"{str(row['dynamic_obstacle_count_requested']):>7}  "
            f"{row['algorithm']:<10}  "
            f"{row['n']:>5}  "
            f"{format_value(row['success_rate_percent'], 1):>9}%  "
            f"{format_value(row['initial_calculation_time_ms_mean']):>12}  "
            f"{format_value(row['total_replanning_time_ms_mean']):>12}  "
            f"{format_value(row['total_calculation_time_ms_mean']):>12}  "
            f"{format_value(row['initial_visited_count_mean'], 1):>12}  "
            f"{format_value(row['total_replanning_visited_count_mean'], 1):>12}  "
            f"{format_value(row['initial_path_length_mean'], 1):>8}  "
            f"{format_value(row['travelled_distance_mean'], 1):>8}  "
            f"{format_value(row['delivery_delay_mean'], 1):>8}  "
            f"{format_value(row['reroute_count_mean'], 1):>9}"
        )

    print("=" * 142)
    print("Viive ja kuljettu matka lasketaan vain onnistuneista ajoista.")


def print_map_summary(summary_rows):
    """Tulostaa karttakohtaisen yhteenvedon."""
    rows = [row for row in summary_rows if row["group"] == "map_by_algorithm"]

    print("\nYHTEENVETO KARTOITTAIN JA ALGORITMEITTAIN")
    print("=" * 132)
    print(
        f"{'Kartta':<28}  {'Algoritmi':<10}  {'N':>5}  {'Onn. %':>7}  "
        f"{'Alkuaika ms':>12}  {'Uud.aika ms':>12}  {'Kok.aika ms':>12}  "
        f"{'Alku solmut':>12}  {'Uud. solmut':>12}  {'Viive':>8}"
    )
    print("-" * 132)

    for row in sorted(rows, key=lambda item: (item["map_display_name"], item["algorithm"])):
        map_display_name = row["map_display_name"][:28]
        print(
            f"{map_display_name:<28}  "
            f"{row['algorithm']:<10}  "
            f"{row['n']:>5}  "
            f"{format_value(row['success_rate_percent'], 1):>6}%  "
            f"{format_value(row['initial_calculation_time_ms_mean']):>12}  "
            f"{format_value(row['total_replanning_time_ms_mean']):>12}  "
            f"{format_value(row['total_calculation_time_ms_mean']):>12}  "
            f"{format_value(row['initial_visited_count_mean'], 1):>12}  "
            f"{format_value(row['total_replanning_visited_count_mean'], 1):>12}  "
            f"{format_value(row['delivery_delay_mean'], 1):>8}"
        )

    print("=" * 132)


def write_summary_csv(output_path, summary_rows):
    """Tallentaa yhteenvetorivit CSV-tiedostoon."""
    with open(output_path, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=SUMMARY_FIELDS)
        writer.writeheader()

        for row in summary_rows:
            writer.writerow(row)


def build_summaries(rows):
    """Rakentaa kaikki yhteenvetoryhmät."""
    summary_rows = []

    # 1) Algoritmi + pyydetty tiesulkumäärä.
    groups = defaultdict(list)
    for row in rows:
        key = (
            row.get("dynamic_obstacle_count_requested", ""),
            row.get("algorithm", ""),
        )
        groups[key].append(row)

    for (dynamic_count, algorithm), group_rows in groups.items():
        summary_rows.append(
            summarize_group(
                group_rows,
                group_name="algorithm_by_dynamic_count",
                dynamic_count=dynamic_count,
                algorithm=algorithm,
            )
        )

    # 2) Kartta + algoritmi.
    groups = defaultdict(list)
    for row in rows:
        key = (
            row.get("map_name", ""),
            row.get("map_display_name", ""),
            row.get("map_category", ""),
            row.get("algorithm", ""),
        )
        groups[key].append(row)

    for (map_name, map_display_name, map_category, algorithm), group_rows in groups.items():
        summary_rows.append(
            summarize_group(
                group_rows,
                group_name="map_by_algorithm",
                map_name=map_name,
                map_display_name=map_display_name,
                map_category=map_category,
                algorithm=algorithm,
            )
        )

    # 3) Karttatyyppi + algoritmi.
    groups = defaultdict(list)
    for row in rows:
        key = (
            row.get("map_category", ""),
            row.get("algorithm", ""),
        )
        groups[key].append(row)

    for (map_category, algorithm), group_rows in groups.items():
        summary_rows.append(
            summarize_group(
                group_rows,
                group_name="map_category_by_algorithm",
                map_category=map_category,
                algorithm=algorithm,
            )
        )

    # 4) Kokonaisyhteenveto algoritmeittain.
    groups = defaultdict(list)
    for row in rows:
        key = row.get("algorithm", "")
        groups[key].append(row)

    for algorithm, group_rows in groups.items():
        summary_rows.append(
            summarize_group(
                group_rows,
                group_name="algorithm_overall",
                algorithm=algorithm,
            )
        )

    return [row for row in summary_rows if row is not None]


def main():
    parser = argparse.ArgumentParser(
        description="Tee yhteenveto kaupunkikarttoihin perustuvan run_experiments.py-ajon CSV-tuloksista."
    )
    parser.add_argument("input", nargs="?", default="experiment_results.csv")
    parser.add_argument("--output", default="summary_results.csv")
    args = parser.parse_args()

    input_path = Path(args.input)

    if not input_path.exists():
        raise FileNotFoundError(f"Tiedostoa ei löytynyt: {input_path}")

    with open(input_path, newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))

    if not rows:
        print("CSV-tiedostossa ei ollut rivejä.")
        return

    summary_rows = build_summaries(rows)

    print_algorithm_summary(summary_rows)
    print_map_summary(summary_rows)

    write_summary_csv(args.output, summary_rows)
    print(f"\nYhteenveto tallennettu tiedostoon {args.output}.")


if __name__ == "__main__":
    main()
