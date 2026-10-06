# Phase 1 Raw Datasets

These files are **SYNTHETIC/DEMONSTRATION development data** created for this project.
They are not real Bengaluru traffic records, government data, FASTag records, or official festival data.
They must not be presented as real observations.

## Dataset Summary

### `traffic.csv`

One row represents a synthetic traffic observation at one junction at one timestamp.

| Column | Type | Meaning |
| --- | --- | --- |
| `timestamp` | Date/time | Observation time in `YYYY-MM-DD HH:MM:SS` format. |
| `junction` | Categorical | Synthetic junction name, including an indirect corridor name. |
| `traffic_volume` | Numeric | Synthetic vehicle count for the observation period. |
| `congestion_level` | Categorical | Synthetic category: `Low`, `Moderate`, `High`, or `Severe`. |
| `weather` | Categorical | Synthetic condition: `Clear`, `Cloudy`, `Light Rain`, or `Heavy Rain`. |
| `signal_status` | Categorical | Synthetic signal state: `Green`, `Yellow`, or `Red`. |

### `toll.csv`

One row represents synthetic toll/FASTag activity at one toll plaza at one timestamp.

| Column | Type | Meaning |
| --- | --- | --- |
| `timestamp` | Date/time | Activity time in `YYYY-MM-DD HH:MM:SS` format. |
| `toll_plaza` | Categorical | Synthetic toll plaza name. |
| `vehicle_count` | Numeric | Synthetic number of vehicles recorded. |
| `transaction_count` | Numeric | Synthetic number of toll transactions. |

### `signal.csv`

One row represents synthetic signal status information for one junction at one timestamp.

| Column | Type | Meaning |
| --- | --- | --- |
| `timestamp` | Date/time | Signal observation time in `YYYY-MM-DD HH:MM:SS` format. |
| `junction` | Categorical | Synthetic junction name. |
| `signal_status` | Categorical | Synthetic signal state: `Green`, `Yellow`, or `Red`. |

### `festival_calendar.csv`

One row represents one synthetic calendar date used for development demonstrations.

| Column | Type | Meaning |
| --- | --- | --- |
| `date` | Date | Calendar date in `YYYY-MM-DD` format. |
| `festival_name` | Categorical | Synthetic demonstration festival name, or `None`. |
| `is_festival` | Categorical boolean | `true` when the date is a synthetic festival date; otherwise `false`. |
| `is_holiday` | Categorical boolean | `true` when the date is a synthetic holiday date; otherwise `false`. |
| `day_type` | Categorical | One of `Normal Day`, `Friday Evening`, `Pre-Holiday`, `Post-Holiday`, or `Festival Day`. |

## Generation and Validation

Run these commands from the project root:

```text
python -m src.ingestion.generate_synthetic_data
python -m src.ingestion.validate_raw_data
```

The generator uses a fixed random seed and a moderate date range so repeated runs produce reproducible local development files without creating unnecessarily large datasets. The scripts use Python's built-in `csv` module; Pandas is not used as the main processing framework in this phase.
