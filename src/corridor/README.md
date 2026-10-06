# Phase 3 Corridor Tagging

## Purpose

Corridor tagging provides a stable identifier for grouping records that share the same observed area and road/intersection location. It makes later corridor-level work possible without inventing geography or traffic metadata.

## Source and Output

- Input: `data/processed/real_traffic_preprocessed.csv`
- Output: `data/processed/real_traffic_corridor_tagged.csv`
- Raw data under `data/raw/` is not read for modification and is not changed.

## Observed Location Values

The processed dataset contains these 8 areas:

- `Electronic City`
- `Hebbal`
- `Indiranagar`
- `Jayanagar`
- `Koramangala`
- `M.G. Road`
- `Whitefield`
- `Yeshwanthpur`

It contains these 16 road/intersection values:

- `100 Feet Road`
- `Anil Kumble Circle`
- `Ballari Road`
- `CMH Road`
- `Hebbal Flyover`
- `Hosur Road`
- `ITPL Main Road`
- `Jayanagar 4th Block`
- `Marathahalli Bridge`
- `Sarjapur Road`
- `Silk Board Junction`
- `Sony World Junction`
- `South End Circle`
- `Trinity Circle`
- `Tumkur Road`
- `Yeshwanthpur Circle`

There are 16 distinct area-road pairs in the input.

## Corridor Rule

No semantic corridor mapping is required because the source provides meaningful location names but no supported corridor identifier. The rule is stored in `config/corridor_mapping.json` and is:

```text
corridor = area + " | " + road_intersection
```

For example, `Electronic City` and `Hosur Road` become `Electronic City | Hosur Road`. The original `area` and `road_intersection` columns remain unchanged.

No traffic direction, coordinates, GPS values, new road names, or unsupported junction information are created. Direction is unavailable and remains reserved for a later integration stage.

## Validation

`tag_real_traffic_corridors.py` reports input/output row counts, unique corridor count, corridor distribution, null corridor count, and sample area/road/corridor records.

Expected validation for the current input:

- Input rows: `8,936`
- Output rows: `8,936`
- Unique corridors: `16`
- Null corridor count: `0`

## Run

From the project root:

```text
python -m src.corridor.tag_real_traffic_corridors
```

This phase does not implement Spark SQL analytics, MLlib, prediction, advisory logic, dashboards, or visualization.
