# Smart Mobility: Bengaluru Traffic Congestion Analytics & Advisory System

A full-stack Bengaluru traffic intelligence project combining a React (Vite) and FastAPI application with an offline PySpark analytics and machine-learning pipeline. The application provides OSRM-based route comparison and CSV-backed historical corridor traffic and advisory views.

---

## 1. Project Overview

This project combines a browser application with a reproducible historical analytics pipeline. The pipeline processes multi-year Bengaluru traffic records alongside a curated Karnataka regional calendar to deliver:

- **Corridor-Level Traffic Analytics**: Aggregated historical metrics across 16 major corridors.
- **Congestion Classification**: Multi-class classification (Low, Medium, High) evaluated on a held-out chronological test split.
- **Historical Scenario Analysis**: Offline comparisons of observed conditions under contextual filters.
- **Model Benchmarking & Evaluation**: Baseline Decision Tree compared against a Random Forest benchmark with per-class metrics and grouped feature importance.
- **Historical Advisory**: Transparent, deterministic recommendations generated from persisted traffic records and, in a separate batch output, predicted test-period classes.
- **Web Application**: A React/Vite frontend with a FastAPI backend for route comparison and CSV-backed historical traffic and advisory endpoints.

### Operational Scope & Clarification
This system is an **offline batch historical analytics and diagnostic classification platform**. It is explicitly **NOT**:
- A real-time traffic monitoring or live camera feed system
- A GPS navigation or live turn-by-turn routing application
- A long-horizon time-series forecasting engine
- An automated physical traffic-signal or infrastructure-control system

---

## 2. Objectives

1. **Ingest & Validate Historical Data**: Safely ingest public Bengaluru traffic records while preserving raw input immutability.
2. **Standardize Corridors & Context**: Derive structured analytical attributes and map intersections to 16 standardized composite corridors.
3. **Conduct Distributed Descriptive Analytics**: Utilize Spark SQL to quantify traffic variations across weekdays, weekends, festivals, holidays, and adverse weather.
4. **Build Baseline & Benchmark Classifiers**: Train a Spark MLlib Decision Tree baseline and evaluate a Random Forest benchmark on a strict chronological split without temporal leakage.
5. **Generate Deterministic Advisories**: Map predicted congestion tiers and contextual flags to traceable operational recommendations.
6. **Deliver Interactive Visualization**: Provide browser-based route search and historical corridor intelligence through React and FastAPI.

---

## 3. Dataset Scope

The primary data source is a validated public dataset of Bengaluru traffic observations integrated with a curated Karnataka festival and holiday calendar:

- **Integrated Dataset Volume**: 8,936 records
- **Historical Coverage**: 2022-01-01 to 2024-08-09
- **Corridor Count**: 16 unique corridors spanning 8 administrative areas
- **Chronological Train/Test Split**:
  - **Training Period**: 2022-01-01 to 2024-01-31 (7,145 records; ~80% of distinct dates)
  - **Testing Period**: 2024-02-01 to 2024-08-09 (1,791 records; ~20% of distinct dates)

> [!NOTE]
> The chronological split ensures that the testing period strictly follows the training period in time, preventing temporal lookahead bias. The model evaluates classification performance on unseen historical periods; this is not time-series forecasting.

---

## 4. Architecture

The project has two connected application/data paths: an offline historical analytics pipeline and a browser application. The FastAPI endpoints read persisted analytics outputs; Spark is not run for each browser request.

```mermaid
flowchart LR
    subgraph Browser
        UI[React + Vite<br/>Route Search, Historical Intelligence]
        MAP[React-Leaflet map]
    end
    subgraph API
        API[FastAPI on Uvicorn]
        ROUTE[Route service]
        HIST[Historical traffic and advisory APIs]
    end
    OSM[Nominatim geocoding] --> ROUTE
    ROUTE --> OSRM[OSRM road-network routing]
    OSRM --> ROUTE
    UI <--> API
    MAP --> UI
    HIST --> CSV[Persisted CSV outputs]
    PIPE[PySpark preprocessing, Spark SQL, MLlib] --> CSV
    CAL[Historical traffic + calendar inputs] --> PIPE
```

Route flow: React sends location text or selected real coordinates to FastAPI; the route service uses Nominatim when geocoding is needed and requests route alternatives from OSRM. The frontend renders the returned geometry with React-Leaflet.

Historical flow: PySpark generates persisted outputs offline. FastAPI reads the persisted corridor summaries and historical advisory output for the React interface. Historical advisory data is not matched to OSRM route geometry.

### Source Directory Organization
- `src/ingestion/`: Raw data validation, synthetic context generation, and calendar integration.
- `src/preprocessing/`: Data cleaning, schema enforcement, date feature extraction, and target class binning.
- `src/corridor/`: Deterministic mapping of areas and intersections to composite corridors.
- `src/analytics/`: Distributed Spark SQL aggregations for corridor, temporal, and festival summaries.
- `src/prediction/`: ML pipeline feature assembly, baseline Decision Tree training, and Random Forest benchmarking.
- `src/advisory/`: Deterministic rule engine and prediction-to-advisory scoring pipeline.
- `src/route/`: Shared Nominatim geocoding and OSRM route parsing/ranking services used by the API.
- `backend/app/`: FastAPI application, route/traffic/advisory endpoints, schemas, and services.
- `frontend/src/`: React application, route search/map/results, and historical traffic/advisory UI.
- `frontend/src/components/RouteSearch.jsx`: Location autocomplete and route-search form.
- `frontend/src/components/RouteMap.jsx`: React-Leaflet route map.
- `frontend/src/components/RouteSummary.jsx`: Route alternatives and OSRM ranking explanation.
- `frontend/src/components/HistoricalTrafficIntelligence.jsx`: Historical corridor metrics and advisory view.
- `frontend/src/components/RouteMetricsCard.jsx`, `RouteAdvisoryCard.jsx`, and `TravelContextBar.jsx`: Reusable components currently present in the source tree; they are not connected to route-specific congestion scoring.
- `src/visualization/`: Production of static publication-quality matplotlib/seaborn charts.

---

## 5. Technology Stack

- **Core Runtime**: Python 3.10+ (tested on Python 3.13)
- **Distributed Processing**: Apache PySpark 3.5.x (PySpark SQL, MLlib)
- **Data Manipulation**: Pandas 2.x
- **Visualization**: Matplotlib 3.8+, Seaborn 0.13+
- **Frontend**: React, Vite, JavaScript, CSS and CSS Modules (no Tailwind dependency is configured).
- **Backend API**: FastAPI and Uvicorn.
- **Geographic Routing & Mapping**: OpenStreetMap Nominatim, OSRM (Open Source Routing Machine), Leaflet and React-Leaflet.
- **Model Specification**: JSON (portable schema-validated specification artifacts)
- **Version Control**: Git / GitHub

---

## 6. Data Processing and Analytics

1. **Preprocessing & Schema Standardization**: Normalizes dates into `yyyy-MM-dd`, validates numeric fields (`traffic_volume`, `average_speed`, `travel_time_index`), and derives `congestion_class` using configured thresholds:
   - `Low`: Congestion Level `< 60`
   - `Medium`: `60 <= Congestion Level < 90`
   - `High`: Congestion Level `>= 90`
2. **Corridor Identification**: Combines `area` and `road_intersection` into 16 composite corridor keys (e.g., `Indiranagar | 100 Feet Road`, `Electronic City | Hosur Road`).
3. **Data Integration**: Performs a row-preserving left join with the Karnataka holiday and festival calendar, attaching `festival_flag`, `festival_name`, and `holiday_flag`.
4. **Spark SQL Aggregations**: Generates summary outputs covering top corridors by average congestion, high-congestion percentages, weekday versus weekend distributions, and festival comparisons.

---

## 7. Historical Scenario Analysis

The offline analytics project includes a historical scenario analysis workflow for comparing persisted observations under contextual combinations:

- **Scenario Controls**: Corridor, Day Type (Weekday/Weekend), Festival (Festival/Non-Festival), Holiday (Holiday/Non-Holiday), Weather (Clear, Fog, Overcast, Rain, Windy), and Roadwork (Yes/No).
- **Comparative Metrics**: Displays historical subset size, average congestion, high-congestion percentage, average speed, traffic volume, and travel time index alongside deltas relative to the full dataset baseline.
- **Descriptive Visualizations**: Categorical breakdown charts comparing the filtered scenario against historical baselines.

> [!IMPORTANT]
> Scenario analysis is descriptive and does not establish causal effects or guarantee future outcomes. Differences reflect observed historical combinations in the public dataset.

---

## 8. Machine Learning

Machine learning models classify historical traffic records into three congestion classes (`Low`, `Medium`, `High`) using a 61-dimensional feature vector (4 numeric features, 55 one-hot encoded categorical features, and 2 boolean flags).

### Decision Tree Baseline
- **Algorithm**: Spark MLlib `DecisionTreeClassifier`
- **Hyperparameters**: `maxDepth=5`, `seed=42`
- **Assembler Inputs**: Numeric features (`traffic_volume`, `average_speed`, `travel_time_index`, `day_of_week`), one-hot encoded categoricals (`corridor`, `area`, `road_intersection`, `weather`, `roadwork`, `day_type`), and boolean flags (`festival_flag`, `holiday_flag`).
- **Validation Test Set Metrics (1,791 rows)**:
  - **Accuracy**: `0.919040`
  - **Weighted Precision**: `0.919577`
  - **Weighted Recall**: `0.919040`
  - **F1 Score**: `0.919270`

### Random Forest Benchmark
- **Algorithm**: Spark MLlib `RandomForestClassifier`
- **Hyperparameters**: `numTrees=20`, `maxDepth=5`, `seed=42`
- **Input Pipeline**: Identical 61-dimensional vector and identical chronological split.
- **Validation Test Set Metrics (1,791 rows)**:
  - **Accuracy**: `0.903406`
  - **Weighted Precision**: `0.903470`
  - **Weighted Recall**: `0.903406`
  - **F1 Score**: `0.899209`

Neither model is characterized as "best", "winner", or "superior". The Random Forest serves strictly as an empirical benchmark to assess ensemble classification stability against the baseline.

---

## 9. Per-Class Evaluation

To avoid reliance on aggregate metrics alone, persisted evaluation outputs include a granular per-class breakdown derived from the validated test-set confusion matrices:

| Class | Model | Precision | Recall | F1 Score | Test Support |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **High** | Decision Tree | 0.953390 | 0.951374 | 0.952381 | 946 |
| **High** | Random Forest | 0.895138 | 0.992600 | 0.941353 | 946 |
| **Low** | Decision Tree | 0.937337 | 0.920513 | 0.928849 | 390 |
| **Low** | Random Forest | 0.934896 | 0.920513 | 0.927649 | 390 |
| **Medium** | Decision Tree | 0.834052 | 0.850549 | 0.842220 | 455 |
| **Medium** | Random Forest | 0.893855 | 0.703297 | 0.787208 | 455 |

*Total test support: 1,791 records covering 2024-02-01 to 2024-08-09.*

---

## 10. Feature Importance

Feature importance is quantified from the Random Forest benchmark ensemble by summing Gini importance across one-hot components into 12 logical feature groups:

1. `traffic_volume`: 0.502176
2. `travel_time_index`: 0.193824
3. `area`: 0.124284
4. `road_intersection`: 0.066804
5. `corridor`: 0.065991
6. `average_speed`: 0.039955
7. `weather`: 0.002407
8. `day_type`: 0.001809
9. `day_of_week`: 0.001328
10. `festival_flag`: 0.000711
11. `roadwork`: 0.000418
12. `holiday_flag`: 0.000294

> [!NOTE]
> Feature importance indicates how the trained tree ensemble uses input variables for classification. It does not establish causation or physical traffic influence.

---

## 11. Leakage Prevention and Model Limitations

Strict architectural safeguards prevent target leakage across the pipeline:
- `congestion_level` is **strictly excluded** from model inputs because `congestion_class` is directly derived from it.
- `congestion_class` is the target column and cannot appear as a feature.
- Raw `date` strings are excluded to prevent temporal memorization.
- `festival_name` is excluded due to extreme calendar sparsity.
- **Chronological Split**: Training records precede all test records in time.

> [!IMPORTANT]
> The model uses contemporaneous traffic variables such as `traffic_volume`, `average_speed`, and `travel_time_index` for historical classification. Therefore, the task should not be interpreted as long-horizon future traffic forecasting.

---

## 12. Rule-Based Traffic Advisory

The advisory module ([src/advisory/advisory_engine.py](src/advisory/advisory_engine.py)) converts predicted congestion classes and contextual flags into deterministic, transparent operational advisories:

### Congestion Tier Mappings
- **Low Congestion** $\to$ **Normal Advisory**: Routine monitoring; standard traffic personnel; no diversion needed.
- **Medium Congestion** $\to$ **Moderate Advisory**: Increased monitoring; consider additional personnel; review diversion planning if congestion persists; review roadwork scheduling.
- **High Congestion** $\to$ **High Advisory**: Deploy additional traffic personnel; prepare and activate diversion planning; suspend or reschedule non-essential roadwork.

### Contextual Triggers
- `festival_flag = True`: Festival preparedness and crowd monitoring note.
- `holiday_flag = True`: Elevated holiday travel demand review note.
- `roadwork = "Yes"`: Roadwork postponement review note during peak congestion.
- `weather in ("Rain", "Fog")`: Adverse weather caution and reduced visibility alert.

Recommendations are operational suggestions derived from deterministic rules; they do not represent live municipal decisions or physical infrastructure dispatch.

---

## 13. React Application

The browser application is implemented in `frontend/` with a Vite development server and React UI. FastAPI serves route, historical traffic, and historical advisory endpoints.

- **Route Search** (`RouteSearch.jsx`): Origin/destination fields with Nominatim-backed autocomplete.
- **Route Results** (`RouteSummary.jsx`): OSRM alternatives, distance, road-network duration estimates, and the existing route recommendation.
- **Leaflet Map** (`RouteMap.jsx`): Displays route geometry, origin/destination markers, and selectable route alternatives using React-Leaflet.
- **Historical Corridor Analytics and Advisory** (`HistoricalTrafficIntelligence.jsx`): Reads persisted CSV-backed API results for corridor summaries, temporal information, and historical advisory data.
- **Reusable UI components**: `TravelContextBar.jsx`, `RouteMetricsCard.jsx`, and `RouteAdvisoryCard.jsx` exist in the source tree but are not currently wired into route-specific congestion scoring. Route metric adjustments are illustrative only, not model predictions.

The API reads persisted historical outputs; it does not launch PySpark for each browser request. Historical corridor/advisory data is not matched to OSRM geometry.

---

## 14. Route Recommendation (Nominatim + OSRM)

- **Nominatim** resolves typed locations and supplies real coordinates.
- **OSRM** returns road-network route alternatives, geometry, distance, and estimated duration.
- **React-Leaflet** renders returned routes in the browser map.
- The current recommendation sorts durations into 60-second buckets, then uses route distance to order routes within a bucket.
- The ranking does **not** use live traffic, historical congestion, or roadwork status. It is separate from the Spark SQL / MLlib pipeline.
- Public geocoding/routing services have their own availability and usage policies; no paid key is configured in this project.

---

## 15. Geographic / GIS Integrity

> [!WARNING]
> The historical dataset does not include GPS coordinates; corridor records use textual composite identifiers (e.g., `Indiranagar | 100 Feet Road`). The system strictly avoids fabricating latitude/longitude values or arbitrarily mapping road segments to historical records.
>
> OpenStreetMap is used exclusively for dynamic geographic routing between user-specified locations, maintaining absolute scientific integrity for the historical Big Data analytics pipeline.

---

## 15. Windows Spark Compatibility

When deploying PySpark on Windows environments, native Spark ML `PipelineModel.save()` calls frequently fail due to missing native Hadoop binaries (`winutils.exe` and `NativeIO$Windows.access0`). 

To guarantee 100% reproducibility across operating systems without external binary dependencies:
- Models are persisted as **lightweight, schema-validated JSON model specifications** (`models/decision_tree_baseline/model_specification.json` and `models/random_forest_benchmark/model_specification.json`).
- These specifications store complete decision tree splits, one-hot category sizes, categorical indexer label orders, hyperparameters, input SHA-256 fingerprints, and evaluation metrics.
- Subsequent pipeline stages reconstruct the exact fitted transformations deterministically from the specification rather than calling native binary loaders.

---

## 16. Project Structure

```text
BDA project/
├── config/                  # Pipeline schemas, thresholds, and mappings
├── backend/                 # FastAPI routes, schemas, and services
├── frontend/                # React/Vite browser application
│   └── src/
│       ├── components/      # Route search, map, results, historical views
│       └── utils/           # UI formatting and corridor helper utilities
├── dashboard/               # Older Python dashboard source retained in the repository
├── data/
│   ├── output/              # Validated CSV summaries, reports, and charts
│   ├── processed/           # Preprocessed and integrated traffic datasets
│   └── raw/                 # Immutable real and synthetic source files
├── docs/                    # Detailed technical documentation and reports
├── models/
│   ├── decision_tree_baseline/       # DT baseline JSON specification
│   └── random_forest_benchmark/      # RF benchmark JSON specification
├── requirements.txt         # Pinned Python package dependencies
├── src/
│   ├── advisory/            # Rule-based advisory engine & pipeline
│   ├── analytics/           # Spark SQL analytical aggregations
│   ├── corridor/            # Corridor identifier tagging logic
│   ├── ingestion/           # Data loading, validation, and integration
│   ├── prediction/          # Decision Tree & Random Forest ML pipelines
│   ├── preprocessing/       # Cleaning and feature engineering
│   ├── spark_session.py     # Centralized SparkSession builder
│   └── visualization/       # Static chart generation scripts
└── tests/                   # Infrastructure smoke tests
```

---

## 17. Installation

The following commands reflect the current Windows project layout, where the Python virtual environment is in the outer `BDA project` folder and the application source is in its inner `BDA project` folder.

### Backend setup and startup

In PowerShell Terminal 1:

```powershell
cd "C:\Users\shivr\Downloads\BDA project"
.\.venv\Scripts\Activate.ps1
python -m uvicorn backend.app.main:app --app-dir "C:\Users\shivr\Downloads\BDA project\BDA project" --reload --port 8000
```

If the environment has not been created, create it and install the Python dependencies from the inner project root first:

```powershell
cd "C:\Users\shivr\Downloads\BDA project"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r ".\BDA project\requirements.txt"
```

### Frontend setup and startup

In PowerShell Terminal 2:

```powershell
cd "C:\Users\shivr\Downloads\BDA project\BDA project\frontend"
npm install
npm run dev
```

### Local URLs

- Frontend: [http://localhost:5173](http://localhost:5173)
- FastAPI Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
- Backend health: [http://localhost:8000/api/health](http://localhost:8000/api/health)

The frontend and backend run in separate terminals. The offline PySpark pipeline is run separately and writes persisted outputs used by the historical APIs.

---

## 19. Pipeline Execution

To reproduce the complete analytics and modeling pipeline from scratch, execute the following modules in sequence from the project root:

```bash
# 1. Validate raw traffic dataset
python -m src.ingestion.validate_real_traffic_data

# 2. Preprocess traffic data
python -m src.preprocessing.preprocess_real_traffic

# 3. Tag corridors
python -m src.corridor.tag_real_traffic_corridors

# 4. Generate synthetic context files (if needed)
python -m src.ingestion.generate_synthetic_data

# 5. Integrate traffic data with holiday/festival calendar
python -m src.ingestion.integrate_data

# 6. Run Spark SQL descriptive analytics
python -m src.analytics.spark_sql_analysis

# 7. Train Decision Tree baseline model
python -m src.prediction.train_decision_tree

# 8. Train Random Forest benchmark model
python -m src.prediction.benchmark_random_forest

# 9. Generate predictions and rule-based advisories
python -m src.advisory.prediction_advisory_pipeline

# 10. Generate static visualization charts
python -m src.visualization.create_visualizations
```

---

## 20. Validation

The analytics pipeline, backend APIs, and browser application have undergone project validation:

- **Compilation**: Clean compilation of all Python modules without syntax or import errors.
- **Runtime Health**: Dashboard health endpoint (`_stcore/health`) and UI load confirmed with HTTP 200.
- **Chronological Split**: Verified 7,145 training rows and 1,791 test rows with strictly ordered date ranges.
- **Matrix Consistency**: Test confusion matrices verified against summary evaluations.
- **Per-Class Metrics**: Precision, Recall, and F1 calculations verified mathematically to 6 decimal places.
- **Feature Importance**: Verified that all 12 feature groups are populated and sum to 1.0 within numerical tolerance.
- **Defensive Edge Cases**: Verified graceful handling of empty date selections, zero-record scenario filters, and missing artifacts.

---

## 21. Limitations

- **Batch Granularity**: Observations are aggregated at the daily level; hourly congestion fluctuations are not captured.
- **Offline Classification**: The machine learning model performs contemporaneous historical classification rather than real-time prediction.
- **Absence of GPS Coordinates**: The dataset lacks validated coordinates; spatial views are corridor-based rather than map-based.
- **Descriptive Scenario Analysis**: Scenario comparisons reflect historical associations, not causal relationships.
- **Heuristic Advisory Rules**: Operational recommendations are derived from fixed rules and do not account for municipal budget, personnel availability, or real-time road closures.
- **Windows Spark Serialization**: Native Spark ML models cannot be persisted directly on Windows without winutils; portable JSON specifications are used instead.

---

## 22. Future Scope

- **Geospatial Coordinate Enrichment**: Integrating verified GIS shapefiles or coordinates for Bengaluru's road network.
- **Time-Series Forecasting**: Developing sequence models (e.g., LSTM, Prophet, ARIMA) on high-frequency hourly sensor feeds.
- **Live Traffic API Ingestion**: Transitioning from batch historical CSVs to real-time streaming ingestion via Kafka and Spark Structured Streaming.
- **Network-Level Routing**: Integrating graph-based routing algorithms (e.g., GraphX) to model spillover congestion across adjacent corridors.
- **Dynamic Resource Optimization**: Coupling advisory outputs with linear programming or reinforcement learning for automated traffic personnel scheduling.
