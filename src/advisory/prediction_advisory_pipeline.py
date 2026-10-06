"""Run Phase 7B: chronological ML prediction followed by rule-based advisories."""

import csv
import hashlib
import json
from pathlib import Path

from pyspark.ml import Pipeline
from pyspark.ml.classification import DecisionTreeClassifier
from pyspark.ml.evaluation import MulticlassClassificationEvaluator
from pyspark.ml.feature import OneHotEncoder, StringIndexer, VectorAssembler
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql.functions import col, lit, when
from pyspark.sql.types import BooleanType, DateType, DoubleType, IntegerType

from src.advisory.advisory_engine import add_context_notes, apply_congestion_rules
from src.spark_session import create_spark_session

INPUT_COLUMNS = [
    "date", "area", "road_intersection", "corridor", "traffic_volume",
    "average_speed", "travel_time_index", "congestion_level", "congestion_class",
    "weather", "roadwork", "day_of_week", "day_type", "festival_flag",
    "festival_name", "holiday_flag",
]
NUMERIC_FEATURES = ["traffic_volume", "average_speed", "travel_time_index", "day_of_week"]
CATEGORICAL_FEATURES = ["corridor", "area", "road_intersection", "weather", "roadwork", "day_type"]
BOOLEAN_FEATURES = ["festival_flag", "holiday_flag"]
FEATURE_COLUMNS = [*NUMERIC_FEATURES, *CATEGORICAL_FEATURES, *BOOLEAN_FEATURES]
TARGET_CLASSES = {"Low", "Medium", "High"}
EXPECTED_INPUT_ROWS = 8936
EXPECTED_TEST_ROWS = 1791
EXPECTED_CUTOFF = "2024-01-31"
MODEL_SPECIFICATION_PATH = "models/decision_tree_baseline/model_specification.json"
OUTPUT_COLUMNS = [
    "date", "corridor", "area", "road_intersection", "actual_congestion_class",
    "predicted_congestion_class", "festival_flag", "festival_name", "holiday_flag",
    "weather", "roadwork", "advisory_level", "recommendation", "personnel_action",
    "diversion_action", "roadwork_action", "context_notes",
]
VALID_LEVELS = ["Normal", "Moderate", "High"]


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def input_path() -> Path:
    return project_root() / "data" / "processed" / "integrated_traffic_data.csv"


def specification_path() -> Path:
    return project_root() / MODEL_SPECIFICATION_PATH


def output_path() -> Path:
    return project_root() / "data" / "output" / "prediction_advisory_output.csv"


def summary_path() -> Path:
    return project_root() / "data" / "output" / "prediction_advisory_summary.txt"


def load_specification() -> dict[str, object]:
    """Load the reproducible Phase 6B artifact; never treat it as PipelineModel data."""
    with specification_path().open("r", encoding="utf-8") as specification_file:
        specification = json.load(specification_file)
    if specification.get("native_spark_pipeline_model") is not False:
        raise ValueError("Phase 7B requires a non-native reproducible model specification.")
    return specification


def load_data(spark: SparkSession) -> DataFrame:
    source = input_path()
    if not source.exists():
        raise FileNotFoundError(f"Integrated input not found: {source}")
    data = spark.read.option("header", "true").option("inferSchema", "true").csv(str(source))
    if data.columns != INPUT_COLUMNS:
        raise ValueError(f"Unexpected integrated columns: {data.columns}")
    data = data.withColumn("date", col("date").cast(DateType()))
    for name in ["traffic_volume", "average_speed", "travel_time_index"]:
        data = data.withColumn(name, col(name).cast(DoubleType()))
    data = data.withColumn("day_of_week", col("day_of_week").cast(IntegerType()))
    for name in BOOLEAN_FEATURES:
        data = data.withColumn(name, col(name).cast(BooleanType()))
    return data


def chronological_split(data: DataFrame, cutoff: str) -> tuple[DataFrame, DataFrame]:
    cutoff_date = cutoff
    training = data.where(col("date") <= lit(cutoff_date))
    testing = data.where(col("date") > lit(cutoff_date))
    return training, testing


def build_pipeline(specification: dict[str, object]) -> Pipeline:
    """Reconstruct Phase 6B preprocessing and classifier settings from the specification."""
    preprocessing = specification["preprocessing"]
    indexer_config = preprocessing["categorical_indexer"]
    indexers = [
        StringIndexer(
            inputCol=name,
            outputCol=f"{name}_index",
            handleInvalid=indexer_config["handleInvalid"],
            stringOrderType=indexer_config["stringOrderType"],
        )
        for name in CATEGORICAL_FEATURES
    ]
    indexed = [f"{name}_index" for name in CATEGORICAL_FEATURES]
    encoder = OneHotEncoder(
        inputCols=indexed,
        outputCols=[f"{name}_encoded" for name in CATEGORICAL_FEATURES],
        handleInvalid="keep",
    )
    target_config = preprocessing["target_indexer"]
    label_indexer = StringIndexer(
        inputCol="congestion_class",
        outputCol="label",
        handleInvalid=target_config["handleInvalid"],
        stringOrderType=target_config["stringOrderType"],
    )
    assembler = VectorAssembler(
        inputCols=specification["features"]["assembler_inputs"],
        outputCol="features",
        handleInvalid="error",
    )
    classifier_config = specification["classifier"]
    classifier = DecisionTreeClassifier(
        labelCol=classifier_config["labelCol"],
        featuresCol=classifier_config["featuresCol"],
        predictionCol=classifier_config["predictionCol"],
        seed=classifier_config["seed"],
        maxDepth=classifier_config["maxDepth"],
    )
    return Pipeline(stages=[*indexers, encoder, label_indexer, assembler, classifier])


def validate_specification(data: DataFrame, specification: dict[str, object]) -> None:
    """Ensure the current input and reconstructed configuration match Phase 6B."""
    if hashlib.sha256(input_path().read_bytes()).hexdigest() != specification["training"]["input_sha256"]:
        raise ValueError("Integrated input fingerprint differs from the Phase 6B specification.")
    if specification["training"]["cutoff_date"] != EXPECTED_CUTOFF:
        raise ValueError("Unexpected Phase 6B cutoff in model specification.")
    if data.count() != EXPECTED_INPUT_ROWS:
        raise ValueError("Unexpected integrated input row count.")
    if set(row["congestion_class"] for row in data.select("congestion_class").distinct().collect()) != TARGET_CLASSES:
        raise ValueError("Actual target classes are not exactly Low, Medium, and High.")


def decode_predictions(predictions: DataFrame, labels: list[str]) -> DataFrame:
    predicted = lit(None).cast("string")
    actual = lit(None).cast("string")
    for index, class_name in enumerate(labels):
        predicted = when(col("prediction") == float(index), class_name).otherwise(predicted)
        actual = when(col("label") == float(index), class_name).otherwise(actual)
    return predictions.withColumn("predicted_congestion_class", predicted).withColumn(
        "actual_congestion_class", actual
    )


def generate_predicted_advisories(predictions: DataFrame) -> DataFrame:
    """Generate advisories from a prediction-only congestion column."""
    prediction_input = predictions.select(
        "date", "corridor", "area", "road_intersection",
        col("predicted_congestion_class").alias("congestion_class"),
        "festival_flag", "festival_name", "holiday_flag", "weather", "roadwork",
    )
    # The actual target is deliberately absent from this DataFrame before rules run.
    advised = add_context_notes(apply_congestion_rules(prediction_input))
    return predictions.select(
        "date", "corridor", "area", "road_intersection", "actual_congestion_class",
        "predicted_congestion_class", "festival_flag", "festival_name", "holiday_flag",
        "weather", "roadwork",
    ).join(
        advised.select(
            "date", "corridor", "advisory_level", "recommendation", "personnel_action",
            "diversion_action", "roadwork_action", "context_notes",
        ),
        ["date", "corridor"],
        "left",
    ).select(OUTPUT_COLUMNS)


def distribution(data: DataFrame, column: str) -> dict[str, int]:
    return {str(row[column]): row["count"] for row in data.groupBy(column).count().orderBy(column).collect()}


def confusion_matrix(predictions: DataFrame) -> list[dict[str, object]]:
    return [
        row.asDict()
        for row in predictions.groupBy("actual_congestion_class", "predicted_congestion_class")
        .count().orderBy("actual_congestion_class", "predicted_congestion_class").collect()
    ]


def evaluate(predictions: DataFrame) -> dict[str, float]:
    metrics = {}
    for name, metric_name in [
        ("accuracy", "accuracy"),
        ("weighted_precision", "weightedPrecision"),
        ("weighted_recall", "weightedRecall"),
        ("f1", "f1"),
    ]:
        metrics[name] = MulticlassClassificationEvaluator(
            labelCol="label", predictionCol="prediction", metricName=metric_name
        ).evaluate(predictions)
    return metrics


def write_csv(data: DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        for row in data.toLocalIterator():
            values = row.asDict()
            values["date"] = values["date"].isoformat()
            writer.writerow(values)


def validate(
    data: DataFrame,
    testing: DataFrame,
    predictions: DataFrame,
    advisories: DataFrame,
    metrics: dict[str, float],
) -> dict[str, bool]:
    """Validate prediction coverage and ensure advisory generation uses predictions."""
    testing_range = testing.selectExpr("MIN(date) AS min_date", "MAX(date) AS max_date").first()
    checks = {
        "test_input_rows_equal_prediction_output_rows": testing.count() == predictions.count() == EXPECTED_TEST_ROWS,
        "actual_and_predicted_columns_present": {"actual_congestion_class", "predicted_congestion_class"}.issubset(predictions.columns),
        "actual_and_predicted_values_supported": predictions.where(
            ~col("actual_congestion_class").isin("Low", "Medium", "High")
            | ~col("predicted_congestion_class").isin("Low", "Medium", "High")
        ).count() == 0,
        "advisory_uses_predicted_class_only": "congestion_class" not in advisories.columns and "actual_congestion_class" in advisories.columns,
        "duplicate_date_corridor_count_zero": advisories.groupBy("date", "corridor").count().where(col("count") > 1).count() == 0,
        "null_predicted_class_count_zero": advisories.where(col("predicted_congestion_class").isNull()).count() == 0,
        "null_advisory_level_count_zero": advisories.where(col("advisory_level").isNull()).count() == 0,
        "advisory_levels_supported": advisories.where(~col("advisory_level").isin(VALID_LEVELS)).count() == 0,
        "test_period_exact": str(testing_range["min_date"]) == "2024-02-01"
        and str(testing_range["max_date"]) == "2024-08-09",
        "metrics_match_phase_6b": all(abs(metrics[name] - expected) < 1e-6 for name, expected in {
            "accuracy": 0.919040, "weighted_precision": 0.919577,
            "weighted_recall": 0.919040, "f1": 0.919270,
        }.items()),
        "output_file_exists": output_path().is_file(),
    }
    if not all(checks.values()):
        raise ValueError(f"Phase 7B validation failed: {checks}")
    return checks


def build_summary(
    specification: dict[str, object], training: DataFrame, testing: DataFrame,
    predictions: DataFrame, advisories: DataFrame, metrics: dict[str, float], checks: dict[str, bool],
) -> str:
    training_range = training.selectExpr("MIN(date) AS min_date", "MAX(date) AS max_date").first()
    testing_range = testing.selectExpr("MIN(date) AS min_date", "MAX(date) AS max_date").first()
    matrix = confusion_matrix(predictions)
    lines = [
        "PHASE 7B - PREDICTION TO ADVISORY",
        "=================================", "",
        f"Input dataset: {input_path()}",
        f"Training date range: {training_range['min_date']} to {training_range['max_date']}",
        f"Testing date range: {testing_range['min_date']} to {testing_range['max_date']}",
        f"Training rows: {training.count()}", f"Testing rows: {testing.count()}", "",
        "Model: Decision Tree",
        f"Feature list: {FEATURE_COLUMNS}",
        "Chronological split: first 80% of distinct dates for training",
        f"Model specification path: {specification_path()}", "",
        "Prediction distribution:",
    ]
    lines.extend(f"- {name}: {distribution(predictions, 'predicted_congestion_class').get(name, 0)}" for name in ["Low", "Medium", "High"])
    lines.extend([
        "", "Evaluation:",
        f"Accuracy: {metrics['accuracy']:.6f}",
        f"Weighted Precision: {metrics['weighted_precision']:.6f}",
        f"Weighted Recall: {metrics['weighted_recall']:.6f}",
        f"F1: {metrics['f1']:.6f}",
        "", "Confusion Matrix:", "actual_congestion_class,predicted_congestion_class,count",
    ])
    lines.extend(f"{row['actual_congestion_class']},{row['predicted_congestion_class']},{row['count']}" for row in matrix)
    lines.extend([
        "", "Advisory distribution:",
    ])
    lines.extend(f"- {name}: {distribution(advisories, 'advisory_level').get(name, 0)}" for name in VALID_LEVELS)
    lines.extend([
        "", "Context counts:",
        f"- Festival: {advisories.where(col('festival_flag') == True).count()}",
        f"- Holiday: {advisories.where(col('holiday_flag') == True).count()}",
        f"- Roadwork: {advisories.where(col('roadwork') == 'Yes').count()}",
        f"- Adverse weather: {advisories.where(col('weather').isin('Rain', 'Fog')).count()}",
        "", "Validation:",
    ])
    lines.extend(f"- {name}: {'PASS' if result else 'FAIL'}" for name, result in checks.items())
    return "\n".join(lines) + "\n"


def main() -> None:
    spark = create_spark_session("PredictionToAdvisory")
    try:
        specification = load_specification()
        data = load_data(spark)
        validate_specification(data, specification)
        training, testing = chronological_split(data, specification["training"]["cutoff_date"])
        pipeline_model = build_pipeline(specification).fit(training)
        labels = list(pipeline_model.stages[len(CATEGORICAL_FEATURES) + 1].labels)
        expected_labels = specification["preprocessing"]["target_indexer"]["labels"]
        if labels != expected_labels:
            raise ValueError(f"Target mapping differs from specification: {labels} != {expected_labels}")
        fitted_indexers = pipeline_model.stages[:len(CATEGORICAL_FEATURES)]
        expected_feature_labels = specification["preprocessing"]["categorical_indexer"]["labels"]
        for name, fitted_indexer in zip(CATEGORICAL_FEATURES, fitted_indexers):
            if list(fitted_indexer.labels) != expected_feature_labels[name]:
                raise ValueError(f"Indexer mapping differs from specification for {name}.")
        fitted_encoder = pipeline_model.stages[len(CATEGORICAL_FEATURES)]
        if list(fitted_encoder.categorySizes) != specification["preprocessing"]["one_hot_encoder"]["categorySizes"]:
            raise ValueError("One-hot category sizes differ from the model specification.")
        predictions = decode_predictions(pipeline_model.transform(testing), labels)
        metrics = evaluate(predictions)
        advisories = generate_predicted_advisories(predictions)
        write_csv(advisories, output_path())
        checks = validate(data, testing, predictions, advisories, metrics)
        summary = build_summary(specification, training, testing, predictions, advisories, metrics, checks)
        summary_path().parent.mkdir(parents=True, exist_ok=True)
        summary_path().write_text(summary, encoding="utf-8")

        print("PHASE 7B PREDICTION TO ADVISORY")
        print("--------------------------------")
        print("Execution succeeded: True")
        print(f"Training rows: {training.count()}")
        print(f"Testing rows: {testing.count()}")
        print(f"Prediction distribution: {distribution(predictions, 'predicted_congestion_class')}")
        print("Confusion matrix:")
        for row in confusion_matrix(predictions):
            print(row)
        print(f"Metrics: {metrics}")
        print(f"Advisory distribution: {distribution(advisories, 'advisory_level')}")
        print("Validation results: all checks PASS")
        print(f"Output: {output_path()}")
        print(f"Summary: {summary_path()}")
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
