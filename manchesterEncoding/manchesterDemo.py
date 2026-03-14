import pigpio
import time

RX_PIN = 17
GPIO_PIN = 27

BIT_RATE = 1000        # Bits per second (1kbps)
HALF_BIT_TIME = int(1000000 / BIT_RATE / 2)

bit_time = HALF_BIT_TIME * 2          # microseconds
half_bit = HALF_BIT_TIME

pi = pigpio.pi()

last_tick = None
last_level = None
alreadyShort = False

state = "WAIT_EDGE"
bits = []

def transmit_binary_manchester(packet_data):
    pi.set_mode(GPIO_PIN, pigpio.OUTPUT)
    pi.wave_clear() 
    
    pulses = []
        # Data bits (LSB first)
    for i in range(64):
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

def text_to_bits(text):
    bits = []
    for char in text:
        bin_val = format(ord(char), '08b') 
        bits.extend([int(bit) for bit in bin_val])
    return bits

def bits_to_text(bits):
    chars = []
    for i in range(0, len(bits), 8):
        byte_chunk = bits[i:i+8]
        if len(byte_chunk) < 8:
            break
        
        bit_str = "".join(map(str, byte_chunk))
        chars.append(chr(int(bit_str, 2)))
        
    return "".join(chars)


def edge_callback(gpio, level, tick):
    global last_tick, last_level, state, bits, alreadyShort

    if last_tick is None:
        last_tick = tick
        last_level = level
        return

    dt = pigpio.tickDiff(last_tick, tick)
    last_tick = tick
    # print(dt)
    if dt < half_bit*1.2:
        if bits == []:
            bits.append(0)
        elif alreadyShort:
            alreadyShort = False
            bits.append(bits[-1])
        else:
            alreadyShort = True
    elif dt < bit_time*1.2:
        alreadyShort = False
        bits.append(bits[-1] ^ 1)
    else:
        alreadyShort = False
        if bits:
            bits = bits[1:-1]

            bits.reverse()
            print("From the other one: ", bits_to_text(bits))
        print("Frame:", bits)

        bits = []
    

pi.set_mode(RX_PIN, pigpio.INPUT)

cb = pi.callback(RX_PIN, pigpio.EITHER_EDGE, edge_callback)

print("Manchester receiver running...")

try:
    while True:
        UserInput = input('What would you like to send as a message (q to quit)>')
        if UserInput == 'q':
            break
        bits.insert(0, 0)
        bits.append(0)
        bits = text_to_bits(UserInput)
        print(int("".join(map(str, bits)), 2))
        transmit_binary_manchester(int("".join(map(str, bits)), 2))

except KeyboardInterrupt:
    cb.cancel()
    pi.stop()