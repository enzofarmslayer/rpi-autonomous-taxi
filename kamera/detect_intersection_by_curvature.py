import numpy as np

import numpy as np

def sample_boundary_by_y(boundary: np.ndarray) -> np.ndarray:
    """
    Downsample boundary so we keep roughly one point every `step_y` pixels in y.
    boundary: (N, 2) array [x, y].
    Returns: (M, 2) array of sampled points, ordered by y.
    """
    if boundary is None or boundary.size == 0:
        return np.empty((0, 2), dtype=float)

    pts = np.asarray(boundary, dtype=float).reshape(-1, 2)

    # Sort by y (row)
    pts = pts[np.argsort(pts[:, 1])]

    sampled = [pts[0]]
    last_y = pts[0, 1]

    for p in pts[1:]:
        y = p[1]
        if y - last_y >= STEP_Y:
            sampled.append(p)
            last_y = y

    # Ensure we include the last point if it's far enough or unique
    if not np.allclose(sampled[-1], pts[-1]):
        if pts[-1, 1] - sampled[-1][1] >= STEP_Y / 2:
            sampled.append(pts[-1])

    return np.vstack(sampled)


def boundary_curvature_score(boundary: np.ndarray) -> float:
    """
    Curvature per unit length for a single boundary,
    computed on points sampled every ~step_y pixels in y.

    0.0  -> perfectly straight
    higher -> more curved

    S-shaped curves (one way then the other) increase the score,
    since we sum |angle change|.
    """
    sampled = sample_boundary_by_y(boundary)
    if sampled.shape[0] < 3:
        return 0.0

    pts = sampled

    # Segment vectors between sampled points
    d = pts[1:] - pts[:-1]      # (M-1, 2)
    seg_lengths = np.linalg.norm(d, axis=1)

    # Filter out degenerate segments
    valid = seg_lengths > EPS
    d = d[valid]
    seg_lengths = seg_lengths[valid]

    if len(d) < 2:
        return 0.0

    total_length = float(seg_lengths.sum())
    if total_length < EPS:
        return 0.0

    # Unit direction vectors
    u = d / seg_lengths[:, None]

    # Angle of each segment (rotation-invariant)
    angles = np.arctan2(u[:, 1], u[:, 0])
    angles = 10 * np.unwrap(angles)

    # Angle change between consecutive segments
    dtheta = np.diff(angles)

    # Sum of absolute angle changes per unit length
    score = 100 * np.sum((np.abs(dtheta)/total_length)**2)

    # LOOK INTO AMPLIFYING SCORE FOR LOWER Y (FURTHER AWAY)!!
    return score


# Tune these based on your data:
CURVE_MIN_SCORE = 0.28
CURVATURE_RATIO_THRESHOLD = 1.6
MAX_STRAIGHT_XY_RATIO = 0.65   # total |dx| is at most 30% of total |dy|
STEP_Y = 4
EPS = 1e-6

def validate_straight_boundry(boundary: np.ndarray) -> bool:
    """
    Returns True if the boundary is 'straight enough' according to the
    ratio of total movement in x vs total movement in y."""

    if boundary is None or boundary.size < 4:
        return False  # not enough info

    pts = np.asarray(boundary, dtype=float).reshape(-1, 2)

    # Optionally sort by y so we walk consistently along the boundary
    pts = pts[np.argsort(pts[:, 1])]

    # Differences between consecutive points
    dx = np.diff(pts[:, 0])
    dy = np.diff(pts[:, 1])

    total_dx = float(np.sum(np.abs(dx)))
    total_dy = float(np.sum(np.abs(dy)))

    if total_dy < EPS:
        # essentially horizontal / degenerate; in your use case, probably not a valid lane boundary
        return False

    ratio = total_dx / total_dy

    # Debug print if you want to tune it:
    # print(f"total_dx={total_dx:.2f}, total_dy={total_dy:.2f}, ratio={ratio:.3f}")

    return ratio <= MAX_STRAIGHT_XY_RATIO


def detect_intersection_from_boundaries(
    left_boundary: np.ndarray,
    right_boundary: np.ndarray,
) -> tuple[bool, float, float]:
    """
    Returns (is_intersection, left_score, right_score)

    Heuristic:
      - Compute curvature scores for each boundary.
      - If one side is 'straight enough' AND
        the other is significantly more curved -> intersection.
    """
    if (left_boundary is None or right_boundary is None or
        left_boundary.size < 6 or right_boundary.size < 6):
        return False, 0.0, 0.0

    left_score = boundary_curvature_score(left_boundary)
    right_score = boundary_curvature_score(right_boundary)

    # Avoid division by zero in ratios
    ls = max(left_score, 1e-6)
    rs = max(right_score, 1e-6)

    ratio_lr = ls / rs
    ratio_rl = rs / ls

    # Case 1: left is straight, right is curved
    left_is_curve =  left_score > CURVE_MIN_SCORE and ratio_lr > CURVATURE_RATIO_THRESHOLD
    right_is_straight = validate_straight_boundry(right_boundary)

    if (left_is_curve and right_is_straight):
        return True, left_score, right_score

    # Case 2: right is straight, left is curved
    right_is_curve =  right_score > CURVE_MIN_SCORE and ratio_rl > CURVATURE_RATIO_THRESHOLD
    left_is_straight = validate_straight_boundry(left_boundary)

    if (right_is_curve and left_is_straight):
        return True, left_score, right_score

    return False, left_score, right_score