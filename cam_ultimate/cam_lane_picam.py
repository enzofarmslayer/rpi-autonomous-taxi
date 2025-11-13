#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from picamera2 import Picamera2
import cv2
import numpy as np

import utilities
from cam_lane import getLaneCurve   # din lane-funktion

FRAME_W, FRAME_H = 640, 480       # verklig kamera
LANE_W, LANE_H   = 480, 240       # det getLaneCurve använder

def main():
    picam2 = Picamera2()
    config = picam2.create_preview_configuration(
        main={"format": "RGB888", "size": (FRAME_W, FRAME_H)}
    )
    picam2.configure(config)
    picam2.start()

    # Trackbars precis som i din gamla mp4-loop
    initialTrackbarValues = [102, 80, 20, 214]
    utilities.initializeTrackbars(initialTrackbarValues, wT=LANE_W, hT=LANE_H)

    try:
        while True:
            frame = picam2.capture_array()
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

            img = cv2.resize(frame, (LANE_W, LANE_H))

            curve = getLaneCurve(img, display=2)
            print("curve:", curve)

            key = cv2.waitKey(1) & 0xFF
            if key in (27, ord('q')):
                break

    finally:
        picam2.stop()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
