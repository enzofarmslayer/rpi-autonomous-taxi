#include "uart_writer.hpp"
#include "bitmask.hpp"
#include "log.hpp"
#include <sys/uio.h>
#include <termios.h>
#include <unistd.h>
#include <cstdio>

UartWriter::UartWriter(Fd& styr_fd, SharedState& s)
    : styr_(styr_fd), st_(s), last_offset_angle_(0) {}

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

void UartWriter::notify_new_offset() {
    std::lock_guard<std::mutex> lk(mx_);
    dirty_ = true;
    cv_.notify_one();
}

void UartWriter::run() {
    std::unique_lock<std::mutex> lk(mx_);
    while (!stop_) {
        cv_.wait(lk, [&]{ return dirty_ || stop_; });
        if (stop_) break;
        dirty_ = false;
        lk.unlock();

        if (st_.offset_angle_needs_update.load(std::memory_order_relaxed)) {
            uint8_t new_offset = st_.offset_angle.load(std::memory_order_relaxed);
            st_.offset_angle_needs_update.store(false, std::memory_order_relaxed);

            if (new_offset != last_offset_angle_) {
                last_offset_angle_ = new_offset;

                if (styr_) {
                    ssize_t wr = ::write(styr_.get(), &new_offset, 1);
                    if (wr != 1) perror("UART write offset");
                    tcdrain(styr_.get());
                    LOG_INFO("Offset angle sent over UART: " << int(new_offset));
                }
            }
        }

        if (styr_) {
            uint8_t out;
            uint8_t current = st_.desired_mask.load();

            if(st_.obstacle_stop.load()){
                if(current & bit(Bit::Fram)){
                    current = bit(Bit::Stop);
                }
            }
            
            ssize_t wr = ::write(styr_.get(), &current, 1);
            if (wr != 1) perror("UART write");
            tcdrain(styr_.get());
        }

        lk.lock();
    }
}