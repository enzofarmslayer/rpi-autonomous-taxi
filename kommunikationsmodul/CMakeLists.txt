cmake_minimum_required(VERSION 3.13)
project(kommunikationsmodul)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
add_compile_options(-O2 -Wall -Wextra -Wpedantic)

include_directories(${CMAKE_SOURCE_DIR}/include)

add_executable(kommunikationsmodul
        src/main.cpp
        src/uart.cpp    
        src/uart_writer.cpp
        src/tcp_session.cpp
        src/sensor_reader.cpp
        src/styr_reader.cpp
        )

target_link_libraries(kommunikationsmodul
        pthread
        )