"""Typed responses for persisted historical corridor advisories."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


CongestionClass = Literal["Low", "Medium", "High"]


class CongestionAction(BaseModel):
    congestion_class: CongestionClass
    advisory_level: str
    recommendation: str
    personnel_action: str
    diversion_action: str
    roadwork_action: str
    record_count: int = Field(ge=0)


class HistoricalContextCounts(BaseModel):
    festival: int = Field(ge=0)
    holiday: int = Field(ge=0)
    roadwork: int = Field(ge=0)
    rain_or_fog: int = Field(ge=0)


class CorridorAdvisoryResponse(BaseModel):
    corridor: str
    record_count: int = Field(gt=0)
    date_start: date
    date_end: date
    congestion_actions: list[CongestionAction]
    context_counts: HistoricalContextCounts
