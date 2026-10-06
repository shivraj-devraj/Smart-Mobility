# Phase 7A Rule-Based Traffic Advisory Engine

## Purpose

This module converts historical congestion classifications and available contextual fields into deterministic, explainable traffic-management recommendations. It is a batch advisory generator, not an automated traffic-control system.

The engine does not use an LLM, generative AI, external ML model, live traffic, signal-event streams, integrated FASTag/toll transactions, direction, GPS coordinates, or hour-level observations.

## Input and outputs

Input:

- `data/processed/integrated_traffic_data.csv`

Outputs:

- `data/output/advisory_output.csv`
- `data/output/advisory_summary.txt`

Exactly one advisory record is generated for each input record.

## Congestion rules

- `Low` maps to `Normal` advisory level and routine monitoring.
- `Medium` maps to `Moderate` advisory level, increased monitoring, possible additional personnel, diversion planning if congestion persists, and review of non-essential roadwork scheduling.
- `High` maps to `High` advisory level, recommended additional traffic personnel, preparation of suitable diversion planning, and possible suspension or rescheduling of non-essential roadwork where operationally appropriate.

The wording is intentionally advisory: recommendations are not claims that personnel were deployed, diversions activated, or roadwork suspended.

## Context rules

Context notes are appended only when supported by the row:

- `festival_flag = true`: festival-related preparedness note.
- `holiday_flag = true`: expected travel-demand review note.
- `roadwork = Yes`: roadwork postponement review note.
- `weather` is `Rain` or `Fog`: additional caution and monitoring note.

Rules are separated from input loading so they can be changed without rewriting the data-loading layer.

## Validation

The engine validates row preservation, duplicate `(date, corridor)` keys, non-null congestion classes, permitted advisory levels, one-to-one congestion-class mapping, each context condition, output fields, and output-file existence. The summary reports advisory-level and congestion-class distributions plus context counts.

## Scope limitation

Results are recommendations derived from historical batch records. They do not represent live operational decisions or infrastructure control, and they do not invent unavailable traffic dimensions.

## Run

```powershell
python -m src.advisory.advisory_engine
```

## Phase 7B Prediction-to-Advisory Flow

`prediction_advisory_pipeline.py` reconstructs the Phase 6B Decision Tree pipeline from `models/decision_tree_baseline/model_specification.json`; it does not call `PipelineModel.load()` because that artifact is a reproducible specification rather than a native Spark model. It fits preprocessing and the classifier only on the chronological training period through `2024-01-31`, predicts the test period, and evaluates predictions against the actual test labels separately from advisory generation.

The rule engine receives only `predicted_congestion_class` plus festival, holiday, roadwork, and weather context. The historical target is retained as `actual_congestion_class` for comparison and never drives advisory rules.

Phase 7B outputs:

- `data/output/prediction_advisory_output.csv`
- `data/output/prediction_advisory_summary.txt`

Run it with:

```powershell
python -m src.advisory.prediction_advisory_pipeline
```
