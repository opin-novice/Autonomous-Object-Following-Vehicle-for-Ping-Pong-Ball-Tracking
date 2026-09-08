# CLAUDE.md — Autonomous Object-Following Vehicle (Ping Pong Ball Tracking)

## Project

Webots simulation of a differential-drive vehicle that detects an orange ping-pong ball
with a front RGB camera, processes the image with OpenCV, and continuously follows the
ball using proportional steering plus distance-based speed control.

The authoritative specification is `A_TO_Z_IMPLEMENTATION.md`. Read it before making
architectural decisions. This file records the operating rules and the verified state of
the machine.

## Operating rules

1. This is a Webots + Python + OpenCV project.
2. Do not introduce ROS 2 or Gazebo.
3. Prefer simple, explainable implementations.
4. Never fabricate experiment results.
5. Never claim a simulation works without running it.
6. Inspect Webots errors before modifying unrelated code.
7. Keep configuration parameters separate from algorithms — all tunables live in `config.py`.
8. Keep vision and control modules separate.
9. Use meaningful variable names.
10. Add comments only where they explain non-obvious logic.
11. Prefer deterministic simulation settings.
12. Save experiment results to CSV.
13. Keep generated plots in `results/plots`.
14. Keep temporary files out of the repository.
15. Do not rewrite working modules unnecessarily.
16. After every major change, run a smoke test.
17. If a Webots API is uncertain, consult the installed Webots documentation/examples rather than guessing.
18. Prioritize a working MVP over optional features.

## Verified environment (checked 2026-09-08)

| Component | Status |
|---|---|
| **Webots R2025a** | **installed and verified running headless** |
| `WEBOTS_HOME` | `C:\Users\USER\Webots` |
| Webots binary | `C:\Users\USER\Webots\msys64\mingw64\bin\webots.exe` |
| Python 3.12.10 | project venv at `.venv/` |
| NumPy 2.5.3 | in venv |
| OpenCV 5.0.0 | in venv |
| Matplotlib 3.11.1 | in venv |
| Git 2.51.1 | installed |
| Node.js 22.21.0 | installed |

Version confirmed from `resources/version.txt`. Offline docs are **not** shipped with this
install (`docs/` contains only `list.txt`), so rule 17 means consulting
`WEBOTS_HOME/projects/**` examples and the shipped binaries, not a local manual.

## Verified Webots facts

These were established by experiment, not assumption. Do not re-litigate them.

**The Python API is ctypes-based and interpreter-agnostic.**
`WEBOTS_HOME/lib/controller/python/controller/` contains only `.py` files — no
version-locked `.pyd`. `from controller import Robot, Camera, Motor` imports cleanly under
the 3.12 venv alongside `cv2` and `numpy`.

**Interpreter selection is the real hazard.** Webots picks the controller interpreter from
its `pythonCommand` preference (registry:
`HKCU:\SOFTWARE\Cyberbotics\Webots-R2025a\General`), which defaults to `python`. On the
persisted machine PATH that resolves to `C:\Python314\python.exe`, which carries
**OpenCV 4.13.0 / NumPy 2.3.5** — a different OpenCV major version from the venv's 5.0.0.
A shell with the venv activated hides this, because `python` then means the venv. Do not
trust a "it worked in my terminal" result for this.

**`runtime.ini` pins it, and the path must be absolute.** Measured with a probe controller
under a cleaned PATH:

| Configuration | Interpreter used |
|---|---|
| no `runtime.ini` | `C:\Python314\python.exe`, cv2 4.13.0 |
| `[python] COMMAND` relative | controller fails to start |
| `[python] COMMAND` absolute | `.venv\Scripts\python.exe`, cv2 5.0.0 |

`webots/controllers/ball_follower/runtime.ini` therefore holds an **absolute** path. If the
project is ever moved, that line must be updated or the controller silently runs against
the wrong OpenCV.

**Headless runs work and are the fast feedback loop.** A world runs to completion in ~2 s:

```powershell
webots.exe --batch --mode=fast --no-rendering --minimize "<absolute world path>"
```

Two gotchas: the world path contains a space, so it must be quoted as a single argument or
Webots exits 1 immediately; and Webots is a GUI-subsystem app, so **controller stdout
cannot be captured through a pipe** — have the controller write to a file when output needs
to be read back programmatically.


**Webots geometry and modelling facts, measured in PROMPT 2.**

- A `Cylinder`'s axis is its local **Z**, not Y. A wheel cylinder must sit inside
  `Pose { rotation 1 0 0 1.5708 }` or it is a horizontal disc and the chassis grounds out.
- A child `Solid` with **no `Physics` node does not collide.** Passive contact geometry
  (the caster) must live in the parent's own `boundingObject`, not in a child Solid.
- A local `controller.py` **shadows the Webots `controller` package**, because Webots puts
  the controller's own directory first on `sys.path`. The control module is therefore named
  `control.py`. Never reintroduce `controller.py` in a controller directory.
- Open-loop rotation runs about 11% under the ideal `omega = R*(w_r - w_l)/L` because the
  caster scrubs. Do not treat the mixer as exact; the follower is closed-loop.

## Unit tests

`tests/test_vision.py` covers the detector with no simulator involved:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

78 tests, all passing (vision + controller + logger) (`test_vision.py` + `test_controller.py`). Fixtures in `tests/fixtures/` are real captured frames from the
simulator across nine ranges. Run these before any Webots run - they are a hundred times
faster and catch most detector regressions.

**Measured detector facts.** Circularity sits at 0.84-0.95 at every range from 0.4 to
2.8 m, never near the 0.60 floor, so `MIN_CIRCULARITY` is not what limits range -
`MIN_CONTOUR_AREA_PX` is, extrapolating to about 3.7 m. The optical centre is 319.5, not
320.0 - `(N-1)/2`, confirmed by 150 frames of zero-spread measurement. `Detection.area` is
`cv2.contourArea`, a polygon measure ~10% under the raw mask pixel count; use `radius` for
distance work. Gaussian blur is disabled on evidence - it biased radius by -5.75% mean and
the bias grew with distance. Morphological **opening** is disabled too: it cost -8.96%
radius at 2.8 m against -2.65% without it. Closing is kept.

**Distance accuracy is 1.5% over 0.6-2.5 m, and about 2.7% at the 0.4 m and 2.8 m band
edges.** The two edges err in opposite directions, so no calibration constant fixes both;
`DISTANCE_CALIBRATION_SCALE` stays 1.000. Validate against the *slant* range
`hypot(horizontal, 0.0649)`, never the horizontal range. See docs/implementation_notes.md.

## Smoke test

`webots/worlds/motion_check.wbt` plus the `motion_check` controller drive the robot
straight, rotate it in place, and check the result against the PROTO geometry, writing
`results/logs/motion_check.txt`. Run it after any change to the robot, the wheel geometry
or `config.py`:

```powershell
& "C:\Users\USER\Webots\msys64\mingw64\bin\webots.exe" --batch --mode=fast --no-rendering --minimize "d:\Autonomous Car\webots\worlds\motion_check.wbt"
```

Last run: ALL PASS - travel error -0.0%, resting pitch +0.06 deg, camera height 0.0849 m.

`webots/worlds/ping_pong_follower.wbt` + the `world_check` controller verify the arena,
the ball, the repeatability of the initial configuration and colour separability, writing
`results/logs/world_check.txt`. Last run: ALL PASS, 16 checks.

The main world now runs `"ball_follower"`. Select `"world_check"` temporarily to re-verify
the arena.

`ball_follower` profiles its own camera pipeline over the first 150 frames into
`results/logs/camera_check.txt`. Last run: ALL PASS, 11 checks.

Environment overrides for automated runs: `BALL_FOLLOWER_HEADLESS` (no cv2 window),
`BALL_FOLLOWER_RUN_SECONDS` (bounded run), `BALL_FOLLOWER_SELFTEST` (rotate during
diagnostics so frame freshness is testable).

**`--no-rendering` is safe for camera work** - verified byte-identical frame differences
with and without it. Camera devices render independently of the main 3D view.

## Phase status

| Phase | Scope | State |
|---|---|---|
| 0 | Skeleton, config, CLAUDE.md, venv, environment verification | done |
| 1a | Robot PROTO + minimal world + motion smoke test (PROMPT 2) | done, verified |
| 1b | Arena + ball + repeatable initial config (PROMPT 3) | done, verified |
| 1c | Camera acquisition loop + BGRA pipeline (PROMPT 4) | done, verified |
| 2a | OpenCV detector + unit tests (PROMPT 5) | done, verified |
| 2b | Debug overlay + HUD (PROMPT 6) | done, verified |
| 3 | Distance + bearing calibration (PROMPT 7) | done, verified |
| 4a | Proportional following controller (PROMPT 8) | done, verified |
| 4b | Ball-lost FSM (PROMPT 9) | not started |
| 5 | CSV logging (PROMPT 10) | done, verified |
| 6 | Evaluation + plots (PROMPT 11-12) | not started |
| 6 | Tuning, robustness, cleanup (PROMPT 13–15) | not started |

## Skeleton convention

Every function body outside `config.py` currently raises `NotImplementedError` with the
phase that will fill it in. This is deliberate: the interfaces are fixed, no algorithm is
pretended to exist. Replace stubs phase by phase — do not leave a half-written body that
looks implemented.

## Module boundaries

- `config.py` — parameters only. No logic, no imports from the other modules.
- `vision.py` — image in, `Detection` out. Knows nothing about motors or Webots.
- `control.py` — `Detection` + distance in, wheel velocities out. Knows nothing about OpenCV.
  **Not** named `controller.py`: that shadows the Webots `controller` package (see below).
- `ball_follower.py` — the only module that talks to the Webots API. Wires the others together.

Keeping `vision.py` free of Webots imports is what makes it testable without the simulator.
