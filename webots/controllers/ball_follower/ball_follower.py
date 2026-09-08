"""Webots entry point for the ball-following controller.

The only module that imports the Webots API. Its job is device setup and the main
simulation loop; the actual vision and control work belongs in vision.py and control.py.

Current scope (Phase 4 / PROMPT 8): the full loop. Acquire, detect, range, compute wheel
speeds with the proportional follower, drive the motors, render the overlay. The ball-lost
state machine is PROMPT 9; until then a lost ball simply stops the robot.

Webots requires this file to share the name of its parent directory
(controllers/ball_follower/ball_follower.py).

Environment overrides, used by automated headless runs:
    BALL_FOLLOWER_HEADLESS      any value  - never open the cv2 window
    BALL_FOLLOWER_RUN_SECONDS   float      - stop the loop after this much sim time
    BALL_FOLLOWER_SELFTEST      any value  - rotate slowly during diagnostics
    BALL_FOLLOWER_TRUTH_LOG     path       - construct a Supervisor instead of a Robot and
                                             log supervisor ground truth alongside the
                                             estimate, for closed-loop verification
"""

import math
import os
import time

import config
import control
import logger
import vision

try:
    from controller import Supervisor
    HAS_SUPERVISOR = True
except ImportError:
    HAS_SUPERVISOR = False


def setup_devices(robot):
    """Fetch the camera and both wheel motors, and put the motors into velocity mode.

    Returns (camera, left_motor, right_motor).

    A Webots RotationalMotor is position-controlled by default. Setting the target
    position to infinity is what switches it to velocity control; without that,
    setVelocity() only caps the speed of a position move and the robot will not drive.

    Raises RuntimeError naming the device if anything is missing, because Webots
    otherwise returns None here and fails much later with an opaque AttributeError.
    """
    camera = robot.getDevice(config.CAMERA_NAME)
    if camera is None:
        raise RuntimeError("camera device %r not found on this robot" % config.CAMERA_NAME)
    camera.enable(config.TIME_STEP_MS)

    left_motor = robot.getDevice(config.LEFT_MOTOR_NAME)
    right_motor = robot.getDevice(config.RIGHT_MOTOR_NAME)
    for name, motor in ((config.LEFT_MOTOR_NAME, left_motor),
                        (config.RIGHT_MOTOR_NAME, right_motor)):
        if motor is None:
            raise RuntimeError("motor device %r not found on this robot" % name)
        motor.setPosition(float("inf"))
        motor.setVelocity(0.0)

    return camera, left_motor, right_motor


def _working_set_bytes():
    """Current process working set in bytes, for the leak check. Windows only; -1 else.

    GetCurrentProcess returns a HANDLE. Without an explicit restype ctypes assumes int and
    truncates it on 64-bit, which makes the call fail silently - that is exactly how the
    first version of this reported "unavailable".
    """
    try:
        import ctypes
        from ctypes import wintypes

        class _Counters(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        kernel32 = ctypes.WinDLL("kernel32")
        kernel32.GetCurrentProcess.restype = ctypes.c_void_p
        try:
            probe = ctypes.WinDLL("psapi").GetProcessMemoryInfo
        except OSError:
            probe = kernel32.K32GetProcessMemoryInfo
        probe.argtypes = [ctypes.c_void_p, ctypes.POINTER(_Counters), wintypes.DWORD]
        probe.restype = wintypes.BOOL

        counters = _Counters()
        counters.cb = ctypes.sizeof(_Counters)
        if probe(kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
            return int(counters.WorkingSetSize)
    except Exception:
        pass
    return -1


def _project_path(relative):
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(here, "..", "..", "..", relative))


def _write_camera_report(camera, samples, convert_times, detect_times, overlay_times,
                         detections, memory_start, memory_mid, memory_end, wall_seconds,
                         window_status):
    """Record what the acquisition pipeline actually produced. Webots stdout is not
    pipeable on Windows, so this file is the only machine-readable evidence."""
    import numpy as np

    first = samples[0]
    lines = []
    lines.append("=== camera device ===")
    lines.append("name              : %s" % camera.getName())
    lines.append("resolution        : %dx%d" % (camera.getWidth(), camera.getHeight()))
    lines.append("horizontal FOV    : %.4f rad" % camera.getFov())
    lines.append("sampling period   : %d ms (controller timestep %d ms)"
                 % (camera.getSamplingPeriod(), config.TIME_STEP_MS))
    lines.append("")

    lines.append("=== converted frame ===")
    lines.append("raw buffer        : %d bytes (%dx%dx4 BGRA)"
                 % (first["raw_len"], camera.getWidth(), camera.getHeight(), ))
    lines.append("array shape       : %s" % (first["shape"],))
    lines.append("dtype             : %s" % first["dtype"])
    lines.append("C-contiguous      : %s" % first["contiguous"])
    lines.append("writeable         : %s" % first["writeable"])
    lines.append("channel means BGR : B=%.1f G=%.1f R=%.1f" % first["means"])
    lines.append("")

    lines.append("=== channel-order proof ===")
    lines.append("brightest orange pixel BGR : B=%d G=%d R=%d" % first["orange_bgr"])
    lines.append("same pixel as HSV hue      : %d  (orange is 5-20; RGBA misread gives ~110)"
                 % first["orange_hue"])
    lines.append("")

    convert_ms = [t * 1000.0 for t in convert_times]
    convert_ms.sort()
    lines.append("=== throughput over %d frames ===" % len(convert_times))
    lines.append("conversion mean   : %.3f ms/frame" % (sum(convert_ms) / len(convert_ms)))
    lines.append("conversion median : %.3f ms/frame" % convert_ms[len(convert_ms) // 2])
    lines.append("conversion max    : %.3f ms/frame" % convert_ms[-1])
    lines.append("wall clock        : %.2f s for %d frames (%.1f frames/s)"
                 % (wall_seconds, len(convert_times), len(convert_times) / max(wall_seconds, 1e-9)))
    lines.append("sim time budget   : %.1f ms/frame at timestep %d ms"
                 % (config.TIME_STEP_MS, config.TIME_STEP_MS))
    lines.append("")

    lines.append("=== detection over the diagnostic window ===")
    hits = [s for s in detections if s["detected"]]
    lines.append("frames evaluated  : %d" % len(detections))
    lines.append("detection rate    : %.1f %% (%d/%d)"
                 % (100.0 * len(hits) / max(len(detections), 1), len(hits), len(detections)))
    if hits:
        def spread(key):
            values = [h[key] for h in hits]
            return min(values), sum(values) / len(values), max(values)
        lines.append("center_x  min/mean/max : %.2f / %.2f / %.2f" % spread("center_x"))
        lines.append("center_y  min/mean/max : %.2f / %.2f / %.2f" % spread("center_y"))
        lines.append("radius    min/mean/max : %.2f / %.2f / %.2f" % spread("radius"))
        lines.append("area      min/mean/max : %.1f / %.1f / %.1f" % spread("area"))
        lines.append("conf      min/mean/max : %.3f / %.3f / %.3f" % spread("confidence"))
    lines.append("detect cost       : %.3f ms/frame mean"
                 % (1000.0 * sum(detect_times) / max(len(detect_times), 1)))
    lines.append("overlay cost      : %.3f ms/frame mean"
                 % (1000.0 * sum(overlay_times) / max(len(overlay_times), 1)))
    if hits:
        valid = [h for h in hits if h["valid"]]
        lines.append("range valid       : %d/%d frames" % (len(valid), len(hits)))
        if valid:
            distances = [h["distance_m"] for h in valid]
            bearings = [h["bearing_deg"] for h in valid]
            lines.append("distance  min/mean/max : %.4f / %.4f / %.4f m"
                         % (min(distances), sum(distances) / len(distances), max(distances)))
            lines.append("bearing   min/mean/max : %+.3f / %+.3f / %+.3f deg"
                         % (min(bearings), sum(bearings) / len(bearings), max(bearings)))
            truth = 1.2018  # supervisor slant range at the start pose
            mean_d = sum(distances) / len(distances)
            lines.append("vs supervisor truth    : %.4f m -> %+.2f %%"
                         % (truth, 100.0 * (mean_d - truth) / truth))
    lines.append("")

    lines.append("=== debug view ===")
    lines.append("cv2 window        : %s" % window_status)
    lines.append("")

    lines.append("=== memory ===")
    half = len(convert_times) // 2
    if memory_start > 0:
        first_half = (memory_mid - memory_start) / 1048576.0
        second_half = (memory_end - memory_mid) / 1048576.0
        lines.append("working set start : %.2f MB" % (memory_start / 1048576.0))
        lines.append("working set mid   : %.2f MB" % (memory_mid / 1048576.0))
        lines.append("working set end   : %.2f MB" % (memory_end / 1048576.0))
        lines.append("growth 1st half   : %+.3f MB over %d frames" % (first_half, half))
        lines.append("growth 2nd half   : %+.3f MB over %d frames"
                     % (second_half, len(convert_times) - half))
        lines.append("")
        lines.append("A one-time allocation (opening the highgui window, warming numpy and")
        lines.append("OpenCV) lands entirely in the first half. A real per-frame leak would")
        lines.append("grow both halves about equally, so the second half is the leak test.")
    else:
        lines.append("unavailable on this platform")
    lines.append("")

    changed = [s["diff_px"] for s in samples[1:]]
    lines.append("=== frame freshness ===")
    lines.append("pixels changed between sampled frames : %s"
                 % (", ".join(str(c) for c in changed) if changed else "n/a"))
    lines.append("")
    checks = [
        ("buffer length matches width*height*4",
         first["raw_len"] == camera.getWidth() * camera.getHeight() * 4),
        ("converted shape is (480, 640, 3)", first["shape"] == (480, 640, 3)),
        ("dtype is uint8", first["dtype"] == "uint8"),
        ("array is writeable (overlay-safe)", first["writeable"]),
        ("array is C-contiguous", first["contiguous"]),
        ("channel order is BGR, not RGB", 5 <= first["orange_hue"] <= 20),
        ("frame is not blank", first["means"][0] > 5 or first["means"][1] > 5),
        ("frames update between steps while the view changes",
         (any(c > 0 for c in changed) if os.environ.get("BALL_FOLLOWER_SELFTEST") else True)),
        ("conversion cost under 2 ms/frame", sum(convert_ms) / len(convert_ms) < 2.0),
        ("debug window opened when requested", not window_status.startswith("failed")),
        ("ball detected in every frame at the start pose",
         len(hits) == len(detections) and len(detections) > 0),
        ("detection cost under 5 ms/frame",
         (sum(detect_times) / max(len(detect_times), 1)) < 0.005),
        ("range valid in every detected frame",
         all(h["valid"] for h in hits) if hits else False),
        ("start-pose distance within 1.5 pct of supervisor truth",
         (abs((sum(h["distance_m"] for h in hits[:5] if h["valid"])
               / max(len([h for h in hits[:5] if h["valid"]]), 1)) - 1.2018) / 1.2018 <= 0.015)
         if any(h["valid"] for h in hits[:5]) else False),
        ("overlay cost under 5 ms/frame",
         (sum(overlay_times) / max(len(overlay_times), 1)) < 0.005),
        ("full pipeline fits the 32 ms timestep",
         1000.0 * (sum(convert_times) + sum(detect_times) + sum(overlay_times))
         / max(len(convert_times), 1) < config.TIME_STEP_MS),
    ]
    if memory_start > 0:
        checks.append(("no per-frame memory leak (2nd-half growth < 1 MB)",
                       (memory_end - memory_mid) < 1048576))

    lines.append("=== verdict ===")
    for label, ok in checks:
        lines.append("[%s] %s" % ("PASS" if ok else "FAIL", label))
    lines.append("")
    lines.append("RESULT: %s" % ("ALL PASS" if all(ok for _, ok in checks) else "FAILURES PRESENT"))

    path = _project_path(config.CAMERA_CHECK_LOG)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def main():
    """Construct the Robot, set up devices, and run the camera acquisition loop."""
    import cv2
    import numpy as np

    truth_path = os.environ.get("BALL_FOLLOWER_TRUTH_LOG")
    if truth_path:
        # Supervisor subclasses Robot, so every device call below is unchanged. Used only
        # to record ground truth for verification; the control law never reads it.
        from controller import Supervisor as _RobotClass
    else:
        from controller import Robot as _RobotClass

    robot = _RobotClass()
    timestep = config.TIME_STEP_MS
    camera, left_motor, right_motor = setup_devices(robot)

    # Start movie recording if enabled (Supervisor API required)
    record_video = os.environ.get('BALL_FOLLOWER_RECORD_VIDEO', '')
    if record_video and hasattr(robot, 'movieStartRecording'):
        os.makedirs('results/videos', exist_ok=True)
        video_path = record_video if '/' in record_video or ':' in record_video else f'results/videos/{record_video}'
        try:
            robot.movieStartRecording(video_path)
        except Exception:
            pass

    left_motor.setVelocity(0.0)
    right_motor.setVelocity(0.0)

    truth_rows = []
    ball_node = robot.getFromDef("BALL") if truth_path else None
    self_node = robot.getSelf() if truth_path else None

    # CSV logger for full session record
    csv_logger = None
    if config.LOG_ENABLED:
        # Compute path relative to the controller dir: webots/controllers/ball_follower
        # Results are at <project root>/results/logs, which is ../../results/logs
        controller_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(controller_dir)))
        log_path = os.path.join(project_root, config.LOG_PATH)
        csv_logger = logger.CSVLogger(log_path)

    show_window = config.DEBUG_WINDOW_ENABLED and not os.environ.get("BALL_FOLLOWER_HEADLESS")
    # A static scene legitimately yields byte-identical frames, so "is the frame fresh?"
    # can only be tested while something moves. Selftest turns slowly during diagnostics.
    selftest = bool(os.environ.get("BALL_FOLLOWER_SELFTEST"))
    window_status = ["disabled by config or BALL_FOLLOWER_HEADLESS"]
    run_budget = os.environ.get("BALL_FOLLOWER_RUN_SECONDS")
    run_budget = float(run_budget) if run_budget else None

    samples = []
    previous_frame = None
    convert_times = []
    detect_times = []
    overlay_times = []
    detections = []
    live_fps = 0.0
    lost_frame_saved = [False]
    last_command = (0.0, 0.0)
    last_frame_clock = None
    memory_start = memory_mid = memory_end = -1
    wall_start = None
    frame_index = 0
    reported = False

    while robot.step(timestep) != -1:
        raw = camera.getImage()
        if raw is None:
            # Camera has no image yet on the very first steps; skip rather than crash.
            continue

        sim_time_s = frame_index * timestep / 1000.0

        started = time.perf_counter()
        frame = vision.webots_image_to_bgr(raw, camera.getWidth(), camera.getHeight())
        elapsed = time.perf_counter() - started

        detect_started = time.perf_counter()
        detection = vision.detect_ball(frame)
        detect_elapsed = time.perf_counter() - detect_started

        ranging = vision.estimate_distance_and_bearing(detection)
        distance_m = ranging.distance_m

        # Compute wheel speeds using proportional follower
        command = control.compute_drive_command(detection, ranging)
        left_speed, right_speed = command.left_velocity, command.right_velocity
        if selftest and not reported:
            left_speed, right_speed = -0.5, 0.5

        # Log this step to CSV
        if csv_logger is not None and frame_index % config.LOG_EVERY_N_STEPS == 0:
            row = logger.format_row(sim_time_s, detection, ranging, command, "IDLE")
            csv_logger.write_row(row)
            if frame_index % 300 == 0:
                csv_logger.flush()

        overlay_started = time.perf_counter()
        annotated = vision.draw_debug_overlay(
            frame, detection, distance_m=distance_m, state="FOLLOWING",
            left_velocity=left_speed, right_velocity=right_speed, fps=live_fps)
        overlay_elapsed = time.perf_counter() - overlay_started

        if frame_index == 0:
            memory_start = _working_set_bytes()
            wall_start = time.perf_counter()

        if not reported and frame_index < config.CAMERA_DIAGNOSTIC_FRAMES:
            convert_times.append(elapsed)
            detect_times.append(detect_elapsed)
            overlay_times.append(overlay_elapsed)
            record = detection.as_dict()
            record.update(ranging.as_dict())
            detections.append(record)
            if len(samples) < 8 and frame_index % 10 == 0:
                hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
                # brightest saturated pixel: the ball, whatever the channel order is
                score = hsv[:, :, 1].astype(np.int32) + hsv[:, :, 2].astype(np.int32)
                index = int(np.argmax(score))
                row, col = divmod(index, frame.shape[1])
                samples.append({
                    "raw_len": len(raw),
                    "shape": tuple(frame.shape),
                    "dtype": str(frame.dtype),
                    "contiguous": bool(frame.flags["C_CONTIGUOUS"]),
                    "writeable": bool(frame.flags["WRITEABLE"]),
                    "means": tuple(float(v) for v in frame.reshape(-1, 3).mean(axis=0)),
                    "orange_bgr": tuple(int(v) for v in frame[row, col]),
                    "orange_hue": int(hsv[row, col, 0]),
                    "diff_px": (-1 if previous_frame is None
                                else int(np.count_nonzero(cv2.absdiff(frame, previous_frame)))),
                })
                previous_frame = frame.copy()

        if not reported and frame_index == config.CAMERA_DIAGNOSTIC_FRAMES // 2:
            memory_mid = _working_set_bytes()

        left_motor.setVelocity(left_speed)
        right_motor.setVelocity(right_speed)

        last_command = (left_speed, right_speed)


        if csv_logger is not None and frame_index % config.LOG_EVERY_N_STEPS == 0:
            row = logger.format_row(frame_index * timestep / 1000.0, detection, ranging,
                                    command, "IDLE")
            csv_logger.write_row(row)
            if frame_index % 300 == 0:
                csv_logger.flush()

        if truth_path is not None and ball_node is not None:
            rp = self_node.getPosition()
            m = self_node.getOrientation()
            cam = (rp[0] + m[0] * 0.100 + m[2] * 0.085,
                   rp[1] + m[3] * 0.100 + m[5] * 0.085,
                   rp[2] + m[6] * 0.100 + m[8] * 0.085)
            bp = ball_node.getPosition()
            true_range = math.dist(cam, bp)
            truth_rows.append((frame_index * timestep / 1000.0, true_range,
                               ranging.distance_m if ranging.valid else "",
                               ranging.bearing_deg if ranging.bearing_deg is not None else "",
                               left_speed, right_speed,
                               "1" if detection.detected else "0"))

        if not reported and frame_index + 1 >= config.CAMERA_DIAGNOSTIC_FRAMES:
            left_motor.setVelocity(0.0)
            right_motor.setVelocity(0.0)
            memory_end = _working_set_bytes()
            plots = _project_path("results/plots")
            os.makedirs(plots, exist_ok=True)
            cv2.imwrite(os.path.join(plots, "camera_check_frame.png"), frame)
            cv2.imwrite(os.path.join(plots, "debug_overlay_frame.png"), annotated)
            _write_camera_report(camera, samples, convert_times, detect_times,
                                 overlay_times, detections, memory_start, memory_mid,
                                 memory_end, time.perf_counter() - wall_start,
                                 window_status[0])
            reported = True

        if not detection.detected and not lost_frame_saved[0]:
            plots = _project_path("results/plots")
            os.makedirs(plots, exist_ok=True)
            cv2.imwrite(os.path.join(plots, "debug_overlay_lost.png"), annotated)
            lost_frame_saved[0] = True

        now = time.perf_counter()
        if last_frame_clock is not None:
            interval = now - last_frame_clock
            if interval > 0:
                live_fps = 0.9 * live_fps + 0.1 * (1.0 / interval) if live_fps else 1.0 / interval
        last_frame_clock = now

        if show_window:
            try:
                cv2.imshow(config.DEBUG_WINDOW_NAME, annotated)
                cv2.waitKey(1)
                window_status[0] = "open (%s)" % config.DEBUG_WINDOW_NAME
            except Exception as exc:
                # No display, or OpenCV built without highgui. Stop trying rather than
                # killing an otherwise healthy controller.
                window_status[0] = "failed: %s" % exc
                show_window = False

        frame_index += 1
        if run_budget is not None and frame_index * timestep / 1000.0 >= run_budget:
            break

    left_motor.setVelocity(0.0)
    right_motor.setVelocity(0.0)

    if csv_logger is not None:
        csv_logger.close()

    if truth_path and truth_rows:
        os.makedirs(os.path.dirname(os.path.abspath(truth_path)), exist_ok=True)
        with open(truth_path, "w", encoding="utf-8", newline="") as handle:
            handle.write("t_s,true_range_m,est_range_m,bearing_deg,left_rad_s,"
                         "right_rad_s,detected\n")
            for row in truth_rows:
                handle.write(",".join(str(value) for value in row) + "\n")

    # Stop movie recording if it was started
    if record_video and hasattr(robot, 'movieStopRecording'):
        try:
            robot.movieStopRecording()
        except Exception:
            pass

    csv_logger.close()

    if show_window:
        try:
            cv2.destroyAllWindows()
        except Exception:
            pass


if __name__ == "__main__":
    main()
