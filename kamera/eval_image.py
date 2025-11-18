import cv2
import numpy as np
import matplotlib.pyplot as plt
import argparse

from process_frame import extract_roi, preprocess
from cluster import find_clusters, find_stop_line, remove_false_clusters, label_remaining_clusters

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

    roi, (off_x, off_y) = extract_roi(frame)
    binary = preprocess(roi)

    labeled_binary, clusters = find_clusters(binary)
    remove_false_clusters(labeled_binary, clusters)
    stop_point = find_stop_line(labeled_binary, clusters)
    
    if not stop_point:
        label_remaining_clusters(labeled_binary, clusters)

    # Visualization setup
    vis = cv2.cvtColor((binary > 0).astype(np.uint8) * 255, cv2.COLOR_GRAY2BGR)

    # Draw clusters
    for cluster in clusters:
        color = get_color(cluster.id)
        y_sl, x_sl = cluster.slice

        # Draw bounding box and center dot
        cv2.rectangle(vis, (x_sl.start, y_sl.start), (x_sl.stop, y_sl.stop), color, 2)

        # ────── NEW: Draw ClusterType text in the middle ──────
        text = cluster.ctype.name.replace("_", " ")
        text_color = color
        
        # Font settings
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.5
        thickness = 2

        # Get text size to center it
        (text_w, text_h), baseline = cv2.getTextSize(text, font, font_scale, thickness)
        text_x = x_sl.start + 5
        text_y = y_sl.start + 15

        cv2.putText(vis, text, (text_x, text_y),
                    font, font_scale, text_color, thickness, cv2.LINE_AA)

        # Draw stop line
        if stop_point:
            sx, sy = map(int, stop_point)
            cv2.line(vis, (cluster.bbox[2], sy), (cluster.bbox[3], sy), (0, 0, 220), 2)
            cv2.putText(vis, "STOP", (sx - 100, sy - 10), cv2.FONT_HERSHEY_COMPLEX_SMALL, 0.8, (0, 10, 240), 1)

    """# DRAW CENTERLINE
    if len(center_array) > 1:
        center_points = center_array.reshape((-1, 1, 2)).astype(np.int32)
        cv2.polylines(vis, [center_points], isClosed=False, 
                    color=(0, 230, 255), thickness=2)"""

    # Show results
    final_rgb = cv2.cvtColor(vis, cv2.COLOR_BGR2RGB)

    plt.figure(figsize=(16, 8))
    plt.subplot(1, 2, 1)
    plt.title("Original + ROI")
    plt.imshow(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    cv2.rectangle(frame, (off_x, off_y), (off_x + binary.shape[1], off_y + binary.shape[0]), (0, 255, 255), 3)
    plt.imshow(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    plt.axis("off")

    plt.subplot(1, 2, 2)
    plt.title("Clusters + Centerline (Green)")
    plt.imshow(final_rgb)
    plt.axis("off")

    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("image", help="Path to JPG image")
    args = parser.parse_args()
    evaluate_image(args.image)