"""Read and validate persisted historical corridor advisory rows."""

import csv
from datetime import date
from pathlib import Path

from backend.app.schemas.advisory import (
    CongestionAction,
    CorridorAdvisoryResponse,
    HistoricalContextCounts,
)

ADVISORY_COLUMNS = {
    "date",
    "corridor",
    "congestion_class",
    "festival_flag",
    "holiday_flag",
    "weather",
    "roadwork",
    "advisory_level",
    "recommendation",
    "personnel_action",
    "diversion_action",
    "roadwork_action",
}
ACTION_COLUMNS = (
    "advisory_level",
    "recommendation",
    "personnel_action",
    "diversion_action",
    "roadwork_action",
)
CONGESTION_CLASSES = ("Low", "Medium", "High")


class AdvisoryDataError(Exception):
    """The persisted advisory source is unavailable or invalid."""


def advisory_output_path() -> Path:
    """Resolve the persisted advisory output independently of process working directory."""
    project_root = Path(__file__).resolve().parents[3]
    return project_root / "data" / "output" / "advisory_output.csv"


def _parse_date(value: str, row_number: int) -> date:
    try:
        parsed_date = date.fromisoformat(value)
    except (TypeError, ValueError) as error:
        raise AdvisoryDataError(
            f"Advisory CSV row {row_number} has an invalid date."
        ) from error
    if parsed_date.isoformat() != value:
        raise AdvisoryDataError(f"Advisory CSV row {row_number} has an invalid date.")
    return parsed_date


def _parse_flag(value: str | None, column: str, row_number: int) -> bool:
    if value == "True":
        return True
    if value == "False":
        return False
    raise AdvisoryDataError(
        f"Advisory CSV row {row_number} has an invalid boolean in {column}."
    )


def get_corridor_advisory(
    corridor: str,
    path: Path | None = None,
) -> CorridorAdvisoryResponse:
    """Aggregate persisted rows for one exact corridor without recomputing advice."""
    if not corridor.strip():
        raise KeyError(corridor)

    source_path = path or advisory_output_path()
    try:
        with source_path.open("r", newline="", encoding="utf-8-sig") as source_file:
            reader = csv.DictReader(source_file)
            if reader.fieldnames is None:
                raise AdvisoryDataError("Advisory CSV is empty or has no header.")
            if len(reader.fieldnames) != len(set(reader.fieldnames)):
                raise AdvisoryDataError("Advisory CSV contains duplicate column names.")

            missing_columns = sorted(ADVISORY_COLUMNS - set(reader.fieldnames))
            if missing_columns:
                raise AdvisoryDataError(
                    "Advisory CSV is missing required columns: "
                    + ", ".join(missing_columns)
                    + "."
                )

            corridor_rows: list[dict[str, str | bool | date]] = []
            for row_number, row in enumerate(reader, start=2):
                if None in row:
                    raise AdvisoryDataError(
                        f"Advisory CSV row {row_number} has extra fields."
                    )
                if any(row.get(column) in (None, "") for column in ADVISORY_COLUMNS):
                    raise AdvisoryDataError(
                        f"Advisory CSV row {row_number} is incomplete."
                    )

                row_date = _parse_date(row["date"], row_number)
                if row["congestion_class"] not in CONGESTION_CLASSES:
                    raise AdvisoryDataError(
                        f"Advisory CSV row {row_number} has an unsupported congestion class."
                    )
                festival_flag = _parse_flag(row["festival_flag"], "festival_flag", row_number)
                holiday_flag = _parse_flag(row["holiday_flag"], "holiday_flag", row_number)
                if row["roadwork"] not in {"Yes", "No"}:
                    raise AdvisoryDataError(
                        f"Advisory CSV row {row_number} has an invalid value in roadwork."
                    )
                if not row["weather"]:
                    raise AdvisoryDataError(
                        f"Advisory CSV row {row_number} has an empty value in weather."
                    )

                if row["corridor"] == corridor:
                    corridor_rows.append(
                        {
                            **row,
                            "date": row_date,
                            "festival_flag": festival_flag,
                            "holiday_flag": holiday_flag,
                        }
                    )
    except FileNotFoundError as error:
        raise AdvisoryDataError("Advisory CSV was not found.") from error
    except AdvisoryDataError:
        raise
    except (OSError, UnicodeError, csv.Error) as error:
        raise AdvisoryDataError("Advisory CSV could not be read.") from error

    if not corridor_rows:
        raise KeyError(corridor)

    class_actions: dict[str, CongestionAction] = {}
    for congestion_class in CONGESTION_CLASSES:
        rows = [row for row in corridor_rows if row["congestion_class"] == congestion_class]
        if not rows:
            continue
        wording = tuple(rows[0][column] for column in ACTION_COLUMNS)
        if any(tuple(row[column] for column in ACTION_COLUMNS) != wording for row in rows[1:]):
            raise AdvisoryDataError(
                f"Advisory CSV contains conflicting actions for {congestion_class} "
                f"within corridor '{corridor}'."
            )
        class_actions[congestion_class] = CongestionAction(
            congestion_class=congestion_class,
            advisory_level=wording[0],
            recommendation=wording[1],
            personnel_action=wording[2],
            diversion_action=wording[3],
            roadwork_action=wording[4],
            record_count=len(rows),
        )

    context_counts = HistoricalContextCounts(
        festival=sum(row["festival_flag"] is True for row in corridor_rows),
        holiday=sum(row["holiday_flag"] is True for row in corridor_rows),
        roadwork=sum(row["roadwork"] == "Yes" for row in corridor_rows),
        rain_or_fog=sum(row["weather"] in {"Rain", "Fog"} for row in corridor_rows),
    )
    dates = [row["date"] for row in corridor_rows]

    return CorridorAdvisoryResponse(
        corridor=corridor,
        record_count=len(corridor_rows),
        date_start=min(dates),
        date_end=max(dates),
        congestion_actions=[
            class_actions[congestion_class]
            for congestion_class in CONGESTION_CLASSES
            if congestion_class in class_actions
        ],
        context_counts=context_counts,
    )
