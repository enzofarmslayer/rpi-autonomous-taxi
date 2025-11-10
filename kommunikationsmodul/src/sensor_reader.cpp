#include "sensor_reader.hpp"
#include "log.hpp"
#include <unistd.h>
#include <cerrno>
#include <vector>

SensorReader::SensorReader(Fd& sensor_fd, SharedState& st, UartWriter& uw)
    : sensor_(sensor_fd), st_(st), uartw_(uw) {}

void SensorReader::start() { thr_ = std::thread(&SensorReader::run, this); }
void SensorReader::join()  { if (thr_.joinable()) thr_.join(); }

void SensorReader::run() {
    std::vector<uint8_t> buf(128);
    while (!st_.global_stop.load()) {
        if (!sensor_) { std::this_thread::sleep_for(std::chrono::milliseconds(200)); continue; }
        ssize_t r = ::read(sensor_.get(), buf.data(), buf.size());
        if (r > 0) {
            uint8_t last = buf[size_t(r - 1)];
            LOG_INFO("[Sensor] byte=0x" << std::hex << int(last) << std::dec);

            st_.sensor_seen.store(true);
            st_.sensor_byte.store(last);

            if (last == '1') {
                st_.obstacle.store(true);
                st_.obstacle_stop.store(1);
                uartw_.request_send_now();
            } else if (last == '0') {
                st_.obstacle.store(false);
                st_.obstacle_stop.store(0);
                uartw_.request_send_now();
            }
        } else if (r == 0) {
            std::this_thread::sleep_for(std::chrono::milliseconds(50));
        } else {
            if (errno == EINTR) continue;
            std::this_thread::sleep_for(std::chrono::milliseconds(5));
        }
    }
}
