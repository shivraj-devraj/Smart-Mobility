"""Adapt the existing route modules into validated API response models."""

import math

from backend.app.schemas.route import (
    LocationResponse,
    LocationSuggestion,
    RouteOption,
    RouteResponse,
)
from src.route.geocoding import LocationPoint, geocode_location, search_location_suggestions
from src.route.routing import (
    Route,
    evaluate_and_recommend_routes,
    fetch_osrm_routes,
    parse_osrm_routes,
)


class RouteServiceError(Exception):
    """An expected error that the HTTP layer can translate into an API response."""

    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def _validate_location(location: LocationPoint) -> None:
    if (
        not math.isfinite(location.lat)
        or not math.isfinite(location.lon)
        or not -90 <= location.lat <= 90
        or not -180 <= location.lon <= 180
    ):
        raise RouteServiceError(
            502,
            "INVALID_GEOCODING_RESPONSE",
            "Nominatim returned invalid location coordinates.",
        )


def _raise_geocoding_error(message: str) -> None:
    lowered_message = message.lower()
    if "timed out" in lowered_message or "timeout" in lowered_message:
        raise RouteServiceError(504, "GEOCODING_TIMEOUT", message)
    if "could not be resolved" in lowered_message or "not found" in lowered_message:
        raise RouteServiceError(404, "LOCATION_NOT_FOUND", message)
    raise RouteServiceError(502, "GEOCODING_SERVICE_ERROR", message)


def _raise_routing_error(message: str) -> None:
    lowered_message = message.lower()
    if "timed out" in lowered_message or "timeout" in lowered_message:
        raise RouteServiceError(504, "OSRM_TIMEOUT", message)
    if "no route" in lowered_message or "noroute" in lowered_message or "no drivable routes" in lowered_message:
        raise RouteServiceError(404, "ROUTE_NOT_FOUND", message)
    raise RouteServiceError(502, "OSRM_SERVICE_ERROR", message)


def _validate_routes(routes: list[Route]) -> None:
    for route in routes:
        if not math.isfinite(route.distance_km) or route.distance_km < 0:
            raise RouteServiceError(502, "INVALID_ROUTING_RESPONSE", "OSRM returned an invalid route distance.")
        if not math.isfinite(route.duration_seconds) or route.duration_seconds < 0:
            raise RouteServiceError(502, "INVALID_ROUTING_RESPONSE", "OSRM returned an invalid route duration.")
        if len(route.coordinates) < 2:
            raise RouteServiceError(502, "INVALID_ROUTING_RESPONSE", "OSRM returned route geometry with fewer than two points.")
        for latitude, longitude in route.coordinates:
            if (
                not math.isfinite(latitude)
                or not math.isfinite(longitude)
                or not -90 <= latitude <= 90
                or not -180 <= longitude <= 180
            ):
                raise RouteServiceError(502, "INVALID_ROUTING_RESPONSE", "OSRM returned invalid route coordinates.")


def _location_response(location: LocationPoint) -> LocationResponse:
    return LocationResponse(
        query=location.query,
        display_name=location.display_name,
        latitude=location.lat,
        longitude=location.lon,
    )


def _resolve_route_location(
    query: str,
    coordinates: tuple[float, float] | None,
    role: str,
) -> LocationPoint:
    if coordinates is not None:
        location = LocationPoint(
            query=query,
            display_name=query,
            lat=coordinates[0],
            lon=coordinates[1],
        )
        _validate_location(location)
        return location

    location, error = geocode_location(query)
    if error:
        _raise_geocoding_error(error)
    if location is None:
        raise RouteServiceError(
            502,
            "INVALID_GEOCODING_RESPONSE",
            f"Nominatim returned no {role} location.",
        )
    _validate_location(location)
    return location


def get_location_suggestions(query: str) -> list[LocationSuggestion]:
    """Return validated suggestions from the existing Nominatim provider."""
    locations, error = search_location_suggestions(query)
    if error:
        raise RouteServiceError(502, "GEOCODING_SERVICE_ERROR", "Nominatim location search is unavailable.")
    if locations is None:
        raise RouteServiceError(502, "GEOCODING_SERVICE_ERROR", "Nominatim returned no suggestion list.")

    suggestions = []
    for location in locations:
        _validate_location(location)
        suggestions.append(
            LocationSuggestion(
                display_name=location.display_name,
                latitude=location.lat,
                longitude=location.lon,
            )
        )
    return suggestions


def resolve_location_suggestion(query: str) -> LocationResponse:
    """Resolve a display-name hint to provider coordinates before accepting it."""
    location, error = geocode_location(query.strip())
    if error:
        _raise_geocoding_error(error)
    if location is None:
        raise RouteServiceError(
            502,
            "INVALID_GEOCODING_RESPONSE",
            "Nominatim returned no location for the selected suggestion.",
        )
    _validate_location(location)
    return _location_response(location)


def get_route_recommendation(
    origin_query: str,
    destination_query: str,
    origin_coordinates: tuple[float, float] | None = None,
    destination_coordinates: tuple[float, float] | None = None,
) -> RouteResponse:
    """Resolve two places and return routes ranked by the existing recommendation logic."""
    clean_origin = origin_query.strip()
    clean_destination = destination_query.strip()
    if not clean_origin:
        raise RouteServiceError(422, "EMPTY_ORIGIN", "Origin must not be empty.")
    if not clean_destination:
        raise RouteServiceError(422, "EMPTY_DESTINATION", "Destination must not be empty.")

    origin = _resolve_route_location(clean_origin, origin_coordinates, "origin")
    destination = _resolve_route_location(clean_destination, destination_coordinates, "destination")

    osrm_response, routing_error = fetch_osrm_routes(origin, destination)
    if routing_error:
        _raise_routing_error(routing_error)
    if not isinstance(osrm_response, dict) or osrm_response.get("code") != "Ok":
        raise RouteServiceError(502, "INVALID_ROUTING_RESPONSE", "OSRM returned an invalid routing response.")
    if not isinstance(osrm_response.get("routes"), list):
        raise RouteServiceError(502, "INVALID_ROUTING_RESPONSE", "OSRM response is missing a valid routes list.")
    if not osrm_response["routes"]:
        raise RouteServiceError(404, "ROUTE_NOT_FOUND", "OSRM returned no drivable routes.")

    try:
        parsed_routes = parse_osrm_routes(osrm_response)
        _validate_routes(parsed_routes)
        ranked_routes, rationale = evaluate_and_recommend_routes(parsed_routes)
    except RouteServiceError:
        raise
    except (AttributeError, IndexError, KeyError, TypeError, ValueError, OverflowError) as error:
        raise RouteServiceError(
            502,
            "INVALID_ROUTING_RESPONSE",
            "OSRM returned route data that could not be parsed.",
        ) from error

    if not ranked_routes:
        raise RouteServiceError(404, "ROUTE_NOT_FOUND", "OSRM returned no drivable routes.")

    route_options = [
        RouteOption(
            id=f"route_{route.route_index}",
            summary=route.summary,
            status=route.status,
            distance_km=route.distance_km,
            duration_minutes=round(route.duration_seconds / 60, 2),
            duration_formatted=route.duration_formatted,
            duration_basis="osrm_road_network_estimate",
            geometry=route.coordinates,
            recommendation_reason=route.recommendation_reason,
        )
        for route in ranked_routes
    ]
    recommended_route = next((route for route in route_options if route.status == "Recommended"), None)

    return RouteResponse(
        origin=_location_response(origin),
        destination=_location_response(destination),
        routes=route_options,
        recommended_route_id=recommended_route.id if recommended_route else None,
        alternatives_available=len(route_options) > 1,
        recommendation_rationale=rationale,
    )