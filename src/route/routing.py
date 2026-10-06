"""Open-source OSRM routing client and transparent route recommendation engine.

This module provides:
- Driving route calculation using the Open Source Routing Machine (OSRM)
- GeoJSON geometry parsing into (latitude, longitude) coordinate paths for Leaflet/Folium
- Transparent, deterministic route comparison and recommendation based on estimated duration and distance
- Clear separation between road-network routing and historical Big Data analytics
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import logging
import urllib.error
import urllib.parse
import urllib.request

from .geocoding import LocationPoint

logger = logging.getLogger(__name__)

OSRM_ROUTE_ENDPOINT = "http://router.project-osrm.org/route/v1/driving"
DEFAULT_USER_AGENT = "SmartMobilityBengaluruAnalytics/1.0 (academic-bda-project)"


@dataclass
class Route:
    """Structured representation of a driving route computed by OSRM."""

    route_index: int
    summary: str
    distance_meters: float
    distance_km: float
    duration_seconds: float
    duration_formatted: str
    coordinates: list[tuple[float, float]] = field(default_factory=list)
    status: str = "Available Route"
    recommendation_reason: str = ""


def format_duration(seconds: float) -> str:
    """Format seconds into clean human-readable strings (e.g. '19 min', '1 hr 12 min')."""
    if seconds <= 0:
        return "0 min"
    minutes = max(1, round(seconds / 60))
    if minutes < 60:
        return f"{minutes} min"
    hours = minutes // 60
    rem_min = minutes % 60
    if rem_min == 0:
        return f"{hours} hr"
    return f"{hours} hr {rem_min} min"


def fetch_osrm_routes(
    origin: LocationPoint,
    destination: LocationPoint,
    timeout_seconds: int = 15,
    user_agent: str = DEFAULT_USER_AGENT,
) -> tuple[dict | None, str | None]:
    """Query OSRM driving service for routes between origin and destination coordinates.

    Args:
        origin: Resolved origin LocationPoint.
        destination: Resolved destination LocationPoint.
        timeout_seconds: Request timeout in seconds.
        user_agent: User-Agent header for the request.

    Returns:
        Tuple of (response_json_dict, None) on success, or (None, error_message) on failure.
    """
    if not origin:
        return None, "Origin location point is required."
    if not destination:
        return None, "Destination location point is required."

    # OSRM expects coordinates in lon,lat order separated by semicolons
    coords_param = f"{origin.lon},{origin.lat};{destination.lon},{destination.lat}"
    params = {
        "overview": "full",
        "geometries": "geojson",
        "alternatives": "true",
        "steps": "true",
    }
    url = f"{OSRM_ROUTE_ENDPOINT}/{coords_param}?{urllib.parse.urlencode(params)}"

    headers = {
        "User-Agent": user_agent,
        "Accept": "application/json",
    }

    req = urllib.request.Request(url, headers=headers, method="GET")

    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as response:
            if response.status != 200:
                return None, f"OSRM routing service returned HTTP {response.status}."

            body = response.read().decode("utf-8")
            data = json.loads(body)

            code = data.get("code")
            if code != "Ok":
                msg = data.get("message", "No route found.")
                return None, f"OSRM routing response: {code} - {msg}"

            routes = data.get("routes", [])
            if not routes:
                return None, "No drivable routes were found between the specified locations."

            return data, None

    except urllib.error.HTTPError as http_err:
        return None, f"OSRM routing service HTTP error {http_err.code}: {http_err.reason}"
    except urllib.error.URLError as url_err:
        return None, f"Network error connecting to OSRM routing service: {url_err.reason}"
    except TimeoutError:
        return None, f"OSRM routing calculation timed out after {timeout_seconds}s."
    except json.JSONDecodeError:
        return None, "Failed to parse OSRM JSON response."
    except Exception as exc:
        return None, f"Unexpected routing failure: {exc}"


def parse_osrm_routes(osrm_response: dict) -> list[Route]:
    """Parse raw OSRM JSON response into structured Route objects."""
    raw_routes = osrm_response.get("routes", [])
    parsed: list[Route] = []

    for idx, r in enumerate(raw_routes):
        dist_m = float(r.get("distance", 0.0))
        dist_km = round(dist_m / 1000.0, 1)
        dur_s = float(r.get("duration", 0.0))

        # Extract human-readable summary from legs or steps
        legs = r.get("legs", [])
        summary = ""
        if legs and isinstance(legs, list):
            summary = legs[0].get("summary", "").strip()
        if not summary:
            summary = f"Route {idx + 1}"

        # Parse GeoJSON coordinates: OSRM provides [lon, lat] -> convert to (lat, lon) for Folium
        coords: list[tuple[float, float]] = []
        geom = r.get("geometry", {})
        raw_coords = geom.get("coordinates", [])
        if isinstance(raw_coords, list):
            for pt in raw_coords:
                if len(pt) >= 2:
                    coords.append((float(pt[1]), float(pt[0])))

        route_obj = Route(
            route_index=idx + 1,
            summary=summary,
            distance_meters=dist_m,
            distance_km=dist_km,
            duration_seconds=dur_s,
            duration_formatted=format_duration(dur_s),
            coordinates=coords,
        )
        parsed.append(route_obj)

    return parsed


def evaluate_and_recommend_routes(routes: list[Route]) -> tuple[list[Route], str]:
    """Perform transparent, deterministic rule-based evaluation of returned OSRM routes.

    Recommendation Rules:
    1. If 0 routes: Return empty list with explanatory notice.
    2. If 1 route: Mark as 'Available Route'; note only one route was returned.
    3. If multiple routes:
       - Sort primarily by estimated duration (`duration_seconds`).
       - If durations are within 60 seconds (effectively equal), tie-break by shorter distance (`distance_meters`).
       - Top route is marked 'Recommended' with duration/distance comparison rationale.
       - Other routes are marked 'Alternative'.

    Data Integrity & Limitations:
    - OSRM computes routes using static OpenStreetMap road-network graphs and speed profiles.
    - This recommendation does NOT reflect live/current traffic or congestion.
    - This recommendation is NOT generated by the project's historical Spark ML model.

    Returns:
        Tuple of (ranked_routes_list, recommendation_rationale).
    """
    if not routes:
        return [], "No routes available to evaluate."

    if len(routes) == 1:
        single = routes[0]
        single.status = "Available Route"
        single.recommendation_reason = (
            f"Only one route was returned by the routing service via {single.summary}. "
            f"Estimated duration: {single.duration_formatted} ({single.distance_km} km)."
        )
        rationale = (
            f"**Available Route**: **{single.summary}** ({single.duration_formatted}, {single.distance_km} km). "
            "Only one route was returned by the routing service."
        )
        return [single], rationale

    # Multi-route deterministic ranking
    def sort_key(r: Route) -> tuple[int, float]:
        # Bucket duration into 60s windows to allow tie-breaking on physical distance
        dur_bucket = int(r.duration_seconds // 60)
        return (dur_bucket, r.distance_meters)

    sorted_routes = sorted(routes, key=sort_key)

    recommended = sorted_routes[0]
    recommended.status = "Recommended"

    # Compare with nearest alternative
    alt = sorted_routes[1]
    time_diff_sec = alt.duration_seconds - recommended.duration_seconds
    time_diff_min = round(time_diff_sec / 60)

    if time_diff_min > 0:
        recommended.recommendation_reason = (
            f"Recommended because it has the lowest estimated routing duration among the returned alternatives "
            f"(saves ~{time_diff_min} min vs alternative via {alt.summary})."
        )
        rationale = (
            f"**Recommended Route**: **{recommended.summary}**. "
            f"Recommended because it has the lowest estimated routing duration (**{recommended.duration_formatted}**, "
            f"{recommended.distance_km} km) among the returned alternatives, saving approximately "
            f"**{time_diff_min} minutes** compared to the next alternative (**{alt.summary}**, {alt.duration_formatted})."
        )
    else:
        dist_diff_km = round(alt.distance_km - recommended.distance_km, 1)
        recommended.recommendation_reason = (
            f"Recommended because it offers the optimal balance of estimated duration ({recommended.duration_formatted}) "
            f"and shorter travel distance ({recommended.distance_km} km)."
        )
        rationale = (
            f"**Recommended Route**: **{recommended.summary}**. "
            f"Estimated durations are comparable; recommended for shorter travel distance (**{recommended.distance_km} km** vs "
            f"{alt.distance_km} km on **{alt.summary}**)."
        )

    for r in sorted_routes[1:]:
        r.status = "Alternative"
        diff_s = r.duration_seconds - recommended.duration_seconds
        diff_m = round(diff_s / 60)
        dist_d = round(r.distance_km - recommended.distance_km, 1)
        r.recommendation_reason = (
            f"Alternative route via {r.summary} (+{diff_m} min, {dist_d:+} km vs Recommended)."
        )

    return sorted_routes, rationale
