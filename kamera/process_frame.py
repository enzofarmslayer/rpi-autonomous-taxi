import cv2
import numpy as np
import math

from config import (
    FRAME_W, FRAME_H,
    ROI_TOP, ROI_BOTTOM, HORIZONTAL_MARGIN,
    GAUSSIAN_KERNEL_SIZE, MORPH_KERNEL_SIZE, MIN_CONTOUR_AREA, FOCAL_LENGTH_PIX, CAMERA_X_OFFSET
)

def extract_roi(frame):
    frame = cv2.resize(frame, (FRAME_W, FRAME_H))

    top = int(FRAME_H * (1.0-ROI_TOP))
    bottom = int(FRAME_H * (1.0 - ROI_BOTTOM))
    left = int(FRAME_W * HORIZONTAL_MARGIN)
    right = int(FRAME_W * (1.0 - HORIZONTAL_MARGIN))

    roi = frame[top:bottom, left:right]
    return roi, (left, top)


def preprocess(roi):
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)

    _, binary = cv2.threshold(
        blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
    )

    kernel = np.ones((3, 3), np.uint8)
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel, iterations=1)

    return binary


def compute_offset_angle(center_x_fullframe: float) -> float:
    """
    Compute horizontal offset angle in degrees: 0° = camera's forward direction
    (which may be offset from FRAME_W/2 if the camera is not centered).
    """
    image_center_x = FRAME_W / 2.0 + CAMERA_X_OFFSET
    dx = center_x_fullframe - image_center_x
    angle_rad = math.atan(dx / FOCAL_LENGTH_PIX)
    return math.degrees(angle_rad)


def _find_segments(xs):
    """Group sorted x indices into contiguous segments [start, end]."""
    if len(xs) == 0:
        return []

    segments = []
    start = xs[0]
    prev = xs[0]

    for x in xs[1:]:
        if x == prev + 1:
            prev = x
        else:
            segments.append((start, prev))
            start = prev = x
    segments.append((start, prev))
    return segments


# Globals near the top of process_frame.py
_prev_center_x = None
_prev_lane_width = None


def _find_segments(xs, min_width=3):
    """
    Group sorted x indices into contiguous segments [start, end].
    Ignore segments narrower than min_width pixels (noise).
    """
    if len(xs) == 0:
        return []

    segments = []
    start = xs[0]
    prev = xs[0]

    for x in xs[1:]:
        if x == prev + 1:
            prev = x
        else:
            if prev - start + 1 >= min_width:
                segments.append((start, prev))
            start = prev = x
    if prev - start + 1 >= min_width:
        segments.append((start, prev))

    return segments


def get_centerline_points(binary, num_scanlines: int = 6):
    """
    Compute lane CENTER points (bottom -> top) using both edges whenever possible.

    For each horizontal row:
      - Detect all white segments (tapes).
      - If 2+ segments -> choose best left/right, compute center = (L+R)/2.
      - If only 1 segment -> treat as left or right based on previous row
        and infer missing edge using previous lane width.

    Returns:
        centers: list of (cx, cy) in ROI coordinates, bottom -> top.
    """
    global _prev_center_x, _prev_lane_width

    h, w = binary.shape[:2]
    mid = w / 2.0

    if _prev_center_x is None:
        _prev_center_x = mid
    if _prev_lane_width is None:
        # Rough initial guess; will quickly be overwritten when we see both edges
        _prev_lane_width = w * 0.4

    rows = np.linspace(h - 1, 0, num_scanlines, dtype=int)

    centers = []

    row_prev_left = _prev_center_x - _prev_lane_width / 2
    row_prev_right = _prev_center_x + _prev_lane_width / 2

    for y in rows:
        row = binary[y, :]
        xs = np.where(row > 0)[0]
        if len(xs) == 0:
            # No tape at this row
            continue

        segments = _find_segments(xs, min_width=3)
        if not segments:
            continue

        # Segment centers
        seg_centers = [(0.5 * (s + e), s, e) for (s, e) in segments]

        left_x = None
        right_x = None

        if len(seg_centers) >= 2:
            # We have at least two stripes; choose pair that best matches previous left/right
            seg_centers.sort(key=lambda t: t[0])  # sort by center x

            best_cost = 1e9
            best_pair = None

            for i in range(len(seg_centers)):
                for j in range(i + 1, len(seg_centers)):
                    cL, _, _ = seg_centers[i]
                    cR, _, _ = seg_centers[j]
                    cost = abs(cL - row_prev_left) + abs(cR - row_prev_right)
                    if cost < best_cost:
                        best_cost = cost
                        best_pair = (cL, cR)

            left_x, right_x = best_pair

        else:
            # Only one tape visible on this row.
            c, s, e = seg_centers[0]

            # Decide whether this is the left or right tape based on previous row
            if abs(c - row_prev_left) < abs(c - row_prev_right):
                # Looks like the left tape; infer right using previous width
                left_x = c
                right_x = c + _prev_lane_width
            else:
                # Looks like the right tape; infer left
                right_x = c
                left_x = c - _prev_lane_width

        # Clamp inferred positions to image bounds
        left_x = float(max(0, min(w - 1, left_x)))
        right_x = float(max(0, min(w - 1, right_x)))

        # Compute lane center, store point
        center_x = 0.5 * (left_x + right_x)
        centers.append((int(center_x), int(y)))

        # Update per-row expected positions and lane width
        row_prev_left, row_prev_right = left_x, right_x
        lane_width = right_x - left_x
        if lane_width > 5:  # avoid degenerate values
            _prev_lane_width = 0.9 * _prev_lane_width + 0.1 * lane_width
        _prev_center_x = center_x

    return centers


def process_frame(frame, debug=False):
    """
    Full pipeline:
      1) Extract ROI
      2) Binarize
      3) Trace road centerline using multiple scanlines
      4) Choose a lookahead point on that centerline
      5) Compute offset angle to that point
      6) Build debug visualization with the *curved* centerline
    """
    # 1) ROI
    roi, (off_x, off_y) = extract_roi(frame)
    roi_h, roi_w = roi.shape[:2]

    # 2) Binary
    binary = preprocess(roi)

    # 3) Centerline points in ROI coordinates
    centers_roi = get_centerline_points(binary, num_scanlines=6)

    if not centers_roi:
        # No line found
        result = {
            "found": False,
            "angle": 0.0,
            "centerline": [],
            "debug_frame": cv2.resize(frame, (FRAME_W, FRAME_H)) if debug else None,
        }
        return result

        # centers_roi: list of (cx, cy) bottom -> top

    # centers_roi: list of (cx, cy) bottom -> top

    roi_h, roi_w = binary.shape[:2]

    if len(centers_roi) >= 2:
        ys = np.array([p[1] for p in centers_roi], dtype=np.float32)
        xs = np.array([p[0] for p in centers_roi], dtype=np.float32)

        # Fit x = a*y + b (least squares)
        a, b = np.polyfit(ys, xs, 1)

        y_bottom = roi_h - 1
        near_cx_roi = int(a * y_bottom + b)
        near_cy_roi = y_bottom

        near_cx_roi = max(0, min(roi_w - 1, near_cx_roi))
    else:
        near_cx_roi, near_cy_roi = centers_roi[0]

    look_cx_roi, look_cy_roi = centers_roi[-1]



    # Map ROI coords -> full frame coords
    near_cx_full = near_cx_roi + off_x
    near_cy_full = near_cy_roi + off_y

    look_cx_full = look_cx_roi + off_x
    look_cy_full = look_cy_roi + off_y

    # 4) Compute angle based on lookahead center x
    angle_deg = compute_offset_angle(look_cx_full)

    # 5) Build debug frame
    debug_frame = None
    if debug:
        debug_frame = cv2.resize(frame, (FRAME_W, FRAME_H))

        # Draw ROI rectangle
        top = off_y
        bottom = off_y + roi_h
        left = off_x
        right = off_x + roi_w
        cv2.rectangle(debug_frame, (left, top), (right, bottom), (0, 255, 0), 1)

        # Draw camera forward (image center)
        mid_x = int(FRAME_W / 2.0 + CAMERA_X_OFFSET)
        cv2.line(
            debug_frame,
            (mid_x, FRAME_H),
            (mid_x, int(FRAME_H * 0.6)),
            (255, 0, 0),
            2,
        )

        # Draw the *curved* centerline polyline
        pts_full = []
        for (cx_roi, cy_roi) in centers_roi:
            pts_full.append([cx_roi + off_x, cy_roi + off_y])
        pts_full = np.array(pts_full, dtype=np.int32)
        if len(pts_full) >= 2:
            cv2.polylines(
                debug_frame,
                [pts_full],
                isClosed=False,
                color=(0, 255, 255),
                thickness=2,
            )

        # Mark near and lookahead points
        cv2.circle(debug_frame, (near_cx_full, near_cy_full), 6, (0, 0, 255), -1)
        cv2.circle(debug_frame, (look_cx_full, look_cy_full), 6, (0, 255, 0), -1)

        # Angle text
        text = f"angle: {angle_deg:.2f}°"
        cv2.putText(
            debug_frame,
            text,
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 255, 255),
            2,
            cv2.LINE_AA,
        )

    return {
        "found": True,
        "angle": angle_deg,
        "centerline": [
            (cx + off_x, cy + off_y) for (cx, cy) in centers_roi
        ],
        "near_point": (near_cx_full, near_cy_full),
        "lookahead_point": (look_cx_full, look_cy_full),
        "debug_frame": debug_frame,
    }
