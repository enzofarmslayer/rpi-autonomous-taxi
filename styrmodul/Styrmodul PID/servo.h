#include <avr/io.h>
#include <avr/interrupt.h>
#include <stdint.h>
#include <stdbool.h>


#define PID_P 3.0
#define PID_I 0.0
#define PID_D 0.0

void servo_init(void);
void set_servo_value(uint16_t percent);
void servo_pid(int8_t error_angle);

void clock_init(void);          // startar 1ms-tick
uint32_t millis(void);          // nuvarande ms-r�knare
bool ms_elapsed(uint32_t *t, uint16_t period_ms); // "har period_ms passerat?


void servo_tick_run(int8_t current_error); // k�r PID vid tidslucka
