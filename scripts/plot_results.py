"""Visualization of tracking simulation results.

Reads results/logs/tracking_log.csv and generates publication-quality plots:
- tracking_error_vs_time.png: Image centering error over time
- distance_vs_time.png: Estimated distance with target reference
- motor_speeds_vs_time.png: Left/right wheel speeds
- ball_position_vs_center.png: Ball X position with image center reference
- detection_status_vs_time.png: Detection status and FSM state timeline
- summary_dashboard.png: Combined 2x3 grid of all core plots

Usage:
    python scripts/plot_results.py [--input LOG_PATH] [--output-dir DIR] [--dpi DPI]

All plots use headless rendering (no windows) and professional styling.
"""

import argparse
import csv
import os
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

# Professional color palette
COLOR_ERROR = '#e74c3c'      # Red
COLOR_DISTANCE = '#3498db'   # Blue
COLOR_LEFT = '#2ecc71'       # Green
COLOR_RIGHT = '#f39c12'      # Orange
COLOR_DETECTION = '#9b59b6'  # Purple
COLOR_GRID = '#ecf0f1'       # Light gray


def load_log(csv_path):
    """Load tracking CSV into arrays, converting empty strings to NaN.

    Args:
        csv_path: Path to tracking_log.csv

    Returns:
        Dict with keys: timestamp, ball_detected, ball_x, ball_y, ball_radius,
        estimated_distance, image_error, linear_velocity, angular_velocity,
        left_motor_velocity, right_motor_velocity, state
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


def plot_tracking_error(ax, log):
    """Plot horizontal image centering error over time."""
    ax.plot(log['timestamp'], log['image_error'], color=COLOR_ERROR, linewidth=1.5, label='Image Error')
    ax.axhline(y=0, color='black', linestyle='-', linewidth=0.8, alpha=0.3)
    ax.fill_between(log['timestamp'], log['image_error'], 0, alpha=0.2, color=COLOR_ERROR)
    ax.set_xlabel('Time (s)', fontsize=10, fontweight='bold')
    ax.set_ylabel('Image Error (px)', fontsize=10, fontweight='bold')
    ax.set_title('Horizontal Centering Error', fontsize=11, fontweight='bold')
    ax.grid(True, color=COLOR_GRID, linestyle='-', linewidth=0.5, alpha=0.7)
    ax.legend(loc='best')


def plot_distance(ax, log):
    """Plot estimated distance with target reference."""
    ax.plot(log['timestamp'], log['estimated_distance'], color=COLOR_DISTANCE, linewidth=1.5, label='Estimated Distance')
    ax.axhline(y=0.40, color='red', linestyle='--', linewidth=1.5, label='Target Distance (0.40 m)', alpha=0.7)
    ax.set_xlabel('Time (s)', fontsize=10, fontweight='bold')
    ax.set_ylabel('Distance (m)', fontsize=10, fontweight='bold')
    ax.set_title('Approach Distance Profile', fontsize=11, fontweight='bold')
    ax.grid(True, color=COLOR_GRID, linestyle='-', linewidth=0.5, alpha=0.7)
    ax.legend(loc='best')
    ax.set_ylim(bottom=0.0)


def plot_motor_speeds(ax, log):
    """Plot left and right motor velocities."""
    ax.plot(log['timestamp'], log['left_motor_velocity'], color=COLOR_LEFT, linewidth=1.5, label='Left Motor')
    ax.plot(log['timestamp'], log['right_motor_velocity'], color=COLOR_RIGHT, linewidth=1.5, label='Right Motor')
    ax.axhline(y=0, color='black', linestyle='-', linewidth=0.8, alpha=0.3)
    ax.set_xlabel('Time (s)', fontsize=10, fontweight='bold')
    ax.set_ylabel('Motor Velocity (rad/s)', fontsize=10, fontweight='bold')
    ax.set_title('Motor Speeds', fontsize=11, fontweight='bold')
    ax.grid(True, color=COLOR_GRID, linestyle='-', linewidth=0.5, alpha=0.7)
    ax.legend(loc='best')


def plot_ball_position(ax, log):
    """Plot ball X position with image center reference."""
    ax.plot(log['timestamp'], log['ball_x'], color=COLOR_DISTANCE, linewidth=1.5, label='Ball X Position')
    ax.axhline(y=319.5, color='red', linestyle='--', linewidth=1.5, label='Image Center (319.5 px)', alpha=0.7)
    ax.set_xlabel('Time (s)', fontsize=10, fontweight='bold')
    ax.set_ylabel('Ball X Position (px)', fontsize=10, fontweight='bold')
    ax.set_title('Ball Horizontal Position', fontsize=11, fontweight='bold')
    ax.grid(True, color=COLOR_GRID, linestyle='-', linewidth=0.5, alpha=0.7)
    ax.legend(loc='best')
    ax.set_ylim(0, 640)


def plot_detection_status(ax, log):
    """Plot detection status and FSM state timeline."""
    ax.fill_between(log['timestamp'], 0, log['ball_detected'], alpha=0.3, color=COLOR_DETECTION, label='Ball Detected')
    ax.plot(log['timestamp'], log['ball_detected'], color=COLOR_DETECTION, linewidth=1.5, marker='.', markersize=2)

    unique_states = [s for s in np.unique(log['state']) if s != '']
    state_to_num = {state: i for i, state in enumerate(unique_states)}
    state_nums = np.array([state_to_num.get(s, -1) if s != '' else -1 for s in log['state']])

    for i, state in enumerate(unique_states):
        mask = state_nums == i
        ax.scatter(log['timestamp'][mask], np.ones_like(log['timestamp'][mask]) * (0.5 - i * 0.08),
                   s=20, marker='s', alpha=0.5, label=f'State: {state}')

    ax.set_xlabel('Time (s)', fontsize=10, fontweight='bold')
    ax.set_ylabel('Detection Status', fontsize=10, fontweight='bold')
    ax.set_title('Detection & FSM State', fontsize=11, fontweight='bold')
    ax.set_ylim(-0.2, 1.2)
    ax.set_yticks([0, 1])
    ax.set_yticklabels(['Not Detected', 'Detected'])
    ax.grid(True, color=COLOR_GRID, linestyle='-', linewidth=0.5, alpha=0.7, axis='x')
    ax.legend(loc='best', fontsize=8)


def create_summary_dashboard(log, output_path, dpi=300):
    """Create a 2x3 grid dashboard with all core plots."""
    fig, axes = plt.subplots(2, 3, figsize=(16, 10), dpi=dpi)
    fig.suptitle('Ball Follower Tracking Performance Dashboard', fontsize=14, fontweight='bold', y=0.995)

    plot_tracking_error(axes[0, 0], log)
    plot_distance(axes[0, 1], log)
    plot_motor_speeds(axes[0, 2], log)
    plot_ball_position(axes[1, 0], log)
    plot_detection_status(axes[1, 1], log)

    axes[1, 2].axis('off')
    axes[1, 2].text(0.5, 0.5, 'Dashboard Summary', ha='center', va='center', fontsize=12, fontweight='bold')
    axes[1, 2].text(0.5, 0.35, 'All plots display tracking performance\nover the full simulation run.',
                    ha='center', va='center', fontsize=10)

    plt.tight_layout()
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    plt.savefig(output_path, dpi=dpi, bbox_inches='tight')
    plt.close()
    print(f"Saved: {output_path}")


def create_individual_plots(log, output_dir, dpi=300):
    """Create individual high-quality plots for each metric."""
    os.makedirs(output_dir, exist_ok=True)

    fig_width, fig_height = 12, 6

    fig, ax = plt.subplots(figsize=(fig_width, fig_height), dpi=dpi)
    plot_tracking_error(ax, log)
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'tracking_error_vs_time.png'), dpi=dpi, bbox_inches='tight')
    plt.close()
    print(f"Saved: {os.path.join(output_dir, 'tracking_error_vs_time.png')}")

    fig, ax = plt.subplots(figsize=(fig_width, fig_height), dpi=dpi)
    plot_distance(ax, log)
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'distance_vs_time.png'), dpi=dpi, bbox_inches='tight')
    plt.close()
    print(f"Saved: {os.path.join(output_dir, 'distance_vs_time.png')}")

    fig, ax = plt.subplots(figsize=(fig_width, fig_height), dpi=dpi)
    plot_motor_speeds(ax, log)
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'motor_speeds_vs_time.png'), dpi=dpi, bbox_inches='tight')
    plt.close()
    print(f"Saved: {os.path.join(output_dir, 'motor_speeds_vs_time.png')}")

    fig, ax = plt.subplots(figsize=(fig_width, fig_height), dpi=dpi)
    plot_ball_position(ax, log)
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'ball_position_vs_center.png'), dpi=dpi, bbox_inches='tight')
    plt.close()
    print(f"Saved: {os.path.join(output_dir, 'ball_position_vs_center.png')}")

    fig, ax = plt.subplots(figsize=(fig_width, fig_height), dpi=dpi)
    plot_detection_status(ax, log)
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'detection_status_vs_time.png'), dpi=dpi, bbox_inches='tight')
    plt.close()
    print(f"Saved: {os.path.join(output_dir, 'detection_status_vs_time.png')}")


def main():
    parser = argparse.ArgumentParser(description='Generate tracking visualization plots.')
    parser.add_argument('--input', default='results/logs/tracking_log.csv',
                        help='Path to tracking log CSV (default: results/logs/tracking_log.csv)')
    parser.add_argument('--output-dir', default='results/plots',
                        help='Output directory for plots (default: results/plots)')
    parser.add_argument('--dpi', type=int, default=300,
                        help='Plot DPI (default: 300)')

    args = parser.parse_args()

    try:
        log = load_log(args.input)
        print(f"Loaded {len(log['timestamp'])} frames from {args.input}")

        create_individual_plots(log, args.output_dir, dpi=args.dpi)
        create_summary_dashboard(log, os.path.join(args.output_dir, 'summary_dashboard.png'), dpi=args.dpi)

        print(f"\nAll plots saved to {args.output_dir}")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
