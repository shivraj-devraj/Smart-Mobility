"""Generate transparent batch traffic advisories from historical records."""

import csv
from pathlib import Path

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql.functions import col, concat_ws, lit, when
from pyspark.sql.types import BooleanType, DateType, DoubleType

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
ADVISORY_COLUMNS = [
    "date",
    "corridor",
    "area",
    "road_intersection",
    "congestion_class",
    "festival_flag",
    "festival_name",
    "holiday_flag",
    "weather",
    "roadwork",
    "advisory_level",
    "recommendation",
    "personnel_action",
    "diversion_action",
    "roadwork_action",
    "context_notes",
]
EXPECTED_ROW_COUNT = 8936
VALID_ADVISORY_LEVELS = ["Normal", "Moderate", "High"]


def project_root() -> Path:
    """Return the project root based on this module's location."""
    return Path(__file__).resolve().parents[2]


def input_path() -> Path:
    return project_root() / "data" / "processed" / "integrated_traffic_data.csv"


def advisory_output_path() -> Path:
    return project_root() / "data" / "output" / "advisory_output.csv"


def summary_output_path() -> Path:
    return project_root() / "data" / "output" / "advisory_summary.txt"


def load_integrated_data(spark: SparkSession) -> DataFrame:
    """Load the integrated batch data with explicit types for rule evaluation."""
    source = input_path()
    if not source.exists():
        raise FileNotFoundError(f"Integrated input not found: {source}")
    data = (
        spark.read.option("header", "true")
        .option("inferSchema", "true")
        .csv(str(source))
    )
    if data.columns != INPUT_COLUMNS:
        raise ValueError(f"Unexpected integrated columns: {data.columns}")
    data = data.withColumn("date", col("date").cast(DateType()))
    for column_name in ["traffic_volume", "average_speed", "travel_time_index", "congestion_level"]:
        data = data.withColumn(column_name, col(column_name).cast(DoubleType()))
    for column_name in ["festival_flag", "holiday_flag"]:
        data = data.withColumn(column_name, col(column_name).cast(BooleanType()))
    return data


def apply_congestion_rules(data: DataFrame) -> DataFrame:
    """Map each congestion class to one transparent advisory action set."""
    # These mappings are intentionally static so each historical row has one explainable outcome.
    advisory_level = (
        when(col("congestion_class") == "Low", "Normal")
        .when(col("congestion_class") == "Medium", "Moderate")
        .when(col("congestion_class") == "High", "High")
    )
    recommendation = (
        when(
            col("congestion_class") == "Low",
            "Normal traffic management; continue routine monitoring.",
        )
        .when(
            col("congestion_class") == "Medium",
            "Increase traffic monitoring and consider additional personnel at the affected corridor.",
        )
        .when(
            col("congestion_class") == "High",
            "Deploy additional traffic personnel and prepare diversion measures for the affected corridor.",
        )
    )
    personnel_action = (
        when(col("congestion_class") == "Low", "Routine traffic personnel")
        .when(col("congestion_class") == "Medium", "Consider additional traffic personnel")
        .when(col("congestion_class") == "High", "Additional traffic personnel recommended")
    )
    diversion_action = (
        when(col("congestion_class") == "Low", "No special diversion recommended")
        .when(col("congestion_class") == "Medium", "Consider diversion planning if congestion persists")
        .when(col("congestion_class") == "High", "Prepare/activate suitable diversion planning")
    )
    roadwork_action = (
        when(col("congestion_class") == "Low", "No special roadwork restriction recommended")
        .when(col("congestion_class") == "Medium", "Review non-essential roadwork scheduling")
        .when(
            col("congestion_class") == "High",
            "Suspend or reschedule non-essential roadwork where operationally appropriate",
        )
    )
    return data.withColumns(
        {
            "advisory_level": advisory_level,
            "recommendation": recommendation,
            "personnel_action": personnel_action,
            "diversion_action": diversion_action,
            "roadwork_action": roadwork_action,
        }
    )


def add_context_notes(data: DataFrame) -> DataFrame:
    """Append only context statements supported by the row's historical fields."""
    context_notes = concat_ws(
        "; ",
        when(
            col("festival_flag") == True,
            "Festival-related traffic conditions detected; strengthen traffic management preparedness.",
        ),
        when(
            col("holiday_flag") == True,
            "Holiday-related traffic conditions detected; review expected travel demand.",
        ),
        when(
            col("roadwork") == "Yes",
            "Roadwork is present; review whether it can be postponed during high-congestion periods.",
        ),
        when(
            col("weather").isin("Rain", "Fog"),
            "Adverse weather is present; consider additional caution and traffic monitoring.",
        ),
    )
    return data.withColumn("context_notes", context_notes)


def build_advisories(data: DataFrame) -> DataFrame:
    """Apply congestion rules, then add contextual notes without changing row cardinality."""
    return add_context_notes(apply_congestion_rules(data)).select(ADVISORY_COLUMNS)


def write_csv(dataset: DataFrame, path: Path) -> None:
    """Write the advisory result with stable columns without Hadoop output writers."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=ADVISORY_COLUMNS)
        writer.writeheader()
        for row in dataset.toLocalIterator():
            values = row.asDict()
            if values["date"] is not None:
                values["date"] = values["date"].isoformat()
            writer.writerow(values)


def validate_advisories(input_data: DataFrame, advisories: DataFrame) -> dict[str, object]:
    """Run row, mapping, uniqueness, and context-specific validation checks."""
    input_rows = input_data.count()
    output_rows = advisories.count()
    duplicate_keys = (
        advisories.groupBy("date", "corridor")
        .count()
        .where(col("count") > 1)
        .count()
    )
    invalid_levels = advisories.where(~col("advisory_level").isin(VALID_ADVISORY_LEVELS)).count()
    class_level_pairs = advisories.select("congestion_class", "advisory_level").distinct().count()
    class_count = advisories.select("congestion_class").distinct().count()
    null_congestion = advisories.where(col("congestion_class").isNull()).count()
    festival_context_errors = advisories.where(
        (col("festival_flag") == True)
        != col("context_notes").contains("Festival-related traffic conditions detected")
    ).count()
    holiday_context_errors = advisories.where(
        (col("holiday_flag") == True)
        != col("context_notes").contains("Holiday-related traffic conditions detected")
    ).count()
    roadwork_context_errors = advisories.where(
        (col("roadwork") == "Yes")
        != col("context_notes").contains("Roadwork is present")
    ).count()
    weather_context_errors = advisories.where(
        col("weather").isin("Rain", "Fog")
        != col("context_notes").contains("Adverse weather is present")
    ).count()
    unsupported_field_check = set(advisories.columns) == set(ADVISORY_COLUMNS)
    checks = {
        "input_row_count_equals_output_row_count": input_rows == output_rows,
        "duplicate_date_corridor_count": duplicate_keys == 0,
        "null_congestion_class_count": null_congestion == 0,
        "valid_advisory_levels": invalid_levels == 0,
        "one_level_per_congestion_class": class_level_pairs == class_count,
        "festival_context_rule": festival_context_errors == 0,
        "holiday_context_rule": holiday_context_errors == 0,
        "roadwork_context_rule": roadwork_context_errors == 0,
        "adverse_weather_context_rule": weather_context_errors == 0,
        "no_unsupported_output_fields": unsupported_field_check,
        "output_file_exists": advisory_output_path().is_file(),
    }
    if not all(checks.values()):
        raise ValueError(f"Advisory validation failed: {checks}")
    return {
        "input_rows": input_rows,
        "output_rows": output_rows,
        "duplicate_date_corridor_count": duplicate_keys,
        "null_congestion_class_count": null_congestion,
        "festival_context_errors": festival_context_errors,
        "holiday_context_errors": holiday_context_errors,
        "roadwork_context_errors": roadwork_context_errors,
        "adverse_weather_context_errors": weather_context_errors,
        "checks": checks,
    }


def distribution(data: DataFrame, column_name: str) -> dict[str, int]:
    """Return a stable count distribution for a categorical advisory field."""
    return {
        str(row[column_name]): row["count"]
        for row in data.groupBy(column_name).count().orderBy(column_name).collect()
    }


def build_summary(
    advisories: DataFrame,
    validation: dict[str, object],
) -> str:
    """Create the requested summary of advisory and context distributions."""
    context_counts = {
        "festival_related": advisories.where(col("festival_flag") == True).count(),
        "holiday_related": advisories.where(col("holiday_flag") == True).count(),
        "roadwork_related": advisories.where(col("roadwork") == "Yes").count(),
        "adverse_weather_related": advisories.where(col("weather").isin("Rain", "Fog")).count(),
    }
    lines = [
        "PHASE 7A - RULE-BASED TRAFFIC ADVISORY ENGINE",
        "===============================================",
        "",
        f"Input dataset: {input_path()}",
        f"Output dataset: {advisory_output_path()}",
        f"Total advisory records: {validation['output_rows']}",
        "",
        f"Advisory level distribution: {distribution(advisories, 'advisory_level')}",
        f"Congestion class distribution: {distribution(advisories, 'congestion_class')}",
        f"Festival-related advisories: {context_counts['festival_related']}",
        f"Holiday-related advisories: {context_counts['holiday_related']}",
        f"Roadwork-related advisories: {context_counts['roadwork_related']}",
        f"Adverse-weather advisories: {context_counts['adverse_weather_related']}",
        "",
        "Validation results:",
    ]
    lines.extend(f"- {name}: {'PASS' if result else 'FAIL'}" for name, result in validation["checks"].items())
    lines.extend(
        [
            "",
            "Scope: deterministic batch historical advisories only.",
            "The engine recommends, considers, prepares, or reviews actions; it does not control traffic infrastructure.",
            "No live traffic, signal events, FASTag/toll integration, direction, GPS, or hour-level values were invented.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    """Generate and validate one advisory record per integrated traffic row."""
    spark = create_spark_session("RuleBasedTrafficAdvisory")
    try:
        input_data = load_integrated_data(spark)
        advisories = build_advisories(input_data)
        write_csv(advisories, advisory_output_path())
        validation = validate_advisories(input_data, advisories)
        summary = build_summary(advisories, validation)
        summary_output_path().parent.mkdir(parents=True, exist_ok=True)
        summary_output_path().write_text(summary, encoding="utf-8")

        print("PHASE 7A ADVISORY SUMMARY")
        print("-------------------------")
        print("Execution succeeded: True")
        print(f"Input row count: {validation['input_rows']}")
        print(f"Output row count: {validation['output_rows']}")
        print(f"Advisory-level distribution: {distribution(advisories, 'advisory_level')}")
        print(f"Congestion-class distribution: {distribution(advisories, 'congestion_class')}")
        print(f"Festival-related advisories: {advisories.where(col('festival_flag') == True).count()}")
        print(f"Holiday-related advisories: {advisories.where(col('holiday_flag') == True).count()}")
        print(f"Roadwork-related advisories: {advisories.where(col('roadwork') == 'Yes').count()}")
        print(
            "Adverse-weather advisories: "
            f"{advisories.where(col('weather').isin('Rain', 'Fog')).count()}"
        )
        print("Validation results: all checks PASS")
        print(f"Advisory output: {advisory_output_path()}")
        print(f"Summary output: {summary_output_path()}")
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
