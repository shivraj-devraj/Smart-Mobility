"""Interactive OpenStreetMap and Leaflet visualization using Folium.

This module provides:
- Clean OpenStreetMap base layer map rendering
- Route polyline visualization with clear differentiation (Recommended vs Alternative)
- Origin ('A') and Destination ('B') marker placement with tooltips and popups
- Automatic bounding-box fitting to frame the entire route journey
- Self-contained HTML output for Streamlit components integration
"""

from __future__ import annotations

import logging
import folium

from .geocoding import LocationPoint
from .routing import Route

logger = logging.getLogger(__name__)


def create_route_map(
    origin: LocationPoint,
    destination: LocationPoint,
    routes: list[Route],
) -> folium.Map:
    """Generate an interactive OpenStreetMap Folium map for the calculated routes.

    Args:
        origin: Resolved origin LocationPoint.
        destination: Resolved destination LocationPoint.
        routes: List of Route objects returned and evaluated by OSRM.

    Returns:
        Configured folium.Map object.
    """
    # Determine center coordinates (default to Bengaluru center 12.9716, 77.5946 if empty)
    center_lat = (origin.lat + destination.lat) / 2.0
    center_lon = (origin.lon + destination.lon) / 2.0

    route_map = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=12,
        tiles="OpenStreetMap",
        control_scale=True,
    )

    all_points: list[tuple[float, float]] = [
        (origin.lat, origin.lon),
        (destination.lat, destination.lon),
    ]

    # Draw alternative routes first so recommended route displays on top
    sorted_for_drawing = sorted(
        routes,
        key=lambda r: 1 if r.status in ("Recommended", "Available Route") else 0,
    )

    for r in sorted_for_drawing:
        if not r.coordinates:
            continue

        all_points.extend(r.coordinates)
        is_rec = r.status in ("Recommended", "Available Route")

        line_color = "#1a73e8" if is_rec else "#6c757d"
        line_weight = 6 if is_rec else 4
        line_opacity = 0.9 if is_rec else 0.65
        dash = None if is_rec else "6, 6"

        popup_html = (
            f"<div style='font-size: 13px; font-family: sans-serif; line-height: 1.4;'>"
            f"<b>Route {r.route_index}: {r.summary}</b><br/>"
            f"<span style='color: {'#137333' if is_rec else '#5f6368'}; font-weight: bold;'>"
            f"[{r.status}]</span><br/>"
            f"Distance: <b>{r.distance_km} km</b><br/>"
            f"Estimated Duration: <b>{r.duration_formatted}</b><br/>"
            f"<small style='color: #666;'>Road-network estimate (OSRM)</small>"
            f"</div>"
        )

        tooltip_text = (
            f"Route {r.route_index} ({r.status}): {r.summary} — "
            f"{r.duration_formatted}, {r.distance_km} km"
        )

        folium.PolyLine(
            locations=r.coordinates,
            color=line_color,
            weight=line_weight,
            opacity=line_opacity,
            dash_array=dash,
            tooltip=tooltip_text,
            popup=folium.Popup(popup_html, max_width=300),
        ).add_to(route_map)

    # Origin marker (Green)
    folium.Marker(
        location=[origin.lat, origin.lon],
        tooltip=f"Origin: {origin.query}",
        popup=folium.Popup(
            f"<b>Origin:</b> {origin.query}<br/><small>{origin.display_name}</small>",
            max_width=280,
        ),
        icon=folium.Icon(color="green", icon="play", prefix="fa"),
    ).add_to(route_map)

    # Destination marker (Red)
    folium.Marker(
        location=[destination.lat, destination.lon],
        tooltip=f"Destination: {destination.query}",
        popup=folium.Popup(
            f"<b>Destination:</b> {destination.query}<br/><small>{destination.display_name}</small>",
            max_width=280,
        ),
        icon=folium.Icon(color="red", icon="flag-checkered", prefix="fa"),
    ).add_to(route_map)

    # Auto-fit bounds so the entire route is framed with clean padding
    if all_points:
        min_lat = min(p[0] for p in all_points)
        max_lat = max(p[0] for p in all_points)
        min_lon = min(p[1] for p in all_points)
        max_lon = max(p[1] for p in all_points)
        route_map.fit_bounds([[min_lat, min_lon], [max_lat, max_lon]], padding=[30, 30])

    return route_map


def render_map_html(route_map: folium.Map) -> str:
    """Render a Folium Map into self-contained HTML suitable for Streamlit components."""
    return route_map._repr_html_()
