"""Unit tests for the benchmark suite.

Tests benchmark orchestration, scenario definition, metrics collection,
and report generation. Run:

    .venv/Scripts/python.exe -m unittest discover -s tests -v
"""

import json
import os
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))

import run_benchmarks
import run_evaluation


class TestBenchmarkScenarios(unittest.TestCase):
    """Tests for benchmark scenario definitions."""

    def test_all_scenarios_defined(self):
        self.assertEqual(len(run_benchmarks.BENCHMARK_SCENARIOS), 5)

    def test_scenario_names(self):
        names = {s['name'] for s in run_benchmarks.BENCHMARK_SCENARIOS}
        expected = {'static_ball', 'lateral_movement', 'approaching_ball', 'ball_lost', 'dynamic_curved'}
        self.assertEqual(names, expected)

    def test_scenario_has_required_fields(self):
        for scenario in run_benchmarks.BENCHMARK_SCENARIOS:
            self.assertIn('name', scenario)
            self.assertIn('description', scenario)
            self.assertIn('duration_s', scenario)
            self.assertIn('environment', scenario)
            self.assertIsInstance(scenario['duration_s'], int)
            self.assertGreater(scenario['duration_s'], 0)

    def test_scenario_descriptions_are_meaningful(self):
        for scenario in run_benchmarks.BENCHMARK_SCENARIOS:
            desc = scenario['description']
            self.assertGreater(len(desc), 10)  # Non-trivial description
            self.assertIn(' ', desc)  # Multi-word

    def test_durations_are_reasonable(self):
        for scenario in run_benchmarks.BENCHMARK_SCENARIOS:
            duration = scenario['duration_s']
            self.assertGreaterEqual(duration, 20)  # At least 20 seconds
            self.assertLessEqual(duration, 60)  # At most 60 seconds


class TestMetricsCollection(unittest.TestCase):
    """Tests for metrics collection and storage."""

    def setUp(self):
        """Create a synthetic log for testing."""
        n = 100
        self.log = {
            'timestamp': np.linspace(0, 3.0, n),
            'ball_detected': np.ones(n),
            'ball_x': np.ones(n) * 319.5,
            'ball_y': np.ones(n) * 240.0,
            'ball_radius': np.ones(n) * 10.0,
            'estimated_distance': np.linspace(1.5, 0.4, n),
            'image_error': np.zeros(n),
            'linear_velocity': np.ones(n) * 1.0,
            'angular_velocity': np.zeros(n),
            'left_motor_velocity': np.ones(n) * 1.0,
            'right_motor_velocity': np.ones(n) * 1.0,
            'state': np.array(['TRACKING'] * n, dtype=object),
        }

    def test_evaluate_scenario_returns_metrics_dict(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as f:
            f.write("timestamp,ball_detected,ball_x,ball_y,ball_radius,estimated_distance,"
                   "image_error,linear_velocity,angular_velocity,left_motor_velocity,"
                   "right_motor_velocity,state\n")
            f.write("0.0,1,320.0,240.0,10.0,1.2,0.0,1.0,0.0,1.0,1.0,TRACKING\n")
            f.flush()
            temp_path = f.name
        try:
            metrics = run_benchmarks.evaluate_scenario('test', temp_path)
            self.assertIsNotNone(metrics)
            self.assertIsInstance(metrics, dict)
            self.assertIn('detection_rate_pct', metrics)
        finally:
            os.unlink(temp_path)

    def test_evaluate_scenario_handles_missing_file(self):
        metrics = run_benchmarks.evaluate_scenario('test', '/nonexistent/path.csv')
        self.assertIsNone(metrics)

    def test_save_metrics_json_creates_valid_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, 'metrics.json')
            metrics = {
                'detection_rate_pct': 100.0,
                'mae_px': 0.5,
                'response_time_s': 0.1,
            }
            run_benchmarks.save_metrics_json('test_scenario', metrics, output_path)
            self.assertTrue(os.path.exists(output_path))

            with open(output_path, 'r') as f:
                data = json.load(f)
            self.assertEqual(data['scenario'], 'test_scenario')
            self.assertIn('metrics', data)
            self.assertEqual(data['metrics']['detection_rate_pct'], 100.0)


class TestReportGeneration(unittest.TestCase):
    """Tests for benchmark report generation."""

    def setUp(self):
        """Create synthetic benchmark results."""
        self.benchmark_results = {
            'static_ball': {
                'detection_rate_pct': 100.0,
                'tracking_success_rate_pct': 90.0,
                'mae_px': 0.5,
                'max_error_px': 2.0,
                'response_time_s': 0.1,
                'final_distance_error_m': 0.03,
                'recovery_time_s': None,
                'num_recoveries': 0,
                'fps': 31.25,
            },
            'lateral_movement': {
                'detection_rate_pct': 98.0,
                'tracking_success_rate_pct': 85.0,
                'mae_px': 1.2,
                'max_error_px': 5.0,
                'response_time_s': 0.2,
                'final_distance_error_m': 0.04,
                'recovery_time_s': None,
                'num_recoveries': 0,
                'fps': 31.25,
            },
        }

    def test_generate_benchmark_report_creates_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = os.path.join(tmpdir, 'benchmark_report.md')
            report_text = run_benchmarks.generate_benchmark_report(
                self.benchmark_results, report_path
            )
            self.assertTrue(os.path.exists(report_path))
            self.assertGreater(len(report_text), 100)

    def test_report_contains_scenario_results(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = os.path.join(tmpdir, 'benchmark_report.md')
            report_text = run_benchmarks.generate_benchmark_report(
                self.benchmark_results, report_path
            )
            self.assertIn('static_ball', report_text)
            self.assertIn('lateral_movement', report_text)

    def test_report_contains_metrics_table(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = os.path.join(tmpdir, 'benchmark_report.md')
            report_text = run_benchmarks.generate_benchmark_report(
                self.benchmark_results, report_path
            )
            # Check for table markers
            self.assertIn('|', report_text)
            self.assertIn('Detection Rate', report_text)
            self.assertIn('MAE (px)', report_text)

    def test_report_handles_none_metrics(self):
        results_with_none = self.benchmark_results.copy()
        results_with_none['bad_scenario'] = None

        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = os.path.join(tmpdir, 'benchmark_report.md')
            report_text = run_benchmarks.generate_benchmark_report(
                results_with_none, report_path
            )
            self.assertTrue(os.path.exists(report_path))
            self.assertIn('bad_scenario', report_text)


class TestBenchmarkResults(unittest.TestCase):
    """Tests for benchmark result analysis."""

    def setUp(self):
        self.results = {
            'static_ball': {'detection_rate_pct': 100.0, 'mae_px': 0.5},
            'lateral_movement': {'detection_rate_pct': 95.0, 'mae_px': 2.0},
            'approaching_ball': {'detection_rate_pct': 98.0, 'mae_px': 1.5},
            'ball_lost': {'detection_rate_pct': 90.0, 'mae_px': 3.0},
            'dynamic_curved': {'detection_rate_pct': 92.0, 'mae_px': 2.5},
        }

    def test_all_scenarios_have_results(self):
        self.assertEqual(len(self.results), 5)
        for name in ['static_ball', 'lateral_movement', 'approaching_ball', 'ball_lost', 'dynamic_curved']:
            self.assertIn(name, self.results)

    def test_best_detection_rate_finder(self):
        best = max(self.results.items(), key=lambda x: x[1]['detection_rate_pct'] if x[1] else 0)
        self.assertEqual(best[0], 'static_ball')
        self.assertEqual(best[1]['detection_rate_pct'], 100.0)

    def test_lowest_mae_finder(self):
        best = min(
            [(k, v) for k, v in self.results.items() if v],
            key=lambda x: x[1]['mae_px']
        )
        self.assertEqual(best[0], 'static_ball')
        self.assertEqual(best[1]['mae_px'], 0.5)


class TestScenarioEnvironment(unittest.TestCase):
    """Tests for scenario environment variable configuration."""

    def test_static_ball_scenario_config(self):
        static = next(s for s in run_benchmarks.BENCHMARK_SCENARIOS if s['name'] == 'static_ball')
        self.assertIn('BALL_MOTION_TYPE', static['environment'])
        self.assertEqual(static['environment']['BALL_MOTION_TYPE'], 'static')

    def test_lateral_movement_scenario_config(self):
        lateral = next(s for s in run_benchmarks.BENCHMARK_SCENARIOS if s['name'] == 'lateral_movement')
        self.assertIn('BALL_MOTION_TYPE', lateral['environment'])
        self.assertEqual(lateral['environment']['BALL_MOTION_TYPE'], 'lateral_sine')

    def test_approaching_ball_scenario_config(self):
        approaching = next(s for s in run_benchmarks.BENCHMARK_SCENARIOS if s['name'] == 'approaching_ball')
        self.assertIn('BALL_MOTION_TYPE', approaching['environment'])
        self.assertEqual(approaching['environment']['BALL_MOTION_TYPE'], 'approaching')

    def test_ball_lost_scenario_config(self):
        lost = next(s for s in run_benchmarks.BENCHMARK_SCENARIOS if s['name'] == 'ball_lost')
        self.assertIn('BALL_MOTION_TYPE', lost['environment'])
        self.assertEqual(lost['environment']['BALL_MOTION_TYPE'], 'disappear_reappear')

    def test_dynamic_curved_scenario_config(self):
        curved = next(s for s in run_benchmarks.BENCHMARK_SCENARIOS if s['name'] == 'dynamic_curved')
        self.assertIn('BALL_MOTION_TYPE', curved['environment'])
        self.assertEqual(curved['environment']['BALL_MOTION_TYPE'], 'circular')


if __name__ == "__main__":
    unittest.main()
