"""Validate the raw public Bengaluru traffic dataset with Spark."""

from pathlib import Path

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, max as spark_max, min as spark_min

from src.ingestion.load_real_traffic_data import (
    REAL_DATASET_COLUMNS,
    load_real_traffic_data,
    real_dataset_path,
    read_real_dataset_header,
)
from src.spark_session import create_spark_session

CATEGORICAL_COLUMNS = [
    "Congestion Level",
    "Weather Conditions",
    "Roadwork and Construction Activity",
]
NUMERIC_COLUMNS = [
    "Traffic Volume",
    "Average Speed",
    "Travel Time Index",
    "Congestion Level",
    "Road Capacity Utilization",
    "Incident Reports",
    "Environmental Impact",
    "Public Transport Usage",
    "Traffic Signal Compliance",
    "Parking Usage",
    "Pedestrian and Cyclist Count",
]


def validate_real_traffic_data(spark: SparkSession, path: Path | None = None) -> list[str]:
    """Print raw-data checks and return issues without changing the DataFrame."""
    dataset_path = path or real_dataset_path()
    if not dataset_path.exists():
        raise FileNotFoundError(
            f"Real dataset not found at {dataset_path}. "
            "Place Banglore_traffic_Dataset.csv in data/raw/real/."
        )

    source_columns = read_real_dataset_header(dataset_path)
    issues = []
    if source_columns != REAL_DATASET_COLUMNS:
        issues.append(f"expected columns {REAL_DATASET_COLUMNS}, found {source_columns}")
        print("REAL DATASET VALIDATION")
        print("-----------------------")
        print("Status: FAIL")
        print(f"Columns: {len(source_columns)}")
        print(f"Column names: {source_columns}")
        for issue in issues:
            print(f"- {issue}")
        return issues

    dataset = load_real_traffic_data(spark, dataset_path)
    actual_columns = dataset.columns

    row_count = dataset.count()
    null_counts = {
        column_name: dataset.filter(col(column_name).isNull()).count()
        for column_name in actual_columns
    }
    duplicate_rows = row_count - dataset.dropDuplicates().count()
    distinct_categories = {
        column_name: [
            row[column_name]
            for row in dataset.select(column_name).distinct().orderBy(column_name).collect()
        ]
        for column_name in CATEGORICAL_COLUMNS
    }
    date_bounds = dataset.select(
        spark_min("Date").alias("minimum_date"),
        spark_max("Date").alias("maximum_date"),
    ).first()
    numeric_summary = dataset.select(NUMERIC_COLUMNS).summary("count", "min", "max", "mean", "stddev")
    distinct_areas = dataset.select("Area Name").distinct().count()
    distinct_roads = dataset.select("Road/Intersection Name").distinct().count()

    print("REAL DATASET VALIDATION")
    print("-----------------------")
    print("Status: PASS" if not issues else "Status: FAIL")
    print(f"Rows: {row_count}")
    print(f"Columns: {len(actual_columns)}")
    print(f"Date range: {date_bounds['minimum_date']} to {date_bounds['maximum_date']}")
    print(f"Distinct areas: {distinct_areas}")
    print(f"Distinct roads: {distinct_roads}")
    print(f"Null values: {null_counts}")
    print(f"Duplicate rows: {duplicate_rows}")
    print(f"Congestion levels: {distinct_categories['Congestion Level']}")
    print(f"Weather categories: {distinct_categories['Weather Conditions']}")
    print(
        "Roadwork categories: "
        f"{distinct_categories['Roadwork and Construction Activity']}"
    )
    print("\nExact schema:")
    dataset.printSchema()
    print("\nNumeric summary:")
    numeric_summary.show(truncate=False)

    if any(null_counts.values()):
        issues.append(f"null values found: {null_counts}")
    if duplicate_rows:
        issues.append(f"duplicate rows found: {duplicate_rows}")
    if date_bounds["minimum_date"] is None or date_bounds["maximum_date"] is None:
        issues.append("Date contains no valid parsed values")

    if issues:
        print("\nValidation issues:")
        for issue in issues:
            print(f"- {issue}")
    else:
        print("\nValidation checks passed without modifying the raw dataset.")
    return issues


def main() -> None:
    """Run validation from the project root and return a failing exit code on issues."""
    spark = create_spark_session("ValidateRealBengaluruTrafficData")
    try:
        issues = validate_real_traffic_data(spark)
    finally:
        spark.stop()
    if issues:
        raise SystemExit(1)


if __name__ == "__main__":
    main()