"""CSV logging of vision, control and state over the simulation run.

Writes one row per step to results/logs/tracking_log.csv with the exact schema and
formatting specified in PROMPT 10. The file is opened once at startup and flushed
periodically to ensure zero data loss on unexpected termination.

Pure formatting - no Webots or OpenCV imports, so the log functions can be unit-tested
in isolation.
"""

import csv
import os


# The exact schema specified in PROMPT 10, in order
FIELDNAMES = [
    "timestamp",
    "ball_detected",
    "ball_x",
    "ball_y",
    "ball_radius",
    "estimated_distance",
    "image_error",
    "linear_velocity",
    "angular_velocity",
    "left_motor_velocity",
    "right_motor_velocity",
    "state",
]


def _format_field(value):
    """Empty values become "", everything else becomes its string representation."""
    if value is None or value == "":
        return ""
    return str(value)


def format_row(timestamp_s, detection, distance_info, control_command, state_name):
    """Build a CSV row dict from vision, control and state.

    Returns a dict ready to pass to csv.DictWriter.writerow(). All formatting rules
    (empty strings for missing, float precision, pixel/metre units) are applied here.
    """
    row = {}
    row["timestamp"] = float(timestamp_s)

    if detection is not None and detection.detected:
        row["ball_detected"] = 1
        row["ball_x"] = float(detection.center_x)
        row["ball_y"] = float(detection.center_y)
        row["ball_radius"] = float(detection.radius)
        # image_error is horizontal error in pixels from the optical centre
        # ImageCenterX is where the camera's principal point projects, so error is
        # center_x - image_center_x. But config.IMAGE_CENTER_X is not imported here,
        # so the caller must pass it, or we fetch it on first use.
        import config
        row["image_error"] = float(detection.center_x - config.IMAGE_CENTER_X)
    else:
        row["ball_detected"] = 0
        row["ball_x"] = ""
        row["ball_y"] = ""
        row["ball_radius"] = ""
        row["image_error"] = ""

    if distance_info is not None and distance_info.valid and distance_info.distance_m is not None:
        row["estimated_distance"] = float(distance_info.distance_m)
    else:
        row["estimated_distance"] = ""

    if control_command is not None:
        row["linear_velocity"] = float(control_command.linear_command)
        row["angular_velocity"] = float(control_command.angular_command)
        row["left_motor_velocity"] = float(control_command.left_velocity)
        row["right_motor_velocity"] = float(control_command.right_velocity)
    else:
        row["linear_velocity"] = ""
        row["angular_velocity"] = ""
        row["left_motor_velocity"] = ""
        row["right_motor_velocity"] = ""

    row["state"] = str(state_name) if state_name is not None else ""

    return row


class CSVLogger:
    """Manages the CSV file lifecycle: open, write, flush, close."""

    def __init__(self, path, timestep_ms=None):
        """Open the CSV file. Create its parent directory if needed."""
        self.path = path
        self.timestep_ms = timestep_ms
        self.handle = None
        self.writer = None
        self.rows_written = 0

        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self.handle = open(path, "w", encoding="utf-8", newline="")
        self.writer = csv.DictWriter(self.handle, fieldnames=FIELDNAMES)
        self.writer.writeheader()
        self.handle.flush()

    def write_row(self, row_dict):
        """Write one row and increment the counter."""
        if self.writer is None:
            raise RuntimeError("Logger is closed")
        self.writer.writerow(row_dict)
        self.rows_written += 1

    def flush(self):
        """Sync the file to disk. Called periodically during the run."""
        if self.handle is not None:
            self.handle.flush()

    def close(self):
        """Close the file. The logger is not reusable after close()."""
        if self.handle is not None:
            self.handle.flush()
            self.handle.close()
            self.handle = None
            self.writer = None
