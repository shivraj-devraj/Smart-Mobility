"""Add deterministic corridor identifiers to the processed real traffic data."""

import csv
import json
from pathlib import Path

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql.functions import col, concat, lit, when

from src.spark_session import create_spark_session

INPUT_COLUMNS = [
    "date",
    "area",
    "road_intersection",
    "traffic_volume",
    "average_speed",
    "travel_time_index",
    "congestion_level",
    "congestion_class",
    "weather",
    "roadwork",
    "day_of_week",
    "day_type",
]
OUTPUT_COLUMNS = [*INPUT_COLUMNS, "corridor"]


def project_root() -> Path:
    """Return the project root based on this module's location."""
    return Path(__file__).resolve().parents[2]


def load_corridor_configuration() -> dict[str, object]:
    """Load and validate the transparent corridor rule configuration."""
    config_path = project_root() / "config" / "corridor_mapping.json"
    with config_path.open("r", encoding="utf-8") as config_file:
        configuration = json.load(config_file)

    if configuration["rule_type"] != "composite_identifier":
        raise ValueError("Unsupported corridor rule type.")
    if configuration["source_fields"] != ["area", "road_intersection"]:
        raise ValueError("Corridor rule must use area and road_intersection.")
    return configuration


def input_path() -> Path:
    """Return the Phase 2 processed dataset path."""
    return project_root() / "data" / "processed" / "real_traffic_preprocessed.csv"


def output_path() -> Path:
    """Return the corridor-tagged output path."""
    return project_root() / "data" / "processed" / "real_traffic_corridor_tagged.csv"


def load_processed_dataset(spark: SparkSession, path: Path | None = None) -> DataFrame:
    """Read the processed CSV without changing its source file."""
    source_path = path or input_path()
    if not source_path.exists():
        raise FileNotFoundError(f"Processed input not found at {source_path}.")

    dataset = (
        spark.read
        .option("header", "true")
        .option("inferSchema", "true")
        .csv(str(source_path))
    )
    if dataset.columns != INPUT_COLUMNS:
        raise ValueError(
            f"Unexpected processed columns. Expected {INPUT_COLUMNS}; "
            f"found {dataset.columns}."
        )
    return dataset


def add_corridor_column(dataset: DataFrame) -> DataFrame:
    """Append a composite corridor while preserving the original location columns."""
    corridor = when(
        col("area").isNull() | col("road_intersection").isNull(),
        None,
    ).otherwise(concat(col("area"), lit(" | "), col("road_intersection")))
    return dataset.withColumn("corridor", corridor).select(OUTPUT_COLUMNS)


def write_corridor_dataset(dataset: DataFrame, path: Path | None = None) -> None:
    """Write the tagged result with standard-library CSV I/O for local development."""
    destination = path or output_path()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        for row in dataset.toLocalIterator():
            values = row.asDict()
            if values["date"] is not None:
                values["date"] = values["date"].isoformat()
            writer.writerow(values)


def report_validation(input_row_count: int, dataset: DataFrame) -> None:
    """Print the required corridor-tagging validation report."""
    output_row_count = dataset.count()
    corridor_distribution = {
        row["corridor"]: row["count"]
        for row in dataset.groupBy("corridor").count().orderBy("corridor").collect()
    }
    null_corridor_count = dataset.filter(col("corridor").isNull()).count()

    print("CORRIDOR TAGGING VALIDATION")
    print("---------------------------")
    print(f"Input row count: {input_row_count}")
    print(f"Output row count: {output_row_count}")
    print(f"Unique corridors: {dataset.select('corridor').distinct().count()}")
    print(f"Null corridor count: {null_corridor_count}")
    print("Corridor distribution:")
    for corridor_name, count in corridor_distribution.items():
        print(f"  {corridor_name}: {count}")
    print("Sample records:")
    dataset.select("area", "road_intersection", "corridor").show(5, truncate=False)


def main() -> None:
    """Tag the processed real traffic dataset and print validation results."""
    spark = create_spark_session("TagRealTrafficCorridors")
    try:
        configuration = load_corridor_configuration()
        print(f"Corridor rule: {configuration['rule']}")
        source_data = load_processed_dataset(spark)
        input_row_count = source_data.count()
        tagged_data = add_corridor_column(source_data)
        write_corridor_dataset(tagged_data)
        report_validation(input_row_count, tagged_data)
        print(f"Output path: {output_path()}")
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
