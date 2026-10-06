"""Generate small, reproducible synthetic datasets for Phase 1 development."""

import csv
import random
from datetime import date, datetime, time, timedelta
from pathlib import Path

SEED = 42
START_DATE = date(2024, 10, 1)
END_DATE = date(2025, 3, 31)

TRAFFIC_COLUMNS = [
    "timestamp",
    "junction",
    "traffic_volume",
    "congestion_level",
    "weather",
    "signal_status",
]
TOLL_COLUMNS = ["timestamp", "toll_plaza", "vehicle_count", "transaction_count"]
SIGNAL_COLUMNS = ["timestamp", "junction", "signal_status"]
CALENDAR_COLUMNS = [
    "date",
    "festival_name",
    "is_festival",
    "is_holiday",
    "day_type",
]

# Names are deliberately labelled as synthetic while preserving useful corridor names.
JUNCTIONS = [
    "SYNTHETIC: Silk Board - Junction 1",
    "SYNTHETIC: Outer Ring Road - Marathahalli",
    "SYNTHETIC: Airport Road - Hebbal",
    "SYNTHETIC: Bannerghatta Road - Dairy Circle",
    "SYNTHETIC: Whitefield Road - KR Puram",
    "SYNTHETIC: Hosur Road - Electronic City",
]
TOLL_PLAZAS = [
    "SYNTHETIC: Nelamangala Toll Plaza",
    "SYNTHETIC: Electronic City Toll Plaza",
    "SYNTHETIC: Hosur Road Toll Plaza",
    "SYNTHETIC: Airport Road Toll Plaza",
]
WEATHER_OPTIONS = ["Clear", "Cloudy", "Light Rain", "Heavy Rain"]

FESTIVALS = {
    date(2024, 10, 11): "SYNTHETIC: Dussehra Demonstration",
    date(2024, 11, 1): "SYNTHETIC: Kannada Rajyotsava Demonstration",
    date(2024, 12, 25): "SYNTHETIC: Christmas Demonstration",
    date(2025, 1, 14): "SYNTHETIC: Sankranti Demonstration",
    date(2025, 2, 26): "SYNTHETIC: Maha Shivaratri Demonstration",
    date(2025, 3, 14): "SYNTHETIC: Holi Demonstration",
}
HOLIDAYS = set(FESTIVALS) | {
    date(2024, 10, 2),
    date(2024, 11, 25),
    date(2025, 1, 26),
    date(2025, 3, 31),
}


def iter_dates() -> list[date]:
    """Return each calendar date in the small development period."""
    current_date = START_DATE
    dates = []
    while current_date <= END_DATE:
        dates.append(current_date)
        current_date += timedelta(days=1)
    return dates


def day_type_for(current_date: date) -> str:
    """Assign a calendar category without using future analytics logic."""
    if current_date in FESTIVALS:
        return "Festival Day"
    if current_date + timedelta(days=1) in HOLIDAYS:
        return "Pre-Holiday"
    if current_date - timedelta(days=1) in HOLIDAYS:
        return "Post-Holiday"
    if current_date.weekday() == 4:
        return "Friday Evening"
    return "Normal Day"


def write_csv(path: Path, columns: list[str], rows: list[dict[str, object]]) -> None:
    """Write rows with a stable column order and CSV header."""
    with path.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def congestion_for(volume: int, capacity: int) -> str:
    """Convert synthetic volume into a simple demonstration category."""
    ratio = volume / capacity
    if ratio >= 0.9:
        return "Severe"
    if ratio >= 0.7:
        return "High"
    if ratio >= 0.45:
        return "Moderate"
    return "Low"


def generate_datasets(output_directory: Path) -> dict[str, int]:
    """Generate all Phase 1 raw datasets and return their row counts."""
    random_generator = random.Random(SEED)
    output_directory.mkdir(parents=True, exist_ok=True)

    traffic_rows = []
    signal_rows = []
    toll_rows = []
    calendar_rows = []

    # The calendar is generated first so traffic rows can reflect its categories.
    for current_date in iter_dates():
        is_festival = current_date in FESTIVALS
        is_holiday = current_date in HOLIDAYS
        calendar_rows.append(
            {
                "date": current_date.isoformat(),
                "festival_name": FESTIVALS.get(current_date, "None"),
                "is_festival": str(is_festival).lower(),
                "is_holiday": str(is_holiday).lower(),
                "day_type": day_type_for(current_date),
            }
        )

    # Six observations per day provide multiple hours across weekdays and weekends.
    for current_date in iter_dates():
        day_type = day_type_for(current_date)
        weather = random_generator.choice(WEATHER_OPTIONS)
        for hour in range(0, 24, 4):
            timestamp = datetime.combine(current_date, time(hour, 0))
            for junction_index, junction in enumerate(JUNCTIONS):
                hour_factor = 420 if hour in {8, 12, 16, 20} else 220
                weekend_factor = 140 if current_date.weekday() >= 5 else 0
                event_factor = 230 if day_type == "Festival Day" else 0
                rain_factor = 180 if weather in {"Light Rain", "Heavy Rain"} else 0
                corridor_factor = junction_index * 35
                volume = max(
                    20,
                    hour_factor
                    + weekend_factor
                    + event_factor
                    + rain_factor
                    + corridor_factor
                    + random_generator.randint(-70, 70),
                )
                capacity = 800 + junction_index * 40
                signal_status = random_generator.choices(
                    ["Green", "Yellow", "Red"],
                    weights=[65, 20, 15],
                    k=1,
                )[0]
                formatted_timestamp = timestamp.strftime("%Y-%m-%d %H:%M:%S")
                traffic_rows.append(
                    {
                        "timestamp": formatted_timestamp,
                        "junction": junction,
                        "traffic_volume": volume,
                        "congestion_level": congestion_for(volume, capacity),
                        "weather": weather,
                        "signal_status": signal_status,
                    }
                )
                signal_rows.append(
                    {
                        "timestamp": formatted_timestamp,
                        "junction": junction,
                        "signal_status": signal_status,
                    }
                )

        # Four toll observations per day keep the local files useful but small.
        for hour in (6, 12, 18, 22):
            timestamp = datetime.combine(current_date, time(hour, 0))
            for plaza_index, toll_plaza in enumerate(TOLL_PLAZAS):
                base_count = 500 + plaza_index * 80
                weekend_factor = 170 if current_date.weekday() >= 5 else 0
                festival_factor = 260 if day_type == "Festival Day" else 0
                vehicle_count = max(
                    20,
                    base_count
                    + weekend_factor
                    + festival_factor
                    + random_generator.randint(-90, 90),
                )
                transaction_count = vehicle_count + random_generator.randint(0, 25)
                toll_rows.append(
                    {
                        "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                        "toll_plaza": toll_plaza,
                        "vehicle_count": vehicle_count,
                        "transaction_count": transaction_count,
                    }
                )

    write_csv(output_directory / "traffic.csv", TRAFFIC_COLUMNS, traffic_rows)
    write_csv(output_directory / "toll.csv", TOLL_COLUMNS, toll_rows)
    write_csv(output_directory / "signal.csv", SIGNAL_COLUMNS, signal_rows)
    write_csv(output_directory / "festival_calendar.csv", CALENDAR_COLUMNS, calendar_rows)

    return {
        "traffic.csv": len(traffic_rows),
        "toll.csv": len(toll_rows),
        "signal.csv": len(signal_rows),
        "festival_calendar.csv": len(calendar_rows),
    }


def main() -> None:
    """Generate raw demonstration data from the project root."""
    project_root = Path(__file__).resolve().parents[2]
    output_directory = project_root / "data" / "raw"
    row_counts = generate_datasets(output_directory)
    print("Generated SYNTHETIC/DEMONSTRATION datasets:")
    for filename, row_count in row_counts.items():
        print(f"  {filename}: {row_count} rows")


if __name__ == "__main__":
    main()
