#pragma once
#include "fd.hpp"
#include "shared_state.hpp"
#include "uart_writer.hpp"
#include <thread>

class StyrReader {
public:
    StyrReader(Fd& styr_fd, SharedState& st, UartWriter& uw);
    void start();
    void join();

private:
    void run();

    Fd& styr_;
    SharedState& st_;
    UartWriter& uartw_;
    std::thread thr_;
};
