"""Load the unchanged public Bengaluru traffic CSV with PySpark."""

import csv
from pathlib import Path

from pyspark.sql import DataFrame
from pyspark.sql import SparkSession
from pyspark.sql.types import DateType, DoubleType, StringType, StructField, StructType

from src.spark_session import create_spark_session

REAL_DATASET_COLUMNS = [
    "Date",
    "Area Name",
    "Road/Intersection Name",
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
    "Weather Conditions",
    "Roadwork and Construction Activity",
]

REAL_DATASET_SCHEMA = StructType(
    [
        StructField("Date", DateType(), True),
        StructField("Area Name", StringType(), True),
        StructField("Road/Intersection Name", StringType(), True),
        StructField("Traffic Volume", DoubleType(), True),
        StructField("Average Speed", DoubleType(), True),
        StructField("Travel Time Index", DoubleType(), True),
        StructField("Congestion Level", DoubleType(), True),
        StructField("Road Capacity Utilization", DoubleType(), True),
        StructField("Incident Reports", DoubleType(), True),
        StructField("Environmental Impact", DoubleType(), True),
        StructField("Public Transport Usage", DoubleType(), True),
        StructField("Traffic Signal Compliance", DoubleType(), True),
        StructField("Parking Usage", DoubleType(), True),
        StructField("Pedestrian and Cyclist Count", DoubleType(), True),
        StructField("Weather Conditions", StringType(), True),
        StructField("Roadwork and Construction Activity", StringType(), True),
    ]
)


def real_dataset_path() -> Path:
    """Return the required path without modifying the raw file."""
    project_root = Path(__file__).resolve().parents[2]
    return project_root / "data" / "raw" / "real" / "Banglore_traffic_Dataset.csv"


def read_real_dataset_header(path: Path) -> list[str]:
    """Read only the raw header so its names can be checked before Spark loading."""
    with path.open("r", newline="", encoding="utf-8-sig") as input_file:
        return next(csv.reader(input_file), [])


def load_real_traffic_data(spark: SparkSession, path: Path | None = None) -> DataFrame:
    """Load the real CSV using its exact header and an explicit Spark schema."""
    dataset_path = path or real_dataset_path()
    if not dataset_path.exists():
        raise FileNotFoundError(
            f"Real dataset not found at {dataset_path}. "
            "Place Banglore_traffic_Dataset.csv in data/raw/real/."
        )
    actual_columns = read_real_dataset_header(dataset_path)
    if actual_columns != REAL_DATASET_COLUMNS:
        raise ValueError(
            "Real dataset columns do not match the expected source header. "
            f"Expected {REAL_DATASET_COLUMNS}; found {actual_columns}."
        )

    return (
        spark.read
        .option("header", "true")
        .option("dateFormat", "yyyy-MM-dd")
        .schema(REAL_DATASET_SCHEMA)
        .csv(str(dataset_path))
    )


def main() -> None:
    """Load and display a small diagnostic summary of the real raw dataset."""
    spark = create_spark_session("LoadRealBengaluruTrafficData")
    try:
        dataset = load_real_traffic_data(spark)
        print(f"Spark version: {spark.version}")
        print(f"Row count: {dataset.count()}")
        print("Schema:")
        dataset.printSchema()
        print("First 5 rows:")
        dataset.show(5, truncate=False)
    finally:
        spark.stop()


if __name__ == "__main__":
    main()