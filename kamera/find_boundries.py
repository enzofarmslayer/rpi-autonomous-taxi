from typing import Dict, List, Tuple, Optional
from collections import defaultdict
import numpy as np
import config

from cluster import Cluster, ClusterType, get_cluster_points


def _is_lane_like(pts: np.ndarray) -> bool:
    """
    Return True if the boundary behaves like a lane (mostly vertical).
    Return False if any segment looks more like a stop line.
    """

    if pts is None or len(pts) < 2:
        return False

    THRESHOLD = 2/5

    for i in range(len(pts) - 1):
        x0, y0 = pts[i]
        x1, y1 = pts[i + 1]

        dx = abs(x1 - x0)
        dy = abs(y1 - y0)

        if dy/dx < THRESHOLD:
            return False  # NOT lane-like

    return True  # all segments behave vertically enough



def collect_boundary_candidates(
    binary_labeled: np.ndarray,
    clusters: list[Cluster],
):
    left_by_y = defaultdict(list)
    right_by_y = defaultdict(list)

    roi_center_x = binary_labeled.shape[1] // 2

    for cl in clusters:
        if cl.ctype == ClusterType.CONTAINS_STOPLINE:
            pts_left = get_cluster_points(binary_labeled, cl, method="left")
            pts_right = get_cluster_points(binary_labeled, cl, method="right")

            for x, y in pts_right:
                right_by_y[int(y)].append(int(x))

            for x, y in pts_left:
                left_by_y[int(y)].append(int(x))

        elif cl.ctype == ClusterType.LEFT:
            pts_center = get_cluster_points(binary_labeled, cl, method="center")
            for x, y in pts_center:
                left_by_y[int(y)].append(int(x))

        elif cl.ctype == ClusterType.RIGHT:
            pts_center = get_cluster_points(binary_labeled, cl, method="center")
            for x, y in pts_center:
                right_by_y[int(y)].append(int(x))

        # IGNORE / OK etc. skipped

    return left_by_y, right_by_y


def select_boundary_for_row(
    y: int,
    roi_center_x: int,
    left_by_y: Dict[int, List[int]],
    right_by_y: Dict[int, List[int]],
) -> Tuple[Optional[Tuple[int, int]], Optional[Tuple[int, int]]]:
    """
    For a single row y, pick R and L closest to center
    """
    left_point = None
    right_point = None

    xs_left = left_by_y.get(y, [])
    xs_right = right_by_y.get(y, [])

    if xs_left:
        x_left = min(xs_left, key=lambda x: abs(x - roi_center_x))
        left_point = (x_left, y)

    if xs_right:
        x_right = min(xs_right, key=lambda x: abs(x - roi_center_x))
        right_point = (x_right, y)

    return left_point, right_point

def apply_centered_boundary_safety_limit(
    boundary: np.ndarray,
) -> np.ndarray:
    """
    Safety filter that:
    1) Takes the MIDDLE boundary point as the trusted anchor.
    2) Moves outward (upwards and downwards in y) enforcing that
       x cannot deviate more than `max_dev` from the previous accepted point.

    boundary: assumed sorted by y ascending.
    """
    if boundary.size == 0:
        return boundary

    boundary = boundary[np.argsort(boundary[:, 1])]
    n = len(boundary)
    mid = n // 2  

    cleaned = [None] * n
    cleaned[mid] = tuple(boundary[mid])

    mid_x, mid_y = boundary[mid]

    # ---- expand downward ----
    prev_x = mid_x
    for i in range(mid + 1, n):
        x, y = boundary[i]
        if abs(x - prev_x) <= config.MAX_BOUNDARY_DEVIATION:
            cleaned[i] = (x, y)
            prev_x = x
        else:
            # skip unsafe point
            continue

    # ---- expand upward ----
    prev_x = mid_x
    for i in range(mid - 1, -1, -1):
        x, y = boundary[i]
        if abs(x - prev_x) <= config.MAX_BOUNDARY_DEVIATION:
            cleaned[i] = (x, y)
            prev_x = x
        else:
            continue

    cleaned = [p for p in cleaned if p is not None]

    return np.array(cleaned, dtype=np.int32)


def compute_lane_boundaries(
    binary_labeled: np.ndarray,
    clusters: List[Cluster],
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Compute left and right road boundaries as sequences of (x, y) points.

    Rules:
    - For stopline clusters: use outer edges of both sides.
    - For LEFT / RIGHT clusters: use centers.
    - If there are multiple left/right candidates in a row,
      pick the one closest to the image center.
    """
    height, width = binary_labeled.shape
    roi_center_x = width // 2

    # 1) Collect all candidates in unified arrays
    left_by_y, right_by_y = collect_boundary_candidates(binary_labeled, clusters)

    # 2) All rows that have any candidates
    rows = sorted(set(left_by_y.keys()) | set(right_by_y.keys()))

    left_boundary: List[Tuple[int, int]] = []
    right_boundary: List[Tuple[int, int]] = []

    # 3) Row-by-row selection
    for y in rows:
        left_pt, right_pt = select_boundary_for_row(y, roi_center_x, left_by_y, right_by_y)
        if left_pt is not None:
            left_boundary.append(left_pt)
        if right_pt is not None:
            right_boundary.append(right_pt)

    # Convert to numpy arrays
    left_arr = np.array(left_boundary, dtype=np.int32) if left_boundary else np.empty((0, 2), dtype=np.int32)
    right_arr = np.array(right_boundary, dtype=np.int32) if right_boundary else np.empty((0, 2), dtype=np.int32)

    # Validate
    left_arr = apply_centered_boundary_safety_limit(left_arr)
    right_arr = apply_centered_boundary_safety_limit(right_arr)

    # For stoplines check so boundry isnt the stopline itself
    for cl in clusters:
        if cl.ctype == ClusterType.CONTAINS_STOPLINE:
            if not _is_lane_like(left_arr):
                left_arr = np.empty((0, 2), dtype=np.int32)

            if not _is_lane_like(right_arr):
                right_arr = np.empty((0, 2), dtype=np.int32)

    return left_arr, right_arr
