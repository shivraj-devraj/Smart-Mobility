"""Tests for the persisted historical corridor advisory endpoint."""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import quote

from fastapi.testclient import TestClient

from backend.app.main import app

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ADVISORY_CSV = PROJECT_ROOT / "data" / "output" / "advisory_output.csv"
FIELDS = [
    "date",
    "corridor",
    "congestion_class",
    "festival_flag",
    "holiday_flag",
    "weather",
    "roadwork",
    "advisory_level",
    "recommendation",
    "personnel_action",
    "diversion_action",
    "roadwork_action",
]


def advisory_row(**overrides: str) -> dict[str, str]:
    row = {
        "date": "2024-01-01",
        "corridor": "Test Corridor",
        "congestion_class": "Low",
        "festival_flag": "False",
        "holiday_flag": "False",
        "weather": "Clear",
        "roadwork": "No",
        "advisory_level": "Normal",
        "recommendation": "Persisted recommendation",
        "personnel_action": "Persisted personnel action",
        "diversion_action": "Persisted diversion action",
        "roadwork_action": "Persisted roadwork action",
    }
    row.update(overrides)
    return row


class TestAdvisoryApi(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def _write_source(
        self,
        directory: str,
        rows: list[dict[str, str]],
        fields: list[str] | None = None,
    ) -> Path:
        path = Path(directory) / "advisory_output.csv"
        with path.open("w", newline="", encoding="utf-8") as output_file:
            writer = csv.DictWriter(
                output_file,
                fieldnames=fields or FIELDS,
                extrasaction="ignore",
            )
            writer.writeheader()
            writer.writerows(rows)
        return path

    def test_known_corridor_returns_persisted_actions_and_aggregates(self) -> None:
        before = ADVISORY_CSV.read_bytes()
        corridor = "Koramangala | Sarjapur Road"
        with ADVISORY_CSV.open("r", newline="", encoding="utf-8") as source_file:
            rows = [row for row in csv.DictReader(source_file) if row["corridor"] == corridor]

        response = self.client.get(
            f"/api/advisory/corridors/{quote(corridor, safe='')}"
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["corridor"], corridor)
        self.assertEqual(body["record_count"], len(rows))
        self.assertEqual(body["date_start"], min(row["date"] for row in rows))
        self.assertEqual(body["date_end"], max(row["date"] for row in rows))
        expected_festival = sum(row["festival_flag"] == "True" for row in rows)
        expected_holiday = sum(row["holiday_flag"] == "True" for row in rows)
        expected_roadwork = sum(row["roadwork"] == "Yes" for row in rows)
        expected_rain_or_fog = sum(row["weather"] in {"Rain", "Fog"} for row in rows)
        self.assertEqual(
            body["context_counts"],
            {
                "festival": expected_festival,
                "holiday": expected_holiday,
                "roadwork": expected_roadwork,
                "rain_or_fog": expected_rain_or_fog,
            },
        )
        self.assertEqual(
            {item["congestion_class"] for item in body["congestion_actions"]},
            {row["congestion_class"] for row in rows},
        )
        for action in body["congestion_actions"]:
            matching = [
                row for row in rows if row["congestion_class"] == action["congestion_class"]
            ]
            self.assertEqual(action["record_count"], len(matching))
            for field in (
                "advisory_level",
                "recommendation",
                "personnel_action",
                "diversion_action",
                "roadwork_action",
            ):
                self.assertEqual(action[field], matching[0][field])
        self.assertEqual(ADVISORY_CSV.read_bytes(), before)

    def test_unknown_corridor_returns_not_found(self) -> None:
        response = self.client.get("/api/advisory/corridors/not-a-persisted-corridor")

        self.assertEqual(response.status_code, 404)
        self.assertIn("No historical advisory data", response.json()["detail"])

    def test_missing_source_returns_clear_server_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            missing_path = Path(directory) / "missing.csv"
            with patch(
                "backend.app.services.advisory_service.advisory_output_path",
                return_value=missing_path,
            ):
                response = self.client.get("/api/advisory/corridors/Test%20Corridor")

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()["detail"], "Advisory CSV was not found.")

    def test_missing_required_column_returns_server_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fields = [field for field in FIELDS if field != "recommendation"]
            path = self._write_source(directory, [advisory_row()], fields)
            with patch(
                "backend.app.services.advisory_service.advisory_output_path",
                return_value=path,
            ):
                response = self.client.get("/api/advisory/corridors/Test%20Corridor")

        self.assertEqual(response.status_code, 500)
        self.assertIn("recommendation", response.json()["detail"])

    def test_malformed_date_returns_server_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = self._write_source(directory, [advisory_row(date="not-a-date")])
            with patch(
                "backend.app.services.advisory_service.advisory_output_path",
                return_value=path,
            ):
                response = self.client.get("/api/advisory/corridors/Test%20Corridor")

        self.assertEqual(response.status_code, 500)
        self.assertIn("invalid date", response.json()["detail"])

    def test_incomplete_row_returns_server_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = self._write_source(directory, [advisory_row(holiday_flag="")])
            with patch(
                "backend.app.services.advisory_service.advisory_output_path",
                return_value=path,
            ):
                response = self.client.get("/api/advisory/corridors/Test%20Corridor")

        self.assertEqual(response.status_code, 500)
        self.assertIn("incomplete", response.json()["detail"])

    def test_conflicting_persisted_actions_are_rejected(self) -> None:
        first = advisory_row()
        second = advisory_row(date="2024-01-02", recommendation="Different persisted text")
        with tempfile.TemporaryDirectory() as directory:
            path = self._write_source(directory, [first, second])
            with patch(
                "backend.app.services.advisory_service.advisory_output_path",
                return_value=path,
            ):
                response = self.client.get("/api/advisory/corridors/Test%20Corridor")

        self.assertEqual(response.status_code, 500)
        self.assertIn("conflicting actions", response.json()["detail"])

    def test_context_flags_are_counted_as_persisted(self) -> None:
        rows = [
            advisory_row(
                date=date(2024, 1, 1).isoformat(),
                festival_flag="True",
                holiday_flag="True",
                weather="Rain",
                roadwork="Yes",
            ),
            advisory_row(
                date=date(2024, 1, 2).isoformat(),
                congestion_class="Medium",
                festival_flag="False",
                holiday_flag="True",
                weather="Fog",
            ),
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = self._write_source(directory, rows)
            with patch(
                "backend.app.services.advisory_service.advisory_output_path",
                return_value=path,
            ):
                response = self.client.get("/api/advisory/corridors/Test%20Corridor")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["context_counts"],
            {"festival": 1, "holiday": 2, "roadwork": 1, "rain_or_fog": 2},
        )
