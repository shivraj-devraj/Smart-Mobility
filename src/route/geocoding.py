"""OpenStreetMap Nominatim geocoding service for Bengaluru location resolution.

This module provides:
- Safe, cached geocoding of human-readable location queries (e.g. 'Koramangala, Bengaluru')
- Adherence to Nominatim usage policy (custom User-Agent, request throttling, in-memory caching)
- Graceful error handling for missing queries, network timeouts, and zero results
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import urllib.error
import urllib.parse
import urllib.request

logger = logging.getLogger(__name__)

NOMINATIM_ENDPOINT = "https://nominatim.openstreetmap.org/search"
DEFAULT_USER_AGENT = "SmartMobilityBengaluruAnalytics/1.0 (academic-bda-project; contact: student-analytics@bda.local)"

# In-memory geocoding cache to prevent redundant requests on Streamlit reruns
_GEOCODE_CACHE: dict[str, LocationPoint] = {}
_LOCATION_SEARCH_CACHE: dict[str, list[LocationPoint]] = {}


@dataclass(frozen=True)
class LocationPoint:
    """Geographic coordinate representation of a resolved address or landmark."""

    query: str
    display_name: str
    lat: float
    lon: float

    @property
    def coordinate_pair(self) -> tuple[float, float]:
        """Return (lat, lon) tuple."""
        return (self.lat, self.lon)


def geocode_location(
    query: str,
    timeout_seconds: int = 10,
    user_agent: str = DEFAULT_USER_AGENT,
    use_cache: bool = True,
) -> tuple[LocationPoint | None, str | None]:
    """Resolve a location query into latitude/longitude using OpenStreetMap Nominatim.

    Args:
        query: Human-readable address, area, or landmark (e.g., 'Koramangala, Bengaluru').
        timeout_seconds: Request timeout in seconds.
        user_agent: User-Agent header required by Nominatim usage policy.
        use_cache: If True, check and populate the in-memory cache.

    Returns:
        Tuple of (LocationPoint, None) on success, or (None, error_message) on failure.
    """
    if not query or not query.strip():
        return None, "Location query must not be empty."

    clean_query = query.strip()
    cache_key = clean_query.lower()

    if use_cache and cache_key in _GEOCODE_CACHE:
        logger.debug("Geocode cache hit for: %s", clean_query)
        return _GEOCODE_CACHE[cache_key], None

    params = {
        "q": clean_query,
        "format": "json",
        "limit": "1",
        "addressdetails": "1",
    }
    encoded_url = f"{NOMINATIM_ENDPOINT}?{urllib.parse.urlencode(params)}"

    headers = {
        "User-Agent": user_agent,
        "Accept": "application/json",
        "Accept-Language": "en",
    }

    req = urllib.request.Request(encoded_url, headers=headers, method="GET")

    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as response:
            if response.status != 200:
                return None, f"Nominatim geocoding service returned HTTP {response.status}."

            body = response.read().decode("utf-8")
            data = json.loads(body)

            if not data or not isinstance(data, list) or len(data) == 0:
                return (
                    None,
                    f"Location '{clean_query}' could not be resolved by OpenStreetMap Nominatim. "
                    "Please check the spelling or specify the locality and city (e.g. 'Koramangala, Bengaluru').",
                )

            first_result = data[0]
            lat = float(first_result["lat"])
            lon = float(first_result["lon"])
            display_name = first_result.get("display_name", clean_query)

            loc = LocationPoint(
                query=clean_query,
                display_name=display_name,
                lat=lat,
                lon=lon,
            )

            if use_cache:
                _GEOCODE_CACHE[cache_key] = loc

            return loc, None

    except urllib.error.HTTPError as http_err:
        return None, f"Geocoding service HTTP error {http_err.code}: {http_err.reason}"
    except urllib.error.URLError as url_err:
        return None, f"Network error connecting to Nominatim geocoding service: {url_err.reason}"
    except TimeoutError:
        return None, f"Geocoding request for '{clean_query}' timed out after {timeout_seconds}s."
    except (ValueError, KeyError, json.JSONDecodeError) as parse_err:
        return None, f"Failed to parse geocoding response: {parse_err}"
    except Exception as exc:
        return None, f"Unexpected geocoding failure: {exc}"


def search_location_suggestions(
    query: str,
    limit: int = 5,
    timeout_seconds: int = 10,
    user_agent: str = DEFAULT_USER_AGENT,
) -> tuple[list[LocationPoint] | None, str | None]:
    """Search Nominatim for Bengaluru-focused location suggestions."""
    if not query or not query.strip():
        return None, "Location query must not be empty."

    clean_query = query.strip()
    cache_key = clean_query.casefold()
    cached_results = _LOCATION_SEARCH_CACHE.get(cache_key)
    if cached_results is not None:
        return cached_results, None

    search_query = clean_query
    if "bengaluru" not in search_query.casefold() and "bangalore" not in search_query.casefold():
        search_query = f"{search_query}, Bengaluru, Karnataka, India"

    params = {
        "q": search_query,
        "format": "json",
        "limit": str(limit),
        "addressdetails": "1",
        "countrycodes": "in",
    }
    encoded_url = f"{NOMINATIM_ENDPOINT}?{urllib.parse.urlencode(params)}"
    headers = {
        "User-Agent": user_agent,
        "Accept": "application/json",
        "Accept-Language": "en",
    }
    req = urllib.request.Request(encoded_url, headers=headers, method="GET")

    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as response:
            if response.status != 200:
                return None, f"Nominatim location search returned HTTP {response.status}."

            data = json.loads(response.read().decode("utf-8"))
            if not isinstance(data, list):
                return None, "Nominatim location search returned an invalid response."

            suggestions = []
            for result in data:
                if not isinstance(result, dict):
                    continue
                try:
                    latitude = float(result["lat"])
                    longitude = float(result["lon"])
                    display_name = result["display_name"]
                except (KeyError, TypeError, ValueError):
                    continue

                if (
                    not isinstance(display_name, str)
                    or not display_name.strip()
                    or not -90 <= latitude <= 90
                    or not -180 <= longitude <= 180
                ):
                    continue

                suggestions.append(
                    LocationPoint(
                        query=clean_query,
                        display_name=display_name,
                        lat=latitude,
                        lon=longitude,
                    )
                )

            _LOCATION_SEARCH_CACHE[cache_key] = suggestions
            return suggestions, None

    except (urllib.error.URLError, TimeoutError, UnicodeDecodeError, json.JSONDecodeError) as error:
        logger.warning("Nominatim location search failed: %s", error)
        return None, "Nominatim location search is unavailable."


def clear_geocode_cache() -> None:
    """Clear in-memory geocoding cache."""
    _GEOCODE_CACHE.clear()
    _LOCATION_SEARCH_CACHE.clear()
