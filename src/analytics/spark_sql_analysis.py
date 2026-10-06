"""Run Phase 5 batch analytics with Spark SQL only."""

import csv
from pathlib import Path

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql.functions import col, to_date
from pyspark.sql.types import BooleanType, DateType, DoubleType, IntegerType, StringType

from src.spark_session import create_spark_session

INPUT_COLUMNS = [
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
    "festival_flag",
    "festival_name",
    "holiday_flag",
]

NUMERIC_COLUMNS = [
    "traffic_volume",
    "average_speed",
    "travel_time_index",
    "congestion_level",
]
IMPORTANT_COLUMNS = [
    "date",
    "corridor",
    "traffic_volume",
    "average_speed",
    "travel_time_index",
    "congestion_level",
    "congestion_class",
    "festival_flag",
    "holiday_flag",
]

ANALYSIS_QUERIES = {
    "corridor_congestion_summary": """
        SELECT
            corridor,
            COUNT(*) AS record_count,
            AVG(traffic_volume) AS average_traffic_volume,
            AVG(average_speed) AS average_speed,
            AVG(congestion_level) AS average_congestion_level,
            AVG(travel_time_index) AS average_travel_time_index,
            SUM(CASE WHEN congestion_class = 'Low' THEN 1 ELSE 0 END) AS low_congestion_count,
            SUM(CASE WHEN congestion_class = 'Medium' THEN 1 ELSE 0 END) AS medium_congestion_count,
            SUM(CASE WHEN congestion_class = 'High' THEN 1 ELSE 0 END) AS high_congestion_count
        FROM traffic_data
        GROUP BY corridor
        ORDER BY average_congestion_level DESC
    """,
    "high_congestion_corridors": """
        SELECT
            corridor,
            COUNT(*) AS total_records,
            SUM(CASE WHEN congestion_class = 'High' THEN 1 ELSE 0 END) AS high_congestion_count,
            100.0 * SUM(CASE WHEN congestion_class = 'High' THEN 1 ELSE 0 END) / COUNT(*)
                AS high_congestion_percentage
        FROM traffic_data
        GROUP BY corridor
        ORDER BY high_congestion_percentage DESC
    """,
    "day_type_congestion_summary": """
        SELECT
            day_type,
            COUNT(*) AS record_count,
            AVG(traffic_volume) AS average_traffic_volume,
            AVG(average_speed) AS average_speed,
            AVG(congestion_level) AS average_congestion_level,
            AVG(travel_time_index) AS average_travel_time_index,
            SUM(CASE WHEN congestion_class = 'High' THEN 1 ELSE 0 END) AS high_congestion_count,
            100.0 * SUM(CASE WHEN congestion_class = 'High' THEN 1 ELSE 0 END) / COUNT(*)
                AS high_congestion_percentage
        FROM traffic_data
        GROUP BY day_type
        ORDER BY day_type
    """,
    "festival_congestion_summary": """
        SELECT
            festival_flag,
            COUNT(*) AS record_count,
            AVG(traffic_volume) AS average_traffic_volume,
            AVG(average_speed) AS average_speed,
            AVG(congestion_level) AS average_congestion_level,
            AVG(travel_time_index) AS average_travel_time_index,
            SUM(CASE WHEN congestion_class = 'High' THEN 1 ELSE 0 END) AS high_congestion_count,
            100.0 * SUM(CASE WHEN congestion_class = 'High' THEN 1 ELSE 0 END) / COUNT(*)
                AS high_congestion_percentage
        FROM traffic_data
        GROUP BY festival_flag
        ORDER BY festival_flag
    """,
    "holiday_congestion_summary": """
        SELECT
            holiday_flag,
            COUNT(*) AS record_count,
            AVG(traffic_volume) AS average_traffic_volume,
            AVG(average_speed) AS average_speed,
            AVG(congestion_level) AS average_congestion_level,
            SUM(CASE WHEN congestion_class = 'High' THEN 1 ELSE 0 END) AS high_congestion_count,
            100.0 * SUM(CASE WHEN congestion_class = 'High' THEN 1 ELSE 0 END) / COUNT(*)
                AS high_congestion_percentage
        FROM traffic_data
        GROUP BY holiday_flag
        ORDER BY holiday_flag
    """,
    "day_of_week_congestion_summary": """
        SELECT
            day_of_week,
            COUNT(*) AS record_count,
            AVG(traffic_volume) AS average_traffic_volume,
            AVG(average_speed) AS average_speed,
            AVG(congestion_level) AS average_congestion_level,
            100.0 * SUM(CASE WHEN congestion_class = 'High' THEN 1 ELSE 0 END) / COUNT(*)
                AS high_congestion_percentage
        FROM traffic_data
        GROUP BY day_of_week
        ORDER BY day_of_week
    """,
    "festival_corridor_analysis": """
        SELECT
            corridor,
            COUNT(*) AS festival_record_count,
            AVG(traffic_volume) AS average_festival_traffic_volume,
            AVG(congestion_level) AS average_festival_congestion_level,
            SUM(CASE WHEN congestion_class = 'High' THEN 1 ELSE 0 END) AS high_congestion_count,
            100.0 * SUM(CASE WHEN congestion_class = 'High' THEN 1 ELSE 0 END) / COUNT(*)
                AS high_congestion_percentage
        FROM traffic_data
        WHERE festival_flag = true
        GROUP BY corridor
        ORDER BY average_festival_congestion_level DESC
    """,
    "top5_average_congestion_corridors": """
        SELECT
            corridor,
            COUNT(*) AS record_count,
            AVG(congestion_level) AS average_congestion_level
        FROM traffic_data
        GROUP BY corridor
        ORDER BY average_congestion_level DESC
        LIMIT 5
    """,
    "top5_high_congestion_percentage_corridors": """
        SELECT
            corridor,
            COUNT(*) AS total_records,
            SUM(CASE WHEN congestion_class = 'High' THEN 1 ELSE 0 END) AS high_congestion_count,
            100.0 * SUM(CASE WHEN congestion_class = 'High' THEN 1 ELSE 0 END) / COUNT(*)
                AS high_congestion_percentage
        FROM traffic_data
        GROUP BY corridor
        ORDER BY high_congestion_percentage DESC
        LIMIT 5
    """,
}

OUTPUT_FILES = {
    "corridor_congestion_summary": "corridor_congestion_summary.csv",
    "high_congestion_corridors": "high_congestion_corridors.csv",
    "day_type_congestion_summary": "day_type_congestion_summary.csv",
    "festival_congestion_summary": "festival_congestion_summary.csv",
    "holiday_congestion_summary": "holiday_congestion_summary.csv",
    "day_of_week_congestion_summary": "day_of_week_congestion_summary.csv",
    "festival_corridor_analysis": "festival_corridor_analysis.csv",
    "top5_average_congestion_corridors": "top5_average_congestion_corridors.csv",
    "top5_high_congestion_percentage_corridors": "top5_high_congestion_percentage_corridors.csv",
}


def project_root() -> Path:
    """Return the project root based on this module's location."""
    return Path(__file__).resolve().parents[2]


def input_path() -> Path:
    return project_root() / "data" / "processed" / "integrated_traffic_data.csv"


def output_directory() -> Path:
    return project_root() / "data" / "output"


def load_traffic_data(spark: SparkSession) -> DataFrame:
    """Load the integrated CSV and enforce the analytics types."""
    source = input_path()
    if not source.exists():
        raise FileNotFoundError(f"Integrated input not found: {source}")
    raw = (
        spark.read.option("header", "true")
        .option("inferSchema", "true")
        .csv(str(source))
    )
    if raw.columns != INPUT_COLUMNS:
        raise ValueError(f"Unexpected integrated columns: {raw.columns}")

    typed = raw.withColumn("date", to_date(col("date"), "yyyy-MM-dd"))
    for column_name in NUMERIC_COLUMNS:
        typed = typed.withColumn(column_name, col(column_name).cast(DoubleType()))
    typed = typed.withColumn("day_of_week", col("day_of_week").cast(IntegerType()))
    typed = typed.withColumn("festival_flag", col("festival_flag").cast(BooleanType()))
    typed = typed.withColumn("holiday_flag", col("holiday_flag").cast(BooleanType()))
    return typed.select(INPUT_COLUMNS)


def report_data_quality(traffic_data: DataFrame) -> None:
    """Print source checks before any analytical query runs."""
    row_count = traffic_data.count()
    bounds = traffic_data.selectExpr("MIN(date) AS minimum_date", "MAX(date) AS maximum_date").first()
    null_counts = {
        column_name: traffic_data.filter(col(column_name).isNull()).count()
        for column_name in IMPORTANT_COLUMNS
    }
    congestion_classes = [
        row["congestion_class"]
        for row in traffic_data.select("congestion_class").distinct().orderBy("congestion_class").collect()
    ]
    festival_counts = {
        str(row["festival_flag"]): row["count"]
        for row in traffic_data.groupBy("festival_flag").count().orderBy("festival_flag").collect()
    }
    holiday_counts = {
        str(row["holiday_flag"]): row["count"]
        for row in traffic_data.groupBy("holiday_flag").count().orderBy("holiday_flag").collect()
    }

    print("DATA QUALITY")
    print("------------")
    print(f"Total rows: {row_count}")
    print(f"Distinct corridors: {traffic_data.select('corridor').distinct().count()}")
    print(f"Minimum date: {bounds['minimum_date']}")
    print(f"Maximum date: {bounds['maximum_date']}")
    print(f"Null counts for important fields: {null_counts}")
    print(f"Distinct congestion classes: {congestion_classes}")
    print(f"Festival true/false counts: {festival_counts}")
    print(f"Holiday true/false counts: {holiday_counts}")

    if row_count != 8936:
        raise ValueError(f"Expected exactly 8,936 source rows; found {row_count}.")
    if traffic_data.select("corridor").distinct().count() != 16:
        raise ValueError("Expected exactly 16 distinct corridors.")


def write_csv(dataset: DataFrame, path: Path) -> None:
    """Write a small analytical result with stable headers on Windows."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=dataset.columns)
        writer.writeheader()
        for row in dataset.toLocalIterator():
            writer.writerow(row.asDict())


def report_output(name: str, dataset: DataFrame) -> None:
    """Print schema, row count, and sample rows for one result."""
    print(f"\nOUTPUT: {name}")
    print(f"Schema: {dataset.schema.simpleString()}")
    print(f"Row count: {dataset.count()}")
    dataset.show(5, truncate=False)


def run_analytics(spark: SparkSession) -> dict[str, DataFrame]:
    """Register the source view and execute every required SQL analysis."""
    traffic_data = load_traffic_data(spark)
    report_data_quality(traffic_data)
    traffic_data.createOrReplaceTempView("traffic_data")

    results = {
        name: spark.sql(query)
        for name, query in ANALYSIS_QUERIES.items()
    }
    if results["corridor_congestion_summary"].count() != 16:
        raise ValueError("Corridor summary must contain exactly 16 corridors.")
    return results


def main() -> None:
    """Run Phase 5 Spark SQL analytics and write all requested outputs."""
    spark = create_spark_session("SparkSQLTrafficAnalytics")
    try:
        results = run_analytics(spark)
        for name, dataset in results.items():
            report_output(name, dataset)
            write_csv(dataset, output_directory() / OUTPUT_FILES[name])
        print("\nGenerated output files:")
        for filename in OUTPUT_FILES.values():
            print(output_directory() / filename)
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
