"""Train and evaluate the Phase 6B Spark MLlib Decision Tree baseline."""

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

from src.spark_session import create_spark_session

TARGET_COLUMN = "congestion_class"
TARGET_CLASSES = {"Low", "Medium", "High"}
EXPECTED_ROW_COUNT = 8936
NUMERIC_FEATURES = [
    "traffic_volume",
    "average_speed",
    "travel_time_index",
    "day_of_week",
]
CATEGORICAL_FEATURES = [
    "corridor",
    "area",
    "road_intersection",
    "weather",
    "roadwork",
    "day_type",
]
BOOLEAN_FEATURES = ["festival_flag", "holiday_flag"]
FEATURE_COLUMNS = [*NUMERIC_FEATURES, *CATEGORICAL_FEATURES, *BOOLEAN_FEATURES]
EXCLUDED_COLUMNS = {
    "congestion_level": "Excluded because congestion_class was directly derived from it; using it would cause target leakage.",
    "congestion_class": "The target column; it cannot be used as an input feature.",
    "festival_name": "Excluded because it is a sparse calendar label and is not part of the specified baseline feature set.",
    "date": "Excluded because raw dates are not used directly as features.",
}
MODEL_DIRECTORY = "models/decision_tree_baseline"


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def input_path() -> Path:
    return project_root() / "data" / "processed" / "integrated_traffic_data.csv"


def report_path() -> Path:
    return project_root() / "data" / "output" / "ml_baseline_evaluation.txt"


def model_path() -> Path:
    return project_root() / MODEL_DIRECTORY


def load_dataset(spark: SparkSession) -> DataFrame:
    """Load the integrated data and apply only explicit ML input typing."""
    source = input_path()
    if not source.exists():
        raise FileNotFoundError(f"Integrated input not found: {source}")
    data = (
        spark.read.option("header", "true")
        .option("inferSchema", "true")
        .csv(str(source))
    )
    expected_columns = [
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
    if data.columns != expected_columns:
        raise ValueError(f"Unexpected integrated columns: {data.columns}")

    data = data.withColumn("date", col("date").cast(DateType()))
    for column_name in ["traffic_volume", "average_speed", "travel_time_index"]:
        data = data.withColumn(column_name, col(column_name).cast(DoubleType()))
    data = data.withColumn("day_of_week", col("day_of_week").cast(IntegerType()))
    for column_name in BOOLEAN_FEATURES:
        data = data.withColumn(column_name, col(column_name).cast(BooleanType()))
    return data


def chronological_split(data: DataFrame) -> tuple[DataFrame, DataFrame, object]:
    """Use the first 80 percent of sorted distinct dates for training."""
    dates = [row["date"] for row in data.select("date").distinct().orderBy("date").collect()]
    if len(dates) < 2:
        raise ValueError("At least two distinct dates are required for a chronological split.")
    training_date_count = max(1, min(len(dates) - 1, int(len(dates) * 0.80)))
    cutoff_date = dates[training_date_count - 1]
    training = data.where(col("date") <= lit(cutoff_date))
    testing = data.where(col("date") > lit(cutoff_date))
    return training, testing, cutoff_date


def build_pipeline() -> Pipeline:
    """Build a leakage-safe Spark ML pipeline for the baseline classifier."""
    categorical_indexers = [
        StringIndexer(
            inputCol=column_name,
            outputCol=f"{column_name}_index",
            handleInvalid="keep",
            stringOrderType="alphabetAsc",
        )
        for column_name in CATEGORICAL_FEATURES
    ]
    categorical_index_columns = [f"{name}_index" for name in CATEGORICAL_FEATURES]
    encoder = OneHotEncoder(
        inputCols=categorical_index_columns,
        outputCols=[f"{name}_encoded" for name in CATEGORICAL_FEATURES],
        handleInvalid="keep",
    )
    label_indexer = StringIndexer(
        inputCol=TARGET_COLUMN,
        outputCol="label",
        handleInvalid="error",
        stringOrderType="alphabetAsc",
    )
    assembler_inputs = [
        *NUMERIC_FEATURES,
        *[f"{name}_encoded" for name in CATEGORICAL_FEATURES],
        *BOOLEAN_FEATURES,
    ]
    assembler = VectorAssembler(
        inputCols=assembler_inputs,
        outputCol="features",
        handleInvalid="error",
    )
    classifier = DecisionTreeClassifier(
        labelCol="label",
        featuresCol="features",
        predictionCol="prediction",
        seed=42,
        maxDepth=5,
    )
    return Pipeline(stages=[*categorical_indexers, encoder, label_indexer, assembler, classifier])


def class_distribution(data: DataFrame, total_rows: int) -> list[dict[str, object]]:
    """Return stable class counts and percentages for reporting."""
    counts = {
        row[TARGET_COLUMN]: row["count"]
        for row in data.groupBy(TARGET_COLUMN).count().collect()
    }
    return [
        {
            "class": class_name,
            "count": counts.get(class_name, 0),
            "percentage": 100.0 * counts.get(class_name, 0) / total_rows,
        }
        for class_name in ["Low", "Medium", "High"]
    ]


def add_class_names(predictions: DataFrame, labels: list[str]) -> DataFrame:
    """Decode numeric label and prediction values with Spark expressions."""
    actual_class = lit(None).cast("string")
    predicted_class = lit(None).cast("string")
    for index, class_name in enumerate(labels):
        actual_class = when(col("label") == lit(float(index)), lit(class_name)).otherwise(actual_class)
        predicted_class = when(col("prediction") == lit(float(index)), lit(class_name)).otherwise(predicted_class)
    return predictions.withColumn("actual_class", actual_class).withColumn(
        "predicted_class", predicted_class
    )


def confusion_matrix(predictions: DataFrame) -> list[dict[str, object]]:
    """Return an ordered, readable confusion matrix using DataFrame operations."""
    return [
        row.asDict()
        for row in predictions.groupBy("actual_class", "predicted_class")
        .count()
        .orderBy("actual_class", "predicted_class")
        .collect()
    ]


def validate_quality(
    data: DataFrame,
    training: DataFrame,
    testing: DataFrame,
    predictions: DataFrame,
    metrics: dict[str, float],
) -> dict[str, object]:
    """Enforce the Phase 6B split, feature, prediction, metric, and output checks."""
    total_rows = data.count()
    training_rows = training.count()
    testing_rows = testing.count()
    if training_rows + testing_rows != total_rows:
        raise ValueError("Training and testing rows do not sum to the input row count.")
    if data.filter(col(TARGET_COLUMN).isNull()).count():
        raise ValueError("Target contains null values.")
    null_counts = {
        column_name: data.filter(col(column_name).isNull()).count()
        for column_name in FEATURE_COLUMNS
    }
    if any(null_counts.values()):
        raise ValueError(f"Feature nulls found: {null_counts}")
    training_max = training.selectExpr("MAX(date) AS maximum_date").first()[0]
    testing_min = testing.selectExpr("MIN(date) AS minimum_date").first()[0]
    if training_max >= testing_min:
        raise ValueError("Training dates are not strictly earlier than testing dates.")
    if predictions.filter(col("actual_class").isNull() | col("predicted_class").isNull()).count():
        raise ValueError("Predictions do not contain both actual and predicted labels.")
    if any(value < 0.0 or value > 1.0 for value in metrics.values()):
        raise ValueError(f"Evaluation metrics must be between 0 and 1: {metrics}")
    return {"total_rows": total_rows, "null_counts": null_counts}


def save_model_specification(
    pipeline_model,
    destination: Path,
    labels: list[str],
    cutoff_date: object,
) -> Path:
    """Persist fitted preprocessing mappings and tree details without Hadoop JNI."""
    indexer_models = pipeline_model.stages[:len(CATEGORICAL_FEATURES)]
    encoder_model = pipeline_model.stages[len(CATEGORICAL_FEATURES)]
    classifier_model = pipeline_model.stages[-1]
    specification = {
        "artifact_type": "reproducible_spark_decision_tree_specification",
        "native_spark_pipeline_model": False,
        "model_class": "DecisionTreeClassifier",
        "classifier": {
            "maxDepth": classifier_model.getOrDefault(classifier_model.maxDepth),
            "seed": classifier_model.getOrDefault(classifier_model.seed),
            "labelCol": classifier_model.getOrDefault(classifier_model.labelCol),
            "featuresCol": classifier_model.getOrDefault(classifier_model.featuresCol),
            "predictionCol": classifier_model.getOrDefault(classifier_model.predictionCol),
            "numNodes": classifier_model.numNodes,
            "depth": classifier_model.depth,
            "tree": classifier_model.toDebugString,
        },
        "features": {
            "numeric": NUMERIC_FEATURES,
            "categorical": CATEGORICAL_FEATURES,
            "boolean": BOOLEAN_FEATURES,
            "assembler_inputs": [
                *NUMERIC_FEATURES,
                *[f"{name}_encoded" for name in CATEGORICAL_FEATURES],
                *BOOLEAN_FEATURES,
            ],
            "excluded": EXCLUDED_COLUMNS,
        },
        "preprocessing": {
            "categorical_indexer": {
                "handleInvalid": "keep",
                "stringOrderType": "alphabetAsc",
                "labels": {
                    name: indexer.labels
                    for name, indexer in zip(CATEGORICAL_FEATURES, indexer_models)
                },
            },
            "one_hot_encoder": {"categorySizes": encoder_model.categorySizes},
            "target_indexer": {
                "handleInvalid": "error",
                "stringOrderType": "alphabetAsc",
                "labels": labels,
            },
        },
        "training": {
            "cutoff_date": str(cutoff_date),
            "input_sha256": hashlib.sha256(input_path().read_bytes()).hexdigest(),
        },
    }
    destination.mkdir(parents=True, exist_ok=True)
    specification_path = destination / "model_specification.json"
    temporary_path = destination / "model_specification.json.tmp"
    temporary_path.write_text(json.dumps(specification, indent=2), encoding="utf-8")
    temporary_path.replace(specification_path)
    return specification_path


def build_report(
    data: DataFrame,
    training: DataFrame,
    testing: DataFrame,
    cutoff_date: object,
    labels: list[str],
    metrics: dict[str, float],
    matrix: list[dict[str, object]],
    quality: dict[str, object],
    specification_path: Path,
) -> str:
    """Build the required evaluation report."""
    training_range = training.selectExpr("MIN(date) AS minimum_date", "MAX(date) AS maximum_date").first()
    testing_range = testing.selectExpr("MIN(date) AS minimum_date", "MAX(date) AS maximum_date").first()
    lines = [
        "PHASE 6B - DECISION TREE BASELINE",
        "=================================",
        "",
        "Input dataset",
        f"{input_path()}",
        f"Total rows: {quality['total_rows']}",
        f"Training rows: {training.count()}",
        f"Testing rows: {testing.count()}",
        f"Training date range: {training_range['minimum_date']} to {training_range['maximum_date']}",
        f"Testing date range: {testing_range['minimum_date']} to {testing_range['maximum_date']}",
        f"Cutoff date: {cutoff_date}",
        "",
        f"Feature list: {FEATURE_COLUMNS}",
        "Excluded columns and reasons:",
    ]
    lines.extend(f"- {name}: {reason}" for name, reason in EXCLUDED_COLUMNS.items())
    lines.extend(
        [
            "",
            "Target label mapping:",
            *[f"- {class_name} = {index}" for index, class_name in enumerate(labels)],
            "",
            "Class distribution - training:",
        ]
    )
    lines.extend(
        f"- {item['class']}: count={item['count']}, percentage={item['percentage']:.4f}%"
        for item in class_distribution(training, training.count())
    )
    lines.append("Class distribution - testing:")
    lines.extend(
        f"- {item['class']}: count={item['count']}, percentage={item['percentage']:.4f}%"
        for item in class_distribution(testing, testing.count())
    )
    lines.extend(
        [
            "",
            f"Accuracy: {metrics['accuracy']:.6f}",
            f"Weighted Precision: {metrics['weighted_precision']:.6f}",
            f"Weighted Recall: {metrics['weighted_recall']:.6f}",
            f"F1 Score: {metrics['f1']:.6f}",
            "",
            "Confusion Matrix",
            "actual_class,predicted_class,count",
        ]
    )
    lines.extend(f"{row['actual_class']},{row['predicted_class']},{row['count']}" for row in matrix)
    lines.extend(
        [
            "",
            f"Native Spark PipelineModel: NOT CREATED (Windows Hadoop NativeIO/access0 limitation)",
            f"Reproducible model specification: {specification_path}",
            "Evaluation report: this file; it contains the metrics and confusion matrix below.",
            "",
            "Data quality checks:",
            f"- Training rows + testing rows = total rows: {training.count()} + {testing.count()} = {quality['total_rows']}",
            "- Target null count: 0",
            f"- Feature null counts: {quality['null_counts']}",
            "- Training dates strictly earlier than testing dates: PASS",
            "- Predictions contain actual and predicted labels: PASS",
            "- Evaluation metrics in [0, 1]: PASS",
            f"- Model specification exists: {'PASS' if specification_path.is_file() else 'FAIL'}",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    """Train, evaluate, save, and report the Decision Tree baseline."""
    spark = create_spark_session("DecisionTreeBaseline")
    try:
        data = load_dataset(spark)
        if data.count() != EXPECTED_ROW_COUNT:
            raise ValueError(f"Expected {EXPECTED_ROW_COUNT} rows; found {data.count()}")
        if set(row[TARGET_COLUMN] for row in data.select(TARGET_COLUMN).distinct().collect()) != TARGET_CLASSES:
            raise ValueError("Target classes are not exactly Low, Medium, and High.")

        training, testing, cutoff_date = chronological_split(data)
        pipeline = build_pipeline()
        pipeline_model = pipeline.fit(training)
        predictions = pipeline_model.transform(testing)

        labels = list(pipeline_model.stages[len(CATEGORICAL_FEATURES) + 1].labels)
        predictions = add_class_names(predictions, labels)
        evaluator = MulticlassClassificationEvaluator(
            labelCol="label",
            predictionCol="prediction",
            metricName="accuracy",
        )
        metrics = {
            "accuracy": evaluator.evaluate(predictions),
            "weighted_precision": MulticlassClassificationEvaluator(
                labelCol="label", predictionCol="prediction", metricName="weightedPrecision"
            ).evaluate(predictions),
            "weighted_recall": MulticlassClassificationEvaluator(
                labelCol="label", predictionCol="prediction", metricName="weightedRecall"
            ).evaluate(predictions),
            "f1": MulticlassClassificationEvaluator(
                labelCol="label", predictionCol="prediction", metricName="f1"
            ).evaluate(predictions),
        }
        matrix = confusion_matrix(predictions)
        quality = validate_quality(data, training, testing, predictions, metrics)
        specification_path = save_model_specification(
            pipeline_model,
            model_path(),
            labels,
            cutoff_date,
        )

        report = build_report(
            data,
            training,
            testing,
            cutoff_date,
            labels,
            metrics,
            matrix,
            quality,
            specification_path,
        )
        report_path().parent.mkdir(parents=True, exist_ok=True)
        report_path().write_text(report, encoding="utf-8")

        print("PHASE 6B TRAINING SUMMARY")
        print("-------------------------")
        print("Training succeeded: True")
        print(f"Total rows: {quality['total_rows']}")
        print(f"Training rows: {training.count()}")
        print(f"Testing rows: {testing.count()}")
        print(f"Cutoff date: {cutoff_date}")
        print(f"Training date range: {training.selectExpr('MIN(date)', 'MAX(date)').first()}")
        print(f"Testing date range: {testing.selectExpr('MIN(date)', 'MAX(date)').first()}")
        print(f"Label mapping: {dict(enumerate(labels))}")
        print(f"Training classes: {class_distribution(training, training.count())}")
        print(f"Testing classes: {class_distribution(testing, testing.count())}")
        for name, value in metrics.items():
            print(f"{name}: {value:.6f}")
        print("Confusion matrix:")
        for row in matrix:
            print(row)
        print("Native Spark PipelineModel saved: False")
        print(f"Reproducible model specification saved: {specification_path}")
        print(f"Evaluation report: {report_path()}")
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
