#pragma once
#include "shared_state.hpp"
#include "uart_writer.hpp"
#include "bitmask.hpp"
#include <atomic>
#include <mutex>
#include <string>

class TcpSession {
public:
    TcpSession(int fd, SharedState& st, UartWriter& uw);
    void run();

private:
    void rx_loop();
    void tx_loop();
    bool handle_command(const std::string& cmd);

    int fd_;
    SharedState& st_;
    UartWriter& uartw_;
    std::atomic<bool> stop_{false};
    std::mutex send_mx_;
};
