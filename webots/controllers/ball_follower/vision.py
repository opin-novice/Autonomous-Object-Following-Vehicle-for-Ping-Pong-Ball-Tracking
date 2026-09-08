"""OpenCV ping-pong ball detection.

Deliberately free of any Webots import: every function takes a plain NumPy array and
returns plain data, so the detector can be exercised from a normal Python session or a
unit test without launching the simulator. See tests/test_vision.py.

Pipeline:
    BGR frame -> optional blur -> HSV -> inRange -> morphological open then close
    -> findContours(RETR_EXTERNAL) -> area, circularity and radius filtering
    -> largest surviving contour -> minEnclosingCircle -> Detection

Thresholds default to config but every one of them is an explicit keyword argument, which
is what makes the filtering rules testable in isolation rather than only as a bundle.
"""

import math
from dataclasses import asdict, dataclass

import cv2
import numpy as np

import config


@dataclass(frozen=True)
class Detection:
    """Result of one detection attempt on one frame.

    Pixel coordinates follow the image convention: center_x grows right, center_y grows
    down, both measured from the top-left corner.
    """

    detected: bool
    center_x: float = 0.0
    center_y: float = 0.0
    radius: float = 0.0
    area: float = 0.0
    confidence: float = 0.0

    @classmethod
    def miss(cls) -> "Detection":
        """The canonical 'no ball this frame' value."""
        return cls(detected=False)

    def as_dict(self) -> dict:
        """The plain-dict form of the data contract."""
        return asdict(self)


def webots_image_to_bgr(image_bytes, width, height):
    """Convert a raw Webots camera buffer into an OpenCV BGR array.

    Webots hands back a flat bytes object of width*height*4 in **BGRA** order. Verified
    rather than assumed: an orange ball (baseColor 1 0.35 0.02) read through this path
    lands at hue ~11 in OpenCV's HSV, where the same buffer interpreted as RGBA would put
    it near hue ~110 and the orange threshold would find nothing.

    cv2.cvtColor is used rather than a `[:, :, :3]` slice on purpose. np.frombuffer wraps
    the caller's bytes in a read-only array, so a slice of it is a read-only view; anything
    later that draws an overlay in place would raise. cvtColor returns a fresh, writable,
    C-contiguous array and costs about 0.1 ms.

    Raises ValueError on a short or absent buffer, which is what a camera that was never
    enable()d looks like.
    """
    if image_bytes is None:
        raise ValueError("camera returned no image - was camera.enable() called, and has "
                         "robot.step() run at least once since?")
    expected = width * height * 4
    if len(image_bytes) != expected:
        raise ValueError("camera buffer is %d bytes, expected %d for %dx%d BGRA"
                         % (len(image_bytes), expected, width, height))

    bgra = np.frombuffer(image_bytes, dtype=np.uint8).reshape((height, width, 4))
    return cv2.cvtColor(bgra, cv2.COLOR_BGRA2BGR)


def build_color_mask(bgr_frame, hsv_lower=None, hsv_upper=None, blur_kernel=-1,
                     morph_kernel=None):
    """Isolate the orange ball as a binary mask.

    Blur (optional) -> HSV -> inRange -> morphological opening then closing.

    Opening removes isolated speckle; closing fills the small interior holes that
    specular shading punches in the ball. Both use the same small elliptical kernel: the
    ball is only ~4 px in radius at the far end of the arena, and a larger kernel erodes
    it out of existence.

    Grey surfaces are rejected by saturation rather than hue. A grey pixel has S near
    zero whatever its hue happens to be, so the S floor is what actually keeps the floor
    and walls out of the mask.

    Pass blur_kernel=None to skip blurring; the default (-1) means "use config".
    """
    hsv_lower = config.HSV_LOWER if hsv_lower is None else hsv_lower
    hsv_upper = config.HSV_UPPER if hsv_upper is None else hsv_upper
    morph_kernel = config.MORPH_KERNEL_SIZE if morph_kernel is None else morph_kernel
    if blur_kernel == -1:
        blur_kernel = config.GAUSSIAN_BLUR_KERNEL

    working = bgr_frame
    if blur_kernel:
        working = cv2.GaussianBlur(working, tuple(blur_kernel), 0)

    hsv = cv2.cvtColor(working, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, np.array(hsv_lower, np.uint8), np.array(hsv_upper, np.uint8))

    element = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, tuple(morph_kernel))
    # iterations=0 is not a no-op in OpenCV, so the stage is skipped explicitly
    if config.MORPH_OPEN_ITERATIONS > 0:
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, element,
                                iterations=config.MORPH_OPEN_ITERATIONS)
    if config.MORPH_CLOSE_ITERATIONS > 0:
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, element,
                                iterations=config.MORPH_CLOSE_ITERATIONS)
    return mask


def circularity(area, perimeter):
    """Shape factor C = 4 * pi * A / P^2. 1.0 for a perfect circle, lower otherwise.

    Returns 0.0 for a degenerate contour rather than dividing by zero - a one-pixel or
    collinear contour has zero perimeter and is never the ball.

    Note that C is biased low for small blobs: a rasterised circle has a staircase
    boundary, so arcLength overestimates the true perimeter and P^2 grows faster than A.
    That bias is the reason MIN_CIRCULARITY doubles as the distance limit.
    """
    if perimeter <= 0.0:
        return 0.0
    return float(4.0 * math.pi * area / (perimeter * perimeter))


def detection_confidence(circ, area, radius):
    """Blend shape quality and fill into a single 0-1 score.

    Two independent ways of being wrong are combined: circularity catches ragged or
    elongated blobs, and the fill ratio A / (pi r^2) catches a contour that encloses a
    large empty circle - a crescent or a pair of merged specks. Each is clamped at 1.0
    before averaging so a small-blob rasterisation artefact cannot push the score above 1.
    """
    if radius <= 0.0:
        return 0.0
    fill = area / (math.pi * radius * radius)
    return float(max(0.0, min(1.0, 0.5 * min(circ, 1.0) + 0.5 * min(fill, 1.0))))


def detect_ball(bgr_frame, mask=None, min_area=None, max_area=None, min_circularity=None,
                min_radius=None, max_radius=None, return_rejects=False):
    """Find the ball in one BGR frame.

    Returns a Detection. `Detection.miss()` when nothing survives filtering, so callers
    never have to test for None.

    Candidate selection is largest-surviving-area rather than best-confidence: the ball is
    the only saturated orange object in the arena, so among valid candidates the biggest
    is the nearest, and preferring it keeps the follower locked on the closest target
    instead of flicking to a cleaner-looking speck.

    Pass return_rejects=True to get (detection, rejects) where rejects lists every
    discarded contour with the reason. That exists for tuning and diagnostics - it is how
    the circularity threshold was chosen - and is off by default so the hot path stays
    allocation-free.
    """
    min_area = config.MIN_CONTOUR_AREA_PX if min_area is None else min_area
    max_area = config.MAX_CONTOUR_AREA_PX if max_area is None else max_area
    min_circ = config.MIN_CIRCULARITY if min_circularity is None else min_circularity
    min_radius = config.MIN_RADIUS_PX if min_radius is None else min_radius
    max_radius = config.MAX_RADIUS_PX if max_radius is None else max_radius

    if mask is None:
        mask = build_color_mask(bgr_frame)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    best = None
    rejects = []
    for contour in contours:
        area = float(cv2.contourArea(contour))
        if area < min_area:
            rejects.append(("area_too_small", area, 0.0, 0.0))
            continue
        if area > max_area:
            rejects.append(("area_too_large", area, 0.0, 0.0))
            continue

        perimeter = float(cv2.arcLength(contour, True))
        circ = circularity(area, perimeter)
        if circ < min_circ:
            rejects.append(("not_circular", area, circ, 0.0))
            continue

        (center_x, center_y), radius = cv2.minEnclosingCircle(contour)
        radius = float(radius)
        if radius < min_radius:
            rejects.append(("radius_too_small", area, circ, radius))
            continue
        if radius > max_radius:
            rejects.append(("radius_too_large", area, circ, radius))
            continue

        candidate = Detection(
            detected=True,
            center_x=float(center_x),
            center_y=float(center_y),
            radius=radius,
            area=area,
            confidence=detection_confidence(circ, area, radius),
        )
        if best is None or candidate.area > best.area:
            best = candidate

    result = best if best is not None else Detection.miss()
    return (result, rejects) if return_rejects else result


def estimate_distance(radius_px, focal_length_px=None, ball_diameter_m=None, scale=None):
    """Monocular apparent-size distance estimate.

        Z = scale * f * D / (2 * r)

    with r the apparent radius in pixels, D the true ball diameter and f the focal length
    in pixels. Returns None for a non-positive radius rather than dividing by zero.

    This is an approximation, not calibrated ranging - report it as "monocular
    apparent-size-based distance estimation".

    The radius must come from cv2.minEnclosingCircle, not from contourArea: the polygon
    area runs about 10% under the true blob because it traces boundary pixel centres.

    No validity gating here - this is the raw model. Use estimate_distance_and_bearing()
    for the gated result.
    """
    if radius_px is None or radius_px <= 0.0:
        return None
    focal = config.FOCAL_LENGTH_PX if focal_length_px is None else focal_length_px
    diameter = config.BALL_DIAMETER_M if ball_diameter_m is None else ball_diameter_m
    factor = config.DISTANCE_CALIBRATION_SCALE if scale is None else scale
    if factor <= 0.0:
        raise ValueError("DISTANCE_CALIBRATION_SCALE must be positive, got %r" % (factor,))
    return float(focal * diameter / (2.0 * radius_px * factor))


def bearing_degrees(center_x, focal_length_px=None, image_center_x=None):
    """Horizontal angle from the optical axis to the ball, in degrees.

    theta = atan((u - u_center) / f). Positive means the ball is right of centre, which
    is the direction the robot must turn toward. This is a true angle rather than a
    normalised pixel error, so it stays meaningful if the resolution or FOV changes.
    """
    focal = config.FOCAL_LENGTH_PX if focal_length_px is None else focal_length_px
    centre = config.IMAGE_CENTER_X if image_center_x is None else image_center_x
    return float(math.degrees(math.atan2(center_x - centre, focal)))



@dataclass(frozen=True)
class RangeBearing:
    """Gated distance and bearing derived from one Detection.

    `valid` is the single flag a caller should branch on. When it is False the distance is
    None and must not be used for control.

    Bearing is deliberately still populated whenever the ball was seen at all, even if the
    distance is gated out. Bearing depends only on center_x, so it stays trustworthy when
    the radius - and therefore the distance - does not, and PROMPT 9 needs a last-known
    direction to search toward after a low-confidence frame.
    """

    valid: bool
    distance_m: float = None
    bearing_rad: float = None
    bearing_deg: float = None

    def as_dict(self) -> dict:
        return asdict(self)


def estimate_distance_and_bearing(detection, focal_length_px=None, ball_diameter_m=None,
                                  scale=None, min_confidence=None, min_distance=None,
                                  max_distance=None):
    """Turn a Detection into a gated range and bearing.

        Z     = f * D / (2 * r * scale)
        theta = atan2(center_x - u_center, f)

    Returns RangeBearing with valid=False and distance_m=None when the ball was not
    detected, when confidence is below MIN_CONFIDENCE_THRESHOLD, or when Z falls outside
    [MIN_VALID_DISTANCE_M, MAX_VALID_DISTANCE_M].
    """
    min_confidence = config.MIN_CONFIDENCE_THRESHOLD if min_confidence is None else min_confidence
    min_distance = config.MIN_VALID_DISTANCE_M if min_distance is None else min_distance
    max_distance = config.MAX_VALID_DISTANCE_M if max_distance is None else max_distance

    if detection is None or not detection.detected:
        return RangeBearing(valid=False)

    bearing_deg = bearing_degrees(detection.center_x, focal_length_px=focal_length_px)
    bearing_rad = math.radians(bearing_deg)

    if detection.confidence < min_confidence:
        return RangeBearing(valid=False, bearing_rad=bearing_rad, bearing_deg=bearing_deg)

    distance = estimate_distance(detection.radius, focal_length_px=focal_length_px,
                                 ball_diameter_m=ball_diameter_m, scale=scale)
    if distance is None or not (min_distance <= distance <= max_distance):
        return RangeBearing(valid=False, bearing_rad=bearing_rad, bearing_deg=bearing_deg)

    return RangeBearing(valid=True, distance_m=distance, bearing_rad=bearing_rad,
                        bearing_deg=bearing_deg)


def _draw_dashed_vertical_line(image, x, colour, dash=12, gap=8, thickness=1):
    """A dashed vertical line. cv2 has no dashed-line primitive."""
    height = image.shape[0]
    x = int(round(x))
    y = 0
    while y < height:
        cv2.line(image, (x, y), (x, min(y + dash, height - 1)), colour, thickness)
        y += dash + gap


# BGR constants, named so the drawing code reads as intent rather than tuples.
_GREEN = (0, 255, 0)
_RED = (0, 0, 255)
_CYAN = (255, 255, 0)
_YELLOW = (0, 255, 255)
_WHITE = (255, 255, 255)
_BLACK = (0, 0, 0)


def draw_debug_overlay(frame, detection, distance_m=None, state=None,
                       left_velocity=None, right_velocity=None, fps=None):
    """Annotate a copy of `frame` with the detection and its derived metrics.

    Returns a new BGR array; the input is never modified. Pure drawing - it does not call
    imshow or waitKey, so it is safe to use in a headless run or to write straight to disk.

    Draws the minimum enclosing circle, the centroid, a dashed line at the optical centre,
    an arrow showing the horizontal error, and a HUD panel of telemetry.
    """
    annotated = frame.copy()
    height, width = annotated.shape[:2]
    centre_x = config.IMAGE_CENTER_X

    _draw_dashed_vertical_line(annotated, centre_x, _CYAN)

    detected = bool(detection.detected)
    if detected:
        u, v = detection.center_x, detection.center_y
        radius = max(int(round(detection.radius)), 1)
        cv2.circle(annotated, (int(round(u)), int(round(v))), radius, _GREEN, 2)
        cv2.circle(annotated, (int(round(u)), int(round(v))), 3, _RED, -1)

        # horizontal error vector: from the optical axis across to the ball, at the
        # ball's own height so it reads as the quantity the steering loop consumes
        start = (int(round(centre_x)), int(round(v)))
        end = (int(round(u)), int(round(v)))
        if abs(end[0] - start[0]) > 2:
            cv2.arrowedLine(annotated, start, end, _YELLOW, 2, tipLength=0.25)
        else:
            cv2.line(annotated, (start[0], start[1] - 6), (start[0], start[1] + 6), _YELLOW, 2)

        error_px = u - centre_x
        bearing = bearing_degrees(u)
        rows = [
            ("DETECTED", _GREEN),
            ("centroid  (%.1f, %.1f) px" % (u, v), _WHITE),
            ("radius    %.2f px" % detection.radius, _WHITE),
            ("distance  %s" % ("%.3f m" % distance_m if distance_m is not None else "n/a"), _WHITE),
            ("bearing   %+.2f deg" % bearing, _WHITE),
            ("error_u   %+.1f px" % error_px, _WHITE),
            ("conf      %.2f" % detection.confidence, _WHITE),
        ]
    else:
        rows = [
            ("LOST", _RED),
            ("centroid  --", _WHITE),
            ("radius    --", _WHITE),
            ("distance  --", _WHITE),
            ("bearing   --", _WHITE),
            ("error_u   --", _WHITE),
            ("conf      0.00", _WHITE),
        ]

    if state is not None:
        rows.append(("state     %s" % state, _WHITE))
    if left_velocity is not None and right_velocity is not None:
        rows.append(("wheels    L %+.2f  R %+.2f rad/s" % (left_velocity, right_velocity), _WHITE))
    if fps is not None:
        rows.append(("fps       %.1f" % fps, _WHITE))

    _draw_hud(annotated, rows)
    return annotated


def _draw_hud(image, rows, origin=(10, 10), line_height=18, font_scale=0.45):
    """Text panel with a translucent backing so it stays readable over any scene."""
    font = cv2.FONT_HERSHEY_SIMPLEX
    widest = max(cv2.getTextSize(text, font, font_scale, 1)[0][0] for text, _ in rows)
    panel_w = widest + 16
    panel_h = line_height * len(rows) + 12
    x0, y0 = origin

    backing = image[y0:y0 + panel_h, x0:x0 + panel_w].copy()
    cv2.rectangle(backing, (0, 0), (panel_w, panel_h), _BLACK, -1)
    cv2.addWeighted(backing, 0.55, image[y0:y0 + panel_h, x0:x0 + panel_w], 0.45, 0,
                    image[y0:y0 + panel_h, x0:x0 + panel_w])
    cv2.rectangle(image, (x0, y0), (x0 + panel_w, y0 + panel_h), (70, 70, 70), 1)

    for index, (text, colour) in enumerate(rows):
        baseline = y0 + line_height * (index + 1)
        cv2.putText(image, text, (x0 + 8, baseline), font, font_scale, colour, 1, cv2.LINE_AA)
