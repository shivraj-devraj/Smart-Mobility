"""HTTP endpoints for Smart Route Recommendation."""

from fastapi import APIRouter, HTTPException, Query

from backend.app.schemas.route import (
    LocationResponse,
    LocationSuggestionsResponse,
    RouteErrorResponse,
    RouteResponse,
)
from backend.app.services.route_service import (
    RouteServiceError,
    get_location_suggestions,
    get_route_recommendation,
    resolve_location_suggestion,
)

router = APIRouter(prefix="/api", tags=["routes"])


@router.get(
    "/route",
    response_model=RouteResponse,
    responses={
        404: {"model": RouteErrorResponse, "description": "Location or drivable route not found."},
        422: {"model": RouteErrorResponse, "description": "Origin or destination is empty."},
        502: {"model": RouteErrorResponse, "description": "Geocoding, routing, or external response failure."},
        504: {"model": RouteErrorResponse, "description": "External service request timed out."},
    },
)
def get_route(
    origin: str = Query(alias="from", description="Starting address, area, or landmark."),
    destination: str = Query(alias="to", description="Destination address, area, or landmark."),
    origin_latitude: float | None = Query(default=None, ge=-90, le=90),
    origin_longitude: float | None = Query(default=None, ge=-180, le=180),
    destination_latitude: float | None = Query(default=None, ge=-90, le=90),
    destination_longitude: float | None = Query(default=None, ge=-180, le=180),
) -> RouteResponse:
    if (origin_latitude is None) != (origin_longitude is None):
        raise HTTPException(
            status_code=422,
            detail={"code": "INVALID_ORIGIN_COORDINATES", "message": "Origin latitude and longitude must be provided together."},
        )
    if (destination_latitude is None) != (destination_longitude is None):
        raise HTTPException(
            status_code=422,
            detail={"code": "INVALID_DESTINATION_COORDINATES", "message": "Destination latitude and longitude must be provided together."},
        )

    origin_coordinates = (
        (origin_latitude, origin_longitude)
        if origin_latitude is not None and origin_longitude is not None
        else None
    )
    destination_coordinates = (
        (destination_latitude, destination_longitude)
        if destination_latitude is not None and destination_longitude is not None
        else None
    )

    try:
        return get_route_recommendation(
            origin,
            destination,
            origin_coordinates,
            destination_coordinates,
        )
    except RouteServiceError as error:
        raise HTTPException(
            status_code=error.status_code,
            detail={"code": error.code, "message": error.message},
        ) from error


@router.get(
    "/geocoding/suggestions",
    response_model=LocationSuggestionsResponse,
    responses={502: {"model": RouteErrorResponse, "description": "Nominatim search failure."}},
)
def get_location_suggestions_endpoint(
    q: str = Query(min_length=3, max_length=200, description="Location search text."),
) -> LocationSuggestionsResponse:
    try:
        return LocationSuggestionsResponse(suggestions=get_location_suggestions(q.strip()))
    except RouteServiceError as error:
        raise HTTPException(
            status_code=error.status_code,
            detail={"code": error.code, "message": error.message},
        ) from error


@router.get(
    "/geocoding/resolve",
    response_model=LocationResponse,
    responses={
        404: {"model": RouteErrorResponse, "description": "Nominatim could not resolve the selected location."},
        502: {"model": RouteErrorResponse, "description": "Nominatim geocoding failure."},
        504: {"model": RouteErrorResponse, "description": "Nominatim request timed out."},
    },
)
def resolve_location_suggestion_endpoint(
    q: str = Query(min_length=3, max_length=200, description="Selected display name to resolve with Nominatim."),
) -> LocationResponse:
    try:
        return resolve_location_suggestion(q)
    except RouteServiceError as error:
        raise HTTPException(
            status_code=error.status_code,
            detail={"code": error.code, "message": error.message},
        ) from error