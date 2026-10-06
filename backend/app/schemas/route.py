"""Pydantic response models for the Smart Route API."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    status: Literal["ok"]


class LocationResponse(BaseModel):
    query: str
    display_name: str
    latitude: float
    longitude: float


class LocationSuggestion(BaseModel):
    display_name: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class LocationSuggestionsResponse(BaseModel):
    suggestions: list[LocationSuggestion]


class RouteOption(BaseModel):
    id: str
    summary: str
    status: Literal["Recommended", "Alternative", "Available Route"]
    distance_km: float = Field(ge=0)
    duration_minutes: float = Field(ge=0)
    duration_formatted: str
    duration_basis: Literal["osrm_road_network_estimate"]
    geometry: list[tuple[float, float]] = Field(
        description="Actual OSRM route coordinates as [latitude, longitude] pairs."
    )
    recommendation_reason: str

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "id": "route_1",
            "summary": "HAL Old Airport Road",
            "status": "Recommended",
            "distance_km": 18.4,
            "duration_minutes": 38.0,
            "duration_formatted": "38 min",
            "duration_basis": "osrm_road_network_estimate",
            "geometry": [[12.93, 77.62], [12.94, 77.65]],
            "recommendation_reason": "Recommended using the existing route ranking logic.",
        }
    })


class RouteResponse(BaseModel):
    origin: LocationResponse
    destination: LocationResponse
    routes: list[RouteOption]
    recommended_route_id: str | None
    alternatives_available: bool
    recommendation_rationale: str


class RouteErrorDetail(BaseModel):
    code: str
    message: str


class RouteErrorResponse(BaseModel):
    detail: RouteErrorDetail