#pragma once
#include <atomic>
#include <cstdint>

struct SharedState {
    std::atomic<uint8_t> sensor_byte{0};     // latest byte seen from sensor UART
    std::atomic<bool>    sensor_seen{false}; // have we received anything yet?
    std::atomic<bool>    obstacle_stop{0};     // true when sensor says 0x01
    std::atomic<uint8_t>    current_mask{0};  // bitmask to styr AVR
    std::atomic<uint8_t> desired_mask{0};   // latest mask we want on styr UART
    //std::atomic<bool>    obstacle{0};       // true when sensor says 0x01
    std::atomic<bool>    global_stop{false};
    std::atomic<uint8_t>     offset_angle{0};   // calibration offset for steering angle TCP
    //std::atomic<uint8_t>     offset_from_center{0};  // calibration offset for lateral position TCP
};