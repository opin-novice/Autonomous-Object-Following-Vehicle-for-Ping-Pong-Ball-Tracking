"""All tunable parameters for the ping-pong ball follower.

This module holds configuration only. It must never import the other controller
modules and must never contain control or vision logic — that separation is what
lets the gains be retuned without touching an algorithm.

Values marked CALIBRATE are placeholders chosen from the geometry of the intended
setup. They are not yet validated against a running simulation.
"""

import math

# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------

TIME_STEP_MS = 32
"""Controller step in milliseconds. Must be a multiple of the world's basicTimeStep."""

# ---------------------------------------------------------------------------
# Camera
# ---------------------------------------------------------------------------

CAMERA_NAME = "camera"
IMAGE_WIDTH = 640
IMAGE_HEIGHT = 480
CAMERA_FOV_RAD = 1.0

IMAGE_CENTER_X = (IMAGE_WIDTH - 1) / 2.0
IMAGE_CENTER_Y = (IMAGE_HEIGHT - 1) / 2.0
"""Optical centre of the pixel grid, 319.5 / 239.5 for 640x480.

Not width/2. Pixel indices run 0..639, so the centre of the grid is (640-1)/2 = 319.5;
using 320.0 puts a permanent half-pixel bias into the steering error. The simulator
confirms it: with the ball dead ahead the detector reports center_x = 319.50 across 150
consecutive frames with zero spread, not 320.0."""

FOCAL_LENGTH_PX = (IMAGE_WIDTH / 2.0) / math.tan(CAMERA_FOV_RAD / 2.0)
"""Pinhole focal length in pixels, derived from the configured horizontal FOV.

With the defaults above this is ~585.8 px. Keep it derived rather than hardcoded so
that changing IMAGE_WIDTH or CAMERA_FOV_RAD cannot silently invalidate the distance
estimate.
"""

# ---------------------------------------------------------------------------
# Target ball
# ---------------------------------------------------------------------------

BALL_DIAMETER_M = 0.040
"""Regulation ping-pong ball diameter.

CALIBRATE / DESIGN RISK: at this diameter the apparent radius is only
  r_px = FOCAL_LENGTH_PX * BALL_DIAMETER_M / (2 * Z)
which is ~5.9 px at 2 m and ~3.9 px at 3 m. Contour circularity is unreliable at that
scale. If Phase 2 detection proves too noisy at the specified 1-3 m start distance,
the options in order of preference are: raise the start distance floor, raise the
camera resolution, or scale the ball up (and say so plainly in the report). Decide
with measured data from Phase 2, not by guessing here.
"""

# HSV bounds for the orange ball, in OpenCV ranges (H 0-179, S 0-255, V 0-255).
# CALIBRATE against the actual rendered frame in Phase 2 (PROMPT 5).
HSV_LOWER = (5, 120, 100)
HSV_UPPER = (20, 255, 255)

# ---------------------------------------------------------------------------
# Detection filtering
# ---------------------------------------------------------------------------

GAUSSIAN_BLUR_KERNEL = None
"""Pre-threshold blur, disabled after measurement. A blur bleeds grey background into the
rim of a small ball, drops its saturation below the threshold and shrinks the blob - and
the shrinkage grows with distance, so it biases the apparent-size distance estimate rather
than just adding noise. Measured mean radius error against the pinhole prediction over
nine ranges from 0.4 to 2.8 m (tests/fixtures/range_*.png):

    raw inRange, no morphology   -0.68 %   (worst -2.67 %)
    morphology 3x3 only          -1.56 %   (worst -8.99 %, at 2.8 m)
    blur 3x3 + morphology 3x3    -5.75 %   (worst -11.33 %)
    blur 5x5 + morphology 3x3    -8.53 %   (worst -14.38 %)

Morphology is kept: it is cheap, it is specified, and it costs almost nothing except on
the smallest blobs. Blur bought nothing here because the rendered arena has no sensor
noise - the measured stray-pixel count outside the ball is zero. Re-enable it with a 3x3
kernel if PROMPT 14 introduces real noise, and re-check the table above if you do."""
MORPH_KERNEL_SIZE = (3, 3)
MORPH_OPEN_ITERATIONS = 0
"""Opening disabled after measurement - it destroyed the far-range radius.

Erosion takes a fixed ring off the blob, which is negligible at 30 px and fatal at 4 px.
Measured radius error against the pinhole prediction, closing held at 2 iterations:

    range      no opening      with 3x3 opening
    1.50 m       -0.31 %            -1.98 %
    2.80 m       -2.65 %            -8.96 %

At 2.8 m that is the difference between a +2.6 % and a +9.8 % distance estimate. The
arena has zero measured stray pixels, so opening was rejecting noise that does not exist.
Restore it (value 1) only alongside real sensor noise, and re-measure this table."""
MORPH_CLOSE_ITERATIONS = 2

MIN_CONTOUR_AREA_PX = 20.0
"""Measured: cv2.contourArea of the ball is ~40 px at 2.8 m, the far wall of the arena."""
MAX_CONTOUR_AREA_PX = 120_000.0
MIN_CIRCULARITY = 0.60
"""Reject contours whose 4*pi*A / P^2 falls below this. 1.0 is a perfect circle."""
MIN_RADIUS_PX = 2.5
MAX_RADIUS_PX = 250.0

# ---------------------------------------------------------------------------
# Distance estimation
# ---------------------------------------------------------------------------

DISTANCE_CALIBRATION_SCALE = 1.000
"""Divisor in Z = f * D / (2 * r * scale). Calibrated, and the answer is 1.000.

Fitted against supervisor truth over seven ranges (tests/fixtures/range_*.png):

    scale 1.0000 (uncalibrated)   max error 2.72 %   5 of 7 within 1.5 %
    scale 1.0045 (mean fit)       max error 2.79 %   5 of 7 within 1.5 %
    scale 1.0015 (minimax fit)    max error 2.56 %   5 of 7 within 1.5 %

No scale improves the count, because the two worst ranges err in opposite directions:
0.40 m reads 2.5 % short and 2.80 m reads 2.6 % long. A single multiplier cannot pull
both toward zero. 1.000 is kept because a fitted constant would buy 0.16 of a percentage
point at the cost of an unexplained magic number."""

MIN_VALID_DISTANCE_M = 0.20
"""Below this the ball overflows the frame and the enclosing circle is clipped."""
MAX_VALID_DISTANCE_M = 3.50
"""Set by the 20 px contour-area floor, which extrapolates to about 3.7 m."""

MIN_CONFIDENCE_THRESHOLD = 0.60
"""Detections below this do not yield a distance. Measured confidence sits at 0.85-0.93
across the whole arena, so this rejects genuinely malformed blobs rather than trimming
the working range."""

# ---------------------------------------------------------------------------
# Robot geometry
# ---------------------------------------------------------------------------

LEFT_MOTOR_NAME = "left wheel motor"
RIGHT_MOTOR_NAME = "right wheel motor"

WHEEL_RADIUS_M = 0.040
WHEEL_SEPARATION_M = 0.160
"""Distance between the two wheel contact points (the 'L' in the mixer equations)."""
# ---------------------------------------------------------------------------
# Control gains and limits
# ---------------------------------------------------------------------------

TARGET_DISTANCE_M = 0.40
"""Camera-to-ball distance the follower holds. The camera sits 0.10 m ahead of the robot
origin, so this leaves the chassis well clear of a 2.7 g ball it would otherwise punt."""

DISTANCE_TOLERANCE_M = 0.025
"""Deadband half-width: 0.37-0.43 m counts as arrived and commands zero forward speed."""

KP_STEER = 2.2
"""Bearing (rad) -> angular command. Applied as v_angular = -KP_STEER * e_theta."""

KP_DIST = 1.8
"""Distance error (m) -> forward command."""

MAX_WHEEL_SPEED = 6.28
"""Controller ceiling, below the 10 rad/s the PROTO motors allow. Keeping headroom means
a clamp here can never be masked by the motor's own saturation."""

MIN_WHEEL_SPEED = 0.5
"""Floor for a wheel that is meant to be turning, to overcome stiction.

Applied only while the follower actually wants to advance. Applying it to a pure steering
correction would turn an arbitrarily small bearing error into a 0.5 rad/s twitch, and the
robot would hunt around the centre line forever instead of settling."""

MAX_WHEEL_VELOCITY_RAD_S = 10.0
"""Hardware limit from the PROTO. MAX_WHEEL_SPEED must stay at or below this."""

STOP_HYSTERESIS_M = 0.06
"""Extra distance the ball must retreat before an arrived robot resumes approaching.
Used by the PROMPT 9 state machine, not by the proportional law itself."""

HEADING_ALIGN_RAD = 0.08
"""Heading error tolerance (rad) for TRACKING -> APPROACHING transition."""

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOG_ENABLED = True
"""Record every step to CSV: timestamp, detection, geometry, control, state."""

LOG_PATH = "results/logs/tracking_log.csv"
"""Relative to the controller working directory (the world's controller directory)."""

LOG_EVERY_N_STEPS = 1
"""Log only every Nth step. Set to 1 for continuous logging."""

# ---------------------------------------------------------------------------
# Ball-lost behaviour
# ---------------------------------------------------------------------------
# Ball-lost behaviour & FSM
# ---------------------------------------------------------------------------

COAST_DURATION_S = 0.3
"""Coasting window before search mode in seconds. Decelerates prior motion."""

SEARCH_SPIN_SPEED = 1.0
"""Angular speed for search spin in rad/s."""

LOST_COAST_SECONDS = 0.3
SEARCH_ANGULAR_VELOCITY_RAD_S = 1.0
SEARCH_DEFAULT_DIRECTION = 1.0
"""Turn direction when there is no last known ball side. +1 left, -1 right."""


# ---------------------------------------------------------------------------
# Logging and debug output
# ---------------------------------------------------------------------------

LOG_ENABLED = True
LOG_PATH = "results/logs/tracking_log.csv"
LOG_EVERY_N_STEPS = 1

DEBUG_OVERLAY_ENABLED = True
DEBUG_WINDOW_ENABLED = True
"""Open a live cv2 window. Set the BALL_FOLLOWER_HEADLESS environment variable to force
this off for automated runs - an OpenCV window in a --batch run is noise, and on a machine
without a display it would raise."""
DEBUG_WINDOW_NAME = "Robot Camera Debug"
DEBUG_SAVE_FRAMES = False
DEBUG_FRAME_DIR = "results/debug_frames"

CAMERA_DIAGNOSTIC_FRAMES = 150
"""Frames to profile at startup before writing CAMERA_CHECK_LOG. Cheap, and it turns
"the camera works" into something with numbers attached."""
CAMERA_CHECK_LOG = "results/logs/camera_check.txt"
