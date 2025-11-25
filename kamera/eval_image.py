import cv2
import numpy as np
import matplotlib.pyplot as plt
import argparse
import time

import process_frame as p_frame
import visualization

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

    pf = p_frame.process_frame(frame, p_frame.Direction.RIGHT)
    vis = visualization.build(frame, pf)

    # Show results
    plt.figure(figsize=(9, 6))

    # ROI visualization with clusters + lane boundaries
    plt.imshow(vis)
    plt.axis("off")

    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("image", help="Path to JPG image")
    args = parser.parse_args()
    evaluate_image(args.image)
