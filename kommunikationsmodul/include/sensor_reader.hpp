#pragma once
#include "fd.hpp"
#include "shared_state.hpp"
#include "uart_writer.hpp"
#include <thread>

class SensorReader {
public:
    SensorReader(Fd& sensor_fd, SharedState& st, UartWriter& uw);
    void start();
    void join();

private:
    void run();

    Fd& sensor_;
    SharedState& st_;
    UartWriter& uartw_;
    std::thread thr_;
};
