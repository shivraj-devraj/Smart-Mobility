# Interactive Dashboard

This Streamlit application presents validated batch historical traffic analysis, corridor summaries, festival/holiday comparisons, Decision Tree test performance, Random Forest benchmark, predicted congestion, rule-based advisories, and an open-source road-network Smart Route Recommendation module.

The dashboard preserves the validated batch outputs of the Spark and MLlib pipeline without modifying or recomputing existing artifacts.

---

## Dashboard Sections

1. **Overview KPIs**: High-level traffic record counts, average congestion levels, high-congestion proportions, and active corridor count.
2. **Historical Congestion**: Distribution of observed congestion classes, weekday vs. weekend comparisons, and festival vs. non-festival patterns.
3. **Corridor Analysis**: Top 5 corridors ranked by average historical congestion and high-congestion record percentage.
4. **Historical Scenario Analysis**: Multi-dimensional contextual what-if analysis across corridor, day type, festival, holiday, weather, and roadwork dimensions.
5. **ML Prediction & Benchmark**: Decision Tree test performance metrics and confusion matrix, benchmarked against a 20-tree Random Forest classifier with per-class metrics and grouped feature importance.
6. **Rule-Based Traffic Advisory**: Deterministic, traceable recommendations generated from predicted congestion classes and operational triggers.
7. **Context Analysis**: High-level counts of contextual observations (festivals, holidays, adverse weather, roadwork).
8. **Key Observations**: Summary points and limitations of the historical batch pipeline.
9. **Smart Route Recommendation**: Open-source route decision support powered by OpenStreetMap, OSRM, and Folium.

---

## 9. Smart Route Recommendation Module (Open-Source Stack)

The Smart Route Recommendation module provides free, open-source driving route calculation and interactive map visualization between arbitrary Bengaluru locations (e.g., Koramangala to Whitefield).

### Core Components
- **Geocoding**: OpenStreetMap Nominatim service for address-to-coordinate resolution, with in-memory caching and custom User-Agent throttling to respect usage policies.
- **Routing Engine**: Open Source Routing Machine (OSRM) driving profile for calculating road-network driving distances, estimated durations, and GeoJSON geometry.
- **Map Visualization**: Interactive Leaflet map rendered using Folium and OpenStreetMap tiles with origin/destination markers and visually distinguished route polylines.
- **Cost & Dependencies**: **100% Free & Open-Source**. Requires **no** API keys, **no** cloud accounts, and **no** paid billing.

### Architectural Boundary & Separation of Concerns
- **Historical Big Data Pipeline**: Apache Spark, Spark SQL, and Spark MLlib operate strictly on historical batch records (2022–2024) across 16 composite corridors. The historical dataset has no GPS coordinates.
- **Route Recommendation Layer**: An external, open-source routing decision-support tool. It computes driving paths dynamically over the OpenStreetMap road network.
- **Zero Fabrication**: The system never invents GPS coordinates or attempts unvalidated spatial mapping between OpenStreetMap geometries and historical dataset corridors.

### Transparent Recommendation Logic
The recommendation engine uses deterministic, transparent rules:
1. Candidate routes returned by OSRM are ranked primarily by lowest estimated duration (`duration_seconds`).
2. If estimated durations are comparable (within 60 seconds), tie-breaking prioritizes the route with shorter physical travel distance (`distance_km`).
3. The top route is marked **Recommended** with the exact time/distance comparison vs alternatives. Other paths are labeled **Alternative**.
4. When only one route is returned by OSRM, it is labeled **Available Route** without claiming alternatives exist.
5. Recommendations are explicitly attributed to OSRM road-network calculations and are never conflated with Spark ML predictions.

### Traffic & Congestion Limitations
- **No Live Traffic**: Live/current traffic conditions and congestion layers are **not** provided by this free, open-source implementation. OSRM computes durations based on static road-network topologies and default speed profiles.
- **Historical Congestion Context**: Historical corridor context is omitted for arbitrary routes because the project dataset lacks validated geographic road-to-corridor mappings. The panel explicitly displays:
  > *"Historical congestion context is unavailable for this route because the project dataset does not contain a validated geographic mapping between route geometry and historical traffic corridors."*

---

## Run

From the project root:

```powershell
streamlit run dashboard/app.py
```

No API keys or cloud credentials are required to launch or use the dashboard.
