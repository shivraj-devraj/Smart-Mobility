# Phase 2 Preprocessing Design

This module prepares the validated real Bengaluru traffic CSV for later phases. It does not implement ML, Spark SQL analytics, an advisory engine, a dashboard, or visualization.

## Source

The source is resolved from `config/data_sources.json`, which identifies `data/raw/real/Banglore_traffic_Dataset.csv` as the primary traffic dataset. The raw CSV is read-only and is never overwritten.

## Transformations

`preprocess_real_traffic.py` uses the existing SparkSession helper and performs only these transformations:

- Reads the real CSV with the existing explicit Spark schema.
- Ensures `Date` is Spark `DateType` using the `yyyy-MM-dd` format.
- Selects standardized analytical names for reliable source fields.
- Derives `day_of_week` from the date using Spark's numeric convention: Sunday `1` through Saturday `7`.
- Derives `day_type` as `Weekend` for Sunday/Saturday and `Weekday` for Monday-Friday.
- Creates `congestion_class` from the numeric `Congestion Level`.
- Writes the result to `data/processed/real_traffic_preprocessed.csv`. Spark performs the reading, transformations, and checks; standard-library CSV output keeps local Windows development independent of Hadoop `winutils.exe`.

No hour, timestamp, direction, festival, toll/FASTag, or signal-event fields are invented. The source has date-level granularity only, so hour-level analysis remains unavailable.

## Congestion Classification

The numeric distribution was inspected before selecting thresholds. The observed values were:

- Minimum: `5.16`
- Maximum: `100.0`
- `< 60`: `1,947` rows
- `60 to < 80`: `1,432` rows
- `80 to < 90`: `882` rows
- `90+`: `4,675` rows
- Upper quantiles were saturated at `100.0`.

The reviewable rules are stored in `config/preprocessing_config.json`:

- `Low`: `Congestion Level < 60.0`
- `Medium`: `60.0 <= Congestion Level < 90.0`
- `High`: `Congestion Level >= 90.0`

The `60.0` boundary preserves the observed lower band. The `90.0` boundary isolates the observed high-congestion tail, including the large group at the dataset maximum. The thresholds are configuration values and can be reviewed or changed without editing transformation code.

## Missing-Value Handling

Missing values are preserved. No rows are dropped, and no values are filled or replaced. If `Congestion Level` is missing, the derived `congestion_class` remains null. The script reports null counts for all standardized important columns.

## Run

From the project root:

```text
python -m src.preprocessing.preprocess_real_traffic
```

The command prints input/output row counts, the processed schema, congestion-class distribution, null counts, and sample rows. The output file is `data/processed/real_traffic_preprocessed.csv`.
