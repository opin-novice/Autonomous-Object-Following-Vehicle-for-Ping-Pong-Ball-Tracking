# A-to-Z Implementation Plan
## Autonomous Object-Following Vehicle for Ping Pong Ball Tracking
### Stack: Webots + Python + OpenCV + Claude Code
### Platform: Windows 10/11
### Deadline: 12:00 AM

---

## 0. Objective

Build a complete Webots simulation of a small differential-drive autonomous vehicle that:

1. Uses a simulated RGB camera.
2. Detects a colored ping-pong ball using OpenCV.
3. Finds the ball center and apparent radius.
4. Estimates relative distance from the ball using its apparent size.
5. Controls left/right wheel velocities.
6. Continuously follows the ball.
7. Stops when the ball is too close.
8. Searches for the ball when it temporarily disappears.
9. Logs tracking/control data.
10. Produces plots and basic quantitative evaluation.

The priority is a **working, demonstrable MVP first**, followed by robustness and presentation improvements.

---

# 1. Final Technology Stack

Use only this stack unless a dependency is genuinely required:

- Webots R2025a or current stable Webots release
- Python 3.11.x preferred
- OpenCV (`opencv-python`)
- NumPy
- Matplotlib
- Git
- Claude Code
- VS Code optional

Do NOT add ROS 2, Gazebo, MATLAB, Docker, or other robotics frameworks for this submission.

Webots is an open-source, multi-platform robot simulator and supports Python robot controllers, cameras, motors, physics, and custom environments. Official documentation also provides Python controller guidance and project structure documentation.

---

# 2. Windows Installation

## 2.1 Install Webots

Download and install Webots from the official Cyberbotics website:

https://www.cyberbotics.com/

Use the current stable Windows release.

After installation, launch Webots once manually.

Verify:

- Webots opens.
- A sample world can run.
- The 3D renderer works.
- No graphics-driver error appears.

---

## 2.2 Install Python

Install Python 3.11.x for Windows.

During installation:

- Enable `Add Python.exe to PATH`.
- Prefer the standard 64-bit installer.

Verify in PowerShell:

```powershell
python --version
```

Expected:

```text
Python 3.11.x
```

Also verify:

```powershell
pip --version
```

---

## 2.3 Create the project virtual environment

Create a project directory:

```powershell
mkdir ping_pong_follower
cd ping_pong_follower
```

Create a virtual environment:

```powershell
python -m venv .venv
```

Activate it:

```powershell
.venv\Scripts\activate
```

Upgrade pip:

```powershell
python -m pip install --upgrade pip
```

Install dependencies:

```powershell
pip install numpy opencv-python matplotlib
```

Verify:

```powershell
python -c "import cv2, numpy, matplotlib; print('OpenCV:', cv2.__version__); print('NumPy:', numpy.__version__)"
```

---

# 3. Install Git

Install Git for Windows:

https://git-scm.com/

Verify:

```powershell
git --version
```

Initialize the project:

```powershell
git init
```

Create the first commit later after the MVP works.

---

# 4. Install Claude Code

Claude Code supports Windows through native Windows/Git Bash as well as WSL. For this Webots project, use the simplest setup that works on your machine: native Windows + Git for Windows/Git Bash.

Claude Code requires Node.js 18+.

Check:

```powershell
node --version
npm --version
```

If Node.js is missing, install a current LTS version from:

https://nodejs.org/

Then install Claude Code:

```powershell
npm install -g @anthropic-ai/claude-code
```

Verify:

```powershell
claude --version
```

Run:

```powershell
claude doctor
```

Authenticate when prompted.

Then enter the project directory:

```powershell
cd path\to\ping_pong_follower
claude
```

Official Claude Code documentation:
https://docs.anthropic.com/en/docs/claude-code/getting-started

---

# 5. Important Claude Code Rule

Do NOT give Claude one enormous instruction and blindly accept everything.

Use staged development.

The correct loop is:

```text
Ask Claude
    ↓
Claude edits files
    ↓
Run simulation
    ↓
Inspect result
    ↓
Report actual error/result
    ↓
Claude fixes it
    ↓
Run again
```

Never claim a feature works until Webots actually runs it.

---

# 6. Target Project Architecture

Create this structure:

```text
ping_pong_follower/
│
├── README.md
├── requirements.txt
├── .gitignore
├── CLAUDE.md
│
├── webots/
│   ├── worlds/
│   │   └── ping_pong_follower.wbt
│   │
│   ├── controllers/
│   │   └── ball_follower/
│   │       ├── ball_follower.py
│   │       ├── vision.py
│   │       ├── controller.py
│   │       └── config.py
│   │
│   ├── protos/
│   │   └── PingPongFollowerRobot.proto
│   │
│   └── textures/
│
├── scripts/
│   ├── run_evaluation.py
│   └── plot_results.py
│
├── results/
│   ├── logs/
│   └── plots/
│
└── docs/
    └── implementation_notes.md
```

Claude may adjust this structure if Webots requires a different arrangement, but keep the project modular.

---

# 7. Robot Design

Build a small differential-drive robot.

Required components:

```text
                 FRONT
                   ↑
             ┌───────────┐
             │   CAMERA  │
             └───────────┘
             ┌───────────┐
             │  CHASSIS  │
             │           │
        O────┤           ├────O
       LEFT  │           │ RIGHT
      WHEEL  │           │ WHEEL
             └───────────┘
```

Robot requirements:

- Two independently controlled drive wheels.
- One passive support caster or simple stable body contact.
- RGB camera mounted at the front.
- Camera faces approximately horizontally.
- Realistic wheel separation.
- Reasonable mass/inertia.
- Ground contact and friction.

Use Webots physics rather than teleporting the robot.

---

# 8. Simulation World

Create a simple indoor test environment.

Requirements:

- Flat floor.
- Walls around the arena.
- Neutral background.
- Adequate lighting.
- One ping-pong ball.
- Robot starting approximately 1–3 meters from the ball.
- Enough room for the robot to turn.

The ping-pong ball should be visually distinctive.

Use a bright orange or another saturated color.

Do NOT depend on Webots recognition/object-recognition features for the primary detector. The project requirement is computer vision, so the controller should actually process the camera image with OpenCV.

---

# 9. Camera Configuration

Use a simulated RGB camera.

Suggested initial settings:

```text
Width:       640
Height:      480
FOV:         approximately 1.0 rad
FPS:         compatible with simulation timestep
```

The camera image must be passed to OpenCV.

The processing pipeline should be:

```text
Webots Camera
      ↓
Camera image
      ↓
Convert to NumPy/OpenCV image
      ↓
BGR/HSV conversion
      ↓
Color threshold
      ↓
Morphological filtering
      ↓
Contour detection
      ↓
Largest valid circular contour
      ↓
Ball center + radius
```

---

# 10. Computer Vision Algorithm

Implement the ball detector in:

```text
webots/controllers/ball_follower/vision.py
```

Use HSV segmentation.

Basic logic:

```python
hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

mask = cv2.inRange(
    hsv,
    lower_color,
    upper_color
)
```

Apply:

```python
cv2.GaussianBlur()
cv2.morphologyEx(..., cv2.MORPH_OPEN, ...)
cv2.morphologyEx(..., cv2.MORPH_CLOSE, ...)
```

Find contours:

```python
contours, _ = cv2.findContours(
    mask,
    cv2.RETR_EXTERNAL,
    cv2.CHAIN_APPROX_SIMPLE
)
```

For every contour:

- Calculate area.
- Calculate perimeter.
- Calculate minimum enclosing circle.
- Calculate circularity.

Circularity:

```text
C = 4πA / P²
```

Reject contours that are:

- too small
- too large
- insufficiently circular
- outside reasonable camera bounds

Select the best valid candidate.

Return:

```text
detected
center_x
center_y
radius
area
confidence
```

---

# 11. Distance Estimation

Use apparent ball radius as a simple distance proxy.

For a pinhole camera:

```text
Z ≈ f * D / d
```

where:

- Z = estimated distance
- f = focal length in pixels
- D = actual ball diameter
- d = observed ball diameter in pixels

For the first working version, it is acceptable to use:

```text
distance ∝ 1 / radius
```

Then calibrate the constant using known simulation distances.

Do not present this as highly accurate physical ranging.

In the report call it:

**monocular apparent-size-based distance estimation**.

---

# 12. Tracking Logic

Calculate horizontal image error:

```text
error_x = ball_center_x - image_center_x
```

Normalize:

```text
normalized_error = error_x / (image_width / 2)
```

Therefore:

```text
-1 → ball far left
 0 → ball centered
+1 → ball far right
```

Use this error for steering.

---

# 13. Motion Controller

Implement the first controller as proportional control.

```text
angular_command = Kp * normalized_error
```

Forward speed should depend on estimated distance.

Conceptually:

```text
far ball   → faster
near ball  → slower
very near  → stop
```

Example control structure:

```text
linear_speed = distance_controller(distance)
angular_speed = steering_controller(error_x)
```

Convert:

```text
v = linear velocity
ω = angular velocity

left_wheel_speed  = (v - ωL/2) / R
right_wheel_speed = (v + ωL/2) / R
```

where:

- L = wheel separation
- R = wheel radius

Clamp both wheel speeds to the motor's maximum velocity.

---

# 14. Ball-Lost Behavior

This is important for robustness.

If the ball is not detected for a short period:

```text
0–0.5 sec:
    continue cautiously

0.5–2 sec:
    slow down

> 2 sec:
    rotate/search
```

Search direction can use the last known ball position.

For example:

```text
last ball left  → rotate left
last ball right → rotate right
unknown         → rotate slowly
```

Stop searching when detection resumes.

---

# 15. Safety / Behavior States

Implement a simple finite-state machine:

```text
SEARCHING
    ↓
TRACKING
    ↓
APPROACHING
    ↓
STOPPED
```

Possible transitions:

```text
SEARCHING → TRACKING
    when ball detected

TRACKING → APPROACHING
    when ball is detected and far away

APPROACHING → STOPPED
    when distance <= stop_distance

TRACKING → SEARCHING
    when ball is lost
```

This is better than putting everything into one large `if/else`.

---

# 16. Visualization

During development, generate a debug camera image.

Overlay:

- Ball bounding circle.
- Ball center.
- Image center line.
- Horizontal error.
- Estimated distance.
- Detection confidence.
- Current state.
- Left motor speed.
- Right motor speed.

Example:

```text
┌───────────────────────────────┐
│             │                 │
│             │      ○         │
│             │    Ball        │
│             │                 │
│─────────────┼─────────────────│
│             │                 │
│             │                 │
├───────────────────────────────┤
│ Error: +0.23                  │
│ Distance: 1.24 m              │
│ State: TRACKING               │
│ Left:  4.1 rad/s              │
│ Right: 6.0 rad/s              │
└───────────────────────────────┘
```

Use this primarily for debugging and demonstration.

---

# 17. Logging

Log at every simulation timestep or at a controlled frequency.

Save CSV:

```text
timestamp
ball_detected
ball_x
ball_y
ball_radius
estimated_distance
image_error
linear_velocity
angular_velocity
left_motor_velocity
right_motor_velocity
state
```

File:

```text
results/logs/tracking_log.csv
```

---

# 18. Evaluation

Create at least these experiments:

### Experiment 1 — Static Ball

Robot starts approximately 2 m away.

Measure:

- detection success
- time to approach
- final distance
- final horizontal error

### Experiment 2 — Ball Moving Left/Right

Move the ball laterally.

Measure:

- tracking error
- steering response
- recovery

### Experiment 3 — Ball Approaching Robot

Move ball toward robot.

Measure:

- speed reduction
- stopping behavior
- minimum distance

### Experiment 4 — Ball Lost

Temporarily hide or move the ball outside the camera FOV.

Measure:

- recovery time
- search behavior

### Experiment 5 — Curved / Dynamic Motion

Move ball along a curved path.

Measure:

- trajectory tracking
- success rate

---

# 19. Metrics

At minimum calculate:

```text
Detection Rate
Tracking Success Rate
Mean Horizontal Error
Mean Absolute Error
Maximum Error
Average FPS
Average Response Time
Final Distance Error
Ball-Lost Recovery Time
```

Useful definitions:

```text
Detection Rate =
detected frames / total frames
```

```text
MAE =
mean(abs(error_x))
```

---

# 20. Plots

Use Matplotlib.

Create:

1. Horizontal tracking error vs time.
2. Estimated distance vs time.
3. Left/right motor velocity vs time.
4. Ball x-position vs image center.
5. Detection status vs time.

Save them to:

```text
results/plots/
```

Example:

```text
tracking_error.png
distance.png
motor_velocities.png
detection_status.png
```

---

# 21. Claude Code Development Sequence

Do NOT ask Claude to build everything at once.

Use these prompts sequentially.

---

## PROMPT 1 — Project initialization

Paste this into Claude Code:

```text
You are the lead robotics software engineer for this project.

Build a Webots + Python + OpenCV simulation called:

"Autonomous Object-Following Vehicle for Ping Pong Ball Tracking"

Target platform: Windows.
Do not use ROS 2 or Gazebo.

First inspect the current project directory.

Create a clean Webots project structure and CLAUDE.md.

Requirements:
- differential-drive robot
- front RGB camera
- ping-pong ball
- Python controller
- OpenCV-based ball detection
- modular code
- configuration separated from logic
- Git-friendly structure

Do not implement everything yet.

First create the project skeleton and explain what files you created.
Do not claim the simulation works until it has actually been run.
```

---

## PROMPT 2 — Build robot

```text
Implement the differential-drive robot in Webots.

Requirements:
- two independently controlled wheels
- stable chassis
- front-mounted RGB camera
- realistic dimensions and mass
- physics enabled
- named devices clearly
- motors accessible from Python

Create a minimal world where the robot can drive forward and rotate.

Run the simulation and verify that the robot actually moves.

Fix any Webots errors before proceeding.
```

---

## PROMPT 3 — Add ball and world

```text
Add the ping-pong ball and a simple indoor arena.

Requirements:
- visually distinctive orange ball
- physically simulated sphere
- floor
- surrounding walls
- reasonable lighting
- robot starts several meters from the ball

Create a repeatable initial configuration.

Run the simulation and verify that both robot and ball exist and physics behave correctly.
```

---

## PROMPT 4 — Camera

```text
Implement the Webots camera controller.

Requirements:
- RGB image
- 640x480 preferred
- continuous image acquisition
- convert Webots image data into an OpenCV-compatible NumPy array
- create a debug view

Verify the camera image is valid before implementing detection.

If the Webots image format is different from expected, inspect the actual API and fix the conversion.
```

---

## PROMPT 5 — OpenCV detector

```text
Implement robust ping-pong ball detection using OpenCV.

Use:
- HSV color segmentation
- morphological opening/closing
- contour extraction
- area filtering
- circularity filtering
- minimum enclosing circle

Return:
detected
center_x
center_y
radius
area
confidence

Keep the detector independent from the robot controller.

Add unit-testable helper functions where practical.

Run the simulation and verify that the ball is detected.
```

---

## PROMPT 6 — Debug visualization

```text
Add a camera debug overlay.

Show:
- detected ball circle
- ball center
- image center
- horizontal error
- radius
- detection confidence

Make the debug output easy to inspect.

Do not modify robot motion yet.
```

---

## PROMPT 7 — Distance estimation

```text
Implement apparent-size-based monocular distance estimation.

Use:

Z = f * D / d

where appropriate.

Create configurable parameters for:
- ball diameter
- camera focal length
- calibration constant
- minimum and maximum valid distance

If exact camera calibration is unavailable, implement a clearly documented approximate calibration procedure using known Webots distances.

Validate the estimated distance at several known positions.
```

---

## PROMPT 8 — Controller

```text
Implement the differential-drive following controller.

Inputs:
- ball horizontal error
- estimated distance
- detection state

Outputs:
- left wheel velocity
- right wheel velocity

Use proportional steering first.

Behavior:
- ball left -> steer left
- ball right -> steer right
- ball centered -> move forward
- ball far -> move faster
- ball close -> slow down
- ball inside stop distance -> stop

Keep all gains and limits configurable.
```

---

## PROMPT 9 — Ball-lost behavior

```text
Implement robust ball-lost behavior.

Create a finite-state machine with:
SEARCHING
TRACKING
APPROACHING
STOPPED

When the ball disappears:
- briefly maintain safe motion
- slow down
- search using the last known direction
- resume tracking immediately when detected

Prevent excessive oscillation.
```

---

## PROMPT 10 — Logging

```text
Add CSV logging.

Log:
timestamp
ball_detected
ball_x
ball_y
ball_radius
estimated_distance
image_error
linear_velocity
angular_velocity
left_motor_velocity
right_motor_velocity
state

Save to results/logs/tracking_log.csv.

Make the logging system robust to simulation resets.
```

---

## PROMPT 11 — Evaluation scripts

```text
Create automated evaluation scripts for:
1. static ball
2. lateral movement
3. approaching ball
4. ball lost
5. curved/dynamic motion

Calculate:
- detection rate
- tracking success rate
- MAE
- maximum error
- response time
- final distance error
- recovery time

Do not fabricate results.
Only report values from actual simulation logs.
```

---

## PROMPT 12 — Plots

```text
Create Matplotlib plotting scripts.

Generate:
- tracking error vs time
- distance vs time
- left/right motor speed vs time
- ball x position vs image center
- detection status vs time

Save figures to results/plots/.

Use clean publication/report-friendly labels and units.
```

---

## PROMPT 13 — Tuning

```text
Run the complete simulation.

Inspect the tracking behavior.

Tune:
- steering Kp
- forward speed
- distance gain
- stop distance
- maximum wheel velocity
- search speed

The objective is smooth following with minimal oscillation.

Do not simply increase speed.

Run multiple trials and compare results.
```

---

## PROMPT 14 — Robustness

```text
Stress-test the simulation.

Test:
- ball far away
- ball close
- ball moving left
- ball moving right
- ball temporarily hidden
- ball near image edge
- rapid ball movement
- false colored objects if available

Identify failure modes.

Fix only genuine problems.

Keep the implementation simple enough to explain in a university project.
```

---

## PROMPT 15 — Final cleanup

```text
Perform a complete engineering review.

Check:
- Python syntax
- Webots project structure
- controller paths
- device names
- imports
- configuration
- logging
- evaluation scripts
- plots
- README
- reproducibility

Run the simulation from a clean state.

Fix all errors.

Do not add unnecessary features.
```

---

# 22. Final README Requirements

Ask Claude:

```text
Write a professional README for the project.

Include:
- project title
- objective
- architecture
- technology stack
- robot design
- computer vision pipeline
- control strategy
- how to install
- how to run
- how to reproduce experiments
- evaluation metrics
- limitations
- future improvements

Do not claim real-world validation because this is a simulation.
```

---

# 23. Suggested System Architecture for the Report

Use this architecture:

```text
                ┌─────────────────┐
                │ Webots Camera   │
                └────────┬────────┘
                         │
                         ▼
                ┌─────────────────┐
                │ OpenCV          │
                │ HSV Segmentation│
                │ + Contours      │
                │ + Circularity   │
                └────────┬────────┘
                         │
                  Ball x, radius
                         │
                         ▼
                ┌─────────────────┐
                │ State Estimator │
                │                 │
                │ Distance        │
                │ Position Error  │
                └────────┬────────┘
                         │
                         ▼
                ┌─────────────────┐
                │ Controller      │
                │                 │
                │ P Steering      │
                │ Speed Control   │
                └────────┬────────┘
                         │
                  Left / Right
                   wheel speeds
                         │
                         ▼
                ┌─────────────────┐
                │ Differential    │
                │ Drive Robot     │
                └────────┬────────┘
                         │
                         ▼
                  Robot Motion
                         │
                         └───────► Camera feedback
```

---

# 24. Minimum Viable Product

If time becomes limited, STOP adding features.

The MVP must have:

- [x] Webots world
- [x] Differential-drive robot
- [x] Camera
- [x] Ping-pong ball
- [x] OpenCV detection
- [x] Ball center calculation
- [x] Left/right motor control
- [x] Ball following
- [x] Basic debug visualization

Everything else is secondary.

---

# 25. Time Plan for a 12 AM Deadline

Assuming work starts around 1:30 PM:

### 1:30–2:00
Install:

- Webots
- Python
- Git
- Node.js if needed
- Claude Code

### 2:00–2:30
Create project + initialize Claude Code.

### 2:30–4:00
Robot + world + physics.

### 4:00–5:00
Camera + ball.

### 5:00–6:30
OpenCV detection.

### 6:30–8:00
Following controller.

### 8:00–9:00
Ball-lost behavior + tuning.

### 9:00–10:00
Logging + evaluation.

### 10:00–11:00
Plots + README + cleanup.

### 11:00–11:30
Final demo and screenshots/video.

### 11:30–12:00
Package everything and submit.

Do not spend the final hour adding new features.

---

# 26. Claude Code Operating Rules

Put these rules into CLAUDE.md:

```text
# Claude Code Rules

1. This is a Webots + Python + OpenCV project.
2. Do not introduce ROS 2 or Gazebo.
3. Prefer simple, explainable implementations.
4. Never fabricate experiment results.
5. Never claim a simulation works without running it.
6. Inspect Webots errors before modifying unrelated code.
7. Keep configuration parameters separate from algorithms.
8. Keep vision and control modules separate.
9. Use meaningful variable names.
10. Add comments only where they explain non-obvious logic.
11. Prefer deterministic simulation settings.
12. Save experiment results to CSV.
13. Keep generated plots in results/plots.
14. Keep temporary files out of the repository.
15. Do not rewrite working modules unnecessarily.
16. After every major change, run a smoke test.
17. If a Webots API is uncertain, consult the installed Webots documentation/examples rather than guessing.
18. Prioritize a working MVP over optional features.
```

---

# 27. Final Demo Checklist

Before submission verify:

```text
[ ] Webots opens the world
[ ] Robot appears
[ ] Ball appears
[ ] Camera works
[ ] OpenCV detects ball
[ ] Ball center is correct
[ ] Robot turns toward ball
[ ] Robot follows ball
[ ] Robot slows near ball
[ ] Robot stops at target distance
[ ] Robot searches when ball is lost
[ ] No Python errors
[ ] No Webots controller errors
[ ] CSV log is generated
[ ] Plots are generated
[ ] README exists
[ ] Screenshots captured
[ ] Demo video captured if required
```

---

# 28. Recommended Final Submission Contents

```text
submission/
│
├── source_code/
│   └── ping_pong_follower/
│
├── README.md
├── requirements.txt
│
├── results/
│   ├── tracking_log.csv
│   └── plots/
│
├── screenshots/
│   ├── simulation.png
│   ├── camera_detection.png
│   └── robot_following.png
│
└── demo.mp4
```

---

# 29. Final Technical Description

Use this as the concise technical description:

The proposed system is a simulated autonomous differential-drive vehicle designed to detect and follow a ping-pong ball in real time. A Webots RGB camera provides the visual input, which is processed using OpenCV. The ball is detected using HSV-based color segmentation, morphological filtering, contour analysis, and circularity constraints. The detected ball centroid is used to calculate the horizontal image-space tracking error, while the apparent ball size provides an approximate distance estimate. A feedback controller converts the visual error and estimated distance into linear and angular velocity commands, which are transformed into independent left and right wheel velocities for the differential-drive robot. A finite-state controller handles tracking, approaching, stopping, and ball-loss recovery. The system is evaluated using detection rate, tracking error, response time, distance error, and recovery time.

---

# 30. Emergency Fallback

If the full system is not working by approximately 8:00 PM:

Do NOT attempt major architectural changes.

Reduce the project to:

```text
Webots
  ↓
Robot + Camera
  ↓
OpenCV color detection
  ↓
Ball center
  ↓
P controller
  ↓
Differential drive
```

Remove:

- sophisticated distance estimation
- advanced FSM
- automated experiment generation
- multiple test scenarios

A working simple simulation is better than an unfinished sophisticated one.

---

# 31. First Command to Give Claude Code

After opening Claude Code in the project directory, paste:

```text
Read the file A_TO_Z_IMPLEMENTATION.md completely.

You are responsible for implementing this project in Webots using Python and OpenCV.

First inspect my current environment and project directory.

Then:
1. Verify Webots/Python availability.
2. Verify the Python dependencies.
3. Create the project structure.
4. Create CLAUDE.md.
5. Implement only Phase 1: the basic Webots world, differential-drive robot, camera, and ping-pong ball.
6. Run a smoke test.
7. Report exactly what worked and any errors.

Do not jump ahead to later phases until Phase 1 is actually working.

Do not fabricate results.
```

Then proceed through the numbered prompts in this document.

---

# 32. Success Criterion

The project is considered successful when:

> The simulated vehicle can visually detect a ping-pong ball through its camera, estimate its image-space position, continuously steer toward it using the OpenCV-derived position error, adjust its forward speed according to approximate distance, and recover when the target temporarily leaves the camera view.

That is the core system. Everything else supports demonstration, evaluation, and reporting.
