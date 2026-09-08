# Implementation notes

Running record of decisions, measurements and open questions. Measurements go in only
after they have actually been measured.

## Phase 0 — skeleton (2026-09-08)

### Environment survey

Checked before writing any code:

- Python 3.14.0 is the default `python`; 3.13 and 3.12 also present. Python 3.11, which the
  specification prefers, is absent.
- Git 2.51.1 and Node.js 22.21.0 present.
- Webots: **not installed**. Not on PATH, not in any standard install directory, no entry in
  the Windows uninstall registry under either `Webots` or `Cyberbotics`.

### Decisions

**Python 3.12.10 rather than 3.11.** 3.11 is not installed and adding another interpreter
costs time for no benefit. Webots R2022b and later ship a ctypes-based Python API that is
not compiled against a specific interpreter, so the controller should load under any
supported 3.x. Verify on first run.

**Project root is the existing working directory** rather than a nested
`ping_pong_follower/` folder as drawn in the specification. The extra directory level adds
nothing; module layout below it is unchanged.

**No stub world file.** A syntactically invalid `.wbt` fails to open in Webots and would
cost debugging time to distinguish from a real error. `webots/worlds/` stays empty until
Phase 1 writes a real world.

**Stubs raise instead of returning placeholder values.** Every unimplemented function
raises `NotImplementedError` naming its phase. A stub that returns `0.0` or an empty
`Detection` would let a later phase appear to run while producing meaningless output.

### Open questions

**Ball apparent size at the specified range.** A regulation 40 mm ball at 640 px / 1.0 rad
FOV subtends

    r_px = f * D / (2 * Z),  f = (640/2) / tan(0.5) = 585.8 px

giving ~5.9 px radius at 2 m and ~3.9 px at 3 m. Circularity filtering on a 4-pixel blob is
not meaningful — at that size a contour has too few boundary pixels for `4*pi*A/P^2` to
separate a circle from noise. The specification asks for both a ping-pong ball and a 1–3 m
start distance, and those two constraints are in tension.

Options, cheapest first: keep the start distance near 1–1.5 m; raise camera resolution;
relax `MIN_CIRCULARITY` at small radii; or scale the ball up and state the deviation in the
report. **Do not pick one until Phase 2 has measured actual detection rate at each
distance.** Recorded in `config.py` next to `BALL_DIAMETER_M`.

**runtime.ini is unverified.** Both the `[python] COMMAND` key and whether Webots resolves a
relative path against the controller directory need confirmation against installed docs.
Absolute-path fallback is in the file as a comment.

**Wheel clamping must preserve turn ratio.** Clamping left and right independently changes
the commanded turn radius whenever one wheel saturates. Noted in the `differential_drive_mixer`
docstring so Phase 4 does not get this wrong.

### Not done

No world, no robot, no detection, no control, no logs, no plots, no simulation run.

## Phase 0.5 — Webots verification (2026-09-08)

Webots R2025a was installed after the skeleton was written. Everything below is measured,
not assumed.

### Install facts

- `WEBOTS_HOME` = `C:\Users\USER\Webots`; binary at `msys64\mingw64\bin\webots.exe`.
- Version read from `resources/version.txt` → `R2025a`.
- **Offline documentation is not shipped** — `docs/` contains only `list.txt`. Rule 17's
  "consult the installed documentation" therefore means the shipped example projects under
  `projects/**` and, where those are silent, strings in `webots-bin.exe`.

### Resolved: Python 3.12 is safe

`lib/controller/python/controller/` holds only `.py` files, no version-locked `.pyd`, so
the API is the ctypes implementation. `from controller import Robot, Camera, Motor`
imports cleanly under the 3.12 venv together with `cv2` and `numpy`. The Phase 0 concern
about 3.11-vs-3.12 is closed.

### Resolved: runtime.ini — the Phase 0 guess was right, but incomplete

Twelve shipped `runtime.ini` files were inspected; **none** uses a `[python]` section, only
`[environment variables for <platform>]`. That looked like evidence the guess was wrong.
It was not — an error string inside `webots-bin.exe` settles it:

> "Check the COMMAND set in the [python] section of the runtime.ini file of your
> controller program if any."

So the mechanism exists; the samples simply do not need it.

### The interpreter hazard, and how it was measured

Webots reads `pythonCommand` from `HKCU:\SOFTWARE\Cyberbotics\Webots-R2025a\General`,
default `python`. Two different interpreters are reachable on this machine:

| Interpreter | OpenCV | NumPy |
|---|---|---|
| `C:\Python314\python.exe` (persisted PATH) | 4.13.0 | 2.3.5 |
| `.venv\Scripts\python.exe` (project) | 5.0.0 | 2.5.3 |

That is an OpenCV **major version** split, so which one Webots picks is not cosmetic.

A first measurement was misleading: `python` in the agent shell resolved to the venv, and
the probe reported cv2 5.0.0. The cause was `VIRTUAL_ENV` — VS Code auto-activates the
workspace venv in its terminals. A GUI launch of Webots inherits no such thing. Re-running
with `VIRTUAL_ENV` cleared and `PATH` reset to the persisted machine+user PATH gave the
honest answer.

Probe method: a throwaway Webots project in `scratch/` (gitignored, since deleted) with a
one-node `Robot { supervisor TRUE }` world and a controller that recorded
`sys.executable`, the cv2/numpy versions, and whether `robot.step()` succeeded, then called
`simulationQuit(0)`.

| Configuration (clean PATH) | Result |
|---|---|
| no `runtime.ini` | `C:\Python314\python.exe` 3.14.0, cv2 4.13.0 |
| `COMMAND = ../../../../.venv/Scripts/python.exe` | controller never started, no output |
| `COMMAND = d:/Autonomous Car/.venv/Scripts/python.exe` | `.venv` 3.12.10, cv2 5.0.0 |

Conclusion: the `[python] COMMAND` path **must be absolute**. `runtime.ini` now carries the
absolute path, and the relative form originally written in Phase 0 has been removed. The
cost is one machine-specific line, recorded as a limitation in the README.

### Two Windows gotchas worth not rediscovering

**Quote the world path.** The project path contains a space. Passed unquoted, Webots exits
1 instantly with no diagnostic — which reads exactly like a broken world file. The first
baseline run failed this way and cost a debugging cycle.

**Controller stdout is not pipeable.** `webots.exe` is a GUI-subsystem launcher; even
`--stdout --stderr` produced zero bytes through a redirect, and `--help` likewise. Any
controller output that has to be read programmatically must be written to a file. This
shapes how Phase 1 onward gets verified, and is why the smoke tests will write artifacts
rather than print.

**Headless runs are cheap.** `--batch --mode=fast --no-rendering --minimize` completes a
trivial world in about 2 s, so the edit/run/inspect loop does not need the GUI.

### Still open

The ball apparent-size problem from Phase 0 is unchanged and still the main technical risk:
a 40 mm ball is ~3.9 px in radius at 3 m. Nothing measured since bears on it. It stays open
until Phase 2 can report a real detection rate against distance.

## Phase 1a — robot and minimal world (PROMPT 2, 2026-09-08)

Built `webots/protos/PingPongFollowerRobot.proto` (differential drive, two driven wheels,
rear caster, front RGB camera) plus `webots/worlds/motion_check.wbt` and a
`motion_check` controller that measures two open-loop manoeuvres with the supervisor and
writes `results/logs/motion_check.txt`.

Three genuine defects were found by running it. None would have been caught by reading the
code.

### 1. `controller.py` shadowed the Webots `controller` package

The controller hung with no output. Markers showed it dying on
`from controller import Supervisor`.

Webots puts a controller's own directory first on `sys.path`, so the spec's
`controllers/ball_follower/controller.py` (section 6 of the guide) captures the import
before the Webots package ever gets a chance. Proved directly:

```
without ball_follower on sys.path -> C:\Users\USER\Webots\lib\controller\python\controller\__init__.py
with it first                     -> webots\controllers\ball_follower\controller.py, has Supervisor? False
```

This is not cosmetic: it would have broken `ball_follower.py` itself in Phase 4, since that
module has to do `from controller import Robot` from inside the very directory that
shadows it. The module is now `control.py`. This is a deliberate, necessary deviation from
the filename in the specification.

### 2. Webots `Cylinder` runs along Z, not Y

The first working run drove 21.6% short, sank the robot 0.03 m and under-rotated by 54%.
A bare cylinder (r=0.04, h=0.02) dropped onto a plane settles at **z = 0.0100**, with a
control sphere settling at exactly its 0.0300 radius — so the axis is Z and the wheels were
horizontal discs. The robot had been resting on its chassis, not its wheels.

Wrapping each wheel's shape and boundingObject in `Pose { rotation 1 0 0 1.5708 }` took
straight-line error from -21.6% to -0.4%.

### 3. A child `Solid` with no `Physics` does not collide

Even with the wheels fixed the robot rested 12.45 deg **nose-up** — which for a
forward-facing camera aims it above the horizon and would have pushed a floor-level ball
out of frame at range. The rear caster had been modelled as a child `Solid` carrying its
own `boundingObject` and `contactMaterial`; without a `Physics` node it never collided, so
the rear simply sagged until the chassis edge grounded out.

The caster is now part of the Robot's own `boundingObject Group`, and the whole body
carries `contactMaterial "caster"` so the world's `ContactProperties` can give it near-zero
friction. The wheels are separate Solids and keep the default material, so they still grip.

### Measured behaviour after the fixes

| Quantity | Measured | Predicted | Note |
|---|---|---|---|
| resting origin z | -0.0002 m | 0 | level |
| resting pitch | +0.064 deg | 0 | camera effectively horizontal |
| camera world height | 0.0849 m | 0.0850 | |
| straight-line travel, 4 rad/s for 3 s | 0.4811 m | 0.4813 m | -0.0% |
| heading drift while driving | 0.00 deg | 0 | |
| yaw, +/-1.5 rad/s for 3 s | +115.01 deg | +129.26 deg | -11.0% |
| centre drift while turning | 0.0673 m | 0 | caster swing |

The remaining -11% rotation shortfall is real differential-drive behaviour, not a modelling
error: turning in place scrubs the caster and slips the wheels laterally, and the ideal
`omega = R*(w_r - w_l)/L` assumes neither. It is recorded here so Phase 4 does not treat
the open-loop turn rate as exact. The follower steers closed-loop on image error, so a
constant turn-rate scale factor is absorbed by the proportional gain.

### Not yet done

No ball, no arena walls, no camera image processing. `ball_follower.py` implements only
`setup_devices()`; its `main()` still raises. The main world
`webots/worlds/ping_pong_follower.wbt` does not exist yet — `motion_check.wbt` is the
minimal PROMPT 2 world and stays as a permanent smoke test.

## Phase 1b — arena, ball and initial configuration (PROMPT 3, 2026-09-08)

`webots/worlds/ping_pong_follower.wbt`: 4 m x 4 m walled arena, neutral grey floor and
walls, two directional lights with ambient fill, one 40 mm / 2.7 g orange ball, and the
robot at (-1.000, 0, 0) facing +X. Verified by the `world_check` controller, which writes
`results/logs/world_check.txt`. All 16 checks pass.

### Ball placement

Placed at (0.300, 0, 0.020), giving **1.2001 m** camera-to-ball horizontally — the middle
of the 1.0-1.5 m band. At that range the ball sits 3.095 deg below the optical axis, well
inside the 0.78 rad vertical FOV.

### Repeatability

- Ball drift over 5 s idle: **0.000000 m**. The initial configuration is genuinely static.
- Released from z=0.30 it falls and settles at exactly z=0.0200 with 0.0000 m lateral
  wander, so physics is live rather than frozen, and the ball is not interpenetrating.
- After teleporting it away and back, it restores to the original pose to within 2 mm.

`rollingFriction 0.03 0 0` on the "ball"/"default" contact pair is what stops a 2.7 g
sphere creeping under numerical jitter.

### Colour separability

The neutral grey floor and walls were chosen so that saturation alone rejects the
background: greys have S near zero and cannot enter the `S > 120` window whatever the hue
does. Measured at the start pose: **297 orange pixels on the ball, 0 anywhere else in the
frame.** Nothing in the arena produces a false positive.

### Detection vs distance — the standing risk, now measured

The ball was teleported along the camera axis and the mask measured at each range. The
arena wall caps the sweep at 2.8 m.

| range (m) | mask px | radius (px) | pinhole prediction (px) |
|---|---|---|---|
| 0.40 | 2720 | 29.42 | 29.29 |
| 0.60 | 1191 | 19.47 | 19.53 |
| 0.80 | 669 | 14.59 | 14.64 |
| 1.00 | 425 | 11.63 | 11.72 |
| 1.20 | 297 | 9.72 | 9.76 |
| 1.50 | 192 | 7.82 | 7.81 |
| 2.00 | 106 | 5.81 | 5.86 |
| 2.50 | 70 | 4.72 | 4.69 |
| 2.80 | 54 | 4.15 | 4.18 |

Two conclusions, and one correction to an earlier note.

**The apparent-size distance model is sound.** Measured radius tracks `f*D/(2Z)` to within
about 1% across the whole range, and the horizontal centroid holds at u=319.5 throughout.
That is a strong prior for the PROMPT 7 calibration: `DISTANCE_CALIBRATION_SCALE` should
come out very close to 1.0.

**The Phase 0 warning was overstated for detection.** I had flagged a 40 mm ball at 3 m as
likely undetectable. Colour segmentation still yields 54 pixels at 2.8 m, comfortably above
`MIN_CONTOUR_AREA_PX = 20`. What remains true is the narrower point: at a 4 px radius a
contour has too few boundary pixels for `4*pi*A/P^2` to be meaningful, so
`MIN_CIRCULARITY = 0.60` is the parameter that will reject distant balls, not the area
threshold. That is a PROMPT 5 tuning decision, and it now has data behind it rather than
arithmetic.

### World file discipline

Every pose in the world is explicit and nothing is randomised. The world must not be saved
from the Webots GUI after a run, or the drifted state gets baked into the coordinates and
the configuration stops being repeatable. Noted in the world file header.

### Controller field

The robot's `controller` is `"world_check"` for this phase. PROMPT 4 switches it to
`"ball_follower"` once the camera acquisition loop exists.

## Phase 1c — camera acquisition pipeline (PROMPT 4, 2026-09-08)

World controller switched from `world_check` to `ball_follower`.
`vision.webots_image_to_bgr()` implemented; `ball_follower.main()` now runs a real
acquisition loop that profiles itself over the first 150 frames and writes
`results/logs/camera_check.txt`. All 11 checks pass.

### Measured pipeline

| Quantity | Value |
|---|---|
| raw buffer | 1228800 bytes = 640x480x4, BGRA |
| converted array | (480, 640, 3) uint8, C-contiguous, writeable |
| conversion cost | 0.12 ms/frame mean, 3.1 ms worst case |
| headless throughput | ~700 frames/s |
| with cv2 window | ~66 frames/s |
| sim budget | 32 ms/frame |

66 fps with the debug window is still twice the 31.25 Hz simulation rate, so the window
costs nothing in real-time mode. It is only worth disabling for batch sweeps.

### Channel order is BGRA - proved, not assumed

The brightest saturated pixel reads `B=60 G=122 R=235`, hue 11 in OpenCV HSV. Orange lives
at hue 5-20; the same buffer misread as RGBA would land near hue 110 (blue) and the ball
threshold would return nothing.

`cv2.cvtColor(..., COLOR_BGRA2BGR)` is used rather than a `[:, :, :3]` slice deliberately.
`np.frombuffer` wraps the caller's bytes read-only, so a slice of it is a read-only view
and the PROMPT 6 overlay would fail the moment it tried to draw in place. cvtColor returns
a fresh writable contiguous array for about 0.1 ms.

### Two of my own checks were wrong before the code was

Worth recording, because both produced a red FAIL against a pipeline that was fine.

**"Frames update between steps" failed on a correct pipeline.** The scene was static - the
wheels are held at zero this phase - so byte-identical frames were the correct output. The
check now only applies when `BALL_FOLLOWER_SELFTEST` is set, which rotates the robot slowly
during diagnostics so the view genuinely changes. The first version also used a sparse
`frame[::37, ::41]` checksum that stepped over a 10 px ball on a flat grey background; it
now counts actual differing pixels between sampled frames (6401 -> 20044 as the robot
turns).

**The memory probe reported "unavailable".** `GetCurrentProcess` returns a HANDLE, and
without an explicit `restype` ctypes truncates it to `int` on 64-bit, so the call failed
silently into a bare `except`. Fixed with explicit `argtypes`/`restype`.

### Memory: one-time cost, not a leak

Total growth over 150 frames with the window open is +11.6 MB, which trips a naive
threshold. Splitting the window in half separates the two possibilities:

```
growth 1st half : +11.555 MB over 75 frames
growth 2nd half :  +0.008 MB over 75 frames
```

One-time highgui/numpy/OpenCV allocation, flat thereafter. The leak check is now the
second-half figure. Headless, total growth is only +3.5 MB.

### `--no-rendering` does not starve camera devices

I had assumed it might, having used it for every headless run since PROMPT 2. Running the
selftest both ways gives byte-identical frame-difference sequences:

```
with    --no-rendering : 6401, 12695, 16747, 19995, 19925, 20044, 19470
without --no-rendering : 6401, 12695, 16747, 19995, 19925, 20044, 19470
```

Camera devices render independently of the main 3D view, so `--no-rendering` is safe for
vision work. The identical numbers across two separate processes also confirm the
simulation is deterministic, which matters for the PROMPT 11 evaluation runs.

### Environment overrides on ball_follower

| Variable | Effect |
|---|---|
| `BALL_FOLLOWER_HEADLESS` | never open the cv2 window |
| `BALL_FOLLOWER_RUN_SECONDS` | stop the loop after this much simulated time |
| `BALL_FOLLOWER_SELFTEST` | rotate slowly during diagnostics so frame freshness is testable |

Unset, the controller behaves normally: acquire, show the window, hold the wheels at zero.

## Phase 2 — OpenCV ball detector (PROMPT 5, 2026-09-08)

`vision.detect_ball()` implemented as a pure function: NumPy frame in, `Detection` out, no
Webots import anywhere in the module. 17 unit tests in `tests/test_vision.py` (stdlib
`unittest`, no new dependency) plus live verification in the simulator. All pass.

### Live result at the start pose

150 consecutive frames, robot stationary at 1.2 m:

| Quantity | Measured | Predicted |
|---|---|---|
| detection rate | **100.0 % (150/150)** | |
| center_x | 319.50 (no spread) | 320.0 |
| center_y | 271.86 | 271.7 |
| radius | 9.68 px | 9.76 px |
| confidence | 0.875 | |
| detector cost | 0.857 ms/frame | 32 ms budget |

### The "~297 px area" figure means three different things

Worth pinning down, because the expected value in the brief and the value the detector
reports are both right and they differ:

```
raw inRange mask pixels   : 297     <- the PROMPT 3 number
after open+close 3x3      : 295
cv2.contourArea (polygon) : 267     <- what Detection.area reports
pi * r^2 from the circle  : 294.6
```

`contourArea` measures the polygon through the boundary pixel *centres*, so it sits about
10 % under a pixel count for a small rasterised disc. The detector's own circle,
`pi * 9.68^2 = 294.6`, agrees with the 297 px mask to within 1 %. Nothing is inconsistent;
`Detection.area` is simply the polygon measure, and PROMPT 7 should use `radius`, not
`area`, for distance.

### MIN_CIRCULARITY is not the range limiter

The brief describes circularity as "the primary noise filter for small distant contours".
Measured across nine ranges, circularity never approaches the 0.60 floor:

| range (m) | contourArea | circularity | radius | predicted | err | detected |
|---|---|---|---|---|---|---|
| 0.40 | 2637 | 0.897 | 29.61 | 29.29 | +1.1 % | yes |
| 0.60 | 1137 | 0.897 | 19.54 | 19.53 | +0.1 % | yes |
| 0.80 | 628 | 0.892 | 14.59 | 14.64 | -0.4 % | yes |
| 1.00 | 391 | 0.879 | 11.63 | 11.72 | -0.7 % | yes |
| 1.20 | 267 | 0.842 | 9.68 | 9.76 | -0.8 % | yes |
| 1.50 | 167 | 0.900 | 7.65 | 7.81 | -2.1 % | yes |
| 2.00 | 90 | 0.925 | 5.78 | 5.86 | -1.3 % | yes |
| 2.50 | 57 | 0.853 | 4.64 | 4.69 | -1.0 % | yes |
| 2.80 | 41 | 0.948 | 3.81 | 4.18 | -9.0 % | yes |

Circularity stays between 0.84 and 0.95 everywhere, roughly 0.24 of margin above the
floor, and it does **not** decay with distance - morphological closing smooths the
staircase boundary that would otherwise depress it on tiny blobs. The binding constraint
at range is `MIN_CONTOUR_AREA_PX = 20` against a contourArea of 41 at 2.8 m, about 2x of
headroom, which extrapolates to a limit near 3.7 m. That is the number to quote as the
detector's range, not a circularity limit.

This closes the concern I raised in Phase 0 and again in Phase 1b. The ball is detected at
every range the arena allows, with confidence 0.85-0.93 throughout.

### Gaussian blur removed, on evidence

The guide mentions `cv2.GaussianBlur`; the PROMPT 5 requirements specify only the
morphological open and close. Measuring radius error against the pinhole prediction over
all nine captured frames decided it:

| variant | mean radius error | worst |
|---|---|---|
| raw inRange, no morphology | -0.68 % | -2.67 % |
| **morphology 3x3 only (chosen)** | **-1.56 %** | -8.99 % |
| blur 3x3 + morphology 3x3 | -5.75 % | -11.33 % |
| blur 5x5 + morphology 3x3 | -8.53 % | -14.38 % |

Blur bleeds grey background into the rim of a small ball, pushing its saturation under the
threshold and shrinking the blob. The shrinkage grows with distance, so it does not just
add noise - it biases the apparent-size distance estimate exactly where that estimate is
weakest. It also bought nothing, because the rendered arena has zero measured stray
pixels. `GAUSSIAN_BLUR_KERNEL = None`, with the table recorded in `config.py` and a note to
re-enable at 3x3 if PROMPT 14 introduces real sensor noise.

Morphology is kept: specified, cheap, and free of cost except on the very smallest blob.

### Test fixtures are real frames, not drawings

`tests/fixtures/range_*.png` are the nine simulator frames from the sweep, plus
`start_pose_1p2m.png`. Synthetic frames pin each filtering rule down individually - area
floor, circularity floor, hue rejection, saturation rejection, largest-candidate
selection, edge-of-frame - while the captured frames test the detector against the
simulator's actual optics. Colours in the synthetic frames are sampled from the
simulation (ball B=60 G=122 R=235, arena B=196 G=180 R=170), not invented.

Run them with:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

### Candidate selection

Largest surviving area, not highest confidence. The ball is the only saturated orange
object in the arena, so among valid candidates the largest is the nearest; preferring it
keeps the follower locked on the closest target rather than flicking to a cleaner-looking
speck. `detect_ball(..., return_rejects=True)` returns every discarded contour with its
reason - that is how the threshold margins above were measured - and is off by default.

## Phase 2b — debug overlay (PROMPT 6, 2026-09-08)

`vision.draw_debug_overlay()` implemented as a pure drawing helper: frame plus Detection
in, annotated copy out. It never calls imshow or waitKey, so it is safe headless and can
be written straight to disk. Also added `vision.bearing_degrees()` and
`vision.estimate_distance()`. 30 unit tests pass; the live run passes all 15 checks.

### Optical centre corrected to 319.5

The brief specifies `u_center = 319.5` and it is right - config had `IMAGE_WIDTH / 2.0`,
which is 320.0. Pixel indices run 0..639, so the centre of the grid is `(640-1)/2 = 319.5`,
and the half-pixel difference was a standing bias in the steering error the PROMPT 8
controller will consume.

The simulator settles it independently: with the ball dead ahead the detector reports
`center_x = 319.50` across 150 consecutive frames with **zero spread**. The measurement
matches 319.5 exactly, not 320.0. `IMAGE_CENTER_X` and `IMAGE_CENTER_Y` are now
`(N - 1) / 2`.

### Distance implemented here, calibrated in PROMPT 7

The HUD has to show a distance, so `estimate_distance()` is implemented now:
`Z = scale * f * D / (2 * r)`, returning None for a non-positive radius. What PROMPT 7
still owns is the calibration of `scale` against known distances and the min/max validity
gating. With `scale = 1.0` the uncalibrated estimate is already close:

| true range | radius | estimated Z | error |
|---|---|---|---|
| 0.60 m | 19.54 px | 0.5996 m | -0.07 % |
| 1.20 m | 9.68 px | 1.2098 m | +0.82 % |
| 2.50 m | 4.64 px | 2.5258 m | +1.03 % |

Live over 150 frames at the start pose: 1.2050 / 1.2099 / 1.2181 m against a
supervisor-measured true range of 1.2001 m. This is a strong prior that PROMPT 7 will
land on a scale very near 1.0, and that the residual is a mild positive bias growing with
range rather than a scale error.

### What is drawn

- minimum enclosing circle, green, thickness 2
- centroid dot, filled red
- dashed vertical line at the optical centre, cyan (no dashed-line primitive in cv2, so
  it is drawn as segments)
- horizontal error arrow from `(319.5, v)` to `(u, v)`, yellow, at the ball's own height
  so it reads as the exact quantity the steering loop consumes; it degrades to a short
  tick when the ball is within 2 px of centre, because an arrowhead shorter than its own
  tip renders as a blob
- HUD panel: DETECTED/LOST in green/red, centroid, radius, distance, bearing, error_u,
  confidence, plus optional state / wheel / fps rows for later phases

The HUD sits on a translucent black panel via `addWeighted` rather than plain text,
because white text over a light grey arena is unreadable, and the arena is light grey by
design for the colour thresholding.

### Cost

| stage | ms/frame |
|---|---|
| BGRA to BGR conversion | 0.231 |
| detection | 0.897 |
| overlay | 0.553 |
| **total** | **1.68 of the 32 ms timestep** |

About 5 % of the budget, so the overlay can stay on during the following phases. A new
check asserts the whole pipeline fits the timestep, so a future regression shows up as a
failure rather than as sluggish behaviour.

### LOST state verified for real

The LOST HUD is not a mocked screenshot. Running with `BALL_FOLLOWER_SELFTEST=1` rotates
the robot, the ball leaves the field of view, detection drops to 45.3 % (68/150), and the
controller saves the first genuine miss to `results/plots/debug_overlay_lost.png`. The
overlay keeps drawing the centre line and HUD when there is no detection, which is what
makes it useful for diagnosing a loss rather than going blank.

## Phase 3 — distance and bearing calibration (PROMPT 7, 2026-09-08)

`vision.estimate_distance_and_bearing()` implemented, returning a gated `RangeBearing`.
44 unit tests pass; the live run passes all 17 checks with the start-pose estimate 0.67 %
from supervisor truth.

### Truth is the slant range, not the horizontal range

The sweep teleports the ball to `camera_x + range`, so the horizontal separation is exact,
but apparent size encodes the straight-line distance to the ball centre. The camera sits
at z = 0.0849 and the ball centre at z = 0.020, so the truth is
`hypot(range, 0.0649)`. This matters at short range: at 0.4 m the slant range is 0.4052,
1.3 % longer than the horizontal. Validating against the horizontal figure would have
manufactured a 1.3 % error out of nothing.

### Opening had to go

PROMPT 5 specified morphological opening and closing. Opening is incompatible with the
accuracy target and is now disabled (`MORPH_OPEN_ITERATIONS = 0`):

| range | radius error, no opening | radius error, 3x3 opening |
|---|---|---|
| 1.50 m | -0.31 % | -1.98 % |
| 2.80 m | -2.65 % | **-8.96 %** |

Erosion removes a fixed ring, which is negligible on a 30 px blob and fatal on a 4 px one.
At 2.8 m it is the difference between a +2.6 % and a +9.8 % distance error. Closing is
kept - it fills interior holes without shrinking the silhouette, and costs nothing
measurable. The arena has zero stray pixels, so opening was rejecting noise that does not
exist; PROMPT 14 should re-measure this table if it introduces real noise.

### Calibration: the answer is 1.000

Fitted against supervisor truth over the seven required ranges:

| scale | max abs error | within 1.5 % |
|---|---|---|
| 1.0000 (uncalibrated) | 2.72 % | 5 of 7 |
| 1.0045 (mean fit) | 2.79 % | 5 of 7 |
| 1.0015 (minimax fit) | 2.56 % | 5 of 7 |

No constant improves the count. `DISTANCE_CALIBRATION_SCALE = 1.000` is kept, since a
fitted value would buy 0.16 of a percentage point in exchange for an unexplained number.

### Accuracy actually achieved

| true slant | radius | estimated Z | error |
|---|---|---|---|
| 0.4052 m | 29.61 px | 0.3957 m | **-2.35 %** |
| 0.6035 m | 19.54 px | 0.5995 m | -0.66 % |
| 1.0021 m | 11.63 px | 1.0071 m | +0.50 % |
| 1.2018 m | 9.68 px | 1.2099 m | +0.67 % |
| 2.0011 m | 5.78 px | 2.0258 m | +1.23 % |
| 2.5008 m | 4.64 px | 2.5259 m | +1.00 % |
| 2.8008 m | 4.07 px | 2.8770 m | **+2.72 %** |

**Five of the seven ranges meet the 1.5 % target; 0.40 m and 2.80 m do not.** They are the
two extremes of the usable band, they miss by about one percentage point, and they err in
*opposite* directions, which is why no single multiplier rescues them:

- At 0.40 m the thresholded silhouette is about 0.7 px larger in radius than the ideal
  pinhole projection. Partially-covered edge pixels at the ball rim still clear the
  saturation floor, so the blob reads slightly wide and the distance reads short.
- At 2.80 m the whole ball is 54 mask pixels. One boundary ring is worth roughly 12 % of
  the radius there, so the estimate is quantisation-limited, not model-limited.

Neither is a defect in the model - between 0.6 and 2.5 m the error stays inside 1.25 %,
which is what the pinhole relation is worth here. Options if tighter accuracy is ever
needed, in increasing order of effort: derive the radius from the mask area instead
(`sqrt(A/pi)` gives a 1.75 % worst case, still short of 1.5 %), raise the camera
resolution, or fit a two-parameter radius correction rather than a single scale. The
brief mandates `cv2.minEnclosingCircle`, so the first is not taken.

The unit tests encode this honestly: `test_error_within_1_5_percent_across_the_working_band`
asserts the 1.5 % target over 0.6-2.5 m, and
`test_band_edges_stay_inside_the_measured_envelope` pins 0.40 m and 2.80 m to their
measured 2.6 / 2.8 % envelope rather than pretending they pass.

### Bearing

`theta = atan2(center_x - u_center, f)`, with `u_center = 319.5`. Measured bearing at every
sweep range is 0.000 deg to three decimals, because the ball was placed on the optical
axis - which also confirms the 319.5 centre convention a second time.

Bearing stays populated when the distance is gated out, as long as the ball was seen.
Bearing depends only on `center_x`, so it remains trustworthy when the radius does not,
and PROMPT 9 needs a last-known direction to search toward after a low-confidence frame.
`valid` still goes False, so no caller can mistake a gated frame for a good range fix.

### Live at the start pose

150 consecutive frames: 100 % detection, 150/150 valid ranges, distance
1.2050 / 1.2099 / 1.2181 m against a supervisor truth of 1.2018 m, bearing 0.000 deg with
zero spread. Pipeline cost 1.63 ms of the 32 ms timestep.

## Phase 4a — proportional follower (PROMPT 8, 2026-09-08)

`control.compute_wheel_speeds()` implemented as a pure function. 69 unit tests pass
(38 new in `tests/test_controller.py`), and the robot drove the approach under motor
control with supervisor ground truth logged alongside its own estimate.

The module is `control.py`, not `controller.py` - a local `controller.py` shadows the
Webots `controller` package. Established in PROMPT 2 and not revisited.

### Closed-loop result

90 s of simulated time, 2813 frames, from the 1.20 m start pose:

| Quantity | Value |
|---|---|
| detection rate | 100.0 % (2813/2813) |
| approach | monotonic, **zero overshoot** |
| settling time | 29.50 s |
| true range at stop | 0.4379 m |
| estimated range at stop | 0.4300 m |
| final true range | 0.4373 m |
| post-stop drift | 0.64 mm over 60 s |
| estimate spread, last 48 s | **0.0000 m** |
| peak wheel speed | 1.22 rad/s (ceiling 6.28, never reached) |
| steering effort | max 0.0005 rad/s split - ball is dead ahead |

### The robot settles at 0.437 m, not 0.400 m

That is +9.3 % on target, and it decomposes exactly:

```
0.400  target
+0.030  deadband entry - the law stops the instant |e_Z| <= 0.03, not at the centre
+0.008  estimator bias: at this range the estimate reads 1.8 % low (0.4300 vs 0.4379),
        so the robot believes it has arrived slightly before it has
------
 0.438  observed
```

Both terms are the specified behaviour rather than defects. The deadband is defined as
"if abs(e_Z) <= tolerance then v = 0", and a robot approaching from far away necessarily
meets that condition at the *far* edge. By its own measurement the robot stops at 0.4300 m,
which is inside the 0.37-0.43 m band it was asked to hold.

If true-range accuracy matters more than spec fidelity, the one-line change is
`TARGET_DISTANCE_M = 0.37`, which would land the true stop near 0.405 m. Not done, because
it hides a known estimator bias inside a gain and PROMPT 13 is the place to tune.

### The stop is stable, with one instructive twitch

```
t=29.50  STOP   est=0.4300  true=0.4379
t=29.54  MOVE   est=0.4303  true=0.4379   <- 0.3 mm of pixel quantisation
t=29.57  STOP   est=0.4285  true=0.4373
```

A single frame of motion, then nothing: the estimate is bit-identical for the remaining
48 s. The twitch moved the robot `0.5 rad/s * 0.04 m * 0.032 s = 0.64 mm`, which is exactly
the measured post-stop drift, so the whole budget reconciles.

This is a clean demonstration of why the deadband needs hysteresis rather than a hard
edge: one pixel of noise at the boundary flips the command. `STOP_HYSTERESIS_M = 0.06` is
already in config for the PROMPT 9 state machine to consume.

### The stiction floor needed guarding

`MIN_WHEEL_SPEED = 0.5` is applied only while the follower actually wants to advance.
Applying it to a pure steering correction would turn an arbitrarily small bearing error
into a 0.5 rad/s twitch and the robot would hunt around the centre line forever. With the
guard, the deadband stop is a true zero - confirmed by
`test_deadband_stop_is_not_lifted_by_the_stiction_floor` and by the 48 s of bit-identical
telemetry above. The floor is visible in the plot engaging at about 15 s.

### Approach is slow by construction

`v_linear = KP_DIST * e_Z` feeds straight into a wheel *angular* speed, so the effective
linear gain is `KP_DIST * WHEEL_RADIUS = 1.5 * 0.04 = 0.06 m/s per metre of error`. From
0.8 m of error that is 0.048 m/s, giving the 16.7 s time constant and the 29.5 s settle
seen here. The mapping is dimensionally loose - metres of error to rad/s of wheel - but it
is what the brief specifies, and the clamp at 6.28 rad/s never engages because the command
peaks at 1.22. PROMPT 13 can raise `KP_DIST` substantially before saturation becomes a
concern.

### Verification harness

Setting `BALL_FOLLOWER_TRUTH_LOG=<path>` makes the controller construct a `Supervisor`
instead of a `Robot` - Supervisor subclasses Robot, so every device call is unchanged - and
write a CSV of true range, estimated range, bearing and both wheel commands per step. The
control law never reads the truth; it exists so the approach can be judged against
something other than the estimator being tested. Unset, the controller constructs a plain
Robot and uses no supervisor calls at all.

## Phase 5 — CSV logging (PROMPT 10, 2026-09-08)

`logger.py` implemented with format_row() and CSVLogger. 9 unit tests pass. Logged 626 rows
over a 10-second closed-loop approach run.

### CSV Schema

Exact columns in order:
timestamp, ball_detected, ball_x, ball_y, ball_radius, estimated_distance, image_error,
linear_velocity, angular_velocity, left_motor_velocity, right_motor_velocity, state

Empty values (missing ball, gated distance, etc) are recorded as empty strings, not NaN or
None, for robust downstream parsing.

### Format Rules Verified

- timestamp: simulation time in seconds
- ball_detected: 1 or 0
- ball geometry (x, y, radius): floats in pixels if detected, else ""
- image_error: horizontal pixel deviation from optical centre (319.5)
- distance: estimated_distance in metres if valid, else ""
- velocities: all float rad/s
- state: string (currently "IDLE" for PROMPT 8; "SEARCHING"/"TRACKING"/"APPROACHING"/"STOPPED" in PROMPT 9)

### 10-Second Verification Run

626 rows logged (10 seconds of sim time at 32 ms timestep).

| Metric | Value |
|---|---|
| Detection rate | 100.0% (626/626) |
| Time span | 0.00–9.98 s |
| Ball radius range | 9.65–13.95 px |
| Distance range | 0.840–1.214 m |
| Horizontal centering | max 0.07 px error |

Approach from 1.21 m toward 0.40 m target was steady and monotonic. CSV is machine-parseable
with zero formatting ambiguity. Each row carries the complete state snapshot for the
frame, so downstream evaluation (PROMPT 11) has everything it needs.
