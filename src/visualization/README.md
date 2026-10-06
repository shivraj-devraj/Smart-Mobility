# Phase 8A Core Visualization

This phase creates eight reproducible static academic charts from validated Phase 5, Phase 6B, and Phase 7B outputs. It uses pandas for CSV reading and matplotlib/seaborn for plotting. It does not use Spark for plotting and does not create a web dashboard.

## Charts

- `congestion_class_distribution.png`: historical Low/Medium/High record counts.
- `top5_average_congestion.png`: top five corridors by average historical congestion level.
- `top5_high_congestion_percentage.png`: top five corridors by high-congestion percentage.
- `festival_vs_nonfestival.png`: observed festival versus non-festival average congestion and high-congestion percentage.
- `weekday_vs_weekend.png`: observed weekday versus weekend average congestion and high-congestion percentage.
- `actual_vs_predicted_confusion_matrix.png`: Decision Tree test-set confusion matrix.
- `predicted_congestion_distribution.png`: predicted class distribution on the chronological test set.
- `advisory_distribution.png`: rule-based advisory-level distribution for predicted test classes.

All outputs are written under `data/output/visualizations/`. The module also writes `visualization_summary.txt` with each chart's source, output path, file size, and validation status.

The congestion charts describe the dataset's historical congestion measure. Festival, weekday/weekend, prediction, and advisory charts show observed batch results only; they do not establish causation or represent real-time traffic. Unavailable hourly, directional, GPS, FASTag, live, and signal-event dimensions are not fabricated.

## Run

```powershell
python -m src.visualization.create_visualizations
```
