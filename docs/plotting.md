# Visualization & Plotting

## Overview

The plotting module generates publication-quality charts from tracking simulation logs. All plots are created in headless mode (no GUI windows) and support high-DPI output (300 DPI default) for reports and papers.

## Quick Start

```bash
# Generate all plots from the tracking log
.venv\Scripts\python.exe scripts/plot_results.py

# Custom input/output paths
.venv\Scripts\python.exe scripts/plot_results.py --input custom.csv --output-dir ./figures --dpi 150
```

## Generated Plots

All plots are saved as high-resolution PNG files in `results/plots/`:

### 1. tracking_error_vs_time.png
**Horizontal Centering Accuracy**
- X-axis: Time (s)
- Y-axis: Image Error (px)
- Red line: Horizontal offset from image center (319.5 px)
- Black dashed line: Zero error reference
- Shaded area: Error magnitude
- **Interpretation:** Smooth tracking with minimal deviation indicates good centering control.

### 2. distance_vs_time.png
**Approach Distance Profile**
- X-axis: Time (s)
- Y-axis: Distance (m)
- Blue line: Estimated distance to ball
- Red dashed line: Target distance (0.40 m)
- **Interpretation:** Shows approach trajectory; good plots converge to target and hold steady.

### 3. motor_speeds_vs_time.png
**Motor Velocity Commands**
- X-axis: Time (s)
- Y-axis: Motor Velocity (rad/s)
- Green line: Left wheel velocity
- Orange line: Right wheel velocity
- **Interpretation:** Speed differences indicate steering; symmetric speeds indicate forward motion.

### 4. ball_position_vs_center.png
**Ball Horizontal Position**
- X-axis: Time (s)
- Y-axis: Ball X Position (px)
- Blue line: Ball X coordinate
- Red dashed line: Image center (319.5 px)
- **Interpretation:** Oscillation around center line indicates centering tracking.

### 5. detection_status_vs_time.png
**Detection & FSM State Timeline**
- X-axis: Time (s)
- Y-axis: Detection status (0/1) and FSM states
- Shaded area: Detection status (1 = detected, 0 = lost)
- Colored markers: FSM state (TRACKING, APPROACHING, SEARCHING, etc.)
- **Interpretation:** Continuous detection = 100% at top; gaps show search periods.

### 6. summary_dashboard.png
**Combined 2×3 Grid Dashboard**
- Combines the five main plots in a single figure for reports/papers
- Professional layout suitable for publication
- Single file for easy insertion into documents

## Implementation Details

### load_log(csv_path)
Loads tracking CSV into arrays, converting empty strings to NaN.

**Args:**
- `csv_path`: Path to tracking_log.csv

**Returns:**
- Dict with all 12 columns as numpy arrays (NaN for missing values)

### Individual Plot Functions
```python
plot_tracking_error(ax, log)     # Image centering error
plot_distance(ax, log)           # Approach distance
plot_motor_speeds(ax, log)       # Motor commands
plot_ball_position(ax, log)      # Ball X position
plot_detection_status(ax, log)   # Detection & FSM state
```

Each function takes an axes object and log dict, adding appropriate lines, labels, grid, and legend.

### create_individual_plots(log, output_dir, dpi=300)
Generates 5 individual high-quality plots.

### create_summary_dashboard(log, output_path, dpi=300)
Generates a combined 2×3 grid dashboard.

## CLI Arguments

```
--input PATH           Path to tracking log CSV (default: results/logs/tracking_log.csv)
--output-dir DIR       Output directory (default: results/plots)
--dpi INT              Plot DPI resolution (default: 300)
```

## Professional Design Features

✅ **High DPI (300 default)** — Suitable for print and publication  
✅ **Color Palette** — Distinct colors for each data series  
✅ **Grid Lines** — Subtle background grid for readability  
✅ **Clear Labels** — All axes labeled with units (s, px, m, rad/s)  
✅ **Legends** — Each plot includes legend with data names  
✅ **Headless Mode** — No GUI windows; works in automated pipelines  
✅ **NaN Handling** — Missing data creates clean gaps, not false zeros  

## Color Scheme

| Use | Color | Hex |
|-----|-------|-----|
| Image Error | Red | #e74c3c |
| Distance | Blue | #3498db |
| Left Motor | Green | #2ecc71 |
| Right Motor | Orange | #f39c12 |
| Detection | Purple | #9b59b6 |
| Grid | Light Gray | #ecf0f1 |

## Testing

### Unit Tests (tests/test_plotter.py)
- 15 tests covering CSV loading, plot creation, and missing data handling
- All tests run without Webots or display server
- Verifies PNG file generation and sizing

### Integration Test
```bash
# Run on real simulation log
.venv\Scripts\python.exe scripts/plot_results.py

# Verify output files
ls -lh results/plots/*.png
```

## Usage Examples

### Programmatic
```python
import sys
sys.path.insert(0, 'scripts')
import plot_results

log = plot_results.load_log('results/logs/tracking_log.csv')
fig, ax = plt.subplots()
plot_results.plot_distance(ax, log)
plt.savefig('distance.png', dpi=300, bbox_inches='tight')
```

### Batch Processing
```bash
for sim in sim_1 sim_2 sim_3; do
    .venv\Scripts\python.exe scripts/plot_results.py \
        --input results/$sim/tracking_log.csv \
        --output-dir results/$sim/plots
done
```

## Performance

- **Load Time:** ~200 ms for 1876-frame log
- **Plot Time:** ~1–2 s per individual plot (low DPI)
- **Memory:** ~20 MB for full dashboard
- **Output Size:** ~150 KB per individual plot (300 DPI), ~450 KB for dashboard

## Common Issues

### No output files created
- Verify input CSV path is correct
- Check output directory is writable
- Run with `--dpi 100` for faster debugging

### Plots look too small/large
- Adjust `--dpi` flag (100 for draft, 300 for publication)
- Adjust figure size in `create_individual_plots()` or `create_summary_dashboard()`

### Missing data creates gaps
- This is intentional: empty strings in CSV → NaN in arrays → gaps in plots
- Use `-\-` to handle this in matplotlib; we use NaN for clean gaps

## Related Files

- `scripts/plot_results.py` — Main plotting module (214 lines)
- `tests/test_plotter.py` — Unit tests (243 lines)
- `results/logs/tracking_log.csv` — Input log file (generated by simulation)
- `results/plots/` — Output directory for all generated plots

## Future Extensions

1. **Animated GIFs** — Time-series animation of the approach
2. **Statistics overlays** — Add metrics (MAE, response time) to plots
3. **Multi-run comparison** — Side-by-side plots from multiple scenarios
4. **Frequency analysis** — FFT of image error and motor commands
5. **Phase portraits** — Distance vs. velocity phase plane
