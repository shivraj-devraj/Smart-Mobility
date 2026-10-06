# Phase 5 Spark SQL Analytics

## Purpose

This module performs descriptive, batch analytics over the Phase 4 integrated traffic dataset using Spark SQL. It measures observed traffic and congestion patterns; it does not infer that festivals or holidays cause congestion.

## Source

The source is `data/processed/integrated_traffic_data.csv`, containing the real traffic records enriched with the manually curated Karnataka holiday and festival calendar. The curated calendar is a project input based on published Karnataka Government holiday information; it is not an official government dataset.

The module registers the typed source DataFrame as the temporary SQL view `traffic_data`. Dates are `DateType`, traffic measures are numeric, day-of-week is integer, and festival/holiday flags are boolean.

## SQL analyses

All analytical aggregations are SQL strings executed with `spark.sql(...)`:

- Corridor congestion summary, ordered by average congestion level descending.
- High-congestion corridor summary, ordered by high-congestion percentage descending.
- Weekday versus Weekend congestion summary.
- Festival-flagged versus non-festival traffic summary.
- Holiday versus non-holiday traffic summary.
- Day-of-week congestion summary, ordered by day number.
- Festival-date corridor analysis, including only corridors with festival records.
- Top five corridors by average congestion level.
- Top five corridors by high-congestion percentage.

These are analytical rankings only. No corridor is assigned an overall best or worst label.

## Outputs

Results are written under `data/output/`:

- `corridor_congestion_summary.csv`
- `high_congestion_corridors.csv`
- `day_type_congestion_summary.csv`
- `festival_congestion_summary.csv`
- `holiday_congestion_summary.csv`
- `day_of_week_congestion_summary.csv`
- `festival_corridor_analysis.csv`
- `top5_average_congestion_corridors.csv`
- `top5_high_congestion_percentage_corridors.csv`

The module prints each output schema, row count, and sample rows. It also verifies that the source contains exactly 8,936 rows and that the corridor summary contains exactly 16 corridors.

## Limitations and provenance

- Direction is unavailable in the source data.
- Hourly data is unavailable; this is date-level historical data.
- Toll and signal sources were not integrated because compatible keys were unavailable.
- Festival and holiday analysis is based on the curated calendar.
- The dataset is historical/batch data, not real-time traffic.
- Results describe observed associations and differences only. They do not establish causation, and no claim is made that festivals or holidays cause congestion.

This phase does not implement MLlib, train/test splitting, prediction, model evaluation, advisory rules, dashboards, charts, visualization, streaming, or APIs.

## Run

From the project root:

```powershell
python -m src.analytics.spark_sql_analysis
```
