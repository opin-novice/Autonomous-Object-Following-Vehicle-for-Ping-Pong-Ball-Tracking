#!/usr/bin/env python3
"""Create an animated video from tracking log data.

Generates an MP4 video showing the ball position, robot distance, and FSM state
over the course of a simulation run.

Usage:
    python scripts/create_video_from_log.py --input results/logs/tracking_log.csv --output results/videos/ball_follower_60s_demo.mp4
"""

import argparse
import os
import sys

import matplotlib.pyplot as plt
import matplotlib.animation as animation
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'webots', 'controllers', 'ball_follower'))

try:
    import scripts.run_evaluation as run_evaluation
except ImportError:
    sys.path.insert(0, os.path.dirname(__file__))
    import run_evaluation


def load_log(csv_path):
    """Load tracking log from CSV."""
    import numpy as np
    
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Log file not found: {csv_path}")
    
    data = np.genfromtxt(
        csv_path, delimiter=',', dtype=str, skip_header=1,
        names=('timestamp', 'ball_detected', 'ball_x', 'ball_y', 'ball_radius',
               'estimated_distance', 'image_error', 'linear_velocity', 'angular_velocity',
               'left_motor_velocity', 'right_motor_velocity', 'state')
    )
    
    # Convert to appropriate types, handling empty strings
    result = {}
    for name in data.dtype.names:
        col = data[name]
        
        # Try to convert to float, handle empty strings
        converted = np.empty(len(col), dtype=float)
        for i, val in enumerate(col):
            if val == '':
                converted[i] = np.nan
            else:
                try:
                    converted[i] = float(val)
                except ValueError:
                    converted[i] = np.nan
        
        result[name] = converted
    
    # Handle state separately (keep as strings)
    result['state'] = data['state']
    
    return result


def create_animated_video(log_path, output_path, fps=30, duration_s=60):
    """Create animated video from tracking log."""
    print(f"Loading log from {log_path}...")
    log = load_log(log_path)
    
    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Calculate number of frames
    n_frames = min(len(log['timestamp']), int(duration_s * fps))
    print(f"Creating {n_frames} frames at {fps} FPS ({duration_s}s)")
    
    # Create figure with 2 subplots
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    fig.suptitle('Ball Follower Robot - Real-Time Tracking', fontsize=16, fontweight='bold')
    
    # Plot 1: Ball position in image
    ax1.set_xlim(0, 640)
    ax1.set_ylim(480, 0)  # Inverted Y axis for image coordinates
    ax1.set_xlabel('X Position (px)')
    ax1.set_ylabel('Y Position (px)')
    ax1.set_title('Ball Position in Image')
    ax1.grid(True, alpha=0.3)
    
    # Draw center crosshair
    ax1.axhline(y=240, color='red', linestyle='--', alpha=0.3, linewidth=1)
    ax1.axvline(x=319.5, color='red', linestyle='--', alpha=0.3, linewidth=1)
    
    ball_scatter = ax1.scatter([], [], s=100, c='orange', edgecolors='black', linewidth=2, label='Ball')
    ax1.legend(loc='upper right')
    
    # Plot 2: Distance and FSM state
    ax2.set_xlim(0, duration_s)
    ax2.set_ylim(0, 3.0)
    ax2.set_xlabel('Time (s)')
    ax2.set_ylabel('Distance (m)')
    ax2.set_title('Distance to Ball & FSM State')
    ax2.grid(True, alpha=0.3)
    ax2.axhline(y=0.40, color='green', linestyle='-', alpha=0.5, linewidth=2, label='Target (0.40m)')
    ax2.axhline(y=0.43, color='blue', linestyle='--', alpha=0.3, linewidth=1, label='Threshold')
    
    distance_line, = ax2.plot([], [], 'b-', linewidth=2, label='Distance')
    ax2.legend(loc='upper right')
    
    # Text annotations
    time_text = ax1.text(0.02, 0.98, '', transform=ax1.transAxes, verticalalignment='top',
                        bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    state_text = ax2.text(0.02, 0.98, '', transform=ax2.transAxes, verticalalignment='top',
                         bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.5))
    
    print(f"Rendering {n_frames} frames...")
    
    def init():
        ball_scatter.set_offsets(np.empty((0, 2)))
        distance_line.set_data([], [])
        time_text.set_text('')
        state_text.set_text('')
        return ball_scatter, distance_line, time_text, state_text
    
    def animate(frame):
        if frame >= len(log['timestamp']):
            return ball_scatter, distance_line, time_text, state_text
        
        t = log['timestamp'][frame]
        detected = log['ball_detected'][frame]
        ball_x = log['ball_x'][frame]
        ball_y = log['ball_y'][frame]
        distance = log['estimated_distance'][frame]
        state = log['state'][frame] if frame < len(log['state']) else 'UNKNOWN'
        
        # Update ball position
        if detected > 0 and not np.isnan(ball_x) and not np.isnan(ball_y):
            ball_scatter.set_offsets([[ball_x, ball_y]])
        else:
            ball_scatter.set_offsets(np.empty((0, 2)))
        
        # Update distance line
        time_data = log['timestamp'][:frame+1]
        dist_data = log['estimated_distance'][:frame+1]
        
        # Filter out NaN values
        valid_idx = ~np.isnan(dist_data)
        if np.any(valid_idx):
            distance_line.set_data(time_data[valid_idx], dist_data[valid_idx])
        
        # Update text
        time_text.set_text(f'Time: {t:.2f}s\nDetected: {"Yes" if detected > 0 else "No"}')
        if not np.isnan(distance):
            state_text.set_text(f'State: {state}\nDistance: {distance:.3f}m')
        else:
            state_text.set_text(f'State: {state}\nDistance: N/A')
        
        return ball_scatter, distance_line, time_text, state_text
    
    # Create animation
    anim = animation.FuncAnimation(
        fig, animate, init_func=init,
        frames=n_frames, interval=1000//fps, blit=True,
        repeat=False
    )
    
    print(f"Saving video to {output_path}...")
    try:
        # Try to save as MP4 using ffmpeg
        Writer = animation.writers['ffmpeg']
        writer = Writer(fps=fps, bitrate=2000)
        anim.save(output_path, writer=writer, dpi=100)
    except Exception as e:
        print(f"ffmpeg not available, trying Pillow...")
        try:
            # Fallback to Pillow (saves as GIF)
            anim.save(output_path.replace('.mp4', '.gif'), writer='pillow', fps=fps)
            output_path = output_path.replace('.mp4', '.gif')
        except Exception as e2:
            print(f"Error saving video: {e2}")
            return False
    
    plt.close(fig)
    print(f"Video saved to {output_path}")
    return True


def main():
    parser = argparse.ArgumentParser(description='Create animated video from tracking log.')
    parser.add_argument('--input', default='results/logs/tracking_log.csv',
                        help='Input CSV log file')
    parser.add_argument('--output', default='results/videos/ball_follower_60s_demo.mp4',
                        help='Output video file')
    parser.add_argument('--fps', type=int, default=30,
                        help='Frames per second')
    parser.add_argument('--duration', type=float, default=60,
                        help='Video duration in seconds')
    
    args = parser.parse_args()
    
    success = create_animated_video(args.input, args.output, fps=args.fps, duration_s=args.duration)
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
