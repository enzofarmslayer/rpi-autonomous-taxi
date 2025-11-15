import cv2
import numpy as np
import math

from config import (
    FRAME_W, FRAME_H, ROI_TOP_SCALE, LANE_WIDTH_OF_ROI,
    ROI_TOP, ROI_BOTTOM, HORIZONTAL_MARGIN, LANE_WIDTH_DECREASE_RATE,
    LOOKAHEAD_POS, FOCAL_LENGTH_PIX, CAMERA_X_OFFSET, SCANLINES,
    MAX_DEV_FROM_PREC_SCANLINE, TAPE_MIN_WIDTH, MIN_LANE_WIDTH_PX
)

_prev_center_x = None
_prev_lane_width = None

def extract_roi(frame):
    frame = cv2.resize(frame, (FRAME_W, FRAME_H))

    top = int(FRAME_H * (1.0-ROI_TOP))
    bottom = int(FRAME_H * (1.0 - ROI_BOTTOM))
    left = int(FRAME_W * HORIZONTAL_MARGIN)
    right = int(FRAME_W * (1.0 - HORIZONTAL_MARGIN))

    roi = frame[top:bottom, left:right]
    return roi, (left, top)


def build_trapezoid_mask(width: int, height: int, top_scale: float) -> np.ndarray:
    """
    Create a single-channel (uint8) mask with a trapezoid:
    """
    top_scale = max(0.0, min(1.0, top_scale))

    mask = np.zeros((height, width), dtype=np.uint8)

    mid_x = width / 2.0
    half_bottom = width / 2.0
    half_top = half_bottom * top_scale

    # Trapezoid corners (x, y)
    top_left  = (int(mid_x - half_top), 0)
    top_right = (int(mid_x + half_top), 0)
    bot_right = (width - 1, height - 1)
    bot_left  = (0, height - 1)

    pts = np.array([top_left, top_right, bot_right, bot_left], dtype=np.int32)
    cv2.fillConvexPoly(mask, pts, 255)

    return mask


def preprocess(roi):
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)

    _, binary = cv2.threshold(blur, 110, 255, cv2.THRESH_BINARY_INV)

    kernel = np.ones((3, 3), np.uint8)
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=1)

    if ROI_TOP_SCALE < 1.0:
        h, w = binary.shape[:2]
        trap_mask = build_trapezoid_mask(w, h, ROI_TOP_SCALE)
        binary = cv2.bitwise_and(binary, trap_mask)

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


def choose_lookahead_point(centers_roi, roi_h, lookahead_pos: float):
    if not centers_roi:
        return None

    lookahead_pos = max(0.0, min(1.0, lookahead_pos))
    target_y = (roi_h - 1) * (1.0 - lookahead_pos)

    # Find the centerline point whose y is closest to target_y
    look_cx_roi, look_cy_roi = min(
        centers_roi,
        key=lambda p: abs(p[1] - target_y)
    )
    return look_cx_roi, look_cy_roi


def roi_to_fullframe(x_roi, y_roi, off_x, off_y):
    """
    Convert from ROI coordinates to full-frame coordinates.
    """
    return x_roi + off_x, y_roi + off_y


def find_segments(tape_points):
    """
    Group sorted x indices into contiguous segments [start, end].
    Ignore segments narrower than min_width pixels (noise).
    """
    if len(tape_points) == 0:
        return []

    segments = []
    start = tape_points[0]
    prev = tape_points[0]

    for x in tape_points[1:]:
        if x == prev + 1:
            prev = x
        else:
            if prev - start + 1 >= TAPE_MIN_WIDTH:
                segments.append((start, prev))
            start = prev = x
    if prev - start + 1 >= TAPE_MIN_WIDTH:
        segments.append((start, prev))

    return segments


def get_centerline_points(binary):
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
        _prev_lane_width = LANE_WIDTH_OF_ROI

    rows = np.linspace(h - 1, 0, SCANLINES, dtype=int)

    centers = []

    row_prev_left = _prev_center_x - _prev_lane_width / 2
    row_prev_right = _prev_center_x + _prev_lane_width / 2

    for y in rows:
        row = binary[y, :]
        tape_points = np.where(row > 0)[0]
        if len(tape_points) == 0:
            # No tape at this row
            continue

        segments = find_segments(tape_points)
        if not segments:
            continue

        # Segment centers
        seg_centers = [(0.5 * (s + e), s, e) for (s, e) in segments]

        left_x = None
        right_x = None
        one_tape = False

        if len(seg_centers) >= 2:
            # Two tapes; choose pair that best matches previous left/right
            seg_centers.sort(key=lambda t: t[0])

            best_cost = 1e9
            best_pair = None

            for i in range(len(seg_centers)):
                for j in range(i + 1, len(seg_centers)):
                    cL, _, _ = seg_centers[i]
                    cR, _, _ = seg_centers[j]
                    if(abs(cL-cR) < MIN_LANE_WIDTH_PX):
                        continue

                    cost = abs(cL - row_prev_left) + abs(cR - row_prev_right)
                    if cost < best_cost:
                        best_cost = cost
                        best_pair = (cL, cR)

            if best_pair:
                left_x, right_x = best_pair
                left_x = float(max(0, min(w - 1, left_x)))
                right_x = float(max(0, min(w - 1, right_x)))
            else:
                one_tape = True
                seg_centers.sort(key=lambda t: abs(t[0]-w/2)) # pick closest to middle

        if len(seg_centers) == 1 or one_tape:
            # One tape
            c, s, e = seg_centers[0]

            # Check if left or right
            if (c < w/2):
                # Left
                left_x = c
                right_x = c + LANE_WIDTH_OF_ROI*w*pow(LANE_WIDTH_DECREASE_RATE, len(centers))
            else:
                # Right
                right_x = c
                left_x = c - LANE_WIDTH_OF_ROI*w*pow(LANE_WIDTH_DECREASE_RATE, len(centers))


        # Compute lane center, store point
        center_x = 0.5 * (left_x + right_x)
        print(f"Center: {center_x:.0f}")
        add = True
        if len(centers):
            if abs(center_x-centers[-1][0] > MAX_DEV_FROM_PREC_SCANLINE):
                add = False
        if add:
            centers.append((int(center_x), int(y)))

        # Update per-row expected positions and lane width
        row_prev_left, row_prev_right = left_x, right_x
        lane_width = right_x - left_x
        if lane_width > 5:  # avoid degenerate values
            _prev_lane_width = 0.9 * _prev_lane_width + 0.1 * lane_width
        _prev_center_x = center_x

    print(centers)

    return centers


def process_frame(frame, debug=False):
    """
    Full pipeline:
      1) Extract ROI
      2) Binarize to black and white
      3) Trace road centerline using multiple scanlines
      4) Select a target lookahead point
      5) Compute offset angle to that point
      6) Build visualization
    """
    # 1) ROI
    roi, (off_x, off_y) = extract_roi(frame)
    roi_h, roi_w = roi.shape[:2]

    # 2) Binary
    binary = preprocess(roi)

    # 3) Centerline points in ROI coordinates
    centers_roi = get_centerline_points(binary)

    if not centers_roi:
        # No line found
        return {
            "found": False,
            "angle": 0.0,
            "centerline": [],
            "debug_frame": cv2.resize(frame, (FRAME_W, FRAME_H)) if debug else None,
        }

    # 4) Compute lookahead point in ROI coords
    lookahead_point_roi = choose_lookahead_point(centers_roi, roi_h, LOOKAHEAD_POS)

    # Safety: if not found
    if lookahead_point_roi is None:
        lookahead_point_roi = centers_roi[0]    # bottom

    look_cx_roi, look_cy_roi = lookahead_point_roi

    # 5) Map ROI coords -> full frame coords
    look_cx_full, look_cy_full = roi_to_fullframe(look_cx_roi, look_cy_roi, off_x, off_y)

    # 6) Compute angle based on lookahead center x
    angle_deg = compute_offset_angle(look_cx_full)

    # 7) Build debug frame
    debug_frame = None
    if debug:
        debug_frame = cv2.resize(frame, (FRAME_W, FRAME_H))

        # Draw ROI rectangle
        if ROI_TOP_SCALE < 1.0:
            # Trapezoid in ROI coords
            mid_x = roi_w / 2.0
            half_bottom = roi_w / 2.0
            half_top = half_bottom * ROI_TOP_SCALE

            top_y = off_y
            bot_y = off_y + roi_h - 1

            top_left  = (int(off_x + mid_x - half_top), top_y)
            top_right = (int(off_x + mid_x + half_top), top_y)
            bot_left  = (off_x, bot_y)
            bot_right = (off_x + roi_w - 1, bot_y)

            pts = np.array([top_left, top_right, bot_right, bot_left], dtype=np.int32)
            cv2.polylines(debug_frame, [pts], isClosed=True, color=(0, 128, 255), thickness=2)


        # Draw road path
        pts_full = np.array(
            [[cx + off_x, cy + off_y] for (cx, cy) in centers_roi],
            dtype=np.int32,
        )
        if len(pts_full) >= 2:
            cv2.polylines(
                debug_frame,
                [pts_full],
                isClosed=False,
                color=(0, 240, 255),
                thickness=3,
            )

        # Draw line from taxi to target
        mid_x = int(FRAME_W / 2.0 + CAMERA_X_OFFSET)
        cv2.line(
            debug_frame,
            (mid_x, FRAME_H),
            (look_cx_full, look_cy_full),
            (10, 10, 10),
            2,
        )

        # Mark
        cv2.circle(debug_frame, (look_cx_full, look_cy_full), 5, (0, 70, 255), -1)

        # Angle text
        text = f"{angle_deg:.1f}"
        text_size, _ = cv2.getTextSize(text, cv2.FONT_ITALIC, 1.0, 2)
        text_w, _ = text_size
        cv2.rectangle(debug_frame, (0,0), (round(6 + text_w*1.2), 44), (0,0,0), -1)
        cv2.putText(
            debug_frame,
            text,
            (10, 35),
            cv2.FONT_ITALIC,
            1.0,
            (220, 220, 220),
            2,
            cv2.LINE_AA,
        )

    return {
        "found": True,
        "angle": angle_deg,
        "centerline": [
            (cx + off_x, cy + off_y) for (cx, cy) in centers_roi
        ],
        "lookahead_point": (look_cx_full, look_cy_full),
        "debug_frame": debug_frame,
    }
