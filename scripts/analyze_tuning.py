"""Analyze current tracking performance and recommend parameter tuning.

Reads the existing tracking_log.csv and provides detailed analysis of:
- Settling behavior and steady-state error
- Heading oscillation and steering responsiveness
- Approach trajectory smoothness
- Search/recovery performance

Generates tuning recommendations based on measured performance.

Usage:
    python scripts/analyze_tuning.py [--log LOG_PATH]
"""

import argparse
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
import run_evaluation


def analyze_settling_behavior(log):
    """Analyze how smoothly the robot settles at the target distance."""
    distances = log['estimated_distance'][~np.isnan(log['estimated_distance'])]
    if len(distances) < 10:
        return None

    target = 0.40
    final_100 = distances[-100:] if len(distances) > 100 else distances
    steady_state = np.mean(final_100)
    steady_error = abs(steady_state - target)
    steady_std = np.std(final_100)

    return {
        'steady_state_distance': steady_state,
        'steady_error': steady_error,
        'steady_std': steady_std,
        'overshoot': max(0, np.min(distances) - 0.35) if len(distances) > 0 else 0,
    }


def analyze_heading_oscillation(log):
    """Measure heading stability (image error smoothness)."""
    errors = log['image_error'][log['ball_detected'] == 1]
    errors = errors[~np.isnan(errors)]
    if len(errors) < 20:
        return None

    final_100 = errors[-100:] if len(errors) > 100 else errors
    oscillation_freq = 0
    oscillation_amplitude = np.std(final_100)

    zero_crossings = np.sum(np.diff(np.sign(final_100)) != 0)
    if len(final_100) > 1:
        oscillation_freq = zero_crossings / (len(final_100) * 0.032)  # Approximate frequency

    return {
        'heading_mae': np.mean(np.abs(final_100)),
        'heading_std': oscillation_amplitude,
        'zero_crossings': zero_crossings,
        'estimated_frequency': oscillation_freq,
    }


def analyze_approach_trajectory(log):
    """Analyze the smoothness of the approach trajectory."""
    distances = log['estimated_distance'][~np.isnan(log['estimated_distance'])]
    if len(distances) < 10:
        return None

    velocities = np.diff(distances)  # Approximate velocity
    accelerations = np.diff(velocities)  # Approximate acceleration

    return {
        'approach_smoothness': np.std(velocities),
        'approach_jerk': np.std(accelerations),
        'max_deceleration': np.min(accelerations),
        'approach_time': len(distances) * 0.032,
    }


def analyze_search_recovery(log):
    """Analyze search mode and recovery performance."""
    detection = log['ball_detected']
    if not np.any(detection == 0):
        return None  # No loss events

    loss_indices = []
    recovery_times = []
    loss_idx = None
    for i in range(1, len(detection)):
        if detection[i-1] == 1 and detection[i] == 0:
            loss_idx = i
            loss_indices.append(i)
        elif loss_idx is not None and detection[i] == 1:
            recovery_time = (i - loss_idx) * 0.032
            recovery_times.append(recovery_time)
            loss_idx = None

    if not recovery_times:
        return None

    return {
        'num_losses': len(loss_indices),
        'avg_recovery_time': np.mean(recovery_times),
        'max_recovery_time': np.max(recovery_times),
        'min_recovery_time': np.min(recovery_times),
    }


def generate_recommendations(metrics, settling, heading, approach, search):
    """Generate tuning recommendations based on analysis."""
    recommendations = []
    explanations = []

    mae = metrics.get('mae_px', 0)
    if mae > 5.0:
        recommendations.append('Reduce KP_STEER from 2.0 to 1.5 (overly aggressive steering)')
        explanations.append(f'  High MAE of {mae:.1f} px indicates oscillatory steering response')
    elif mae < 1.0 and settling and settling['steady_std'] < 0.5:
        recommendations.append('Increase KP_STEER from 2.0 to 2.5 (conservative steering)')
        explanations.append(f'  Very smooth tracking ({mae:.1f} px) suggests room for tighter control')

    if settling:
        if settling['steady_error'] > 0.05:
            recommendations.append('Increase KP_DIST from 1.5 to 2.0 (weak distance tracking)')
            explanations.append(f'  Steady-state distance error {settling["steady_error"]:.3f} m suggests weak approach gain')

    if heading:
        if heading['zero_crossings'] > 50:
            recommendations.append('Reduce MAX_WHEEL_SPEED from 6.28 to 5.5 rad/s (oscillation damping)')
            explanations.append(f'  {heading["zero_crossings"]} heading reversals suggest too-aggressive speed')

    if approach:
        if approach['approach_smoothness'] > 0.05:
            recommendations.append('Tighten DISTANCE_TOLERANCE_M from 0.03 to 0.02 m (earlier braking)')
            explanations.append(f'  Approach jerk of {approach["approach_jerk"]:.4f} suggests abrupt deceleration')

    if not recommendations:
        recommendations.append('Current configuration is well-balanced; no major changes recommended')
        explanations.append('  Steady-state performance is smooth and accurate')

    return recommendations, explanations


def print_analysis_report(log, metrics, settling, heading, approach, search):
    """Print detailed analysis report."""
    print("\n" + "=" * 70)
    print("CONTROLLER PERFORMANCE ANALYSIS")
    print("=" * 70)

    print("\n[EVALUATION METRICS]")
    print(f"  Detection Rate:             {metrics.get('detection_rate_pct', 0):.1f}%")
    print(f"  Tracking Success Rate:      {metrics.get('tracking_success_rate_pct', 0):.1f}%")
    print(f"  Image Error MAE:            {metrics.get('mae_px', 0):.2f} px")
    print(f"  Max Image Error:            {metrics.get('max_error_px', 0):.2f} px")
    print(f"  Response Time:              {metrics.get('response_time_s', 0):.3f} s")
    print(f"  Final Distance Error:       {metrics.get('final_distance_error_m', 0):.4f} m")

    if settling:
        print("\n[SETTLING BEHAVIOR]")
        print(f"  Steady-State Distance:      {settling['steady_state_distance']:.4f} m")
        print(f"  Steady-State Error:         {settling['steady_error']:.4f} m")
        print(f"  Steady-State Std Dev:       {settling['steady_std']:.4f} m")
        print(f"  Overshoot:                  {settling['overshoot']:.4f} m")

    if heading:
        print("\n[HEADING STABILITY]")
        print(f"  Final Heading MAE:          {heading['heading_mae']:.2f} px")
        print(f"  Heading Oscillation Amp:    {heading['heading_std']:.2f} px")
        print(f"  Estimated Oscillation Freq: {heading['estimated_frequency']:.2f} Hz")
        print(f"  Zero Crossings:             {heading['zero_crossings']}")

    if approach:
        print("\n[APPROACH TRAJECTORY]")
        print(f"  Approach Smoothness Std:    {approach['approach_smoothness']:.4f} m/s")
        print(f"  Approach Jerk Std:          {approach['approach_jerk']:.4f} m/s²")
        print(f"  Max Deceleration:           {approach['max_deceleration']:.4f} m/s²")
        print(f"  Total Approach Time:        {approach['approach_time']:.1f} s")

    if search:
        print("\n[SEARCH & RECOVERY]")
        print(f"  Number of Loss Events:      {search['num_losses']}")
        print(f"  Average Recovery Time:      {search['avg_recovery_time']:.3f} s")
        print(f"  Max Recovery Time:          {search['max_recovery_time']:.3f} s")
        print(f"  Min Recovery Time:          {search['min_recovery_time']:.3f} s")

    print("\n" + "=" * 70)
    print("TUNING RECOMMENDATIONS")
    print("=" * 70)

    recommendations, explanations = generate_recommendations(metrics, settling, heading, approach, search)
    for i, (rec, exp) in enumerate(zip(recommendations, explanations), 1):
        print(f"\n{i}. {rec}")
        print(exp)


def main():
    parser = argparse.ArgumentParser(description='Analyze tracking performance and recommend tuning.')
    parser.add_argument('--log', default='results/logs/tracking_log.csv',
                        help='Path to tracking log (default: results/logs/tracking_log.csv)')
    args = parser.parse_args()

    if not os.path.exists(args.log):
        print(f"Error: Log file not found: {args.log}", file=sys.stderr)
        sys.exit(1)

    try:
        log = run_evaluation.load_log(args.log)
        metrics = run_evaluation.compute_metrics(log)

        settling = analyze_settling_behavior(log)
        heading = analyze_heading_oscillation(log)
        approach = analyze_approach_trajectory(log)
        search = analyze_search_recovery(log)

        print_analysis_report(log, metrics, settling, heading, approach, search)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
