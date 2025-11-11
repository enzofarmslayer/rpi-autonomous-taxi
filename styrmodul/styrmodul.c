/*
 * GccApplication1.c
 *
 * Created: 2025-11-04 14:00:36
 * Author : tobul865
 */ 

#define F_CPU 16000000UL

#include <avr/io.h>
#include <avr/interrupt.h>
#include <util/delay.h>
#include <stdint.h>
#include "servo_test.h"
#include "servo.h"

#define TEST

#define PD2_DIR PD2
#define PD3_BRAKE PD3
#define PD6_PWM PD6
#define PD4_TRN PD4
#define BAUD 115200
#define MYUBRR (F_CPU/8/BAUD - 1)

uint8_t MAX_PERCENT = 128;

void clock_init(void);


void pwn_init(void) {
	// Fast PWM on Timer2, non-inverting mode on OC2B
	TCCR2A = (1 << WGM21) | (1 << WGM20) | (1 << COM2B1);

	// Fast PWM mode (WGM22) + prescaler 32 (CS21, CS20)
	TCCR2B = (1 << WGM22) | (1 << CS21) | (1 << CS20);

	OCR2A = MAX_PERCENT;
	OCR2B = 0;

	// Configure ports
	DDRD |= (1 << PD2_DIR) | (1 << PD3_BRAKE) | (1 << PD6_PWM);
}

void set_gas_percent(uint8_t percent, uint8_t dir) {
	PORTD &= ~(1 << PD3_BRAKE);
	
	if (dir == 0) {
		PORTD &= ~(1 << PD2_DIR);
	} else if (dir == 1) {
		PORTD |= (1 << PD2_DIR);
	}
	
	if (percent > 100) percent = 100;
	OCR2B = (uint16_t)percent*MAX_PERCENT/100;
}

void uart_init(void) {
	UCSR0A = (1 << U2X0);
	UBRR0H = (uint8_t)(MYUBRR >> 8);
	UBRR0L = (uint8_t)MYUBRR;
	
    UCSR0B = (1 << RXEN0) | (1 << TXEN0);
	UCSR0C = (1 << UCSZ01) | (1 << UCSZ00);
}

uint8_t uart_reciever() {
	while(!(UCSR0A & (1 << RXC0)));
	return UDR0;
}

void stop() {
	PORTD |= (1 << PD3_BRAKE);
}


int main(void)
{
	//pwn_init();
	clock_init();       // startar Timer0 1 ms-tick (för ms_elapsed, millis)
    sei();              // aktiverar globala avbrott
    servo_test_init();
	
	while (1) {
		#ifdef TEST
			servo_test_task();  
		#endif
	}
}