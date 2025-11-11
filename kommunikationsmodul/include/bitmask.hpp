#pragma once
#include <cstdint>

enum class Bit : uint8_t {
    Fram=0x80,
    Stop=0x40,
    Vanster=0x20,
    Hoger=0x10,
    Bakat=0x08,
};

//Behövs detta?
inline uint8_t bit(Bit b) {
    return static_cast<uint8_t>(b);
}