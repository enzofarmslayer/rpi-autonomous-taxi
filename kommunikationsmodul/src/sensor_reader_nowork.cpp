#include "sensor_reader.hpp"
#include "log.hpp"
#include <unistd.h>
#include <cerrno>
#include <vector>
#include <sstream>



// NO work



SensorReader::SensorReader(Fd& sensor_fd, SharedState& st, UartWriter& uw)
    : sensor_(sensor_fd), st_(st), uartw_(uw) {}

void SensorReader::start() { thr_ = std::thread(&SensorReader::run, this); }
void SensorReader::join()  { if (thr_.joinable()) thr_.join(); }

void SensorReader::run() {
    std::vector<uint8_t> buf(128);
    std::string line_buffer;  // Accumulate data until newline
    bool have_prev = false;
    uint8_t prev = 0;

    while (!st_.global_stop.load()) {
        if (!sensor_) { 
            std::this_thread::sleep_for(std::chrono::seconds(1)); 
            continue; 
        }

        ssize_t r = ::read(sensor_.get(), buf.data(), buf.size());
        
        if (r > 0) {
            st_.sensor_seen.store(true);

            // Debug: Print raw received data
            std::cout << "Received " << r << " bytes: [";
            for (ssize_t i = 0; i < r; i++) {
                if (buf[i] >= 32 && buf[i] <= 126) {
                    std::cout << static_cast<char>(buf[i]);
                } else {
                    std::cout << "\\x" << std::hex << std::setfill('0') << std::setw(2) 
                              << static_cast<int>(buf[i]) << std::dec;
                }
            }
            std::cout << "]" << std::endl;
            // Append new data to line buffer
            line_buffer.append(reinterpret_cast<char*>(buf.data()), r);
            
            // Process complete lines (messages ending with '\n')
            size_t pos;
            while ((pos = line_buffer.find('\n')) != std::string::npos) {
                std::string line = line_buffer.substr(0, pos);
                line_buffer.erase(0, pos + 1);  // Remove processed line
                
                // Trim whitespace
                line.erase(0, line.find_first_not_of(" \r\t"));
                line.erase(line.find_last_not_of(" \r\t") + 1);
                
                if (line.empty()) continue;
                
                // Parse the message
                if (line.size() >= 2 && line[0] == 'U' && line[1] == ':') {
                    // Ultrasonic sensor message: "U:1" or "U:0"
                    handle_ultrasonic(line, have_prev, prev);
                    
                } else if (line.size() >= 2 && line[0] == 'D' && line[1] == '=') {
                    // Hall effect sensor message: "D=50"
                    handle_hall_sensor(line);
                    
                } else {
                    // Unknown message format
                    std::cerr << "Unknown sensor message: " << line << std::endl;
                }
            }
            
            // Prevent buffer from growing indefinitely
            if (line_buffer.size() > 256) {
                std::cerr << "Line buffer overflow, clearing" << std::endl;
                line_buffer.clear();
            }
            
        } else if (r == 0) {
            std::this_thread::sleep_for(std::chrono::milliseconds(50));
        } else {
            if (errno == EINTR) continue;
            std::this_thread::sleep_for(std::chrono::milliseconds(5));
        }
    }
}

void SensorReader::handle_ultrasonic(const std::string& line, bool& have_prev, uint8_t& prev) {
    if (line.size() < 3) return;
    
    char value = line[2];  // Character after "U:"
    std::cout << "Ultrasonic: " << value << std::endl;
    
    st_.sensor_byte.store(value);
    
    // Edge-trigger: only act if it actually changed
    if (!have_prev || value != prev) {
        prev = value;
        have_prev = true;
        
        if (value == '1') {
            std::cout << "OBSTACLE DETECTED - Stopping" << std::endl;
            st_.obstacle_stop.store(1);
            uartw_.request_send_now();
            
        } else if (value == '0') {
            std::cout << "Path clear - Resuming" << std::endl;
            st_.obstacle_stop.store(0);
            uartw_.request_send_now();
        }
    }
}

void SensorReader::handle_hall_sensor(const std::string& line) {
    try {
        // Parse "D=123" format
        std::string distance_str = line.substr(2);
        distance_str.erase(0, distance_str.find_first_not_of(" \t\r\n"));
        distance_str.erase(distance_str.find_last_not_of(" \t\r\n") + 1);
        int distance = std::stoi(distance_str);
        
        std::cout << "Distance = " << distance << " cm" << std::endl;
        
        // Store distance in shared state if you have a field for it
        // st_.hall_distance.store(distance);
        
        // Optional: Trigger action based on distance threshold
        // if (distance < 10) {
        //     st_.obstacle_stop.store(1);
        //     uartw_.request_send_now();
        // }
        
    } catch (const std::exception& e) {
        std::cerr << "Failed to parse Hall sensor distance: " << e.what() << std::endl;
    }
}