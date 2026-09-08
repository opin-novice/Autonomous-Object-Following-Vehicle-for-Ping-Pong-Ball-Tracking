"""Validate tracking_log.csv structure and data integrity (PROMPT 10 verification)."""

import csv
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "webots", "controllers", "ball_follower"))
import logger


def validate_csv(csv_path):
    checks = []

    if not os.path.exists(csv_path):
        print("FAIL: File does not exist: %s" % csv_path)
        return False

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = list(csv.reader(f))

    # Check 1: Header matches schema
    header = reader[0]
    header_ok = header == logger.HEADER
    checks.append(("header matches schema", header_ok))
    if not header_ok:
        print("  Expected: %s" % logger.HEADER)
        print("  Got:      %s" % header)

    # Check 2: Has data rows
    data_rows = reader[1:]
    has_data = len(data_rows) > 0
    checks.append(("has data rows (%d)" % len(data_rows), has_data))

    # Check 3: All rows have 12 columns
    correct_cols = all(len(row) == 12 for row in data_rows)
    checks.append(("all rows have 12 columns", correct_cols))

    # Check 4: Timestamps are parseable floats and monotonically increasing
    timestamps = []
    ts_ok = True
    for row in data_rows:
        try:
            timestamps.append(float(row[0]))
        except ValueError:
            ts_ok = False
            break
    monotonic = all(timestamps[i] <= timestamps[i + 1] for i in range(len(timestamps) - 1))
    checks.append(("timestamps are parseable floats", ts_ok))
    checks.append(("timestamps are monotonically increasing", monotonic))

    # Check 5: ball_detected is 0 or 1
    det_ok = all(row[1] in ("0", "1") for row in data_rows)
    checks.append(("ball_detected is 0 or 1", det_ok))

    # Check 6: When ball_detected=0, ball fields are empty
    empty_ok = True
    for row in data_rows:
        if row[1] == "0":
            if row[2] != "" or row[3] != "" or row[4] != "" or row[6] != "":
                empty_ok = False
                break
    checks.append(("missing ball fields are empty strings", empty_ok))

    # Check 7: When ball_detected=1, ball fields are non-empty parseable floats
    fill_ok = True
    for row in data_rows:
        if row[1] == "1":
            try:
                float(row[2])  # ball_x
                float(row[3])  # ball_y
                float(row[4])  # ball_radius
                float(row[6])  # image_error
            except (ValueError, IndexError):
                fill_ok = False
                break
    checks.append(("detected ball fields are parseable floats", fill_ok))

    # Check 8: State is one of the four allowed values
    valid_states = {"SEARCHING", "TRACKING", "APPROACHING", "STOPPED"}
    state_ok = all(row[11] in valid_states for row in data_rows)
    checks.append(("state is a valid FSM state", state_ok))

    # Check 9: Enough rows for ~10 seconds at 32ms timestep (~312 rows)
    enough = len(data_rows) >= 100
    checks.append(("enough rows for a meaningful run (>= 100)", enough))

    # Check 10: Last timestamp is near 10 seconds
    if timestamps:
        near_10 = timestamps[-1] >= 8.0
        checks.append(("last timestamp >= 8.0s (run completed)", near_10))

    print("\n=== tracking_log.csv validation ===")
    print("File: %s" % csv_path)
    print("Rows: %d (header + %d data)" % (len(reader), len(data_rows)))
    if timestamps:
        print("Time range: %.4f - %.4f s" % (timestamps[0], timestamps[-1]))
    print()
    all_ok = True
    for label, ok in checks:
        print("[%s] %s" % ("PASS" if ok else "FAIL", label))
        if not ok:
            all_ok = False

    print()
    print("RESULT: %s" % ("ALL PASS" if all_ok else "FAILURES PRESENT"))
    return all_ok


if __name__ == "__main__":
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "results", "logs", "tracking_log.csv")
    validate_csv(path)
