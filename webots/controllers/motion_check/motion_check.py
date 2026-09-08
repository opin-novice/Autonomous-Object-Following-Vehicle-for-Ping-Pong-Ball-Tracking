"""Phase 1 smoke test: does PingPongFollowerRobot actually drive and rotate?

Runs two open-loop manoeuvres and measures the result with the supervisor, comparing
against the differential-drive prediction from the PROTO geometry. This exercises the
real setup_devices() from the ball_follower controller, so a device-naming mistake shows
up here rather than in Phase 4.

Webots on Windows is a GUI-subsystem app whose stdout cannot be piped, so the verdict
goes to results/logs/motion_check.txt and progress markers to motion_check_trace.txt.
"""

import math
import os
import sys
import traceback

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.normpath(os.path.join(_HERE, "..", "..", ".."))
_LOG_DIR = os.path.join(_PROJECT_ROOT, "results", "logs")
_TRACE = os.path.join(_LOG_DIR, "motion_check_trace.txt")
REPORT_PATH = os.path.join(_LOG_DIR, "motion_check.txt")


def _mark(text):
    """Append a progress marker, so a failure shows how far the controller got."""
    os.makedirs(_LOG_DIR, exist_ok=True)
    with open(_TRACE, "a", encoding="utf-8") as handle:
        handle.write(text + "\n")


if os.path.exists(_TRACE):
    os.remove(_TRACE)
_mark("00 controller entered")
sys.path.insert(0, os.path.join(_PROJECT_ROOT, "webots", "controllers", "ball_follower"))

import config
_mark("01 config imported")
from ball_follower import setup_devices
_mark("02 ball_follower imported")
from controller import Supervisor
_mark("03 webots api imported")

DRIVE_WHEEL_RAD_S = 4.0
DRIVE_SECONDS = 3.0
TURN_WHEEL_RAD_S = 1.5
TURN_SECONDS = 3.0
SETTLE_SECONDS = 0.5


def yaw_of(node):
    """Heading about +Z, from the rotation matrix.

    getOrientation() is row-major 3x3; the robot's forward axis (+X local) maps to world
    (m[0], m[3], m[6]), so heading is atan2 of its Y and X components.
    """
    m = node.getOrientation()
    return math.atan2(m[3], m[0])


def main():
    robot = Supervisor()
    _mark("04 supervisor constructed")
    timestep = config.TIME_STEP_MS
    camera, left_motor, right_motor = setup_devices(robot)
    _mark("05 devices set up")
    self_node = robot.getSelf()
    _mark("06 self node acquired")

    lines = []

    def run(seconds, left_velocity, right_velocity):
        left_motor.setVelocity(left_velocity)
        right_motor.setVelocity(right_velocity)
        steps = int(round(seconds * 1000.0 / timestep))
        for _ in range(steps):
            if robot.step(timestep) == -1:
                break
        return steps * timestep / 1000.0

    lines.append("=== device check ===")
    lines.append("camera             : %s  %dx%d  fov=%.3f rad"
                 % (camera.getName(), camera.getWidth(), camera.getHeight(), camera.getFov()))
    lines.append("left motor         : %s  maxVelocity=%.2f rad/s"
                 % (left_motor.getName(), left_motor.getMaxVelocity()))
    lines.append("right motor        : %s  maxVelocity=%.2f rad/s"
                 % (right_motor.getName(), right_motor.getMaxVelocity()))
    lines.append("config wheel radius: %.4f m" % config.WHEEL_RADIUS_M)
    lines.append("config wheel sep   : %.4f m" % config.WHEEL_SEPARATION_M)
    lines.append("")

    run(SETTLE_SECONDS, 0.0, 0.0)
    _mark("07 settled on floor")

    settled = list(self_node.getPosition())
    m = self_node.getOrientation()
    pitch = math.degrees(math.asin(max(-1.0, min(1.0, m[6]))))
    roll = math.degrees(math.asin(max(-1.0, min(1.0, m[7]))))
    cam_height = settled[2] + m[6] * 0.100 + m[8] * 0.085

    lines.append("=== resting pose after settle ===")
    lines.append("origin z           : %+.4f m  (nominal 0.0000)" % settled[2])
    lines.append("pitch              : %+.3f deg (+ = nose up)" % pitch)
    lines.append("roll               : %+.3f deg" % roll)
    lines.append("camera world height: %.4f m  (nominal 0.0850)" % cam_height)
    lines.append("")

    start_pos = list(self_node.getPosition())
    start_yaw = yaw_of(self_node)
    elapsed = run(DRIVE_SECONDS, DRIVE_WHEEL_RAD_S, DRIVE_WHEEL_RAD_S)
    run(SETTLE_SECONDS, 0.0, 0.0)
    end_pos = list(self_node.getPosition())
    end_yaw = yaw_of(self_node)

    dx = end_pos[0] - start_pos[0]
    dy = end_pos[1] - start_pos[1]
    travelled = math.hypot(dx, dy)
    expected_travel = config.WHEEL_RADIUS_M * DRIVE_WHEEL_RAD_S * elapsed
    heading_drift = math.degrees(abs(end_yaw - start_yaw))

    lines.append("=== manoeuvre 1: drive forward ===")
    lines.append("both wheels        : %.2f rad/s for %.2f s" % (DRIVE_WHEEL_RAD_S, elapsed))
    lines.append("start position     : x=%.4f y=%.4f z=%.4f" % tuple(start_pos))
    lines.append("end position       : x=%.4f y=%.4f z=%.4f" % tuple(end_pos))
    lines.append("distance travelled : %.4f m" % travelled)
    lines.append("expected (R*w*t)   : %.4f m" % expected_travel)
    lines.append("slip / error       : %+.1f %%"
                 % (100.0 * (travelled - expected_travel) / expected_travel))
    lines.append("forward dx         : %+.4f m    lateral dy: %+.4f m" % (dx, dy))
    lines.append("heading drift      : %.2f deg" % heading_drift)
    lines.append("")
    _mark("08 drive manoeuvre done")

    start_yaw = yaw_of(self_node)
    start_pos = list(self_node.getPosition())
    elapsed = run(TURN_SECONDS, -TURN_WHEEL_RAD_S, TURN_WHEEL_RAD_S)
    run(SETTLE_SECONDS, 0.0, 0.0)
    end_yaw = yaw_of(self_node)
    end_pos = list(self_node.getPosition())

    turned = end_yaw - start_yaw
    while turned > math.pi:
        turned -= 2.0 * math.pi
    while turned < -math.pi:
        turned += 2.0 * math.pi
    expected_rate = (config.WHEEL_RADIUS_M * (2.0 * TURN_WHEEL_RAD_S)
                     / config.WHEEL_SEPARATION_M)
    expected_turn = expected_rate * elapsed
    drift = math.hypot(end_pos[0] - start_pos[0], end_pos[1] - start_pos[1])

    lines.append("=== manoeuvre 2: rotate in place ===")
    lines.append("wheels             : left %.2f / right %+.2f rad/s for %.2f s"
                 % (-TURN_WHEEL_RAD_S, TURN_WHEEL_RAD_S, elapsed))
    lines.append("yaw change         : %+.2f deg" % math.degrees(turned))
    lines.append("expected           : %+.2f deg" % math.degrees(expected_turn))
    lines.append("error              : %+.1f %%"
                 % (100.0 * (abs(turned) - expected_turn) / expected_turn))
    lines.append("centre drift       : %.4f m" % drift)
    lines.append("")
    _mark("09 turn manoeuvre done")

    checks = [
        ("robot drove forward", travelled > 0.05),
        ("travel within 25%% of prediction",
         abs(travelled - expected_travel) < 0.25 * expected_travel),
        ("drove roughly straight (drift < 10 deg)", heading_drift < 10.0),
        ("robot rotated", abs(math.degrees(turned)) > 10.0),
        ("rotation within 30%% of prediction",
         abs(abs(turned) - expected_turn) < 0.30 * expected_turn),
        ("rotated near in place (drift < 0.10 m)", drift < 0.10),
        ("camera resolution matches config",
         camera.getWidth() == config.IMAGE_WIDTH and camera.getHeight() == config.IMAGE_HEIGHT),
    ]
    lines.append("=== verdict ===")
    for label, ok in checks:
        lines.append("[%s] %s" % ("PASS" if ok else "FAIL", label % ()))
    lines.append("")
    lines.append("RESULT: %s" % ("ALL PASS" if all(ok for _, ok in checks) else "FAILURES PRESENT"))

    os.makedirs(_LOG_DIR, exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
    _mark("10 report written")

    robot.simulationQuit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        _mark("!! EXCEPTION\n" + traceback.format_exc())
        raise
