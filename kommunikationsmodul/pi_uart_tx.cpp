// Build: g++ -O2 -Wall -std=c++17 pi_uart_tx.cpp -o pi_uart_tx
// Run:   ./pi_uart_tx /dev/ttyUSB0 115200
// Test kan ta bort senare

#include <array>
#include <chrono>
#include <cstdint>
#include <cstring>
#include <fcntl.h>
#include <iomanip>
#include <iostream>
#include <optional>
#include <stdexcept>
#include <string>
#include <string_view>
#include <sys/select.h>
#include <termios.h>
#include <thread>
#include <unistd.h>
#include <vector>

namespace uart {

constexpr uint8_t START_BYTE = 0xAA;

enum class MsgType : uint8_t {
    TEST        = 0x00, // typ 0, testram
    PING        = 0x01,
    CFG_PID     = 0x10,
    MANUAL_PWM  = 0x11
};

inline void sleep_ms(int ms) {
    std::this_thread::sleep_for(std::chrono::milliseconds(ms));
}

inline void hexdump(const uint8_t* p, std::size_t n) {
    for (std::size_t i = 0; i < n; ++i) {
        std::cout << std::hex << std::uppercase << std::setw(2)
                  << std::setfill('0') << static_cast<int>(p[i])
                  << (i + 1 == n ? "" : " ");
    }
    std::cout << std::dec << "\n";
}

inline speed_t baud_to_flag(long baud) {
    switch (baud) {
        case 9600:   return B9600;
        case 19200:  return B19200;
        case 38400:  return B38400;
        case 57600:  return B57600;
        case 115200: return B115200;
        case 230400: return B230400;
        default:     return B115200; // fallback
    }
}

class SerialPort {
public:
    SerialPort(std::string path, long baud)
    : path_(std::move(path)), baud_(baud)
    {
        fd_ = ::open(path_.c_str(), O_RDWR | O_NOCTTY | O_NONBLOCK);
        if (fd_ < 0) {
            throw std::runtime_error("open(" + path_ + "): " + std::string(std::strerror(errno)));
        }

        termios tio{};
        if (tcgetattr(fd_, &tio) < 0) {
            close_and_throw("tcgetattr");
        }

        cfmakeraw(&tio);
        tio.c_cflag |= (CLOCAL | CREAD);
        tio.c_cflag &= ~PARENB;
        tio.c_cflag &= ~CSTOPB;
        tio.c_cflag &= ~CSIZE; tio.c_cflag |= CS8;
        tio.c_cflag &= ~CRTSCTS;

        const auto flag = baud_to_flag(baud_);
        cfsetispeed(&tio, flag);
        cfsetospeed(&tio, flag);

        tio.c_cc[VMIN]  = 0;
        tio.c_cc[VTIME] = 0;

        if (tcsetattr(fd_, TCSANOW, &tio) < 0) {
            close_and_throw("tcsetattr");
        }

        tcflush(fd_, TCIOFLUSH);
    }

    ~SerialPort() {
        if (fd_ >= 0) ::close(fd_);
    }

    SerialPort(const SerialPort&) = delete;
    SerialPort& operator=(const SerialPort&) = delete;

    ssize_t write_all(const uint8_t* data, std::size_t n) {
        std::size_t sent = 0;
        while (sent < n) {
            const auto r = ::write(fd_, data + sent, n - sent);
            if (r < 0) {
                if (errno == EAGAIN || errno == EWOULDBLOCK) {
                    sleep_ms(1);
                    continue;
                }
                throw std::runtime_error("write: " + std::string(std::strerror(errno)));
            }
            sent += static_cast<std::size_t>(r);
        }
        return static_cast<ssize_t>(sent);
    }

    ssize_t read_into(uint8_t* buf, std::size_t cap) {
        const auto r = ::read(fd_, buf, cap);
        if (r < 0 && (errno == EAGAIN || errno == EWOULDBLOCK)) return 0;
        if (r < 0) throw std::runtime_error("read: " + std::string(std::strerror(errno)));
        return r;
    }

    int fd() const { return fd_; }
    long baud() const { return baud_; }
    const std::string& path() const { return path_; }

private:
    void close_and_throw(const char* what) {
        int e = errno;
        ::close(fd_);
        fd_ = -1;
        throw std::runtime_error(std::string(what) + ": " + std::string(std::strerror(e)));
    }

    std::string path_;
    long baud_;
    int fd_{-1};
};

// Frame builder: [0xAA | TYPE | LEN | DATA...]
inline std::size_t build_frame(std::array<uint8_t, 256>& buf,
                               MsgType type, const void* payload, uint8_t len)
{
    std::size_t i = 0;
    buf[i++] = START_BYTE;
    buf[i++] = static_cast<uint8_t>(type);
    buf[i++] = len;
    if (len && payload) {
        std::memcpy(&buf[i], payload, len);
        i += len;
    }
    return i;
}

// RX parser for debugging/inspection
class RxParser {
public:
    enum class State { WAIT_START, WAIT_TYPE, WAIT_LEN, WAIT_DATA };

    struct Result {
        uint8_t type{};
        std::vector<uint8_t> data;
    };

    RxParser() { reset(); }

    // Feed a single byte. Returns a completed frame (if any).
    std::optional<Result> feed(uint8_t b) {
        switch (st_) {
            case State::WAIT_START:
                if (b == START_BYTE) st_ = State::WAIT_TYPE;
                break;

            case State::WAIT_TYPE:
                type_ = b;
                st_ = State::WAIT_LEN;
                break;

            case State::WAIT_LEN:
                len_ = b;
                data_.clear();
                data_.reserve(len_);
                if (len_ == 0) {
                    Result out{type_, {}};
                    reset(); // ready for next
                    return out;
                }
                st_ = State::WAIT_DATA;
                break;

            case State::WAIT_DATA:
                data_.push_back(b);
                if (data_.size() == len_) {
                    Result out{type_, std::move(data_)};
                    reset();
                    return out;
                }
                break;
        }
        return std::nullopt;
    }

    void reset() {
        st_ = State::WAIT_START;
        type_ = 0;
        len_  = 0;
        data_.clear();
    }

private:
    State st_{State::WAIT_START};
    uint8_t type_{0};
    uint8_t len_{0};
    std::vector<uint8_t> data_;
};

} // namespace uart

// ---- main -------------------------------------------------------------

int main(int argc, char** argv) {
    using namespace uart;

    const std::string dev  = (argc > 1) ? argv[1] : "/dev/ttyUSB0";
    const long baud       = (argc > 2) ? std::strtol(argv[2], nullptr, 10) : 115200;

    try {
        SerialPort sp(dev, baud);
        std::cout << "Opened " << sp.path() << " @ " << sp.baud() << " 8N1\n";

        std::array<uint8_t, 256> frame{};
        RxParser rx;

        // 1) Send an initial TEST frame with payload 0xFF
        uint8_t testdata = 0xFF;
        std::size_t n = build_frame(frame, MsgType::TEST, &testdata, 1);

        std::cout << "TX INIT TEST FRAME: ";
        hexdump(frame.data(), n);

        sp.write_all(frame.data(), n);

        // 2) RX loop (and place for future TX)
        std::array<uint8_t, 128> buf{};
        for (;;) {
            const auto r = sp.read_into(buf.data(), buf.size());
            if (r > 0) {
                for (ssize_t i = 0; i < r; ++i) {
                    if (auto got = rx.feed(buf[static_cast<std::size_t>(i)])) {
                        std::cout << "RX frame type=0x"
                                  << std::hex << std::uppercase << std::setw(2) << std::setfill('0')
                                  << static_cast<int>(got->type)
                                  << std::dec << " len=" << got->data.size();
                        if (!got->data.empty()) {
                            std::cout << " data: ";
                            hexdump(got->data.data(), got->data.size());
                        } else {
                            std::cout << "\n";
                        }
                    }
                }
            }
            sleep_ms(10);
        }
    } catch (const std::exception& e) {
        std::cerr << "fatal: " << e.what() << "\n";
        return 1;
    }
}
