"""Integrate compatible Phase 4 sources without fabricating relationships."""

import csv
import json
from pathlib import Path

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql.functions import coalesce, col, count, lit, max as spark_max

from src.spark_session import create_spark_session

PRIMARY_INPUT_COLUMNS = [
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
    "corridor",
]
PRIMARY_OUTPUT_COLUMNS = [
    "date",
    "area",
    "road_intersection",
    "corridor",
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
INTEGRATED_COLUMNS = [
    *PRIMARY_OUTPUT_COLUMNS,
    "festival_flag",
    "festival_name",
    "holiday_flag",
]


def project_root() -> Path:
    """Return the project root based on this module's location."""
    return Path(__file__).resolve().parents[2]


def load_integration_config() -> dict[str, object]:
    """Load the reviewed source paths and integration policy."""
    config_path = project_root() / "config" / "integration_config.json"
    with config_path.open("r", encoding="utf-8") as config_file:
        return json.load(config_file)


def configured_path(relative_path: str) -> Path:
    """Resolve a project-relative configured path."""
    return project_root() / relative_path


def read_csv(spark: SparkSession, path: Path) -> DataFrame:
    """Read a CSV for inspection using Spark and its header."""
    if not path.exists():
        raise FileNotFoundError(f"Configured integration input not found: {path}")
    return (
        spark.read
        .option("header", "true")
        .option("inferSchema", "true")
        .csv(str(path))
    )


def validate_primary_schema(primary: DataFrame) -> None:
    """Ensure the Phase 3 primary fields are not silently changed."""
    if primary.columns != PRIMARY_INPUT_COLUMNS:
        raise ValueError(
            f"Unexpected primary columns. Expected {PRIMARY_INPUT_COLUMNS}; "
            f"found {primary.columns}."
        )


def validate_festival_keys(festival: DataFrame) -> int:
    """Reject duplicate calendar dates before joining to prevent row multiplication."""
    duplicate_date_count = (
        festival.groupBy("date")
        .count()
        .where(col("count") > 1)
        .count()
    )
    if duplicate_date_count:
        raise ValueError(
            f"Festival calendar has {duplicate_date_count} duplicate date keys; "
            "integration stopped to prevent accidental row multiplication."
        )
    return duplicate_date_count


def integrate_festival_calendar(primary: DataFrame, festival: DataFrame) -> DataFrame:
    """Left-join one calendar row per date while retaining every traffic record."""
    validate_festival_keys(festival)
    festival_lookup = festival.select(
        col("date").alias("festival_date"),
        col("festival_flag").alias("festival_source_flag"),
        col("festival_name"),
        col("holiday_flag").alias("holiday_source_flag"),
    )
    return (
        primary.join(
            festival_lookup,
            primary["date"] == festival_lookup["festival_date"],
            "left",
        )
        .select(
            *[primary[column_name] for column_name in PRIMARY_OUTPUT_COLUMNS],
            coalesce(col("festival_source_flag"), lit(False)).alias("festival_flag"),
            col("festival_name"),
            coalesce(col("holiday_source_flag"), lit(False)).alias("holiday_flag"),
        )
    )


def write_csv(dataset: DataFrame, path: Path) -> None:
    """Write the small processed result without using the Windows Hadoop writer."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=INTEGRATED_COLUMNS)
        writer.writeheader()
        for row in dataset.toLocalIterator():
            values = row.asDict()
            if values["date"] is not None:
                values["date"] = values["date"].isoformat()
            writer.writerow(values)


def report_validation(
    primary: DataFrame,
    festival: DataFrame,
    toll: DataFrame,
    signal: DataFrame,
    integrated: DataFrame,
    duplicate_calendar_dates: int,
) -> None:
    """Print integration counts, key checks, provenance-relevant distributions, and schema."""
    primary_row_count = primary.count()
    festival_row_count = festival.count()
    toll_row_count = toll.count()
    signal_row_count = signal.count()
    integrated_row_count = integrated.count()
    duplicate_primary_keys = (
        primary.groupBy("date", "corridor").count().where(col("count") > 1).count()
    )
    duplicate_integrated_keys = (
        integrated.groupBy("date", "corridor").count().where(col("count") > 1).count()
    )
    null_counts = {
        column_name: integrated.filter(col(column_name).isNull()).count()
        for column_name in INTEGRATED_COLUMNS
    }
    festival_flags = {
        str(row["festival_flag"]): row["count"]
        for row in integrated.groupBy("festival_flag").count().orderBy("festival_flag").collect()
    }
    holiday_flags = {
        str(row["holiday_flag"]): row["count"]
        for row in integrated.groupBy("holiday_flag").count().orderBy("holiday_flag").collect()
    }
    integrated_festival_names = [
        row["festival_name"]
        for row in integrated.select("festival_name")
        .where(col("festival_name").isNotNull())
        .distinct()
        .orderBy("festival_name")
        .collect()
    ]
    unique_corridors = integrated.select("corridor").distinct().count()

    print("INTEGRATION VALIDATION")
    print("----------------------")
    print(f"Traffic input row count: {primary_row_count}")
    print(f"Festival input row count: {festival_row_count}")
    print(f"Toll input row count: {toll_row_count}")
    print(f"Signal input row count: {signal_row_count}")
    print(f"Integrated output row count: {integrated_row_count}")
    print(f"Duplicate festival date keys: {duplicate_calendar_dates}")
    print(f"Duplicate primary (date, corridor) keys: {duplicate_primary_keys}")
    print(f"Duplicate integrated (date, corridor) keys: {duplicate_integrated_keys}")
    print(f"Null counts for important fields: {null_counts}")
    print(f"Festival flag distribution: {festival_flags}")
    print(f"Holiday flag distribution: {holiday_flags}")
    print(f"Festival name non-null count: {integrated.filter(col('festival_name').isNotNull()).count()}")
    print(f"Unique festival names: {integrated_festival_names}")
    print(f"Unique corridors: {unique_corridors}")
    print("Final integrated schema:")
    integrated.printSchema()
    print("Sample integrated records:")
    integrated.select(
        "date",
        "area",
        "road_intersection",
        "corridor",
        "festival_flag",
        "festival_name",
        "holiday_flag",
    ).show(5, truncate=False)

    if integrated_row_count != primary_row_count:
        raise ValueError(
            "Integrated output row count differs from the primary traffic input: "
            f"{integrated_row_count} != {primary_row_count}."
        )


def main() -> None:
    """Integrate the real traffic data with only the compatible calendar source."""
    spark = create_spark_session("IntegrateTrafficData")
    try:
        configuration = load_integration_config()
        primary = read_csv(spark, configured_path(configuration["primary_real_traffic"]))
        festival = read_csv(
            spark,
            configured_path(configuration["supplementary_real_curated"]["festival_calendar"]),
        )
        toll = read_csv(spark, configured_path(configuration["supplementary_synthetic"]["toll"]))
        signal = read_csv(spark, configured_path(configuration["supplementary_synthetic"]["signal"]))
        validate_primary_schema(primary)
        duplicate_calendar_dates = validate_festival_keys(festival)
        integrated = integrate_festival_calendar(primary, festival)
        output_path = project_root() / "data" / "processed" / "integrated_traffic_data.csv"
        write_csv(integrated, output_path)
        report_validation(
            primary,
            festival,
            toll,
            signal,
            integrated,
            duplicate_calendar_dates,
        )
        print(f"Integrated output path: {output_path}")
        print("Toll and signal remain separate: no compatible real traffic join keys exist.")
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
