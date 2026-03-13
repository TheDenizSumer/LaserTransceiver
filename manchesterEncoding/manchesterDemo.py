import pigpio
import time

RX_PIN = 17
bit_time = 1000          # microseconds
half_bit = bit_time / 2

pi = pigpio.pi()

last_tick = None
last_level = None
alreadyShort = False

state = "WAIT_EDGE"
bits = []

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
        from tx import transmit_binary_manchester
        transmit_binary_manchester(int("".join(map(str, bits)), 2))

except KeyboardInterrupt:
    cb.cancel()
    pi.stop()