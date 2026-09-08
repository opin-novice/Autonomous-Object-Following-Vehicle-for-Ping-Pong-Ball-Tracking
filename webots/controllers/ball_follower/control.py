"""Proportional differential-drive following controller.

Takes a Detection plus the gated RangeBearing from vision and produces wheel velocities.
Holds no OpenCV and no Webots imports, so the control law can be reasoned about and tested
in isolation from both the vision stack and the simulator - see tests/test_controller.py.

Named control.py, NOT controller.py: Webots puts a controller's own directory first on
sys.path, so a local controller.py shadows the Webots `controller` package and
`from controller import Robot` silently imports this file instead. Verified, see
docs/implementation_notes.md.

Sign conventions, all consistent with the robot frame (+X forward, +Y left):

    e_theta > 0   ball is right of the optical axis
    v_angular     = -KP_STEER * e_theta        (negative to turn right)
    left  wheel   = v_linear - v_angular       (speeds up to turn right)
    right wheel   = v_linear + v_angular

so a ball on the right drives the left wheel faster and the robot yaws toward it.
"""

import math
from dataclasses import dataclass
from enum import Enum

import config


class RobotState(Enum):
    """Behaviour states. The transitions are wired up in PROMPT 9; the proportional law
    below is stateless and does not consult them."""

    SEARCHING = "SEARCHING"
    TRACKING = "TRACKING"
    APPROACHING = "APPROACHING"
    STOPPED = "STOPPED"


@dataclass(frozen=True)
class DriveCommand:
    """Wheel velocities in rad/s, already clamped, plus the intermediates that produced
    them. Carrying v_linear and v_angular keeps the CSV log self-explaining in PROMPT 10
    without recomputing anything."""

    left_velocity: float
    right_velocity: float
    linear_command: float
    angular_command: float

    def as_tuple(self):
        return self.left_velocity, self.right_velocity


def clamp(value, low, high):
    """Constrain a value to [low, high]."""
    return max(low, min(high, value))


def distance_error(distance_m, target_m=None):
    """e_Z = measured distance - target. Positive means the ball is too far away."""
    target = config.TARGET_DISTANCE_M if target_m is None else target_m
    return float(distance_m - target)


def linear_command(error_z, gain=None, tolerance=None):
    """Forward command from the distance error, with a deadband around the target.

    Inside the deadband the result is exactly 0.0 rather than something small. That is
    what makes "arrived" a stable condition instead of a slow creep.
    """
    gain = config.KP_DIST if gain is None else gain
    tolerance = config.DISTANCE_TOLERANCE_M if tolerance is None else tolerance
    if abs(error_z) <= tolerance:
        return 0.0
    return float(gain * error_z)


def angular_command(error_theta, gain=None):
    """Steering command from the bearing error, in the sign convention above."""
    gain = config.KP_STEER if gain is None else gain
    return float(-gain * error_theta)


def apply_min_wheel_speed(speed, floor=None):
    """Lift a small non-zero command up to the stiction floor, preserving its sign.

    Exactly zero stays zero - the floor is for wheels that are supposed to be turning.
    """
    floor = config.MIN_WHEEL_SPEED if floor is None else floor
    if speed == 0.0 or abs(speed) >= floor:
        return float(speed)
    return float(math.copysign(floor, speed))


def differential_drive_mixer(v_linear, v_angular, max_speed=None, min_speed=None,
                             apply_floor=True):
    """Map (forward, angular) commands onto left and right wheel speeds.

        left  = v_linear - v_angular
        right = v_linear + v_angular

    both clamped to +/- max_speed. The stiction floor is applied only when the follower
    actually wants to advance (apply_floor and v_linear non-zero); a pure steering
    correction is left alone so that a vanishing bearing error produces a vanishing
    command rather than a 0.5 rad/s twitch.
    """
    max_speed = config.MAX_WHEEL_SPEED if max_speed is None else max_speed

    left = clamp(v_linear - v_angular, -max_speed, max_speed)
    right = clamp(v_linear + v_angular, -max_speed, max_speed)

    if apply_floor and v_linear != 0.0:
        left = clamp(apply_min_wheel_speed(left, min_speed), -max_speed, max_speed)
        right = clamp(apply_min_wheel_speed(right, min_speed), -max_speed, max_speed)

    return left, right


def compute_wheel_speeds(detection, distance_info):
    """The follower control law. Returns (left_speed, right_speed) in rad/s.

    Stops the motors whenever there is nothing trustworthy to follow: no detection, or a
    RangeBearing that failed its confidence or range gating. Fail-stop rather than
    fail-coast, because a stale command on a lost ball drives the robot into whatever it
    stopped being able to see.

    PROMPT 9 replaces the stop with a search behaviour; until then, stopping is correct.
    """
    return compute_drive_command(detection, distance_info).as_tuple()


def compute_drive_command(detection, distance_info):
    """compute_wheel_speeds with the intermediate commands kept, for logging."""
    if (detection is None or not detection.detected
            or distance_info is None or not distance_info.valid
            or distance_info.distance_m is None or distance_info.bearing_rad is None):
        return DriveCommand(0.0, 0.0, 0.0, 0.0)

    error_z = distance_error(distance_info.distance_m)
    v_linear = linear_command(error_z)
    v_angular = angular_command(distance_info.bearing_rad)
    left, right = differential_drive_mixer(v_linear, v_angular)
    return DriveCommand(left, right, v_linear, v_angular)


class FollowController:
    """Stateful policy: owns the FSM, the lost-ball timer and the last known ball side.

    State Definitions & Behaviors:
    - SEARCHING: Ball lost (no detection or confidence < min_confidence). Coast-decelerates
      for COAST_DURATION_S, then spins at SEARCH_SPIN_SPEED toward last_known_bearing.
    - TRACKING: Ball detected, but heading error |theta| > HEADING_ALIGN_RAD. Orienting
      towards ball center (linear command = 0).
    - APPROACHING: Ball detected and aligned (|theta| <= HEADING_ALIGN_RAD). Driving forward
      towards target distance (Z_target = 0.40 m).
    - STOPPED: Ball reached target distance. Motors locked in zero-state until ball moves
      beyond hysteresis boundary (STOP_HYSTERESIS_M).
    """

    def __init__(self, initial_state=RobotState.SEARCHING):
        self.state = initial_state
        self.last_known_bearing = 0.0
        self.time_since_lost = 0.0
        self.last_linear_command = 0.0
        self.last_angular_command = 0.0

    def step(self, detection, distance_info, delta_time_s=0.032):
        """Advance one control step and return a DriveCommand."""
        is_detected = (
            detection is not None
            and bool(detection.detected)
            and detection.confidence >= config.MIN_CONFIDENCE_THRESHOLD
            and distance_info is not None
            and distance_info.bearing_rad is not None
        )

        if is_detected:
            self.time_since_lost = 0.0
            self.last_known_bearing = distance_info.bearing_rad

            # Evaluate state transitions when DETECTED
            if self.state == RobotState.STOPPED:
                if distance_info.valid and distance_info.distance_m is not None:
                    error_z = distance_error(distance_info.distance_m)
                    # Hysteresis check: resume motion if distance error exceeds tolerance + hysteresis
                    if abs(error_z) > (config.DISTANCE_TOLERANCE_M + config.STOP_HYSTERESIS_M):
                        if abs(distance_info.bearing_rad) > config.HEADING_ALIGN_RAD:
                            self.state = RobotState.TRACKING
                        else:
                            self.state = RobotState.APPROACHING
                    # else remain in STOPPED
            else:
                if (distance_info.valid 
                        and distance_info.distance_m is not None
                        and abs(distance_error(distance_info.distance_m)) <= config.DISTANCE_TOLERANCE_M):
                    self.state = RobotState.STOPPED
                elif abs(distance_info.bearing_rad) > config.HEADING_ALIGN_RAD:
                    self.state = RobotState.TRACKING
                else:
                    self.state = RobotState.APPROACHING

            # Compute command based on current state
            if self.state == RobotState.STOPPED:
                cmd = DriveCommand(0.0, 0.0, 0.0, 0.0)
            elif self.state == RobotState.TRACKING:
                v_linear = 0.0
                v_angular = angular_command(distance_info.bearing_rad)
                left, right = differential_drive_mixer(v_linear, v_angular, apply_floor=False)
                cmd = DriveCommand(left, right, v_linear, v_angular)
            else:  # APPROACHING
                error_z = distance_error(distance_info.distance_m) if (distance_info.valid and distance_info.distance_m is not None) else 0.0
                v_linear = linear_command(error_z)
                v_angular = angular_command(distance_info.bearing_rad)
                left, right = differential_drive_mixer(v_linear, v_angular, apply_floor=True)
                cmd = DriveCommand(left, right, v_linear, v_angular)

            self.last_linear_command = cmd.linear_command
            self.last_angular_command = cmd.angular_command
            return cmd

        else:
            # Ball lost / not detected
            self.time_since_lost += max(0.0, float(delta_time_s))

            if self.time_since_lost <= config.COAST_DURATION_S:
                # Coasting phase: decelerate previous command smoothly
                decay = max(0.0, 1.0 - (self.time_since_lost / config.COAST_DURATION_S))
                v_linear = self.last_linear_command * decay
                v_angular = self.last_angular_command * decay
                left, right = differential_drive_mixer(v_linear, v_angular, apply_floor=False)
                self.state = RobotState.SEARCHING
                cmd = DriveCommand(left, right, v_linear, v_angular)
            else:
                # Full SEARCHING state: spin towards last_known_bearing
                self.state = RobotState.SEARCHING
                cmd = self.search_command()

            self.last_linear_command = cmd.linear_command
            self.last_angular_command = cmd.angular_command
            return cmd

    def search_command(self):
        """Rotate toward the last known ball side to reacquire the target."""
        speed = config.SEARCH_SPIN_SPEED
        # In SEARCHING state, rotate left if last_known_bearing >= 0, else rotate right.
        if self.last_known_bearing >= 0.0:
            v_angular = speed
        else:
            v_angular = -speed
        left, right = differential_drive_mixer(0.0, v_angular, apply_floor=False)
        return DriveCommand(left, right, 0.0, v_angular)

