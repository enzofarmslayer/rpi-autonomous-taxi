import cv2
import numpy as np
import math

from config import (
    FRAME_W, FRAME_H, ROI_TOP_SCALE,
    ROI_TOP, ROI_BOTTOM, HORIZONTAL_MARGIN,
    LOOKAHEAD_POS, FOCAL_LENGTH_PIX, CAMERA_X_OFFSET, BLACK_THRESHOLD
)

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

    _, binary = cv2.threshold(blur, BLACK_THRESHOLD, 255, cv2.THRESH_BINARY_INV)

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
    centers_roi = compute_path(binary)

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
