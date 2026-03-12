import pigpio
import time

RX_PIN = 13
bit_time = 10          # microseconds
half_bit = bit_time / 2

pi = pigpio.pi()

last_tick = None
last_level = None

half_seen = False
bits = []

def edge_callback(gpio, level, tick):
    global last_tick, last_level, half_seen, bits

    if last_tick is None:
        last_tick = tick
        last_level = level
        return

    dt = pigpio.tickDiff(last_tick, tick)

    # Detect frame break (3 bit-times silence)
    if dt > bit_time * 3:
        if bits:
            print("Frame:", bits)
        bits = []
        half_seen = False
        last_tick = tick
        last_level = level
        return

    # Detect half-bit transition
    if abs(dt - half_bit) < half_bit * 0.5:

        if half_seen:
            # This is the mid-bit transition
            if last_level == 0 and level == 1:
                bits.append(1)
            elif last_level == 1 and level == 0:
                bits.append(0)

            half_seen = False
        else:
            half_seen = True

    # Detect full-bit transition (missed half)
    elif abs(dt - bit_time) < half_bit:
        if last_level == 0 and level == 1:
            bits.append(1)
        elif last_level == 1 and level == 0:
            bits.append(0)

        half_seen = False

    last_tick = tick
    last_level = level


pi.set_mode(RX_PIN, pigpio.INPUT)

cb = pi.callback(RX_PIN, pigpio.EITHER_EDGE, edge_callback)

print("Listening for Manchester data...")

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    cb.cancel()
    pi.stop()