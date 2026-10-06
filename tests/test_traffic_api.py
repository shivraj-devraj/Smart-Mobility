"""Tests for the read-only persisted corridor traffic API."""

from __future__ import annotations

import csv
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import quote

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.traffic_service import (
    TrafficDataError,
    load_corridor_summaries,
    load_day_of_week_congestion_summary,
    load_day_type_congestion_summary,
    load_high_congestion_corridors,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CORRIDOR_CSV = PROJECT_ROOT / "data" / "output" / "corridor_congestion_summary.csv"
REQUIRED_FIELDS = {
    "corridor",
    "record_count",
    "average_traffic_volume",
    "average_speed",
    "average_congestion_level",
    "average_travel_time_index",
    "low_congestion_count",
    "medium_congestion_count",
    "high_congestion_count",
}
INTEGER_FIELDS = {
    "record_count",
    "low_congestion_count",
    "medium_congestion_count",
    "high_congestion_count",
}
FLOAT_FIELDS = {
    "average_traffic_volume",
    "average_speed",
    "average_congestion_level",
    "average_travel_time_index",
}
HIGH_CONGESTION_CSV = PROJECT_ROOT / "data" / "output" / "high_congestion_corridors.csv"
HIGH_CONGESTION_FIELDS = {
    "corridor",
    "total_records",
    "high_congestion_count",
    "high_congestion_percentage",
}
HIGH_CONGESTION_INTEGER_FIELDS = {"total_records", "high_congestion_count"}
DAY_TYPE_CSV = PROJECT_ROOT / "data" / "output" / "day_type_congestion_summary.csv"
DAY_OF_WEEK_CSV = PROJECT_ROOT / "data" / "output" / "day_of_week_congestion_summary.csv"
DAY_TYPE_FIELDS = {
    "day_type",
    "record_count",
    "average_traffic_volume",
    "average_speed",
    "average_congestion_level",
    "average_travel_time_index",
    "high_congestion_count",
    "high_congestion_percentage",
}
DAY_OF_WEEK_FIELDS = {
    "day_of_week",
    "record_count",
    "average_traffic_volume",
    "average_speed",
    "average_congestion_level",
    "high_congestion_percentage",
}


class TestTrafficApi(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_list_corridors_returns_all_persisted_summaries(self) -> None:
        with CORRIDOR_CSV.open("r", newline="", encoding="utf-8") as source_file:
            persisted_rows = list(csv.DictReader(source_file))

        response = self.client.get("/api/traffic/corridors")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(set(body), {"count", "corridors"})
        self.assertEqual(body["count"], 16)
        self.assertEqual(body["count"], len(body["corridors"]))
        self.assertEqual(len(body["corridors"]), len(persisted_rows))

        for actual, persisted in zip(body["corridors"], persisted_rows):
            with self.subTest(corridor=actual["corridor"]):
                self.assertEqual(set(actual), REQUIRED_FIELDS)
                self.assertEqual(actual["corridor"], persisted["corridor"])
                for field in INTEGER_FIELDS:
                    self.assertIs(type(actual[field]), int)
                    self.assertEqual(actual[field], int(persisted[field]))
                for field in FLOAT_FIELDS:
                    self.assertIs(type(actual[field]), float)
                    self.assertEqual(actual[field], float(persisted[field]))

    def test_get_known_corridor_matches_persisted_row(self) -> None:
        known_corridor = "Koramangala | Sarjapur Road"
        with CORRIDOR_CSV.open("r", newline="", encoding="utf-8") as source_file:
            persisted = next(
                row for row in csv.DictReader(source_file) if row["corridor"] == known_corridor
            )

        response = self.client.get(f"/api/traffic/corridors/{quote(known_corridor, safe='')}")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["corridor"], known_corridor)
        self.assertEqual(set(body), REQUIRED_FIELDS)
        for field in INTEGER_FIELDS:
            self.assertEqual(body[field], int(persisted[field]))
        for field in FLOAT_FIELDS:
            self.assertEqual(body[field], float(persisted[field]))

    def test_unknown_corridor_returns_404(self) -> None:
        response = self.client.get("/api/traffic/corridors/Unknown%20%7C%20Road")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"detail": "Corridor not found: Unknown | Road"})

    def test_api_returns_clear_error_when_source_is_unavailable(self) -> None:
        with patch(
            "backend.app.routes.traffic_api.load_corridor_summaries",
            side_effect=TrafficDataError("Corridor summary CSV was not found."),
        ):
            response = self.client.get("/api/traffic/corridors")

        self.assertEqual(response.status_code, 500)
        self.assertEqual(
            response.json(),
            {"detail": "Corridor summary CSV was not found."},
        )

    def test_list_high_congestion_corridors_matches_persisted_csv(self) -> None:
        with HIGH_CONGESTION_CSV.open("r", newline="", encoding="utf-8") as source_file:
            persisted_rows = list(csv.DictReader(source_file))

        response = self.client.get("/api/traffic/high-congestion-corridors")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(set(body), {"count", "corridors"})
        self.assertEqual(body["count"], len(persisted_rows))
        self.assertEqual(body["count"], 16)
        self.assertEqual(len(body["corridors"]), 16)

        for actual, persisted in zip(body["corridors"], persisted_rows):
            with self.subTest(corridor=actual["corridor"]):
                self.assertEqual(set(actual), HIGH_CONGESTION_FIELDS)
                self.assertEqual(actual["corridor"], persisted["corridor"])
                for field in HIGH_CONGESTION_INTEGER_FIELDS:
                    self.assertIs(type(actual[field]), int)
                    self.assertEqual(actual[field], int(persisted[field]))
                self.assertIs(type(actual["high_congestion_percentage"]), float)
                self.assertEqual(
                    actual["high_congestion_percentage"],
                    float(persisted["high_congestion_percentage"]),
                )

    def test_high_congestion_endpoint_returns_clear_error_when_source_is_unavailable(self) -> None:
        with patch(
            "backend.app.routes.traffic_api.load_high_congestion_corridors",
            side_effect=TrafficDataError("High-congestion corridor CSV was not found."),
        ):
            response = self.client.get("/api/traffic/high-congestion-corridors")

        self.assertEqual(response.status_code, 500)
        self.assertEqual(
            response.json(),
            {"detail": "High-congestion corridor CSV was not found."},
        )

    def test_day_type_temporal_summary_matches_csv(self) -> None:
        with DAY_TYPE_CSV.open("r", newline="", encoding="utf-8") as source_file:
            persisted_rows = list(csv.DictReader(source_file))

        response = self.client.get("/api/traffic/temporal", params={"dimension": "day-type"})

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(set(body), {"dimension", "count", "rows"})
        self.assertEqual(body["dimension"], "day-type")
        self.assertEqual(body["count"], len(persisted_rows))
        self.assertEqual(body["count"], 2)
        for actual, persisted in zip(body["rows"], persisted_rows):
            self.assertEqual(set(actual), DAY_TYPE_FIELDS)
            for field in DAY_TYPE_FIELDS:
                self.assertEqual(actual[field], _temporal_csv_value(field, persisted[field]))
            for field in {"record_count", "high_congestion_count"}:
                self.assertIs(type(actual[field]), int)
            for field in DAY_TYPE_FIELDS - {"day_type", "record_count", "high_congestion_count"}:
                self.assertIs(type(actual[field]), float)

    def test_day_of_week_temporal_summary_matches_csv(self) -> None:
        with DAY_OF_WEEK_CSV.open("r", newline="", encoding="utf-8") as source_file:
            persisted_rows = list(csv.DictReader(source_file))

        response = self.client.get(
            "/api/traffic/temporal",
            params={"dimension": "day-of-week"},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(set(body), {"dimension", "count", "rows"})
        self.assertEqual(body["dimension"], "day-of-week")
        self.assertEqual(body["count"], len(persisted_rows))
        self.assertEqual(body["count"], 7)
        for actual, persisted in zip(body["rows"], persisted_rows):
            self.assertEqual(set(actual), DAY_OF_WEEK_FIELDS)
            for field in DAY_OF_WEEK_FIELDS:
                self.assertEqual(actual[field], _temporal_csv_value(field, persisted[field]))
            self.assertIs(type(actual["day_of_week"]), int)
            self.assertIs(type(actual["record_count"]), int)
            for field in DAY_OF_WEEK_FIELDS - {"day_of_week", "record_count"}:
                self.assertIs(type(actual[field]), float)

    def test_temporal_unsupported_dimension_returns_400(self) -> None:
        response = self.client.get("/api/traffic/temporal", params={"dimension": "invalid"})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json(),
            {
                "detail": (
                    "Unsupported temporal dimension. Use 'day-type' or 'day-of-week'."
                )
            },
        )

    def test_temporal_missing_source_returns_clear_500(self) -> None:
        with patch(
            "backend.app.routes.traffic_api.load_day_type_congestion_summary",
            side_effect=TrafficDataError("Day-type summary CSV was not found."),
        ):
            response = self.client.get("/api/traffic/temporal?dimension=day-type")

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json(), {"detail": "Day-type summary CSV was not found."})


class TestTrafficService(unittest.TestCase):
    def test_missing_file_is_reported(self) -> None:
        missing_path = Path(tempfile.gettempdir()) / "missing_corridor_summary_for_test.csv"
        with self.assertRaisesRegex(TrafficDataError, "was not found"):
            load_corridor_summaries(missing_path)

    def test_missing_columns_are_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "corridors.csv"
            source.write_text("corridor,record_count\nTest,1\n", encoding="utf-8")

            with self.assertRaisesRegex(TrafficDataError, "missing required columns"):
                load_corridor_summaries(source)

    def test_empty_csv_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "corridors.csv"
            source.write_text("", encoding="utf-8")

            with self.assertRaisesRegex(TrafficDataError, "empty or has no header"):
                load_corridor_summaries(source)

    def test_unreadable_csv_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "corridors.csv"
            source.write_bytes(b"\xff")

            with self.assertRaisesRegex(TrafficDataError, "could not be read"):
                load_corridor_summaries(source)

    def test_header_only_csv_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "corridors.csv"
            source.write_text(",".join(sorted(REQUIRED_FIELDS)) + "\n", encoding="utf-8")

            with self.assertRaisesRegex(TrafficDataError, "contains no corridor records"):
                load_corridor_summaries(source)

    def test_invalid_numeric_value_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "corridors.csv"
            fields = [
                "corridor",
                "record_count",
                "average_traffic_volume",
                "average_speed",
                "average_congestion_level",
                "average_travel_time_index",
                "low_congestion_count",
                "medium_congestion_count",
                "high_congestion_count",
            ]
            row = {field: "1" for field in fields}
            row["corridor"] = "Test Corridor"
            row["average_speed"] = "not-a-number"
            with source.open("w", newline="", encoding="utf-8") as output_file:
                writer = csv.DictWriter(output_file, fieldnames=fields)
                writer.writeheader()
                writer.writerow(row)

            with self.assertRaisesRegex(TrafficDataError, "invalid number in average_speed"):
                load_corridor_summaries(source)

    def test_high_congestion_missing_file_is_reported(self) -> None:
        missing_path = Path(tempfile.gettempdir()) / "missing_high_congestion_csv_for_test.csv"
        with self.assertRaisesRegex(TrafficDataError, "was not found"):
            load_high_congestion_corridors(missing_path)

    def test_high_congestion_missing_columns_are_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "high_congestion.csv"
            source.write_text("corridor,total_records\nTest,1\n", encoding="utf-8")

            with self.assertRaisesRegex(TrafficDataError, "missing required columns"):
                load_high_congestion_corridors(source)

    def test_high_congestion_empty_csv_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "high_congestion.csv"
            source.write_text("", encoding="utf-8")

            with self.assertRaisesRegex(TrafficDataError, "empty or has no header"):
                load_high_congestion_corridors(source)

    def test_high_congestion_invalid_numeric_value_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "high_congestion.csv"
            source.write_text(
                "corridor,total_records,high_congestion_count,high_congestion_percentage\n"
                "Test,invalid,1,50.0\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(TrafficDataError, "invalid integer in total_records"):
                load_high_congestion_corridors(source)

    def test_high_congestion_malformed_row_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "high_congestion.csv"
            source.write_text(
                "corridor,total_records,high_congestion_count,high_congestion_percentage\n"
                "Test,1,1\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(TrafficDataError, "is incomplete"):
                load_high_congestion_corridors(source)

    def test_day_type_missing_columns_are_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "day_type.csv"
            source.write_text("day_type,record_count\nWeekday,1\n", encoding="utf-8")

            with self.assertRaisesRegex(TrafficDataError, "missing required columns"):
                load_day_type_congestion_summary(source)

    def test_day_type_invalid_numeric_data_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "day_type.csv"
            source.write_text(
                "day_type,record_count,average_traffic_volume,average_speed,"
                "average_congestion_level,average_travel_time_index,"
                "high_congestion_count,high_congestion_percentage\n"
                "Weekday,invalid,10,20,30,1.2,1,50\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(TrafficDataError, "invalid integer in record_count"):
                load_day_type_congestion_summary(source)

    def test_day_of_week_missing_file_is_reported(self) -> None:
        missing_path = Path(tempfile.gettempdir()) / "missing_day_of_week_summary_for_test.csv"
        with self.assertRaisesRegex(TrafficDataError, "was not found"):
            load_day_of_week_congestion_summary(missing_path)

    def test_day_of_week_malformed_row_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "day_of_week.csv"
            source.write_text(
                "day_of_week,record_count,average_traffic_volume,average_speed,"
                "average_congestion_level,high_congestion_percentage\n"
                "1,100,not-a-number,20,30,50\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(TrafficDataError, "invalid number in average_traffic_volume"):
                load_day_of_week_congestion_summary(source)


def _temporal_csv_value(field: str, value: str) -> str | int | float:
    if field in {"day_of_week", "record_count", "high_congestion_count"}:
        return int(value)
    if field in {
        "average_traffic_volume",
        "average_speed",
        "average_congestion_level",
        "average_travel_time_index",
        "high_congestion_percentage",
    }:
        return float(value)
    return value


if __name__ == "__main__":
    unittest.main()
