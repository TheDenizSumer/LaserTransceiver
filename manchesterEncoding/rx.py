import pigpio
import time

RX_PIN = 17
GPIO_PIN = 27
bit_time = 1000          # microseconds
half_bit = bit_time / 2

pi = pigpio.pi()

last_tick = None
last_level = None
alreadyShort = False

state = "WAIT_EDGE"
bits = []

# def decode_bit(prev, curr):
#     if prev == 0 and curr == 1:
#         return 1
#     if prev == 1 and curr == 0:
#         return 0
#     return None



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
        print("Raw:", bits)
        bits.reverse()
        count = 0
        for i in range(len(bits)-1, 0, -1):
            count += bits[i]
            if count == 2:
                bits = bits[:i]
                break
        count = 0
        for i in range(0, len(bits)):
            count += bits[i]
            if count == 2:
                bits = bits[i+1:]
                break
        print("Parsed:", "".join(bits))
        bits = []
    
    # # frame break
    # if dt > bit_time * 3:
    #     if bits:
    #         print("Frame:", bits)
    #     bits = []
    #     state = "WAIT_EDGE"
    #     last_tick = tick
    #     last_level = level
    #     return

    # # classify timing
    # short = abs(dt - half_bit) < half_bit * 0.6
    # long = abs(dt - bit_time) < half_bit



pi.set_mode(RX_PIN, pigpio.INPUT)

cb = pi.callback(RX_PIN, pigpio.EITHER_EDGE, edge_callback)

print("Manchester receiver running...")

try:
    while True:
        time.sleep(1)

except KeyboardInterrupt:
    cb.cancel()
    pi.stop()