import pigpio
import time

# --- Configuration ---
GPIO_PIN = 27       # BCM numbering
BIT_RATE = 1000     # Bits per second (1kbps)
# Calculate half-bit time in microseconds
HALF_BIT_TIME = int(1000000 / BIT_RATE / 2)

pi = pigpio.pi()

if not pi.connected:
    print("Error: pigpiod daemon is not running. Run 'sudo pigpiod'.")
    exit()

def transmit_binary_manchester(binary_str):
    """
    Converts a string of '1's and '0's into a Manchester Waveform.
    Standard (IEEE 802.3): 1 = High-to-Low (10), 0 = Low-to-High (01)
    """
    pi.set_mode(GPIO_PIN, pigpio.OUTPUT)
    pi.wave_clear()  # Clear any previous pulse data
    
    pulses = []
    
    # Optional: Add a 'Preamble' (8 bits of alternating 1/0) to help receivers sync
    # For simplicity, we'll skip to the data, but you can add it here.

    for bit in binary_str:
        if bit == '1':
            # Bit 1: High for half-bit, then Low for half-bit
            pulses.append(pigpio.pulse(1 << GPIO_PIN, 0, HALF_BIT_TIME))
            pulses.append(pigpio.pulse(0, 1 << GPIO_PIN, HALF_BIT_TIME))
        elif bit == '0':
            # Bit 0: Low for half-bit, then High for half-bit
            pulses.append(pigpio.pulse(0, 1 << GPIO_PIN, HALF_BIT_TIME))
            pulses.append(pigpio.pulse(1 << GPIO_PIN, 0, HALF_BIT_TIME))
    
    # Load all pulses into the buffer
    pi.wave_add_generic(pulses)
    
    # Create the wave ID
    wave_id = pi.wave_create()
    
    if wave_id >= 0:
        print(f"Sending: {binary_str}")
        pi.wave_send_once(wave_id)
        
        # Wait for transmission to finish so the script doesn't close too early
        while pi.wave_tx_busy():
            time.sleep(0.01)
            
        print("Transmission complete.")
        pi.wave_delete(wave_id) # Clean up the Wave ID to save memory
    else:
        print("Failed to create waveform. Too many pulses?")

# --- Main Execution ---
try:
    # Example: Send the letter 'A' in binary (01000001)
    my_data = "01000001"
    transmit_binary_manchester(my_data)
    
finally:
    pi.stop()