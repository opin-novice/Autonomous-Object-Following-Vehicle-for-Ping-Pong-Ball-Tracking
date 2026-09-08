r"""Unit tests for the FollowController Finite State Machine (PROMPT 9).

Tests state transitions, hysteresis bounds, coasting, and search direction.

Run:
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
    """Create a mock detection and range fix."""
    center_x = config.IMAGE_CENTER_X + config.FOCAL_LENGTH_PX * math.tan(math.radians(bearing_deg))
    detection = vision.Detection(
        detected=True, center_x=center_x, center_y=272.0,
        radius=9.7, area=270.0, confidence=confidence
    )
    ranging = vision.RangeBearing(
        valid=True, distance_m=distance_m,
        bearing_rad=math.radians(bearing_deg),
        bearing_deg=bearing_deg
    )
    return detection, ranging


class TestFSMStateTransitions(unittest.TestCase):
    def test_initial_state_defaults_to_searching(self):
        follower = control.FollowController()
        self.assertEqual(follower.state, control.RobotState.SEARCHING)

    def test_detection_with_large_bearing_transitions_to_tracking(self):
        follower = control.FollowController()
        detection, ranging = seen(bearing_deg=10.0, distance_m=1.5)
        cmd = follower.step(detection, ranging, delta_time_s=0.032)
        self.assertEqual(follower.state, control.RobotState.TRACKING)
        self.assertAlmostEqual(cmd.linear_command, 0.0, places=5)
        self.assertNotEqual(cmd.angular_command, 0.0)

    def test_detection_with_small_bearing_transitions_to_approaching(self):
        follower = control.FollowController()
        detection, ranging = seen(bearing_deg=2.0, distance_m=1.5)
        cmd = follower.step(detection, ranging, delta_time_s=0.032)
        self.assertEqual(follower.state, control.RobotState.APPROACHING)
        self.assertGreater(cmd.linear_command, 0.0)

    def test_reaching_target_distance_transitions_to_stopped(self):
        follower = control.FollowController()
        detection, ranging = seen(bearing_deg=0.0, distance_m=config.TARGET_DISTANCE_M)
        cmd = follower.step(detection, ranging, delta_time_s=0.032)
        self.assertEqual(follower.state, control.RobotState.STOPPED)
        self.assertEqual((cmd.left_velocity, cmd.right_velocity), (0.0, 0.0))

    def test_reacquisition_from_searching_immediately_exits_searching(self):
        follower = control.FollowController()
        self.assertEqual(follower.state, control.RobotState.SEARCHING)

        detection, ranging = seen(bearing_deg=1.0, distance_m=1.0, confidence=0.85)
        follower.step(detection, ranging, delta_time_s=0.032)
        self.assertIn(follower.state, [control.RobotState.APPROACHING, control.RobotState.TRACKING])


class TestFSMHysteresis(unittest.TestCase):
    def test_stopped_state_holds_within_hysteresis_boundary(self):
        follower = control.FollowController()
        # Arrive at target distance
        detection, ranging = seen(bearing_deg=0.0, distance_m=config.TARGET_DISTANCE_M)
        follower.step(detection, ranging, delta_time_s=0.032)
        self.assertEqual(follower.state, control.RobotState.STOPPED)

        # Ball shifts slightly further away, but inside hysteresis boundary
        slight_drift = config.TARGET_DISTANCE_M + config.DISTANCE_TOLERANCE_M + (config.STOP_HYSTERESIS_M * 0.5)
        detection2, ranging2 = seen(bearing_deg=0.0, distance_m=slight_drift)
        cmd = follower.step(detection2, ranging2, delta_time_s=0.032)

        self.assertEqual(follower.state, control.RobotState.STOPPED)
        self.assertEqual((cmd.left_velocity, cmd.right_velocity), (0.0, 0.0))

    def test_stopped_state_resumes_motion_when_beyond_hysteresis(self):
        follower = control.FollowController()
        # Arrive at target distance
        detection, ranging = seen(bearing_deg=0.0, distance_m=config.TARGET_DISTANCE_M)
        follower.step(detection, ranging, delta_time_s=0.032)
        self.assertEqual(follower.state, control.RobotState.STOPPED)

        # Ball shifts beyond target + tolerance + hysteresis
        large_drift = config.TARGET_DISTANCE_M + config.DISTANCE_TOLERANCE_M + config.STOP_HYSTERESIS_M + 0.02
        detection2, ranging2 = seen(bearing_deg=0.0, distance_m=large_drift)
        cmd = follower.step(detection2, ranging2, delta_time_s=0.032)

        self.assertEqual(follower.state, control.RobotState.APPROACHING)
        self.assertGreater(cmd.linear_command, 0.0)


class TestCoastingAndSearch(unittest.TestCase):
    def test_ball_loss_coasting_decelerates(self):
        follower = control.FollowController()
        # Drive forward first
        detection, ranging = seen(bearing_deg=0.0, distance_m=1.5)
        cmd_init = follower.step(detection, ranging, delta_time_s=0.032)
        self.assertEqual(follower.state, control.RobotState.APPROACHING)
        self.assertGreater(cmd_init.linear_command, 0.0)

        # Loss frame 1 (within coast window)
        cmd_coast1 = follower.step(vision.Detection.miss(), vision.RangeBearing(valid=False), delta_time_s=0.1)
        self.assertEqual(follower.state, control.RobotState.SEARCHING)
        self.assertLess(cmd_coast1.linear_command, cmd_init.linear_command)
        self.assertGreater(cmd_coast1.linear_command, 0.0)

        # Loss past coast duration -> full search spin
        cmd_search = follower.step(vision.Detection.miss(), vision.RangeBearing(valid=False), delta_time_s=0.3)
        self.assertEqual(follower.state, control.RobotState.SEARCHING)
        self.assertEqual(cmd_search.linear_command, 0.0)
        self.assertNotEqual(cmd_search.angular_command, 0.0)

    def test_search_direction_remembers_last_known_bearing(self):
        follower = control.FollowController()

        # Last seen on the right (positive bearing)
        detection, ranging = seen(bearing_deg=+15.0, distance_m=1.0)
        follower.step(detection, ranging, delta_time_s=0.032)
        self.assertGreaterEqual(follower.last_known_bearing, 0.0)

        # Trigger search mode
        follower.step(vision.Detection.miss(), vision.RangeBearing(valid=False), delta_time_s=0.5)
        cmd_right = follower.search_command()
        self.assertGreater(cmd_right.angular_command, 0.0)  # Rotate left (positive v_angular)

        # Last seen on the left (negative bearing)
        detection_left, ranging_left = seen(bearing_deg=-15.0, distance_m=1.0)
        follower.step(detection_left, ranging_left, delta_time_s=0.032)
        self.assertLess(follower.last_known_bearing, 0.0)

        # Trigger search mode
        follower.step(vision.Detection.miss(), vision.RangeBearing(valid=False), delta_time_s=0.5)
        cmd_left = follower.search_command()
        self.assertLess(cmd_left.angular_command, 0.0)  # Rotate right (negative v_angular)


if __name__ == "__main__":
    unittest.main()
