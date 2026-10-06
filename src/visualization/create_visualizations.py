"""Create reproducible static charts from validated project outputs."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIRECTORY = PROJECT_ROOT / "data" / "output" / "visualizations"
SUMMARY_PATH = OUTPUT_DIRECTORY / "visualization_summary.txt"

INPUT_FILES = {
    "integrated": PROJECT_ROOT / "data" / "processed" / "integrated_traffic_data.csv",
    "corridor_summary": PROJECT_ROOT / "data" / "output" / "corridor_congestion_summary.csv",
    "day_type_summary": PROJECT_ROOT / "data" / "output" / "day_type_congestion_summary.csv",
    "festival_summary": PROJECT_ROOT / "data" / "output" / "festival_congestion_summary.csv",
    "holiday_summary": PROJECT_ROOT / "data" / "output" / "holiday_congestion_summary.csv",
    "day_of_week_summary": PROJECT_ROOT / "data" / "output" / "day_of_week_congestion_summary.csv",
    "top_average": PROJECT_ROOT / "data" / "output" / "top5_average_congestion_corridors.csv",
    "top_percentage": PROJECT_ROOT / "data" / "output" / "top5_high_congestion_percentage_corridors.csv",
    "prediction_advisory": PROJECT_ROOT / "data" / "output" / "prediction_advisory_output.csv",
    "advisory": PROJECT_ROOT / "data" / "output" / "advisory_output.csv",
}

REQUIRED_COLUMNS = {
    "integrated": {"congestion_class"},
    "corridor_summary": {"corridor", "average_congestion_level"},
    "day_type_summary": {"day_type", "average_congestion_level", "high_congestion_percentage"},
    "festival_summary": {"festival_flag", "average_congestion_level", "high_congestion_percentage"},
    "holiday_summary": {"holiday_flag", "average_congestion_level", "high_congestion_percentage"},
    "day_of_week_summary": {"day_of_week", "average_congestion_level", "high_congestion_percentage"},
    "top_average": {"corridor", "average_congestion_level"},
    "top_percentage": {"corridor", "high_congestion_percentage"},
    "prediction_advisory": {
        "actual_congestion_class",
        "predicted_congestion_class",
        "advisory_level",
    },
    "advisory": {"advisory_level"},
}

CHARTS = [
    ("Congestion class distribution", "integrated", "congestion_class_distribution.png"),
    ("Top corridors by average congestion", "top_average", "top5_average_congestion.png"),
    ("Top corridors by high-congestion percentage", "top_percentage", "top5_high_congestion_percentage.png"),
    ("Festival versus non-festival", "festival_summary", "festival_vs_nonfestival.png"),
    ("Weekday versus weekend", "day_type_summary", "weekday_vs_weekend.png"),
    ("Actual versus predicted congestion", "prediction_advisory", "actual_vs_predicted_confusion_matrix.png"),
    ("Predicted congestion distribution", "prediction_advisory", "predicted_congestion_distribution.png"),
    ("Advisory distribution", "prediction_advisory", "advisory_distribution.png"),
]


def read_and_validate_inputs() -> dict[str, pd.DataFrame]:
    """Load all declared validated outputs and check their required columns."""
    missing_files = [str(path) for path in INPUT_FILES.values() if not path.is_file()]
    if missing_files:
        raise FileNotFoundError(f"Missing visualization inputs: {missing_files}")

    frames = {}
    for name, path in INPUT_FILES.items():
        frame = pd.read_csv(path)
        missing_columns = REQUIRED_COLUMNS[name] - set(frame.columns)
        if missing_columns:
            raise ValueError(f"{path} is missing columns: {sorted(missing_columns)}")
        frames[name] = frame
    return frames


def configure_style() -> None:
    """Use a restrained academic style with readable labels."""
    sns.set_theme(style="whitegrid", context="notebook", palette="deep")
    plt.rcParams.update({
        "figure.figsize": (10, 6),
        "axes.titlesize": 14,
        "axes.labelsize": 11,
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
        "legend.fontsize": 10,
    })


def save_figure(figure: plt.Figure, filename: str) -> Path:
    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIRECTORY / filename
    figure.tight_layout()
    figure.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(figure)
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError(f"Chart was not created or is empty: {path}")
    return path


def plot_congestion_class_distribution(frames: dict[str, pd.DataFrame]) -> Path:
    counts = frames["integrated"]["congestion_class"].value_counts().reindex(["Low", "Medium", "High"], fill_value=0)
    figure, axis = plt.subplots()
    bars = axis.bar(counts.index, counts.values, color=["#4C956C", "#E0A458", "#BC4749"])
    axis.set_title("Bengaluru Historical Congestion Class Distribution")
    axis.set_xlabel("Historical congestion class")
    axis.set_ylabel("Traffic records")
    axis.bar_label(bars, padding=3)
    return save_figure(figure, "congestion_class_distribution.png")


def plot_top_average(frames: dict[str, pd.DataFrame]) -> Path:
    frame = frames["top_average"].sort_values("average_congestion_level")
    figure, axis = plt.subplots(figsize=(10, 6))
    axis.barh(frame["corridor"], frame["average_congestion_level"], color="#2F6690")
    axis.set_title("Top 5 Corridors by Average Historical Congestion")
    axis.set_xlabel("Average historical congestion level")
    axis.set_ylabel("Corridor")
    axis.set_xlim(left=0)
    return save_figure(figure, "top5_average_congestion.png")


def plot_top_percentage(frames: dict[str, pd.DataFrame]) -> Path:
    frame = frames["top_percentage"].sort_values("high_congestion_percentage")
    figure, axis = plt.subplots(figsize=(10, 6))
    axis.barh(frame["corridor"], frame["high_congestion_percentage"], color="#7A5195")
    axis.set_title("Top 5 Corridors by High-Congestion Percentage")
    axis.set_xlabel("High-congestion records (%)")
    axis.set_ylabel("Corridor")
    axis.set_xlim(0, 100)
    return save_figure(figure, "top5_high_congestion_percentage.png")


def plot_group_comparison(frames: dict[str, pd.DataFrame], source: str, labels: dict[object, str], filename: str, title: str) -> Path:
    frame = frames[source].copy()
    grouping_column = "festival_flag" if source == "festival_summary" else "day_type"
    if source == "festival_summary":
        frame["group"] = frame[grouping_column].map(labels)
    else:
        frame["group"] = frame[grouping_column].map(labels).fillna(frame[grouping_column])
    frame = frame.set_index("group").reindex(list(labels.values()))
    figure, axes = plt.subplots(1, 2, figsize=(11, 5))
    congestion_bars = axes[0].bar(frame.index, frame["average_congestion_level"], color=["#2F6690", "#E0A458"])
    percentage_bars = axes[1].bar(frame.index, frame["high_congestion_percentage"], color=["#2F6690", "#E0A458"])
    axes[0].set_title("Average congestion")
    axes[0].set_ylabel("Average historical congestion level")
    axes[1].set_title("High-congestion percentage")
    axes[1].set_ylabel("High-congestion records (%)")
    axes[1].set_ylim(0, 100)
    for axis, bars in [(axes[0], congestion_bars), (axes[1], percentage_bars)]:
        axis.set_xlabel("Group")
        axis.bar_label(bars, fmt="%.2f", padding=3)
    figure.suptitle(title, y=1.03)
    return save_figure(figure, filename)


def plot_confusion_matrix(frames: dict[str, pd.DataFrame]) -> Path:
    frame = frames["prediction_advisory"]
    classes = ["Low", "Medium", "High"]
    matrix = pd.crosstab(
        frame["actual_congestion_class"],
        frame["predicted_congestion_class"],
    ).reindex(index=classes, columns=classes, fill_value=0)
    figure, axis = plt.subplots(figsize=(7, 6))
    sns.heatmap(matrix, annot=True, fmt="d", cmap="Blues", cbar=False, ax=axis)
    axis.set_title("Decision Tree: Actual vs Predicted Congestion")
    axis.set_xlabel("Predicted congestion class")
    axis.set_ylabel("Actual congestion class")
    return save_figure(figure, "actual_vs_predicted_confusion_matrix.png")


def plot_predicted_distribution(frames: dict[str, pd.DataFrame]) -> Path:
    counts = frames["prediction_advisory"]["predicted_congestion_class"].value_counts().reindex(["Low", "Medium", "High"], fill_value=0)
    figure, axis = plt.subplots()
    bars = axis.bar(counts.index, counts.values, color=["#4C956C", "#E0A458", "#BC4749"])
    axis.set_title("Predicted Congestion Distribution on Test Data")
    axis.set_xlabel("Predicted congestion class")
    axis.set_ylabel("Test records")
    axis.bar_label(bars, padding=3)
    return save_figure(figure, "predicted_congestion_distribution.png")


def plot_advisory_distribution(frames: dict[str, pd.DataFrame]) -> Path:
    counts = frames["prediction_advisory"]["advisory_level"].value_counts().reindex(["Normal", "Moderate", "High"], fill_value=0)
    figure, axis = plt.subplots()
    bars = axis.bar(counts.index, counts.values, color=["#4C956C", "#E0A458", "#BC4749"])
    axis.set_title("Traffic Advisory Distribution")
    axis.set_xlabel("Advisory level")
    axis.set_ylabel("Test records")
    axis.bar_label(bars, padding=3)
    return save_figure(figure, "advisory_distribution.png")


def create_all_visualizations(frames: dict[str, pd.DataFrame]) -> list[dict[str, object]]:
    generated = [
        ("Congestion class distribution", "integrated", plot_congestion_class_distribution(frames)),
        ("Top corridors by average congestion", "top_average", plot_top_average(frames)),
        ("Top corridors by high-congestion percentage", "top_percentage", plot_top_percentage(frames)),
        ("Festival versus non-festival", "festival_summary", plot_group_comparison(
            frames, "festival_summary", {True: "Festival", False: "Non-Festival"},
            "festival_vs_nonfestival.png", "Festival vs Non-Festival Historical Congestion",
        )),
        ("Weekday versus weekend", "day_type_summary", plot_group_comparison(
            frames, "day_type_summary", {"Weekday": "Weekday", "Weekend": "Weekend"},
            "weekday_vs_weekend.png", "Weekday vs Weekend Historical Congestion",
        )),
        ("Actual versus predicted congestion", "prediction_advisory", plot_confusion_matrix(frames)),
        ("Predicted congestion distribution", "prediction_advisory", plot_predicted_distribution(frames)),
        ("Advisory distribution", "prediction_advisory", plot_advisory_distribution(frames)),
    ]
    return [
        {
            "name": name,
            "source": str(INPUT_FILES[source]),
            "output": str(path),
            "size_bytes": path.stat().st_size,
            "status": "PASS",
        }
        for name, source, path in generated
    ]


def write_summary(records: list[dict[str, object]]) -> None:
    lines = [
        "PHASE 8A - CORE VISUALIZATION SUMMARY",
        "======================================",
        "",
        "All charts are static, reproducible views of historical batch outputs.",
        "They do not represent real-time traffic and do not invent hourly, directional, GPS, FASTag, or signal-event dimensions.",
        "",
    ]
    for record in records:
        lines.extend([
            f"Visualization: {record['name']}",
            f"Source file: {record['source']}",
            f"Output path: {record['output']}",
            f"File size: {record['size_bytes']} bytes",
            f"Validation: {record['status']}",
            "",
        ])
    lines.append("Overall validation: PASS")
    SUMMARY_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    """Validate source outputs, create eight charts, and write the manifest."""
    configure_style()
    frames = read_and_validate_inputs()
    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    records = create_all_visualizations(frames)
    if len(records) != 8 or not all(record["size_bytes"] > 0 for record in records):
        raise ValueError("Visualization output validation failed.")
    write_summary(records)
    if not SUMMARY_PATH.is_file() or SUMMARY_PATH.stat().st_size == 0:
        raise ValueError("Visualization summary was not created or is empty.")
    print("PHASE 8A VISUALIZATION SUMMARY")
    print("------------------------------")
    print("Execution succeeded: True")
    for record in records:
        print(f"{record['name']}: {record['status']}; source={record['source']}; output={record['output']}; size={record['size_bytes']} bytes")
    print(f"Summary: {SUMMARY_PATH}")
    print("Validation: all required inputs and eight PNG outputs PASS")


if __name__ == "__main__":
    main()
