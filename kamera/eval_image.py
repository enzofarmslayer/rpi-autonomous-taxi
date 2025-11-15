import argparse
import cv2
import numpy as np
import matplotlib.pyplot as plt

from config import FRAME_W, FRAME_H
from process_frame import (
    process_frame,
    extract_roi,
    preprocess,
    get_centerline_points,
)


def evaluate_image(image_path: str):
    frame = cv2.imread(image_path)
    if frame is None:
        raise FileNotFoundError(f"Could not read image: {image_path}")

    frame = cv2.resize(frame, (FRAME_W, FRAME_H))

    # Run main pipeline
    result = process_frame(frame, debug=True)
    found = result["found"]
    angle = result["angle"]
    debug_frame = result["debug_frame"]

    if found:
        print(f"Offset: {angle:.1f}")
    else:
        print("No line detected")

    # ROI + binary + ROI centerline
    roi, (off_x, off_y) = extract_roi(frame)
    binary = preprocess(roi)
    centers_roi = get_centerline_points(binary)

    roi_vis = cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)

    if centers_roi:
        pts_roi = np.array([[cx, cy] for (cx, cy) in centers_roi], dtype=np.int32)
        if len(pts_roi) >= 2:
            cv2.polylines(
                roi_vis,
                [pts_roi],
                isClosed=False,
                color=(0, 240, 255),
                thickness=3,
            )

    # Plot
    plt.figure(figsize=(12, 6))

    plt.subplot(1, 2, 1)
    title_left = "Full view"
    plt.title(title_left)
    plt.imshow(cv2.cvtColor(debug_frame, cv2.COLOR_BGR2RGB))
    plt.axis("off")

    plt.subplot(1, 2, 2)
    plt.title("ROI Binary")
    plt.imshow(cv2.cvtColor(roi_vis, cv2.COLOR_BGR2RGB))
    plt.axis("off")

    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("image", help="Path to JPG image")
    args = parser.parse_args()
    evaluate_image(args.image)
