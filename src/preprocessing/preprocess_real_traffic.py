"""Prepare the primary real traffic dataset for later analytical phases."""

import csv
import json
from pathlib import Path

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql.functions import col, dayofweek, to_date, when

from src.ingestion.load_real_traffic_data import load_real_traffic_data
from src.spark_session import create_spark_session

STANDARDIZED_COLUMNS = [
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
IMPORTANT_COLUMNS = STANDARDIZED_COLUMNS


def project_root() -> Path:
    """Return the project root based on this module's location."""
    return Path(__file__).resolve().parents[2]


def load_json_config(path: Path) -> dict[str, object]:
    """Read a small JSON configuration file without changing it."""
    with path.open("r", encoding="utf-8") as config_file:
        return json.load(config_file)


def primary_dataset_path() -> Path:
    """Resolve the primary traffic path from data_sources.json."""
    configuration = load_json_config(project_root() / "config" / "data_sources.json")
    primary_source = configuration["primary_traffic_source"]
    if primary_source["type"] != "real":
        raise ValueError("Configured primary traffic source must be the real dataset.")
    return project_root() / primary_source["path"]


def output_path() -> Path:
    """Return the processed CSV location without touching raw data."""
    return project_root() / "data" / "processed" / "real_traffic_preprocessed.csv"


def load_threshold_configuration() -> dict[str, object]:
    """Load the reviewable congestion thresholds from project configuration."""
    configuration = load_json_config(project_root() / "config" / "preprocessing_config.json")
    classification = configuration["congestion_classification"]
    low_max = float(classification["low_max_exclusive"])
    medium_max = float(classification["medium_max_exclusive"])
    if low_max >= medium_max:
        raise ValueError("Congestion thresholds must be strictly increasing.")
    return classification


def build_preprocessed_dataset(
    spark: SparkSession,
    input_path: Path | None = None,
    thresholds: dict[str, object] | None = None,
) -> DataFrame:
    """Create standardized columns while preserving all input rows and values."""
    source_path = input_path or primary_dataset_path()
    threshold_config = thresholds or load_threshold_configuration()
    low_max = float(threshold_config["low_max_exclusive"])
    medium_max = float(threshold_config["medium_max_exclusive"])

    raw_data = load_real_traffic_data(spark, source_path)
    date_column = to_date(col("Date"), "yyyy-MM-dd")
    congestion_class = (
        when(col("Congestion Level").isNull(), None)
        .when(col("Congestion Level") < low_max, "Low")
        .when(col("Congestion Level") < medium_max, "Medium")
        .otherwise("High")
    )

    # Only reliable source fields and date-level calendar fields are standardized here.
    return raw_data.select(
        date_column.alias("date"),
        col("Area Name").alias("area"),
        col("Road/Intersection Name").alias("road_intersection"),
        col("Traffic Volume").alias("traffic_volume"),
        col("Average Speed").alias("average_speed"),
        col("Travel Time Index").alias("travel_time_index"),
        col("Congestion Level").alias("congestion_level"),
        congestion_class.alias("congestion_class"),
        col("Weather Conditions").alias("weather"),
        col("Roadwork and Construction Activity").alias("roadwork"),
        date_column.alias("date_for_day_type"),
    ).withColumn(
        "day_of_week",
        dayofweek(col("date_for_day_type")),
    ).withColumn(
        "day_type",
        when(col("date_for_day_type").isNull(), None)
        .when(col("day_of_week").isin(1, 7), "Weekend")
        .otherwise("Weekday"),
    ).drop("date_for_day_type").select(STANDARDIZED_COLUMNS)


def write_preprocessed_dataset(dataset: DataFrame, path: Path | None = None) -> None:
    """Write the processed dataset with Python CSV I/O for local Windows use."""
    destination = path or output_path()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=STANDARDIZED_COLUMNS)
        writer.writeheader()
        for row in dataset.toLocalIterator():
            values = row.asDict()
            if values["date"] is not None:
                values["date"] = values["date"].isoformat()
            writer.writerow(values)


def report_validation(input_row_count: int, dataset: DataFrame) -> None:
    """Print the small validation/check report required for this phase."""
    output_row_count = dataset.count()
    class_distribution = {
        row["congestion_class"]: row["count"]
        for row in dataset.groupBy("congestion_class").count().orderBy("congestion_class").collect()
    }
    null_counts = {
        column_name: dataset.filter(col(column_name).isNull()).count()
        for column_name in IMPORTANT_COLUMNS
    }

    print("PREPROCESSING VALIDATION")
    print("------------------------")
    print(f"Input row count: {input_row_count}")
    print(f"Output row count: {output_row_count}")
    print("Schema:")
    dataset.printSchema()
    print(f"Congestion class distribution: {class_distribution}")
    print(f"Null counts for important columns: {null_counts}")
    print("Sample output:")
    dataset.show(5, truncate=False)


def main() -> None:
    """Run preprocessing and write the primary real traffic output."""
    spark = create_spark_session("PreprocessRealTraffic")
    try:
        source_path = primary_dataset_path()
        raw_data = load_real_traffic_data(spark, source_path)
        input_row_count = raw_data.count()
        processed_data = build_preprocessed_dataset(spark, source_path)
        write_preprocessed_dataset(processed_data)
        report_validation(input_row_count, processed_data)
        print(f"Processed output: {output_path()}")
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
