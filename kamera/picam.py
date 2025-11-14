#!/usr/bin/env python3
# Runs only on Raspberry Pi

from picamera2 import Picamera2
import cv2
import socket
import time

import config
from kamera.streamer import FrameTCPStreamer
from process_frame import process_frame   # your vision pipeline

picam2 = Picamera2()
streamer = FrameTCPStreamer(host="0.0.0.0", port=config.PORT)

JPEG_QUALITY = 60  # adjust as you like (0–100)

def picam_init():
    cam_cfg = picam2.create_preview_configuration(
        main={"format": "RGB888", "size": (config.FRAME_W, config.FRAME_H)}
    )
    picam2.configure(cam_cfg)
    picam2.start()

def streamer_init():
    streamer.start()

def capture_frame():
    frame = picam2.capture_array()
    # Picamera2 gives RGB, OpenCV wants BGR
    frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
    return frame

# --- Heading quantization & Unix socket telemetry ---

def quantize_heading_deg_to_7bit(heading_deg: float, lo=-25.0, hi=25.0) -> int:
    """
    Map heading angle in degrees to a 7-bit integer (0..100).
    Values outside [lo, hi] are clamped.
    """
    clamped = max(lo, min(hi, heading_deg))
    norm = (clamped - lo) / (hi - lo)
    return int(round(norm * 127)) & 0x7F  # 0..127


SOCKET_PATH = "/tmp/cam_offset.sock"
_udps = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)


def send_heading(heading_deg: float):
    q = quantize_heading_deg_to_7bit(heading_deg)
    try:
        _udps.sendto(bytes([q]), SOCKET_PATH)  # 1 byte to local socket file
    except FileNotFoundError:
        # Receiver not up yet; ignore and keep running
        pass
    except Exception:
        # Swallow transient errors to avoid stalling vision loop
        pass


def main():
    picam_init()
    streamer_init()

    print("Camera + streamer running. Press Ctrl+C to exit.")
    fps_t0 = time.time()
    frame_count = 0

    try:
        while True:
            frame = capture_frame()

            # Run vision pipeline
            result = process_frame(frame, debug=True)
            heading_corr = result["angle"] if result["found"] else 0.0
            vis = result["debug_frame"] if result["debug_frame"] is not None else frame

            # Send 7-bit heading via Unix datagram socket
            send_heading(heading_corr)

            # Send JPEG to TCP client (if connected)
            if streamer.has_client():
                ok, jpg = cv2.imencode(
                    ".jpg", vis, [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY]
                )
                if ok:
                    streamer.push_jpeg(jpg.tobytes())

            # (Optional) FPS print every second for debugging
            frame_count += 1
            now = time.time()
            if now - fps_t0 >= 1.0:
                print(f"FPS: {frame_count / (now - fps_t0):.1f}, heading: {heading_corr:.2f}")
                fps_t0 = now
                frame_count = 0

    except KeyboardInterrupt:
        print("Stopping...")

    finally:
        try:
            picam2.stop()
        except Exception:
            pass
        streamer.stop()
        _udps.close()
        print("Exited.")

if __name__ == "__main__":
    main()
