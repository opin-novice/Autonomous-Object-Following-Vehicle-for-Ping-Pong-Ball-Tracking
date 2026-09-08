"""Unit tests for the CSV logger."""

import csv
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "webots", "controllers", "ball_follower"))

import config
import control
import logger
import vision


class TestLoggerFormatting(unittest.TestCase):
    def test_detected_ball_fields_populated(self):
        det = vision.Detection(detected=True, center_x=350.0, center_y=270.0,
                               radius=9.7, area=280.0, confidence=0.9)
        ranging = vision.RangeBearing(valid=True, distance_m=1.2,
                                      bearing_rad=0.0, bearing_deg=0.0)
        cmd = control.DriveCommand(left_velocity=1.0, right_velocity=1.0,
                                   linear_command=0.9, angular_command=0.0)
        row = logger.format_row(1.0, det, ranging, cmd, "TRACKING")

        self.assertEqual(row["timestamp"], 1.0)
        self.assertEqual(row["ball_detected"], 1)
        self.assertAlmostEqual(row["ball_x"], 350.0)
        self.assertAlmostEqual(row["ball_y"], 270.0)
        self.assertAlmostEqual(row["ball_radius"], 9.7)
        self.assertAlmostEqual(row["estimated_distance"], 1.2)
        self.assertAlmostEqual(row["image_error"],
                               350.0 - config.IMAGE_CENTER_X)
        self.assertAlmostEqual(row["linear_velocity"], 0.9)
        self.assertEqual(row["state"], "TRACKING")

    def test_missing_ball_fields_empty(self):
        det = vision.Detection.miss()
        ranging = vision.RangeBearing(valid=False)
        cmd = control.DriveCommand(0.0, 0.0, 0.0, 0.0)
        row = logger.format_row(2.0, det, ranging, cmd, "SEARCHING")

        self.assertEqual(row["ball_detected"], 0)
        self.assertEqual(row["ball_x"], "")
        self.assertEqual(row["ball_y"], "")
        self.assertEqual(row["ball_radius"], "")
        self.assertEqual(row["image_error"], "")
        self.assertEqual(row["estimated_distance"], "")
        self.assertEqual(row["state"], "SEARCHING")

    def test_gated_distance_is_empty(self):
        # bearing survives gating, distance doesn't
        det = vision.Detection(detected=True, center_x=320.0, center_y=270.0,
                               radius=2.0, area=12.0, confidence=0.95)
        ranging = vision.estimate_distance_and_bearing(det)
        self.assertFalse(ranging.valid)
        self.assertIsNotNone(ranging.bearing_deg)
        row = logger.format_row(3.0, det, ranging, None, "STOPPED")

        self.assertEqual(row["ball_detected"], 1)
        self.assertEqual(row["estimated_distance"], "")
        self.assertEqual(row["state"], "STOPPED")

    def test_none_inputs_are_handled(self):
        row = logger.format_row(4.0, None, None, None, None)
        self.assertEqual(row["ball_detected"], 0)
        self.assertEqual(row["ball_x"], "")
        self.assertEqual(row["estimated_distance"], "")
        self.assertEqual(row["state"], "")

    def test_fieldnames_match_the_spec(self):
        expected = ["timestamp", "ball_detected", "ball_x", "ball_y", "ball_radius",
                    "estimated_distance", "image_error", "linear_velocity",
                    "angular_velocity", "left_motor_velocity", "right_motor_velocity", "state"]
        self.assertEqual(logger.FIELDNAMES, expected)


class TestCSVLogger(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.path = os.path.join(self.tmpdir, "test.csv")

    def tearDown(self):
        import shutil
        if os.path.exists(self.tmpdir):
            shutil.rmtree(self.tmpdir)

    def test_logger_creates_parent_directory(self):
        nested_path = os.path.join(self.tmpdir, "sub", "dir", "test.csv")
        log = logger.CSVLogger(nested_path)
        self.assertTrue(os.path.exists(os.path.dirname(nested_path)))
        log.close()

    def test_logger_writes_header(self):
        log = logger.CSVLogger(self.path)
        log.close()
        with open(self.path, newline="") as f:
            reader = csv.DictReader(f)
            self.assertEqual(reader.fieldnames, logger.FIELDNAMES)

    def test_logger_writes_and_reads_back_rows(self):
        log = logger.CSVLogger(self.path)
        det = vision.Detection(detected=True, center_x=320.0, center_y=270.0,
                               radius=9.7, area=280.0, confidence=0.9)
        ranging = vision.RangeBearing(valid=True, distance_m=1.2,
                                      bearing_rad=0.0, bearing_deg=0.0)
        cmd = control.DriveCommand(1.0, 1.0, 0.9, 0.0)
        row = logger.format_row(0.032, det, ranging, cmd, "TRACKING")
        log.write_row(row)
        log.close()

        with open(self.path, newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            self.assertEqual(len(rows), 1)
            self.assertAlmostEqual(float(rows[0]["timestamp"]), 0.032)
            self.assertEqual(rows[0]["ball_detected"], "1")
            self.assertAlmostEqual(float(rows[0]["estimated_distance"]), 1.2)
            self.assertEqual(rows[0]["state"], "TRACKING")

    def test_logger_rows_written_counter(self):
        log = logger.CSVLogger(self.path)
        det = vision.Detection(detected=True, center_x=320.0, center_y=270.0,
                               radius=9.7, area=280.0, confidence=0.9)
        ranging = vision.RangeBearing(valid=True, distance_m=1.2,
                                      bearing_rad=0.0, bearing_deg=0.0)
        cmd = control.DriveCommand(1.0, 1.0, 0.9, 0.0)
        for i in range(5):
            row = logger.format_row(0.032 * i, det, ranging, cmd, "TRACKING")
            log.write_row(row)
        log.close()
        self.assertEqual(log.rows_written, 5)


if __name__ == "__main__":
    unittest.main()
