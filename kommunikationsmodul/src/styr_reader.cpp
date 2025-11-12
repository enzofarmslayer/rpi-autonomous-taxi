#include "styr_reader.hpp"
#include "log.hpp"
#include <unistd.h>
#include <cerrno>
#include <vector>
using namespace std;

StyrReader::StyrReader(Fd& styr_fd, SharedState& st, UartWriter& uw)
    : styr_(styr_fd), st_(st), uartw_(uw) {}

void StyrReader::start() { thr_ = std::thread(&StyrReader::run, this); }
void StyrReader::join()  { if (thr_.joinable()) thr_.join(); }

void StyrReader::run() {
    std::vector<uint8_t> buf(128);

    while (!st_.global_stop.load()) {
        if (!styr_) { std::this_thread::sleep_for(std::chrono::seconds(1)); continue; }

       ssize_t r = ::read(styr_.get(), buf.data(), buf.size()); // blocking or non-blocking
        if (r >= 2) { // need at least 2 bytes for (identifier, value)
            uint8_t id  = buf[0];
            uint8_t val = buf[1];
            char cid = (char)id;
            std::cout << "PID VALUES ---> ID: " << cid << "  Value: " << +val << std::endl;
        } 
        else if (r > 0) {
            std::this_thread::sleep_for(std::chrono::milliseconds(50));
        } else {
            if (errno == EINTR) continue;
            std::this_thread::sleep_for(std::chrono::milliseconds(5));
        }
    }
}

//     void StyrReader::run() {
//     uint8_t b = 0;
//     bool have_prev = false;
//     uint8_t prev = 0;

//     while (!st_.global_stop.load()) {
//         if (!styr_) { std::this_thread::sleep_for(std::chrono::seconds(1)); continue; }

//         ssize_t r = ::read(styr_.get(), &b, 1);
//         if (r == 1) {
//             if (!have_prev) {
//                 prev = b;
//                 have_prev = true; // wait for next byte
//             } else {
//                 uint8_t id  = prev;
//                 uint8_t val = b;
//                 have_prev = false;
//                 char cid = (char)id;
//                 std::cout << "ID: " << cid << "  Value: " << +val << std::endl;
//             }
//         } else if (r == 0) {
//             std::this_thread::sleep_for(std::chrono::milliseconds(50));
//         } else {
//             if (errno == EINTR) continue;
//             std::this_thread::sleep_for(std::chrono::milliseconds(5));
//         }
//     }
// }
