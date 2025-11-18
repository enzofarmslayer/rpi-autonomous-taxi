from typing import Tuple
import numpy as np
import config

def compute_lane_center(
    left_boundary: np.ndarray,
    right_boundary: np.ndarray,
    roi_shape: Tuple[int, int],
) -> np.ndarray:
    """
    Compute lane center points using left/right boundaries.

    - The ROI is split into `config.SCANLINES` horizontal bands (scanlines).
    - For each band:
        * If both left & right exist: center = (mean_left_x + mean_right_x) / 2
        * If only one boundary exists:
            - Estimate lane width in pixels using:
                DEFAULT_LANE_WIDTH_OF_ROI * (LANE_WIDTH_DECREASE_RATE ** i_from_bottom)
            - Shift from the existing boundary by half that width.
    - Returns an array of shape (N, 2) with [x, y] center points in ROI coords.
    """
    h, w = roi_shape
    centers = []

    # No boundaries at all -> empty center
    if left_boundary.size == 0 and right_boundary.size == 0:
        return np.empty((0, 2), dtype=np.int32)

    # Pre-extract ys for speed
    left_y = left_boundary[:, 1] if left_boundary.size > 0 else None
    right_y = right_boundary[:, 1] if right_boundary.size > 0 else None

    # We define scanlines from bottom (near camera) to top (far away)
    band_height = h / config.SCANLINES

    for i in range(config.SCANLINES):
        # Band in y (inclusive)
        y_min = int(h - (i + 1) * band_height)
        y_max = int(h - i * band_height)

        # Clamp to image bounds
        y_min = max(0, y_min)
        y_max = min(h - 1, y_max)
        if y_min > y_max:
            continue

        # Band's representative y (middle of band)
        y_center = int(0.5 * (y_min + y_max))

        # ---- get mean left x in this band ----
        x_left_avg = None
        if left_boundary.size > 0:
            mask_l = (left_y >= y_min) & (left_y <= y_max)
            if np.any(mask_l):
                x_left_avg = float(left_boundary[mask_l, 0].mean())

        # ---- get mean right x in this band ----
        x_right_avg = None
        if right_boundary.size > 0:
            mask_r = (right_y >= y_min) & (right_y <= y_max)
            if np.any(mask_r):
                x_right_avg = float(right_boundary[mask_r, 0].mean())

        # ---- compute center x ----
        if x_left_avg is not None and x_right_avg is not None:
            center_x = 0.5 * (x_left_avg + x_right_avg)

        elif x_left_avg is not None or x_right_avg is not None:
            # only one boundary -> estimate lane width & shift
            lane_width_norm = (
                config.DEFAULT_LANE_WIDTH_OF_ROI
                * (config.LANE_WIDTH_DECREASE_RATE ** i)
            )
            lane_width_px = lane_width_norm * w

            if x_left_avg is not None:
                # lane to the right of left boundary
                center_x = x_left_avg + lane_width_px / 2.0
            else:
                # lane to the left of right boundary
                center_x = x_right_avg - lane_width_px / 2.0
        else:
            continue

        centers.append((int(round(center_x)), y_center))

    if not centers:
        return np.empty((0, 2), dtype=np.int32)

    return np.array(centers, dtype=np.int32)
