/*
 * ultrasonic.cpp
 *
 * Created: 2025-11-11 13:30:46
 *  Author: oskna605
 */ 

#include "ultrasonic.h"
#include <avr/io.h>
#include <avr/interrupt.h>
#include <util/delay.h>

// -------------------- Globals --------------------
volatile uint16_t icr_start = 0;
volatile uint16_t icr_end = 0;
volatile uint8_t echo_done = 0;

// -------------------- Ultrasonic functions --------------------
void echo_icp_init(void) {
	DDRD  &= ~(1 << DDD6);   // ECHO pin as input
	PORTD &= ~(1 << PORTD6); // No pull-up
	TCCR1A = 0;
	TCCR1B = (1 << CS11) | (1 << ICES1); // Prescaler 8, rising edge first
	TIFR1  |= (1 << ICF1) | (1 << TOV1); // Clear flags
	TIMSK1 |= (1 << ICIE1);              // Enable Input Capture Interrupt
}

void start_sens(void) {
	DDRD |= (1 << PD5_TRIG);   // TRIG pin as output
	PORTD |= (1 << PD5_TRIG);
	_delay_us(20);             // 20µs pulse
	PORTD &= ~(1 << PD5_TRIG);
}

// -------------------- UART functions --------------------
void uart_init(unsigned long baud) {
	UCSR0A |= (1 << U2X0); // Double speed
	uint16_t ubrr = (F_CPU / 8 / baud) - 1;
	UBRR0H = (uint8_t)(ubrr >> 8);
	UBRR0L = (uint8_t)ubrr;
	UCSR0B |= (1 << TXEN0);             // Enable transmitter
	UCSR0C |= (1 << UCSZ01) | (1 << UCSZ00); // 8-bit, no parity, 1 stop
}

void uart_send_char(char c) {
	while (!(UCSR0A & (1 << UDRE0))); // Wait for empty buffer
	UDR0 = c;
}

// -------------------- ISR --------------------
ISR(TIMER1_CAPT_vect) {
	uint16_t cap = ICR1;
	if (TCCR1B & (1 << ICES1)) { // Rising edge
		icr_start = cap;
		TCCR1B &= ~(1 << ICES1); // Switch to falling edge
		} else {                     // Falling edge
		icr_end = cap;
		echo_done = 1;
		TCCR1B |= (1 << ICES1);  // Switch back to rising edge
	}
}
