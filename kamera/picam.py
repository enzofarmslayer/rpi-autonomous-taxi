# Runs only on Raspberry Pi

from picamera2 import Picamera2
import cv2
import socket
import time
from enum import Enum
import os

import config
from streamer import FrameTCPStreamer
from process_frame import process_frame, Direction
import visualization

picam2 = Picamera2()
streamer = FrameTCPStreamer(host="0.0.0.0", port=config.PORT)
_udps = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)

SOCKET_PATH = "/tmp/cam_offset.sock"
JPEG_QUALITY = 60

SOCKET_PATH_CPP_TO_PY = "/tmp/cpp_to_py.sock"

_rx_sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
_rx_sock.setblocking(False)

try:
    os.unlink(SOCKET_PATH_CPP_TO_PY)
except FileNotFoundError:
    pass

_rx_sock.bind(SOCKET_PATH_CPP_TO_PY)

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

def recv_uint8_array():
    # ta emot "lagom mycket", C++ kan skicka max 255 (uint8_t) element
    data, _ = _rx_sock.recvfrom(1 + 255)  # 1 byte count + upp till 255 data

    if not data or len(data) < 1:
        return []

    count = data[0]
    print("KOM HIT")

    available = len(data) - 1

    if count > available:
        count = available

    if count == 0:
        return []

    vals = list(data[1:1 + count])
    return vals # V, F, S, B

def send_stop():
    try:
        _udps.sendto(bytes([0xFF]), SOCKET_PATH)
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
    route_len = 0
    _current_dir_index = 0
    _in_intersection = False
    _intersection_count = 0
    route_complete = False
    on_stopline = False
    time_of_stop = 0.0
    vals = []

    try:
        while True:
            frame = capture_frame()

            try:
                vals = recv_uint8_array()
                if vals:
                    print("Fick array från C++:", vals)
                    route_len = len(vals)
            except BlockingIOError:
                pass
            
            dir = Direction.STRAIGHT 
            if vals:
                command = vals[_current_dir_index]
                if command == 86:
                    dir == Direction.LEFT
                elif command == 72:
                    dir == Direction.RIGHT

            # Run vision processing pipeline
            res = process_frame(frame, dir)

            if not _in_intersection and res.other_path is not None:
                if _intersection_count > 1:
                    _in_intersection = True
                    print("Intersection detected")
                    _intersection_count = 2
                else:
                    _intersection_count += 1

            if _in_intersection and res.other_path is None:
                if _intersection_count <= 0:
                    _in_intersection = False
                    print("Intersection done")
                    _current_dir_index += 1
                    _intersection_count = 0
                else:
                    _intersection_count -= 1
            
            if res.stop_point:
                if _current_dir_index >= route_len-1:
                    send_stop()
                    print("STOPPPPPPPP I LAGENS NAMN")
                    print("Route complete")
                    print(f"Distance to stopline: {res.dist_to_stopline:.2f}")
                else:
                    t = time.time()
                    if not on_stopline:
                        time_of_stop = t
                        on_stopline = True
                    _current_dir_index += 1

            if on_stopline:
                t = time.time()
                if t-time_of_stop > 2.0:
                    on_stopline = False

            # Send 7-bit heading via Unix datagram socket
            send_heading(res.heading)

            # Send JPEG to TCP client (if connected)
            if streamer.has_client():
                vis = visualization.build(frame, res)
                ok, jpg = cv2.imencode(
                    ".jpg", vis, [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY]
                )
                if ok:
                    streamer.push_jpeg(jpg.tobytes())
 
            # FPS print every 2 seconds for debugging
            frame_count += 1
            now = time.time()
            if now - fps_t0 >= 2.0:
                print(f"FPS: {frame_count / (now - fps_t0):.1f}, heading: {res.heading:.1f}")
                fps_t0 = now
                frame_count = 0

    except KeyboardInterrupt:
        print("Stopping...")
        send_stop()

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
