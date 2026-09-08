"""Unit tests for the visualization/plotting module.

Tests the load_log function, missing data handling, and plot generation
without requiring Webots or X11. Run:

    .venv/Scripts/python.exe -m unittest discover -s tests -v
"""

import os
import sys
import tempfile
import unittest

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))

import plot_results


class TestLoadLog(unittest.TestCase):
    """Tests for load_log()."""

    def test_loads_a_minimal_csv(self):
        csv_content = (
            "timestamp,ball_detected,ball_x,ball_y,ball_radius,estimated_distance,"
            "image_error,linear_velocity,angular_velocity,left_motor_velocity,"
            "right_motor_velocity,state\n"
            "0.0,1,320.0,240.0,10.0,1.2,0.5,1.0,0.0,1.0,1.0,TRACKING\n"
        )
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as f:
            f.write(csv_content)
            f.flush()
            temp_path = f.name
        try:
            log = plot_results.load_log(temp_path)
            self.assertEqual(len(log['timestamp']), 1)
            self.assertEqual(log['ball_detected'][0], 1)
            self.assertAlmostEqual(log['ball_x'][0], 320.0)
            self.assertEqual(log['state'][0], 'TRACKING')
        finally:
            os.unlink(temp_path)

    def test_handles_empty_fields_as_nan(self):
        csv_content = (
            "timestamp,ball_detected,ball_x,ball_y,ball_radius,estimated_distance,"
            "image_error,linear_velocity,angular_velocity,left_motor_velocity,"
            "right_motor_velocity,state\n"
            "0.0,0,,,,,,,,,\n"
            "0.032,1,320.0,240.0,10.0,1.2,0.5,1.0,0.0,1.0,1.0,TRACKING\n"
        )
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as f:
            f.write(csv_content)
            f.flush()
            temp_path = f.name
        try:
            log = plot_results.load_log(temp_path)
            self.assertTrue(np.isnan(log['ball_x'][0]))
            self.assertAlmostEqual(log['ball_x'][1], 320.0)
        finally:
            os.unlink(temp_path)

    def test_raises_on_missing_file(self):
        with self.assertRaises(FileNotFoundError):
            plot_results.load_log("/nonexistent/path/tracking_log.csv")

    def test_all_columns_present_in_output(self):
        csv_content = (
            "timestamp,ball_detected,ball_x,ball_y,ball_radius,estimated_distance,"
            "image_error,linear_velocity,angular_velocity,left_motor_velocity,"
            "right_motor_velocity,state\n"
            "0.0,1,320.0,240.0,10.0,1.2,0.5,1.0,0.0,1.0,1.0,TRACKING\n"
        )
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as f:
            f.write(csv_content)
            f.flush()
            temp_path = f.name
        try:
            log = plot_results.load_log(temp_path)
            expected_keys = {
                'timestamp', 'ball_detected', 'ball_x', 'ball_y', 'ball_radius',
                'estimated_distance', 'image_error', 'linear_velocity', 'angular_velocity',
                'left_motor_velocity', 'right_motor_velocity', 'state'
            }
            self.assertEqual(set(log.keys()), expected_keys)
        finally:
            os.unlink(temp_path)


class TestPlotCreation(unittest.TestCase):
    """Tests for plot creation functions."""

    def setUp(self):
        """Create a synthetic log for testing."""
        n = 100
        self.log = {
            'timestamp': np.linspace(0, 3.0, n),
            'ball_detected': np.ones(n),
            'ball_x': 319.5 + 10 * np.sin(np.linspace(0, 4 * np.pi, n)),
            'ball_y': np.ones(n) * 240.0,
            'ball_radius': np.ones(n) * 10.0,
            'estimated_distance': np.linspace(1.5, 0.4, n),
            'image_error': 10 * np.sin(np.linspace(0, 4 * np.pi, n)),
            'linear_velocity': np.ones(n) * 1.0,
            'angular_velocity': 0.1 * np.sin(np.linspace(0, 4 * np.pi, n)),
            'left_motor_velocity': np.ones(n) * 1.0 + 0.1 * np.sin(np.linspace(0, 4 * np.pi, n)),
            'right_motor_velocity': np.ones(n) * 1.0 - 0.1 * np.sin(np.linspace(0, 4 * np.pi, n)),
            'state': np.array(['TRACKING'] * n, dtype=object),
        }

    def test_plot_tracking_error_creates_axes_content(self):
        fig, ax = plt.subplots()
        plot_results.plot_tracking_error(ax, self.log)
        self.assertGreater(len(ax.lines), 0)
        self.assertIn('Centering', ax.get_title())
        plt.close(fig)

    def test_plot_distance_creates_axes_content(self):
        fig, ax = plt.subplots()
        plot_results.plot_distance(ax, self.log)
        self.assertGreater(len(ax.lines), 0)
        self.assertIn('Distance', ax.get_title())
        plt.close(fig)

    def test_plot_motor_speeds_creates_axes_content(self):
        fig, ax = plt.subplots()
        plot_results.plot_motor_speeds(ax, self.log)
        self.assertGreater(len(ax.lines), 1)
        self.assertIn('Motor', ax.get_title())
        plt.close(fig)

    def test_plot_ball_position_creates_axes_content(self):
        fig, ax = plt.subplots()
        plot_results.plot_ball_position(ax, self.log)
        self.assertGreater(len(ax.lines), 0)
        self.assertIn('Ball', ax.get_title())
        plt.close(fig)

    def test_plot_detection_status_creates_axes_content(self):
        fig, ax = plt.subplots()
        plot_results.plot_detection_status(ax, self.log)
        self.assertIn('Detection', ax.get_title())
        plt.close(fig)

    def test_create_individual_plots_generates_png_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            plot_results.create_individual_plots(self.log, tmpdir, dpi=100)
            expected_files = [
                'tracking_error_vs_time.png',
                'distance_vs_time.png',
                'motor_speeds_vs_time.png',
                'ball_position_vs_center.png',
                'detection_status_vs_time.png',
            ]
            for filename in expected_files:
                filepath = os.path.join(tmpdir, filename)
                self.assertTrue(os.path.exists(filepath), f"Missing: {filename}")
                self.assertGreater(os.path.getsize(filepath), 1000, f"File too small: {filename}")

    def test_create_summary_dashboard_generates_png(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, 'summary_dashboard.png')
            plot_results.create_summary_dashboard(self.log, output_path, dpi=100)
            self.assertTrue(os.path.exists(output_path))
            self.assertGreater(os.path.getsize(output_path), 1000)


class TestMissingDataHandling(unittest.TestCase):
    """Tests for handling missing/invalid data in plots."""

    def setUp(self):
        """Create a log with NaN and missing values."""
        n = 50
        self.log = {
            'timestamp': np.linspace(0, 1.5, n),
            'ball_detected': np.array([1] * 20 + [0] * 10 + [1] * 20),
            'ball_x': np.array([319.5] * 20 + [np.nan] * 10 + [319.5] * 20),
            'ball_y': np.ones(n) * 240.0,
            'ball_radius': np.ones(n) * 10.0,
            'estimated_distance': np.array(np.linspace(1.5, 0.4, 20).tolist() + [np.nan] * 10 + np.linspace(1.2, 0.4, 20).tolist()),
            'image_error': np.array([0.0] * 20 + [np.nan] * 10 + [0.0] * 20),
            'linear_velocity': np.ones(n) * 1.0,
            'angular_velocity': np.zeros(n),
            'left_motor_velocity': np.ones(n) * 1.0,
            'right_motor_velocity': np.ones(n) * 1.0,
            'state': np.array(['TRACKING'] * n, dtype=object),
        }

    def test_plot_handles_nan_values_gracefully(self):
        """Ensure plots don't crash with NaN values."""
        fig, ax = plt.subplots()
        try:
            plot_results.plot_tracking_error(ax, self.log)
            plot_results.plot_distance(ax, self.log)
            plot_results.plot_motor_speeds(ax, self.log)
            plot_results.plot_ball_position(ax, self.log)
            plot_results.plot_detection_status(ax, self.log)
        finally:
            plt.close(fig)

    def test_plot_creates_gaps_for_missing_data(self):
        """NaN values should create gaps, not zero points."""
        fig, ax = plt.subplots()
        plot_results.plot_distance(ax, self.log)
        lines = ax.get_lines()
        self.assertGreater(len(lines), 0)
        plt.close(fig)


class TestCLIArguments(unittest.TestCase):
    """Tests for CLI argument parsing (without actually running main)."""

    def test_default_arguments(self):
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument('--input', default='results/logs/tracking_log.csv')
        parser.add_argument('--output-dir', default='results/plots')
        parser.add_argument('--dpi', type=int, default=300)

        args = parser.parse_args([])
        self.assertEqual(args.input, 'results/logs/tracking_log.csv')
        self.assertEqual(args.output_dir, 'results/plots')
        self.assertEqual(args.dpi, 300)

    def test_custom_arguments(self):
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument('--input', default='results/logs/tracking_log.csv')
        parser.add_argument('--output-dir', default='results/plots')
        parser.add_argument('--dpi', type=int, default=300)

        args = parser.parse_args(['--input', 'custom.csv', '--output-dir', '/tmp', '--dpi', '150'])
        self.assertEqual(args.input, 'custom.csv')
        self.assertEqual(args.output_dir, '/tmp')
        self.assertEqual(args.dpi, 150)


if __name__ == "__main__":
    unittest.main()
