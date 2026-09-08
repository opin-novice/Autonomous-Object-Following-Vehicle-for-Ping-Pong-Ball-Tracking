"""Compute evaluation metrics from a tracking log.

Reads results/logs/tracking_log.csv and reports detection rate, tracking success rate,
MAE, maximum error, response time, final distance error and ball-lost recovery time.

Metrics are computed from recorded simulation data only. Never write a number here that
did not come out of a log file.

Usage:
    python scripts/run_evaluation.py [csv_path] [output_path]

Defaults to results/logs/tracking_log.csv and results/logs/evaluation_report.txt
"""

import csv
import os
import sys
from pathlib import Path

import numpy as np


def load_log(csv_path):
    """Read a tracking CSV into column arrays.

    Args:
        csv_path: Path to the CSV file.

    Returns:
        A dict mapping column names to numpy arrays. Missing values (empty strings)
        are represented as NaN for numeric columns, and empty strings for string columns.
    """
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Log file not found: {csv_path}")

    data = {
        'timestamp': [],
        'ball_detected': [],
        'ball_x': [],
        'ball_y': [],
        'ball_radius': [],
        'estimated_distance': [],
        'image_error': [],
        'linear_velocity': [],
        'angular_velocity': [],
        'left_motor_velocity': [],
        'right_motor_velocity': [],
        'state': [],
    }

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            data['timestamp'].append(float(row['timestamp']) if row['timestamp'] else np.nan)
            data['ball_detected'].append(int(row['ball_detected']) if row['ball_detected'] else 0)
            data['ball_x'].append(float(row['ball_x']) if row['ball_x'] else np.nan)
            data['ball_y'].append(float(row['ball_y']) if row['ball_y'] else np.nan)
            data['ball_radius'].append(float(row['ball_radius']) if row['ball_radius'] else np.nan)
            data['estimated_distance'].append(float(row['estimated_distance']) if row['estimated_distance'] else np.nan)
            data['image_error'].append(float(row['image_error']) if row['image_error'] else np.nan)
            data['linear_velocity'].append(float(row['linear_velocity']) if row['linear_velocity'] else np.nan)
            data['angular_velocity'].append(float(row['angular_velocity']) if row['angular_velocity'] else np.nan)
            data['left_motor_velocity'].append(float(row['left_motor_velocity']) if row['left_motor_velocity'] else np.nan)
            data['right_motor_velocity'].append(float(row['right_motor_velocity']) if row['right_motor_velocity'] else np.nan)
            data['state'].append(row['state'] if row['state'] else "")

    for key in data:
        if key != 'state':
            data[key] = np.array(data[key])
        else:
            data[key] = np.array(data[key], dtype=object)

    return data


def compute_metrics(log):
    """Return the metric dictionary from the log data.

    Args:
        log: Dict of column arrays returned by load_log().

    Returns:
        A dict with metric names and values.
    """
    metrics = {}

    n_frames = len(log['timestamp'])
    if n_frames == 0:
        return metrics

    # Detection rate: % of frames where ball_detected == 1
    detected_frames = np.sum(log['ball_detected'] == 1)
    metrics['detection_rate_pct'] = 100.0 * detected_frames / n_frames if n_frames > 0 else 0.0

    # Tracking success rate: % of frames in TRACKING or APPROACHING state
    tracking_frames = 0
    for state in log['state']:
        if state in ('TRACKING', 'APPROACHING'):
            tracking_frames += 1
    metrics['tracking_success_rate_pct'] = 100.0 * tracking_frames / n_frames if n_frames > 0 else 0.0

    # Image error metrics (across detected frames only)
    valid_errors = log['image_error'][log['ball_detected'] == 1]
    valid_errors = valid_errors[~np.isnan(valid_errors)]
    if len(valid_errors) > 0:
        metrics['mae_px'] = float(np.mean(np.abs(valid_errors)))
        metrics['max_error_px'] = float(np.max(np.abs(valid_errors)))
    else:
        metrics['mae_px'] = 0.0
        metrics['max_error_px'] = 0.0

    # Response time: time from first frame to first frame where |image_error| < 5 px
    response_time_s = None
    first_timestamp = log['timestamp'][0] if len(log['timestamp']) > 0 else None
    for i, (detected, error, timestamp) in enumerate(
            zip(log['ball_detected'], log['image_error'], log['timestamp'])):
        if detected == 1 and not np.isnan(error) and abs(error) < 5.0:
            response_time_s = timestamp - first_timestamp
            break
    metrics['response_time_s'] = response_time_s if response_time_s is not None else None

    # Final distance error: mean of |estimated_distance - 0.40| over the last 50 frames
    # where estimated_distance is valid
    target_distance = 0.40
    last_n = 50
    final_distances = log['estimated_distance'][-last_n:]
    valid_final = final_distances[~np.isnan(final_distances)]
    if len(valid_final) > 0:
        metrics['final_distance_error_m'] = float(np.mean(np.abs(valid_final - target_distance)))
    else:
        metrics['final_distance_error_m'] = None

    # Recovery time: time from ball loss (1->0) to re-acquisition (0->1)
    # If no recovery occurs, leave as None
    recovery_times = []
    loss_idx = None
    for i in range(1, len(log['ball_detected'])):
        prev_detected = log['ball_detected'][i - 1]
        curr_detected = log['ball_detected'][i]
        if prev_detected == 1 and curr_detected == 0:
            loss_idx = i
        elif loss_idx is not None and curr_detected == 1:
            recovery_time_s = log['timestamp'][i] - log['timestamp'][loss_idx]
            recovery_times.append(recovery_time_s)
            loss_idx = None

    if recovery_times:
        metrics['recovery_time_s'] = float(np.mean(recovery_times))
        metrics['num_recoveries'] = len(recovery_times)
    else:
        metrics['recovery_time_s'] = None
        metrics['num_recoveries'] = 0

    # Average FPS: based on timestep
    if len(log['timestamp']) > 1:
        time_span = log['timestamp'][-1] - log['timestamp'][0]
        if time_span > 0:
            metrics['fps'] = (n_frames - 1) / time_span
        else:
            metrics['fps'] = 0.0
    else:
        metrics['fps'] = 0.0

    return metrics


def format_report(metrics):
    """Format metrics as a readable report string."""
    lines = []
    lines.append("=" * 60)
    lines.append("EVALUATION REPORT")
    lines.append("=" * 60)
    lines.append("")

    if 'detection_rate_pct' in metrics:
        lines.append(f"Detection Rate:            {metrics['detection_rate_pct']:7.2f} %")
    if 'tracking_success_rate_pct' in metrics:
        lines.append(f"Tracking Success Rate:     {metrics['tracking_success_rate_pct']:7.2f} %")
    lines.append("")

    if 'mae_px' in metrics:
        lines.append(f"Mean Absolute Error (MAE): {metrics['mae_px']:7.2f} px")
    if 'max_error_px' in metrics:
        lines.append(f"Maximum Error:             {metrics['max_error_px']:7.2f} px")
    lines.append("")

    if 'response_time_s' in metrics and metrics['response_time_s'] is not None:
        lines.append(f"Response Time:             {metrics['response_time_s']:7.3f} s")
    else:
        lines.append("Response Time:             N/A (ball never centered)")

    if 'final_distance_error_m' in metrics and metrics['final_distance_error_m'] is not None:
        lines.append(f"Final Distance Error:      {metrics['final_distance_error_m']:7.4f} m")
    else:
        lines.append("Final Distance Error:      N/A (no valid distance data)")
    lines.append("")

    if 'recovery_time_s' in metrics and metrics['recovery_time_s'] is not None:
        lines.append(f"Recovery Time (avg):       {metrics['recovery_time_s']:7.3f} s")
        lines.append(f"Number of Recoveries:      {metrics['num_recoveries']:7d}")
    else:
        lines.append("Recovery Time (avg):       N/A (no ball loss/recovery)")
        lines.append(f"Number of Recoveries:      {metrics['num_recoveries']:7d}")
    lines.append("")

    if 'fps' in metrics:
        lines.append(f"Average FPS:               {metrics['fps']:7.2f} Hz")
    lines.append("")
    lines.append("=" * 60)

    return "\n".join(lines)


def main():
    csv_path = sys.argv[1] if len(sys.argv) > 1 else "results/logs/tracking_log.csv"
    report_path = sys.argv[2] if len(sys.argv) > 2 else "results/logs/evaluation_report.txt"

    if not os.path.exists(csv_path):
        print(f"Error: CSV file not found: {csv_path}", file=sys.stderr)
        sys.exit(1)

    try:
        log = load_log(csv_path)
        metrics = compute_metrics(log)
        report = format_report(metrics)

        print(report)

        os.makedirs(os.path.dirname(os.path.abspath(report_path)), exist_ok=True)
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"\nReport saved to: {report_path}")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
