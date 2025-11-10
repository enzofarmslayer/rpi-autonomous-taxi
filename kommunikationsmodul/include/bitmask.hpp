#pragma once
#include <cstdint>

enum class Bit : uint8_t {
    BIT_FRAM=0x80;
    BIT_STOP=0x40;
    BIT_VANSTER=0x20;
    BIT_HOGER=0x10;
    BIT_BAKAT=0x08;
};

//Behövs detta?
inline uint8_t bit(Bit b) {
    return static_cast<uint8_t>(b);
}