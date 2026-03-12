from outQueue import transmitPacket
import asyncio

packet_data = 0b0100100110110 # Example packet data
import pigpio

pi = pigpio.pi()
GPIO_PIN = 17
BIT_RATE = 1000  # Bits per second
HALF_BIT_TIME = int(1000000 / BIT_RATE / 2) # Microseconds

def create_manchester_wave(data_byte):
    pulses = []
    
    # Iterate through each bit (MSB first)
    for i in range(7, -1, -1):
        bit = (data_byte >> i) & 1
        
        if bit == 1:
            # Bit 1: High for half, Low for half (10)
            pulses.append(pigpio.pulse(1 << GPIO_PIN, 0, HALF_BIT_TIME))
            pulses.append(pigpio.pulse(0, 1 << GPIO_PIN, HALF_BIT_TIME))
        else:
            # Bit 0: Low for half, High for half (01)
            pulses.append(pigpio.pulse(0, 1 << GPIO_PIN, HALF_BIT_TIME))
            pulses.append(pigpio.pulse(1 << GPIO_PIN, 0, HALF_BIT_TIME))
            
    pi.wave_clear()
    pi.wave_add_generic(pulses)
    return pi.wave_create()

# Usage
wave_id = create_manchester_wave(0x41) # Send ASCII 'A' (01000001)
pi.wave_send_once(wave_id)

# Cleanup after sending
while pi.wave_tx_busy():
    pass
pi.wave_delete(wave_id)