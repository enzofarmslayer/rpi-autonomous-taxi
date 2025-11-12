#pragma once
#include "fd.hpp"
#include "shared_state.hpp"
#include <condition_variable>
#include <mutex>
#include <thread>

class UartWriter {
public:
    UartWriter(Fd& styr_fd, SharedState& s);
    void start();
    void stop();
    void request_send_now();
    void notify_new_offset();

private:
    void run();
    void update_offset_angle(uint8_t new_offset);

    Fd& styr_;
    SharedState& st_;
    std::thread thr_;
    std::condition_variable cv_;
    std::mutex mx_;
    bool dirty_ = false;
    bool stop_  = false;
    uint8_t last_offset_angle_ = 0;
};
