"""Read persisted historical traffic summaries for the API."""

import csv
import math
from pathlib import Path

from backend.app.schemas.traffic import (
    CorridorSummary,
    DayOfWeekTrafficSummary,
    DayTypeTrafficSummary,
    HighCongestionCorridor,
)

CORRIDOR_COLUMNS = [
    "corridor",
    "record_count",
    "average_traffic_volume",
    "average_speed",
    "average_congestion_level",
    "average_travel_time_index",
    "low_congestion_count",
    "medium_congestion_count",
    "high_congestion_count",
]
INTEGER_COLUMNS = {
    "record_count",
    "low_congestion_count",
    "medium_congestion_count",
    "high_congestion_count",
}
FLOAT_COLUMNS = {
    "average_traffic_volume",
    "average_speed",
    "average_congestion_level",
    "average_travel_time_index",
}
HIGH_CONGESTION_COLUMNS = [
    "corridor",
    "total_records",
    "high_congestion_count",
    "high_congestion_percentage",
]
HIGH_CONGESTION_INTEGER_COLUMNS = {"total_records", "high_congestion_count"}
DAY_TYPE_COLUMNS = [
    "day_type",
    "record_count",
    "average_traffic_volume",
    "average_speed",
    "average_congestion_level",
    "average_travel_time_index",
    "high_congestion_count",
    "high_congestion_percentage",
]
DAY_OF_WEEK_COLUMNS = [
    "day_of_week",
    "record_count",
    "average_traffic_volume",
    "average_speed",
    "average_congestion_level",
    "high_congestion_percentage",
]
TEMPORAL_INTEGER_COLUMNS = {"record_count", "high_congestion_count"}
TEMPORAL_FLOAT_COLUMNS = {
    "average_traffic_volume",
    "average_speed",
    "average_congestion_level",
    "average_travel_time_index",
    "high_congestion_percentage",
}


class TrafficDataError(Exception):
    """An expected problem reading or validating the persisted traffic data."""


def corridor_summary_path() -> Path:
    """Resolve the project data path independently of the process working directory."""
    project_root = Path(__file__).resolve().parents[3]
    return project_root / "data" / "output" / "corridor_congestion_summary.csv"


def high_congestion_corridors_path() -> Path:
    """Resolve the persisted high-congestion summary independently of the working directory."""
    project_root = Path(__file__).resolve().parents[3]
    return project_root / "data" / "output" / "high_congestion_corridors.csv"


def day_type_congestion_summary_path() -> Path:
    """Resolve the persisted day-type summary independently of the working directory."""
    project_root = Path(__file__).resolve().parents[3]
    return project_root / "data" / "output" / "day_type_congestion_summary.csv"


def day_of_week_congestion_summary_path() -> Path:
    """Resolve the persisted day-of-week summary independently of the working directory."""
    project_root = Path(__file__).resolve().parents[3]
    return project_root / "data" / "output" / "day_of_week_congestion_summary.csv"


def load_corridor_summaries(path: Path | None = None) -> list[CorridorSummary]:
    """Load and validate the persisted corridor summaries without recalculating them."""
    source_path = path or corridor_summary_path()
    try:
        with source_path.open("r", newline="", encoding="utf-8-sig") as source_file:
            reader = csv.DictReader(source_file)
            if reader.fieldnames is None:
                raise TrafficDataError("Corridor summary CSV is empty or has no header.")

            missing_columns = [name for name in CORRIDOR_COLUMNS if name not in reader.fieldnames]
            if missing_columns:
                raise TrafficDataError(
                    "Corridor summary CSV is missing required columns: "
                    + ", ".join(missing_columns)
                    + "."
                )

            summaries: list[CorridorSummary] = []
            seen_corridors: set[str] = set()
            for row_number, row in enumerate(reader, start=2):
                if None in row:
                    raise TrafficDataError(f"Corridor summary CSV row {row_number} has extra fields.")
                if any(row.get(column) is None for column in CORRIDOR_COLUMNS):
                    raise TrafficDataError(f"Corridor summary CSV row {row_number} is incomplete.")

                corridor = row["corridor"]
                if not corridor:
                    raise TrafficDataError(f"Corridor summary CSV row {row_number} has an empty corridor.")
                if corridor in seen_corridors:
                    raise TrafficDataError(f"Corridor summary CSV contains duplicate corridor: {corridor}.")
                seen_corridors.add(corridor)

                values: dict[str, str | int | float] = {"corridor": corridor}
                for column in INTEGER_COLUMNS:
                    try:
                        values[column] = int(row[column])
                    except ValueError as error:
                        raise TrafficDataError(
                            f"Corridor summary CSV row {row_number} has an invalid integer in {column}."
                        ) from error
                for column in FLOAT_COLUMNS:
                    try:
                        values[column] = float(row[column])
                    except ValueError as error:
                        raise TrafficDataError(
                            f"Corridor summary CSV row {row_number} has an invalid number in {column}."
                        ) from error

                try:
                    summaries.append(CorridorSummary(**values))
                except (TypeError, ValueError) as error:
                    raise TrafficDataError(
                        f"Corridor summary CSV row {row_number} contains invalid values."
                    ) from error

    except FileNotFoundError as error:
        raise TrafficDataError("Corridor summary CSV was not found.") from error
    except TrafficDataError:
        raise
    except (OSError, UnicodeError, csv.Error) as error:
        raise TrafficDataError("Corridor summary CSV could not be read.") from error

    if not summaries:
        raise TrafficDataError("Corridor summary CSV contains no corridor records.")
    return summaries


def get_corridor_summary(corridor: str) -> CorridorSummary | None:
    """Find a persisted corridor record using exact string equality."""
    return next(
        (summary for summary in load_corridor_summaries() if summary.corridor == corridor),
        None,
    )


def load_high_congestion_corridors(
    path: Path | None = None,
) -> list[HighCongestionCorridor]:
    """Load the persisted high-congestion corridor metrics without recalculating them."""
    source_path = path or high_congestion_corridors_path()
    try:
        with source_path.open("r", newline="", encoding="utf-8-sig") as source_file:
            reader = csv.DictReader(source_file)
            if reader.fieldnames is None:
                raise TrafficDataError(
                    "High-congestion corridor CSV is empty or has no header."
                )

            missing_columns = [
                name for name in HIGH_CONGESTION_COLUMNS if name not in reader.fieldnames
            ]
            if missing_columns:
                raise TrafficDataError(
                    "High-congestion corridor CSV is missing required columns: "
                    + ", ".join(missing_columns)
                    + "."
                )

            corridors: list[HighCongestionCorridor] = []
            seen_corridors: set[str] = set()
            for row_number, row in enumerate(reader, start=2):
                if None in row:
                    raise TrafficDataError(
                        f"High-congestion corridor CSV row {row_number} has extra fields."
                    )
                if any(row.get(column) is None for column in HIGH_CONGESTION_COLUMNS):
                    raise TrafficDataError(
                        f"High-congestion corridor CSV row {row_number} is incomplete."
                    )

                corridor = row["corridor"]
                if not corridor:
                    raise TrafficDataError(
                        f"High-congestion corridor CSV row {row_number} has an empty corridor."
                    )
                if corridor in seen_corridors:
                    raise TrafficDataError(
                        f"High-congestion corridor CSV contains duplicate corridor: {corridor}."
                    )
                seen_corridors.add(corridor)

                values: dict[str, str | int | float] = {"corridor": corridor}
                for column in HIGH_CONGESTION_INTEGER_COLUMNS:
                    try:
                        values[column] = int(row[column])
                    except ValueError as error:
                        raise TrafficDataError(
                            f"High-congestion corridor CSV row {row_number} "
                            f"has an invalid integer in {column}."
                        ) from error
                try:
                    values["high_congestion_percentage"] = float(
                        row["high_congestion_percentage"]
                    )
                except ValueError as error:
                    raise TrafficDataError(
                        f"High-congestion corridor CSV row {row_number} "
                        "has an invalid number in high_congestion_percentage."
                    ) from error

                try:
                    corridors.append(HighCongestionCorridor(**values))
                except (TypeError, ValueError) as error:
                    raise TrafficDataError(
                        f"High-congestion corridor CSV row {row_number} contains invalid values."
                    ) from error

    except FileNotFoundError as error:
        raise TrafficDataError("High-congestion corridor CSV was not found.") from error
    except TrafficDataError:
        raise
    except (OSError, UnicodeError, csv.Error) as error:
        raise TrafficDataError("High-congestion corridor CSV could not be read.") from error

    if not corridors:
        raise TrafficDataError("High-congestion corridor CSV contains no corridor records.")
    return corridors


def _load_temporal_rows(
    source_path: Path,
    required_columns: list[str],
    integer_columns: set[str],
    float_columns: set[str],
    dimension_name: str,
) -> list[dict[str, str | int | float]]:
    """Read typed rows from one persisted temporal summary CSV."""
    try:
        with source_path.open("r", newline="", encoding="utf-8-sig") as source_file:
            reader = csv.DictReader(source_file)
            if reader.fieldnames is None:
                raise TrafficDataError(f"{dimension_name} CSV is empty or has no header.")

            missing_columns = [
                name for name in required_columns if name not in reader.fieldnames
            ]
            if missing_columns:
                raise TrafficDataError(
                    f"{dimension_name} CSV is missing required columns: "
                    + ", ".join(missing_columns)
                    + "."
                )

            rows: list[dict[str, str | int | float]] = []
            for row_number, row in enumerate(reader, start=2):
                if None in row:
                    raise TrafficDataError(
                        f"{dimension_name} CSV row {row_number} has extra fields."
                    )
                if any(row.get(column) in (None, "") for column in required_columns):
                    raise TrafficDataError(
                        f"{dimension_name} CSV row {row_number} is incomplete."
                    )

                values: dict[str, str | int | float] = {}
                for column in required_columns:
                    if column in integer_columns:
                        try:
                            values[column] = int(row[column])
                        except ValueError as error:
                            raise TrafficDataError(
                                f"{dimension_name} CSV row {row_number} "
                                f"has an invalid integer in {column}."
                            ) from error
                    elif column in float_columns:
                        try:
                            numeric_value = float(row[column])
                        except ValueError as error:
                            raise TrafficDataError(
                                f"{dimension_name} CSV row {row_number} "
                                f"has an invalid number in {column}."
                            ) from error
                        if not math.isfinite(numeric_value):
                            raise TrafficDataError(
                                f"{dimension_name} CSV row {row_number} "
                                f"has a non-finite number in {column}."
                            )
                        values[column] = numeric_value
                    else:
                        values[column] = row[column]
                rows.append(values)

    except FileNotFoundError as error:
        raise TrafficDataError(f"{dimension_name} CSV was not found.") from error
    except TrafficDataError:
        raise
    except (OSError, UnicodeError, csv.Error) as error:
        raise TrafficDataError(f"{dimension_name} CSV could not be read.") from error

    if not rows:
        raise TrafficDataError(f"{dimension_name} CSV contains no records.")
    return rows


def load_day_type_congestion_summary(
    path: Path | None = None,
) -> list[DayTypeTrafficSummary]:
    """Load persisted day-type analytics without recalculating any metric."""
    rows = _load_temporal_rows(
        path or day_type_congestion_summary_path(),
        DAY_TYPE_COLUMNS,
        TEMPORAL_INTEGER_COLUMNS,
        TEMPORAL_FLOAT_COLUMNS,
        "Day-type summary",
    )
    try:
        return [DayTypeTrafficSummary(**row) for row in rows]
    except (TypeError, ValueError) as error:
        raise TrafficDataError("Day-type summary CSV contains invalid values.") from error


def load_day_of_week_congestion_summary(
    path: Path | None = None,
) -> list[DayOfWeekTrafficSummary]:
    """Load persisted day-of-week analytics without recalculating any metric."""
    rows = _load_temporal_rows(
        path or day_of_week_congestion_summary_path(),
        DAY_OF_WEEK_COLUMNS,
        TEMPORAL_INTEGER_COLUMNS - {"high_congestion_count"},
        TEMPORAL_FLOAT_COLUMNS - {"average_travel_time_index"},
        "Day-of-week summary",
    )
    try:
        return [DayOfWeekTrafficSummary(**row) for row in rows]
    except (TypeError, ValueError) as error:
        raise TrafficDataError("Day-of-week summary CSV contains invalid values.") from error
