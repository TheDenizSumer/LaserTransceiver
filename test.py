from outQueue import transmitPacket
import asyncio

packet_data = 0b0100100110110 # Example packet data

import pigpio

pi = pigpio.pi()
import time

TX_PIN = 27
bit_time = 1000 #mircoseconds
BIT_PERIOD = bit_time * 1/1000000 # convert to seconds

pi.set_mode(TX_PIN, pigpio.OUTPUT)



def send_packet(bits):
    for b in bits:
        pi = pigpio.pi()
        GPIO = 17

        # 1. Define pulses (on_mask, off_mask, delay)
        pulses = []

        if b == 0:
            pulses.append(pigpio.pulse(1<<GPIO, 0, int(bit_time/2))) # Pin 17 ON for half bit time
            pulses.append(pigpio.pulse(0, 1<<GPIO, int(bit_time/2))) # Pin 17 OFF for half bit time
        else:
            pulses.append(pigpio.pulse(0, 1<<GPIO, int(bit_time/2))) # Pin 17 OFF for half bit time
            pulses.append(pigpio.pulse(1<<GPIO, 0, int(bit_time/2))) # Pin 17 ON for half bit time


    pi.wave_clear()
    pi.wave_add_generic(pulses)
    wave_id = pi.wave_create()

    pi.wave_send_repeat(wave_id) # Hardware takes over here!


packet = [0,1,0,1,1,0,0,1,0,0]
send_packet(packet)


