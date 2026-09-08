r"""Unit tests for the proportional follower controller.

control.py is pure arithmetic over plain dataclasses, so none of this needs Webots or
OpenCV. Run:

    .venv\Scripts\python.exe -m unittest discover -s tests -v
"""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "webots", "controllers", "ball_follower"))

import config
import control
import vision


def seen(bearing_deg=0.0, distance_m=1.2, confidence=0.9):
    """A detection and range fix as the vision stack would deliver them."""
    center_x = config.IMAGE_CENTER_X + config.FOCAL_LENGTH_PX * math.tan(math.radians(bearing_deg))
    detection = vision.Detection(detected=True, center_x=center_x, center_y=272.0,
                                 radius=9.7, area=270.0, confidence=confidence)
    ranging = vision.RangeBearing(valid=True, distance_m=distance_m,
                                  bearing_rad=math.radians(bearing_deg),
                                  bearing_deg=bearing_deg)
    return detection, ranging


class TestSafetyStops(unittest.TestCase):
    def test_no_detection_stops_the_motors(self):
        self.assertEqual(control.compute_wheel_speeds(vision.Detection.miss(),
                                                      vision.RangeBearing(valid=False)),
                         (0.0, 0.0))

    def test_invalid_range_stops_the_motors(self):
        detection, _ = seen()
        self.assertEqual(control.compute_wheel_speeds(detection,
                                                      vision.RangeBearing(valid=False)),
                         (0.0, 0.0))

    def test_none_inputs_stop_the_motors(self):
        self.assertEqual(control.compute_wheel_speeds(None, None), (0.0, 0.0))

    def test_gated_low_confidence_stops_the_motors(self):
        weak = vision.Detection(detected=True, center_x=400.0, center_y=240.0,
                                radius=9.7, area=270.0, confidence=0.2)
        ranging = vision.estimate_distance_and_bearing(weak)
        self.assertFalse(ranging.valid)
        self.assertEqual(control.compute_wheel_speeds(weak, ranging), (0.0, 0.0))


class TestSteering(unittest.TestCase):
    def test_ball_on_the_right_turns_right(self):
        left, right = control.compute_wheel_speeds(*seen(bearing_deg=+10.0))
        self.assertGreater(left, right)

    def test_ball_on_the_left_turns_left(self):
        left, right = control.compute_wheel_speeds(*seen(bearing_deg=-10.0))
        self.assertGreater(right, left)

    def test_centred_ball_drives_both_wheels_equally(self):
        left, right = control.compute_wheel_speeds(*seen(bearing_deg=0.0))
        self.assertAlmostEqual(left, right, places=9)
        self.assertGreater(left, 0.0)

    def test_steering_effort_grows_with_bearing(self):
        small = control.compute_wheel_speeds(*seen(bearing_deg=2.0))
        large = control.compute_wheel_speeds(*seen(bearing_deg=20.0))
        self.assertGreater(abs(small[0] - small[1]), 0.0)
        self.assertGreater(abs(large[0] - large[1]), abs(small[0] - small[1]))

    def test_angular_command_sign_convention(self):
        self.assertLess(control.angular_command(+0.2), 0.0)
        self.assertGreater(control.angular_command(-0.2), 0.0)


class TestForwardSpeed(unittest.TestCase):
    def test_far_ball_drives_forward(self):
        left, right = control.compute_wheel_speeds(*seen(distance_m=1.2))
        self.assertGreater(left, 0.0)
        self.assertGreater(right, 0.0)

    def test_closer_ball_drives_more_slowly(self):
        far = control.compute_wheel_speeds(*seen(distance_m=1.5))[0]
        near = control.compute_wheel_speeds(*seen(distance_m=0.7))[0]
        self.assertGreater(far, near)

    def test_ball_inside_target_reverses(self):
        left, right = control.compute_wheel_speeds(*seen(distance_m=0.25))
        self.assertLess(left, 0.0)
        self.assertLess(right, 0.0)

    def test_linear_command_is_proportional_to_error(self):
        self.assertAlmostEqual(control.linear_command(0.8), config.KP_DIST * 0.8, places=9)
        self.assertAlmostEqual(control.linear_command(-0.5), config.KP_DIST * -0.5, places=9)


class TestDeadband(unittest.TestCase):
    def test_at_target_distance_the_robot_stops(self):
        left, right = control.compute_wheel_speeds(*seen(distance_m=config.TARGET_DISTANCE_M))
        self.assertEqual((left, right), (0.0, 0.0))

    def test_both_deadband_edges_command_zero_forward(self):
        # probed just inside the edge rather than exactly on it: reconstructing the
        # boundary as target +/- tolerance lands a few 1e-17 outside it in binary
        # floating point, which would test IEEE754 rather than the controller
        inset = config.DISTANCE_TOLERANCE_M * 0.999
        for distance in (config.TARGET_DISTANCE_M - inset,
                         config.TARGET_DISTANCE_M + inset):
            with self.subTest(distance_m=distance):
                self.assertEqual(control.linear_command(
                    control.distance_error(distance)), 0.0)

    def test_just_outside_the_deadband_on_either_side_moves(self):
        outset = config.DISTANCE_TOLERANCE_M * 1.01
        self.assertLess(control.linear_command(
            control.distance_error(config.TARGET_DISTANCE_M - outset)), 0.0)
        self.assertGreater(control.linear_command(
            control.distance_error(config.TARGET_DISTANCE_M + outset)), 0.0)

    def test_just_outside_the_deadband_moves_again(self):
        beyond = config.TARGET_DISTANCE_M + config.DISTANCE_TOLERANCE_M + 0.01
        self.assertGreater(control.linear_command(control.distance_error(beyond)), 0.0)

    def test_inside_the_deadband_a_bearing_error_still_steers(self):
        left, right = control.compute_wheel_speeds(
            *seen(distance_m=config.TARGET_DISTANCE_M, bearing_deg=15.0))
        self.assertNotEqual(left, right)

    def test_deadband_stop_is_not_lifted_by_the_stiction_floor(self):
        left, right = control.compute_wheel_speeds(
            *seen(distance_m=config.TARGET_DISTANCE_M, bearing_deg=0.0))
        self.assertEqual((left, right), (0.0, 0.0))


class TestLimits(unittest.TestCase):
    def test_wheel_speeds_are_clamped(self):
        left, right = control.compute_wheel_speeds(*seen(distance_m=3.4, bearing_deg=25.0))
        for speed in (left, right):
            self.assertLessEqual(abs(speed), config.MAX_WHEEL_SPEED + 1e-9)

    def test_controller_ceiling_respects_the_motor_limit(self):
        self.assertLessEqual(config.MAX_WHEEL_SPEED, config.MAX_WHEEL_VELOCITY_RAD_S)

    def test_clamp_helper(self):
        self.assertEqual(control.clamp(5.0, -1.0, 1.0), 1.0)
        self.assertEqual(control.clamp(-5.0, -1.0, 1.0), -1.0)
        self.assertEqual(control.clamp(0.25, -1.0, 1.0), 0.25)

    def test_stiction_floor_lifts_small_commands_and_keeps_sign(self):
        self.assertEqual(control.apply_min_wheel_speed(0.0), 0.0)
        self.assertEqual(control.apply_min_wheel_speed(0.1), config.MIN_WHEEL_SPEED)
        self.assertEqual(control.apply_min_wheel_speed(-0.1), -config.MIN_WHEEL_SPEED)
        self.assertEqual(control.apply_min_wheel_speed(3.0), 3.0)

    def test_mixer_matches_the_documented_equations(self):
        left, right = control.differential_drive_mixer(1.0, 0.25, apply_floor=False)
        self.assertAlmostEqual(left, 0.75, places=9)
        self.assertAlmostEqual(right, 1.25, places=9)


class TestDriveCommandRecord(unittest.TestCase):
    def test_command_carries_its_intermediates(self):
        command = control.compute_drive_command(*seen(distance_m=1.2, bearing_deg=5.0))
        self.assertAlmostEqual(command.linear_command,
                               config.KP_DIST * (1.2 - config.TARGET_DISTANCE_M), places=9)
        self.assertAlmostEqual(command.angular_command,
                               -config.KP_STEER * math.radians(5.0), places=9)
        self.assertEqual(command.as_tuple(), (command.left_velocity, command.right_velocity))


if __name__ == "__main__":
    unittest.main()
