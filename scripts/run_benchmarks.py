"""Automated multi-scenario benchmark runner for the ball follower robot.

Executes 5 standard evaluation scenarios, collects metrics, and generates
a unified comparison report.

Scenarios:
  1. static_ball      - Ball stationary at 1.2 m (baseline)
  2. lateral_movement - Ball oscillating side-to-side
  3. approaching_ball - Ball moving toward robot
  4. ball_lost        - Ball disappears and reappears (FSM test)
  5. dynamic_curved   - Ball following circular path

Usage:
    python scripts/run_benchmarks.py [--output-dir DIR]

Generates:
    - results/logs/<scenario>_log.csv for each scenario
    - results/reports/<scenario>_metrics.json for each scenario
    - results/plots/<scenario>/ with individual plots
    - docs/benchmark_report.md with unified comparison
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
import run_evaluation
import plot_results


BENCHMARK_SCENARIOS = [
    {
        'name': 'static_ball',
        'description': 'Ball stationary at 1.2 m (baseline accuracy)',
        'duration_s': 30,
        'environment': {'BALL_MOTION_TYPE': 'static'},
    },
    {
        'name': 'lateral_movement',
        'description': 'Ball oscillating side-to-side (y-axis sine motion, 0.5 Hz)',
        'duration_s': 30,
        'environment': {'BALL_MOTION_TYPE': 'lateral_sine'},
    },
    {
        'name': 'approaching_ball',
        'description': 'Ball moving toward robot (2.0m to 0.4m over 20s)',
        'duration_s': 25,
        'environment': {'BALL_MOTION_TYPE': 'approaching'},
    },
    {
        'name': 'ball_lost',
        'description': 'Ball disappears after 5s, reappears after 5s (FSM recovery test)',
        'duration_s': 30,
        'environment': {'BALL_MOTION_TYPE': 'disappear_reappear'},
    },
    {
        'name': 'dynamic_curved',
        'description': 'Ball following circular path around robot',
        'duration_s': 30,
        'environment': {'BALL_MOTION_TYPE': 'circular'},
    },
]


def run_scenario_simulation(scenario, output_log_path, duration_s=30):
    """Run Webots simulation for a scenario.

    Returns True if successful, False otherwise.
    """
    env = os.environ.copy()
    env['BALL_FOLLOWER_HEADLESS'] = '1'
    env['BALL_FOLLOWER_RUN_SECONDS'] = str(duration_s)
    env.update(scenario.get('environment', {}))

    webots_exe = "C:\\Users\\USER\\Webots\\msys64\\mingw64\\bin\\webots.exe"
    world_path = "d:\\Autonomous Car\\webots\\worlds\\ping_pong_follower.wbt"

    try:
        result = subprocess.run(
            [webots_exe, '--batch', '--mode=fast', '--no-rendering', '--minimize', world_path],
            env=env,
            timeout=120,
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            print(f"Warning: Webots exited with code {result.returncode}")
    except subprocess.TimeoutExpired:
        print(f"Warning: Simulation timeout for {scenario['name']}")
        return False
    except Exception as e:
        print(f"Error running simulation: {e}")
        return False

    # Copy log to scenario-specific path if it exists
    default_log = 'results/logs/tracking_log.csv'
    if os.path.exists(default_log) and output_log_path != default_log:
        os.makedirs(os.path.dirname(output_log_path), exist_ok=True)
        shutil.copy(default_log, output_log_path)
        print(f"Saved {scenario['name']} log to {output_log_path}")
        return True
    return False


def evaluate_scenario(scenario_name, log_path):
    """Evaluate a scenario and return metrics."""
    try:
        if not os.path.exists(log_path):
            print(f"Log file not found: {log_path}")
            return None

        log = run_evaluation.load_log(log_path)
        metrics = run_evaluation.compute_metrics(log)
        return metrics
    except Exception as e:
        print(f"Error evaluating {scenario_name}: {e}")
        return None


def generate_plots_for_scenario(scenario_name, log_path, plots_dir, dpi=150):
    """Generate plots for a scenario."""
    try:
        if not os.path.exists(log_path):
            return False

        os.makedirs(plots_dir, exist_ok=True)
        log_data = plot_results.load_log(log_path)
        plot_results.create_individual_plots(log_data, plots_dir, dpi=dpi)
        plot_results.create_summary_dashboard(
            log_data, os.path.join(plots_dir, 'summary_dashboard.png'), dpi=dpi
        )
        print(f"Generated plots for {scenario_name} in {plots_dir}")
        return True
    except Exception as e:
        print(f"Warning: Could not generate plots for {scenario_name}: {e}")
        return False


def save_metrics_json(scenario_name, metrics, output_path):
    """Save metrics to JSON file."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump({
            'scenario': scenario_name,
            'timestamp': datetime.now().isoformat(),
            'metrics': {
                k: v for k, v in metrics.items()
                if v is not None and not isinstance(v, (list, dict))
            }
        }, f, indent=2)


def generate_benchmark_report(benchmark_results, output_path):
    """Generate unified benchmark report."""
    report = []
    report.append("# Multi-Scenario Benchmark Report")
    report.append("")
    report.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("")
    report.append("## Overview")
    report.append("")
    report.append("This report compares the ball follower robot performance across 5 standard evaluation scenarios.")
    report.append("Each scenario tests different aspects of the controller:")
    report.append("")
    report.append("- **static_ball:** Baseline accuracy and steady-state precision")
    report.append("- **lateral_movement:** Steering response and heading tracking")
    report.append("- **approaching_ball:** Approach trajectory and distance tracking")
    report.append("- **ball_lost:** FSM search mode and recovery time")
    report.append("- **dynamic_curved:** Tracking agility and dynamic response")
    report.append("")

    # Summary table
    report.append("## Performance Summary Table")
    report.append("")
    report.append("| Scenario | Detection Rate | MAE (px) | Response Time (s) | Final Distance Error (m) | Recovery Time (s) |")
    report.append("|----------|----------------|----------|-------------------|--------------------------|-------------------| ")

    for name, metrics in benchmark_results.items():
        if metrics:
            det_rate = f"{metrics.get('detection_rate_pct', 0):.1f}%"
            mae = f"{metrics.get('mae_px', 0):.2f}"
            resp_time = f"{metrics.get('response_time_s', 0):.3f}" if metrics.get('response_time_s') else "N/A"
            final_err = f"{metrics.get('final_distance_error_m', 0):.4f}" if metrics.get('final_distance_error_m') else "N/A"
            recovery = f"{metrics.get('recovery_time_s', 0):.3f}" if metrics.get('recovery_time_s') else "N/A"
            report.append(f"| {name} | {det_rate} | {mae} | {resp_time} | {final_err} | {recovery} |")
        else:
            report.append(f"| {name} | Error | — | — | — | — |")

    report.append("")
    report.append("## Detailed Scenario Results")
    report.append("")

    for name, metrics in benchmark_results.items():
        report.append(f"### {name.replace('_', ' ').title()}")
        report.append("")

        if metrics:
            report.append(f"**Detection Rate:** {metrics.get('detection_rate_pct', 0):.1f}%")
            report.append("")
            report.append(f"**Tracking Success Rate:** {metrics.get('tracking_success_rate_pct', 0):.1f}%")
            report.append("")
            report.append(f"**Image Error:**")
            report.append(f"  - MAE: {metrics.get('mae_px', 0):.2f} px")
            report.append(f"  - Max Error: {metrics.get('max_error_px', 0):.2f} px")
            report.append("")
            report.append(f"**Timing:**")
            report.append(f"  - Response Time: {metrics.get('response_time_s', 'N/A')} s")
            report.append(f"  - Average FPS: {metrics.get('fps', 0):.1f} Hz")
            report.append("")
            report.append(f"**Distance Control:**")
            report.append(f"  - Final Distance Error: {metrics.get('final_distance_error_m', 'N/A')} m")
            report.append(f"  - Recovery Time: {metrics.get('recovery_time_s', 'N/A')} s")
            report.append(f"  - Num Recoveries: {metrics.get('num_recoveries', 0)}")
        else:
            report.append("*No data available*")

        report.append("")

    report.append("## Analysis")
    report.append("")
    report.append("### Best Performers")
    report.append("")

    # Find best detection rate
    best_detection = max(benchmark_results.items(), key=lambda x: x[1].get('detection_rate_pct', 0) if x[1] else 0)
    if best_detection[1]:
        report.append(f"**Highest Detection Rate:** {best_detection[0]} ({best_detection[1].get('detection_rate_pct', 0):.1f}%)")

    report.append("")

    # Find lowest MAE
    best_mae = min(
        [(k, v) for k, v in benchmark_results.items() if v],
        key=lambda x: x[1].get('mae_px', float('inf')),
        default=(None, None)
    )
    if best_mae[1]:
        report.append(f"**Lowest Image Error (MAE):** {best_mae[0]} ({best_mae[1].get('mae_px', 0):.2f} px)")

    report.append("")
    report.append("### Observations")
    report.append("")
    report.append("- Baseline static ball test provides reference performance metrics")
    report.append("- Dynamic scenarios test controller responsiveness and stability")
    report.append("- Ball-lost scenario validates FSM search and recovery behavior")
    report.append("")
    report.append("## Recommendations")
    report.append("")
    report.append("- Review scenarios with detection rate < 95% for robustness improvements")
    report.append("- Compare MAE across scenarios to identify handling weaknesses")
    report.append("- Use recovery time as metric for FSM performance optimization")
    report.append("")

    # Write report
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w') as f:
        f.write("\n".join(report))

    return "\n".join(report)


def run_benchmarks(output_dir='results'):
    """Run all benchmark scenarios."""
    logs_dir = os.path.join(output_dir, 'logs')
    reports_dir = os.path.join(output_dir, 'reports')
    plots_base_dir = os.path.join(output_dir, 'plots')
    docs_dir = 'docs'

    benchmark_results = {}

    print("\n" + "=" * 70)
    print("BALL FOLLOWER BENCHMARK SUITE")
    print("=" * 70)

    for scenario in BENCHMARK_SCENARIOS:
        name = scenario['name']
        print(f"\n[{len(benchmark_results) + 1}/5] Running {name}...")
        print(f"  Description: {scenario['description']}")

        # Run simulation
        scenario_log = os.path.join(logs_dir, f"{name}_log.csv")
        if run_scenario_simulation(scenario, scenario_log, scenario['duration_s']):
            # Evaluate
            metrics = evaluate_scenario(name, scenario_log)
            if metrics:
                benchmark_results[name] = metrics

                # Save metrics JSON
                metrics_json = os.path.join(reports_dir, f"{name}_metrics.json")
                save_metrics_json(name, metrics, metrics_json)

                # Generate plots
                scenario_plots_dir = os.path.join(plots_base_dir, name)
                generate_plots_for_scenario(name, scenario_log, scenario_plots_dir)

                print(f"  [OK] Completed: MAE={metrics.get('mae_px', 0):.2f}px, ")
                print(f"      Detection={metrics.get('detection_rate_pct', 0):.1f}%")
        else:
            print(f"  [FAIL] Simulation failed")
            benchmark_results[name] = None

    # Generate unified report
    print("\n" + "=" * 70)
    print("GENERATING BENCHMARK REPORT")
    print("=" * 70)

    report_path = os.path.join(docs_dir, 'benchmark_report.md')
    report_text = generate_benchmark_report(benchmark_results, report_path)
    print(f"\nSaved report to {report_path}")
    print("\n" + report_text[:500] + "...")

    print("\n" + "=" * 70)
    print("BENCHMARK SUITE COMPLETE")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description='Run ball follower benchmark suite.')
    parser.add_argument('--output-dir', default='results',
                        help='Output directory for results (default: results)')
    args = parser.parse_args()

    run_benchmarks(output_dir=args.output_dir)


if __name__ == "__main__":
    main()
