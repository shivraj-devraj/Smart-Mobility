"""Unit tests for the open-source Smart Route Recommendation module (OSRM + OpenStreetMap + Folium)."""

from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock, patch
import urllib.error

from src.route import (
    LocationPoint,
    Route,
    create_route_map,
    evaluate_and_recommend_routes,
    fetch_osrm_routes,
    format_duration,
    geocode_location,
    clear_geocode_cache,
    search_location_suggestions,
    parse_osrm_routes,
    render_map_html,
)


class TestOpenSourceSmartRoute(unittest.TestCase):
    """Test suite verifying Nominatim geocoding, OSRM routing, recommendation logic, and Folium maps."""

    def setUp(self):
        clear_geocode_cache()

    def test_format_duration(self):
        self.assertEqual(format_duration(0), "0 min")
        self.assertEqual(format_duration(45), "1 min")
        self.assertEqual(format_duration(1134), "19 min")
        self.assertEqual(format_duration(3600), "1 hr")
        self.assertEqual(format_duration(4320), "1 hr 12 min")

    def test_geocode_input_validation(self):
        loc, err = geocode_location("")
        self.assertIsNone(loc)
        self.assertIn("Location query must not be empty", err)

        loc, err = geocode_location("   ")
        self.assertIsNone(loc)
        self.assertIn("Location query must not be empty", err)

    @patch("urllib.request.urlopen")
    def test_geocode_success(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.status = 200
        mock_payload = [
            {
                "lat": "12.935737",
                "lon": "77.624081",
                "display_name": "Koramangala, Bengaluru, Karnataka, India",
            }
        ]
        mock_response.read.return_value = json.dumps(mock_payload).encode("utf-8")
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        loc, err = geocode_location("Koramangala, Bengaluru")
        self.assertIsNone(err)
        self.assertIsNotNone(loc)
        self.assertEqual(loc.lat, 12.935737)
        self.assertEqual(loc.lon, 77.624081)
        self.assertIn("Koramangala", loc.display_name)

    @patch("urllib.request.urlopen")
    def test_location_suggestions_use_bengaluru_focused_nominatim_search(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = json.dumps([
            {
                "lat": "12.935737",
                "lon": "77.624081",
                "display_name": "Koramangala, Bengaluru, Karnataka, India",
            },
            {
                "lat": "12.934000",
                "lon": "77.623000",
                "display_name": "Koramangala 1st Block, Bengaluru, Karnataka, India",
            },
        ]).encode("utf-8")
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        suggestions, error = search_location_suggestions("Kor")

        self.assertIsNone(error)
        self.assertEqual(len(suggestions), 2)
        self.assertEqual(suggestions[0].lat, 12.935737)
        request = mock_urlopen.call_args.args[0]
        from urllib.parse import parse_qs, urlparse

        params = parse_qs(urlparse(request.full_url).query)
        self.assertEqual(params["q"], ["Kor, Bengaluru, Karnataka, India"])
        self.assertEqual(params["format"], ["json"])
        self.assertEqual(params["limit"], ["5"])
        self.assertEqual(params["addressdetails"], ["1"])
        self.assertEqual(params["countrycodes"], ["in"])

    @patch("urllib.request.urlopen")
    def test_geocode_zero_results(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = json.dumps([]).encode("utf-8")
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        loc, err = geocode_location("NonExistentPlaceXYZ123")
        self.assertIsNone(loc)
        self.assertIn("could not be resolved", err)

    @patch("urllib.request.urlopen")
    def test_geocode_http_error(self, mock_urlopen):
        http_error = urllib.error.HTTPError(
            url="https://nominatim.openstreetmap.org",
            code=503,
            msg="Service Unavailable",
            hdrs={},
            fp=None,
        )
        mock_urlopen.side_effect = http_error

        loc, err = geocode_location("Whitefield, Bengaluru")
        self.assertIsNone(loc)
        self.assertIn("HTTP error 503", err)

    def test_fetch_osrm_input_validation(self):
        loc = LocationPoint(query="Test", display_name="Test", lat=12.9, lon=77.6)
        data, err = fetch_osrm_routes(None, loc)
        self.assertIsNone(data)
        self.assertIn("Origin location point is required", err)

        data, err = fetch_osrm_routes(loc, None)
        self.assertIsNone(data)
        self.assertIn("Destination location point is required", err)

    @patch("urllib.request.urlopen")
    def test_fetch_osrm_routes_success(self, mock_urlopen):
        orig = LocationPoint(query="Koramangala", display_name="Koramangala", lat=12.9357, lon=77.6241)
        dest = LocationPoint(query="Whitefield", display_name="Whitefield", lat=12.9698, lon=77.7499)

        mock_response = MagicMock()
        mock_response.status = 200
        mock_payload = {
            "code": "Ok",
            "routes": [
                {
                    "distance": 17400.0,
                    "duration": 1140.0,
                    "legs": [{"summary": "HAL Old Airport Road"}],
                    "geometry": {
                        "coordinates": [[77.6241, 12.9357], [77.7499, 12.9698]]
                    },
                }
            ],
        }
        mock_response.read.return_value = json.dumps(mock_payload).encode("utf-8")
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        data, err = fetch_osrm_routes(orig, dest)
        self.assertIsNone(err)
        self.assertIsNotNone(data)
        self.assertEqual(data["code"], "Ok")
        self.assertEqual(len(data["routes"]), 1)

    @patch("urllib.request.urlopen")
    def test_fetch_osrm_routes_failure(self, mock_urlopen):
        orig = LocationPoint(query="A", display_name="A", lat=12.9, lon=77.6)
        dest = LocationPoint(query="B", display_name="B", lat=12.95, lon=77.65)

        mock_urlopen.side_effect = TimeoutError()

        data, err = fetch_osrm_routes(orig, dest, timeout_seconds=5)
        self.assertIsNone(data)
        self.assertIn("timed out after 5s", err)

    def test_parse_osrm_routes(self):
        raw_osrm = {
            "code": "Ok",
            "routes": [
                {
                    "distance": 18400.0,
                    "duration": 2280.0,
                    "legs": [{"summary": "HAL Old Airport Road"}],
                    "geometry": {
                        "coordinates": [[77.62, 12.93], [77.65, 12.94], [77.74, 12.96]]
                    },
                },
                {
                    "distance": 21200.0,
                    "duration": 2760.0,
                    "legs": [{"summary": "Outer Ring Road"}],
                    "geometry": {
                        "coordinates": [[77.62, 12.93], [77.68, 12.95], [77.74, 12.96]]
                    },
                },
            ],
        }

        routes = parse_osrm_routes(raw_osrm)
        self.assertEqual(len(routes), 2)

        r1 = routes[0]
        self.assertEqual(r1.route_index, 1)
        self.assertEqual(r1.summary, "HAL Old Airport Road")
        self.assertEqual(r1.distance_km, 18.4)
        self.assertEqual(r1.duration_formatted, "38 min")
        # Notice coordinates are converted from [lon, lat] to (lat, lon)
        self.assertEqual(r1.coordinates[0], (12.93, 77.62))

        r2 = routes[1]
        self.assertEqual(r2.route_index, 2)
        self.assertEqual(r2.summary, "Outer Ring Road")
        self.assertEqual(r2.distance_km, 21.2)
        self.assertEqual(r2.duration_formatted, "46 min")

    def test_evaluate_and_recommend_single_route(self):
        r1 = Route(
            route_index=1,
            summary="via Varthur Road",
            distance_meters=17400.0,
            distance_km=17.4,
            duration_seconds=1200.0,
            duration_formatted="20 min",
            coordinates=[(12.93, 77.62), (12.96, 77.74)],
        )

        ranked, rationale = evaluate_and_recommend_routes([r1])
        self.assertEqual(len(ranked), 1)
        self.assertEqual(ranked[0].status, "Available Route")
        self.assertIn("Only one route was returned", rationale)

    def test_evaluate_and_recommend_multiple_routes(self):
        r1 = Route(
            route_index=1,
            summary="HAL Old Airport Road",
            distance_meters=18400.0,
            distance_km=18.4,
            duration_seconds=2280.0,  # 38 min
            duration_formatted="38 min",
            coordinates=[(12.93, 77.62), (12.96, 77.74)],
        )
        r2 = Route(
            route_index=2,
            summary="Outer Ring Road",
            distance_meters=21200.0,
            distance_km=21.2,
            duration_seconds=2760.0,  # 46 min
            duration_formatted="46 min",
            coordinates=[(12.93, 77.62), (12.98, 77.74)],
        )

        # Pass in reverse order to verify sorting
        ranked, rationale = evaluate_and_recommend_routes([r2, r1])
        self.assertEqual(len(ranked), 2)
        self.assertEqual(ranked[0].summary, "HAL Old Airport Road")
        self.assertEqual(ranked[0].status, "Recommended")
        self.assertEqual(ranked[1].status, "Alternative")
        self.assertIn("lowest estimated routing duration", rationale)
        self.assertIn("saving approximately", rationale)

    def test_create_route_map_and_html(self):
        orig = LocationPoint(query="Koramangala", display_name="Koramangala", lat=12.9357, lon=77.6241)
        dest = LocationPoint(query="Whitefield", display_name="Whitefield", lat=12.9698, lon=77.7499)
        r1 = Route(
            route_index=1,
            summary="HAL Old Airport Road",
            distance_meters=17400.0,
            distance_km=17.4,
            duration_seconds=1140.0,
            duration_formatted="19 min",
            coordinates=[(12.9357, 77.6241), (12.9500, 77.6800), (12.9698, 77.7499)],
            status="Recommended",
        )

        folium_map = create_route_map(orig, dest, [r1])
        html_code = render_map_html(folium_map)

        self.assertIn("leaflet", html_code.lower())
        self.assertIn("OpenStreetMap", html_code)
        self.assertIn("HAL Old Airport Road", html_code)

    def test_dashboard_integration_apptest_default_load(self):
        """Verify dashboard loads smoothly without external API keys or exceptions."""
        from streamlit.testing.v1 import AppTest

        at = AppTest.from_file("dashboard/app.py")
        at.run(timeout=30)
        self.assertEqual(len(at.exception), 0)

        # Check all headers 1 to 9 exist
        headers = [h.value for h in at.header]
        self.assertIn("1. Overview KPIs", headers)
        self.assertIn("2. Historical Congestion", headers)
        self.assertIn("3. Corridor Analysis", headers)
        self.assertIn("4. Historical Scenario Analysis", headers)
        self.assertIn("5. ML Prediction", headers)
        self.assertIn("6. Rule-Based Traffic Advisory", headers)
        self.assertIn("7. Context Analysis", headers)
        self.assertIn("8. Key Observations", headers)
        self.assertIn("9. Smart Route Recommendation", headers)

        # Verify default inputs are present and enabled
        inputs = [(ti.label, ti.value, ti.disabled) for ti in at.text_input]
        self.assertTrue(any(item[0] == "Origin" and not item[2] for item in inputs))
        self.assertTrue(any(item[0] == "Destination" and not item[2] for item in inputs))

    @patch("src.route.routing.fetch_osrm_routes")
    @patch("src.route.geocoding.geocode_location")
    def test_dashboard_integration_find_routes_flow(self, mock_geocode, mock_fetch_osrm):
        """Verify Section 9 executes open-source routing flow cleanly."""
        from streamlit.testing.v1 import AppTest

        mock_orig = LocationPoint(
            query="Koramangala, Bengaluru",
            display_name="Koramangala, Bengaluru, Karnataka, India",
            lat=12.9357,
            lon=77.6241,
        )
        mock_dest = LocationPoint(
            query="Whitefield, Bengaluru",
            display_name="Whitefield, Bengaluru, Karnataka, India",
            lat=12.9698,
            lon=77.7499,
        )

        def geocode_side_effect(q, **kwargs):
            if "Koramangala" in q:
                return mock_orig, None
            return mock_dest, None

        mock_geocode.side_effect = geocode_side_effect

        mock_osrm_payload = {
            "code": "Ok",
            "routes": [
                {
                    "distance": 17400.0,
                    "duration": 1140.0,
                    "legs": [{"summary": "HAL Old Airport Road"}],
                    "geometry": {
                        "coordinates": [[77.6241, 12.9357], [77.7499, 12.9698]]
                    },
                }
            ],
        }
        mock_fetch_osrm.return_value = (mock_osrm_payload, None)

        at = AppTest.from_file("dashboard/app.py")
        at.run(timeout=30)
        self.assertEqual(len(at.exception), 0)

        # Click the Find Routes button
        at.button(key="btn_find_osm_routes").click().run(timeout=30)
        self.assertEqual(len(at.exception), 0)

        # Confirm success banner appears
        success_banners = [s.value for s in at.success]
        self.assertTrue(any("Available Route" in s or "Recommended Route" in s for s in success_banners))

        # Confirm dataframes count includes the comparison table
        self.assertGreaterEqual(len(at.dataframe), 5)


if __name__ == "__main__":
    unittest.main()
