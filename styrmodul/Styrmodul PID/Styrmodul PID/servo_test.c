#include <avr/io.h>
#include <stdint.h>
#include <stdbool.h>
#include "servo.h"

// We reuse your clock/timer system
extern uint32_t millis(void);
extern bool ms_elapsed(uint32_t *t, uint16_t period_ms);

// UART settings
#define BAUD 115200UL
#define MYUBRR (F_CPU / 8 / BAUD - 1)

// optional: export servo output value from your servo code
extern volatile uint8_t g_last_out;

// === Simple UART helpers ===
static void uart_init(void) {
	UCSR0A = (1 << U2X0);
	UBRR0H = (uint8_t)(MYUBRR >> 8);
	UBRR0L = (uint8_t)(MYUBRR);
	UCSR0B = (1 << TXEN0);
	UCSR0C = (1 << UCSZ01) | (1 << UCSZ00);  // 8N1
}

static void uart_putc(char c) {
	while (!(UCSR0A & (1 << UDRE0)));
	UDR0 = c;
}

static void uart_uint(uint32_t x) {
	char buf[11];
	int i = 10;
	buf[i] = 0;
	do {
		buf[--i] = '0' + (x % 10);
		x /= 10;
	} while (x && i);
	while (buf[i]) uart_putc(buf[i++]);
}

static void uart_int(int32_t v) {
	if (v < 0) {
		uart_putc('-');
		v = -v;
	}
	uart_uint((uint32_t)v);
}

static void uart_str(const char *s) {
	while (*s) uart_putc(*s++);
}

// === Simple step test ===
void servo_test_init(void) {
	uart_init();
	servo_init();
	uart_str("time_ms;error;output\n");
}

void servo_test_task(void) {
	static uint32_t t_step = 0;
	static int8_t error = +15;
	static uint32_t t_print = 0;

	// Toggle error every 5 seconds
	if (ms_elapsed(&t_step, 5000)) {
		error = (error == +15) ? -15 : +15;
	}

	// Run your servo PID every loop (you can internally rate limit)
	servo_tick_run(error);

	// Print every 100 ms
	if (ms_elapsed(&t_print, 100)) {
		uart_uint(millis()); uart_putc(';');
		uart_int(error);     uart_putc(';');
		uart_uint(g_last_out); uart_putc('\n');
	}
}
