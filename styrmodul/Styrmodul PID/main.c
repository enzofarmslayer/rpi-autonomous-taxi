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
#include "servo.h"

#define PD2_DIR PD2
#define PD3_BRAKE PD3
#define PD6_PWM PD6
#define PD4_TRN PD4
#define BAUD 115200
#define MYUBRR (F_CPU/8/BAUD - 1)

uint8_t MAX_COUNT = 255;

void clock_init(void);


// -------------------- UART functions --------------------
void uart_init(unsigned long baud) {
	UCSR0A |= (1 << U2X0); // Double speed
	uint16_t ubrr = (F_CPU / 8 / baud) - 1;
	UBRR0H = (uint8_t)(ubrr >> 8);
	UBRR0L = (uint8_t)ubrr;
	UCSR0B = (1 << RXEN0) | (1 << TXEN0);             // Enable transmitter
	UCSR0C |= (1 << UCSZ01) | (1 << UCSZ00); // 8-bit, no parity, 1 stop
}

void uart_send_char(uint8_t c) {
	while (!(UCSR0A & (1 << UDRE0))); // Wait for empty buffer
	UDR0 = c;
}

// YOLO FUNCTION
void uart_sender(uint8_t descriptor, uint8_t data) {
	uart_send_char(descriptor);
	uart_send_char(data);
}


void pwn_init(void) {
	// Fast PWM on Timer2, non-inverting mode on OC2B
	TCCR2A = (1 << WGM21) | (1 << WGM20) | (1 << COM2B1);

	// Fast PWM mode (WGM22) + prescaler 32 (CS21, CS20)
	TCCR2B = (1 << WGM22) | (1 << CS21) | (1 << CS20);

	OCR2A = MAX_COUNT;
	OCR2B = 0;

	// Configure ports
	DDRD |= (1 << PD2_DIR) | (1 << PD3_BRAKE) | (1 << PD6_PWM);
}

void set_gas_percent(uint8_t percent, uint8_t dir) {
	if (percent < 40) percent = 0; // Min throttle to avoid stall

	PORTD &= ~(1 << PD3_BRAKE);
	
	if (dir == 0) {
		PORTD &= ~(1 << PD2_DIR);
	} else if (dir == 1) {
		PORTD |= (1 << PD2_DIR);
	}
	
	if (percent > 100) percent = 100;
	OCR2B = (uint16_t)percent*MAX_COUNT/100;
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
	uart_init(115200);
	pwn_init();
	clock_init();       // startar Timer0 1 ms-tick (för ms_elapsed, millis)
	servo_init();
	sei();              // aktiverar globala avbrott
	int8_t data_signed = 0;
	
	while (1) {
		/*
		_delay_ms(1000);
		uint8_t test1 = 'd';
		uint8_t test2 = 67;
		uart_sender(test1, test2);
		_delay_ms(1000);
		*/
		
		
		uint8_t data = uart_reciever();
		
		if(data){
			data_signed = (int8_t)data - 63;
			int8_t offset = data_signed > 0 ? data_signed : -data_signed;
			
			if (offset < 30) {
				set_gas_percent(65-(offset>>1), 0);
			} else {
				set_gas_percent(0, 0);
			}
		}
		servo_tick_run(data_signed);
		_delay_ms(10);
	}
}