#include "sensor_reader.hpp"
#include "log.hpp"
#include <unistd.h>
#include <cerrno>
#include <vector>
using namespace std;

SensorReader::SensorReader(Fd& sensor_fd, SharedState& st, UartWriter& uw)
    : sensor_(sensor_fd), st_(st), uartw_(uw) {}

void SensorReader::start() { thr_ = std::thread(&SensorReader::run, this); }
void SensorReader::join()  { if (thr_.joinable()) thr_.join(); }

void SensorReader::run() {
    std::vector<uint8_t> buf(128);
    bool have_prev = false;
    uint8_t prev = 0;

    while (!st_.global_stop.load()) {
        if (!sensor_) { std::this_thread::sleep_for(std::chrono::seconds(1)); continue; }

        ssize_t r = ::read(sensor_.get(), buf.data(), buf.size()); // blocking
        if (r > 0) {
            uint8_t last = buf[size_t(r - 1)];
            std::cout << last << endl;
            st_.sensor_seen.store(true);
            st_.sensor_byte.store(last);

            // Edge-trigger: only act if it actually changed
            if (!have_prev || last != prev) {
                prev = last; 
                have_prev = true;

                if (last == '1') {
                    st_.obstacle_stop.store(1);
                } else if (last == '0') {
                    st_.obstacle_stop.store(0);
                } else {
                    // ignore other bytes
                    continue;
                }
                uartw_.request_send_now();  // trigger exactly once per change
            }
        } else if (r == 0) {
            std::this_thread::sleep_for(std::chrono::milliseconds(50));
        } else {
            if (errno == EINTR) continue;
            std::this_thread::sleep_for(std::chrono::milliseconds(5));
        }
    }
}
