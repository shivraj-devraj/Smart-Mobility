# Real Raw Dataset

`Banglore_traffic_Dataset.csv` is the real public Bengaluru traffic dataset used as the primary traffic and congestion data source for development.

The raw file must remain unchanged. The project does not rename columns, remove rows, fill missing values, normalize values, or create synthetic replacements for this file.

## Important Time Limitation

Date is stored in the raw dataset using yyyy-MM-dd format and has date-level granularity only. There is no hour or timestamp field. No hourly measurements are assumed or invented. Year, month, day-of-week, and weekend/weekday fields may be derived in a later phase, but hour-level analysis requires another legitimate time-based source.

Festival/holiday information and supplementary sources are handled separately in the synthetic development datasets under `data/raw/synthetic/`.

## Loading and Validation

From the project root:

```text
python -m src.ingestion.load_real_traffic_data
python -m src.ingestion.validate_real_traffic_data
```

The scripts use PySpark and preserve the exact 16 source column names. They are limited to loading, displaying, and validating the raw data; preprocessing, analytics, feature engineering, ML, prediction, advisory logic, and dashboards are outside this phase.