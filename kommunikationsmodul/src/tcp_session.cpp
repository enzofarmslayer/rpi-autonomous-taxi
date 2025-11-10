#include "tcp_session.hpp"
#include "bitmask.hpp"
#include "uart.hpp"
#include "log.hpp"
#include <sys/socket.h>
#include <unistd.h>
#include <cstdio>

TcpSession::TcpSession(int fd, SharedState& st, UartWriter& uw)
    : fd_(fd), st_(st), uartw_(uw) {}

void TcpSession::run() {
    set_nodelay(fd_);
    LOG_INFO("Klient ansluten");
    std::thread rx(&TcpSession::rx_loop, this);
    std::thread tx(&TcpSession::tx_loop, this);
    rx.join(); tx.join();
    ::close(fd_);
    LOG_INFO("Klient frånkopplad");
}

void TcpSession::rx_loop() {
    std::string buf; buf.reserve(1024);
    char tmp[1024];
    while (!stop_) {
        ssize_t r = ::recv(fd_, tmp, sizeof(tmp), 0);
        if (r <= 0) break;
        buf.append(tmp, tmp + r);

        size_t pos;
        while ((pos = buf.find('\n')) != std::string::npos) {
            std::string line = buf.substr(0, pos);
            buf.erase(0, pos + 1);
            if (!line.empty() && line.back() == '\r') line.pop_back();
            if (!handle_command(line)) { stop_ = true; break; }
        }
    }
    stop_ = true;
}

void TcpSession::tx_loop() {
    int seq = 0;
    while (!stop_) {
        char hex[3] = {0};
        if (st_.sensor_seen.load()) {
            std::snprintf(hex, sizeof(hex), "%02X", st_.sensor_byte.load());
        } else {
            hex[0] = '\0';
        }
        char line[256];
        int n = std::snprintf(line, sizeof(line),
                              "{\"seq\":%d,\"batt_v\":%.2f,\"speed\":%.2f,\"sensor_raw\":\"%s\"}\n",
                              seq++, 7.6, 0.0, hex);
        std::lock_guard<std::mutex> lk(send_mx_);
        if (::send(fd_, line, n, 0) <= 0) { stop_ = true; break; }
        std::this_thread::sleep_for(std::chrono::milliseconds(50)); // 20 Hz
    }
}

bool TcpSession::handle_command(const std::string& cmd) {
    LOG_INFO("CMD: " << cmd);
    if (cmd == "quit") return false;

    auto set_bit = [&](Bit b) {
        uint8_t m = st_.current_mask.load();
        m |= bit(b);
        st_.current_mask.store(m);
    };
    auto clear_bit = [&](Bit b) {
        uint8_t m = st_.current_mask.load();
        m &= ~bit(b);
        st_.current_mask.store(m);
    };
    auto request = [&] { uartw_.request_send_now(); };

    if (cmd == "stop_down") { set_bit(Bit::Stop); request(); }
    else if (cmd == "stop_up") { clear_bit(Bit::Stop); request(); }
    else if (cmd == "fram_down") {
        if (!(st_.current_mask.load() & bit(Bit::Fram))) { set_bit(Bit::Fram); request(); }
    } else if (cmd == "fram_up") { clear_bit(Bit::Fram); request(); }
    else if (cmd == "bakåt_down") {
        if (!(st_.current_mask.load() & bit(Bit::Fram))) { set_bit(Bit::Bakat); request(); }
    } else if (cmd == "bakåt_up") { clear_bit(Bit::Bakat); request(); }
    else if (cmd == "vänster_down") {
        set_bit(Bit::Vanster); clear_bit(Bit::Hoger); request();
    } else if (cmd == "vänster_up") { clear_bit(Bit::Vanster); request(); }
    else if (cmd == "höger_down") {
        set_bit(Bit::Hoger); clear_bit(Bit::Vanster); request();
    } else if (cmd == "höger_up") { clear_bit(Bit::Hoger); request(); }
    // okända kommandon ignoreras
    return true;
}
