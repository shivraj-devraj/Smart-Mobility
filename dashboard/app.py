"""Streamlit dashboard for validated batch historical traffic outputs and smart route decision support."""

from pathlib import Path
import io
import json
import re
import sys

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
import streamlit as st
import streamlit.components.v1 as components


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.route import (
    LocationPoint,
    Route,
    create_route_map,
    evaluate_and_recommend_routes,
    fetch_osrm_routes,
    geocode_location,
    parse_osrm_routes,
    render_map_html,
)

DATA = PROJECT_ROOT / "data"
OUTPUT = DATA / "output"
VISUALIZATIONS = OUTPUT / "visualizations"

PATHS = {
    "integrated": DATA / "processed" / "integrated_traffic_data.csv",
    "corridor_summary": OUTPUT / "corridor_congestion_summary.csv",
    "day_type_summary": OUTPUT / "day_type_congestion_summary.csv",
    "festival_summary": OUTPUT / "festival_congestion_summary.csv",
    "holiday_summary": OUTPUT / "holiday_congestion_summary.csv",
    "day_of_week_summary": OUTPUT / "day_of_week_congestion_summary.csv",
    "top_average": OUTPUT / "top5_average_congestion_corridors.csv",
    "top_percentage": OUTPUT / "top5_high_congestion_percentage_corridors.csv",
    "prediction_advisory": OUTPUT / "prediction_advisory_output.csv",
    "prediction_summary": OUTPUT / "prediction_advisory_summary.txt",
    "advisory": OUTPUT / "advisory_output.csv",
    "advisory_summary": OUTPUT / "advisory_summary.txt",
}

INTEGRATED_COLUMNS = [
    "date", "area", "road_intersection", "corridor", "traffic_volume",
    "average_speed", "travel_time_index", "congestion_level", "congestion_class",
    "weather", "roadwork", "day_of_week", "day_type", "festival_flag",
    "festival_name", "holiday_flag",
]

st.set_page_config(
    page_title="Smart Mobility Bengaluru Analytics",
    page_icon=":bar_chart:",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_data(show_spinner=False)
def load_csv(path_string: str, parse_dates: list[str] | None = None) -> pd.DataFrame:
    """Load an existing output without modifying or recomputing it."""
    return pd.read_csv(path_string, parse_dates=parse_dates or [])


@st.cache_data(show_spinner=False)
def load_text(path_string: str) -> str:
    return Path(path_string).read_text(encoding="utf-8")


def require_files() -> None:
    missing = [str(path) for path in PATHS.values() if not path.is_file()]
    missing_images = [
        str(path)
        for path in [
            VISUALIZATIONS / "congestion_class_distribution.png",
            VISUALIZATIONS / "top5_average_congestion.png",
            VISUALIZATIONS / "top5_high_congestion_percentage.png",
            VISUALIZATIONS / "festival_vs_nonfestival.png",
            VISUALIZATIONS / "weekday_vs_weekend.png",
            VISUALIZATIONS / "actual_vs_predicted_confusion_matrix.png",
            VISUALIZATIONS / "predicted_congestion_distribution.png",
            VISUALIZATIONS / "advisory_distribution.png",
        ]
        if not path.is_file()
    ]
    if missing or missing_images:
        st.error("Required validated outputs are missing.")
        if missing:
            st.write("Missing data files:", missing)
        if missing_images:
            st.write("Missing visualization files:", missing_images)
        st.stop()


def parse_metrics(summary: str) -> dict[str, float]:
    patterns = {
        "Accuracy": r"Accuracy:\s*([0-9.]+)",
        "Weighted Precision": r"Weighted Precision:\s*([0-9.]+)",
        "Weighted Recall": r"Weighted Recall:\s*([0-9.]+)",
        "F1": r"(?:F1 Score|F1):\s*([0-9.]+)",
    }
    metrics = {}
    for name, pattern in patterns.items():
        match = re.search(pattern, summary)
        if not match:
            raise ValueError(f"Metric '{name}' is missing from the evaluation summary.")
        try:
            value = float(match.group(1))
        except ValueError as exc:
            raise ValueError(f"Metric '{name}' has an invalid numerical value: {match.group(1)}") from exc
        if not (0.0 <= value <= 1.0):
            raise ValueError(f"Metric '{name}' has value {value}, which is outside the valid range [0.0, 1.0].")
        metrics[name] = value
    return metrics


def apply_filters(frame: pd.DataFrame, filters: dict[str, object]) -> pd.DataFrame:
    filtered = frame.copy()
    if "date" in filtered:
        filtered["date"] = pd.to_datetime(filtered["date"], errors="coerce")
        start_date = pd.to_datetime(filters["date_range"][0])
        end_date = pd.to_datetime(filters["date_range"][1])
        filtered = filtered[
            filtered["date"].notna()
            & filtered["date"].between(start_date, end_date, inclusive="both")
        ]
    if "corridor" in filtered:
        filtered = filtered[filtered["corridor"].isin(filters["corridors"])]
    class_column = "congestion_class" if "congestion_class" in filtered else "actual_congestion_class"
    if class_column in filtered:
        filtered = filtered[filtered[class_column].isin(filters["classes"])]
    if "day_type" in filtered:
        filtered = filtered[filtered["day_type"].isin(filters["day_types"])]
    for column, value in [("festival_flag", filters["festival_flag"]), ("holiday_flag", filters["holiday_flag"])]:
        if column in filtered and value != "All":
            filtered = filtered[filtered[column] == (value == "True")]
    return filtered


def historical_bar(frame: pd.DataFrame, column: str, title: str, y_label: str) -> None:
    counts = frame[column].value_counts().reindex(["Low", "Medium", "High"], fill_value=0)
    st.bar_chart(counts.rename("Records"), height=280)
    st.caption(title + " | historical records")


def comparison_frame(frame: pd.DataFrame, group_column: str, labels: dict[object, str]) -> pd.DataFrame:
    grouped = frame.assign(group=frame[group_column].map(labels)).groupby("group", dropna=False).agg(
        average_congestion=("congestion_level", "mean"),
        high_percentage=("congestion_class", lambda values: (values == "High").mean() * 100),
    )
    return grouped.reindex(list(labels.values())).reset_index()


def show_comparison(frame: pd.DataFrame, title: str, group_column: str, labels: dict[object, str]) -> None:
    comparison = comparison_frame(frame, group_column, labels)
    left, right = st.columns(2)
    with left:
        st.markdown("**Average historical congestion**")
        st.bar_chart(comparison.set_index("group")["average_congestion"], height=260)
    with right:
        st.markdown("**High-congestion records (%)**")
        st.bar_chart(comparison.set_index("group")["high_percentage"], height=260)
    st.caption(title + " | observed historical pattern, not causation")


def show_confusion(predictions: pd.DataFrame) -> None:
    classes = ["Low", "Medium", "High"]
    matrix = pd.crosstab(
        predictions["actual_congestion_class"], predictions["predicted_congestion_class"]
    ).reindex(index=classes, columns=classes, fill_value=0)
    figure, axis = plt.subplots(figsize=(6, 4.5))
    sns.heatmap(matrix, annot=True, fmt="d", cmap="Blues", cbar=False, ax=axis)
    axis.set_xlabel("Predicted congestion class")
    axis.set_ylabel("Actual congestion class")
    axis.set_title("Decision Tree: Actual vs Predicted Congestion")
    figure.tight_layout()
    st.pyplot(figure, use_container_width=True)
    plt.close(figure)


def filter_scenario(
    data: pd.DataFrame,
    corridor: str,
    day_type: str,
    festival: str,
    holiday: str,
    weather: str,
    roadwork: str,
) -> pd.DataFrame:
    """Filter historical records according to selected contextual scenario conditions."""
    result = data.copy()
    if corridor != "All Corridors":
        result = result[result["corridor"] == corridor]
    if day_type != "All":
        result = result[result["day_type"] == day_type]
    if festival != "All":
        result = result[result["festival_flag"] == (festival == "Festival")]
    if holiday != "All":
        result = result[result["holiday_flag"] == (holiday == "Holiday")]
    if weather != "All":
        result = result[result["weather"] == weather]
    if roadwork != "All":
        result = result[result["roadwork"] == roadwork]
    return result


def load_rf_benchmark_metrics(spec_path: Path) -> tuple[dict[str, float] | None, str | None]:
    """Load and validate Random Forest benchmark metrics without fabricating values."""
    if not spec_path.is_file():
        return None, f"Random Forest benchmark specification not found: {spec_path.name}"
    try:
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, f"Failed to read Random Forest specification: {exc}"
    evaluation = spec.get("evaluation")
    if not isinstance(evaluation, dict):
        return None, "Random Forest specification is missing a valid 'evaluation' section."
    required = ["Accuracy", "Weighted Precision", "Weighted Recall", "F1 Score"]
    metrics = {}
    for name in required:
        if name not in evaluation:
            return None, f"Random Forest benchmark metric '{name}' is missing."
        try:
            val = float(evaluation[name])
        except (TypeError, ValueError):
            return None, f"Random Forest benchmark metric '{name}' is not numeric: {evaluation[name]}."
        if not (0.0 <= val <= 1.0):
            return None, f"Random Forest benchmark metric '{name}' has value {val}, which is outside [0.0, 1.0]."
        metrics[name] = val
    return metrics, None


def calculate_class_metrics(confusion_matrix: pd.DataFrame) -> dict[str, dict[str, float | int]]:
    """Derive per-class Precision, Recall, F1, and Support from a confusion matrix.

    Classes are evaluated in order: High, Low, Medium.
    Assumes row index = actual class, column index = predicted class.
    Zero denominators are handled safely by returning 0.0.
    """
    classes = ["High", "Low", "Medium"]
    cm = confusion_matrix.reindex(index=classes, columns=classes, fill_value=0)
    results = {}
    for c in classes:
        tp = float(cm.loc[c, c])
        fp = float(cm[c].sum() - tp)
        fn = float(cm.loc[c].sum() - tp)
        support = int(cm.loc[c].sum())

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

        results[c] = {
            "Precision": precision,
            "Recall": recall,
            "F1": f1,
            "Support": support,
        }
    return results


def load_rf_confusion_matrix(benchmark_path: Path) -> tuple[pd.DataFrame | None, str | None]:
    """Load and validate Random Forest test confusion matrix from benchmark report."""
    if not benchmark_path.is_file():
        return None, f"Benchmark report not found: {benchmark_path.name}"
    try:
        text = benchmark_path.read_text(encoding="utf-8")
        lines = text.splitlines()
        csv_lines = []
        capture = False
        for line in lines:
            if "actual_class,predicted_class,count" in line:
                capture = True
            if capture:
                stripped = line.strip()
                if not stripped or stripped.startswith("---") or stripped.startswith("Random Forest Grouped") or stripped.startswith("Persistence"):
                    if csv_lines:
                        break
                else:
                    csv_lines.append(stripped)
        if not csv_lines:
            return None, "Random Forest confusion matrix not found in benchmark report."
        df = pd.read_csv(io.StringIO("\n".join(csv_lines)))
        classes = ["High", "Low", "Medium"]
        matrix = df.pivot(index="actual_class", columns="predicted_class", values="count").fillna(0).reindex(index=classes, columns=classes, fill_value=0).astype(int)
        return matrix, None
    except Exception as exc:
        return None, f"Failed to parse Random Forest confusion matrix: {exc}"


def load_rf_feature_importances(spec_path: Path) -> tuple[dict[str, float] | None, str | None]:
    """Load and validate Random Forest grouped feature importances from specification artifact."""
    if not spec_path.is_file():
        return None, f"Random Forest benchmark specification not found: {spec_path.name}"
    try:
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, f"Failed to read Random Forest specification: {exc}"

    if not isinstance(spec, dict) or "classifier" not in spec:
        return None, "Random Forest specification is missing valid model information."

    importances_raw = spec.get("grouped_feature_importances")
    if not isinstance(importances_raw, dict):
        return None, "Random Forest specification is missing 'grouped_feature_importances' mapping."

    expected_groups = [
        "traffic_volume", "travel_time_index", "area", "road_intersection",
        "corridor", "average_speed", "weather", "day_type",
        "day_of_week", "festival_flag", "roadwork", "holiday_flag",
    ]
    missing_groups = [g for g in expected_groups if g not in importances_raw]
    if missing_groups:
        return None, f"Missing expected feature group(s): {', '.join(missing_groups)}"

    importances = {}
    for name in expected_groups:
        val_raw = importances_raw[name]
        try:
            val = float(val_raw)
        except (TypeError, ValueError):
            return None, f"Feature importance for '{name}' is not numeric: {val_raw}"
        if val < 0.0:
            return None, f"Feature importance for '{name}' is negative: {val}"
        importances[name] = val

    total = sum(importances.values())
    if abs(total - 1.0) > 0.01:
        return None, f"Total grouped feature importance ({total:.6f}) deviates significantly from 1.0."

    return importances, None


def show_rf_feature_importance(importances: dict[str, float]) -> None:
    """Render a horizontal bar chart of Random Forest grouped feature importances."""
    series = pd.Series(importances).sort_values(ascending=True)
    figure, axis = plt.subplots(figsize=(8, 5))
    bars = axis.barh(series.index, series.values, color="#1f77b4", edgecolor="#0e4166", height=0.65)
    axis.set_xlabel("Relative Importance (Gini)")
    axis.set_ylabel("Feature Group")
    axis.set_title("Model Feature Importance (Random Forest Benchmark)")
    axis.set_xlim(0, max(series.values) * 1.15)
    for bar in bars:
        w = bar.get_width()
        axis.text(w + 0.005, bar.get_y() + bar.get_height() / 2, f"{w:.6f}", va="center", ha="left", fontsize=8)
    axis.spines["top"].set_visible(False)
    axis.spines["right"].set_visible(False)
    figure.tight_layout()
    st.pyplot(figure, use_container_width=True)
    plt.close(figure)


def render_smart_route_section() -> None:
    """Render Section 9: Smart Route Recommendation using OpenStreetMap and OSRM."""
    st.header("9. Smart Route Recommendation")
    st.caption("Open-source road-network route decision support powered by OpenStreetMap and OSRM.")
    st.caption(
        "Free, open-source routing and map visualization - completely independent of external paid APIs or cloud billing."
    )

    col1, col2 = st.columns(2)
    with col1:
        origin_val = st.text_input(
            "Origin",
            value="Koramangala, Bengaluru",
            help="Starting address, area, or landmark in Bengaluru",
            key="osm_route_origin",
        )
    with col2:
        dest_val = st.text_input(
            "Destination",
            value="Whitefield, Bengaluru",
            help="Destination address, area, or landmark in Bengaluru",
            key="osm_route_dest",
        )

    find_clicked = st.button("Find Routes", type="primary", key="btn_find_osm_routes")

    if find_clicked:
        if not origin_val.strip() or not dest_val.strip():
            st.error("Please enter both an Origin and a Destination.")
            st.session_state["osm_route_error"] = "Origin and Destination must not be empty."
            st.session_state["osm_route_data"] = None
        else:
            with st.spinner("Resolving locations and calculating routes via OpenStreetMap & OSRM..."):
                # 1. Geocode Origin
                orig_point, orig_err = geocode_location(origin_val.strip())
                if orig_err or not orig_point:
                    st.session_state["osm_route_error"] = f"Origin Geocoding Error: {orig_err}"
                    st.session_state["osm_route_data"] = None
                    st.session_state["osm_route_rationale"] = None
                else:
                    # 2. Geocode Destination
                    dest_point, dest_err = geocode_location(dest_val.strip())
                    if dest_err or not dest_point:
                        st.session_state["osm_route_error"] = f"Destination Geocoding Error: {dest_err}"
                        st.session_state["osm_route_data"] = None
                        st.session_state["osm_route_rationale"] = None
                    else:
                        # 3. Fetch OSRM Routes
                        osrm_resp, osrm_err = fetch_osrm_routes(orig_point, dest_point)
                        if osrm_err or not osrm_resp:
                            st.session_state["osm_route_error"] = f"OSRM Routing Error: {osrm_err}"
                            st.session_state["osm_route_data"] = None
                            st.session_state["osm_route_rationale"] = None
                        else:
                            parsed = parse_osrm_routes(osrm_resp)
                            ranked_routes, rationale = evaluate_and_recommend_routes(parsed)
                            folium_map = create_route_map(orig_point, dest_point, ranked_routes)
                            map_html = render_map_html(folium_map)

                            st.session_state["osm_route_data"] = ranked_routes
                            st.session_state["osm_route_rationale"] = rationale
                            st.session_state["osm_route_map_html"] = map_html
                            st.session_state["osm_route_error"] = None
                            st.session_state["osm_route_orig_display"] = orig_point.display_name
                            st.session_state["osm_route_dest_display"] = dest_point.display_name

    route_error = st.session_state.get("osm_route_error")
    routes_list = st.session_state.get("osm_route_data")
    routes_rationale = st.session_state.get("osm_route_rationale")
    map_html = st.session_state.get("osm_route_map_html")

    if route_error:
        st.error(route_error)
    elif routes_list:
        st.markdown("### Route Recommendation & Comparison")
        st.success(routes_rationale)

        # Route comparison table
        table_rows = []
        for r in routes_list:
            table_rows.append({
                "Route": f"Route {r.route_index}",
                "Summary Road": r.summary,
                "Distance": f"{r.distance_km} km",
                "Estimated Duration": r.duration_formatted,
                "Status": r.status,
                "Recommendation Rationale": r.recommendation_reason,
            })
        comparison_df = pd.DataFrame(table_rows)
        st.dataframe(comparison_df, use_container_width=True, hide_index=True)
        st.caption(
            "Distance and estimated duration are calculated by OSRM using OpenStreetMap road-network graphs and default speed profiles."
        )

        # Interactive OpenStreetMap with Folium / Leaflet
        st.markdown("### Interactive Route Map (OpenStreetMap / Leaflet)")
        components.html(map_html, height=520)
        st.caption(
            "Map rendered via Folium and Leaflet using OpenStreetMap tiles. "
            "Solid Blue = Recommended Route; Dashed Gray = Alternative Route(s). "
            "Click on markers or polylines to view location details."
        )

        # Historical Traffic Context
        with st.expander("Historical Traffic Context", expanded=False):
            st.info(
                "Historical congestion context is unavailable for this route because the "
                "project dataset does not contain a validated geographic mapping between route "
                "geometry and historical traffic corridors."
            )
            st.caption(
                "The project's historical dataset records traffic observations across 16 composite corridors "
                "(e.g., 'Indiranagar | 100 Feet Road') without latitude/longitude coordinates. "
                "In accordance with rigorous academic and scientific standards, the system does not "
                "invent GPS coordinates or guess road mappings."
            )

        # Live Traffic Limitation Note
        st.caption(
            "Live Traffic Note: Live/current traffic conditions are not provided by this open-source "
            "routing implementation. OSRM calculates routes based on static road-network topology."
        )

        # Architectural separation notice
        st.caption(
            "Architectural Note: The Smart Route Recommendation module operates as an open-source "
            "geographic decision-support tool. It is completely independent of the historical "
            "Spark ML congestion classification model."
        )


def main() -> None:
    require_files()
    integrated = load_csv(str(PATHS["integrated"]), ["date"])
    integrated["date"] = pd.to_datetime(integrated["date"])
    prediction_advisory = load_csv(str(PATHS["prediction_advisory"]), ["date"])
    prediction_advisory["date"] = pd.to_datetime(prediction_advisory["date"])
    top_average = load_csv(str(PATHS["top_average"])).set_index("corridor")
    top_percentage = load_csv(str(PATHS["top_percentage"])).set_index("corridor")
    metrics = parse_metrics(load_text(str(PATHS["prediction_summary"])))

    st.title("Smart Mobility: Bengaluru Traffic Congestion Analytics & Advisory")
    st.subheader("Festival & Weekend Travel Surge Prediction and Traffic Advisory System")
    st.info("Batch Historical Analysis")
    st.caption("Historical batch analysis only — not a real-time traffic monitoring or traffic-control system.")

    with st.sidebar:
        st.header("Historical filters")
        min_date = integrated["date"].min().date()
        max_date = integrated["date"].max().date()
        date_range = st.date_input("Date range", value=(min_date, max_date), min_value=min_date, max_value=max_date)
        if len(date_range) != 2:
            date_range = (min_date, max_date)
        corridors = st.multiselect("Corridor", sorted(integrated["corridor"].dropna().unique()), default=sorted(integrated["corridor"].dropna().unique()))
        classes = st.multiselect("Congestion class", ["Low", "Medium", "High"], default=["Low", "Medium", "High"])
        day_types = st.multiselect("Day type", sorted(integrated["day_type"].dropna().unique()), default=sorted(integrated["day_type"].dropna().unique()))
        festival_flag = st.selectbox("Festival flag", ["All", "True", "False"])
        holiday_flag = st.selectbox("Holiday flag", ["All", "True", "False"])
        st.caption("Filters use only fields available in the integrated historical dataset.")

    filters = {
        "date_range": date_range,
        "corridors": corridors,
        "classes": classes,
        "day_types": day_types,
        "festival_flag": festival_flag,
        "holiday_flag": holiday_flag,
    }
    filtered = apply_filters(integrated, filters)
    filtered_predictions = apply_filters(prediction_advisory, filters)

    st.header("1. Overview KPIs")
    high_count = int((filtered["congestion_class"] == "High").sum())
    kpis = st.columns(5)
    kpis[0].metric("Historical traffic records", f"{len(filtered):,}")
    kpis[1].metric("Average congestion level", f"{filtered['congestion_level'].mean():.2f}" if len(filtered) else "N/A")
    kpis[2].metric("High-congestion records", f"{high_count:,}")
    kpis[3].metric("High-congestion percentage", f"{high_count / len(filtered) * 100:.2f}%" if len(filtered) else "N/A")
    kpis[4].metric("Corridors", f"{filtered['corridor'].nunique():,}")

    st.header("2. Historical Congestion")
    a, b = st.columns(2)
    with a:
        st.markdown("**Congestion class distribution**")
        historical_bar(filtered, "congestion_class", "Bengaluru Historical Congestion Class Distribution", "Traffic records")
    with b:
        st.markdown("**Historical distribution source chart**")
        st.image(str(VISUALIZATIONS / "congestion_class_distribution.png"), use_container_width=True)
    show_comparison(filtered, "Weekday versus weekend", "day_type", {"Weekday": "Weekday", "Weekend": "Weekend"})
    show_comparison(filtered, "Festival versus non-festival", "festival_flag", {True: "Festival", False: "Non-Festival"})

    st.header("3. Corridor Analysis")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Top 5 corridors by average historical congestion**")
        st.dataframe(top_average.reset_index(), use_container_width=True, hide_index=True)
        st.image(str(VISUALIZATIONS / "top5_average_congestion.png"), use_container_width=True)
    with c2:
        st.markdown("**Top 5 corridors by high-congestion percentage**")
        st.dataframe(top_percentage.reset_index(), use_container_width=True, hide_index=True)
        st.image(str(VISUALIZATIONS / "top5_high_congestion_percentage.png"), use_container_width=True)

    st.header("4. Historical Scenario Analysis")
    st.caption("Historical Scenario Analysis — descriptive comparison of existing historical records.")
    st.caption("Explore how historical traffic indicators compare under specific contextual conditions.")

    with st.expander("Scenario Context Controls", expanded=True):
        sc_col1, sc_col2, sc_col3 = st.columns(3)
        with sc_col1:
            sc_corridor = st.selectbox(
                "Corridor",
                ["All Corridors"] + sorted(integrated["corridor"].dropna().unique().tolist()),
                key="scenario_corridor",
            )
            sc_day_type = st.selectbox(
                "Day type",
                ["All", "Weekday", "Weekend"],
                key="scenario_day_type",
            )
        with sc_col2:
            sc_festival = st.selectbox(
                "Festival",
                ["All", "Festival", "Non-Festival"],
                key="scenario_festival",
            )
            sc_holiday = st.selectbox(
                "Holiday",
                ["All", "Holiday", "Non-Holiday"],
                key="scenario_holiday",
            )
        with sc_col3:
            sc_weather = st.selectbox(
                "Weather",
                ["All"] + sorted(integrated["weather"].dropna().unique().tolist()),
                key="scenario_weather",
            )
            sc_roadwork = st.selectbox(
                "Roadwork",
                ["All", "Yes", "No"],
                key="scenario_roadwork",
            )
        st.caption("Controls operate on the integrated historical dataset (8,936 records) independently from sidebar filters.")

    scenario_records = filter_scenario(
        integrated,
        sc_corridor,
        sc_day_type,
        sc_festival,
        sc_holiday,
        sc_weather,
        sc_roadwork,
    )

    if len(scenario_records) == 0:
        st.info("No historical records match the selected scenario.")
    else:
        base_cong = integrated["congestion_level"].mean()
        base_high = (integrated["congestion_class"] == "High").mean() * 100
        base_speed = integrated["average_speed"].mean()
        base_vol = integrated["traffic_volume"].mean()
        base_tti = integrated["travel_time_index"].mean()

        sc_cong = scenario_records["congestion_level"].mean()
        sc_high = (scenario_records["congestion_class"] == "High").mean() * 100
        sc_speed = scenario_records["average_speed"].mean()
        sc_vol = scenario_records["traffic_volume"].mean()
        sc_tti = scenario_records["travel_time_index"].mean()

        st.markdown("**Scenario Historical Summary vs. All Historical Records**")
        sc_kpis = st.columns(6)
        sc_kpis[0].metric(
            "Historical records",
            f"{len(scenario_records):,}",
            help=f"Out of {len(integrated):,} total records",
        )
        sc_kpis[1].metric(
            "Avg congestion level",
            f"{sc_cong:.2f}",
            delta=f"{sc_cong - base_cong:+.2f} vs all",
        )
        sc_kpis[2].metric(
            "High-congestion %",
            f"{sc_high:.2f}%",
            delta=f"{sc_high - base_high:+.2f}% vs all",
        )
        sc_kpis[3].metric(
            "Avg speed (km/h)",
            f"{sc_speed:.2f}",
            delta=f"{sc_speed - base_speed:+.2f} vs all",
        )
        sc_kpis[4].metric(
            "Avg traffic volume",
            f"{sc_vol:,.0f}",
            delta=f"{sc_vol - base_vol:+,.0f} vs all",
        )
        sc_kpis[5].metric(
            "Avg travel time index",
            f"{sc_tti:.3f}",
            delta=f"{sc_tti - base_tti:+.3f} vs all",
        )
        st.caption("Historical comparison only — differences do not establish causation.")

        st.markdown(
            f"Historical records matching this scenario show an average congestion level of "
            f"**{sc_cong:.2f}** across **{len(scenario_records):,}** records, with "
            f"**{sc_high:.2f}%** classified as High congestion."
        )

        sc_chart1, sc_chart2 = st.columns(2)
        with sc_chart1:
            st.markdown("**Scenario congestion class distribution**")
            sc_class_counts = scenario_records["congestion_class"].value_counts().reindex(
                ["Low", "Medium", "High"], fill_value=0
            )
            st.bar_chart(sc_class_counts.rename("Records"), height=260)
            st.caption("Historical records in this scenario by congestion class.")

        with sc_chart2:
            st.markdown("**Historical average congestion comparison**")
            if sc_weather == "All":
                weather_avg = scenario_records.groupby("weather")["congestion_level"].mean()
                st.bar_chart(weather_avg.rename("Avg Congestion Level"), height=260)
                st.caption("Observed average congestion across weather categories in this scenario.")
            elif sc_day_type == "All":
                day_avg = scenario_records.groupby("day_type")["congestion_level"].mean()
                st.bar_chart(day_avg.rename("Avg Congestion Level"), height=260)
                st.caption("Observed average congestion by day type in this scenario.")
            else:
                comp_series = pd.Series({
                    "Selected Scenario": sc_cong,
                    "All Historical Data": base_cong,
                })
                st.bar_chart(comp_series.rename("Avg Congestion Level"), height=260)
                st.caption("Selected scenario average congestion vs. overall baseline.")

    st.header("5. ML Prediction")
    st.caption("Batch historical classification on a held-out chronological test set — not a real-time or time-series traffic forecast.")
    st.caption("Evaluation is based on the chronological test period.")
    st.write("Training period: **2022-01-01 to 2024-01-31**")
    st.write("Testing period: **2024-02-01 to 2024-08-09**")
    metric_columns = st.columns(4)
    for column, (name, value) in zip(metric_columns, metrics.items()):
        column.metric(name, f"{value:.6f}")
    show_confusion(prediction_advisory)
    st.bar_chart(prediction_advisory["predicted_congestion_class"].value_counts().reindex(["Low", "Medium", "High"], fill_value=0), height=280)

    st.subheader("ML Model Benchmark")
    rf_spec_path = PROJECT_ROOT / "models" / "random_forest_benchmark" / "model_specification.json"
    rf_metrics, rf_error = load_rf_benchmark_metrics(rf_spec_path)
    if rf_error:
        st.warning(f"Unable to display Random Forest benchmark: {rf_error}")
    else:
        st.markdown("**Random Forest Configuration**: 20 trees | max depth = 5 | seed = 42")
        benchmark_table = pd.DataFrame({
            "Metric": ["Accuracy", "Weighted Precision", "Weighted Recall", "F1 Score"],
            "Decision Tree": [
                f"{metrics['Accuracy']:.6f}",
                f"{metrics['Weighted Precision']:.6f}",
                f"{metrics['Weighted Recall']:.6f}",
                f"{metrics['F1']:.6f}",
            ],
            "Random Forest": [
                f"{rf_metrics['Accuracy']:.6f}",
                f"{rf_metrics['Weighted Precision']:.6f}",
                f"{rf_metrics['Weighted Recall']:.6f}",
                f"{rf_metrics['F1 Score']:.6f}",
            ],
        })
        st.dataframe(benchmark_table, use_container_width=True, hide_index=True)
    st.caption("Random Forest is benchmarked against the validated Decision Tree using the same chronological test period and feature pipeline.")

    st.markdown("**Per-Class Model Performance**")
    rf_benchmark_txt = OUTPUT / "ml_model_benchmark.txt"
    rf_cm, rf_cm_error = load_rf_confusion_matrix(rf_benchmark_txt)

    dt_cm = pd.crosstab(
        prediction_advisory["actual_congestion_class"],
        prediction_advisory["predicted_congestion_class"],
    ).reindex(index=["High", "Low", "Medium"], columns=["High", "Low", "Medium"], fill_value=0)

    if rf_cm_error:
        st.warning(f"Unable to display Random Forest per-class metrics: {rf_cm_error}")
    else:
        dt_class_metrics = calculate_class_metrics(dt_cm)
        rf_class_metrics = calculate_class_metrics(rf_cm)

        per_class_rows = []
        for c in ["High", "Low", "Medium"]:
            dt_m = dt_class_metrics[c]
            per_class_rows.append({
                "Class": c,
                "Model": "Decision Tree",
                "Precision": f"{dt_m['Precision']:.6f}",
                "Recall": f"{dt_m['Recall']:.6f}",
                "F1": f"{dt_m['F1']:.6f}",
                "Support": dt_m["Support"],
            })
            rf_m = rf_class_metrics[c]
            per_class_rows.append({
                "Class": c,
                "Model": "Random Forest",
                "Precision": f"{rf_m['Precision']:.6f}",
                "Recall": f"{rf_m['Recall']:.6f}",
                "F1": f"{rf_m['F1']:.6f}",
                "Support": rf_m["Support"],
            })

        per_class_df = pd.DataFrame(per_class_rows)
        st.dataframe(per_class_df, use_container_width=True, hide_index=True)
        st.caption("Per-class metrics are derived from the validated chronological test-set confusion matrices (2024-02-01 to 2024-08-09).")

    st.markdown("**Model Feature Importance (Random Forest Benchmark)**")
    rf_importances, rf_imp_error = load_rf_feature_importances(rf_spec_path)
    if rf_imp_error:
        st.warning(f"Unable to display Random Forest feature importance: {rf_imp_error}")
    else:
        show_rf_feature_importance(rf_importances)
        st.caption("Feature importance reflects how the model uses input variables for historical classification; it does not establish causation or physical traffic influence.")

    st.header("6. Rule-Based Traffic Advisory")
    advisory_counts = prediction_advisory["advisory_level"].value_counts().reindex(["Normal", "Moderate", "High"], fill_value=0)
    st.bar_chart(advisory_counts, height=280)
    advisory_columns = [
        "date", "corridor", "predicted_congestion_class", "advisory_level",
        "recommendation", "personnel_action", "diversion_action", "roadwork_action", "context_notes",
    ]
    st.dataframe(filtered_predictions[advisory_columns].sort_values(["date", "corridor"]), use_container_width=True, hide_index=True)
    st.caption("Recommendations are generated from predicted congestion class and contextual fields; actual congestion is used only for evaluation.")

    st.header("7. Context Analysis")
    context = st.columns(4)
    context[0].metric("Festival-related records", f"{int(filtered['festival_flag'].sum()):,}")
    context[1].metric("Holiday-related records", f"{int(filtered['holiday_flag'].sum()):,}")
    context[2].metric("Roadwork-related records", f"{int((filtered['roadwork'] == 'Yes').sum()):,}")
    context[3].metric("Adverse-weather records", f"{int(filtered['weather'].isin(['Rain', 'Fog']).sum()):,}")
    st.caption("These are associated observations in historical records, not causal findings.")

    st.header("8. Key Observations")
    predicted_high = int((prediction_advisory["predicted_congestion_class"] == "High").sum())
    advisory_high = int((prediction_advisory["advisory_level"] == "High").sum())
    st.markdown(
        "\n".join([
            f"- {len(filtered):,} historical traffic records are currently selected.",
            f"- {filtered['corridor'].nunique():,} corridors are represented in the current selection.",
            f"- Selected historical classes: Low {int((filtered['congestion_class'] == 'Low').sum()):,}, Medium {int((filtered['congestion_class'] == 'Medium').sum()):,}, High {int((filtered['congestion_class'] == 'High').sum()):,}.",
            f"- Decision Tree test accuracy is {metrics['Accuracy']:.6f} on the chronological test period.",
            f"- The test output contains {predicted_high:,} predicted High-congestion records.",
            f"- The test output contains {advisory_high:,} High advisory records.",
        ])
    )

    # 9. Smart Route Recommendation
    render_smart_route_section()

    with st.expander("Data Sources & Limitations"):
        st.markdown(
            "\n".join([
                "Primary traffic source: public Bengaluru historical traffic dataset used in this project.",
                "",
                "Festival/holiday information is based on the project's curated Karnataka holiday calendar.",
                "",
                "Supplementary toll/signal synthetic data is not represented as official live transaction/event data.",
                "",
                "Geospatial GIS mapping is intentionally excluded because the project dataset does not contain a validated latitude/longitude coordinate source.",
                "",
                "Current implementation is batch-based and does not provide real-time traffic monitoring.",
                "",
                "Open-source Smart Route Recommendation (OpenStreetMap + OSRM) provides road-network routing and route comparison without requiring paid APIs or live traffic feeds; it does not modify or train upon historical Spark dataset records.",
            ])
        )


if __name__ == "__main__":
    main()
