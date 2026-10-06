"""Train and evaluate the Phase 4 Spark MLlib Random Forest benchmark."""

import hashlib
import json
from pathlib import Path
import re

from pyspark.ml import Pipeline
from pyspark.ml.classification import RandomForestClassifier
from pyspark.ml.evaluation import MulticlassClassificationEvaluator
from pyspark.ml.feature import OneHotEncoder, StringIndexer, VectorAssembler
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql.functions import col

from src.spark_session import create_spark_session
from src.prediction.train_decision_tree import (
    load_dataset,
    chronological_split,
    add_class_names,
    confusion_matrix,
    class_distribution,
    NUMERIC_FEATURES,
    CATEGORICAL_FEATURES,
    BOOLEAN_FEATURES,
    FEATURE_COLUMNS,
    TARGET_COLUMN,
    TARGET_CLASSES,
    EXPECTED_ROW_COUNT,
)

NUM_TREES = 20
MAX_DEPTH = 5
SEED = 42


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def input_path() -> Path:
    return project_root() / "data" / "processed" / "integrated_traffic_data.csv"


def baseline_report_path() -> Path:
    return project_root() / "data" / "output" / "ml_baseline_evaluation.txt"


def benchmark_report_path() -> Path:
    return project_root() / "data" / "output" / "ml_model_benchmark.txt"


def model_dir() -> Path:
    return project_root() / "models" / "random_forest_benchmark"


def load_baseline_metrics() -> dict[str, float]:
    """Read the existing validated baseline metrics without recomputing or overwriting them."""
    path = baseline_report_path()
    if not path.is_file():
        raise FileNotFoundError(f"Baseline report not found: {path}")
    text = path.read_text(encoding="utf-8")
    patterns = {
        "Accuracy": r"Accuracy:\s*([0-9.]+)",
        "Weighted Precision": r"Weighted Precision:\s*([0-9.]+)",
        "Weighted Recall": r"Weighted Recall:\s*([0-9.]+)",
        "F1 Score": r"F1 Score:\s*([0-9.]+)",
    }
    metrics = {k: float(re.search(p, text).group(1)) for k, p in patterns.items()}
    return metrics


def build_rf_pipeline(
    num_trees: int = NUM_TREES,
    max_depth: int = MAX_DEPTH,
    seed: int = SEED,
) -> Pipeline:
    """Build a leakage-safe Spark ML pipeline for the Random Forest benchmark."""
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
    classifier = RandomForestClassifier(
        labelCol="label",
        featuresCol="features",
        predictionCol="prediction",
        numTrees=num_trees,
        maxDepth=max_depth,
        seed=seed,
    )
    return Pipeline(stages=[*categorical_indexers, encoder, label_indexer, assembler, classifier])


def extract_feature_importances(
    rf_model,
    indexer_models: list,
) -> tuple[list[dict[str, object]], dict[str, float]]:
    """Extract vector-level and grouped logical feature importances."""
    importances = rf_model.featureImportances
    vector_names = []

    for name in NUMERIC_FEATURES:
        vector_names.append({"feature": name, "group": name, "type": "numeric"})

    for cat_name, indexer in zip(CATEGORICAL_FEATURES, indexer_models):
        labels = list(indexer.labels)
        for label in labels:
            vector_names.append({
                "feature": f"{cat_name}={label}",
                "group": cat_name,
                "type": "categorical_one_hot",
            })
        vector_names.append({
            "feature": f"{cat_name}=<unseen_or_invalid>",
            "group": cat_name,
            "type": "categorical_one_hot_keep",
        })

    for name in BOOLEAN_FEATURES:
        vector_names.append({"feature": name, "group": name, "type": "boolean"})

    vector_importances = []
    grouped_importances = {name: 0.0 for name in FEATURE_COLUMNS}

    for idx, item in enumerate(vector_names):
        val = float(importances[idx]) if idx < len(importances) else 0.0
        vector_importances.append({
            "vector_index": idx,
            "feature": item["feature"],
            "group": item["group"],
            "type": item["type"],
            "importance": round(val, 6),
        })
        grouped_importances[item["group"]] = round(grouped_importances[item["group"]] + val, 6)

    sorted_grouped = dict(sorted(grouped_importances.items(), key=lambda kv: kv[1], reverse=True))
    return vector_importances, sorted_grouped


def save_specification(
    rf_model,
    destination: Path,
    labels: list[str],
    cutoff_date: object,
    training_rows: int,
    testing_rows: int,
    metrics: dict[str, float],
    grouped_importances: dict[str, float],
    vector_importances: list[dict[str, object]],
) -> Path:
    """Save reproducible model specification without relying on Hadoop native persistence."""
    destination.mkdir(parents=True, exist_ok=True)
    specification = {
        "artifact_type": "reproducible_spark_random_forest_specification",
        "native_spark_pipeline_model": False,
        "model_class": "RandomForestClassifier",
        "classifier": {
            "numTrees": rf_model.getNumTrees if isinstance(rf_model.getNumTrees, int) else rf_model.getNumTrees(),
            "maxDepth": rf_model.getMaxDepth(),
            "seed": rf_model.getOrDefault(rf_model.seed),
            "labelCol": rf_model.getOrDefault(rf_model.labelCol),
            "featuresCol": rf_model.getOrDefault(rf_model.featuresCol),
            "predictionCol": rf_model.getOrDefault(rf_model.predictionCol),
            "totalNumNodes": rf_model.totalNumNodes,
            "feature_vector_dimension": len(rf_model.featureImportances),
        },
        "features": {
            "numeric": NUMERIC_FEATURES,
            "categorical": CATEGORICAL_FEATURES,
            "boolean": BOOLEAN_FEATURES,
            "feature_count": len(FEATURE_COLUMNS),
            "vector_dimension": len(rf_model.featureImportances),
        },
        "target": {
            "column": TARGET_COLUMN,
            "classes": sorted(TARGET_CLASSES),
            "class_mapping": {class_name: idx for idx, class_name in enumerate(labels)},
        },
        "training": {
            "cutoff_date": str(cutoff_date),
            "training_rows": training_rows,
            "testing_rows": testing_rows,
            "input_sha256": hashlib.sha256(input_path().read_bytes()).hexdigest(),
        },
        "evaluation": metrics,
        "grouped_feature_importances": grouped_importances,
        "vector_feature_importances": vector_importances,
        "persistence_note": (
            "Lightweight reproducible specification; native Spark PipelineModel persistence "
            "was not used due to Windows Hadoop/winutils filesystem limitations."
        ),
    }
    specification_path = destination / "model_specification.json"
    temp_path = destination / "model_specification.json.tmp"
    temp_path.write_text(json.dumps(specification, indent=2), encoding="utf-8")
    temp_path.replace(specification_path)
    return specification_path


def build_benchmark_report(
    training: DataFrame,
    testing: DataFrame,
    cutoff_date: object,
    baseline_metrics: dict[str, float],
    rf_metrics: dict[str, float],
    matrix: list[dict[str, object]],
    grouped_importances: dict[str, float],
    specification_path: Path,
) -> str:
    """Format comparative benchmark text report."""
    training_range = training.selectExpr("MIN(date) AS min_date", "MAX(date) AS max_date").first()
    testing_range = testing.selectExpr("MIN(date) AS min_date", "MAX(date) AS max_date").first()

    lines = [
        "PHASE 4 - ML MODEL BENCHMARK REPORT",
        "====================================",
        "",
        "Random Forest is benchmarked against the existing validated Decision Tree using the same features and chronological test split.",
        "",
        "Dataset and Split Configuration:",
        "--------------------------------",
        f"- Input dataset: {input_path()}",
        f"- Total rows: {training.count() + testing.count()}",
        f"- Cutoff date: {cutoff_date}",
        f"- Training date range: {training_range['min_date']} to {training_range['max_date']} ({training.count():,} rows)",
        f"- Testing date range: {testing_range['min_date']} to {testing_range['max_date']} ({testing.count():,} rows)",
        f"- Total input features: {len(FEATURE_COLUMNS)} (vector dimension: 61)",
        f"- Target column: {TARGET_COLUMN} (High=0, Low=1, Medium=2)",
        "",
        "Model Configurations:",
        "---------------------",
        "- Baseline: DecisionTreeClassifier (maxDepth=5, seed=42)",
        f"- Benchmark: RandomForestClassifier (numTrees={NUM_TREES}, maxDepth={MAX_DEPTH}, seed={SEED})",
        "",
        "Comparative Evaluation Metrics (Chronological Held-Out Test Set):",
        "----------------------------------------------------------------",
        f"{'Metric':<24} {'Decision Tree':<20} {'Random Forest':<20}",
        f"{'-'*24} {'-'*20} {'-'*20}",
        f"{'Accuracy':<24} {baseline_metrics['Accuracy']:<20.6f} {rf_metrics['Accuracy']:<20.6f}",
        f"{'Weighted Precision':<24} {baseline_metrics['Weighted Precision']:<20.6f} {rf_metrics['Weighted Precision']:<20.6f}",
        f"{'Weighted Recall':<24} {baseline_metrics['Weighted Recall']:<20.6f} {rf_metrics['Weighted Recall']:<20.6f}",
        f"{'F1 Score':<24} {baseline_metrics['F1 Score']:<20.6f} {rf_metrics['F1 Score']:<20.6f}",
        "",
        "Random Forest Confusion Matrix:",
        "-------------------------------",
        "actual_class,predicted_class,count",
    ]
    lines.extend(f"{row['actual_class']},{row['predicted_class']},{row['count']}" for row in matrix)
    lines.extend([
        "",
        "Random Forest Grouped Feature Importances (summed over one-hot components):",
        "--------------------------------------------------------------------------",
        f"{'Feature Group':<28} {'Importance':<12}",
        f"{'-'*28} {'-'*12}",
    ])
    lines.extend(f"{name:<28} {val:<12.6f}" for name, val in grouped_importances.items())
    lines.extend([
        "",
        "Persistence & Reproducibility:",
        "------------------------------",
        f"- Random Forest specification: {specification_path}",
        "- Native Spark PipelineModel: NOT CREATED (Windows Hadoop winutils/JNI limitation)",
        "- Baseline status: Decision Tree baseline files remain completely unchanged.",
        "",
    ])
    return "\n".join(lines)


def main() -> None:
    spark = create_spark_session("RandomForestBenchmark")
    try:
        data = load_dataset(spark)
        if data.count() != EXPECTED_ROW_COUNT:
            raise ValueError(f"Expected {EXPECTED_ROW_COUNT} rows; found {data.count()}")

        baseline_metrics = load_baseline_metrics()
        training, testing, cutoff_date = chronological_split(data)

        pipeline = build_rf_pipeline(num_trees=NUM_TREES, max_depth=MAX_DEPTH, seed=SEED)
        pipeline_model = pipeline.fit(training)

        rf_model = pipeline_model.stages[-1]
        indexer_models = pipeline_model.stages[:len(CATEGORICAL_FEATURES)]
        label_indexer_model = pipeline_model.stages[len(CATEGORICAL_FEATURES) + 1]
        labels = list(label_indexer_model.labels)

        predictions = pipeline_model.transform(testing)
        predictions = add_class_names(predictions, labels)

        evaluator_acc = MulticlassClassificationEvaluator(labelCol="label", predictionCol="prediction", metricName="accuracy")
        evaluator_prec = MulticlassClassificationEvaluator(labelCol="label", predictionCol="prediction", metricName="weightedPrecision")
        evaluator_rec = MulticlassClassificationEvaluator(labelCol="label", predictionCol="prediction", metricName="weightedRecall")
        evaluator_f1 = MulticlassClassificationEvaluator(labelCol="label", predictionCol="prediction", metricName="f1")

        rf_metrics = {
            "Accuracy": evaluator_acc.evaluate(predictions),
            "Weighted Precision": evaluator_prec.evaluate(predictions),
            "Weighted Recall": evaluator_rec.evaluate(predictions),
            "F1 Score": evaluator_f1.evaluate(predictions),
        }

        matrix = confusion_matrix(predictions)
        vector_importances, grouped_importances = extract_feature_importances(rf_model, indexer_models)

        specification_path = save_specification(
            rf_model=rf_model,
            destination=model_dir(),
            labels=labels,
            cutoff_date=cutoff_date,
            training_rows=training.count(),
            testing_rows=testing.count(),
            metrics=rf_metrics,
            grouped_importances=grouped_importances,
            vector_importances=vector_importances,
        )

        report = build_benchmark_report(
            training=training,
            testing=testing,
            cutoff_date=cutoff_date,
            baseline_metrics=baseline_metrics,
            rf_metrics=rf_metrics,
            matrix=matrix,
            grouped_importances=grouped_importances,
            specification_path=specification_path,
        )
        benchmark_report_path().parent.mkdir(parents=True, exist_ok=True)
        benchmark_report_path().write_text(report, encoding="utf-8")

        print("PHASE 4 RANDOM FOREST BENCHMARK COMPLETE")
        print("========================================")
        print(f"Training rows: {training.count()}")
        print(f"Testing rows: {testing.count()}")
        print(f"Cutoff date: {cutoff_date}")
        print("\nComparative Metrics:")
        print(f"{'Metric':<24} {'Decision Tree':<16} {'Random Forest':<16}")
        print(f"{'-'*24} {'-'*16} {'-'*16}")
        for m in ["Accuracy", "Weighted Precision", "Weighted Recall", "F1 Score"]:
            print(f"{m:<24} {baseline_metrics[m]:<16.6f} {rf_metrics[m]:<16.6f}")
        print(f"\nBenchmark report written to: {benchmark_report_path()}")
        print(f"Model specification saved to: {specification_path}")

    finally:
        spark.stop()


if __name__ == "__main__":
    main()
