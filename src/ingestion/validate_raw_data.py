"""Validate the Phase 1 raw CSV schemas and basic data quality."""

import csv
from datetime import datetime
from pathlib import Path

DATASETS = {
    "traffic.csv": {
        "columns": [
            "timestamp",
            "junction",
            "traffic_volume",
            "congestion_level",
            "weather",
            "signal_status",
        ],
        "categorical": ["junction", "congestion_level", "weather", "signal_status"],
        "time_column": "timestamp",
        "time_format": "%Y-%m-%d %H:%M:%S",
    },
    "toll.csv": {
        "columns": ["timestamp", "toll_plaza", "vehicle_count", "transaction_count"],
        "categorical": ["toll_plaza"],
        "time_column": "timestamp",
        "time_format": "%Y-%m-%d %H:%M:%S",
    },
    "signal.csv": {
        "columns": ["timestamp", "junction", "signal_status"],
        "categorical": ["junction", "signal_status"],
        "time_column": "timestamp",
        "time_format": "%Y-%m-%d %H:%M:%S",
    },
    "festival_calendar.csv": {
        "columns": ["date", "festival_name", "is_festival", "is_holiday", "day_type"],
        "categorical": ["festival_name", "is_festival", "is_holiday", "day_type"],
        "time_column": "date",
        "time_format": "%Y-%m-%d",
    },
}


def validate_file(path: Path, configuration: dict[str, object]) -> list[str]:
    """Validate one CSV and print the requested summary information."""
    issues = []
    required_columns = configuration["columns"]
    categorical_columns = configuration["categorical"]
    time_column = configuration["time_column"]
    time_format = configuration["time_format"]

    with path.open("r", newline="", encoding="utf-8") as input_file:
        reader = csv.DictReader(input_file)
        actual_columns = reader.fieldnames or []
        rows = list(reader)

    missing_columns = [column for column in required_columns if column not in actual_columns]
    if missing_columns:
        issues.append(f"missing required columns: {missing_columns}")

    missing_values = {
        column: sum(not row.get(column, "").strip() for row in rows)
        for column in required_columns
        if column in actual_columns
    }
    missing_values = {column: count for column, count in missing_values.items() if count}
    if missing_values:
        issues.append(f"missing values: {missing_values}")

    duplicate_count = len(rows) - len({tuple(row.items()) for row in rows})
    if duplicate_count:
        issues.append(f"duplicate rows: {duplicate_count}")

    unique_values = {
        column: sorted({row[column] for row in rows})
        for column in categorical_columns
        if column in actual_columns
    }
    parsed_times = []
    if time_column in actual_columns:
        for row_number, row in enumerate(rows, start=2):
            try:
                parsed_times.append(datetime.strptime(row[time_column], time_format))
            except ValueError:
                issues.append(
                    f"invalid {time_column} at CSV row {row_number}: {row[time_column]}"
                )

    print(f"\n{path.name}")
    print(f"  schema: {actual_columns}")
    print(f"  row count: {len(rows)}")
    print(f"  missing values: {missing_values or 'none'}")
    print(f"  duplicate rows: {duplicate_count}")
    print(f"  categorical values: {unique_values}")
    if parsed_times:
        print(f"  minimum {time_column}: {min(parsed_times).isoformat(sep=' ')}")
        print(f"  maximum {time_column}: {max(parsed_times).isoformat(sep=' ')}")

    return issues


def validate_raw_data(data_directory: Path) -> list[str]:
    """Validate every configured raw dataset and return all issues."""
    issues = []
    for filename, configuration in DATASETS.items():
        path = data_directory / filename
        if not path.exists():
            issues.append(f"missing file: {path}")
            print(f"\n{filename}\n  ERROR: file does not exist")
            continue
        issues.extend(f"{filename}: {issue}" for issue in validate_file(path, configuration))
    return issues


def main() -> None:
    """Validate raw files from the project root and return a useful exit status."""
    project_root = Path(__file__).resolve().parents[2]
    issues = validate_raw_data(project_root / "data" / "raw")
    if issues:
        print("\nValidation issues found:")
        for issue in issues:
            print(f"- {issue}")
        raise SystemExit(1)
    print("\nValidation passed: all required raw datasets are present and valid.")


if __name__ == "__main__":
    main()
