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

private:
    void run();

    Fd& styr_;
    SharedState& st_;
    std::thread thr_;
    std::condition_variable cv_;
    std::mutex mx_;
    bool dirty_ = false;
    bool stop_  = false;
};
