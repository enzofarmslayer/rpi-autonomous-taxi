import cv2
import numpy as np
import matplotlib.pyplot as plt
import argparse
import time

import process_frame as p_frame
import cluster as cl
import line_detection as ld
import find_boundries as lc
import find_path as fp
import detect_intersection as di

import config

COLORS = [
    (128, 0,   255),  # Purple
    (255, 128, 0),    # Orange
    (255, 0,   255),  # Magenta
    (0,   255, 128),  # Spring green
]

def get_color(cluster_id: int):
    return COLORS[cluster_id % len(COLORS)]


def evaluate_image(image_path: str):
    frame = cv2.imread(image_path)
    if frame is None:
        raise FileNotFoundError(f"Could not read image: {image_path}")
    frame = cv2.resize(frame, (config.FRAME_W, config.FRAME_H))

    pf = p_frame.process_frame(frame, p_frame.Direction.LEFT)


    # Visualization setup (ROI)
    vis = cv2.cvtColor((pf["labeled_binary"] > 0).astype(np.uint8) * 255, cv2.COLOR_GRAY2BGR)

    left_boundary = pf["boundaries"][0]
    right_boundary = pf["boundaries"][1]
    target_path = pf["target_path"]
    other_path = pf["other_path"]

    # Draw boundries
    if left_boundary.size > 1:
        left_pts = left_boundary.reshape((-1, 1, 2)).astype(np.int32)
        cv2.polylines(
            vis, [left_pts], isClosed=False,
            color=(0, 0, 255), thickness=4
        )

    if right_boundary.size > 1:
        right_pts = right_boundary.reshape((-1, 1, 2)).astype(np.int32)
        cv2.polylines(
            vis, [right_pts], isClosed=False,
            color=(0, 0, 255), thickness=4
        )

    # Draw center path
    if target_path is not None and target_path.size > 1:
        center_pts = target_path.reshape((-1, 1, 2)).astype(np.int32)
        cv2.polylines(vis, [center_pts], isClosed=False, color=(0, 200, 255), thickness=2)

    if other_path is not None and other_path.size > 1:
        center_pts = other_path.reshape((-1, 1, 2)).astype(np.int32)
        cv2.polylines(vis, [center_pts], isClosed=False, color=(0, 90, 120), thickness=2)
    
    
    # Draw clusters and show boundary points inside each one
    for cluster in pf["clusters"]:
        color = get_color(cluster.id)
        y_sl, x_sl = cluster.slice

        # Draw bounding box
        cv2.rectangle(
            vis,
            (x_sl.start, y_sl.start),
            (x_sl.stop,  y_sl.stop),
            color, 2
        )

        # Draw ClusterType text
        text = cluster.ctype.name.replace("_", " ")
        text_color = color

        (text_w, text_h), baseline = cv2.getTextSize(
            text, config.FONT, config.FONT_SCALE, config.FONT_THICKNESS)
        text_x = x_sl.start + 5
        text_y = y_sl.start + 15

        cv2.putText(
            vis, text, (text_x, text_y),
            config.FONT, config.FONT_SCALE, text_color, config.FONT_THICKNESS, cv2.LINE_AA)

        # Draw stop line (unchanged – still in ROI coords)
        if cluster.ctype == cl.ClusterType.CONTAINS_STOPLINE:
            sx, sy = map(int, pf["stop_point"])
            cv2.line(
                vis,
                (cluster.bbox[2], sy),
                (cluster.bbox[3], sy),
                (0, 0, 220), 2
            )
            cv2.putText(
                vis, "STOP", (cluster.bbox[2] + 8, sy - 8),
                config.FONT, config.FONT_SCALE,
                (0, 10, 240), config.FONT_THICKNESS, cv2.LINE_AA
            )


    # Convert to RGB for Matplotlib
    final_rgb = cv2.cvtColor(vis, cv2.COLOR_BGR2RGB)

    # Show results
    plt.figure(figsize=(16, 8))

    # Original + ROI rectangle
    plt.subplot(1, 2, 1)
    plt.title("Original + ROI")
    frame_with_roi = frame.copy()
    plt.imshow(cv2.cvtColor(frame_with_roi, cv2.COLOR_BGR2RGB))
    plt.axis("off")

    # ROI visualization with clusters + lane boundaries
    plt.subplot(1, 2, 2)
    plt.title("Clusters + Lane Boundaries")
    plt.imshow(final_rgb)
    plt.axis("off")

    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("image", help="Path to JPG image")
    args = parser.parse_args()
    evaluate_image(args.image)
