"""Systematic parameter tuning for the ball follower controller.

Tests multiple parameter configurations via simulation and compares performance
using evaluation metrics (MAE, peak error, settling time, response time).

Usage:
    python scripts/tune_controller.py [--duration SECONDS]

Generates:
    - results/tuning/baseline_<timestamp>/ — Baseline trial logs and plots
    - results/tuning/trial_<N>_<timestamp>/ — Candidate trial logs and plots
    - results/tuning/comparison.csv — Summary of all trials
    - docs/tuning_report.md — Final report with recommendations
"""

import argparse
import csv
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
import run_evaluation


# Baseline configuration (current working values)
BASELINE_CONFIG = {
    'KP_STEER': 2.0,
    'KP_DIST': 1.5,
    'MAX_WHEEL_SPEED': 6.28,
    'TARGET_DISTANCE_M': 0.40,
    'DISTANCE_TOLERANCE_M': 0.03,
    'STOP_HYSTERESIS_M': 0.06,
    'SEARCH_SPIN_SPEED': 1.0,
}

# Candidate configurations for tuning
CANDIDATE_CONFIGS = [
    # Trial 1: Reduce steering gain for smoother turning
    {
        'name': 'Lower Steering Gain',
        'KP_STEER': 1.5,
        'KP_DIST': 1.5,
        'MAX_WHEEL_SPEED': 6.28,
    },
    # Trial 2: Increase distance gain for faster approach
    {
        'name': 'Higher Distance Gain',
        'KP_STEER': 2.0,
        'KP_DIST': 2.0,
        'MAX_WHEEL_SPEED': 6.28,
    },
    # Trial 3: Reduce max speed for stability
    {
        'name': 'Lower Max Speed',
        'KP_STEER': 2.0,
        'KP_DIST': 1.5,
        'MAX_WHEEL_SPEED': 5.0,
    },
    # Trial 4: Tighter deadband for precise stopping
    {
        'name': 'Tighter Deadband',
        'KP_STEER': 2.0,
        'KP_DIST': 1.5,
        'MAX_WHEEL_SPEED': 6.28,
        'DISTANCE_TOLERANCE_M': 0.02,
    },
    # Trial 5: Balanced tuning
    {
        'name': 'Balanced Tuning',
        'KP_STEER': 1.8,
        'KP_DIST': 1.7,
        'MAX_WHEEL_SPEED': 5.5,
        'DISTANCE_TOLERANCE_M': 0.025,
    },
]


def read_config_file(config_path):
    """Read current config.py values."""
    config = {}
    with open(config_path, 'r') as f:
        for line in f:
            for key in BASELINE_CONFIG.keys():
                if line.strip().startswith(key + ' ='):
                    parts = line.split('=')
                    if len(parts) == 2:
                        try:
                            value = float(parts[1].strip())
                            config[key] = value
                        except ValueError:
                            pass
    return config


def update_config_file(config_path, params):
    """Update config.py with new parameter values."""
    with open(config_path, 'r') as f:
        lines = f.readlines()

    output_lines = []
    for line in lines:
        updated = False
        for key, value in params.items():
            if line.strip().startswith(key + ' ='):
                # Replace the value
                indent = len(line) - len(line.lstrip())
                output_lines.append(' ' * indent + f'{key} = {value}\n')
                updated = True
                break
        if not updated:
            output_lines.append(line)

    with open(config_path, 'w') as f:
        f.writelines(output_lines)


def run_simulation(duration_s=30):
    """Run Webots simulation and return path to tracking log."""
    env = os.environ.copy()
    env['BALL_FOLLOWER_HEADLESS'] = '1'
    env['BALL_FOLLOWER_RUN_SECONDS'] = str(duration_s)

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
            print(f"stdout: {result.stdout[:500]}")
            print(f"stderr: {result.stderr[:500]}")
    except subprocess.TimeoutExpired:
        print("Warning: Webots simulation timed out")
    except Exception as e:
        print(f"Error running simulation: {e}")
        return None

    log_path = 'results/logs/tracking_log.csv'
    return log_path if os.path.exists(log_path) else None


def evaluate_trial(log_path, trial_name):
    """Run evaluation on a trial log and return metrics."""
    try:
        log = run_evaluation.load_log(log_path)
        metrics = run_evaluation.compute_metrics(log)
        return metrics
    except Exception as e:
        print(f"Error evaluating {trial_name}: {e}")
        return None


def save_trial_results(trial_name, trial_dir, log_path, metrics):
    """Save trial log and plots to the trial directory."""
    os.makedirs(trial_dir, exist_ok=True)

    # Copy log file
    log_filename = os.path.join(trial_dir, 'tracking_log.csv')
    shutil.copy(log_path, log_filename)

    # Generate plots
    try:
        import plot_results
        plots_dir = os.path.join(trial_dir, 'plots')
        os.makedirs(plots_dir, exist_ok=True)
        log_data = plot_results.load_log(log_filename)
        plot_results.create_individual_plots(log_data, plots_dir, dpi=150)
        plot_results.create_summary_dashboard(log_data, os.path.join(plots_dir, 'summary_dashboard.png'), dpi=150)
    except Exception as e:
        print(f"Warning: Could not generate plots for {trial_name}: {e}")

    # Save metrics to file
    metrics_path = os.path.join(trial_dir, 'metrics.txt')
    with open(metrics_path, 'w') as f:
        f.write(f"Trial: {trial_name}\n")
        f.write(f"Timestamp: {datetime.now().isoformat()}\n\n")
        for key, value in sorted(metrics.items()):
            if value is not None:
                if isinstance(value, float):
                    f.write(f"{key}: {value:.4f}\n")
                else:
                    f.write(f"{key}: {value}\n")


def run_tuning_campaign(duration_s=30):
    """Run systematic tuning campaign."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    tuning_dir = f"results/tuning/{timestamp}"
    os.makedirs(tuning_dir, exist_ok=True)

    config_path = 'webots/controllers/ball_follower/config.py'
    original_config = read_config_file(config_path)

    results = []

    # Trial 0: Baseline
    print("\n=" * 60)
    print("BASELINE TRIAL")
    print("=" * 60)
    baseline_dir = os.path.join(tuning_dir, 'baseline')
    log_path = run_simulation(duration_s)
    if log_path:
        metrics = evaluate_trial(log_path, 'Baseline')
        if metrics:
            save_trial_results('Baseline', baseline_dir, log_path, metrics)
            results.append(('Baseline', BASELINE_CONFIG.copy(), metrics))
            print(f"Baseline MAE: {metrics.get('mae_px', 'N/A'):.2f} px")
            print(f"Baseline Response Time: {metrics.get('response_time_s', 'N/A'):.3f} s")

    # Candidate trials
    for trial_num, candidate in enumerate(CANDIDATE_CONFIGS, 1):
        print(f"\n=" * 60)
        print(f"TRIAL {trial_num}: {candidate['name']}")
        print("=" * 60)

        # Merge with baseline
        trial_config = BASELINE_CONFIG.copy()
        trial_config.update(candidate)
        config_subset = {k: trial_config[k] for k in BASELINE_CONFIG.keys() if k in trial_config}

        # Update config file
        update_config_file(config_path, config_subset)
        print(f"Updated config: {config_subset}")

        # Run simulation
        log_path = run_simulation(duration_s)
        if log_path:
            metrics = evaluate_trial(log_path, candidate['name'])
            if metrics:
                trial_dir = os.path.join(tuning_dir, f'trial_{trial_num}')
                save_trial_results(candidate['name'], trial_dir, log_path, metrics)
                results.append((candidate['name'], config_subset, metrics))
                print(f"{candidate['name']} MAE: {metrics.get('mae_px', 'N/A'):.2f} px")
                print(f"{candidate['name']} Response Time: {metrics.get('response_time_s', 'N/A'):.3f} s")

        time.sleep(1)

    # Restore original config
    update_config_file(config_path, original_config)
    print("\nRestored original config.")

    # Save comparison results
    comparison_path = os.path.join(tuning_dir, 'comparison.csv')
    with open(comparison_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Trial Name', 'KP_STEER', 'KP_DIST', 'MAX_WHEEL_SPEED',
                        'MAE (px)', 'Response Time (s)', 'Final Distance Error (m)'])
        for name, config, metrics in results:
            writer.writerow([
                name,
                config.get('KP_STEER', ''),
                config.get('KP_DIST', ''),
                config.get('MAX_WHEEL_SPEED', ''),
                f"{metrics.get('mae_px', 'N/A'):.2f}",
                f"{metrics.get('response_time_s', 'N/A'):.3f}",
                f"{metrics.get('final_distance_error_m', 'N/A'):.4f}",
            ])

    print(f"\n=" * 60)
    print("Tuning campaign complete!")
    print(f"Results saved to {tuning_dir}")
    print(f"Comparison: {comparison_path}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description='Systematic controller parameter tuning.')
    parser.add_argument('--duration', type=int, default=30,
                        help='Simulation duration in seconds (default: 30)')
    args = parser.parse_args()

    run_tuning_campaign(duration_s=args.duration)


if __name__ == "__main__":
    main()
