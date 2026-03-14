import pigpio
import time

# --- Configuration ---
GPIO_PIN = 27       # BCM numbering
BIT_RATE = 1000     # Bits per second (1kbps)

HALF_BIT_TIME = int(1000000 / BIT_RATE / 2)

pi = pigpio.pi()

if not pi.connected:
    print("Error: pigpiod daemon is not running. Run 'sudo pigpiod'.")
    exit()

def transmit_binary_manchester(packet_data):
    length = packet_data.bit_length() - 1
    bit_string = bin(packet_data)[3:]

    new_data = int(bit_string, 2)

    b_str = bin(new_data)[2:]

    add_start = "000101" + b_str
    add_end = add_start + "101000"

    packet_data = int(add_end, 2)
    length = packet_data.bit_length()
    pi.set_mode(GPIO_PIN, pigpio.OUTPUT)
    pi.wave_clear() 
    
    pulses = []
        # Data bits (LSB first)
    for i in range(length):
        bit = True if (packet_data >> i) & 1 else False
        if bit == 0:
            # Bit 0: High for half-bit, then Low for half-bit
            pulses.append(pigpio.pulse(1 << GPIO_PIN, 0, HALF_BIT_TIME))
            pulses.append(pigpio.pulse(0, 1 << GPIO_PIN, HALF_BIT_TIME))
        elif bit == 1:
            # Bit 1: Low for half-bit, then High for half-bit
            pulses.append(pigpio.pulse(0, 1 << GPIO_PIN, HALF_BIT_TIME))
            pulses.append(pigpio.pulse(1 << GPIO_PIN, 0, HALF_BIT_TIME))
    
    # Load all pulses into the buffer
    pi.wave_add_generic(pulses)
    
    # Create the wave ID
    wave_id = pi.wave_create()
    
    if wave_id >= 0:
        print(f"Sending: {bin(packet_data)}")
        pi.wave_send_once(wave_id)
        
        # Wait for transmission to finish so the script doesn't close too early
        while pi.wave_tx_busy():
            time.sleep(0.01)
            
        print("Transmission complete.")
        pi.wave_delete(wave_id) # Clean up the Wave ID to save memory
    else:
        print("Failed to create waveform. Too many pulses?")

# --- Main Execution ---

UserInput = input("Send Message > ")
from bin2text import text_to_bits
bitsIn = text_to_bits(UserInput)

bits_val = 0
for bit in bitsIn:
    # Shift existing bits left by 1, then OR with the new bit
    bits_val = (bits_val << 1) | bit

#bits_val |= (1 << bits_val.bit_length())
print(bits_val)
try:
    # my_data = 0b111000001100101011011100110100101110011011100000110111101110000

    transmit_binary_manchester(bits_val)
    
finally:
    pi.stop()