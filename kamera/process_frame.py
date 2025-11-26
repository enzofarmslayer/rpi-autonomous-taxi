import cv2
import numpy as np
import math
from enum import Enum
import cluster as cl
import line_detection as ld
import find_boundries as lc
import find_path as fp
import config
from dataclasses import dataclass
from typing import Optional, Tuple


class Direction(Enum):
    LEFT = 0
    STRAIGHT = 1
    RIGHT = 2
    STOP = 3

@dataclass
class FrameResult:
    heading: float
    dist_to_stopline: Optional[np.ndarray]
    stop_point: Optional[Tuple[int, int]]
    target_point: np.ndarray
    target_path: np.ndarray
    other_path: Optional[np.ndarray]
    roi: np.ndarray
    roi_offset: Tuple[int, int]
    labeled_binary: np.ndarray
    clusters: cl.Cluster
    boundaries: Tuple[np.ndarray, np.ndarray]


def _extract_roi(frame):
    frame = cv2.resize(frame, (config.FRAME_W, config.FRAME_H))

    top = int(config.FRAME_H * (1.0-config.ROI_TOP))
    bottom = int(config.FRAME_H * (1.0 - config.ROI_BOTTOM))
    left = int(config.FRAME_W * config.HORIZONTAL_MARGIN)
    right = int(config.FRAME_W * (1.0 - config.HORIZONTAL_MARGIN))

    roi = frame[top:bottom, left:right]
    return roi, (left, top)


def _build_trapezoid_mask(width: int, height: int, top_scale: float) -> np.ndarray:
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


def _preprocess(roi):
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)

    _, binary = cv2.threshold(blur, config.BLACK_THRESHOLD, 255, cv2.THRESH_BINARY_INV)

    kernel = np.ones((3, 3), np.uint8)
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=1)

    if config.ROI_TOP_SCALE < 1.0:
        h, w = binary.shape[:2]
        trap_mask = _build_trapezoid_mask(w, h, config.ROI_TOP_SCALE)
        binary = cv2.bitwise_and(binary, trap_mask)

    return binary


def _compute_heading(center_x_fullframe: float) -> float:
    """
    Find horizontal offset angle where 0 = camera's forward direction
    """
    image_center_x = config.FRAME_W / 2.0 + config.CAMERA_X_OFFSET
    dx = center_x_fullframe - image_center_x
    angle_rad = math.atan(dx / config.FOCAL_LENGTH_PIX)
    return math.degrees(angle_rad)


def _choose_lookahead_point(centers_roi, roi_h):
    target_y = (roi_h - 1) * (1.0 - config.LOOKAHEAD_POS)

    # Find the centerline point whose y is closest to target_y
    look_cx_roi, look_cy_roi = min(
        centers_roi,
        key=lambda p: abs(p[1] - target_y)
    )
    return look_cx_roi, look_cy_roi


def _roi_to_fullframe(point, offsets):
    """
    Convert from ROI coordinates to full-frame coordinates.
    """
    return np.add(point, offsets)


def process_frame(frame, dir: Direction) -> FrameResult:
    """
    Full pipeline:
      1) Extract ROI
      2) Binarize from predefined threshold and invert
      3) Find clusters of white pixels
      4) Label clusters
      5) Find lane
      6) Decide what to follow
      7) Compute heading based on lookahead point
    """

    # 1) ROI
    roi, offset = _extract_roi(frame)

    # 2) Binary
    binary = _preprocess(roi)

    # 3) Clusters
    labeled_binary, clusters = cl.find_clusters(binary)
    ld.remove_false_clusters(labeled_binary, clusters)

    # 4) Label clusters
    stop_point = ld.find_stop_line(labeled_binary, clusters)
    dist_to_stop = None
    if stop_point:
        dist_to_stop = _roi_to_fullframe(stop_point, offset)

    ld.label_remaining_clusters(labeled_binary, clusters)
    
    # 5) Boundries
    left_boundary, right_boundary = lc.compute_lane_boundaries(labeled_binary, clusters)

    # 6) Find possible paths
    path_l = fp.compute_lane_center(left_boundary, right_boundary, roi_shape=binary.shape,
                                         force_side="left")
    path_r = fp.compute_lane_center(left_boundary, right_boundary, roi_shape=binary.shape,
                                         force_side="right")
    
    # 7) Scan for intersection
    diverging_paths = fp.detect_diverging_paths(path_l, path_r, binary.shape)
    print("Div paths? ", str(diverging_paths))

    target_path = None
    other_path = None
    if not diverging_paths:
        target_path = fp.compute_lane_center(left_boundary, right_boundary, roi_shape=binary.shape,
                                         force_side=None)
    else:
        if dir == Direction.LEFT:
            target_path = path_l
            other_path = path_r
        else:
            target_path = path_r
            other_path = path_l

    # 8) Compute heading based on lookahead point
    target_point_roi = _choose_lookahead_point(target_path, roi.shape[0])
    target_point = _roi_to_fullframe(target_point_roi, offset)
    heading = _compute_heading(target_point[0])

    return FrameResult(
        heading=heading,
        dist_to_stopline=dist_to_stop,
        stop_point=stop_point,
        target_point=target_point,
        target_path=target_path,
        other_path=other_path,
        roi=roi,
        roi_offset=offset,
        labeled_binary=labeled_binary,
        clusters=clusters,
        boundaries=(left_boundary, right_boundary),
    )
