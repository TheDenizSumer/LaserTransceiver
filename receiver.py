import pigpio
import time

RX_PIN = 17
bit_time = 1000          # microseconds
half_bit = bit_time / 2

pi = pigpio.pi()

last_tick = None
last_level = None
alreadyShort = False

bits = []

def edge_callback(gpio, level, tick):
    global last_tick, last_level, state, bits, alreadyShort

    if last_tick is None:
        last_tick = tick
        last_level = level
        return

    dt = pigpio.tickDiff(last_tick, tick)
    last_tick = tick
    if dt < half_bit*1.2:
        if bits == []:
            bits.append(0)
        elif alreadyShort:
            alreadyShort = False
            bits.insert(0, bits[-1])
        else:
            alreadyShort = True
    elif dt < bit_time*1.2:
        alreadyShort = False
        bits.insert(0, bits[-1] ^ 1)
    else:
        alreadyShort = False
        packet = int("".join(map(str,bits)), 2)
        bits = []

pi.set_mode(RX_PIN, pigpio.INPUT)
cb = pi.callback(RX_PIN, pigpio.EITHER_EDGE, edge_callback)


try:
    while True:
        time.sleep(1)

except KeyboardInterrupt:
    cb.cancel()
    pi.stop()