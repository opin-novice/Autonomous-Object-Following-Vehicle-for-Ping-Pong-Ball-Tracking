"""PROMPT 3 verification: do the robot and ball exist, is the physics sane, and is the
ball actually visible and separable from the background?

Checks, in order:
  1. both nodes resolve, and the robot settles level
  2. the ball is at rest and stays at rest (repeatable initial configuration)
  3. the ball falls correctly when released from a height (physics is live)
  4. the camera sees it, and an HSV threshold on the configured bounds isolates it
  5. the measured blob matches the pinhole prediction from the supervisor geometry

The HSV work here is throwaway verification, deliberately kept out of vision.py - the
real detector is PROMPT 5. The BGRA to BGR conversion is likewise inlined rather than
calling vision.webots_image_to_bgr, which is still a PROMPT 4 stub.

Output: results/logs/world_check.txt (Webots stdout is not pipeable on Windows).
"""

import math
import os
import sys
import traceback

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.normpath(os.path.join(_HERE, "..", "..", ".."))
_LOG_DIR = os.path.join(_PROJECT_ROOT, "results", "logs")
_TRACE = os.path.join(_LOG_DIR, "world_check_trace.txt")
REPORT_PATH = os.path.join(_LOG_DIR, "world_check.txt")


def _mark(text):
    os.makedirs(_LOG_DIR, exist_ok=True)
    with open(_TRACE, "a", encoding="utf-8") as handle:
        handle.write(text + "\n")


if os.path.exists(_TRACE):
    os.remove(_TRACE)
_mark("00 controller entered")

sys.path.insert(0, os.path.join(_PROJECT_ROOT, "webots", "controllers", "ball_follower"))
import config
import vision
from ball_follower import setup_devices
_mark("01 project modules imported")

import cv2
import numpy as np
from controller import Supervisor
_mark("02 cv2 / numpy / webots imported")

SETTLE_SECONDS = 2.0
REST_WATCH_SECONDS = 5.0
DROP_HEIGHT = 0.30


def main():
    robot = Supervisor()
    timestep = config.TIME_STEP_MS
    camera, left_motor, right_motor = setup_devices(robot)
    left_motor.setVelocity(0.0)
    right_motor.setVelocity(0.0)
    _mark("03 devices ready")

    robot_node = robot.getSelf()
    ball_node = robot.getFromDef("BALL")
    floor_node = robot.getFromDef("FLOOR")
    walls = [robot.getFromDef(n) for n in
             ("WALL_NORTH", "WALL_SOUTH", "WALL_EAST", "WALL_WEST")]
    _mark("04 nodes resolved")

    lines = []
    checks = []

    def step(seconds):
        for _ in range(int(round(seconds * 1000.0 / timestep))):
            if robot.step(timestep) == -1:
                break

    lines.append("=== scene inventory ===")
    lines.append("robot node   : %s" % ("found" if robot_node else "MISSING"))
    lines.append("ball node    : %s" % ("found" if ball_node else "MISSING"))
    lines.append("floor node   : %s" % ("found" if floor_node else "MISSING"))
    lines.append("walls found  : %d of 4" % sum(1 for w in walls if w))
    lines.append("")
    checks.append(("robot node exists", robot_node is not None))
    checks.append(("ball node exists", ball_node is not None))
    checks.append(("floor node exists", floor_node is not None))
    checks.append(("all four walls exist", all(w is not None for w in walls)))

    step(SETTLE_SECONDS)
    _mark("05 settled")

    rpos = list(robot_node.getPosition())
    m = robot_node.getOrientation()
    pitch = math.degrees(math.asin(max(-1.0, min(1.0, m[6]))))
    bpos = list(ball_node.getPosition())

    cam_world = [
        rpos[0] + m[0] * 0.100 + m[2] * 0.085,
        rpos[1] + m[3] * 0.100 + m[5] * 0.085,
        rpos[2] + m[6] * 0.100 + m[8] * 0.085,
    ]
    dx = bpos[0] - cam_world[0]
    dy = bpos[1] - cam_world[1]
    dz = bpos[2] - cam_world[2]
    ground_range = math.hypot(dx, dy)
    slant_range = math.sqrt(dx * dx + dy * dy + dz * dz)

    lines.append("=== resting geometry ===")
    lines.append("robot position   : x=%+.4f y=%+.4f z=%+.4f" % tuple(rpos))
    lines.append("robot pitch      : %+.3f deg" % pitch)
    lines.append("camera position  : x=%+.4f y=%+.4f z=%+.4f" % tuple(cam_world))
    lines.append("ball position    : x=%+.4f y=%+.4f z=%+.4f" % tuple(bpos))
    lines.append("camera-to-ball   : %.4f m horizontal, %.4f m slant"
                 % (ground_range, slant_range))
    lines.append("ball below axis  : %.3f deg" % math.degrees(math.atan2(-dz, ground_range)))
    lines.append("")
    checks.append(("ball rests on floor (z within 1 mm of radius)", abs(bpos[2] - 0.020) < 0.001))
    checks.append(("camera-to-ball inside the 1.0-1.5 m band", 1.0 <= ground_range <= 1.5))
    checks.append(("robot level (pitch under 1 deg)", abs(pitch) < 1.0))

    before = list(ball_node.getPosition())
    step(REST_WATCH_SECONDS)
    after = list(ball_node.getPosition())
    creep = math.dist(before, after)
    lines.append("=== initial-configuration stability ===")
    lines.append("ball drift over %.1f s idle : %.6f m" % (REST_WATCH_SECONDS, creep))
    lines.append("")
    checks.append(("ball does not creep (under 1 mm in 5 s)", creep < 0.001))
    _mark("06 rest check done")

    translation_field = ball_node.getField("translation")
    original = list(translation_field.getSFVec3f())
    translation_field.setSFVec3f([original[0], original[1], DROP_HEIGHT])
    ball_node.resetPhysics()
    step(1.5)
    landed = list(ball_node.getPosition())
    lines.append("=== physics check: drop the ball ===")
    lines.append("released from z  : %.3f m" % DROP_HEIGHT)
    lines.append("settled at z     : %.4f m (expected 0.0200)" % landed[2])
    lines.append("lateral wander   : %.4f m"
                 % math.hypot(landed[0] - original[0], landed[1] - original[1]))
    lines.append("")
    checks.append(("ball fell and came to rest on the floor", abs(landed[2] - 0.020) < 0.004))

    translation_field.setSFVec3f(original)
    ball_node.resetPhysics()
    step(1.0)
    restored = list(ball_node.getPosition())
    lines.append("restored to      : x=%+.4f y=%+.4f z=%+.4f" % tuple(restored))
    lines.append("")
    checks.append(("initial configuration restorable", math.dist(restored, original) < 0.002))
    _mark("07 physics check done")

    step(0.5)
    width, height = camera.getWidth(), camera.getHeight()
    raw = camera.getImage()
    frame = np.frombuffer(raw, np.uint8).reshape((height, width, 4))
    bgr = frame[:, :, :3]

    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, np.array(config.HSV_LOWER, np.uint8),
                       np.array(config.HSV_UPPER, np.uint8))
    orange_pixels = int(cv2.countNonZero(mask))

    lines.append("=== camera and colour separability ===")
    lines.append("image            : %dx%d, %d bytes" % (width, height, len(raw)))
    lines.append("HSV window       : %s .. %s" % (config.HSV_LOWER, config.HSV_UPPER))
    lines.append("orange pixels    : %d" % orange_pixels)
    checks.append(("camera returns a full frame", len(raw) == width * height * 4))
    checks.append(("ball visible to the HSV window", orange_pixels > 20))

    if orange_pixels > 0:
        ys, xs = np.nonzero(mask)
        cx, cy = float(xs.mean()), float(ys.mean())
        measured_radius = math.sqrt(orange_pixels / math.pi)
        predicted_radius = config.FOCAL_LENGTH_PX * config.BALL_DIAMETER_M / (2.0 * slant_range)
        predicted_cx = config.IMAGE_CENTER_X
        predicted_cy = config.IMAGE_CENTER_Y + config.FOCAL_LENGTH_PX * (-dz) / ground_range

        lines.append("blob centroid    : u=%.1f v=%.1f" % (cx, cy))
        lines.append("predicted        : u=%.1f v=%.1f" % (predicted_cx, predicted_cy))
        lines.append("blob radius      : %.2f px" % measured_radius)
        lines.append("predicted radius : %.2f px" % predicted_radius)
        lines.append("radius error     : %+.1f pct"
                     % (100.0 * (measured_radius - predicted_radius) / predicted_radius))

        blob_mask = np.zeros_like(mask)
        cv2.circle(blob_mask, (int(round(cx)), int(round(cy))),
                   int(math.ceil(measured_radius)) + 6, 255, -1)
        stray = int(cv2.countNonZero(cv2.bitwise_and(mask, cv2.bitwise_not(blob_mask))))
        lines.append("stray orange px  : %d (outside the ball blob)" % stray)

        checks.append(("centroid within 12 px of prediction",
                       abs(cx - predicted_cx) < 12.0 and abs(cy - predicted_cy) < 12.0))
        checks.append(("apparent radius within 25 pct of pinhole prediction",
                       abs(measured_radius - predicted_radius) < 0.25 * predicted_radius))
        checks.append(("background produces no stray orange", stray == 0))

        plot_dir = os.path.join(_PROJECT_ROOT, "results", "plots")
        os.makedirs(plot_dir, exist_ok=True)
        cv2.imwrite(os.path.join(plot_dir, "world_check_view.png"), bgr)
        cv2.imwrite(os.path.join(plot_dir, "world_check_mask.png"), mask)
        lines.append("saved            : results/plots/world_check_view.png and _mask.png")

    lines.append("")
    _mark("08 vision check done")

    # ---- 6. detection vs distance ------------------------------------------
    # Converts the standing "is a 40 mm ball big enough?" question into measurements.
    # The ball is teleported along the camera axis; the arena wall at x=2.025 caps the
    # sweep at 2.8 m of range.
    lines.append("=== detection vs distance sweep ===")
    lines.append("  range_m  mask_px  contArea  circ   radius  predicted  conf   detected")
    far_ok = True
    fixture_dir = os.path.join(_PROJECT_ROOT, "tests", "fixtures")
    os.makedirs(fixture_dir, exist_ok=True)
    for target in (0.4, 0.6, 0.8, 1.0, 1.2, 1.5, 2.0, 2.5, 2.8):
        translation_field.setSFVec3f([cam_world[0] + target, original[1], original[2]])
        ball_node.resetPhysics()
        step(0.4)
        sweep_frame = vision.webots_image_to_bgr(camera.getImage(), width, height)
        sweep_mask = vision.build_color_mask(sweep_frame)
        count = int(cv2.countNonZero(sweep_mask))

        # circularity of the largest contour regardless of whether it passes, so the
        # threshold can be judged against what the optics actually deliver
        contours, _ = cv2.findContours(sweep_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            biggest = max(contours, key=cv2.contourArea)
            cont_area = float(cv2.contourArea(biggest))
            circ = vision.circularity(cont_area, float(cv2.arcLength(biggest, True)))
        else:
            cont_area = circ = 0.0

        found = vision.detect_ball(sweep_frame, mask=sweep_mask)
        pred = config.FOCAL_LENGTH_PX * config.BALL_DIAMETER_M / (2.0 * target)
        lines.append("  %6.2f  %7d  %8.1f  %5.3f  %6.2f  %9.2f  %5.3f  %s"
                     % (target, count, cont_area, circ, found.radius, pred,
                        found.confidence, "yes" if found.detected else "NO"))
        cv2.imwrite(os.path.join(fixture_dir, "range_%03dcm.png" % int(round(target * 100))),
                    sweep_frame)
        if abs(target - 1.5) < 1e-6 and not found.detected:
            far_ok = False

    translation_field.setSFVec3f(original)
    ball_node.resetPhysics()
    step(0.5)
    lines.append("")
    checks.append(("still detectable at the far end of the chosen band (1.5 m)", far_ok))
    _mark("09 distance sweep done")

    lines.append("=== verdict ===")
    for label, ok in checks:
        lines.append("[%s] %s" % ("PASS" if ok else "FAIL", label))
    lines.append("")
    lines.append("RESULT: %s" % ("ALL PASS" if all(ok for _, ok in checks) else "FAILURES PRESENT"))

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
