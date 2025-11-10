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
            const uint8_t want = st_.desired_mask.load();
            const bool can_back = (st_.obstacle_stop.load() == 0) &&
                                  (want & bit(Bit::Bakat));
            out = can_back ? want : bit(Bit::Stop);

            ssize_t wr = ::write(styr_.get(), &out, 1);
            if (wr != 1) perror("UART write");
            tcdrain(styr_.get());
            LOG_INFO("UART TX mask=0x" << std::hex << int(out) << std::dec);
        }

        lk.lock();
    }
}
