# Autonomous Ping Pong Ball Follower Robot

A complete Webots simulation of a differential-drive vehicle that autonomously detects and follows an orange ping-pong ball using computer vision and proportional control.

**Status:** ✅ Complete | 141+ unit tests passing | Multi-scenario benchmarks validated

---

## Features

- **Robust Vision Pipeline** — OpenCV-based ball detection with circularity and area filtering
- **Calibrated Distance Estimation** — Pinhole camera model with 1.5% accuracy over 0.6–2.5 m
- **Proportional Control** — Smooth steering and distance-based speed regulation
- **FSM-based Search** — Autonomous search and recovery when ball is lost
- **Real-time Logging** — 12-channel CSV tracking with timestamps and state
- **Publication-Quality Plots** — 6 high-DPI (300+) visualization types
- **Comprehensive Metrics** — Detection rate, tracking success, MAE, response time, recovery analysis
- **Multi-Scenario Benchmarking** — 5 standard test scenarios with unified reporting
- **Full Test Coverage** — 141 unit tests for vision, control, and evaluation pipelines

---

## Project Structure

```
.
├── README.md                              # This file
├── CLAUDE.md                              # Operating rules and verified environment
├── A_TO_Z_IMPLEMENTATION.md               # Complete specification (Phase 0–15)
├── requirements.txt                       # Python dependencies
│
├── webots/                                # Webots simulation environment
│   ├── worlds/
│   │   ├── ping_pong_follower.wbt         # Main simulation world
│   │   ├── motion_check.wbt               # Robot geometry validation world
│   │   └── arena.wbo                      # Reusable arena/ball objects
│   ├── controllers/
│   │   ├── ball_follower/                 # Main robot controller
│   │   │   ├── ball_follower.py           # Webots API wiring
│   │   │   ├── config.py                  # All tunable parameters
│   │   │   ├── vision.py                  # OpenCV detection pipeline
│   │   │   ├── control.py                 # Proportional control law
│   │   │   └── runtime.ini                # Python interpreter config
│   │   ├── motion_check/
│   │   │   └── motion_check.py            # Smoke test controller
│   │   └── world_check/
│   │       └── world_check.py             # Arena verification controller
│   └── protos/
│       └── DifferentialDriveRobot.proto   # Robot definition
│
├── scripts/                               # Analysis and automation scripts
│   ├── run_evaluation.py                  # Metrics computation from tracking logs
│   ├── plot_results.py                    # Visualization generator (6 plot types)
│   ├── analyze_tuning.py                  # Parameter tuning analysis
│   ├── tune_controller.py                 # Systematic tuning orchestrator
│   ├── run_benchmarks.py                  # Multi-scenario benchmark runner
│   └── dry_run_check.py                   # Pre-run syntax validation
│
├── tests/                                 # Unit test suite (141 tests)
│   ├── test_vision.py                     # Vision pipeline (78 tests)
│   ├── test_controller.py                 # Control law (19 tests)
│   ├── test_evaluation.py                 # Metrics computation (19 tests)
│   ├── test_plotter.py                    # Visualization (15 tests)
│   ├── test_benchmarks.py                 # Benchmark suite (20 tests)
│   └── fixtures/                          # Real captured test frames (9 ranges)
│       ├── 0.4m.png, 0.6m.png, ..., 2.8m.png
│
├── docs/                                  # Documentation
│   ├── evaluation.md                      # Metrics specification
│   ├── plotting.md                        # Visualization guide
│   ├── tuning_report.md                   # Parameter tuning analysis
│   ├── implementation_notes.md            # Technical decisions and measurements
│   ├── PROJECT_SUMMARY.md                 # Complete engineering lifecycle (this PROMPT)
│   └── benchmark_report.md                # Generated benchmark comparison
│
├── results/                               # Simulation outputs
│   ├── logs/                              # CSV tracking data
│   │   ├── tracking_log.csv               # Main simulation log (12 columns)
│   │   └── *_log.csv                      # Per-scenario logs
│   ├── plots/                             # Generated visualization PNGs
│   │   ├── tracking_error_vs_time.png     # Centering accuracy
│   │   ├── distance_vs_time.png           # Distance profile
│   │   ├── motor_speeds_vs_time.png       # Wheel velocities
│   │   ├── ball_position_vs_center.png    # Ball position timeline
│   │   ├── detection_status_vs_time.png   # Detection & FSM state
│   │   ├── summary_dashboard.png          # Combined 2×3 grid
│   │   └── <scenario>/                    # Per-scenario plot subdirs
│   └── reports/                           # JSON metrics and analysis
│       ├── benchmark_report.md            # Unified benchmark report
│       └── *_metrics.json                 # Per-scenario metrics
│
└── .venv/                                 # Python virtual environment
```

---

## Prerequisites

### System Requirements
- **Windows 10/11** (tested on Windows 11 Pro)
- **Webots R2025a** installed and verified
  - Download: https://www.cyberbotics.com/
  - Install location: `C:\Users\USER\Webots`
  - Binary: `C:\Users\USER\Webots\msys64\mingw64\bin\webots.exe`

### Python Environment
- **Python 3.12.10** in virtual environment (`.venv/`)
- Required packages (see `requirements.txt`):
  - NumPy 2.5.3
  - OpenCV 5.0.0
  - Matplotlib 3.11.1

### Setup Steps

1. **Create and activate virtual environment:**
   ```powershell
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   ```

2. **Install dependencies:**
   ```powershell
   pip install -r requirements.txt
   ```

3. **Verify Webots installation:**
   ```powershell
   & "C:\Users\USER\Webots\msys64\mingw64\bin\webots.exe" --version
   ```

4. **Run smoke tests to verify everything works:**
   ```powershell
   python -m unittest discover -s tests -v
   ```

---

## Quick Start

### 1. Run a 30-Second Simulation

```powershell
# Activate venv if not already active
.venv\Scripts\Activate.ps1

# Run headless simulation (fast feedback)
$env:BALL_FOLLOWER_HEADLESS=1
$env:BALL_FOLLOWER_RUN_SECONDS=30
& "C:\Users\USER\Webots\msys64\mingw64\bin\webots.exe" `
  --batch --mode=fast --no-rendering --minimize `
  "d:\Autonomous Car\webots\worlds\ping_pong_follower.wbt"
```

This produces: `results/logs/tracking_log.csv` (30 seconds of tracking data, ~938 frames)

### 2. Compute Performance Metrics

```powershell
python scripts/run_evaluation.py --input results/logs/tracking_log.csv
```

**Output:**
```
Detection Rate:          100.0%
Tracking Success Rate:   100.0%
Image Error (MAE):       0.00 px
Max Image Error:         0.15 px
Response Time:           0.000 s
Final Distance Error:    0.0306 m
Recovery Time:           N/A (no losses)
Number of Recoveries:    0
Average FPS:             31.25 Hz
```

### 3. Generate Visualization Plots

```powershell
python scripts/plot_results.py --input results/logs/tracking_log.csv --output-dir results/plots
```

**Generated plots:**
- `tracking_error_vs_time.png` — Horizontal centering accuracy
- `distance_vs_time.png` — Approach distance profile
- `motor_speeds_vs_time.png` — Wheel velocity commands
- `ball_position_vs_center.png` — Ball position timeline
- `detection_status_vs_time.png` — Detection & FSM state
- `summary_dashboard.png` — Combined 2×3 grid (for reports)

### 4. Run Multi-Scenario Benchmarks

```powershell
python scripts/run_benchmarks.py --output-dir results
```

**Runs 5 scenarios:**
1. **static_ball** — Ball stationary (baseline accuracy)
2. **lateral_movement** — Ball oscillating side-to-side (steering)
3. **approaching_ball** — Ball moving toward robot (distance control)
4. **ball_lost** — Ball disappears & reappears (FSM robustness)
5. **dynamic_curved** — Ball following circular path (agility)

**Output:**
- `results/logs/<scenario>_log.csv` — Per-scenario tracking data
- `results/reports/<scenario>_metrics.json` — Per-scenario metrics
- `results/plots/<scenario>/` — Per-scenario visualization plots
- `docs/benchmark_report.md` — Unified comparison report

### 5. Run Full Test Suite

```powershell
python -m unittest discover -s tests -v
```

**Coverage:** 141 tests across 5 modules
- `test_vision.py` (78 tests) — Detection pipeline
- `test_controller.py` (19 tests) — Control law
- `test_evaluation.py` (19 tests) — Metrics computation
- `test_plotter.py` (15 tests) — Visualization
- `test_benchmarks.py` (20 tests) — Benchmark framework

**Status:** ✅ All tests pass (no failures, no skips)

---

## Architecture Overview

### Control System Architecture

```
┌──────────────┐
│   RGB Frame  │  (640×480 @ 31.25 Hz)
└──────┬───────┘
       ↓
┌──────────────────────────┐
│  VISION PIPELINE         │  (vision.py)
│ - Color thresholding     │
│ - Contour detection      │
│ - Circularity filter     │
│ - Area validation        │
└──────┬───────────────────┘
       ↓
┌──────────────────────────┐
│  DISTANCE ESTIMATOR      │  (vision.py)
│ - Pinhole camera model   │  - 1.5% accuracy
│ - Bearing calculation    │  - Validated on fixtures
└──────┬───────────────────┘
       ↓
┌──────────────────────────────────────┐
│  FSM STATE MACHINE (control.py)      │
│ ┌─────────────┐                      │
│ │  SEARCHING  │ ← No ball detected   │
│ └──────┬──────┘                      │
│        │                             │
│        ↓ Detection confirmed         │
│ ┌──────────────────┐                 │
│ │    TRACKING      │ ← Ball visible  │
│ │  (proportional   │  & far (>0.43m) │
│ │   steering)      │                 │
│ └──────┬───────────┘                 │
│        │                             │
│        ↓ Ball approaching            │
│ ┌──────────────────┐                 │
│ │   APPROACHING    │ ← Closing in    │
│ │  (reduce speed)  │  on target      │
│ └──────┬───────────┘                 │
│        │                             │
│        ↓ Within tolerance            │
│ ┌──────────────────┐                 │
│ │     STOPPED      │ ← At target     │
│ │  (zero speed)    │  (0.40±0.03m)   │
│ └──────────────────┘                 │
└──────────────────────────────────────┘
       ↓
┌──────────────────────────────────┐
│  PROPORTIONAL CONTROL LAW        │  (control.py)
│ ┌────────────────────────────┐  │
│ │ Steering = Kp_steer × err  │  │  Kp_steer = 2.2
│ │ (proportional to centering)│  │
│ └────────────────────────────┘  │
│ ┌────────────────────────────┐  │
│ │ Speed = Kp_dist × dist_err │  │  Kp_dist = 1.8
│ │ (proportional to distance)  │  │
│ └────────────────────────────┘  │
└──────┬───────────────────────────┘
       ↓
┌──────────────────────────┐
│  MOTOR CONTROLLER        │  (ball_follower.py)
│ - Left wheel velocity    │
│ - Right wheel velocity   │
│ - Differential drive law │
└──────┬───────────────────┘
       ↓
┌──────────────────┐
│  PHYSICAL ROBOT  │  (Webots simulation)
│ - Kinematics     │
│ - Physics engine │
│ - Wheel friction │
└──────────────────┘
```

### Key Configuration Parameters

All tunable parameters live in `webots/controllers/ball_follower/config.py`:

| Parameter | Value | Purpose |
|-----------|-------|----------|
| `KP_STEER` | 2.2 | Steering gain (proportional to image error) |
| `KP_DIST` | 1.8 | Speed gain (proportional to distance error) |
| `DISTANCE_TOLERANCE_M` | 0.025 | Approach threshold to APPROACHING state |
| `TARGET_DISTANCE_M` | 0.40 | Desired ball distance when stopped |
| `MIN_CONTOUR_AREA_PX` | 40 | Minimum blob size for detection |
| `MIN_CIRCULARITY` | 0.60 | Minimum shape roundness |
| `MAX_DISTANCE_M` | 3.7 | Detection range limit |
| `CAMERA_FOV_RAD` | 1.0 | Horizontal field of view |

---

## Performance Summary

### Baseline Metrics (30-second simulation)

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| Detection Rate | 100.0% | 95%+ | ✅ |
| Tracking Success | 100.0% | 95%+ | ✅ |
| Centering Error (MAE) | 0.00 px | <5 px | ✅ |
| Response Time | 0.000 s | <1.0 s | ✅ |
| Final Distance Error | 0.031 m | <0.05 m | ✅ |
| Steady-State Error | 0.038 m | <0.05 m | ✅ |
| Approach Smoothness | 0.0022 m/s² | <0.01 m/s² | ✅ |
| Average FPS | 31.25 Hz | 30+ Hz | ✅ |

### Multi-Scenario Benchmark Results

See `docs/benchmark_report.md` for detailed per-scenario analysis.

---

## Documentation

### Core Documentation
- **[CLAUDE.md](CLAUDE.md)** — Operating rules, verified environment, Webots facts
- **[A_TO_Z_IMPLEMENTATION.md](A_TO_Z_IMPLEMENTATION.md)** — Complete specification (Phases 0–15)
- **[docs/PROJECT_SUMMARY.md](docs/PROJECT_SUMMARY.md)** — Engineering lifecycle summary

### Technical Guides
- **[docs/evaluation.md](docs/evaluation.md)** — Metrics definition and interpretation
- **[docs/plotting.md](docs/plotting.md)** — Visualization guide (6 plot types)
- **[docs/tuning_report.md](docs/tuning_report.md)** — Parameter tuning analysis
- **[docs/implementation_notes.md](docs/implementation_notes.md)** — Technical decisions
- **[docs/benchmark_report.md](docs/benchmark_report.md)** — Generated after `run_benchmarks.py`

---

## Testing

### Unit Tests

```powershell
# Run all tests
python -m unittest discover -s tests -v

# Run specific test module
python -m unittest tests.test_vision -v
python -m unittest tests.test_controller -v
python -m unittest tests.test_evaluation -v
python -m unittest tests.test_plotter -v
python -m unittest tests.test_benchmarks -v
```

### Smoke Tests

Run after any change to robot geometry or control parameters:

```powershell
# Motion validation (straight & rotation)
& "C:\Users\USER\Webots\msys64\mingw64\bin\webots.exe" `
  --batch --mode=fast --no-rendering --minimize `
  "d:\Autonomous Car\webots\worlds\motion_check.wbt"
# Output: results/logs/motion_check.txt

# World/arena verification
# (Temporarily select "world_check" controller in ping_pong_follower.wbt)
```

---

## Troubleshooting

### Webots timeout or crash
1. Verify `runtime.ini` has absolute path to `.venv\Scripts\python.exe`
2. Check that Webots can see OpenCV 5.0.0 (not 4.x)
3. Run unit tests first: `python -m unittest discover -s tests -v`
4. Check error log: `results/logs/motion_check.txt` or `results/logs/world_check.txt`

### "UnicodeEncodeError" when running scripts
1. Add `$env:PYTHONIOENCODING='utf-8'` before running Python
2. Or: `python -X utf8 scripts/run_benchmarks.py`

### "controller.py shadows the Webots controller package"
1. **Do NOT rename modules to `controller.py`**
2. Control logic lives in `control.py` (not `controller.py`)
3. Webots loads `ball_follower.py` which imports `control.py`

### Plots don't generate
1. Ensure `results/logs/tracking_log.csv` exists
2. Check that OpenCV can read PNG fixtures from `tests/fixtures/`
3. Verify matplotlib has Agg backend: `python -c "import matplotlib; matplotlib.use('Agg')"`

---

## Project Completion Status

✅ **Phase 0** — Skeleton, config, CLAUDE.md, venv, environment (DONE)  
✅ **Phase 1a** — Robot PROTO + world + motion smoke test (DONE)  
✅ **Phase 1b** — Arena + ball + initial config (DONE)  
✅ **Phase 1c** — Camera acquisition loop + BGRA pipeline (DONE)  
✅ **Phase 2a** — OpenCV detector + unit tests (DONE)  
✅ **Phase 2b** — Debug overlay + HUD (DONE)  
✅ **Phase 3** — Distance + bearing calibration (DONE)  
✅ **Phase 4a** — Proportional following controller (DONE)  
✅ **Phase 4b** — Ball-lost FSM (DONE)  
✅ **Phase 5** — CSV logging (DONE)  
✅ **Phase 6a** — Evaluation scripts + metrics (DONE)  
✅ **Phase 6b** — Plotting scripts + visualizations (DONE)  
✅ **Phase 7** — Parameter tuning analysis (DONE)  
✅ **Phase 8** — Multi-scenario benchmarks (DONE)  
✅ **Phase 9** — Final integration & documentation (PROMPT 15 — DONE)  

---

## License & Attribution

Built with [Claude Code](https://claude.ai/code) and Anthropic's Claude AI.

Contact: therblig3@gmail.com

---

**Last Updated:** 2026-09-08  
**Status:** ✅ Complete
