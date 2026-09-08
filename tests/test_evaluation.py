"""Unit tests for the evaluation metrics computation.

Tests the load_log and compute_metrics functions with synthetic log data
and edge cases. Run:

    .venv/Scripts/python.exe -m unittest discover -s tests -v
"""

import os
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))

import run_evaluation


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
            log = run_evaluation.load_log(temp_path)
            self.assertEqual(len(log['timestamp']), 1)
            self.assertEqual(log['ball_detected'][0], 1)
            self.assertAlmostEqual(log['ball_x'][0], 320.0)
            self.assertEqual(log['state'][0], 'TRACKING')
        finally:
            os.unlink(temp_path)

    def test_handles_empty_fields(self):
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
            log = run_evaluation.load_log(temp_path)
            self.assertEqual(log['ball_detected'][0], 0)
            self.assertTrue(np.isnan(log['ball_x'][0]))
            self.assertEqual(log['ball_detected'][1], 1)
            self.assertAlmostEqual(log['ball_x'][1], 320.0)
        finally:
            os.unlink(temp_path)

    def test_raises_on_missing_file(self):
        with self.assertRaises(FileNotFoundError):
            run_evaluation.load_log("/nonexistent/path/tracking_log.csv")


class TestComputeMetrics(unittest.TestCase):
    """Tests for compute_metrics()."""

    def make_log(self, rows):
        """Helper to create a log dict from a list of row dicts."""
        log = {
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
        for row in rows:
            for key in log:
                if key == 'state':
                    log[key].append(row.get(key, ''))
                else:
                    log[key].append(row.get(key, np.nan))
        for key in log:
            if key != 'state':
                log[key] = np.array(log[key])
            else:
                log[key] = np.array(log[key], dtype=object)
        return log

    def test_empty_log_returns_empty_metrics(self):
        log = self.make_log([])
        metrics = run_evaluation.compute_metrics(log)
        self.assertEqual(len(metrics), 0)

    def test_detection_rate_all_detected(self):
        log = self.make_log([
            {'timestamp': 0.0, 'ball_detected': 1},
            {'timestamp': 0.032, 'ball_detected': 1},
            {'timestamp': 0.064, 'ball_detected': 1},
        ])
        metrics = run_evaluation.compute_metrics(log)
        self.assertAlmostEqual(metrics['detection_rate_pct'], 100.0, places=1)

    def test_detection_rate_none_detected(self):
        log = self.make_log([
            {'timestamp': 0.0, 'ball_detected': 0},
            {'timestamp': 0.032, 'ball_detected': 0},
        ])
        metrics = run_evaluation.compute_metrics(log)
        self.assertAlmostEqual(metrics['detection_rate_pct'], 0.0, places=1)

    def test_detection_rate_partial(self):
        log = self.make_log([
            {'timestamp': 0.0, 'ball_detected': 1},
            {'timestamp': 0.032, 'ball_detected': 0},
            {'timestamp': 0.064, 'ball_detected': 1},
            {'timestamp': 0.096, 'ball_detected': 0},
        ])
        metrics = run_evaluation.compute_metrics(log)
        self.assertAlmostEqual(metrics['detection_rate_pct'], 50.0, places=1)

    def test_tracking_success_rate(self):
        log = self.make_log([
            {'timestamp': 0.0, 'state': 'SEARCHING'},
            {'timestamp': 0.032, 'state': 'TRACKING'},
            {'timestamp': 0.064, 'state': 'APPROACHING'},
            {'timestamp': 0.096, 'state': 'STOPPED'},
        ])
        metrics = run_evaluation.compute_metrics(log)
        self.assertAlmostEqual(metrics['tracking_success_rate_pct'], 50.0, places=1)

    def test_mae_from_detected_frames(self):
        log = self.make_log([
            {'timestamp': 0.0, 'ball_detected': 1, 'image_error': 0.0},
            {'timestamp': 0.032, 'ball_detected': 1, 'image_error': 2.0},
            {'timestamp': 0.064, 'ball_detected': 1, 'image_error': -4.0},
            {'timestamp': 0.096, 'ball_detected': 0, 'image_error': np.nan},
        ])
        metrics = run_evaluation.compute_metrics(log)
        expected_mae = (abs(0.0) + abs(2.0) + abs(-4.0)) / 3
        self.assertAlmostEqual(metrics['mae_px'], expected_mae, places=6)

    def test_max_error(self):
        log = self.make_log([
            {'timestamp': 0.0, 'ball_detected': 1, 'image_error': 5.0},
            {'timestamp': 0.032, 'ball_detected': 1, 'image_error': 2.0},
            {'timestamp': 0.064, 'ball_detected': 1, 'image_error': -10.0},
        ])
        metrics = run_evaluation.compute_metrics(log)
        self.assertAlmostEqual(metrics['max_error_px'], 10.0, places=6)

    def test_response_time_first_centering(self):
        log = self.make_log([
            {'timestamp': 0.0, 'ball_detected': 1, 'image_error': 50.0},
            {'timestamp': 0.032, 'ball_detected': 1, 'image_error': 20.0},
            {'timestamp': 0.064, 'ball_detected': 1, 'image_error': 3.0},
            {'timestamp': 0.096, 'ball_detected': 1, 'image_error': 1.0},
        ])
        metrics = run_evaluation.compute_metrics(log)
        self.assertAlmostEqual(metrics['response_time_s'], 0.064, places=3)

    def test_response_time_none_if_never_centered(self):
        log = self.make_log([
            {'timestamp': 0.0, 'ball_detected': 1, 'image_error': 50.0},
            {'timestamp': 0.032, 'ball_detected': 1, 'image_error': 20.0},
            {'timestamp': 0.064, 'ball_detected': 1, 'image_error': 10.0},
        ])
        metrics = run_evaluation.compute_metrics(log)
        self.assertIsNone(metrics['response_time_s'])

    def test_final_distance_error(self):
        log = self.make_log([
            {'timestamp': 0.0, 'estimated_distance': 1.2},
            {'timestamp': 0.032, 'estimated_distance': 0.9},
            {'timestamp': 0.064, 'estimated_distance': 0.42},
        ])
        metrics = run_evaluation.compute_metrics(log)
        expected = (abs(1.2 - 0.40) + abs(0.9 - 0.40) + abs(0.42 - 0.40)) / 3
        self.assertAlmostEqual(metrics['final_distance_error_m'], expected, places=4)

    def test_recovery_time_single_loss_recovery(self):
        log = self.make_log([
            {'timestamp': 0.0, 'ball_detected': 1},
            {'timestamp': 0.032, 'ball_detected': 1},
            {'timestamp': 0.064, 'ball_detected': 0},
            {'timestamp': 0.096, 'ball_detected': 0},
            {'timestamp': 0.128, 'ball_detected': 1},
        ])
        metrics = run_evaluation.compute_metrics(log)
        expected_recovery_time = 0.128 - 0.064
        self.assertAlmostEqual(metrics['recovery_time_s'], expected_recovery_time, places=3)
        self.assertEqual(metrics['num_recoveries'], 1)

    def test_recovery_time_multiple_losses(self):
        log = self.make_log([
            {'timestamp': 0.0, 'ball_detected': 1},
            {'timestamp': 0.032, 'ball_detected': 0},
            {'timestamp': 0.064, 'ball_detected': 1},
            {'timestamp': 0.096, 'ball_detected': 0},
            {'timestamp': 0.128, 'ball_detected': 0},
            {'timestamp': 0.160, 'ball_detected': 1},
        ])
        metrics = run_evaluation.compute_metrics(log)
        recovery_times = [(0.064 - 0.032), (0.160 - 0.096)]
        expected_avg = sum(recovery_times) / len(recovery_times)
        self.assertAlmostEqual(metrics['recovery_time_s'], expected_avg, places=3)
        self.assertEqual(metrics['num_recoveries'], 2)

    def test_recovery_time_none_if_no_loss(self):
        log = self.make_log([
            {'timestamp': 0.0, 'ball_detected': 1},
            {'timestamp': 0.032, 'ball_detected': 1},
            {'timestamp': 0.064, 'ball_detected': 1},
        ])
        metrics = run_evaluation.compute_metrics(log)
        self.assertIsNone(metrics['recovery_time_s'])
        self.assertEqual(metrics['num_recoveries'], 0)

    def test_fps_calculation(self):
        log = self.make_log([
            {'timestamp': 0.0},
            {'timestamp': 0.032},
            {'timestamp': 0.064},
            {'timestamp': 0.096},
            {'timestamp': 0.128},
        ])
        metrics = run_evaluation.compute_metrics(log)
        expected_fps = 4 / 0.128
        self.assertAlmostEqual(metrics['fps'], expected_fps, places=1)


class TestFormatReport(unittest.TestCase):
    """Tests for format_report()."""

    def test_format_report_includes_key_metrics(self):
        metrics = {
            'detection_rate_pct': 95.5,
            'tracking_success_rate_pct': 88.2,
            'mae_px': 3.4,
            'max_error_px': 12.1,
            'response_time_s': 0.5,
            'final_distance_error_m': 0.02,
            'recovery_time_s': 1.2,
            'num_recoveries': 3,
            'fps': 31.25,
        }
        report = run_evaluation.format_report(metrics)
        self.assertIn('Detection Rate', report)
        self.assertIn('95.50', report)
        self.assertIn('Tracking Success Rate', report)
        self.assertIn('Mean Absolute Error', report)
        self.assertIn('3.40', report)

    def test_format_report_handles_none_values(self):
        metrics = {
            'detection_rate_pct': 50.0,
            'response_time_s': None,
            'final_distance_error_m': None,
            'recovery_time_s': None,
            'num_recoveries': 0,
            'fps': 0.0,
        }
        report = run_evaluation.format_report(metrics)
        self.assertIn('N/A', report)


if __name__ == "__main__":
    unittest.main()
