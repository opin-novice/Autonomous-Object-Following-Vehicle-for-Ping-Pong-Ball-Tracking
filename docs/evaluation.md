# Evaluation Metrics & Reporting

## Overview

The evaluation system computes performance metrics from the tracking log CSV generated during simulation runs. All metrics are derived solely from the recorded data—no fabricated numbers are used.

## Quick Start

```bash
# Run a 30-second simulation
$env:BALL_FOLLOWER_HEADLESS=1
$env:BALL_FOLLOWER_RUN_SECONDS=30
& "C:\Users\USER\Webots\msys64\mingw64\bin\webots.exe" --batch --mode=fast --no-rendering --minimize "d:\Autonomous Car\webots\worlds\ping_pong_follower.wbt"

# Compute metrics from the tracking log
.venv\Scripts\python.exe scripts/run_evaluation.py
```

## Metrics Computed

### Detection Rate (Detection Rate %)
Percentage of frames where the ball was detected (`ball_detected == 1`).
- **Range:** 0–100%
- **Ideal:** 100% (always sees the ball)
- **Interpretation:** High rates indicate robust vision across the operating range.

### Tracking Success Rate (Tracking Success Rate %)
Percentage of frames where the robot was in `TRACKING` or `APPROACHING` state.
- **Range:** 0–100%
- **Ideal:** High during active following
- **Interpretation:** Time spent actively pursuing the ball vs. searching or idle.

### Image Error: Mean & Maximum

**MAE (Mean Absolute Error)**
- Mean of |image_error| across all frames where the ball was detected
- **Units:** pixels
- **Ideal:** < 5 px (well-centered)
- **Interpretation:** Centering accuracy; lower is better.

**Maximum Error**
- Largest |image_error| observed
- **Units:** pixels
- **Interpretation:** Peak centering deviation; identifies overshoot events.

### Response Time (Response Time)
Time from the first frame of the simulation to the first frame where |image_error| < 5 px (first centered).
- **Units:** seconds
- **Ideal:** < 1.0 s
- **Interpretation:** How quickly the robot acquired and centered the ball.
- **N/A:** If the ball never enters the 5 px window.

### Final Distance Error (Final Distance Error)
Mean absolute distance error over the last 50 frames, comparing `estimated_distance` to the target distance (0.40 m).
- **Units:** meters
- **Ideal:** < 0.05 m (5 cm)
- **Interpretation:** How close to the target holding distance the robot settled.
- **N/A:** If no valid distance measurements in the final window.

### Recovery Time (Recovery Time)
Average time from when the ball is lost (detection transitions 1→0) to re-acquisition (0→1).
- **Units:** seconds
- **Ideal:** < 0.5 s (quick recovery)
- **Interpretation:** Robustness of the search/re-acquisition logic.
- **N/A:** If no loss/recovery events occur.

**Number of Recoveries**
- Count of how many times the robot lost and re-found the ball.
- **Ideal:** 0 (never loses sight)

### Frame Rate (Average FPS)
Average sampling rate of the log in Hz.
- **Typical:** ~31.25 Hz (32 ms timestep)
- **Interpretation:** Consistency check; confirms timestep.

## CSV Schema

The input tracking log uses this schema (12 columns):

| Column | Type | Notes |
|---|---|---|
| timestamp | float | Simulation time in seconds |
| ball_detected | int | 1 if ball found, 0 if not |
| ball_x | float | Pixel column of ball center (or empty) |
| ball_y | float | Pixel row of ball center (or empty) |
| ball_radius | float | Detected ball radius in pixels (or empty) |
| estimated_distance | float | Range in meters (or empty if invalid) |
| image_error | float | Horizontal pixel offset from image center (or empty) |
| linear_velocity | float | Forward speed command (m/s or rad/s depending on implementation) |
| angular_velocity | float | Rotation speed command (rad/s) |
| left_motor_velocity | float | Left wheel velocity (rad/s) |
| right_motor_velocity | float | Right wheel velocity (rad/s) |
| state | string | FSM state name (SEARCHING, TRACKING, APPROACHING, STOPPED, IDLE, etc.) |

Missing ball fields are encoded as empty strings (""), not NaN or None.

## Implementation Details

### load_log(csv_path)
Reads a tracking CSV into a dict of numpy arrays.

**Args:**
- `csv_path`: Path to the tracking log CSV.

**Returns:**
- Dict with keys: `['timestamp', 'ball_detected', 'ball_x', 'ball_y', 'ball_radius', 'estimated_distance', 'image_error', 'linear_velocity', 'angular_velocity', 'left_motor_velocity', 'right_motor_velocity', 'state']`
- Numeric columns are numpy arrays (NaN for missing values); `'state'` is an object array.

**Raises:**
- `FileNotFoundError` if the CSV does not exist.

### compute_metrics(log)
Computes all metrics from the loaded log.

**Args:**
- `log`: Dict returned by `load_log()`.

**Returns:**
- Dict with metric names and values:
  - `detection_rate_pct`
  - `tracking_success_rate_pct`
  - `mae_px`
  - `max_error_px`
  - `response_time_s` (or None)
  - `final_distance_error_m` (or None)
  - `recovery_time_s` (or None)
  - `num_recoveries`
  - `fps`

### format_report(metrics)
Formats the metrics dict as a readable multi-line report string.

## Usage Examples

### Programmatic
```python
import sys
sys.path.insert(0, 'scripts')
import run_evaluation

log = run_evaluation.load_log('results/logs/tracking_log.csv')
metrics = run_evaluation.compute_metrics(log)
report = run_evaluation.format_report(metrics)
print(report)
```

### Command Line
```bash
.venv\Scripts\python.exe scripts/run_evaluation.py results/logs/tracking_log.csv results/logs/evaluation_report.txt
```

## Test Coverage

The evaluation module has 19 unit tests covering:
- CSV loading with empty fields and multiple rows
- Detection and tracking rate calculations
- Error metrics (MAE, max error)
- Response time detection
- Final distance error over the last 50 frames
- Recovery time computation (single and multiple losses)
- Frame rate calculation
- Report formatting with None values

Run tests:
```bash
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Example Output

```
============================================================
EVALUATION REPORT
============================================================

Detection Rate:             100.00 %
Tracking Success Rate:       88.45 %

Mean Absolute Error (MAE):    2.34 px
Maximum Error:               15.67 px

Response Time:               0.256 s
Final Distance Error:       0.0215 m

Recovery Time (avg):         0.512 s
Number of Recoveries:            2

Average FPS:                 31.25 Hz

============================================================
```

## Design Rationale

1. **No Fabrication:** Every number in a report is extracted directly from the CSV. Metrics are never guessed or estimated.
2. **Minimal Requirements:** The evaluation needs only the tracking log CSV—no supervisor ground truth, no external data.
3. **Robustness:** All metrics handle missing/invalid data gracefully (empty strings, NaN) and report N/A where appropriate.
4. **Testability:** Pure functions (`load_log`, `compute_metrics`, `format_report`) allow comprehensive unit testing without simulation.

## Related Files

- `scripts/run_evaluation.py` — Main evaluation module
- `tests/test_evaluation.py` — Unit tests
- `webots/controllers/ball_follower/logger.py` — Log generation
- `results/logs/tracking_log.csv` — Input log file (generated by simulation)
- `results/logs/evaluation_report.txt` — Output report file

## Future Extensions

1. **Scenario-specific metrics:** Time to approach, approach smoothness, overshoots
2. **Comparative plots:** Distance profile, image error over time, FPS graph
3. **Batch evaluation:** Run multiple scenarios and compare reports
4. **Regression detection:** Flag metrics that drop below historical baselines
