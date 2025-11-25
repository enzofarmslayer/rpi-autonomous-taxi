# Runs only on Raspberry Pi

from picamera2 import Picamera2
import cv2
import socket
import time
from enum import Enum

import config
from streamer import FrameTCPStreamer
from process_frame import process_frame, Direction

picam2 = Picamera2()
streamer = FrameTCPStreamer(host="0.0.0.0", port=config.PORT)
_udps = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)

SOCKET_PATH = "/tmp/cam_offset.sock"
JPEG_QUALITY = 60

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
    # frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
    return frame

def quantize_heading_to_7bit(heading_deg: float, min=-25.0, max=25.0) -> int:
    """
    Map heading angle in degrees to a 7-bit integer (0..100).
    """
    clamped = max(min, min(max, heading_deg))
    norm = (clamped - min) / (max - min)
    return int(round(norm * 127)) & 0x7F  # 0..127

def send_heading(heading_deg: float):
    q = quantize_heading_to_7bit(heading_deg)
    try:
        _udps.sendto(bytes([q]), SOCKET_PATH)
    except FileNotFoundError:
        pass
    except Exception:
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

            # Run vision processing pipeline
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
