# Phase 4 Data Integration

## Provenance

- **PRIMARY REAL DATA:** `data/processed/real_traffic_corridor_tagged.csv`, derived from the validated public Bengaluru traffic dataset.
- **REAL/CURATED SUPPLEMENTARY DATA:** `data/raw/real/karnataka_holidays_2022_2024.csv`, a manually curated project input based on published Karnataka Government holiday information. It is not an official government dataset.
- **SYNTHETIC SUPPLEMENTARY DATA:** `data/raw/synthetic/toll.csv`, `signal.csv`, and `festival_calendar.csv`. These files are development/testing data only and must never be presented as official Bengaluru traffic, FASTag, signal-event, or festival records.
- Files under `data/raw/` remain immutable.

## Compatibility Inspection

The inspected schemas and key observations were:

| Source | Key fields | Compatibility result |
| --- | --- | --- |
| Primary traffic | `date`, `area`, `road_intersection`, `corridor`, traffic measures | Date-level primary records; 8,936 rows. |
| Curated Karnataka calendar | `date`, `festival_name`, `festival_flag`, `holiday_flag`, `source` | Date key is compatible. One row per date; 44 rows. All 44 dates overlap the primary traffic date range. |
| Synthetic toll | `timestamp`, `toll_plaza`, `vehicle_count`, `transaction_count` | Timestamp-level, synthetic toll names, no aligned real corridor key, and no overlapping dates. Kept separate. |
| Synthetic signal | `timestamp`, `junction`, `signal_status` | Timestamp-level, synthetic junction names, no aligned real junction/corridor key, and no overlapping dates. Kept separate. |

The primary traffic dates are `2022-01-01` through `2024-08-09`. The curated calendar dates are `2022-01-15` through `2024-07-17`; all 44 calendar dates overlap the primary traffic date range.

No direction field is available in any compatible source. No hour-level join is attempted because the primary source is date-only. Toll transactions and signal events are not joined because no reliable real-to-synthetic location/time key exists.

## Integration Rule

`integrate_data.py` performs a left join from the primary traffic dataset to the one-row-per-date curated calendar:

```text
primary.date = festival_calendar.date
```

The left join preserves every primary traffic record. Duplicate calendar dates are checked and cause a clear failure before joining, preventing accidental row multiplication. `festival_flag` and `holiday_flag` use the calendar values when a date matches and `false` otherwise. `festival_name` is retained for matched dates and is null for unmatched primary dates.

## Output

The compatible integration is written to:

```text
data/processed/integrated_traffic_data.csv
```

The output retains all primary traffic fields and adds `festival_flag`, `festival_name`, and `holiday_flag`. Toll and signal files remain separate synthetic supplementary inputs; the synthetic festival calendar is also retained separately and is not used for this integration.

## Validation Result

Validation is printed by the integration module and checks:

- Traffic input rows: `8,936`
- Curated calendar input rows: `44`
- Toll input rows: `2,912`
- Signal input rows: `6,552`
- Integrated output rows: `8,936`
- Duplicate calendar date keys: `0`
- Duplicate integrated `(date, corridor)` keys: `0`
- Festival and holiday flag distributions, festival-name non-null count, unique festival names, and complete null counts
- Unique corridors: `16`

## Run

From the project root:

```text
python -m src.ingestion.integrate_data
```

This phase does not implement Spark SQL analytics, MLlib, prediction, advisory logic, dashboards, visualization, streaming, or live APIs.
