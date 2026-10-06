"""Inspect Phase 4 features before any MLlib training or splitting."""

from pathlib import Path

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql.functions import col, count, lit, min as spark_min, max as spark_max
from pyspark.sql.types import BooleanType, DateType, DoubleType, IntegerType

from src.spark_session import create_spark_session

TARGET_COLUMN = "congestion_class"
TARGET_CLASSES = ["Low", "Medium", "High"]
EXPECTED_ROW_COUNT = 8936

NUMERIC_CANDIDATES = [
    "traffic_volume",
    "average_speed",
    "travel_time_index",
    "congestion_level",
    "road_capacity_utilization",
    "incident_reports",
    "environmental_impact",
    "public_transport_usage",
    "traffic_signal_compliance",
    "parking_usage",
    "pedestrian_and_cyclist_count",
]
CATEGORICAL_CANDIDATES = [
    "corridor",
    "area",
    "road_intersection",
    "weather",
    "roadwork",
    "day_type",
]
TEMPORAL_CANDIDATES = ["day_of_week", "festival_flag", "holiday_flag"]
CATEGORICAL_CARDINALITY_COLUMNS = [
    "corridor",
    "area",
    "road_intersection",
    "weather",
    "roadwork",
    "day_type",
]

PROPOSED_FEATURES = [
    "traffic_volume",
    "average_speed",
    "travel_time_index",
    "corridor",
    "area",
    "road_intersection",
    "weather",
    "roadwork",
    "day_of_week",
    "day_type",
    "festival_flag",
    "holiday_flag",
]
EXCLUDED_FEATURES = {
    "congestion_level": "Target leakage: congestion_class was derived directly from this field during preprocessing.",
    "congestion_class": "The target itself; it must never be an input feature.",
    "festival_name": "Excluded from the initial set because it is a sparse calendar label and duplicates the festival indicator semantics; revisit only with a documented encoding decision.",
    "date": "Excluded as a raw identifier; derive temporal features deliberately instead of using the date string.",
}
UNAVAILABLE_FEATURES = [
    "road_capacity_utilization",
    "incident_reports",
    "environmental_impact",
    "public_transport_usage",
    "traffic_signal_compliance",
    "parking_usage",
    "pedestrian_and_cyclist_count",
    "hour",
    "direction",
    "GPS coordinates",
    "live traffic features",
    "FASTag features",
    "signal-event features",
]


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def input_path() -> Path:
    return project_root() / "data" / "processed" / "integrated_traffic_data.csv"


def report_path() -> Path:
    return project_root() / "data" / "output" / "ml_feature_inspection.txt"


def load_dataset(spark: SparkSession) -> DataFrame:
    """Load the integrated data and enforce types needed for inspection."""
    source = input_path()
    if not source.exists():
        raise FileNotFoundError(f"Integrated input not found: {source}")
    data = (
        spark.read.option("header", "true")
        .option("inferSchema", "true")
        .csv(str(source))
    )
    data = data.withColumn("date", col("date").cast(DateType()))
    for column_name in [
        "traffic_volume",
        "average_speed",
        "travel_time_index",
        "congestion_level",
    ]:
        data = data.withColumn(column_name, col(column_name).cast(DoubleType()))
    data = data.withColumn("day_of_week", col("day_of_week").cast(IntegerType()))
    data = data.withColumn("festival_flag", col("festival_flag").cast(BooleanType()))
    data = data.withColumn("holiday_flag", col("holiday_flag").cast(BooleanType()))
    return data


def inspect_dataset(data: DataFrame) -> dict[str, object]:
    """Collect inspection facts without fitting any MLlib estimator."""
    actual_columns = data.columns
    available_numeric = [name for name in NUMERIC_CANDIDATES if name in actual_columns]
    available_categorical = [name for name in CATEGORICAL_CANDIDATES if name in actual_columns]
    available_temporal = [name for name in TEMPORAL_CANDIDATES if name in actual_columns]
    available_candidates = [
        *available_numeric,
        *available_categorical,
        *available_temporal,
    ]
    target_values = [
        row[TARGET_COLUMN]
        for row in data.select(TARGET_COLUMN).distinct().orderBy(TARGET_COLUMN).collect()
    ]
    target_counts = {
        row[TARGET_COLUMN]: row["count"]
        for row in data.groupBy(TARGET_COLUMN).count().orderBy(TARGET_COLUMN).collect()
    }
    null_counts = {
        name: data.filter(col(name).isNull()).count()
        for name in actual_columns
    }
    categorical_cardinalities = {
        name: data.select(name).distinct().count()
        for name in CATEGORICAL_CARDINALITY_COLUMNS
        if name in actual_columns
    }
    numeric_summary = data.select(available_numeric).summary(
        "count", "mean", "stddev", "min", "max"
    ).collect()
    class_balance = {
        class_name: {
            "count": target_counts.get(class_name, 0),
            "percentage": 100.0 * target_counts.get(class_name, 0) / data.count(),
        }
        for class_name in TARGET_CLASSES
    }
    return {
        "actual_columns": actual_columns,
        "schema": data.schema.simpleString(),
        "available_numeric": available_numeric,
        "available_categorical": available_categorical,
        "available_temporal": available_temporal,
        "available_candidates": available_candidates,
        "target_values": target_values,
        "target_counts": target_counts,
        "null_counts": null_counts,
        "categorical_cardinalities": categorical_cardinalities,
        "numeric_summary": numeric_summary,
        "class_balance": class_balance,
        "row_count": data.count(),
        "minimum_date": data.select(spark_min("date")).first()[0],
        "maximum_date": data.select(spark_max("date")).first()[0],
    }


def format_numeric_summary(rows: list[object]) -> list[str]:
    lines = []
    for row in rows:
        lines.append(", ".join(f"{field}={row[field]}" for field in row.__fields__))
    return lines


def build_report(facts: dict[str, object]) -> str:
    """Build the text report required for this preparation-only phase."""
    balance = facts["class_balance"]
    lines = [
        "PHASE 6A - ML FEATURE INSPECTION AND PREPARATION",
        "=================================================",
        "",
        "Scope: inspection and preprocessing design only.",
        "No MLlib estimator was fit, no split was created, and no predictions or evaluation were performed.",
        "",
        "DATASET",
        "-------",
        f"Source: {input_path()}",
        f"Rows: {facts['row_count']}",
        f"Date range: {facts['minimum_date']} to {facts['maximum_date']}",
        f"Schema columns: {facts['actual_columns']}",
        f"Spark schema: {facts['schema']}",
        "",
        "TARGET DISTRIBUTION",
        "------------------",
        f"Target column: {TARGET_COLUMN}",
        f"Distinct target classes: {facts['target_values']}",
    ]
    for class_name in TARGET_CLASSES:
        lines.append(
            f"{class_name}: count={balance[class_name]['count']}, "
            f"percentage={balance[class_name]['percentage']:.4f}%"
        )
    lines.extend(
        [
            "",
            "AVAILABLE FEATURES",
            "------------------",
            f"Numeric: {facts['available_numeric']}",
            f"Categorical: {facts['available_categorical']}",
            f"Temporal/derived: {facts['available_temporal']}",
            "",
            "EXCLUDED FEATURES AND LEAKAGE ANALYSIS",
            "--------------------------------------",
        ]
    )
    lines.extend(f"{name}: {reason}" for name, reason in EXCLUDED_FEATURES.items())
    lines.extend(
        [
            "",
            "The target congestion_class was created from congestion_level during preprocessing.",
            "Using congestion_level would expose the rule used to create the target and cause direct target leakage.",
            "The default model feature set therefore excludes congestion_level.",
            "No other available field was identified as a direct representation of congestion_class.",
            "",
            "CATEGORICAL CARDINALITIES",
            "-------------------------",
        ]
    )
    lines.extend(
        f"{name}: {count} distinct values"
        for name, count in facts["categorical_cardinalities"].items()
    )
    lines.extend(["", "NULL COUNTS", "-----------"])
    lines.extend(f"{name}: {count}" for name, count in facts["null_counts"].items())
    lines.extend(
        [
            "",
            "NUMERIC SUMMARIES (ALL AVAILABLE NUMERIC FIELDS)",
            "------------------------------------------------",
            "congestion_level is shown for inspection but remains excluded from the proposed model feature set.",
        ]
    )
    lines.extend(format_numeric_summary(facts["numeric_summary"]))
    lines.extend(
        [
            "",
            "PROPOSED INITIAL FEATURE SET",
            "----------------------------",
            f"{PROPOSED_FEATURES}",
            "",
            "UNAVAILABLE FEATURES",
            "--------------------",
            *[f"- {name}" for name in UNAVAILABLE_FEATURES],
            "",
            "PROPOSED SPARK MLLIB PREPROCESSING",
            "----------------------------------",
            "1. StringIndexer for categorical features with handleInvalid='keep'.",
            "2. OneHotEncoder for indexed categorical features.",
            "3. VectorAssembler for encoded categorical, numeric, and temporal/boolean feature columns.",
            "4. StringIndexer for congestion_class as the eventual label.",
            "5. StandardScaler may be considered for scale-sensitive estimators; defer the choice until model selection.",
            "No pipeline is fitted or saved in Phase 6A.",
            "",
            "RECOMMENDED SPLIT STRATEGY",
            "--------------------------",
            "Use a chronological split for the historical batch dataset: earlier dates for training and later dates for testing.",
            "This better represents forecasting future traffic and avoids allowing later observations to inform the past.",
            "A random split may be used only as a secondary sensitivity check because records are date-correlated and corridor-repeated.",
        ]
    )
    return "\n".join(lines) + "\n"


def print_inspection(facts: dict[str, object]) -> None:
    print(build_report(facts))
    print("DATASET SCHEMA")
    print("--------------")
    print(facts["schema"])
    print("Target counts:", facts["target_counts"])
    print("Categorical cardinalities:", facts["categorical_cardinalities"])
    print("Numeric summary:")
    for line in format_numeric_summary(facts["numeric_summary"]):
        print(line)


def main() -> None:
    """Inspect ML candidates and write the preparation design report."""
    spark = create_spark_session("MLFeatureInspection")
    try:
        data = load_dataset(spark)
        facts = inspect_dataset(data)
        if facts["target_values"] != sorted(TARGET_CLASSES):
            raise ValueError(
                f"Expected target classes {sorted(TARGET_CLASSES)}; found {facts['target_values']}"
            )
        if facts["row_count"] != EXPECTED_ROW_COUNT:
            raise ValueError(
                f"Expected exactly {EXPECTED_ROW_COUNT} rows; found {facts['row_count']}"
            )
        print_inspection(facts)
        destination = report_path()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(build_report(facts), encoding="utf-8")
        print(f"Inspection report: {destination}")
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
