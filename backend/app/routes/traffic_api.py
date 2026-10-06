"""HTTP endpoints for persisted historical traffic summaries."""

from fastapi import APIRouter, HTTPException, Query

from backend.app.schemas.traffic import (
    CorridorSummariesResponse,
    CorridorSummary,
    DayOfWeekTrafficResponse,
    DayTypeTrafficResponse,
    HighCongestionCorridorsResponse,
)
from backend.app.services.traffic_service import (
    TrafficDataError,
    get_corridor_summary,
    load_day_of_week_congestion_summary,
    load_day_type_congestion_summary,
    load_high_congestion_corridors,
    load_corridor_summaries,
)

router = APIRouter(prefix="/api/traffic", tags=["traffic"])


def _raise_data_error(error: TrafficDataError) -> None:
    raise HTTPException(status_code=500, detail=str(error)) from error


@router.get("/corridors", response_model=CorridorSummariesResponse)
def list_corridors() -> CorridorSummariesResponse:
    try:
        corridors = load_corridor_summaries()
    except TrafficDataError as error:
        _raise_data_error(error)
    return CorridorSummariesResponse(count=len(corridors), corridors=corridors)


@router.get("/corridors/{corridor}", response_model=CorridorSummary)
def read_corridor(corridor: str) -> CorridorSummary:
    try:
        summary = get_corridor_summary(corridor)
    except TrafficDataError as error:
        _raise_data_error(error)
    if summary is None:
        raise HTTPException(status_code=404, detail=f"Corridor not found: {corridor}")
    return summary


@router.get(
    "/high-congestion-corridors",
    response_model=HighCongestionCorridorsResponse,
)
def list_high_congestion_corridors() -> HighCongestionCorridorsResponse:
    try:
        corridors = load_high_congestion_corridors()
    except TrafficDataError as error:
        _raise_data_error(error)
    return HighCongestionCorridorsResponse(count=len(corridors), corridors=corridors)


@router.get(
    "/temporal",
    response_model=DayTypeTrafficResponse | DayOfWeekTrafficResponse,
)
def read_temporal_summary(
    dimension: str = Query(..., description="Historical summary dimension."),
) -> DayTypeTrafficResponse | DayOfWeekTrafficResponse:
    if dimension == "day-type":
        try:
            rows = load_day_type_congestion_summary()
        except TrafficDataError as error:
            _raise_data_error(error)
        return DayTypeTrafficResponse(
            dimension="day-type",
            count=len(rows),
            rows=rows,
        )
    if dimension == "day-of-week":
        try:
            rows = load_day_of_week_congestion_summary()
        except TrafficDataError as error:
            _raise_data_error(error)
        return DayOfWeekTrafficResponse(
            dimension="day-of-week",
            count=len(rows),
            rows=rows,
        )
    raise HTTPException(
        status_code=400,
        detail="Unsupported temporal dimension. Use 'day-type' or 'day-of-week'.",
    )
