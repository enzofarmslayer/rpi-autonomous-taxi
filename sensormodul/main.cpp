
/*
 * sensormodul.cpp
 *
 * Created: 2025-11-06 11:14:19
 * Author : tobul865, oskna605
 */ 

#define F_CPU 16000000UL
#include <avr/io.h>
#include <avr/interrupt.h>
#include <stdint.h>
#include <util/delay.h>
#include <stdio.h>
#include "odometry.h"
#include "ultrasonic.h"

int main(void)
{	
	
	// Ultrasonic Sensor
	echo_icp_init();
	uart_init(115200);
	sei();
	DDRD |= (1 << PD5_TRIG) | (1 << PD1);
	PORTD &= ~(1 << PD5_TRIG);
	PORTD &= ~(1 << PD1);
	uint8_t obstacle_present = 0;
	uint8_t has_sent_obstacle = 0;
	
	// Hall sensors
	timer0_init();
	hall_left_init();
	hall_right_init();
	
	Odometry odom = {0};
	reset_odometry();
	sei();
	
	while (1)
	{	
		// Hall sensor
		_delay_ms(1000);
		update_odometry(&odom);

		// Hall sensor testing 
		/*
		uint32_t dist_mm = (uint32_t)(odom.average_distance_mm + 0.5); 
		uint32_t speed_mm_s = (uint32_t)(odom.average_speed_mm_s + 0.5);

		char buf[100]; 
		sprintf(buf, "L=%lu, R=%lu, Dist=%lumm, Speed=%lumm/s\n", 
				odom.left_pulses, 
				odom.right_pulses, 
				dist_mm,
				speed_mm_s); 
		for (char *p = buf; *p; p++) uart_send_char(*p); 
		*/
		
		// Send odometry data, beginning with just distance travelled 
		int distance_cm = (int)((odom.average_distance_mm / 10.0) + 0.5); // convert mm to cm
		int speed_cm_s = (int)((odom.average_speed_mm_s / 10.0) + 0.5);   // convert mm/s to cm/s
	
		volatile int puls = odom.right_pulses;
		//uart_send_char((char)puls);
		
		volatile int distance = (int)(puls *1.25);
		
		if (distance >= 100) {
			uart_send_char('1');
		}
		
		// Ultrasonic sensor
		//echo_done = 0;
		//start_sens();
		//
		//uint16_t timeout = 60000;
		//while(!echo_done && timeout--){}
		//
		//if (echo_done) {
			//uint16_t start = icr_start;
			//uint16_t end = icr_end;
			//
			//uint16_t length = (end >= start) ? (end - start) : (end + 0x10000 - start);
			//
			//if (length < 2500) {
				//obstacle_present = 1;
				//} else {
				//obstacle_present = 0;
			//}
		//}
		//if (obstacle_present && !has_sent_obstacle) {
			//uart_send_char('1');
			//has_sent_obstacle = 1;
			//} else if(!obstacle_present && has_sent_obstacle) {
			//uart_send_char('0');
			//has_sent_obstacle = 0;
		//}
		//_delay_ms(20);
	}
}


