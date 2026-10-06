"""Pydantic response models for persisted historical traffic analytics."""

from typing import Literal

from pydantic import BaseModel, Field


class CorridorSummary(BaseModel):
    corridor: str
    record_count: int
    average_traffic_volume: float
    average_speed: float
    average_congestion_level: float
    average_travel_time_index: float
    low_congestion_count: int
    medium_congestion_count: int
    high_congestion_count: int


class CorridorSummariesResponse(BaseModel):
    count: int
    corridors: list[CorridorSummary]


class HighCongestionCorridor(BaseModel):
    corridor: str
    total_records: int = Field(ge=0)
    high_congestion_count: int = Field(ge=0)
    high_congestion_percentage: float = Field(ge=0, le=100)


class HighCongestionCorridorsResponse(BaseModel):
    count: int
    corridors: list[HighCongestionCorridor]


class DayTypeTrafficSummary(BaseModel):
    day_type: str
    record_count: int = Field(ge=0)
    average_traffic_volume: float
    average_speed: float
    average_congestion_level: float
    average_travel_time_index: float
    high_congestion_count: int = Field(ge=0)
    high_congestion_percentage: float = Field(ge=0, le=100)


class DayOfWeekTrafficSummary(BaseModel):
    day_of_week: int = Field(ge=1, le=7)
    record_count: int = Field(ge=0)
    average_traffic_volume: float
    average_speed: float
    average_congestion_level: float
    high_congestion_percentage: float = Field(ge=0, le=100)


class DayTypeTrafficResponse(BaseModel):
    dimension: Literal["day-type"]
    count: int
    rows: list[DayTypeTrafficSummary]


class DayOfWeekTrafficResponse(BaseModel):
    dimension: Literal["day-of-week"]
    count: int
    rows: list[DayOfWeekTrafficSummary]
