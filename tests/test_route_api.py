"""Tests for the FastAPI route adapter using mocked external service responses."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.app.main import app
from src.route.geocoding import LocationPoint


class TestRouteApi(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)
        self.origin = LocationPoint(
            query="Koramangala, Bengaluru",
            display_name="Koramangala, Bengaluru, Karnataka, India",
            lat=12.9357,
            lon=77.6241,
        )
        self.destination = LocationPoint(
            query="Whitefield, Bengaluru",
            display_name="Whitefield, Bengaluru, Karnataka, India",
            lat=12.9698,
            lon=77.7499,
        )

    def successful_geocode(self, query: str, **kwargs):
        return (self.origin if "Koramangala" in query else self.destination), None

    @staticmethod
    def osrm_payload() -> dict:
        return {
            "code": "Ok",
            "routes": [
                {
                    "distance": 18400.0,
                    "duration": 2280.0,
                    "legs": [{"summary": "HAL Old Airport Road"}],
                    "geometry": {"coordinates": [[77.62, 12.93], [77.65, 12.94], [77.74, 12.96]]},
                },
                {
                    "distance": 21200.0,
                    "duration": 2760.0,
                    "legs": [{"summary": "Outer Ring Road"}],
                    "geometry": {"coordinates": [[77.62, 12.93], [77.68, 12.95], [77.74, 12.96]]},
                },
            ],
        }

    def test_health(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_cors_allows_localhost_frontend(self):
        response = self.client.options(
            "/api/route",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["access-control-allow-origin"], "http://localhost:5173")

    def test_route_returns_actual_geometry_and_existing_ranking(self):
        with (
            patch("backend.app.services.route_service.geocode_location", side_effect=self.successful_geocode),
            patch("backend.app.services.route_service.fetch_osrm_routes", return_value=(self.osrm_payload(), None)),
        ):
            response = self.client.get(
                "/api/route",
                params={"from": "Koramangala, Bengaluru", "to": "Whitefield, Bengaluru"},
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["origin"]["latitude"], self.origin.lat)
        self.assertEqual(body["destination"]["longitude"], self.destination.lon)
        self.assertEqual(body["recommended_route_id"], "route_1")
        self.assertTrue(body["alternatives_available"])
        self.assertEqual(body["routes"][0]["geometry"][0], [12.93, 77.62])
        self.assertEqual(body["routes"][0]["duration_basis"], "osrm_road_network_estimate")

    def test_location_suggestions_return_nominatim_coordinates(self):
        with patch(
            "backend.app.services.route_service.search_location_suggestions",
            return_value=([self.origin, self.destination], None),
        ) as search:
            response = self.client.get("/api/geocoding/suggestions", params={"q": "Kor"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(search.call_args.args, ("Kor",))
        self.assertEqual(
            response.json()["suggestions"],
            [
                {
                    "display_name": self.origin.display_name,
                    "latitude": self.origin.lat,
                    "longitude": self.origin.lon,
                },
                {
                    "display_name": self.destination.display_name,
                    "latitude": self.destination.lat,
                    "longitude": self.destination.lon,
                },
            ],
        )

    def test_location_suggestions_hide_provider_errors(self):
        with patch(
            "backend.app.services.route_service.search_location_suggestions",
            return_value=(None, "Network detail that should not reach clients"),
        ):
            response = self.client.get("/api/geocoding/suggestions", params={"q": "Kor"})

        self.assertEqual(response.status_code, 502)
        self.assertEqual(
            response.json()["detail"]["message"],
            "Nominatim location search is unavailable.",
        )

    def test_static_locality_hint_resolves_using_nominatim_coordinates(self):
        with patch(
            "backend.app.services.route_service.geocode_location",
            return_value=(self.origin, None),
        ) as geocode:
            response = self.client.get(
                "/api/geocoding/resolve",
                params={"q": "Koramangala, Bengaluru"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(geocode.call_args.args, ("Koramangala, Bengaluru",))
        self.assertEqual(response.json()["display_name"], self.origin.display_name)
        self.assertEqual(response.json()["latitude"], self.origin.lat)
        self.assertEqual(response.json()["longitude"], self.origin.lon)

    def test_unresolvable_static_locality_hint_returns_error_without_coordinates(self):
        with patch(
            "backend.app.services.route_service.geocode_location",
            return_value=(None, "Location 'Unknown, Bengaluru' could not be resolved by OpenStreetMap Nominatim."),
        ):
            response = self.client.get(
                "/api/geocoding/resolve",
                params={"q": "Unknown, Bengaluru"},
            )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"]["code"], "LOCATION_NOT_FOUND")
        self.assertNotIn("latitude", response.json())
        self.assertNotIn("longitude", response.json())

    def test_invalid_static_locality_coordinates_are_rejected(self):
        invalid_location = LocationPoint(
            query="Koramangala, Bengaluru",
            display_name="Koramangala, Bengaluru",
            lat=91.0,
            lon=77.6,
        )
        with patch(
            "backend.app.services.route_service.geocode_location",
            return_value=(invalid_location, None),
        ):
            response = self.client.get(
                "/api/geocoding/resolve",
                params={"q": "Koramangala, Bengaluru"},
            )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["detail"]["code"], "INVALID_GEOCODING_RESPONSE")
        self.assertNotIn("latitude", response.json())
        self.assertNotIn("longitude", response.json())

    def test_selected_coordinates_are_reused_without_geocoding_again(self):
        with (
            patch("backend.app.services.route_service.geocode_location") as geocode,
            patch(
                "backend.app.services.route_service.fetch_osrm_routes",
                return_value=(self.osrm_payload(), None),
            ) as fetch_routes,
        ):
            response = self.client.get(
                "/api/route",
                params={
                    "from": self.origin.display_name,
                    "to": self.destination.display_name,
                    "origin_latitude": self.origin.lat,
                    "origin_longitude": self.origin.lon,
                    "destination_latitude": self.destination.lat,
                    "destination_longitude": self.destination.lon,
                },
            )

        self.assertEqual(response.status_code, 200)
        geocode.assert_not_called()
        self.assertEqual(fetch_routes.call_args.args[0].lat, self.origin.lat)
        self.assertEqual(fetch_routes.call_args.args[1].lon, self.destination.lon)

    def test_route_rejects_incomplete_selected_coordinates(self):
        response = self.client.get(
            "/api/route",
            params={
                "from": "Koramangala, Bengaluru",
                "to": "Whitefield, Bengaluru",
                "origin_latitude": self.origin.lat,
            },
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"]["code"], "INVALID_ORIGIN_COORDINATES")

    def test_empty_origin_and_destination_return_422(self):
        cases = [
            ({"from": "  ", "to": "Whitefield, Bengaluru"}, "EMPTY_ORIGIN"),
            ({"from": "Koramangala, Bengaluru", "to": "  "}, "EMPTY_DESTINATION"),
        ]
        for params, expected_code in cases:
            with self.subTest(expected_code=expected_code):
                response = self.client.get("/api/route", params=params)
                self.assertEqual(response.status_code, 422)
                self.assertEqual(response.json()["detail"]["code"], expected_code)

    def test_location_not_found_returns_404(self):
        with patch(
            "backend.app.services.route_service.geocode_location",
            return_value=(None, "Location 'Unknown' could not be resolved by OpenStreetMap Nominatim."),
        ):
            response = self.client.get("/api/route", params={"from": "Unknown", "to": "Whitefield"})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"]["code"], "LOCATION_NOT_FOUND")

    def test_invalid_geocoding_coordinates_return_502(self):
        invalid_location = LocationPoint(
            query="Invalid",
            display_name="Invalid",
            lat=91.0,
            lon=77.6,
        )
        with (
            patch(
                "backend.app.services.route_service.geocode_location",
                return_value=(invalid_location, None),
            ),
            patch("backend.app.services.route_service.fetch_osrm_routes") as fetch_routes,
        ):
            response = self.client.get("/api/route", params={"from": "Invalid", "to": "Whitefield"})

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["detail"]["code"], "INVALID_GEOCODING_RESPONSE")
        fetch_routes.assert_not_called()

    def test_external_timeouts_return_504(self):
        with patch(
            "backend.app.services.route_service.geocode_location",
            return_value=(None, "Geocoding request timed out after 10s."),
        ):
            geocode_response = self.client.get("/api/route", params={"from": "Koramangala", "to": "Whitefield"})
        self.assertEqual(geocode_response.status_code, 504)

        with (
            patch("backend.app.services.route_service.geocode_location", side_effect=self.successful_geocode),
            patch(
                "backend.app.services.route_service.fetch_osrm_routes",
                return_value=(None, "OSRM routing calculation timed out after 15s."),
            ),
        ):
            routing_response = self.client.get("/api/route", params={"from": "Koramangala", "to": "Whitefield"})
        self.assertEqual(routing_response.status_code, 504)
        self.assertEqual(routing_response.json()["detail"]["code"], "OSRM_TIMEOUT")

    def test_no_routes_and_invalid_geometry_have_useful_errors(self):
        with (
            patch("backend.app.services.route_service.geocode_location", side_effect=self.successful_geocode),
            patch(
                "backend.app.services.route_service.fetch_osrm_routes",
                return_value=(None, "No drivable routes were found between the specified locations."),
            ),
        ):
            no_route_response = self.client.get("/api/route", params={"from": "Koramangala", "to": "Whitefield"})
        self.assertEqual(no_route_response.status_code, 404)
        self.assertEqual(no_route_response.json()["detail"]["code"], "ROUTE_NOT_FOUND")

        with (
            patch("backend.app.services.route_service.geocode_location", side_effect=self.successful_geocode),
            patch(
                "backend.app.services.route_service.fetch_osrm_routes",
                return_value=(None, "OSRM routing response: NoRoute - No route found."),
            ),
        ):
            osrm_no_route_response = self.client.get(
                "/api/route",
                params={"from": "Koramangala", "to": "Whitefield"},
            )
        self.assertEqual(osrm_no_route_response.status_code, 404)
        self.assertEqual(osrm_no_route_response.json()["detail"]["code"], "ROUTE_NOT_FOUND")

        invalid_payload = {
            "code": "Ok",
            "routes": [{
                "distance": 1000,
                "duration": 60,
                "legs": [{"summary": "Invalid route"}],
                "geometry": {"coordinates": [[181, 12], [77.6, 12.9]]},
            }],
        }
        with (
            patch("backend.app.services.route_service.geocode_location", side_effect=self.successful_geocode),
            patch(
                "backend.app.services.route_service.fetch_osrm_routes",
                return_value=(invalid_payload, None),
            ),
        ):
            invalid_response = self.client.get("/api/route", params={"from": "Koramangala", "to": "Whitefield"})
        self.assertEqual(invalid_response.status_code, 502)
        self.assertEqual(invalid_response.json()["detail"]["code"], "INVALID_ROUTING_RESPONSE")


if __name__ == "__main__":
    unittest.main()