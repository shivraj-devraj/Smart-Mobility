# Phase 6A and Phase 6B ML Preparation

## Phase 6A Scope

This phase inspects the Phase 4 integrated dataset and designs a future Spark MLlib preprocessing pipeline. It does not fit a model, create a train/test split, generate predictions, evaluate a model, or save a model.

## Target

The target is `congestion_class` with the expected classes `Low`, `Medium`, and `High`.

Observed distribution:

- Low: 1,947 records, 21.7883%
- Medium: 2,314 records, 25.8953%
- High: 4,675 records, 52.3165%

The class distribution is reported only. No rebalancing, SMOTE, or other balancing technique is applied.

## Feature selection

The source is `data/processed/integrated_traffic_data.csv` with 8,936 rows.

Available candidate features:

- Numeric: `traffic_volume`, `average_speed`, `travel_time_index`, `congestion_level`
- Categorical: `corridor`, `area`, `road_intersection`, `weather`, `roadwork`, `day_type`
- Temporal/derived: `day_of_week`, `festival_flag`, `holiday_flag`

The initial proposed feature set is:

`traffic_volume`, `average_speed`, `travel_time_index`, `corridor`, `area`, `road_intersection`, `weather`, `roadwork`, `day_of_week`, `day_type`, `festival_flag`, `holiday_flag`

## Leakage decisions

`congestion_level` is excluded by default. During preprocessing, `congestion_class` was created directly from `congestion_level`, so using it would expose the target-generation rule and cause direct target leakage.

`congestion_class` is the target and cannot be used as a feature. `festival_name` is excluded from the initial feature set because it is a sparse calendar label that duplicates festival-indicator semantics and would require a separate encoding decision. The raw `date` is excluded as an identifier; intentional temporal features should be derived instead.

The other available fields were not identified as direct representations of the target. The inspection report records every exclusion and reason.

## Categorical cardinality

The inspection reports the distinct counts for `corridor`, `area`, `road_intersection`, `weather`, `roadwork`, and `day_type`. These counts will guide future `StringIndexer` and `OneHotEncoder` choices.

## Proposed future MLlib preparation

1. Apply `StringIndexer(handleInvalid='keep')` to selected categorical columns.
2. Apply `OneHotEncoder` to indexed categorical columns.
3. Combine encoded categoricals, numeric fields, and temporal/boolean fields with `VectorAssembler`.
4. Apply `StringIndexer` to `congestion_class` as the eventual label.
5. Consider `StandardScaler` only when the selected estimator requires it.

No component is fitted or saved in Phase 6A.

## Split strategy

A chronological split is recommended because this is historical batch traffic data and the eventual task concerns future traffic. Earlier dates should be used for training and later dates for testing. A random split may be a secondary sensitivity check, but repeated corridor/date observations can allow information from later periods to influence the training sample.

## Limitations

The dataset does not provide hour, direction, GPS coordinates, live traffic features, FASTag features, or signal-event features. Toll and signal data were not integrated because compatible keys were unavailable. Festival and holiday indicators come from the curated project calendar. No causal claim should be made from these fields.

## Run

```powershell
python -m src.prediction.feature_inspection
```

The command writes `data/output/ml_feature_inspection.txt`.

## Phase 6B Decision Tree Baseline

Phase 6B trains the first Spark MLlib baseline: a `DecisionTreeClassifier` predicting `congestion_class` from the specified leakage-safe feature set. It uses the Phase 4 integrated dataset and a chronological split based on the first approximately 80% of sorted distinct dates. Preprocessing transformers and the classifier are fitted together in a Spark `Pipeline` using training data only.

The baseline uses:

- Numeric: `traffic_volume`, `average_speed`, `travel_time_index`, `day_of_week`
- Categorical: `corridor`, `area`, `road_intersection`, `weather`, `roadwork`, `day_type`
- Boolean: `festival_flag`, `holiday_flag`

`congestion_level`, `congestion_class`, `festival_name`, and raw `date` are excluded. In particular, `congestion_level` directly generated the target during preprocessing and would cause target leakage.

Categorical columns use `StringIndexer(handleInvalid='keep')` and `OneHotEncoder`. The target uses deterministic alphabetical indexing: `High = 0`, `Low = 1`, `Medium = 2`. `VectorAssembler` creates the model feature vector.

The script reports chronological train/test ranges and class distributions, accuracy, weighted precision, weighted recall, F1, and a Spark DataFrame confusion matrix. It writes a reproducible fitted-model specification to `models/decision_tree_baseline/model_specification.json` and the evaluation report to `data/output/ml_baseline_evaluation.txt`.

The JSON is not a native Spark `PipelineModel`; it records the fitted preprocessing mappings, deterministic target labels, one-hot category sizes, Decision Tree parameters and tree structure, feature configuration, chronological cutoff, and input-file SHA-256. This preserves a reproducible project artifact without falsely claiming that Spark native persistence succeeded. Native `PipelineModel` persistence remains unavailable in this Windows environment because Hadoop native filesystem support (`winutils.exe` and compatible native libraries) is unavailable.

## Phase 6B Run

```powershell
python -m src.prediction.train_decision_tree
```

This is a baseline only. It does not implement Random Forest, tuning, advisory logic, dashboards, or later project phases.
