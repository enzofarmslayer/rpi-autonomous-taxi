# Autonomous robot taxi

A self-driving model car that acts as a robot taxi on a predefined road network with stop lines, intersections and curves. It follows the lane using a camera, stops for obstacles, and can switch between autonomous and manual driving from a laptop over WiFi.

Built by a group of seven students in the course TSEA29 (Konstruktion med mikrodatorer) at Linköping University, autumn 2025.

## System overview

| Module | Hardware | Code |
| --- | --- | --- |
| Communication module | Raspberry Pi 3B+ | `kommunikationsmodul/` (C++): multithreaded hub that talks to the two microcontrollers over UART and to the laptop over TCP/WiFi, and plans the route. |
| Camera | Raspberry Pi Camera Module 2 | `kamera/`, `cam_ultimate/` (Python, OpenCV): finds the lane boundaries and computes the car's offset from the lane center. |
| Steering module | ATmega1284 | `styrmodul/` (C): PWM control of the motor and steering servo, with PID control to keep the car in its lane. |
| Sensor module | ATmega1284 | `sensormodul/` (C++): ultrasonic distance sensor for obstacle detection and Hall-effect sensors for wheel speed and distance. |
| Laptop GUI | PC | `TCP/` (Python, Tkinter): telemetry, live camera view, manual driving and PID tuning over TCP. |

The modules exchange binary messages in the format `[START][TYPE][LENGTH][DATA]` over UART and TCP.
