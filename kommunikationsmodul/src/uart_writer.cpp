#include "uart_writer.hpp"
#include "bitmask.hpp"
#include "log.hpp"
#include <sys/uio.h>
#include <termios.h>
#include <unistd.h>
#include <cstdio>

UartWriter::UartWriter(Fd& styr_fd, SharedState& s)
    : styr_(styr_fd), st_(s) {}

void UartWriter::start() { thr_ = std::thread(&UartWriter::run, this); }

void UartWriter::stop() {
    {
        std::lock_guard<std::mutex> lk(mx_);
        stop_ = true;
        dirty_ = true;
    }
    cv_.notify_one();
    if (thr_.joinable()) thr_.join();
}

void UartWriter::request_send_now() {
    auto cur2 = st_.current_mask.load();
    st_.desired_mask.store(st_.current_mask.load());
    {
        std::lock_guard<std::mutex> lk(mx_);
        dirty_ = true;
    }
    cv_.notify_one();
}

void UartWriter::run() {
    std::unique_lock<std::mutex> lk(mx_);
    while (!stop_) {
        cv_.wait(lk, [&]{ return dirty_ || stop_; });
        if (stop_) break;
        dirty_ = false;
        lk.unlock();

        if (styr_) {
            uint8_t out;
            uint8_t current = st_.desired_mask.load();

            if(st_.obstacle_stop){
                if(current & 0x80) {
                    current = 0x40;
                }
            }
            
            ssize_t wr = ::write(styr_.get(), &current, 1);
            if (wr != 1) perror("UART write");
            tcdrain(styr_.get());
        }

        lk.lock();
    }
}
